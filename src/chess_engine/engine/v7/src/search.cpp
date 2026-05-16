// V7 search.cpp — fork of v6/src/search.cpp with the four pre-C1 must-fixes:
//   - FOUND-04 : SearchInfo.external_stop polled in check_time (header)
//   - SRCH-02  : aspiration re-search capped at ASPIRATION_MAX_REWIDENS
//   - SRCH-13  : score_to_tt / score_from_tt wrapping at every TT site
//   - SRCH-14  : in-tree 3-fold repetition via Engine-owned RepStack;
//                50-move TT cutoff guard at halfmove_clock >= 80
//   - SRCH-15  : TimeManager::allocate + soft deadline gating ID iterations
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

        // SEE pruning
        if (see(board, m) < 0) {
            continue;
        }

        // Make move
        Piece captured = board.piece_at(move_to(m));
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
// ALPHA-BETA SEARCH (PVS) — V6 + SRCH-13 + SRCH-14 patches
// =============================================================================

int alpha_beta(Board& board, int depth, int alpha, int beta,
               SearchInfo& info, int ply, std::vector<Move>& pv,
               bool do_null) {

    if (info.stopped || (info.nodes % 4096 == 0 && info.check_time())) {
        return 0;
    }

    pv.clear();
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

    // Check extension
    if (in_check) {
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
    // -------------------------------------------------------------------------
    TTEntry tt_entry;
    Move tt_move = MOVE_NONE;
    if (g_tt.probe(board.hash, tt_entry)) {
        tt_move = tt_entry.best_move;
        // SRCH-14 — when near the 50-move boundary, still use the TT for move
        // ordering (tt_move above) but do NOT cut off on the cached score;
        // it doesn't know about the looming 50-move-rule draw.
        bool fifty_guard = (board.halfmove_clock >= MAX_HALFMOVE_FOR_TT_CUTOFF);
        if (!is_root && !fifty_guard && tt_entry.depth >= depth) {
            // SRCH-13 — convert stored mate-distance back into ply-relative score
            int tt_score = score_from_tt(static_cast<int>(tt_entry.score), ply);
            if (tt_entry.flag == TT_EXACT) {
                pv.push_back(tt_move);
                return tt_score;
            } else if (tt_entry.flag == TT_ALPHA && tt_score <= alpha) {
                return alpha;
            } else if (tt_entry.flag == TT_BETA && tt_score >= beta) {
                return beta;
            }
        }
    }

    int static_eval = evaluate(board);

    // Reverse futility pruning
    if (!in_check && !is_root && depth <= 5) {
        int margin = RFP_MARGIN[depth];
        if (static_eval - margin >= beta) {
            return static_eval - margin;
        }
    }

    // Null move pruning
    if (do_null && !in_check && depth >= NULL_MOVE_MIN_DEPTH && static_eval >= beta) {
        // Make null move
        Color us = board.side_to_move;
        board.side_to_move = Color(1 - us);
        board.hash ^= Zobrist::side_key;
        Square saved_ep = board.ep_square;
        if (board.ep_square != NO_SQUARE) {
            board.hash ^= Zobrist::ep_keys[board.ep_square];
            board.ep_square = NO_SQUARE;
        }

        std::vector<Move> null_pv;
        int reduction = NULL_MOVE_R + depth / 4;
        int null_score = -alpha_beta(board, depth - reduction - 1,
                                     -beta, -beta + 1, info, ply + 1, null_pv, false);

        // Unmake null move
        board.side_to_move = us;
        board.hash ^= Zobrist::side_key;
        if (saved_ep != NO_SQUARE) {
            board.ep_square = saved_ep;
            board.hash ^= Zobrist::ep_keys[saved_ep];
        }

        if (info.stopped) return 0;

        if (null_score >= beta) {
            return beta;
        }
    }

    // Generate moves
    MoveList moves;
    generate_legal_moves(board, moves);

    if (moves.count == 0) {
        return in_check ? -MATE_SCORE + ply : DRAW_SCORE;
    }

    // Move ordering (TT move first, then by score)
    std::array<Move, 64> killers = {};                  // Simplified (V6 parity)
    std::array<std::array<int, 64>, 12> history = {};   // Simplified (V6 parity)
    int move_scores[256];
    score_moves(board, moves, tt_move, killers, history, move_scores);

    std::array<MoveOrder, 256> ordered;
    for (int i = 0; i < moves.count; ++i) {
        ordered[i] = {moves[i], move_scores[i]};
    }

    Move best_move = MOVE_NONE;
    int best_score = -INFINITY_SCORE;
    TTFlag tt_flag = TT_ALPHA;

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

        // Late move pruning
        if (!in_check && !is_root && depth <= LMP_DEPTH && i >= 4 + depth * depth) {
            continue;
        }

        // Make move
        Piece captured = board.piece_at(move_to(m));
        int prev_castling = board.castling_rights;
        Square prev_ep = board.ep_square;
        int prev_halfmove = board.halfmove_clock;

        board.make_move(m);

        // SRCH-14 — push the post-move hash onto the Engine-owned rep stack
        // for in-tree repetition detection. Board itself is NEVER modified;
        // the push/pop bracket lives in this search function alone.
        if (info.rep_stack) info.rep_stack->push(board.hash);

        std::vector<Move> child_pv;
        int score;

        bool do_lmr = !in_check && i >= LMR_FULL_DEPTH_MOVES &&
                      depth >= LMR_REDUCTION_LIMIT && captured == NO_PIECE &&
                      move_type(m) != PROMOTION;

        if (do_lmr) {
            int reduction = LMR_TABLE[std::min(depth, 63)][std::min(i, 63)];
            score = -alpha_beta(board, depth - 1 - reduction, -alpha - 1, -alpha,
                                info, ply + 1, child_pv, true);

            if (score > alpha) {
                score = -alpha_beta(board, depth - 1, -beta, -alpha,
                                    info, ply + 1, child_pv, true);
            }
        } else if (i > 0) {
            // PVS
            score = -alpha_beta(board, depth - 1, -alpha - 1, -alpha,
                                info, ply + 1, child_pv, true);
            if (score > alpha && score < beta) {
                score = -alpha_beta(board, depth - 1, -beta, -alpha,
                                    info, ply + 1, child_pv, true);
            }
        } else {
            score = -alpha_beta(board, depth - 1, -beta, -alpha,
                                info, ply + 1, child_pv, true);
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

                pv.clear();
                pv.push_back(m);
                pv.insert(pv.end(), child_pv.begin(), child_pv.end());

                if (score >= beta) {
                    tt_flag = TT_BETA;
                    // SRCH-13 — store mate-distance-corrected score
                    g_tt.store(board.hash, best_move,
                               score_to_tt(best_score, ply), depth, tt_flag);
                    return beta;
                }
            }
        }
    }

    // SRCH-13 — store mate-distance-corrected score
    g_tt.store(board.hash, best_move,
               score_to_tt(best_score, ply), depth, tt_flag);
    return best_score;
}

// =============================================================================
// ITERATIVE DEEPENING — V6 + SRCH-01 + SRCH-02 + SRCH-15 patches
// =============================================================================

SearchResultFull iterative_deepening(Board& board, SearchInfo& info, bool verbose) {
    SearchResultFull result;
    result.best_move = MOVE_NONE;
    result.score = 0;
    result.depth = 0;
    result.nodes = 0;

    std::vector<Move> pv;
    int alpha = -INFINITY_SCORE;
    int beta = INFINITY_SCORE;

    for (int depth = 1; depth <= 64 && !info.stopped; ++depth) {
        info.depth = depth;
        pv.clear();

        // Aspiration windows (V6 — entered at depth 4+)
        if (depth >= 4) {
            alpha = result.score - ASPIRATION_WINDOW;
            beta  = result.score + ASPIRATION_WINDOW;
        } else {
            alpha = -INFINITY_SCORE;
            beta  = INFINITY_SCORE;
        }

        int score = alpha_beta(board, depth, alpha, beta, info, 0, pv, true);

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
            score = alpha_beta(board, depth, alpha, beta, info, 0, pv, true);
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
        result.pv = pv;
        if (!pv.empty()) {
            result.best_move = pv[0];
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
            for (Move m : pv) {
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

SearchResultFull search(Board& board, int time_limit_ms, bool verbose) {
    g_tt.new_search();

    SearchInfo info;
    info.reset();
    info.time_limit_ms = time_limit_ms;

    return iterative_deepening(board, info, verbose);
}

} // namespace v7
