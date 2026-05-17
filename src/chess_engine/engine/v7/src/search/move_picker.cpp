// MovePicker stub — created by Plan 03-01 cross-Wave-2 scaffold.
// Plan 03-02 Task 2 fills in the stage-dispatch body per
// RESEARCH.md Code Examples §"Staged Move Picker".
//
// Consumed by: Plan 03-02 Task 2 — staged move picker body (SRCH-06).
// This TU is wired into V7_SOURCES in CMakeLists.txt so it compiles
// and links as part of the v7_engine module.

#include "search/move_picker.hpp"

namespace v7 {

MovePicker::MovePicker(const Board& /*board*/, Move /*tt_move*/,
                       const SearchInfo& /*info*/, int /*ply*/) {
    // Plan 03-02 Task 2 fills in ctor body:
    //   stage_ = S_TT;
    //   tt_move_ = tt_move;
    //   ply_ = ply;
    //   history_ = info.history;
    //   ... (move buffers, counts)
    stage_ = S_TT;
}

Move MovePicker::next(const Board& /*board*/) {
    // Stub: always signal "no more moves" until Plan 03-02 Task 2 fills in
    // the full stage-dispatch (S_TT → S_GEN_CAPTURES → S_GOOD_CAPTURES →
    // S_KILLERS → S_COUNTER → S_GEN_QUIETS → S_QUIETS → S_BAD_CAPTURES).
    // Returning MOVE_NONE here is safe: callers that use MovePicker will
    // fall back to generate_legal_moves until Plan 03-02 implements the body.
    (void)stage_;  // suppress unused-member-warning until Plan 03-02
    return MOVE_NONE;
}

} // namespace v7
