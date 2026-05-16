#pragma once

#include "types.hpp"
#include <atomic>
#include <memory>

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

struct TTEntry {
    uint64_t key;       // Zobrist hash
    Move best_move;     // Best move from this position
    int16_t score;      // Score (may be adjusted for mate)
    int8_t depth;       // Search depth
    uint8_t flag;       // TT_EXACT, TT_ALPHA, TT_BETA
    uint8_t age;        // Generation for replacement

    bool is_valid(uint64_t hash, int min_depth) const {
        return key == hash && depth >= min_depth;
    }
};

// =============================================================================
// LOCK-FREE TRANSPOSITION TABLE (Thread-safe for OpenMP)
// =============================================================================

class TT {
public:
    TT(size_t size_mb = 64);
    ~TT();

    // Probe the table
    bool probe(uint64_t hash, TTEntry& entry) const;

    // Store an entry (thread-safe)
    void store(uint64_t hash, Move best_move, int score, int depth, TTFlag flag);

    // Clear the table
    void clear();

    // New generation (for replacement strategy)
    void new_search() { ++generation; }

    // Stats
    size_t size() const { return num_entries; }
    uint64_t hits() const { return hit_count.load(); }
    uint64_t misses() const { return miss_count.load(); }
    double hit_rate() const {
        uint64_t total = hit_count + miss_count;
        return total > 0 ? static_cast<double>(hit_count) / total : 0.0;
    }

private:
    TTEntry* entries;
    size_t num_entries;
    uint8_t generation = 0;

    mutable std::atomic<uint64_t> hit_count{0};
    mutable std::atomic<uint64_t> miss_count{0};

    size_t index(uint64_t hash) const { return hash % num_entries; }
};

// Global TT instance (legacy free-function access, mirrors V6).
// Plan 03 uses the Engine::tt_ member instead of this global; this global is
// retained for verbatim-fork parity and legacy callers.
extern TT g_tt;

} // namespace v7
