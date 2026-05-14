#include "tt.hpp"
#include <cstring>
#include <new>

#ifdef _MSC_VER
#include <malloc.h>  // For _aligned_malloc/_aligned_free on MSVC
#endif

namespace v6 {

// Global TT instance (64MB default)
TranspositionTable TT(64);

TranspositionTable::TranspositionTable(size_t size_mb) {
    size_t size_bytes = size_mb * 1024 * 1024;
    num_entries = size_bytes / sizeof(TTEntry);
    
    // Align to cache line (64 bytes)
#ifdef _MSC_VER
    entries = static_cast<TTEntry*>(_aligned_malloc(num_entries * sizeof(TTEntry), 64));
#else
    entries = static_cast<TTEntry*>(std::aligned_alloc(64, num_entries * sizeof(TTEntry)));
#endif
    if (!entries) {
        throw std::bad_alloc();
    }
    
    clear();
}

TranspositionTable::~TranspositionTable() {
#ifdef _MSC_VER
    _aligned_free(entries);
#else
    std::free(entries);
#endif
}

void TranspositionTable::clear() {
    std::memset(entries, 0, num_entries * sizeof(TTEntry));
    hit_count = 0;
    miss_count = 0;
}

bool TranspositionTable::probe(uint64_t hash, TTEntry& entry) const {
    size_t idx = index(hash);
    const TTEntry& stored = entries[idx];
    
    if (stored.key == hash && stored.flag != TT_NONE) {
        entry = stored;
        hit_count.fetch_add(1, std::memory_order_relaxed);
        return true;
    }
    
    miss_count.fetch_add(1, std::memory_order_relaxed);
    return false;
}

void TranspositionTable::store(uint64_t hash, Move best_move, int score, int depth, TTFlag flag) {
    size_t idx = index(hash);
    TTEntry& stored = entries[idx];
    
    // Replacement strategy: always replace if:
    // 1. Same position (same hash)
    // 2. New entry has higher depth
    // 3. Old entry is from previous generation
    bool should_replace = (stored.key == hash) ||
                          (stored.depth < depth) ||
                          (stored.age != generation);
    
    if (should_replace) {
        stored.key = hash;
        stored.best_move = best_move;
        stored.score = static_cast<int16_t>(score);
        stored.depth = static_cast<int8_t>(depth);
        stored.flag = static_cast<uint8_t>(flag);
        stored.age = generation;
    }
}

} // namespace v6
