// V7 search header — fork of v6/include/search.hpp with the four pre-C1
// must-fixes layered on top (FOUND-04, SRCH-02, SRCH-13, SRCH-14, SRCH-15).
//
// V6 AUDIT (per plan 03 task 1 step 1):
//   - V6 does NOT implement score_to_tt / score_from_tt anywhere
//     (grepped v6/src/tt.cpp + v6/include/tt.hpp + v6/src/search.cpp — only
//     reference to MATE inside search is line 190's `return in_check
//     ? -MATE_SCORE + ply : DRAW_SCORE;`). V7 ADDS the inline functions and
//     wraps every TT.store/TT.probe site in src/search.cpp (SRCH-13 active
//     patch, NOT inheritance).
//   - V6 has NO repetition stack on Board or SearchInfo. V7 ADDS RepStack as
//     a struct owned by Engine (NOT Board — perft-clean invariant from plan
//     02 checker issue #3) and threads it through SearchInfo (SRCH-14 active
//     patch, NOT inheritance).

#pragma once

#include "board.hpp"
#include "movegen.hpp"
#include <atomic>
#include <chrono>
#include <cstdint>
#include <vector>

namespace v7 {

// =============================================================================
// REPETITION STACK (SRCH-14)
// =============================================================================
//
// Lives on Engine (see include/engine.hpp `RepStack rep_stack_;`). NEVER on
// Board (checker issue #3 — Board::make_move/unmake_move stay perft-clean).
// SearchInfo holds a non-owning pointer; alpha_beta pushes/pops at the
// make_move/unmake_move site INSIDE the search, NOT inside Board itself.
//
// CAP=1024 covers the longest plausible game (well over the 50-move-rule
// reset window) plus search ply depth. Overflow silently clamps (no-op
// push) — the consequence is one missed repetition detection in a
// pathologically deep search, not a crash.

struct RepStack {
    static constexpr int CAP = 1024;
    uint64_t data[CAP];
    int top = 0;
    void push(uint64_t h) { if (top < CAP) data[top++] = h; }
    void pop()            { if (top > 0)   --top; }
    void clear()          { top = 0; }
};

// =============================================================================
// SEARCH INFO — Shared state for search control
// =============================================================================
//
// V6 fields kept verbatim. V7 adds (FOUND-04 / SRCH-14 / SRCH-15):
//   - external_stop   : non-owning pointer to Engine::stop_flag_; survives
//                       SearchInfo::reset(), so Python-side stop() observable
//                       from another thread even after a new search begins.
//   - soft_deadline_ms: ID iteration gate (TimeManager-set; ~50% of budget).
//   - hard_deadline_ms: mid-iteration interrupt (TimeManager-set; ~90% of
//                       budget for the 10% safety margin per SRCH-15).
//   - rep_stack       : non-owning pointer to Engine::rep_stack_; alpha_beta
//                       reads/writes for in-tree 3-fold detection.

struct SearchInfo {
    // Time control
    std::chrono::steady_clock::time_point start_time;
    int time_limit_ms = 5000;

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

    // --- V7 additions ---
    std::atomic<bool>* external_stop = nullptr;  // FOUND-04 — points at Engine::stop_flag_
    int soft_deadline_ms = 0;                    // SRCH-15 — TimeManager-set; 0 = unused
    int hard_deadline_ms = 0;                    // SRCH-15 — TimeManager-set; 0 = unused
    RepStack* rep_stack = nullptr;               // SRCH-14 — points at Engine::rep_stack_

    void reset() {
        nodes = 0;
        depth = 0;
        seldepth = 0;
        score = 0;
        best_move = MOVE_NONE;
        // Do NOT clobber external_stop or rep_stack (preserve across reset).
        // Propagate external_stop into local `stopped` so a stop set BEFORE
        // search begins is respected from the first node poll.
        if (external_stop) stopped.store(external_stop->load(std::memory_order_relaxed));
        else               stopped.store(false);
        start_time = std::chrono::steady_clock::now();
    }

    bool check_time() {
        if (stopped.load(std::memory_order_relaxed)) return true;
        // FOUND-04 — external (Python) stop takes precedence over the clock.
        if (external_stop && external_stop->load(std::memory_order_relaxed)) {
            stopped.store(true, std::memory_order_relaxed);
            return true;
        }
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
                           now - start_time).count();
        // SRCH-15 — hard_deadline_ms takes precedence over the legacy V6
        // time_limit_ms when set, so the TimeManager's safety-margin clamp
        // is honored end-to-end.
        int hard = (hard_deadline_ms > 0) ? hard_deadline_ms : time_limit_ms;
        if (elapsed >= hard) {
            stopped.store(true, std::memory_order_relaxed);
            return true;
        }
        return false;
    }

    int elapsed_ms() const {
        auto now = std::chrono::steady_clock::now();
        return static_cast<int>(std::chrono::duration_cast<std::chrono::milliseconds>(
                                    now - start_time).count());
    }
};

// =============================================================================
// SEARCH RESULT
// =============================================================================

struct SearchResultFull {
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

// Single-threaded search (fork of V6 search()).
SearchResultFull search(Board& board, int time_limit_ms, bool verbose = false);

// Iterative deepening with bounded aspiration re-search (SRCH-01, SRCH-02).
SearchResultFull iterative_deepening(Board& board, SearchInfo& info, bool verbose = false);

// Alpha-beta (PVS) with pruning, repetition detection (SRCH-14), and
// mate-TT correction (SRCH-13) at every store/probe.
int alpha_beta(Board& board, int depth, int alpha, int beta,
               SearchInfo& info, int ply, std::vector<Move>& pv,
               bool do_null = true);

// Quiescence search.
int quiescence(Board& board, int alpha, int beta, SearchInfo& info, int ply);

// =============================================================================
// SEARCH CONSTANTS
// =============================================================================

// Null Move Pruning (V6 verbatim)
constexpr int NULL_MOVE_R = 4;
constexpr int NULL_MOVE_MIN_DEPTH = 3;

// Late Move Reductions (V6 verbatim)
constexpr int LMR_FULL_DEPTH_MOVES = 4;
constexpr int LMR_REDUCTION_LIMIT = 3;

// Late Move Pruning (V6 verbatim)
constexpr int LMP_DEPTH = 8;

// Futility Pruning margins (V6 verbatim)
constexpr std::array<int, 6> FUTILITY_MARGIN = {0, 100, 200, 300, 400, 500};

// Reverse Futility Pruning margins (V6 verbatim)
constexpr std::array<int, 6> RFP_MARGIN = {0, 80, 160, 240, 320, 400};

// Aspiration window (V6 verbatim; SRCH-02 adds bounded re-search count)
constexpr int ASPIRATION_WINDOW = 25;
constexpr int ASPIRATION_MAX_REWIDENS = 4;  // SRCH-02 — cap before full-window fallback

// 50-move TT cutoff guard threshold (SRCH-14 second part). When
// board.halfmove_clock crosses this, TT probe is still consulted for the
// best-move ordering hint but the cached score is NOT used as a cutoff —
// the cached score does not reflect the imminent 50-move-rule draw.
constexpr int MAX_HALFMOVE_FOR_TT_CUTOFF = 80;

// Pre-computed LMR reduction table (V6 verbatim)
extern int LMR_TABLE[64][64];
void init_lmr_table();

// =============================================================================
// MATE-TT SCORE CORRECTION (SRCH-13, PITFALLS #1)
// =============================================================================
//
// V6 does NOT do this — V7 wraps EVERY TT.store and TT.probe consumer site
// in src/search.cpp. Without these, a mate-in-N score stored at one ply and
// probed at another ply silently reports the wrong mate distance, causing
// the engine to either claim mates that don't exist or miss real ones.
//
// MATE_SCORE comes from types.hpp (=29000). Anything within 256 of it is
// treated as a mate score; the constant matches V6's mate-detection band.

constexpr int MATE_IN_MAX_PLY = MATE_SCORE - 256;

inline int score_to_tt(int score, int ply) {
    if (score >=  MATE_IN_MAX_PLY) return score + ply;
    if (score <= -MATE_IN_MAX_PLY) return score - ply;
    return score;
}

inline int score_from_tt(int score, int ply) {
    if (score >=  MATE_IN_MAX_PLY) return score - ply;
    if (score <= -MATE_IN_MAX_PLY) return score + ply;
    return score;
}

// =============================================================================
// TIME MANAGER (SRCH-15)
// =============================================================================
//
// Allocates a per-move budget with ≥10% safety margin. soft_deadline gates
// new ID iterations between depths; hard_deadline interrupts mid-iteration
// via SearchInfo::check_time().

struct TimeManager {
    int hard_deadline_ms;
    int soft_deadline_ms;
    static TimeManager allocate(int remaining_ms, int increment_ms, int moves_to_go = 30);
};

} // namespace v7
