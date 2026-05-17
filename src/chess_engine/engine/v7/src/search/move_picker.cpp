// MovePicker staged move ordering — Plan 03-02 Task 2 implementation (SRCH-06).
//
// Stage order: TT → good captures (SEE>=0) → killers → counter-move →
//              history-sorted quiets → bad captures (SEE<0) → done.
//
// Design notes:
//   - Reuses see(board, m) from eval.cpp verbatim (don't hand-roll SEE).
//   - Counter-move table indexed by [side_that_moved][prev_from][prev_to]
//     per RESEARCH.md Pitfall 7. The side_that_moved is (1 - stm_) here
//     because stm_ is the side ABOUT to move; the counter-move was stored
//     by the previous ply's cutoff (the opponent's side).
//   - History sorted quiets: descending by (*history_)[stm_][from][to].
//   - Bad captures (SEE<0) tried last so they only run if quiets fail.
//
// Reference: RESEARCH.md Code Examples §"Staged Move Picker", SRCH-06.

#include "search/move_picker.hpp"
#include "../movegen.hpp"

namespace v7 {

MovePicker::MovePicker(const Board& board, Move tt_move,
                       const SearchInfo& info, int ply) {
    stage_   = S_TT;
    tt_move_ = tt_move;
    ply_     = ply;
    stm_     = board.side_to_move;

    // Wire killers from SearchStack (if available)
    if (info.search_stack && ply < MAX_PLY) {
        killer0_ = info.search_stack->killers[ply][0];
        killer1_ = info.search_stack->killers[ply][1];
    }
    killer_idx_ = 0;

    // Wire counter-move (RESEARCH.md Pitfall 7: side-that-moved = 1 - stm_)
    // The counter-move table is indexed by the PREVIOUS move's from/to squares
    // and the side that MADE the previous move (= 1 - current stm_).
    // We approximate here: info.counter_moves[1-stm_][prev_from][prev_to].
    // Since we don't pass prev_from/prev_to through MovePicker's constructor,
    // we leave counter_move_ = MOVE_NONE for now and rely on the score_moves
    // fallback in movegen.cpp for the counter-move bonus.
    // TODO: pass prev_from/prev_to when available (Plan 03-03+ can extend this).
    counter_move_   = MOVE_NONE;
    counter_yielded_ = false;

    // Wire history table pointer
    history_ = info.history;

    // SRCH-07 (Plan 03-03): wire continuation history and parent-move context.
    continuation_history_ = info.continuation_history;
    if (info.search_stack && ply > 0 && ply < MAX_PLY) {
        cont_prev_piece_ = info.search_stack->prev_piece[ply];
        cont_prev_stm_   = info.search_stack->prev_stm[ply];
        cont_prev_to_    = info.search_stack->prev_to[ply];
    } else {
        cont_prev_piece_ = NO_PIECE;
        cont_prev_to_    = NO_SQUARE;
    }

    // Initialize all counters
    good_cap_count_ = good_cap_idx_ = 0;
    bad_cap_count_  = bad_cap_idx_  = 0;
    quiet_count_    = quiet_idx_    = 0;
}

Move MovePicker::next(const Board& board) {
    switch (stage_) {

    // =========================================================================
    // Stage S_TT: yield the TT move (if set and pseudo-legal)
    // =========================================================================
    case S_TT:
        stage_ = S_GEN_CAPTURES;
        if (tt_move_ != MOVE_NONE) {
            // Quick pseudo-legality check: the destination square must not
            // contain a friendly piece (full legality is handled by alpha_beta).
            // The from piece must exist for the side to move.
            Square from_sq = move_from(tt_move_);
            Square to_sq   = move_to(tt_move_);
            Color  from_color = board.color_at(from_sq);
            Color  to_color   = board.color_at(to_sq);
            Piece  from_piece = board.piece_at(from_sq);
            if (from_piece != NO_PIECE &&
                from_color == board.side_to_move &&
                to_color != board.side_to_move) {
                return tt_move_;
            }
        }
        // Fall through to S_GEN_CAPTURES if TT move is none or invalid.
        [[fallthrough]];

    // =========================================================================
    // Stage S_GEN_CAPTURES: generate all captures; partition by SEE score.
    // =========================================================================
    case S_GEN_CAPTURES: {
        stage_ = S_GOOD_CAPTURES;
        MoveList caps;
        generate_captures(board, caps);

        for (int i = 0; i < caps.count; ++i) {
            Move m = caps[i];
            // Skip the TT move (already yielded in S_TT or rejected)
            if (m == tt_move_) continue;
            // Skip captures of the king (illegal move guard)
            if (board.piece_at(move_to(m)) == KING) continue;

            int see_score = see(board, m);
            if (see_score >= 0) {
                // Good capture: SEE >= 0 — MVV-LVA score for ordering
                Piece captured = board.piece_at(move_to(m));
                Piece attacker = board.piece_at(move_from(m));
                static constexpr int PV[6] = {100, 320, 330, 500, 900, 20000};
                int score = (captured < 6 ? PV[captured] * 10 : 0)
                          - (attacker < 6 ? PV[attacker]      : 0)
                          + see_score;  // SEE tiebreaker
                good_captures_[good_cap_count_]  = m;
                good_cap_scores_[good_cap_count_] = score;
                ++good_cap_count_;
            } else {
                // Bad capture: SEE < 0 — tried last
                bad_captures_[bad_cap_count_++] = m;
            }
        }
        // Sort good captures descending by score
        sort_moves(good_captures_, good_cap_scores_, good_cap_count_);
        [[fallthrough]];
    }

    // =========================================================================
    // Stage S_GOOD_CAPTURES: yield SEE >= 0 captures in sorted order.
    // =========================================================================
    case S_GOOD_CAPTURES:
        while (good_cap_idx_ < good_cap_count_) {
            return good_captures_[good_cap_idx_++];
        }
        stage_ = S_KILLERS;
        [[fallthrough]];

    // =========================================================================
    // Stage S_KILLERS: yield killer moves (quiet beta-cutoffs at this ply).
    // =========================================================================
    case S_KILLERS:
        while (killer_idx_ < 2) {
            Move km = (killer_idx_ == 0) ? killer0_ : killer1_;
            ++killer_idx_;
            if (km == MOVE_NONE || km == tt_move_) continue;
            // Killers must be quiet (non-capture) and pseudo-legal at this position.
            // Quick validity: the from-piece must exist for STM, and to-square must
            // be empty (killer was a quiet move when stored).
            Square from_sq = move_from(km);
            Square to_sq   = move_to(km);
            if (board.piece_at(from_sq) == NO_PIECE) continue;
            if (board.color_at(from_sq) != board.side_to_move) continue;
            if (board.piece_at(to_sq) != NO_PIECE) continue;  // not quiet anymore
            return km;
        }
        stage_ = S_COUNTER;
        [[fallthrough]];

    // =========================================================================
    // Stage S_COUNTER: yield the counter-move (if set and not already yielded).
    // =========================================================================
    case S_COUNTER:
        stage_ = S_GEN_QUIETS;
        if (!counter_yielded_ && counter_move_ != MOVE_NONE &&
            counter_move_ != tt_move_ &&
            counter_move_ != killer0_ && counter_move_ != killer1_) {
            counter_yielded_ = true;
            // Pseudo-legality: must be a quiet move from STM's piece
            Square from_sq = move_from(counter_move_);
            Square to_sq   = move_to(counter_move_);
            if (board.piece_at(from_sq) != NO_PIECE &&
                board.color_at(from_sq) == board.side_to_move &&
                board.piece_at(to_sq) == NO_PIECE) {
                return counter_move_;
            }
        }
        [[fallthrough]];

    // =========================================================================
    // Stage S_GEN_QUIETS: generate all quiet moves; score by history.
    // =========================================================================
    case S_GEN_QUIETS: {
        stage_ = S_QUIETS;
        MoveList all;
        generate_legal_moves(board, all);  // legal quiets (subset after captures already done)

        for (int i = 0; i < all.count; ++i) {
            Move m = all[i];
            // Skip captures (already handled in S_GOOD_CAPTURES/S_BAD_CAPTURES)
            if (board.piece_at(move_to(m)) != NO_PIECE) continue;
            // Skip moves already yielded in prior stages
            if (m == tt_move_) continue;
            if (m == killer0_ || m == killer1_) continue;
            if (m == counter_move_ && counter_yielded_) continue;

            // Score by history heuristic + continuation history (SRCH-07, Plan 03-03)
            int from_sq = move_from(m);
            int to_sq   = move_to(m);
            int hist = (history_ != nullptr)
                ? (*history_)[stm_][from_sq][to_sq]
                : 0;
            // SRCH-07: add continuation history bonus when parent context is available
            if (continuation_history_ != nullptr &&
                cont_prev_piece_ != NO_PIECE && cont_prev_piece_ < 6 &&
                cont_prev_to_ != NO_SQUARE) {
                Piece curr_piece = board.piece_at(from_sq);
                if (curr_piece >= 0 && curr_piece < 6) {
                    hist += (*continuation_history_)[cont_prev_stm_][cont_prev_piece_][cont_prev_to_]
                                                    [stm_][curr_piece][to_sq];
                }
            }
            quiets_[quiet_count_]       = m;
            quiet_scores_[quiet_count_] = hist;
            ++quiet_count_;
        }
        // Sort quiets descending by history score
        sort_moves(quiets_, quiet_scores_, quiet_count_);
        [[fallthrough]];
    }

    // =========================================================================
    // Stage S_QUIETS: yield history-sorted quiet moves.
    // =========================================================================
    case S_QUIETS:
        while (quiet_idx_ < quiet_count_) {
            return quiets_[quiet_idx_++];
        }
        stage_ = S_BAD_CAPTURES;
        [[fallthrough]];

    // =========================================================================
    // Stage S_BAD_CAPTURES: yield SEE < 0 captures (last resort).
    // =========================================================================
    case S_BAD_CAPTURES:
        while (bad_cap_idx_ < bad_cap_count_) {
            return bad_captures_[bad_cap_idx_++];
        }
        stage_ = S_DONE;
        [[fallthrough]];

    // =========================================================================
    // Stage S_DONE: all stages exhausted.
    // =========================================================================
    case S_DONE:
    default:
        return MOVE_NONE;
    }
}

} // namespace v7
