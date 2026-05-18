#pragma once

#include "types.hpp"
#include <atomic>
#include <cstddef>
#include <cstdint>

namespace v7 {

// =============================================================================
// TRANSPOSITION TABLE ENTRY
// =============================================================================

enum TTFlag : uint8_t {
    TT_NONE = 0,
    TT_EXACT = 1,
    TT_ALPHA = 2,  // Upper bound (failed low)
    TT_BETA = 3    // Lower bound (failed high)
};

// PUBLIC output struct returned by TT::probe(). Signature-compatible with V6's
// TTEntry surface — search.cpp callsites populate this via probe() and read
// best_move/score/depth/flag/age unchanged from Plan 03-01's call shape.
//
// This is NOT what is stored on the slab. Storage is a packed `AtomicEntry`
// (two std::atomic<uint64_t> slots — see below). probe() unpacks into this.
struct TTEntry {
    uint64_t key;       // Zobrist hash (restored by probe = the queried hash)
    Move best_move;     // Best move from this position (uint16_t)
    int16_t score;      // Score (mate-distance correction done on SEARCH side)
    int8_t depth;       // Search depth
    uint8_t flag;       // TT_EXACT, TT_ALPHA, TT_BETA
    uint8_t age;        // Generation for replacement

    bool is_valid(uint64_t hash, int min_depth) const {
        return key == hash && depth >= min_depth;
    }
};

// =============================================================================
// LOCKLESS TT — Hyatt-Mann XOR pattern (Plan 03-05, D-07 / D-09 / PAR-01/02)
// =============================================================================
//
// AtomicEntry is the on-slab storage. Two relaxed std::atomic<uint64_t> slots
// per bucket:
//   xkey = hash ^ data           — sole correctness validator
//   data = packed payload        — Move|score|depth|flag|age fit in uint64_t
//
// Probe loads both atomics with memory_order_relaxed. Validation:
//     (xkey ^ data) == hash      — if torn (one writer raced), this is
//                                   silently treated as a miss (RESEARCH.md
//                                   Pattern 1; T-03-01 in 03-05 STRIDE).
// Store writes data FIRST, then xkey — a concurrent probe between the two
// stores sees the new data XORed with the old xkey, validation fails, miss.
//
// Bit-pack layout (D-09 — byte-identical footprint to V6 TTEntry: 16 bytes):
//     bits  0..15  — Move (uint16_t)
//     bits 16..31  — score (int16_t reinterpreted as uint16_t)
//     bits 32..39  — depth (int8_t reinterpreted as uint8_t)
//     bits 40..47  — flag (uint8_t — low 2 bits used)
//     bits 48..55  — age (uint8_t — generation_)
//     bits 56..63  — reserved/pad (zero)
//
// std::atomic<uint64_t> on every supported platform (MSVC, libc++, libstdc++)
// is standard-layout, trivially-default-constructible (required since C++20
// and de-facto since C++11), so memset(0) over the slab is well-defined.

struct AtomicEntry {
    std::atomic<uint64_t> xkey;
    std::atomic<uint64_t> data;
};

// D-09: sizeof(AtomicEntry) MUST equal V6 TTEntry's 16-byte footprint so
// cache-line packing math (4 entries per 64B line) is preserved verbatim.
static_assert(sizeof(AtomicEntry) == 16,
              "AtomicEntry must match V6 TTEntry 16-byte footprint (D-09)");

class TT {
public:
    explicit TT(size_t size_mb = 64);
    ~TT();

    // Probe the table — XOR-validated lockless load.
    // On hit: populates `out` with unpacked fields and returns true.
    // On miss (slot empty OR (xkey ^ data) != hash, including torn reads):
    //   returns false; `out` is left zero-initialized by the caller.
    bool probe(uint64_t hash, TTEntry& out);

    // Store an entry — Hyatt-Mann XOR write with age-then-depth replacement.
    //
    // Replacement policy (D-07):
    //   - same key in slot          → always replace (refresh)
    //   - different key, stale age  → always replace (older generation loses)
    //   - different key, same age   → replace only if new depth >= old depth
    void store(uint64_t hash, Move best_move, int score, int depth, TTFlag flag);

    // Clear the slab (memset 0) and reset hit/miss counters.
    void clear();

    // Bump generation counter (called once per search by Engine::search).
    void new_search() { ++generation_; }

    // Stats
    size_t size() const { return num_entries_; }
    uint64_t hits() const { return hit_count_.load(std::memory_order_relaxed); }
    uint64_t misses() const { return miss_count_.load(std::memory_order_relaxed); }
    // Convenience aliases kept for any older callers expecting V6's names.
    uint64_t hit_count() const { return hits(); }
    uint64_t miss_count() const { return misses(); }
    double hit_rate() const {
        uint64_t h = hits();
        uint64_t total = h + misses();
        return total > 0 ? static_cast<double>(h) / total : 0.0;
    }

    // num_entries: exposed so tests can construct deterministic slot collisions
    // (any two hashes with the same `hash % num_entries` map to the same slot).
    size_t num_entries() const { return num_entries_; }

private:
    AtomicEntry* entries_;
    size_t num_entries_;
    uint8_t generation_ = 0;

    mutable std::atomic<uint64_t> hit_count_{0};
    mutable std::atomic<uint64_t> miss_count_{0};

    size_t index(uint64_t hash) const { return hash % num_entries_; }
};

// Plan 03-01 D-01: g_tt global removed. All search-side TT access goes through
// SearchInfo::tt (non-owning pointer to Engine::tt_). This severs search.cpp's
// dependency on the global so Plan 03-05's lockless TT rewrite is file-disjoint
// from search.cpp. See PATTERNS.md Shared Pattern 4 for the pointer contract.

} // namespace v7
