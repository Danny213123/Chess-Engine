#pragma once

// MovePicker skeleton — created by Plan 03-01 cross-Wave-2 scaffold.
// Plan 03-02 Task 2 fills in the stage-dispatch body per
// RESEARCH.md Code Examples §"Staged Move Picker".
//
// Consumed by: Plan 03-02 Task 2 — staged move picker body (SRCH-06).
// Constructor and next() stub live in src/search/move_picker.cpp.

#include "../board.hpp"
#include "../search.hpp"

namespace v7 {

class MovePicker {
public:
    // Stage enumeration — all stages declared here so Plan 03-02 Task 2
    // only fills bodies, not the class interface (Wave 2 file-conflict safety).
    enum Stage {
        S_TT,             // Yield TT move first (if any)
        S_GEN_CAPTURES,   // Generate captures
        S_GOOD_CAPTURES,  // Yield SEE >= 0 captures (MVV-LVA order)
        S_KILLERS,        // Yield killer moves
        S_COUNTER,        // Yield counter-move (Plan 03-02 Task 2)
        S_GEN_QUIETS,     // Generate quiet moves
        S_QUIETS,         // Yield history-ordered quiet moves
        S_BAD_CAPTURES,   // Yield remaining captures (SEE < 0)
        S_DONE            // Exhausted all stages
    };

    // Constructor: binds board state, TT move, info, and ply.
    // Plan 03-02 Task 2 adds private state initialization (stage_, ply_,
    // move buffers, history pointer, etc.).
    MovePicker(const Board& board, Move tt_move, const SearchInfo& info, int ply);

    // next: returns the next move to try, or MOVE_NONE when exhausted.
    // Stub returns MOVE_NONE; Plan 03-02 Task 2 fills in stage dispatch.
    Move next(const Board& board);

private:
    // Plan 03-02 Task 2 fills in private state.
    Stage stage_ = S_TT;  // current stage
    // Additional private state (tt_move_, ply_, history ptr, etc.)
    // will be added by Plan 03-02 without changing the public interface.
};

} // namespace v7
