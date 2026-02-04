# V4 Chess Algorithm - Grandmaster Edition
# Logic: Aspiration Windows + Null Move + LMR + Endgame Heuristics
# Base: V3 Thread-Safe Engine

import random
import time
import threading
import copy
from typing import Optional, List, Dict, Any

# Import V3 shared resources
from main.engine.v3 import chess_hash
from main.engine.v3.chess_opening_book import OpeningBook
from main.engine.v3.chess_transposition_table import (
    ThreadSafeTranspositionTable, TTEntry,
    get_transposition_table, clear_transposition_table
)
from main.engine.v3.device import get_device, DeviceType
from main.engine.v3.parallel_search import get_search_manager

# Use Numba-optimized evaluation from V3
try:
    from main.engine.v3.cpu_kernels import score_board_fast as score_board
except ImportError:
    print("[V4] Numba optimized eval not available, using Python version")
    from main.engine.v3.chess_heuristic_calculation import score_board

# ============================================================================
# GLOBAL STATE (Thread-Safe)
# ============================================================================
OPENING_BOOK = OpeningBook()

# Search parameters for V4
DEPTH = 8  # Increased depth for V4 Grandmaster Mode
ASPIRATION_WINDOW = 50  # Window size for aspiration search

# Piece values
PIECE_VALUES = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 20000}

# Thread-safe tables
_history_lock = threading.RLock()
_killer_lock = threading.RLock()

history_table = [[0 for _ in range(64)] for _ in range(64)]
killer_moves = [[None, None] for _ in range(64)]

# Thread-local storage
_thread_local = threading.local()

# Global total for stats
_total_nodes = 0

def get_counter():
    """Thread-safe counter access."""
    if not hasattr(_thread_local, 'counter'):
        _thread_local.counter = 0
    return _thread_local.counter

def increment_counter(count=1):
    """Thread-safe counter increment."""
    if not hasattr(_thread_local, 'counter'):
        _thread_local.counter = 0
    _thread_local.counter += count

def reset_counter():
    """Reset thread-local counter."""
    global _total_nodes
    _thread_local.counter = 0
    _total_nodes = 0

def get_total_nodes():
    """Get total nodes searched."""
    return _total_nodes + get_counter()


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
    """Convert board coordinates to 0-63 index."""
    return (7 - row) * 8 + col


# ============================================================================
# ENDGAME & HEURISTICS (V4 Mop-up)
# ============================================================================

def get_endgame_phase(game_state):
    """
    Determine endgame phase based on material.
    Returns: float 0.0 (opening) to 1.0 (pure pawn endgame)
    """
    # Simple material count
    queens = 0
    minors = 0
    for r in range(8):
        for c in range(8):
            p = game_state.board[r][c]
            if p[1] == 'Q': queens += 1
            elif p[1] in ['R', 'B', 'N']: minors += 1
            
    # Heuristic definition of endgame: no queens or very few pieces
    if queens == 0:
        return 1.0
    if queens == 2 and minors <= 2: # Q vs Q endgame
        return 0.5
    return 0.0

def score_endgame(game_state, material_score):
    """Apply V4 mop-up evaluation for won endgames."""
    # If we have a significant advantage in endgame, drive enemy king to corner
    
    # Check simple material balance
    white_mat = score_board(game_state) # Evaluated from white's perspective
    
    # Are we winning?
    is_white_winning = white_mat > 500
    is_black_winning = white_mat < -500
    
    if not (is_white_winning or is_black_winning):
        return material_score
        
    winning_color = "w" if is_white_winning else "b"
    losing_king_sq = None
    winning_king_sq = None
    
    # Find kings
    for r in range(8):
        for c in range(8):
            p = game_state.board[r][c]
            if p == f"{'b' if is_white_winning else 'w'}K":
                losing_king_sq = (r, c)
            elif p == f"{winning_color}K":
                winning_king_sq = (r, c)
                
    if not losing_king_sq or not winning_king_sq:
        return material_score
        
    # Mop-up Bonus
    mop_up_score = 0
    
    # 1. Drive losing king to edge
    # Center distance (manhattan distance from 3.5, 3.5)
    center_dist_r = max(3 - losing_king_sq[0], losing_king_sq[0] - 4)
    center_dist_c = max(3 - losing_king_sq[1], losing_king_sq[1] - 4)
    center_dist = center_dist_r + center_dist_c
    mop_up_score += center_dist * 10 # Push to edge
    
    # 2. Minimize distance between kings (to help checkmate)
    dist_r = abs(losing_king_sq[0] - winning_king_sq[0])
    dist_c = abs(losing_king_sq[1] - winning_king_sq[1])
    kings_dist = dist_r + dist_c
    mop_up_score += (14 - kings_dist) * 5 # Get close
    
    if is_black_winning:
        mop_up_score = -mop_up_score
        
    return material_score + mop_up_score


# ============================================================================
# SEE (Static Exchange Evaluation) - Reused from V3 Logic
# ============================================================================
# (Simplified inline version for brevity in initial V4 file, could import if needed but easier to keep self-contained for modifications)
def is_square_attacked_by(game_state, row, col, by_white):
    """Check if a square is attacked by the specified color."""
    # Check knight
    knight_piece = "wN" if by_white else "bN"
    key = (row, col)
    # Re-implement simple attack logic here or import from V3?
    # Better to duplicate small logic to avoid massive import dependencies if we change signature
    pass 
    # Actually, let's keep it simple and assume we import the full logic if we need complex SEE.
    # For now, let's copy V3's implementation exactly to ensure it works.
    
    # Check knight attacks
    knight_moves = [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]
    for dr, dc in knight_moves:
        r, c = row + dr, col + dc
        if 0 <= r < 8 and 0 <= c < 8:
            if game_state.board[r][c] == knight_piece: return True
            
    # Check pawn attacks
    pawn_piece = "wP" if by_white else "bP"
    pawn_dir = 1 if by_white else -1
    for dc in [-1, 1]:
        r, c = row + pawn_dir, col + dc
        if 0 <= r < 8 and 0 <= c < 8:
            if game_state.board[r][c] == pawn_piece: return True
            
    # Check king attacks
    king_piece = "wK" if by_white else "bK"
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0: continue
            r, c = row + dr, col + dc
            if 0 <= r < 8 and 0 <= c < 8 and game_state.board[r][c] == king_piece: return True
            
    # Sliding pieces
    dirs = [(0,1),(0,-1),(1,0),(-1,0)] # R/Q
    sliders = ["wR", "wQ"] if by_white else ["bR", "bQ"]
    for dr, dc in dirs:
        r, c = row + dr, col + dc
        while 0 <= r < 8 and 0 <= c < 8:
            p = game_state.board[r][c]
            if p != "--":
                if p in sliders: return True
                break
            r, c = r+dr, c+dc
            
    dirs = [(1,1),(1,-1),(-1,1),(-1,-1)] # B/Q
    sliders = ["wB", "wQ"] if by_white else ["bB", "bQ"]
    for dr, dc in dirs:
        r, c = row + dr, col + dc
        while 0 <= r < 8 and 0 <= c < 8:
            p = game_state.board[r][c]
            if p != "--":
                if p in sliders: return True
                break
            r, c = r+dr, c+dc
            
    return False

def see_capture(game_state, move):
    if move.pieceCaptured == "--": return 0
    victim = PIECE_VALUES.get(move.pieceCaptured[1], 0)
    attacker = PIECE_VALUES.get(move.pieceMoved[1], 0)
    
    # Optimistic: Gain = Victim
    # Pessimistic: Gain = Victim - Attacker (if recaptured)
    # We'll use a simple version: if protected, assume exchange.
    game_state.make_move(move)
    is_white = move.pieceMoved[0] == "w"
    is_protected = is_square_attacked_by(game_state, move.end_row, move.end_col, not is_white)
    game_state.undo_move()
    
    if is_protected:
        return victim - attacker
    return victim


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
# SEARCH (The V4 Brain)
# ============================================================================

def find_best_move(game_state, valid_moves, engine):
    """Entry point for V4 search."""
    device = get_device()
    print(f"[V4] Using {device.device_type.value.upper()} (Grandmaster Mode)")
    
    # 1. Book Check
    fen = game_state.get_fen().split(" ")[0]
    book_moves = OPENING_BOOK.get_move(fen)
    if book_moves:
        for bm in book_moves:
            for vm in valid_moves:
                if str(vm) == bm:
                    print(f"[BOOK] {vm}")
                    return vm
                    
    # 2. Search
    best_move = iterative_deepening(game_state, valid_moves)
    if best_move:
        print(f"[SEARCH] Best: {best_move}")
        return best_move
    return None

def iterative_deepening(game_state, valid_moves):
    global _total_nodes
    reset_counter()
    start_time = time.time()
    
    best_move = None
    alpha = float("-inf")
    beta = float("inf")
    
    # Aspiration Window Variables
    last_score = 0
    
    for depth in range(1, DEPTH + 1):
        # Aspiration Window Logic (Depth > 3)
        if depth > 3:
            alpha = last_score - ASPIRATION_WINDOW
            beta = last_score + ASPIRATION_WINDOW
        else:
            alpha = float("-inf")
            beta = float("inf")
            
        turn_mult = 1 if game_state.white else -1
        
        # Sort moves (PV move first from previous iteration)
        # (Simplified: relying on TT ordering primarily here)
        
        while True: # Aspiration Refit Loop
            best_val = float("-inf")
            
            # Root Search
            # We use parallel search at root for V4 as well
            results = root_search_parallel(game_state, valid_moves, depth, alpha, beta, turn_mult)
            
            # Find best
            results.sort(key=lambda x: x[1], reverse=True)
            if results:
                curr_move, curr_score = results[0]
                best_val = curr_score
                
            # Check Aspiration Bounds
            if depth > 3:
                if best_val <= alpha:
                    print(f"[V4] Fail Low at depth {depth}, widening...")
                    alpha -= ASPIRATION_WINDOW * 2
                    continue # Re-search
                elif best_val >= beta:
                    print(f"[V4] Fail High at depth {depth}, widening...")
                    beta += ASPIRATION_WINDOW * 2
                    continue # Re-search
            
            # Result valid
            best_move = curr_move
            last_score = best_val
            break 
            
        elapsed = time.time() - start_time
        print(f"Depth {depth}: {get_total_nodes()} nodes, {elapsed:.2f}s, Score: {last_score}, Move: {best_move}")
        
    return best_move

def root_search_parallel(game_state, moves, depth, alpha, beta, turn_mult):
    """Distributes root moves to worker threads."""
    moves = order_moves(moves, game_state, 0) # Basic ordering
    
    results = [] # [(move, score)]
    
    # Prepare task for main thread (first move - PV)
    if not moves: return []
    
    pv_move = moves[0]
    
    # Search PV move serially
    game_state.make_move(pv_move)
    score = -negascout(game_state, game_state.get_valid_moves(), depth-1, -beta, -alpha, -turn_mult, 1, null_allowed=True)
    game_state.undo_move()
    
    results.append((pv_move, score))
    if score > alpha: alpha = score
    
    # Remaining moves
    remaining = moves[1:]
    if not remaining: return results
    
    # Worker Def
    def worker(m):
        reset_counter()
        gs = copy.deepcopy(game_state)
        gs.make_move(m)
        s = -negascout(gs, gs.get_valid_moves(), depth-1, -alpha-1, -alpha, -turn_mult, 1, null_allowed=True)
        if alpha < s < beta:
            s = -negascout(gs, gs.get_valid_moves(), depth-1, -beta, -alpha, -turn_mult, 1, null_allowed=True)
        return m, s, get_counter()

    search_manager = get_search_manager()
    batch_results = search_manager.parallel_root_search(remaining, worker)
    
    global _total_nodes
    for item in batch_results:
        if len(item) == 3:
            m, s, n = item
            _total_nodes += n
            results.append((m, s))
        
    return results

def negascout(game_state, valid_moves, depth, alpha, beta, turn_mult, ply, null_allowed):
    global _total_nodes
    increment_counter()
    
    # Mop-up / Endgame Eval base
    score_start = turn_mult * score_board(game_state)
    
    if depth <= 0:
        # Check if endgame and modify score
        # Note: expensive to check every leaf, maybe only check if depth == 0
        endgame_phase = get_endgame_phase(game_state)
        if endgame_phase > 0:
            return score_endgame(game_state, score_start)
        return quiescence(game_state, valid_moves, alpha, beta, turn_mult)

    # NULL MOVE PRUNING
    # If it's our turn, we are likely to improve. If we pass (do nothing) and are STILL winning (>= beta),
    # then we don't need to search this branch carefully.
    # Conditions: Not in check, depth >= 3, not endgame (zugzwang risk)
    if (null_allowed and depth >= 3 and not game_state.in_check and 
        score_start >= beta): # Only if static eval is already good
        
        # R = Reduction. R=2 is standard.
        R = 2
        
        # Make null move (switch turn without moving)
        game_state.white = not game_state.white
        # (Note: En passant capture validity technically changes but ignored for null move heuristic usually)
        
        # Search with reduced depth
        val = -negascout(game_state, game_state.get_valid_moves(), depth - 1 - R, -beta, -beta + 1, -turn_mult, ply + 1, False)
        
        # Undo null move
        game_state.white = not game_state.white
        
        if val >= beta:
            return beta # Cutoff

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
        
        # Late Move Reduction (LMR)
        # Search later moves (likely bad) at reduced depth
        needs_full_search = True
        
        if i >= 4 and depth >= 3 and not game_state.in_check and m.pieceCaptured == "--" and m.pieceMoved[1] != 'P':
            # Try searching with reduced depth
            reduced_depth = depth - 2
            score = -negascout(game_state, nxt, reduced_depth, -alpha - 1, -alpha, -turn_mult, ply + 1, True)
            
            # If the move turned out to be good (beat alpha), we must re-search fully
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
    global _total_nodes
    increment_counter()
    if d > 12: return mul * score_board(game_state)
    
    stand_pat = mul * score_board(game_state)
    if stand_pat >= beta: return beta
    if stand_pat > alpha: alpha = stand_pat
    
    # Delta Pruning
    if stand_pat + 950 < alpha: return alpha # Queen margin
    
    # Captures only
    caps = [m for m in moves if m.pieceCaptured != "--"]
    caps = order_moves(caps, game_state, 0)
    
    for m in caps:
        game_state.make_move(m)
        s = -quiescence(game_state, game_state.get_valid_moves(), -beta, -alpha, -mul, d+1)
        game_state.undo_move()
        
        if s >= beta: return beta
        if s > alpha: alpha = s
        
    return alpha
