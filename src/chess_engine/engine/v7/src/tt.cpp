#include "tt.hpp"
#include <cstdint>
#include <cstring>
#include <new>

#ifdef _MSC_VER
#include <malloc.h>  // For _aligned_malloc/_aligned_free on MSVC
#endif

namespace v7 {

// Plan 03-05 — Lockless Hyatt-Mann XOR TT (PAR-01 / PAR-02).
//
// All atomic ops use memory_order_relaxed per D-07. The XOR validator is the
// sole correctness primitive — no acquire/release fences. Any torn read on a
// concurrent store causes (xkey ^ data) != hash, which is silently treated as
// a TT miss. The cost of a miss is one extra search node; correctness is
// preserved (T-03-01 mitigation in 03-05 STRIDE).

namespace {

// Bit-pack helpers (D-09 layout, private to this TU).
//
// Layout (uint64_t data field):
//   bits  0..15 — Move (uint16_t)
//   bits 16..31 — score (int16_t reinterpreted as uint16_t)
//   bits 32..39 — depth (int8_t reinterpreted as uint8_t)
//   bits 40..47 — flag  (uint8_t)
//   bits 48..55 — age   (uint8_t)
//   bits 56..63 — reserved (zero)
inline uint64_t pack_data(Move m, int16_t score, int8_t depth, uint8_t flag, uint8_t age) {
    return  (uint64_t(uint16_t(m))                      )       // 0..15
         |  (uint64_t(uint16_t(score))            << 16)        // 16..31
         |  (uint64_t(uint8_t(depth))             << 32)        // 32..39
         |  (uint64_t(flag)                       << 40)        // 40..47
         |  (uint64_t(age)                        << 48);       // 48..55
}

inline void unpack_data(uint64_t data,
                        Move& m, int16_t& score,
                        int8_t& depth, uint8_t& flag, uint8_t& age) {
    m     =  Move(   uint16_t( data        & 0xFFFFu));
    score = int16_t( uint16_t((data >> 16) & 0xFFFFu));
    depth =  int8_t( uint8_t ((data >> 32) & 0xFFu));
    flag  =  uint8_t(         (data >> 40) & 0xFFu);
    age   =  uint8_t(         (data >> 48) & 0xFFu);
}

}  // namespace

TT::TT(size_t size_mb) {
    size_t size_bytes = size_mb * 1024 * 1024;
    num_entries_ = size_bytes / sizeof(AtomicEntry);

    // Align to cache line (64 bytes) — verbatim from V6 tt.cpp:18-23.
#ifdef _MSC_VER
    entries_ = static_cast<AtomicEntry*>(_aligned_malloc(num_entries_ * sizeof(AtomicEntry), 64));
#else
    entries_ = static_cast<AtomicEntry*>(std::aligned_alloc(64, num_entries_ * sizeof(AtomicEntry)));
#endif
    if (!entries_) {
        throw std::bad_alloc();
    }

    clear();
}

TT::~TT() {
#ifdef _MSC_VER
    _aligned_free(entries_);
#else
    std::free(entries_);
#endif
}

void TT::clear() {
    // memset(0) is well-defined here: std::atomic<uint64_t> is standard-layout
    // and trivially-default-constructible on every supported platform (MSVC,
    // libc++, libstdc++). All-zero bit-pattern represents (xkey=0, data=0)
    // which validates as hash==0 only — for hash==0 the bucket appears as a
    // "hit on key 0 with empty payload" but since flag=TT_NONE in that case
    // and TT_NONE is never stored by store(), search-side probe consumers
    // never act on the zeroed entry. TSan stress harness (Task 2 / 3) is the
    // canonical verification.
    std::memset(entries_, 0, num_entries_ * sizeof(AtomicEntry));
    hit_count_.store(0, std::memory_order_relaxed);
    miss_count_.store(0, std::memory_order_relaxed);
}

bool TT::probe(uint64_t hash, TTEntry& out) {
    AtomicEntry& slot = entries_[index(hash)];

    // Hyatt-Mann XOR probe (RESEARCH.md Pattern 1 canonical form).
    // Both loads are memory_order_relaxed — the XOR validator is the only
    // correctness primitive (D-07 / PAR-02).
    uint64_t xkey = slot.xkey.load(std::memory_order_relaxed);
    uint64_t data = slot.data.load(std::memory_order_relaxed);

    // XOR validation: any torn read produces (xkey ^ data) != hash → silent miss.
    if ((xkey ^ data) != hash) {
        miss_count_.fetch_add(1, std::memory_order_relaxed);
        return false;
    }

    // Validated — unpack the data payload into the output struct.
    unpack_data(data, out.best_move, out.score, out.depth, out.flag, out.age);
    out.key = hash;

    // Treat slot-never-written (flag == TT_NONE) as a miss so legacy callers
    // that rely on the V6 `flag != TT_NONE` semantic stay correct. Search.cpp
    // checks tt_entry.flag explicitly downstream, but counting this as a miss
    // keeps the hit/miss accounting consistent with V6.
    if (out.flag == TT_NONE) {
        miss_count_.fetch_add(1, std::memory_order_relaxed);
        return false;
    }

    hit_count_.fetch_add(1, std::memory_order_relaxed);
    return true;
}

void TT::store(uint64_t hash, Move best_move, int score, int depth, TTFlag flag) {
    AtomicEntry& slot = entries_[index(hash)];

    // Read current contents to decide replacement (relaxed loads only — D-07).
    uint64_t old_xkey = slot.xkey.load(std::memory_order_relaxed);
    uint64_t old_data = slot.data.load(std::memory_order_relaxed);
    uint64_t old_hash = old_xkey ^ old_data;

    // Replacement policy (D-07 — age-then-depth):
    //   1. Same key in slot     → always replace (refresh).
    //   2. Different key, stale → always replace (older generation loses).
    //   3. Different key, same  → replace only if new depth >= old depth.
    bool should_replace;
    if (old_hash == hash) {
        should_replace = true;                                 // refresh
    } else {
        uint8_t old_age   = uint8_t((old_data >> 48) & 0xFFu);
        int8_t  old_depth = int8_t(uint8_t((old_data >> 32) & 0xFFu));
        if (old_age != generation_) {
            should_replace = true;                              // stale → replace
        } else {
            should_replace = (depth >= int(old_depth));         // same age tie-break
        }
    }
    if (!should_replace) return;

    // Pack new payload and write. Narrow score/depth/flag to their packed widths.
    uint64_t new_data = pack_data(best_move,
                                  static_cast<int16_t>(score),
                                  static_cast<int8_t>(depth),
                                  static_cast<uint8_t>(flag),
                                  generation_);

    // STORE ORDER IS LOAD-BEARING: data first, xkey second.
    // A concurrent probe between the two stores sees `(old_xkey ^ new_data) != hash`
    // and treats it as a miss — the XOR validator catches the torn write.
    slot.data.store(new_data, std::memory_order_relaxed);
    slot.xkey.store(hash ^ new_data, std::memory_order_relaxed);
}

} // namespace v7
