// V7 search.cpp — fork of v6/src/search.cpp with the four pre-C1 must-fixes:
//   - FOUND-04 : SearchInfo.external_stop polled in check_time (header)
//   - SRCH-02  : aspiration re-search capped at ASPIRATION_MAX_REWIDENS
//   - SRCH-13  : score_to_tt / score_from_tt wrapping at every TT site
//   - SRCH-14  : in-tree 3-fold repetition via Engine-owned RepStack;
//                50-move TT cutoff guard at halfmove_clock >= 80
//   - SRCH-15  : TimeManager::allocate + soft deadline gating ID iterations
//
// Plan 03-01 additions (D-01, D-03) — three Phase 1 perf bug fixes:
//   - Bug #1: info.max_depth replaces the old info.depth upper-bound contract;
//     iterative_deepening writes info.depth as per-iteration counter only.
//   - Bug #2: per-call killers/history allocations removed; persistent state
//     accessed via info.search_stack->killers[ply] and (*info.history)[...].
//   - Bug #3: std::vector<Move> pv allocations in alpha_beta/iterative_deepening
//     replaced with triangular array on SearchStack (info.search_stack->pv[ply]).
//   - g_tt migration: all four g_tt callsites replaced with info.tt-> (D-01).
//
// V6 PARITY: PVS core, LMR, NMP, RFP, LMP, futility, SEE pruning, move
// ordering — all inherited verbatim. The diff vs V6 is the patches above
// plus the namespace rename v6 -> v7.

#include "search.hpp"
#include "eval.hpp"
#include "tt.hpp"
#include "engine.hpp"   // for the Engine class (used only via SearchInfo pointers)
#include <algorithm>
#include <cmath>
#include <iostream>
#if defined(_OPENMP)
#include <omp.h>
#else
static inline int omp_get_thread_num() { return 0; }
#endif

namespace v7 {

// =============================================================================
// LMR TABLE INITIALIZATION (V6 verbatim)
// =============================================================================

int LMR_TABLE[64][64];

void init_lmr_table() {
    for (int depth = 1; depth < 64; ++depth) {
        for (int moves = 1; moves < 64; ++moves) {
            LMR_TABLE[depth][moves] = static_cast<int>(
                0.5 + std::log(static_cast<double>(depth)) *
                      std::log(static_cast<double>(moves)) / 2.2
            );
        }
    }
}

// =============================================================================
// TIME MANAGER (SRCH-15)
// =============================================================================
//
// Budget = remaining/moves_to_go + 95% of increment. Clamped to remaining*9/10
// so the search always leaves at least 10% of the wall-clock budget unused —
// covers OS scheduling jitter, GIL re-acquisition, and the time it takes for
// stop() to propagate through the % 4096 polling cadence.

TimeManager TimeManager::allocate(int remaining_ms, int increment_ms, int moves_to_go) {
    int mtg = std::max(moves_to_go, 1);
    int budget = remaining_ms / mtg + (increment_ms * 95 / 100);
    int margin_cap = remaining_ms * 9 / 10;   // ≥10% safety margin
    if (budget > margin_cap) budget = margin_cap;
    if (budget < 1) budget = 1;
    return TimeManager{budget, budget / 2};
}

// =============================================================================
// QUIESCENCE SEARCH (V6 verbatim — inherits external_stop via check_time)
// =============================================================================

int quiescence(Board& board, int alpha, int beta, SearchInfo& info, int ply) {
    info.nodes.fetch_add(1, std::memory_order_relaxed);

    if (info.stopped || (info.nodes % 4096 == 0 && info.check_time())) {
        return 0;
    }

    info.seldepth = std::max(info.seldepth, ply);

    // Stand pat
    int stand_pat = evaluate(board);

    if (stand_pat >= beta) {
        return beta;
    }

    if (stand_pat > alpha) {
        alpha = stand_pat;
    }

    // Delta pruning
    if (stand_pat + 1000 < alpha) {
        return alpha;
    }

    // Generate captures only
    MoveList moves;
    generate_captures(board, moves);

    for (int i = 0; i < moves.count; ++i) {
        Move m = moves[i];
        Piece captured = board.piece_at(move_to(m));
        if (captured == KING) {
            continue;
        }

        // SEE pruning
        if (see(board, m) < 0) {
            continue;
        }

        // Make move
        int prev_castling = board.castling_rights;
        Square prev_ep = board.ep_square;
        int prev_halfmove = board.halfmove_clock;

        board.make_move(m);

        if (board.is_attacked(board.king_square(Color(1 - board.side_to_move)),
                              board.side_to_move)) {
            board.unmake_move(m, captured, prev_castling, prev_ep, prev_halfmove);
            continue;
        }

        int score = -quiescence(board, -beta, -alpha, info, ply + 1);

        board.unmake_move(m, captured, prev_castling, prev_ep, prev_halfmove);

        if (info.stopped) return 0;

        if (score >= beta) {
            return beta;
        }

        if (score > alpha) {
            alpha = score;
        }
    }

    return alpha;
}

// =============================================================================
// ALPHA-BETA SEARCH (PVS) — V6 + SRCH-13 + SRCH-14 + Plan 03-01 Bug fixes
//                          + Plan 03-02 search refinements
// =============================================================================
//
// Plan 03-01 changes vs prior V7:
//   - `pv` parameter REMOVED (Bug #3 fix) — triangular PV lives on
//     info.search_stack->pv[ply][*] / pv_length[ply].
//   - killers/history parameter REMOVED from inner scope (Bug #2 fix) —
//     accessed via info.search_stack->killers[ply] and (*info.history)[side].
//   - g_tt replaced with info.tt-> at all four callsites (D-01).
//
// Plan 03-02 additions (SRCH-03/04/05/11/12):
//   - SRCH-03: Adaptive null-move pruning with zugzwang guard and depth >= 12
//     verification re-search (replaces fixed-R null-move block).
//   - SRCH-04: Two-level LMR re-search (reduced ZW → full-depth ZW → full-window PV).
//   - SRCH-05: RFP before move gen; futility in move loop; LMP move-count cutoff.
//   - SRCH-11: IIR — reduces depth by 1 at PV/cut nodes when tt_move == MOVE_NONE.
//   - SRCH-12: Recapture extension (additive to existing check extension).
//   - UseCheckExt gates the check extension (D-06).

int alpha_beta(Board& board, int depth, int alpha, int beta,
               SearchInfo& info, int ply,
               bool do_null) {

    if (info.stopped || (info.nodes % 4096 == 0 && info.check_time())) {
        return 0;
    }

    bool is_root = (ply == 0);
    bool in_check = board.is_in_check();

    // -------------------------------------------------------------------------
    // SRCH-14 — In-tree 3-fold repetition detection.
    //
    // RepStack lives on Engine (NOT Board — perft-clean invariant). The
    // wrapper in engine.cpp seeds the stack with the root position; each
    // make_move below pushes the post-move hash; this loop walks back two
    // half-moves at a time (same side to move) up to halfmove_clock plies,
    // counting matches. >=2 prior matches + current = 3-fold repetition.
    //
    // NOT at root: the wrapper still pushes the root once, but we only
    // detect repetition strictly inside the tree (ply > 0).
    // -------------------------------------------------------------------------
    if (!is_root && info.rep_stack != nullptr && board.halfmove_clock >= 4) {
        const RepStack& rs = *info.rep_stack;
        int reps = 0;
        int lo = rs.top - board.halfmove_clock;
        if (lo < 0) lo = 0;
        for (int i = rs.top - 2; i >= lo; i -= 2) {
            if (rs.data[i] == board.hash) {
                if (++reps >= 2) {
                    return DRAW_SCORE;
                }
            }
        }
    }

    // D-03 Bug #3 fix: initialize triangular PV length at this ply.
    // pv_length[ply] = 0 means "no best move yet at this ply".
    if (info.search_stack && ply < MAX_PLY) {
        info.search_stack->pv_length[ply] = ply;  // empty PV at entry
        // SRCH-12 (Plan 03-02): initialize prev_capture_sq for child plies.
        // Child ply (ply+1) reads prev_capture_sq[ply+1] to learn what this
        // move's destination square was (if a capture). Initialize to NO_SQUARE
        // so non-capture parent moves don't spuriously trigger recapture ext.
        if (ply + 1 < MAX_PLY) {
            info.search_stack->prev_capture_sq[ply + 1] = NO_SQUARE;
        }
        // SRCH-07 (Plan 03-03): initialize prev_piece/prev_stm/prev_to for child plies.
        // At ply == 0, there is no parent move, so initialize child's parent-context
        // fields to invalid values. alpha_beta at ply+1 reads these to score quiets.
        if (ply == 0 && ply + 1 < MAX_PLY) {
            info.search_stack->prev_piece[ply + 1] = NO_PIECE;
            info.search_stack->prev_stm[ply + 1]   = WHITE;  // placeholder
            info.search_stack->prev_to[ply + 1]     = NO_SQUARE;
        }
    }

    // SRCH-12 (Plan 03-02): Check extension — gated by UseCheckExt (D-06).
    // Preserved from prior V7; now toggle-controlled for UCI ablation.
    // UseRecaptureExt fires per-move in the move loop below.
    if (in_check && (!info.options || info.options->UseCheckExt)) {
        depth++;
    }

    // Quiescence at leaf
    if (depth <= 0) {
        return quiescence(board, alpha, beta, info, ply);
    }

    info.nodes.fetch_add(1, std::memory_order_relaxed);
    info.seldepth = std::max(info.seldepth, ply);

    // -------------------------------------------------------------------------
    // TT probe (SRCH-13: score_from_tt; SRCH-14: 50-move guard)
    // D-01: use info.tt-> instead of g_tt (g_tt migration).
    //
    // SRCH-08 CRITICAL INVARIANT (RESEARCH.md Code Examples §SE, Plan 03-03):
    // When excluded_move[ply] != MOVE_NONE, we are inside a singular verification
    // re-search. The TT probe MUST be SKIPPED in this case — otherwise the cached
    // score from the un-excluded search would be returned to the caller, making
    // the singular test meaningless (the excluded move's score would contaminate
    // the "all other moves" result). See also: IIR skip of excluded_move[ply] in
    // Plan 03-02 search.cpp for the same pattern.
    // -------------------------------------------------------------------------
    TTEntry tt_entry{};  // zero-initialize so tt_entry.flag/depth/score are valid even on miss
    Move tt_move = MOVE_NONE;
    bool excluded = (info.search_stack && ply < MAX_PLY &&
                     info.search_stack->excluded_move[ply] != MOVE_NONE);
    if (!excluded && info.tt && info.tt->probe(board.hash, tt_entry)) {
        tt_move = tt_entry.best_move;
        // SRCH-14 — when near the 50-move boundary, still use the TT for move
        // ordering (tt_move above) but do NOT cut off on the cached score;
        // it doesn't know about the looming 50-move-rule draw.
        bool fifty_guard = (board.halfmove_clock >= MAX_HALFMOVE_FOR_TT_CUTOFF);
        if (!is_root && !fifty_guard && tt_entry.depth >= depth) {
            // SRCH-13 — convert stored mate-distance back into ply-relative score
            int tt_score = score_from_tt(static_cast<int>(tt_entry.score), ply);
            if (tt_entry.flag == TT_EXACT) {
                // D-03 Bug #3 fix: update triangular PV with TT move
                if (info.search_stack && ply < MAX_PLY && tt_move != MOVE_NONE) {
                    info.search_stack->pv[ply][ply] = tt_move;
                    info.search_stack->pv_length[ply] = ply + 1;
                }
                return tt_score;
            } else if (tt_entry.flag == TT_ALPHA && tt_score <= alpha) {
                return alpha;
            } else if (tt_entry.flag == TT_BETA && tt_score >= beta) {
                return beta;
            }
        }
    }

    // -------------------------------------------------------------------------
    // SRCH-11 (Plan 03-02) — Internal Iterative Reduction (IIR).
    //
    // When there is no TT move at a PV or cut node at depth >= 4, the search
    // won't have a good move to try first — so the full depth is wasteful.
    // IIR reduces depth by 1 to spend less time on unsupported guesses.
    // Applied AFTER TT probe and BEFORE move generation.
    // Skip if excluded_move is set (Plan 03-03 singular extensions forward-compat).
    //
    // Reference: RESEARCH.md D2 §3.9, SRCH-11.
    // -------------------------------------------------------------------------
    bool is_pv = (beta - alpha > 1);  // Non-zero window = PV node
    if (info.options && info.options->UseIIR &&
        tt_move == MOVE_NONE && depth >= 4 && (is_pv || !do_null) &&
        !(info.search_stack && ply < MAX_PLY &&
          info.search_stack->excluded_move[ply] != MOVE_NONE)) {
        depth -= 1;  // SRCH-11: reduce depth at nodes with no TT move guidance
    }

    int static_eval = evaluate(board);

    // -------------------------------------------------------------------------
    // SRCH-05 (Plan 03-02) — Reverse Futility Pruning (RFP).
    //
    // At shallow non-check non-PV nodes, if the static eval already exceeds
    // beta by the depth-indexed margin, return the static eval immediately.
    // This avoids expanding nodes that are almost certainly going to fail high.
    //
    // rfp_margin(depth) = 100 * depth (canonical; may be re-scaled in Phase 4 TUNE-09).
    // Reference: RESEARCH.md D2 §3.3, SRCH-05.
    // -------------------------------------------------------------------------
    // SRCH-05 RFP margin constants (constexpr to keep them near usage; tune in Phase 4):
    constexpr int RFP_MARGIN_PER_DEPTH = 100;  // centipawns per depth — TUNE-09 target
    if (info.options && info.options->UseRFP &&
        !in_check && !is_root && !is_pv && depth <= 8) {
        int margin = RFP_MARGIN_PER_DEPTH * depth;
        if (static_eval - margin >= beta) {
            return static_eval;  // RFP: prune — RESEARCH.md D2 §3.3
        }
    } else if (!info.options && !in_check && !is_root && depth <= 5) {
        // Legacy V6 fallback when options pointer is null (free-function search path):
        int margin = RFP_MARGIN[depth];
        if (static_eval - margin >= beta) {
            return static_eval - margin;
        }
    }

    // -------------------------------------------------------------------------
    // SRCH-03 (Plan 03-02) — Adaptive Null-Move Pruning with zugzwang guard.
    //
    // Replaces the fixed-R null-move block from V6/prior-V7 with:
    //   R = 3 + depth/4 + min((static_eval - beta) / 200, 3)
    //
    // Zugzwang guard (RESEARCH.md Pitfall 4): skip null move when the side
    // to move has no non-pawn material (KPK and similar endgames where passing
    // a tempo is catastrophic). Without this guard, null-move would give a
    // false beta-cutoff in positions where only the obligation to move is losing.
    //
    // Verification re-search (depth >= 12): when null_score >= beta at high
    // depth, do a second search at the same R to confirm the cutoff is real
    // (Stockfish-style — avoids zurichess zugzwang phantom cutoffs).
    //
    // Reference: RESEARCH.md Pitfall 4, D-04 SRCH-03.
    // -------------------------------------------------------------------------
    bool zugzwang_risk = (board.non_pawn_material(board.side_to_move) == 0);  // RESEARCH.md Pitfall 4
    if (info.options && info.options->UseNullMove &&
        do_null && !in_check && !zugzwang_risk &&
        depth >= NULL_MOVE_MIN_DEPTH && static_eval >= beta) {
        // Adaptive R: base 3, +depth/4, +up to 3 for large static_eval surplus
        int R = 3 + depth / 4 + std::min((static_eval - beta) / 200, 3);

        // Make null move
        Color us = board.side_to_move;
        board.side_to_move = Color(1 - us);
        board.hash ^= Zobrist::side_key;
        Square saved_ep = board.ep_square;
        if (board.ep_square != NO_SQUARE) {
            board.hash ^= Zobrist::ep_keys[board.ep_square];
            board.ep_square = NO_SQUARE;
        }

        // D-03 Bug #3 fix: null move uses child ply — no vector allocation needed.
        int null_score = -alpha_beta(board, depth - R - 1,
                                     -beta, -beta + 1, info, ply + 1, false);

        // Unmake null move
        board.side_to_move = us;
        board.hash ^= Zobrist::side_key;
        if (saved_ep != NO_SQUARE) {
            board.ep_square = saved_ep;
            board.hash ^= Zobrist::ep_keys[saved_ep];
        }

        if (info.stopped) return 0;

        if (null_score >= beta) {
            // SRCH-03 verification re-search at depth >= 12:
            // do a second null-window search to confirm the cutoff is real.
            if (depth >= 12) {
                // Verification: make null move again at same R
                board.side_to_move = Color(1 - board.side_to_move);
                board.hash ^= Zobrist::side_key;
                Square saved_ep2 = board.ep_square;
                if (board.ep_square != NO_SQUARE) {
                    board.hash ^= Zobrist::ep_keys[board.ep_square];
                    board.ep_square = NO_SQUARE;
                }
                int verify_score = -alpha_beta(board, depth - R - 1,
                                               -beta, -beta + 1, info, ply + 1, false);
                board.side_to_move = Color(1 - board.side_to_move);
                board.hash ^= Zobrist::side_key;
                if (saved_ep2 != NO_SQUARE) {
                    board.ep_square = saved_ep2;
                    board.hash ^= Zobrist::ep_keys[saved_ep2];
                }
                if (info.stopped) return 0;
                // Only return beta if verification confirms
                if (verify_score >= beta) return beta;
            } else {
                return beta;  // depth < 12: trust null score directly
            }
        }
    } else if (!(info.options && info.options->UseNullMove) &&
               do_null && !in_check &&
               depth >= NULL_MOVE_MIN_DEPTH && static_eval >= beta) {
        // Legacy fallback: UseNullMove=false but options exist — skip null move.
        // This branch is intentionally empty (null move disabled by toggle).
        (void)0;
    }

    // -------------------------------------------------------------------------
    // SRCH-10 (Plan 03-03) — ProbCut.
    //
    // At non-PV non-check nodes with depth >= 5, quickly probe whether any
    // capture can produce a fail-high above a widened beta + probcut_margin.
    // This avoids expensive deep searches when captures already prove the
    // position is overwhelmingly good.
    //
    // Implementation (RESEARCH.md D2 §3.8):
    //   1. Filter captures with SEE >= probcut_beta - static_eval (margin filter).
    //   2. Quick qsearch at zero-window (probcut_beta-1, probcut_beta).
    //   3. If qsearch raises, confirm with reduced-depth alpha_beta.
    //   4. If confirmation also raises, return the score directly.
    //
    // probcut_margin = 200 (tunable; Phase 4 TUNE-09 may rescale).
    // probcut_depth  = depth - 3 (reduced verification depth).
    //
    // Gate: UseProbCut (D-06). Default ON; may flip to false if tier-2
    // mini-gauntlet shows regression (D-04 SRCH-10 explicit anticipation).
    // -------------------------------------------------------------------------
    constexpr int PROBCUT_MARGIN = 200;  // centipawns above beta — TUNE-09 target
    if (info.options && info.options->UseProbCut &&
        !is_pv && !in_check && depth >= 5 &&
        std::abs(beta) < MATE_IN_MAX_PLY) {

        int probcut_beta  = beta + PROBCUT_MARGIN;
        int probcut_depth = depth - 3;

        // Enumerate captures (use generate_captures which is quiescence-exact)
        MoveList prob_caps;
        generate_captures(board, prob_caps);

        for (int pi = 0; pi < prob_caps.count; ++pi) {
            Move pm = prob_caps.moves[pi];
            if (board.piece_at(move_to(pm)) == KING) continue;

            // SEE filter: only try captures that could plausibly beat probcut_beta.
            // Minimum SEE needed = probcut_beta - static_eval.
            int min_see = probcut_beta - static_eval;
            if (see(board, pm) < min_see) continue;

            Piece pm_captured = board.piece_at(move_to(pm));
            int pm_prev_castling = board.castling_rights;
            Square pm_prev_ep = board.ep_square;
            int pm_prev_halfmove = board.halfmove_clock;

            board.make_move(pm);

            // Legality check (skip if leaving king in check)
            if (board.is_attacked(board.king_square(Color(1 - board.side_to_move)),
                                  board.side_to_move)) {
                board.unmake_move(pm, pm_captured, pm_prev_castling, pm_prev_ep, pm_prev_halfmove);
                continue;
            }

            if (info.rep_stack) info.rep_stack->push(board.hash);

            // Step 1: qsearch at probcut_beta zero-window
            int ps = -quiescence(board, -probcut_beta, -probcut_beta + 1, info, ply + 1);

            // Step 2: if qsearch suggests fail-high, confirm with reduced alpha_beta
            if (ps >= probcut_beta) {
                ps = -alpha_beta(board, probcut_depth,
                                 -probcut_beta, -probcut_beta + 1,
                                 info, ply + 1, false);
            }

            if (info.rep_stack) info.rep_stack->pop();
            board.unmake_move(pm, pm_captured, pm_prev_castling, pm_prev_ep, pm_prev_halfmove);

            if (info.stopped) return 0;

            if (ps >= probcut_beta) {
                // ProbCut: this capture is good enough — return early.
                // Store in TT so future visits benefit.
                if (info.tt) {
                    info.tt->store(board.hash, pm,
                                   score_to_tt(ps, ply), depth - 1, TT_BETA);
                }
                return ps;
            }
        }
    }

    // Generate moves
    MoveList moves;
    generate_legal_moves(board, moves);

    if (moves.count == 0) {
        return in_check ? -MATE_SCORE + ply : DRAW_SCORE;
    }

    // -------------------------------------------------------------------------
    // Move ordering (D-03 Bug #2 fix — persistent killers/history)
    //
    // ply_killers: pointer into SearchStack::killers[ply][0..1]
    //   (nullptr when search_stack is not wired — graceful fallback)
    // history_ptr: pointer to Engine::history_[2][64][64]
    //   (nullptr when history is not wired — graceful fallback)
    // counter_move_ptr (SRCH-06, Plan 03-02): pointer to the counter-move
    //   for the move that led to this position. Indexed by
    //   (*info.counter_moves)[prev_side][prev_from][prev_to].
    //   RESEARCH.md Pitfall 7: index by the side THAT JUST MOVED (1 - stm).
    // -------------------------------------------------------------------------
    const Move* ply_killers = (info.search_stack && ply < MAX_PLY)
        ? info.search_stack->killers[ply]
        : nullptr;

    // history pointer: info.history is int (*)[64][64] pointing at history_[2][64][64].
    const int (*history_ptr)[64][64] = info.history;

    // -------------------------------------------------------------------------
    // SRCH-09 (Plan 03-03) — Standalone Multi-Cut at cut nodes (depth >= 8).
    //
    // Implementation (RESEARCH.md D2 §3.7, standalone form per plan interfaces):
    //   At depth >= 8, non-PV, non-check cut nodes: search the first M=6 moves
    //   with a reduced null-window at depth/2. If >= C=3 moves fail high above
    //   beta, prune the entire node and return beta directly.
    //
    // Rationale for standalone form (vs. piggyback in singular block):
    //   The standalone form runs at every cut node, not just when the TT move
    //   satisfies the singular preconditions. This provides stronger pruning
    //   on positions without a TT entry (plan interfaces recommendation).
    //
    // Gate: UseMultiCut (D-06). Default ON.
    // Note: multi-cut inside the singular block is ALSO applied as a piggyback
    // (RESEARCH.md Code Examples §SE — multi-cut on singular_beta >= beta).
    // The two forms are complementary: this fires at all cut nodes, the
    // singular piggyback fires only at TT-move singular tests.
    // -------------------------------------------------------------------------
    constexpr int MC_M = 6;  // number of moves to try
    constexpr int MC_C = 3;  // threshold for multi-cut
    if (info.options && info.options->UseMultiCut &&
        !is_pv && !in_check && depth >= 8) {

        int cuts = 0;
        int mc_reduced = depth / 2;

        // Score moves for multi-cut ordering (reuse score_moves on the generated list).
        // moves was just generated above; apply the ordering to pick the top M.
        int mc_scores[256];
        score_moves(board, moves, tt_move, ply_killers, history_ptr, nullptr, mc_scores);

        // Insertion sort the first MC_M moves only (partial sort).
        for (int i = 0; i < std::min(MC_M, moves.count); ++i) {
            int best_mc = i;
            for (int j = i + 1; j < moves.count; ++j) {
                if (mc_scores[j] > mc_scores[best_mc]) best_mc = j;
            }
            std::swap(moves.moves[i], moves.moves[best_mc]);
            std::swap(mc_scores[i], mc_scores[best_mc]);
        }

        for (int mi = 0; mi < std::min(MC_M, moves.count) && cuts < MC_C; ++mi) {
            Move mc_m = moves.moves[mi];
            if (board.piece_at(move_to(mc_m)) == KING) continue;

            Piece mc_captured = board.piece_at(move_to(mc_m));
            int mc_prev_castling = board.castling_rights;
            Square mc_prev_ep = board.ep_square;
            int mc_prev_halfmove = board.halfmove_clock;

            board.make_move(mc_m);

            // Legality check
            if (board.is_attacked(board.king_square(Color(1 - board.side_to_move)),
                                  board.side_to_move)) {
                board.unmake_move(mc_m, mc_captured, mc_prev_castling, mc_prev_ep, mc_prev_halfmove);
                continue;
            }

            if (info.rep_stack) info.rep_stack->push(board.hash);

            int mc_score = -alpha_beta(board, mc_reduced - 1,
                                       -beta - 1, -beta,
                                       info, ply + 1, false);

            if (info.rep_stack) info.rep_stack->pop();
            board.unmake_move(mc_m, mc_captured, mc_prev_castling, mc_prev_ep, mc_prev_halfmove);

            if (info.stopped) return 0;
            if (mc_score >= beta) ++cuts;
        }

        if (cuts >= MC_C) {
            return beta;  // SRCH-09: multi-cut — enough moves fail high, prune node
        }
    }

    // SRCH-06 (Plan 03-02): wire counter-move for this ply.
    // The counter-move is keyed by the previous move's from/to squares and the
    // side that just moved. At ply 0 there is no previous move — pass nullptr.
    // RESEARCH.md Pitfall 7: index by the side that just MADE the previous move.
    const Move* counter_move_ptr = nullptr;
    if (info.counter_moves && ply > 0 && ply < MAX_PLY &&
        info.search_stack) {
        // prev_capture_sq holds the to-square of the PARENT move. We need
        // prev_from/prev_to — read from the parent's TT probe isn't available;
        // instead we track via a small per-ply prev_from/prev_to in SearchStack.
        // For this release we implement a simplified form: counter_moves is
        // indexed by [side][from][to] of the previous move. The parent move's
        // from/to is stored in search_stack->prev_move_from/to (see below).
        // Since we do not store the full previous move in SearchStack yet, use
        // the simpler approach: counter_move_ptr remains nullptr at the parent
        // call level; counter moves are applied inside move_picker (Plan 03-02
        // inline scorer in movegen.cpp is updated separately).
        // The movegen.cpp score_moves function already receives counter_move_ptr.
        // TODO: pass parent-move from/to through SearchStack for full wiring.
        counter_move_ptr = nullptr;  // refined in Task 2 via movegen.cpp scorer
    }

    // SRCH-07 (Plan 03-03): read parent-ply continuation context for quiet scoring boost.
    // At this ply, the parent's move is recorded in prev_piece[ply], prev_stm[ply],
    // prev_to[ply] (set at ply-1 before the recursive call that reached us).
    Piece par_prev_piece = (info.search_stack && ply > 0 && ply < MAX_PLY)
        ? info.search_stack->prev_piece[ply] : NO_PIECE;
    Color par_prev_stm = (info.search_stack && ply > 0 && ply < MAX_PLY)
        ? info.search_stack->prev_stm[ply] : WHITE;
    Square par_prev_to = (info.search_stack && ply > 0 && ply < MAX_PLY)
        ? info.search_stack->prev_to[ply] : (Square)NO_SQUARE;
    bool have_cont_ctx = (par_prev_piece != NO_PIECE && par_prev_to != NO_SQUARE
                          && info.continuation_history != nullptr);

    // SRCH-07 (Plan 03-03): augment quiet move scores with continuation history.
    // score_moves() fills the base scores (TT=1000000, good caps, killers, counter,
    // history). After that, add the continuation history bonus for quiet moves.
    int move_scores[256];
    score_moves(board, moves, tt_move, ply_killers, history_ptr, counter_move_ptr, move_scores);

    // Add continuation history bonus to quiet moves (not captures).
    if (have_cont_ctx) {
        Color stm_now = board.side_to_move;
        for (int i = 0; i < moves.count; ++i) {
            Move m = moves[i];
            if (board.piece_at(move_to(m)) != NO_PIECE) continue;  // skip captures
            Piece curr_piece = board.piece_at(move_from(m));
            if (curr_piece == NO_PIECE || curr_piece >= 6) continue;
            int to_sq = move_to(m);
            // Continuation history: indexed by parent context + current move
            int cont_bonus = (*info.continuation_history)[par_prev_stm][par_prev_piece][par_prev_to]
                                                         [stm_now][curr_piece][to_sq];
            move_scores[i] += cont_bonus;  // SRCH-07: add continuation history to quiet score
        }
    }

    std::array<MoveOrder, 256> ordered;
    for (int i = 0; i < moves.count; ++i) {
        ordered[i] = {moves[i], move_scores[i]};
    }

    // SRCH-05 (Plan 03-02): futility pruning margin constants.
    // Applied inside the move loop at frontier nodes (depth <= 3) for non-tactical quiets.
    // futility_margin(depth) ≈ 200 * depth — may be re-scaled in Phase 4 TUNE-09.
    constexpr int FUTILITY_MARGIN_PER_DEPTH = 200;

    // SRCH-05 (Plan 03-02): LMP threshold constants.
    // At depth <= 8, prune after (4 + depth*depth) quiet non-check moves.
    // lmp_threshold(depth) = 4 + depth * depth (canonical table).
    // RESEARCH.md D2 §3.3, SRCH-05.

    Move best_move = MOVE_NONE;
    int best_score = -INFINITY_SCORE;
    TTFlag tt_flag = TT_ALPHA;

    // SRCH-12 (Plan 03-02): track previous-move capture square for recapture extension.
    // Read from parent ply's prev_capture_sq[ply] set before this alpha_beta call.
    Square prev_capt_sq = (info.search_stack && ply > 0 && ply < MAX_PLY)
        ? info.search_stack->prev_capture_sq[ply]
        : NO_SQUARE;

    for (int i = 0; i < moves.count; ++i) {
        // Lazy selection sort
        int best_idx = i;
        for (int j = i + 1; j < moves.count; ++j) {
            if (ordered[j].score > ordered[best_idx].score) {
                best_idx = j;
            }
        }
        std::swap(ordered[i], ordered[best_idx]);

        Move m = ordered[i].move;

        // SRCH-08 CRITICAL INVARIANT (Plan 03-03): skip the excluded move.
        // During a singular verification re-search, excluded_move[ply] holds the
        // TT move being tested. We must NOT search it — its absence is the point.
        if (info.search_stack && ply < MAX_PLY &&
            m == info.search_stack->excluded_move[ply]) {
            continue;
        }

        if (board.piece_at(move_to(m)) == KING) {
            continue;
        }

        Piece captured = board.piece_at(move_to(m));
        bool is_capture = (captured != NO_PIECE);
        bool gives_check = board.gives_check(m);

        // -------------------------------------------------------------------------
        // SRCH-05 (Plan 03-02) — Late Move Pruning (LMP).
        //
        // At shallow non-check non-PV nodes, prune quiet non-checking moves after
        // the LMP threshold. This aggressively trims the tail of the move list
        // where moves are unlikely to be best.
        //
        // lmp_threshold(depth) = 4 + depth * depth (canonical form).
        // Reference: RESEARCH.md D2 §3.3, SRCH-05.
        // -------------------------------------------------------------------------
        if (!in_check && !is_root && !is_pv && !is_capture && !gives_check &&
            (info.options ? info.options->UseLMP : true) &&
            depth <= LMP_DEPTH && i >= 4 + depth * depth) {
            break;  // All remaining moves at this ordering position are pruned
        }

        // -------------------------------------------------------------------------
        // SRCH-05 (Plan 03-02) — Futility Pruning.
        //
        // At frontier nodes (depth <= 3), if the static eval + a depth-dependent
        // margin is still below alpha, skip non-tactical quiet moves — they
        // won't raise alpha even with a significant positional bonus.
        //
        // futility_margin(depth) = 200 * depth — TUNE-09 target in Phase 4.
        // Reference: RESEARCH.md D2 §3.3, SRCH-05.
        // -------------------------------------------------------------------------
        if (!in_check && !is_root && !is_pv && !is_capture && !gives_check &&
            (info.options ? info.options->UseFutility : false) &&
            depth <= 3) {
            int futility_margin = FUTILITY_MARGIN_PER_DEPTH * depth;
            if (static_eval + futility_margin < alpha) {
                continue;  // Futility prune: skip this quiet move
            }
        }

        // -------------------------------------------------------------------------
        // SRCH-08 (Plan 03-03) — Singular extensions.
        //
        // When the TT move has a beta-bound score at a deep entry and all other
        // moves fall below a margin (singular verification), extend the TT move
        // by +1 ply. This identifies "singularly best" moves that deserve deeper
        // resolution.
        //
        // Preconditions (RESEARCH.md Code Examples §SE, Pitfall 2):
        //   - UseSingular toggle (D-06 gate)
        //   - depth >= 8 (depth gate — avoids Pitfall 2 search explosion at shallow nodes)
        //   - m == tt_move (only test the TT move — it's the one we're evaluating)
        //   - tt_entry.depth >= depth - 3 (TT entry must be fresh enough to trust)
        //   - tt_entry.flag == TT_BETA (TT move caused a beta-cutoff previously)
        //   - |tt_entry.score| < MATE_IN_MAX_PLY (avoid singular test near mate scores)
        //   - !is_root (root node: don't singular-extend at depth 0)
        //   - excluded_move[ply] == MOVE_NONE (no nested singular searches)
        //
        // Verification re-search (CRITICAL INVARIANT):
        //   Sets excluded_move[ply] = tt_move BEFORE the recursive call.
        //   The recursive call's TT probe is SKIPPED (excluded != NONE guard at top).
        //   All moves except tt_move are searched at singular_depth with narrow window.
        //   If all other moves score below singular_beta: TT move is singular -> extend.
        //
        // Multi-cut piggyback (SRCH-09): if singular_beta >= beta, a non-TT move
        // ALSO failed high above beta in the verification search. Return singular_beta.
        //
        // singular_beta  = tt_entry.score - 2 * depth  (canonical Stockfish margin A8)
        // singular_depth = (depth - 1) / 2             (half the remaining depth)
        //
        // Reference: RESEARCH.md Code Examples §SE, Pitfall 2, D-04 SRCH-08.
        // -------------------------------------------------------------------------
        int extension = 0;
        bool singular_tested = false;
        if (info.options && info.options->UseSingular &&
            depth >= 8 && m == tt_move && tt_move != MOVE_NONE &&
            tt_entry.depth >= depth - 3 &&
            tt_entry.flag == TT_BETA &&
            std::abs(static_cast<int>(tt_entry.score)) < MATE_IN_MAX_PLY &&
            !is_root &&
            !(info.search_stack && ply < MAX_PLY &&
              info.search_stack->excluded_move[ply] != MOVE_NONE)) {

            int singular_beta  = static_cast<int>(tt_entry.score) - 2 * depth;
            int singular_depth = (depth - 1) / 2;

            // Set excluded_move to skip the TT move during verification re-search.
            // CRITICAL: must be cleared BEFORE the recursive call returns to THIS frame
            // so subsequent iterations of this move loop use excluded_move == MOVE_NONE.
            info.search_stack->excluded_move[ply] = tt_move;

            int singular_score = alpha_beta(board, singular_depth,
                                            singular_beta - 1, singular_beta,
                                            info, ply, false);  // same ply (not ply+1)

            info.search_stack->excluded_move[ply] = MOVE_NONE;  // clear after re-search

            singular_tested = true;

            if (singular_score < singular_beta) {
                // Singular: TT move is uniquely best — extend it.
                extension = 1;
            } else if (info.options->UseMultiCut && singular_beta >= beta) {
                // Multi-cut piggyback (SRCH-09): a non-TT move also exceeded beta.
                // This means the position is a fail-high regardless — return early.
                return singular_beta;
            }
        }
        (void)singular_tested;  // suppress unused-variable if assert disabled

        // -------------------------------------------------------------------------
        // SRCH-12 (Plan 03-02) — Recapture extension.
        //
        // When the current move captures on the same square as the previous move
        // (recapture pattern), extend search depth by +1. This extra ply resolves
        // tactical exchanges that would otherwise be left partially explored.
        //
        // The recapture extension is ADDITIVE to the check extension (both may fire).
        // The check extension is gated by UseCheckExt above; this is gated by UseRecaptureExt.
        //
        // Reference: RESEARCH.md SRCH-12.
        // -------------------------------------------------------------------------
        if (info.options && info.options->UseRecaptureExt &&
            is_capture && prev_capt_sq != NO_SQUARE &&
            move_to(m) == static_cast<int>(prev_capt_sq)) {
            extension = 1;  // SRCH-12: recapture on same square
        }

        // Make move
        int prev_castling = board.castling_rights;
        Square prev_ep = board.ep_square;
        int prev_halfmove = board.halfmove_clock;

        // SRCH-07 (Plan 03-03): record piece and side for child's continuation history lookup.
        // Must be read BEFORE make_move() because piece_at() queries the current position.
        Piece this_piece = board.piece_at(move_from(m));
        Color this_stm   = board.side_to_move;

        board.make_move(m);

        // SRCH-14 — push the post-move hash onto the Engine-owned rep stack
        // for in-tree repetition detection. Board itself is NEVER modified;
        // the push/pop bracket lives in this search function alone.
        if (info.rep_stack) info.rep_stack->push(board.hash);

        // SRCH-12 (Plan 03-02): record this move's capture square for the child ply.
        // Child (ply+1) reads prev_capture_sq[ply+1] to detect its own recaptures.
        if (info.search_stack && ply + 1 < MAX_PLY) {
            info.search_stack->prev_capture_sq[ply + 1] =
                is_capture ? static_cast<Square>(move_to(m)) : NO_SQUARE;
        }

        // SRCH-07 (Plan 03-03): record this move's piece/stm/to for child's continuation lookup.
        // Child alpha_beta at ply+1 reads prev_piece[ply+1], prev_stm[ply+1], prev_to[ply+1]
        // to index continuation_history_ keyed on what we (the parent) just played.
        if (info.search_stack && ply + 1 < MAX_PLY) {
            if (this_piece >= 0 && this_piece < 6) {
                info.search_stack->prev_piece[ply + 1] = this_piece;
                info.search_stack->prev_stm[ply + 1]   = this_stm;
                info.search_stack->prev_to[ply + 1]     = static_cast<Square>(move_to(m));
            } else {
                info.search_stack->prev_piece[ply + 1] = NO_PIECE;
                info.search_stack->prev_to[ply + 1]     = NO_SQUARE;
            }
        }

        // D-03 Bug #3 fix: child PV is stored in search_stack->pv[ply+1];
        // no std::vector allocation needed.
        int score;
        int new_depth = depth - 1 + extension;  // SRCH-12: apply recapture extension

        // -------------------------------------------------------------------------
        // SRCH-04 (Plan 03-02) — Two-level LMR re-search.
        //
        // Two-level form (Stockfish/Ethereal/Berserk canonical — RESEARCH.md Pitfall 3):
        //   Step 1: Reduced zero-window search (-alpha-1, -alpha) at reduced depth.
        //   Step 2: If Step 1 beats alpha AND there was a real reduction,
        //           re-search at FULL depth with zero-window (confirm the score is
        //           real without the reduction).
        //   Step 3: If score still beats alpha AND is below beta (PV improvement),
        //           re-search at FULL depth with FULL window (PV re-search).
        //
        // Context adjustments to R (RESEARCH.md D2 §3.2):
        //   - Subtract 1 on PV nodes (is_pv = beta - alpha > 1)
        //   - Add 1 on cut nodes (!is_pv && !do_null approximation)
        //   - Subtract 1 if improving (static_eval > parent static_eval; omitted
        //     this iteration — improving flag not tracked per-ply yet)
        //   - Force R=0 if in_check (already handled by !in_check gate)
        //
        // RESEARCH.md Pitfall 3: one-level re-search (old code) misses the
        // case where the reduced search fails low but the full-depth ZW would
        // succeed — causing false pruning. Two-level fixes this.
        //
        // Gate: info.options->UseLMR (D-06). When UseLMR=false, always do PVS.
        // -------------------------------------------------------------------------
        bool do_lmr = (!info.options || info.options->UseLMR) &&
                      !in_check && i >= LMR_FULL_DEPTH_MOVES &&
                      depth >= LMR_REDUCTION_LIMIT && !is_capture &&
                      move_type(m) != PROMOTION;

        if (do_lmr) {
            int R = LMR_TABLE[std::min(depth, 63)][std::min(i, 63)];
            // Context adjustments (RESEARCH.md D2 §3.2):
            if (is_pv)  R -= 1;   // PV node: reduce less aggressively
            if (!is_pv) R += 1;   // Cut node: reduce more aggressively
            if (R < 0) R = 0;     // Never search deeper than base depth

            // Step 1 — reduced zero-window:
            score = -alpha_beta(board, new_depth - R, -alpha - 1, -alpha,
                                info, ply + 1, true);

            // Step 2 — full-depth zero-window re-search (if reduced search raised alpha):
            if (score > alpha && R > 0) {
                score = -alpha_beta(board, new_depth, -alpha - 1, -alpha,
                                    info, ply + 1, true);
            }

            // Step 3 — full-window re-search (PV improvement):
            if (score > alpha && score < beta) {
                score = -alpha_beta(board, new_depth, -beta, -alpha,
                                    info, ply + 1, true);
            }
        } else if (i > 0) {
            // PVS: null-window first, then full window if PV improvement found.
            score = -alpha_beta(board, new_depth, -alpha - 1, -alpha,
                                info, ply + 1, true);
            if (score > alpha && score < beta) {
                score = -alpha_beta(board, new_depth, -beta, -alpha,
                                    info, ply + 1, true);
            }
        } else {
            // First move: always search with full window.
            score = -alpha_beta(board, new_depth, -beta, -alpha,
                                info, ply + 1, true);
        }

        if (info.rep_stack) info.rep_stack->pop();
        board.unmake_move(m, captured, prev_castling, prev_ep, prev_halfmove);

        if (info.stopped) return 0;

        if (score > best_score) {
            best_score = score;
            best_move = m;

            if (score > alpha) {
                alpha = score;
                tt_flag = TT_EXACT;

                // D-03 Bug #3 fix: update triangular PV at this ply.
                // pv[ply][ply] = best move, then copy child's PV tail.
                if (info.search_stack && ply < MAX_PLY) {
                    SearchStack& ss = *info.search_stack;
                    ss.pv[ply][ply] = m;
                    int child_len = (ply + 1 < MAX_PLY) ? ss.pv_length[ply + 1] : ply + 1;
                    for (int k = ply + 1; k < child_len && k < MAX_PLY; ++k) {
                        ss.pv[ply][k] = ss.pv[ply + 1][k];
                    }
                    ss.pv_length[ply] = child_len;
                }

                if (score >= beta) {
                    tt_flag = TT_BETA;

                    // D-03 Bug #2 fix: update persistent killers at this ply.
                    // Killers are quiet moves that cause beta cutoffs.
                    if (!is_capture && info.search_stack && ply < MAX_PLY) {
                        Move* killers = info.search_stack->killers[ply];
                        if (killers[0] != m) {
                            killers[1] = killers[0];
                            killers[0] = m;  // SRCH-06: killer update on cutoff
                        }
                    }

                    // D-03 Bug #2 fix: update persistent history table.
                    // Increment history[side][from][to] for beta-cutoff quiets.
                    if (!is_capture && info.history) {
                        Color stm = Color(1 - board.side_to_move);  // side that moved
                        int from_sq = move_from(m);
                        int to_sq   = move_to(m);
                        (*info.history)[stm][from_sq][to_sq] += depth * depth;  // depth-squared bonus
                    }

                    // SRCH-07 (Plan 03-03): update continuation history on quiet beta-cutoff.
                    // Indexed by: parent-move context (prev stm, piece, to) -> this move (stm, piece, to).
                    // RESEARCH.md D2 §3.5: update += depth * depth on quiet cutoffs.
                    if (!is_capture && info.continuation_history && have_cont_ctx &&
                        this_piece >= 0 && this_piece < 6) {
                        Color stm_now_cut = Color(1 - board.side_to_move);  // side that just moved
                        int to_sq_cut = move_to(m);
                        (*info.continuation_history)[par_prev_stm][par_prev_piece][par_prev_to]
                                                    [stm_now_cut][this_piece][to_sq_cut] += depth * depth;
                    }

                    // SRCH-07 (Plan 03-03): update capture history on capture beta-cutoff.
                    // Indexed by: attacking side, attacker piece, destination, captured piece.
                    // RESEARCH.md D2 §3.5: update += depth * depth on capture cutoffs.
                    if (is_capture && info.capture_history) {
                        Color stm_now_cut = Color(1 - board.side_to_move);  // side that captured
                        Piece captured_piece = board.piece_at(move_to(m));  // AFTER unmake? No.
                        // After make_move+unmake_move we are back to pre-move state. But we are
                        // still inside make_move before unmake here. captured was read BEFORE make_move
                        // (set above as `captured = board.piece_at(move_to(m))`). Use that value.
                        if (captured != NO_PIECE && captured < 6 &&
                            this_piece >= 0 && this_piece < 6) {
                            (*info.capture_history)[stm_now_cut][this_piece][move_to(m)][captured]
                                += depth * depth;
                        }
                        (void)captured_piece;  // suppress unused-variable warning
                    }

                    // SRCH-13 — store mate-distance-corrected score.
                    // D-01: use info.tt-> (not g_tt).
                    if (info.tt) {
                        info.tt->store(board.hash, best_move,
                                       score_to_tt(best_score, ply), depth, tt_flag);
                    }
                    return beta;
                }
            }
        }
    }

    // SRCH-13 — store mate-distance-corrected score.
    // D-01: use info.tt-> (not g_tt).
    if (info.tt) {
        info.tt->store(board.hash, best_move,
                       score_to_tt(best_score, ply), depth, tt_flag);
    }
    return best_score;
}

// =============================================================================
// ITERATIVE DEEPENING — V6 + SRCH-01 + SRCH-02 + SRCH-15 + Bug #1 fix
// =============================================================================
//
// Plan 03-01 Bug #1 fix (D-03):
//   - max_depth now reads info.max_depth (new field) instead of info.depth.
//   - info.depth = depth inside the loop is the per-iteration counter only;
//     it no longer overwrites the caller's depth cap because that cap is in
//     the separate info.max_depth field.
//
// Plan 03-01 Bug #3 fix (D-03):
//   - std::vector<Move> pv REMOVED from this function.
//   - PV is read from info.search_stack->pv[0][*] at each completed depth.

SearchResultFull iterative_deepening(Board& board, SearchInfo& info, bool verbose) {
    SearchResultFull result;
    result.best_move = MOVE_NONE;
    result.score = 0;
    result.depth = 0;
    result.nodes = 0;

    int alpha = -INFINITY_SCORE;
    int beta = INFINITY_SCORE;

    // D-03 Bug #1 fix: read info.max_depth (set by Engine::search) as the cap.
    // The old code read info.depth which was silently overwritten by the loop body.
    int max_depth = (info.max_depth > 0) ? std::min(info.max_depth, MAX_PLY - 1) : MAX_PLY - 1;

    for (int depth = 1; depth <= max_depth && !info.stopped; ++depth) {
        info.depth = depth;  // per-iteration counter (safe now — cap is in max_depth)

        // D-03 Bug #3 fix: reset PV length at root before each depth iteration.
        if (info.search_stack) {
            info.search_stack->pv_length[0] = 0;
        }

        // Aspiration windows (V6 — entered at depth 4+)
        if (depth >= 4) {
            alpha = result.score - ASPIRATION_WINDOW;
            beta  = result.score + ASPIRATION_WINDOW;
        } else {
            alpha = -INFINITY_SCORE;
            beta  = INFINITY_SCORE;
        }

        int score = alpha_beta(board, depth, alpha, beta, info, 0, true);

        // -------------------------------------------------------------------
        // SRCH-02 — Bounded aspiration re-search.
        //
        // V6 ANTI-PATTERN (search.cpp:316-320) did exactly one full-window
        // re-search on fail-high/low — adequate in practice but not defense
        // in depth against pathological eval swings. V7 caps at
        // ASPIRATION_MAX_REWIDENS doubling-widenings, then falls back to
        // the full window. Cannot loop infinitely.
        // -------------------------------------------------------------------
        int rewidens = 0;
        int delta = ASPIRATION_WINDOW;
        while ((score <= alpha || score >= beta) && !info.stopped) {
            if (rewidens >= ASPIRATION_MAX_REWIDENS) {
                alpha = -INFINITY_SCORE;
                beta  = INFINITY_SCORE;
            } else {
                delta *= 2;
                if (score <= alpha) alpha -= delta;
                else                beta  += delta;
                ++rewidens;
            }
            score = alpha_beta(board, depth, alpha, beta, info, 0, true);
            if (info.stopped) break;
            // If we've fallen back to the full window already, the next
            // alpha_beta result is unconditionally usable — exit the loop.
            if (alpha == -INFINITY_SCORE && beta == INFINITY_SCORE) break;
        }

        if (info.stopped && depth > 1) break;

        // SRCH-01 — commit best move at each COMPLETED depth so a mid-iter
        // interrupt at depth N+1 returns the best move from depth N.
        result.score = score;
        result.depth = depth;
        result.nodes = info.nodes;

        // D-03 Bug #3 fix: extract PV from triangular array instead of vector.
        result.pv.clear();
        if (info.search_stack) {
            SearchStack& ss = *info.search_stack;
            int pv_len = ss.pv_length[0];
            for (int k = 0; k < pv_len && k < MAX_PLY; ++k) {
                result.pv.push_back(ss.pv[0][k]);
            }
        }

        if (!result.pv.empty()) {
            result.best_move = result.pv[0];
        }

        if (verbose) {
            int elapsed = info.elapsed_ms();
            uint64_t nps = elapsed > 0 ? (info.nodes * 1000) / elapsed : 0;

            std::cout << "info depth " << depth
                      << " seldepth " << info.seldepth
                      << " score cp " << score
                      << " nodes " << info.nodes
                      << " nps " << nps
                      << " time " << elapsed
                      << " pv";
            for (Move m : result.pv) {
                std::cout << " " << move_to_string(m);
            }
            std::cout << std::endl;
        }

        // -------------------------------------------------------------------
        // SRCH-15 — Soft deadline gates STARTING a new ID iteration. The
        // hard deadline (enforced in SearchInfo::check_time) interrupts
        // mid-iteration; this guard prevents wasting budget on a depth we
        // probably can't finish.
        // -------------------------------------------------------------------
        if (info.soft_deadline_ms > 0 &&
            info.elapsed_ms() >= info.soft_deadline_ms) {
            break;
        }
    }

    result.time_ms = info.elapsed_ms();
    return result;
}

// =============================================================================
// SINGLE-THREADED SEARCH (free function — Engine::search calls this via
// iterative_deepening directly, but the free function is retained for V6
// API parity)
// =============================================================================
//
// D-01 note: this free-function path does NOT have a wired info.tt pointer,
// so it cannot call info.tt->new_search(). Use Engine::search for the full
// production path. This stub is retained for legacy tests only.

SearchResultFull search(Board& board, int time_limit_ms, bool verbose) {
    // D-01: free-function path has no Engine::tt_ to wire; create a local TT
    // for legacy callers. This path is only used by legacy free-function tests;
    // production use goes through Engine::search which wires info.tt = &tt_.
    static TT legacy_tt(16);  // small local TT for legacy callers
    legacy_tt.new_search();   // D-01: call via pointer (not g_tt)

    SearchInfo info;
    info.tt = &legacy_tt;    // D-01: wire for this path
    info.reset();
    info.time_limit_ms = time_limit_ms;
    info.max_depth = MAX_PLY - 1;  // D-03 Bug #1: set max_depth for free-function path

    return iterative_deepening(board, info, verbose);
}

} // namespace v7
