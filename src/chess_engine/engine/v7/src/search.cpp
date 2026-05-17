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
// =============================================================================
//
// Plan 03-01 changes vs prior V7:
//   - `pv` parameter REMOVED (Bug #3 fix) — triangular PV lives on
//     info.search_stack->pv[ply][*] / pv_length[ply].
//   - killers/history parameter REMOVED from inner scope (Bug #2 fix) —
//     accessed via info.search_stack->killers[ply] and (*info.history)[side].
//   - g_tt replaced with info.tt-> at all four callsites (D-01).

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
    // D-01: use info.tt-> instead of g_tt (g_tt migration).
    // -------------------------------------------------------------------------
    TTEntry tt_entry;
    Move tt_move = MOVE_NONE;
    if (info.tt && info.tt->probe(board.hash, tt_entry)) {
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

        // D-03 Bug #3 fix: null move uses child ply — no vector allocation needed.
        // The child's pv is stored in search_stack->pv[ply+1] automatically.
        int reduction = NULL_MOVE_R + depth / 4;
        int null_score = -alpha_beta(board, depth - reduction - 1,
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
            return beta;
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
    // counter_move_ptr: TODO Plan 03-02 will wire counter-move bonus here;
    //   pointer passed now so the score_moves signature is final.
    // -------------------------------------------------------------------------
    const Move* ply_killers = (info.search_stack && ply < MAX_PLY)
        ? info.search_stack->killers[ply]
        : nullptr;

    // history pointer: info.history is int (*)[64][64] pointing at history_[2][64][64].
    // Callers access (*info.history)[side][from][to]. Pass as-is to score_moves.
    const int (*history_ptr)[64][64] = info.history;

    // counter_move_ptr: TODO Plan 03-02 will compute the counter-move for the
    // current position and pass it here; for now pass nullptr.
    const Move* counter_move_ptr = nullptr;

    int move_scores[256];
    score_moves(board, moves, tt_move, ply_killers, history_ptr, counter_move_ptr, move_scores);

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
        if (board.piece_at(move_to(m)) == KING) {
            continue;
        }

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

        // D-03 Bug #3 fix: child PV is stored in search_stack->pv[ply+1];
        // no std::vector allocation needed.
        int score;

        bool do_lmr = !in_check && i >= LMR_FULL_DEPTH_MOVES &&
                      depth >= LMR_REDUCTION_LIMIT && captured == NO_PIECE &&
                      move_type(m) != PROMOTION;

        if (do_lmr) {
            int reduction = LMR_TABLE[std::min(depth, 63)][std::min(i, 63)];
            score = -alpha_beta(board, depth - 1 - reduction, -alpha - 1, -alpha,
                                info, ply + 1, true);

            if (score > alpha) {
                score = -alpha_beta(board, depth - 1, -beta, -alpha,
                                    info, ply + 1, true);
            }
        } else if (i > 0) {
            // PVS
            score = -alpha_beta(board, depth - 1, -alpha - 1, -alpha,
                                info, ply + 1, true);
            if (score > alpha && score < beta) {
                score = -alpha_beta(board, depth - 1, -beta, -alpha,
                                    info, ply + 1, true);
            }
        } else {
            score = -alpha_beta(board, depth - 1, -beta, -alpha,
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
                    if (captured == NO_PIECE && info.search_stack && ply < MAX_PLY) {
                        Move* killers = info.search_stack->killers[ply];
                        if (killers[0] != m) {
                            killers[1] = killers[0];
                            killers[0] = m;
                        }
                    }

                    // D-03 Bug #2 fix: update persistent history table.
                    // Increment history[side][from][to] for beta-cutoff quiets.
                    if (captured == NO_PIECE && info.history) {
                        Color stm = Color(1 - board.side_to_move);  // side that moved
                        int from = move_from(m);
                        int to   = move_to(m);
                        (*info.history)[stm][from][to] += depth * depth;  // depth-squared bonus
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
