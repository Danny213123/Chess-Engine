#include "search.hpp"
#include "eval.hpp"
#include "tt.hpp"
#include <algorithm>
#include <iostream>
#include <omp.h>

namespace v6 {

// =============================================================================
// LMR TABLE INITIALIZATION
// =============================================================================

int LMR_TABLE[64][64];

void init_lmr_table() {
    for (int depth = 1; depth < 64; ++depth) {
        for (int moves = 1; moves < 64; ++moves) {
            LMR_TABLE[depth][moves] = static_cast<int>(
                0.5 + std::log(depth) * std::log(moves) / 2.2
            );
        }
    }
}

// =============================================================================
// QUIESCENCE SEARCH
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
        
        if (board.is_attacked(board.king_square(Color(1 - board.side_to_move)), board.side_to_move)) {
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
// ALPHA-BETA SEARCH
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
    
    // TT probe
    TTEntry tt_entry;
    Move tt_move = MOVE_NONE;
    if (TT.probe(board.hash, tt_entry)) {
        tt_move = tt_entry.best_move;
        if (!is_root && tt_entry.depth >= depth) {
            int tt_score = tt_entry.score;
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
        if (board.ep_square != NO_SQUARE) {
            board.hash ^= Zobrist::ep_keys[board.ep_square];
            board.ep_square = NO_SQUARE;
        }
        
        std::vector<Move> null_pv;
        int reduction = NULL_MOVE_R + depth / 4;
        int null_score = -alpha_beta(board, depth - reduction - 1, -beta, -beta + 1, info, ply + 1, null_pv, false);
        
        // Unmake null move
        board.side_to_move = us;
        board.hash ^= Zobrist::side_key;
        
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
    std::array<Move, 64> killers = {};  // Simplified
    std::array<std::array<int, 64>, 12> history = {};  // Simplified
    int move_scores[256];
    score_moves(board, moves, tt_move, killers, history, move_scores);
    
    // Populate ordered array with moves and their scores
    std::array<MoveOrder, 256> ordered;
    for (int i = 0; i < moves.count; ++i) {
        ordered[i] = {moves[i], move_scores[i]};
    }
    
    Move best_move = MOVE_NONE;
    int best_score = -INFINITY_SCORE;
    TTFlag tt_flag = TT_ALPHA;
    
    for (int i = 0; i < moves.count; ++i) {
        // Move to front (lazy selection sort)
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
        
        std::vector<Move> child_pv;
        int score;
        
        // LMR
        bool do_lmr = !in_check && i >= LMR_FULL_DEPTH_MOVES && 
                      depth >= LMR_REDUCTION_LIMIT && captured == NO_PIECE && 
                      move_type(m) != PROMOTION;
        
        if (do_lmr) {
            int reduction = LMR_TABLE[std::min(depth, 63)][std::min(i, 63)];
            score = -alpha_beta(board, depth - 1 - reduction, -alpha - 1, -alpha, info, ply + 1, child_pv, true);
            
            if (score > alpha) {
                score = -alpha_beta(board, depth - 1, -beta, -alpha, info, ply + 1, child_pv, true);
            }
        } else if (i > 0) {
            // PVS
            score = -alpha_beta(board, depth - 1, -alpha - 1, -alpha, info, ply + 1, child_pv, true);
            if (score > alpha && score < beta) {
                score = -alpha_beta(board, depth - 1, -beta, -alpha, info, ply + 1, child_pv, true);
            }
        } else {
            score = -alpha_beta(board, depth - 1, -beta, -alpha, info, ply + 1, child_pv, true);
        }
        
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
                    TT.store(board.hash, best_move, best_score, depth, tt_flag);
                    return beta;
                }
            }
        }
    }
    
    TT.store(board.hash, best_move, best_score, depth, tt_flag);
    return best_score;
}

// =============================================================================
// ITERATIVE DEEPENING
// =============================================================================

SearchResult iterative_deepening(Board& board, SearchInfo& info, bool verbose) {
    SearchResult result;
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
        
        // Aspiration windows
        if (depth >= 4) {
            alpha = result.score - ASPIRATION_WINDOW;
            beta = result.score + ASPIRATION_WINDOW;
        }
        
        int score = alpha_beta(board, depth, alpha, beta, info, 0, pv, true);
        
        // Re-search if outside window
        if (score <= alpha || score >= beta) {
            alpha = -INFINITY_SCORE;
            beta = INFINITY_SCORE;
            score = alpha_beta(board, depth, alpha, beta, info, 0, pv, true);
        }
        
        if (info.stopped && depth > 1) break;
        
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
    }
    
    result.time_ms = info.elapsed_ms();
    return result;
}

// =============================================================================
// PARALLEL SEARCH (LAZY SMP with OpenMP)
// =============================================================================

SearchResult search_parallel(Board& board, int time_limit_ms, int num_threads, bool verbose) {
    TT.new_search();
    
    SearchInfo info;
    info.reset();
    info.time_limit_ms = time_limit_ms;
    info.num_threads = num_threads;
    
    SearchResult best_result;
    best_result.best_move = MOVE_NONE;
    best_result.score = 0;
    
    #pragma omp parallel num_threads(num_threads) shared(info, best_result)
    {
        int thread_id = omp_get_thread_num();
        Board local_board = board;  // Each thread gets a copy
        
        // Lazy SMP: each thread searches with slightly different parameters
        SearchInfo local_info;
        local_info.start_time = info.start_time;
        local_info.time_limit_ms = time_limit_ms;
        local_info.stopped = false;
        
        std::vector<Move> pv;
        
        for (int depth = 1 + (thread_id % 2); depth <= 64 && !info.stopped; depth += 1) {
            local_info.depth = depth;
            pv.clear();
            
            int score = alpha_beta(local_board, depth, -INFINITY_SCORE, INFINITY_SCORE, 
                                   local_info, 0, pv, true);
            
            info.nodes.fetch_add(local_info.nodes, std::memory_order_relaxed);
            local_info.nodes = 0;
            
            // Update best result (thread 0 is primary)
            #pragma omp critical
            {
                if (!pv.empty() && (thread_id == 0 || depth > best_result.depth)) {
                    best_result.best_move = pv[0];
                    best_result.score = score;
                    best_result.depth = depth;
                    best_result.pv = pv;
                    
                    if (verbose && thread_id == 0) {
                        int elapsed = info.elapsed_ms();
                        uint64_t nps = elapsed > 0 ? (info.nodes * 1000) / elapsed : 0;
                        std::cout << "info depth " << depth
                                  << " score cp " << score
                                  << " nodes " << info.nodes.load()
                                  << " nps " << nps
                                  << " threads " << num_threads
                                  << " pv " << move_to_string(pv[0]) << std::endl;
                    }
                }
            }
            
            // Check time
            if (info.check_time()) {
                break;
            }
        }
    }
    
    best_result.nodes = info.nodes;
    best_result.time_ms = info.elapsed_ms();
    return best_result;
}

// =============================================================================
// SINGLE-THREADED SEARCH
// =============================================================================

SearchResult search(Board& board, int time_limit_ms, bool verbose) {
    TT.new_search();
    
    SearchInfo info;
    info.reset();
    info.time_limit_ms = time_limit_ms;
    
    return iterative_deepening(board, info, verbose);
}

} // namespace v6
