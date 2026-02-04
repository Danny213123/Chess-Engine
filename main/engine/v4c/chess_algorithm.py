# V4c Chess Algorithm - CPU Optimized (16 Thread Lazy SMP)
# Logic: Aspiration Windows + Null Move + LMR + Endgame Heuristics + TRUE LAZY SMP
# Base: V4 (Grandmaster Edition) - No GPU, Pure CPU Power

import random
import time
import threading
import copy
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import V3 shared resources
from main.engine.v3 import chess_hash
from main.engine.v3.chess_opening_book import OpeningBook
from main.engine.v3.chess_transposition_table import (
    ThreadSafeTranspositionTable, TTEntry,
    get_transposition_table, clear_transposition_table
)
from main.engine.v3.device import get_device

# Use Numba-optimized evaluation from V3 (CPU)
try:
    from main.engine.v3.cpu_kernels import score_board_fast as score_board
except ImportError:
    print("[V4c] Numba optimized eval not available, using Python version")
    from main.engine.v3.chess_heuristic_calculation import score_board

# ============================================================================
# GLOBAL STATE (Thread-Safe)
# ============================================================================
OPENING_BOOK = OpeningBook()

# Search parameters for V4c
DEPTH = 8  # Matched V4
ASPIRATION_WINDOW = 50

# CPU CONFIG - Hardcoded for 16 threads
CPU_THREADS = 16

# Piece values
PIECE_VALUES = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 20000}

# Thread-safe tables
_history_lock = threading.RLock()
_killer_lock = threading.RLock()

history_table = [[0 for _ in range(64)] for _ in range(64)]
killer_moves = [[None, None] for _ in range(64)]

# Thread-local storage for node counting
_thread_local = threading.local()

def get_counter():
    if not hasattr(_thread_local, 'counter'):
        _thread_local.counter = 0
    return _thread_local.counter

def increment_counter(count=1):
    if not hasattr(_thread_local, 'counter'):
        _thread_local.counter = 0
    _thread_local.counter += count

def reset_counter():
    _thread_local.counter = 0


def clear_search_state():
    """Clear search state between games."""
    global history_table, killer_moves
    with _history_lock:
        history_table = [[0 for _ in range(64)] for _ in range(64)]
    with _killer_lock:
        killer_moves = [[None, None] for _ in range(64)]
    clear_transposition_table()
    reset_counter()


def sq_to_index(row, col):
    return (7 - row) * 8 + col


# ============================================================================
# ENDGAME & HEURISTICS (V4 Mop-up)
# ============================================================================

def get_endgame_phase(game_state):
    queens = 0
    minors = 0
    for r in range(8):
        for c in range(8):
            p = game_state.board[r][c]
            if p[1] == 'Q': queens += 1
            elif p[1] in ['R', 'B', 'N']: minors += 1
    if queens == 0:
        return 1.0
    if queens == 2 and minors <= 2:
        return 0.5
    return 0.0

def score_endgame(game_state, material_score):
    white_mat = score_board(game_state)
    is_white_winning = white_mat > 500
    is_black_winning = white_mat < -500
    
    if not (is_white_winning or is_black_winning):
        return material_score
        
    winning_color = "w" if is_white_winning else "b"
    losing_king_sq = None
    winning_king_sq = None
    
    for r in range(8):
        for c in range(8):
            p = game_state.board[r][c]
            if p == f"{'b' if is_white_winning else 'w'}K":
                losing_king_sq = (r, c)
            elif p == f"{winning_color}K":
                winning_king_sq = (r, c)
                
    if not losing_king_sq or not winning_king_sq:
        return material_score
        
    mop_up_score = 0
    center_dist_r = max(3 - losing_king_sq[0], losing_king_sq[0] - 4)
    center_dist_c = max(3 - losing_king_sq[1], losing_king_sq[1] - 4)
    center_dist = center_dist_r + center_dist_c
    mop_up_score += center_dist * 10
    
    dist_r = abs(losing_king_sq[0] - winning_king_sq[0])
    dist_c = abs(losing_king_sq[1] - winning_king_sq[1])
    kings_dist = dist_r + dist_c
    mop_up_score += (14 - kings_dist) * 5
    
    if is_black_winning:
        mop_up_score = -mop_up_score
        
    return material_score + mop_up_score


# ============================================================================
# MOVE ORDERING
# ============================================================================
def score_move(move, game_state, ply):
    score = 0
    if move.pieceCaptured != "--":
        victim = PIECE_VALUES.get(move.pieceCaptured[1], 0)
        attacker = PIECE_VALUES.get(move.pieceMoved[1], 0)
        score = 10000 + victim * 10 - attacker
    else:
        if ply < len(killer_moves):
            if killer_moves[ply][0] and move.moveID == killer_moves[ply][0].moveID: score = 9000
            elif killer_moves[ply][1] and move.moveID == killer_moves[ply][1].moveID: score = 8000
            else:
                s_idx = sq_to_index(move.start_row, move.start_col)
                e_idx = sq_to_index(move.end_row, move.end_col)
                score = history_table[s_idx][e_idx]
    return score

def order_moves(moves, game_state, ply):
    scored = [(score_move(m, game_state, ply), m) for m in moves]
    scored.sort(reverse=True, key=lambda x: x[0])
    return [m for _, m in scored]

def update_tables(move, depth, ply):
    s = sq_to_index(move.start_row, move.start_col)
    e = sq_to_index(move.end_row, move.end_col)
    with _history_lock:
        history_table[s][e] += depth * depth
        
    with _killer_lock:
        if ply < len(killer_moves) and move.pieceCaptured == "--":
            if killer_moves[ply][0] is None or move.moveID != killer_moves[ply][0].moveID:
                killer_moves[ply][1] = killer_moves[ply][0]
                killer_moves[ply][0] = move


# ============================================================================
# SEARCH (The V4c Brain - True Lazy SMP)
# ============================================================================

def find_best_move(game_state, valid_moves, engine):
    """Entry point for V4c search."""
    print(f"[V4c] CPU Optimized - Using {CPU_THREADS} threads (Lazy SMP)")
    
    # 1. Book Check
    fen = game_state.get_fen().split(" ")[0]
    book_moves = OPENING_BOOK.get_move(fen)
    if book_moves:
        for bm in book_moves:
            for vm in valid_moves:
                if str(vm) == bm:
                    print(f"[BOOK] {vm}")
                    return vm
                    
    # 2. Search with Lazy SMP
    best_move = iterative_deepening_lazy_smp(game_state, valid_moves)
    if best_move:
        print(f"[SEARCH] Best: {best_move}")
        return best_move
    return None


def iterative_deepening_lazy_smp(game_state, valid_moves):
    """
    True Lazy SMP: Multiple threads search the SAME root position independently.
    They share the transposition table but don't synchronize alpha/beta.
    """
    start_time = time.time()
    
    best_move = None
    last_score = 0
    total_nodes = 0
    
    for depth in range(1, DEPTH + 1):
        # Aspiration Window
        if depth > 3:
            alpha = last_score - ASPIRATION_WINDOW
            beta = last_score + ASPIRATION_WINDOW
        else:
            alpha = float("-inf")
            beta = float("inf")
            
        turn_mult = 1 if game_state.white else -1
        
        while True:  # Aspiration Refit Loop
            # Launch multiple threads searching the SAME position
            # Each thread gets a slightly different move order (due to timing)
            results = lazy_smp_search(game_state, valid_moves, depth, alpha, beta, turn_mult)
            
            # Aggregate results - pick best move found by any thread
            if not results:
                break
                
            # Sort by score
            results.sort(key=lambda x: x[1], reverse=True)
            curr_move, curr_score, nodes = results[0]
            total_nodes += sum(r[2] for r in results)
            
            # Check Aspiration Bounds
            if depth > 3:
                if curr_score <= alpha:
                    print(f"[V4c] Fail Low at depth {depth}, widening...")
                    alpha -= ASPIRATION_WINDOW * 2
                    continue
                elif curr_score >= beta:
                    print(f"[V4c] Fail High at depth {depth}, widening...")
                    beta += ASPIRATION_WINDOW * 2
                    continue
            
            best_move = curr_move
            last_score = curr_score
            break
            
        elapsed = time.time() - start_time
        nps = int(total_nodes / elapsed) if elapsed > 0 else 0
        print(f"Depth {depth}: {total_nodes} nodes, {elapsed:.2f}s ({nps} nps), Score: {last_score}, Move: {best_move}")
        
    return best_move


def lazy_smp_search(game_state, valid_moves, depth, alpha, beta, turn_mult):
    """
    Launch CPU_THREADS independent searches.
    Each thread searches the full tree from root but may explore different branches
    due to TT hits from other threads.
    """
    results = []
    
    def worker(thread_id):
        """Independent search worker."""
        reset_counter()
        
        # Each thread gets its own copy of game state
        gs = copy.deepcopy(game_state)
        moves = order_moves(list(valid_moves), gs, 0)
        
        # Slightly randomize move order for thread diversity (except thread 0)
        if thread_id > 0 and len(moves) > 2:
            # Swap some moves around to encourage exploration diversity
            import random
            random.seed(thread_id)
            # Only shuffle non-PV moves
            pv = moves[0]
            rest = moves[1:]
            random.shuffle(rest)
            moves = [pv] + rest
        
        best_move = None
        best_score = float("-inf")
        local_alpha = alpha
        
        for i, m in enumerate(moves):
            gs.make_move(m)
            
            if i == 0:
                score = -negascout(gs, gs.get_valid_moves(), depth-1, -beta, -local_alpha, -turn_mult, 1, True)
            else:
                # Null window search
                score = -negascout(gs, gs.get_valid_moves(), depth-1, -local_alpha-1, -local_alpha, -turn_mult, 1, True)
                if local_alpha < score < beta:
                    score = -negascout(gs, gs.get_valid_moves(), depth-1, -beta, -local_alpha, -turn_mult, 1, True)
            
            gs.undo_move()
            
            if score > best_score:
                best_score = score
                best_move = m
            if score > local_alpha:
                local_alpha = score
            if local_alpha >= beta:
                break
                
        return (best_move, best_score, get_counter())
    
    # Use ThreadPoolExecutor for true parallel execution
    with ThreadPoolExecutor(max_workers=CPU_THREADS) as executor:
        futures = [executor.submit(worker, i) for i in range(CPU_THREADS)]
        for future in as_completed(futures):
            try:
                result = future.result()
                if result[0] is not None:
                    results.append(result)
            except Exception as e:
                print(f"[V4c] Worker error: {e}")
                
    return results


def negascout(game_state, valid_moves, depth, alpha, beta, turn_mult, ply, null_allowed):
    increment_counter()
    
    score_start = turn_mult * score_board(game_state)
    
    if depth <= 0:
        endgame_phase = get_endgame_phase(game_state)
        if endgame_phase > 0:
            return score_endgame(game_state, score_start)
        return quiescence(game_state, valid_moves, alpha, beta, turn_mult)

    # NULL MOVE PRUNING
    if null_allowed and depth >= 3 and not game_state.in_check and score_start >= beta:
        R = 2
        game_state.white = not game_state.white
        val = -negascout(game_state, game_state.get_valid_moves(), depth - 1 - R, -beta, -beta + 1, -turn_mult, ply + 1, False)
        game_state.white = not game_state.white
        if val >= beta:
            return beta

    # TT Probe
    tt = get_transposition_table()
    key = chess_hash.zobrist_key(game_state)
    entry = tt.get(key)
    if entry and entry.depth >= depth:
        if entry.flag == "exact": return entry.score
        if entry.flag == "lower" and entry.score > alpha: alpha = entry.score
        if entry.flag == "upper" and entry.score < beta: beta = entry.score
        if alpha >= beta: return entry.score

    # Move Generation & Ordering
    valid_moves = order_moves(valid_moves, game_state, ply)
    if not valid_moves:
        if game_state.in_check: return -99999 + ply
        return 0

    best = float("-inf")
    best_move = None
    
    for i, m in enumerate(valid_moves):
        game_state.make_move(m)
        nxt = game_state.get_valid_moves()
        
        # LMR
        needs_full_search = True
        if i >= 4 and depth >= 3 and not game_state.in_check and m.pieceCaptured == "--" and m.pieceMoved[1] != 'P':
            reduced_depth = depth - 2
            score = -negascout(game_state, nxt, reduced_depth, -alpha - 1, -alpha, -turn_mult, ply + 1, True)
            if score <= alpha:
                needs_full_search = False
        
        if needs_full_search:
            if i == 0:
                score = -negascout(game_state, nxt, depth - 1, -beta, -alpha, -turn_mult, ply + 1, True)
            else:
                score = -negascout(game_state, nxt, depth - 1, -alpha - 1, -alpha, -turn_mult, ply + 1, True)
                if alpha < score < beta:
                    score = -negascout(game_state, nxt, depth - 1, -beta, -alpha, -turn_mult, ply + 1, True)

        game_state.undo_move()
        
        if score > best:
            best = score
            best_move = m
        if score > alpha:
            alpha = score
        if alpha >= beta:
            update_tables(m, depth, ply)
            break
            
    # Store TT
    flag = "exact"
    if best <= alpha: flag = "upper"
    elif best >= beta: flag = "lower"
    tt.put(key, TTEntry(depth, best, flag, best_move))
    
    return best


def quiescence(game_state, moves, alpha, beta, mul, d=0):
    increment_counter()
    
    stand_pat = mul * score_board(game_state)
    
    if d > 12: return stand_pat
    if stand_pat >= beta: return beta
    if stand_pat > alpha: alpha = stand_pat
    if stand_pat + 950 < alpha: return alpha
    
    caps = [m for m in moves if m.pieceCaptured != "--"]
    caps = order_moves(caps, game_state, 0)
    
    for m in caps:
        game_state.make_move(m)
        s = -quiescence(game_state, game_state.get_valid_moves(), -beta, -alpha, -mul, d+1)
        game_state.undo_move()
        
        if s >= beta: return beta
        if s > alpha: alpha = s
        
    return alpha
