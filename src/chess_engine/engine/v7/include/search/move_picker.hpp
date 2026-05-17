#pragma once

// MovePicker — staged move ordering (Plan 03-02, SRCH-06).
// Created as a skeleton by Plan 03-01; body implemented in Plan 03-02 Task 2.
//
// Stage order: TT → good captures (SEE>=0) → killers → counter-move →
//              history-sorted quiets → bad captures (SEE<0) → done.
//
// RESEARCH.md Pitfall 7: counter-move indexed by side that just moved
//   ([1 - side_to_move][prev_from][prev_to]).
//
// Reuses the existing see(board, m) at eval.cpp:430 — do NOT re-implement.
// History scores from persistent Engine::history_[2][64][64].

#include "../board.hpp"
#include "../search.hpp"
#include "../eval.hpp"

namespace v7 {

class MovePicker {
public:
    // Stage enumeration — all stages declared here for stable interface.
    enum Stage {
        S_TT,             // Yield TT move first (if any)
        S_GEN_CAPTURES,   // Generate captures
        S_GOOD_CAPTURES,  // Yield SEE >= 0 captures (by score order)
        S_KILLERS,        // Yield killer moves
        S_COUNTER,        // Yield counter-move
        S_GEN_QUIETS,     // Generate quiet moves
        S_QUIETS,         // Yield history-ordered quiet moves
        S_BAD_CAPTURES,   // Yield remaining captures (SEE < 0)
        S_DONE            // Exhausted all stages
    };

    // Constructor: binds board state, TT move, info, and ply.
    // Plan 03-02 Task 2 fills private state initialization.
    MovePicker(const Board& board, Move tt_move, const SearchInfo& info, int ply);

    // next: returns the next move to try, or MOVE_NONE when exhausted.
    // Stage dispatch: S_TT → S_GOOD_CAPTURES → S_KILLERS → S_COUNTER →
    //                 S_QUIETS → S_BAD_CAPTURES → S_DONE.
    Move next(const Board& board);

private:
    Stage stage_;

    // TT move
    Move tt_move_;
    bool tt_yielded_ = false;

    // Ply for killer/counter-move lookup
    int ply_;

    // Killers from SearchStack::killers[ply][0..1]
    Move killer0_ = MOVE_NONE;
    Move killer1_ = MOVE_NONE;
    int killer_idx_ = 0;  // 0 = try killer0, 1 = try killer1, 2 = done

    // Counter-move (RESEARCH.md Pitfall 7: indexed by side-that-moved / prev_from / prev_to)
    Move counter_move_ = MOVE_NONE;
    bool counter_yielded_ = false;

    // History pointer for quiet move ordering
    const int (*history_)[64][64] = nullptr;  // Engine::history_[2][64][64]
    Color stm_ = WHITE;  // side to move in this position

    // SRCH-07 (Plan 03-03): continuation history for quiet move scoring boost.
    const int (*continuation_history_)[6][64][2][6][64] = nullptr;  // -> Engine::continuation_history_[2]
    Piece cont_prev_piece_ = NO_PIECE;  // parent move's piece (for continuation indexing)
    Color cont_prev_stm_   = WHITE;     // parent move's stm
    Square cont_prev_to_   = NO_SQUARE; // parent move's destination

    // Capture move buffers (split into good and bad by SEE score)
    static constexpr int MAX_MOVES = 256;
    Move good_captures_[MAX_MOVES];
    int  good_cap_scores_[MAX_MOVES];
    int  good_cap_count_ = 0;
    int  good_cap_idx_ = 0;

    Move bad_captures_[MAX_MOVES];
    int  bad_cap_count_ = 0;
    int  bad_cap_idx_ = 0;

    // Quiet move buffers
    Move quiets_[MAX_MOVES];
    int  quiet_scores_[MAX_MOVES];
    int  quiet_count_ = 0;
    int  quiet_idx_ = 0;

    // Helper: insertion-sort a move buffer by score descending
    static void sort_moves(Move* moves, int* scores, int count) {
        for (int i = 1; i < count; ++i) {
            Move  tmp_m = moves[i];
            int   tmp_s = scores[i];
            int j = i - 1;
            while (j >= 0 && scores[j] < tmp_s) {
                moves[j + 1]  = moves[j];
                scores[j + 1] = scores[j];
                --j;
            }
            moves[j + 1]  = tmp_m;
            scores[j + 1] = tmp_s;
        }
    }
};

} // namespace v7
