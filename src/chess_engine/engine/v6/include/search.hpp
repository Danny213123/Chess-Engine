#pragma once

#include "board.hpp"
#include "movegen.hpp"
#include <atomic>
#include <chrono>

namespace v6 {

// =============================================================================
// SEARCH INFO - Shared state for search control
// =============================================================================

struct SearchInfo {
    // Time control
    std::chrono::steady_clock::time_point start_time;
    int time_limit_ms = 5000;  // Default 5 seconds
    
    // Search statistics
    std::atomic<uint64_t> nodes{0};
    int depth = 0;
    int seldepth = 0;
    int score = 0;
    Move best_move = MOVE_NONE;
    
    // Stop control
    std::atomic<bool> stopped{false};
    
    // Thread count
    int num_threads = 1;
    
    void reset() {
        nodes = 0;
        depth = 0;
        seldepth = 0;
        score = 0;
        best_move = MOVE_NONE;
        stopped = false;
        start_time = std::chrono::steady_clock::now();
    }
    
    bool check_time() {
        if (stopped) return true;
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - start_time).count();
        if (elapsed >= time_limit_ms) {
            stopped = true;
            return true;
        }
        return false;
    }
    
    int elapsed_ms() const {
        auto now = std::chrono::steady_clock::now();
        return static_cast<int>(std::chrono::duration_cast<std::chrono::milliseconds>(now - start_time).count());
    }
};

// =============================================================================
// SEARCH RESULT
// =============================================================================

struct SearchResult {
    Move best_move = MOVE_NONE;
    int score = 0;
    int depth = 0;
    uint64_t nodes = 0;
    int time_ms = 0;
    std::vector<Move> pv;
    
    int nps() const { return time_ms > 0 ? static_cast<int>(nodes * 1000 / time_ms) : 0; }
};

// =============================================================================
// MAIN SEARCH FUNCTIONS
// =============================================================================

// Single-threaded search
SearchResult search(Board& board, int time_limit_ms, bool verbose = false);

// Multi-threaded search with OpenMP (Lazy SMP)
SearchResult search_parallel(Board& board, int time_limit_ms, int num_threads, bool verbose = false);

// Iterative deepening
SearchResult iterative_deepening(Board& board, SearchInfo& info, bool verbose = false);

// Alpha-beta with all pruning techniques
int alpha_beta(Board& board, int depth, int alpha, int beta, 
               SearchInfo& info, int ply, std::vector<Move>& pv,
               bool do_null = true);

// Quiescence search
int quiescence(Board& board, int alpha, int beta, SearchInfo& info, int ply);

// =============================================================================
// SEARCH CONSTANTS
// =============================================================================

// Null Move Pruning
constexpr int NULL_MOVE_R = 4;
constexpr int NULL_MOVE_MIN_DEPTH = 3;

// Late Move Reductions
constexpr int LMR_FULL_DEPTH_MOVES = 4;
constexpr int LMR_REDUCTION_LIMIT = 3;

// Late Move Pruning
constexpr int LMP_DEPTH = 8;

// Futility Pruning margins
constexpr std::array<int, 6> FUTILITY_MARGIN = {0, 100, 200, 300, 400, 500};

// Reverse Futility Pruning margins
constexpr std::array<int, 6> RFP_MARGIN = {0, 80, 160, 240, 320, 400};

// Aspiration window
constexpr int ASPIRATION_WINDOW = 25;

// Pre-computed LMR reduction table
extern int LMR_TABLE[64][64];
void init_lmr_table();

} // namespace v6
