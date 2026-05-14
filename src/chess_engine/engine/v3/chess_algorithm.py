# V3 Chess Algorithm - Thread-Safe with GPU/CPU Support
# Reference: https://www.chessprogramming.org/NegaScout
# Features: Thread-safe TT, Parallel Search, CUDA acceleration, CPU fallback

import random
import time
import threading
import copy
from typing import Optional, List, Dict, Any

from . import chess_hash
from .chess_opening_book import OpeningBook
# Use Numba-optimized evaluation for performance and threading support
try:
    from .cpu_kernels import score_board_fast as score_board
except ImportError:
    # Fallback if Numba not working
    print("[V3] Numba optimized eval not available, using Python version")
    from .chess_heuristic_calculation import score_board

from .chess_transposition_table import (
    ThreadSafeTranspositionTable, TTEntry,
    get_transposition_table, clear_transposition_table
)
from .device import get_device, DeviceType
from .parallel_search import get_search_manager, get_batch_evaluator

# ============================================================================
# GLOBAL STATE (Thread-Safe)
# ============================================================================
OPENING_BOOK = OpeningBook()

# Search parameters
DEPTH = 5  # Balanced between speed and tactical vision

# Piece values for SEE
PIECE_VALUES = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 20000}

# Thread-safe tables with locks
_history_lock = threading.RLock()
_killer_lock = threading.RLock()

# History heuristic table: [from_sq][to_sq] -> score
history_table = [[0 for _ in range(64)] for _ in range(64)]

# Killer moves: [ply] -> [move1, move2]
killer_moves = [[None, None] for _ in range(64)]

# Thread-local storage for search state
_thread_local = threading.local()

# Global total for stats (updated by main thread after batches)
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
    """Get total nodes searched (main thread + estimated others)."""
    # This is an approximation for parallel search as we can't easily peek into other threads
    # For reporting purposes, we'll use the tracked total + current thread
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
# STATIC EXCHANGE EVALUATION (SEE)
# ============================================================================
def is_square_attacked_by(game_state, row, col, by_white):
    """Check if a square is attacked by the specified color."""
    # Check knight attacks
    knight_moves = [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]
    knight_piece = "wN" if by_white else "bN"
    for dr, dc in knight_moves:
        r, c = row + dr, col + dc
        if 0 <= r < 8 and 0 <= c < 8:
            if game_state.board[r][c] == knight_piece:
                return True
    
    # Check pawn attacks
    pawn_piece = "wP" if by_white else "bP"
    pawn_dir = 1 if by_white else -1  # White attacks upward (decreasing row)
    for dc in [-1, 1]:
        r, c = row + pawn_dir, col + dc
        if 0 <= r < 8 and 0 <= c < 8:
            if game_state.board[r][c] == pawn_piece:
                return True
    
    # Check king attacks
    king_piece = "wK" if by_white else "bK"
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            r, c = row + dr, col + dc
            if 0 <= r < 8 and 0 <= c < 8:
                if game_state.board[r][c] == king_piece:
                    return True
    
    # Check sliding pieces (rook, queen for straight lines)
    rook_piece = "wR" if by_white else "bR"
    queen_piece = "wQ" if by_white else "bQ"
    for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
        r, c = row + dr, col + dc
        while 0 <= r < 8 and 0 <= c < 8:
            piece = game_state.board[r][c]
            if piece != "--":
                if piece == rook_piece or piece == queen_piece:
                    return True
                break  # Blocked
            r, c = r + dr, c + dc
    
    # Check sliding pieces (bishop, queen for diagonals)
    bishop_piece = "wB" if by_white else "bB"
    for dr, dc in [(1,1),(1,-1),(-1,1),(-1,-1)]:
        r, c = row + dr, col + dc
        while 0 <= r < 8 and 0 <= c < 8:
            piece = game_state.board[r][c]
            if piece != "--":
                if piece == bishop_piece or piece == queen_piece:
                    return True
                break
            r, c = r + dr, c + dc
    
    return False


def see_capture(game_state, move):
    """
    Static Exchange Evaluation - estimate if a capture is winning.
    Returns estimated material gain (positive = good capture).
    """
    if move.pieceCaptured == "--":
        return 0
    
    target_row, target_col = move.end_row, move.end_col
    attacker_value = PIECE_VALUES.get(move.pieceMoved[1], 0)
    victim_value = PIECE_VALUES.get(move.pieceCaptured[1], 0)
    
    # Simulate the capture
    game_state.make_move(move)
    
    # Check if the target square is attacked by opponent
    attacker_is_white = move.pieceMoved[0] == "w"
    defender_is_white = not attacker_is_white
    
    if is_square_attacked_by(game_state, target_row, target_col, defender_is_white):
        # Attacker can be recaptured
        # Simple SEE: gain = victim - attacker (if recaptured)
        see_value = victim_value - attacker_value
    else:
        # Not defended, free capture
        see_value = victim_value
    
    game_state.undo_move()
    
    return see_value


# ============================================================================
# MOVE ORDERING
# ============================================================================
def score_move(move, game_state, ply, use_see=False):
    """
    Score a move for ordering. Higher = search first.
    MVV-LVA for captures, killer moves for quiets.
    """
    score = 0
    
    # Captures: MVV-LVA with SEE adjustment
    if move.pieceCaptured != "--":
        victim_val = PIECE_VALUES.get(move.pieceCaptured[1], 0)
        attacker_val = PIECE_VALUES.get(move.pieceMoved[1], 0)
        
        # MVV-LVA base score
        score = 10000 + victim_val * 10 - attacker_val
        
        # Optionally use SEE to demote losing captures
        if use_see:
            see_val = see_capture(game_state, move)
            if see_val < 0:
                score = see_val  # Demote losing captures
    else:
        # Quiet moves: killer moves first, then history
        if ply < len(killer_moves):
            if killer_moves[ply][0] is not None and move.moveID == killer_moves[ply][0].moveID:
                score = 9000
            elif killer_moves[ply][1] is not None and move.moveID == killer_moves[ply][1].moveID:
                score = 8000
            else:
                from_idx = sq_to_index(move.start_row, move.start_col)
                to_idx = sq_to_index(move.end_row, move.end_col)
                score = history_table[from_idx][to_idx]
        else:
            from_idx = sq_to_index(move.start_row, move.start_col)
            to_idx = sq_to_index(move.end_row, move.end_col)
            score = history_table[from_idx][to_idx]
    
    return score


def order_moves(valid_moves, game_state, ply=0, use_see=False):
    """Order moves for better alpha-beta pruning."""
    scored_moves = [(score_move(m, game_state, ply, use_see), m) for m in valid_moves]
    scored_moves.sort(reverse=True, key=lambda x: x[0])
    return [m for _, m in scored_moves]


def update_history(move, depth):
    """Thread-safe history table update."""
    from_idx = sq_to_index(move.start_row, move.start_col)
    to_idx = sq_to_index(move.end_row, move.end_col)
    with _history_lock:
        history_table[from_idx][to_idx] += depth * depth


def update_killers(move, ply):
    """Thread-safe killer move update."""
    with _killer_lock:
        if ply < len(killer_moves) and move.pieceCaptured == "--":
            if killer_moves[ply][0] is None or move.moveID != killer_moves[ply][0].moveID:
                killer_moves[ply][1] = killer_moves[ply][0]
                killer_moves[ply][0] = move


# ============================================================================
# MAIN SEARCH FUNCTIONS
# ============================================================================

def find_best_move(game_state, valid_moves, engine):
    """Find the best move. Uses thread-safe TT. Checks opening book first."""
    # Get thread-safe transposition table
    tt = get_transposition_table()
    
    # Log device info on first call
    device = get_device()
    print(f"[V3] Using {device.device_type.value.upper()}", end="")
    if device.is_cpu:
        print(f" with {device.num_threads} threads")
    else:
        print()
    
    # Check Opening Book
    try:
        fen = game_state.get_fen().split(" ")[0]
        book_moves = OPENING_BOOK.get_move(fen)
        
        if book_moves:
            candidates = []
            for move_str in book_moves:
                for vm in valid_moves:
                    if str(vm) == move_str:
                        candidates.append(vm)
                        break
            
            if candidates:
                chosen = random.choice(candidates)
                print(f"[BOOK] {chosen}")
                return chosen
    except Exception as e:
        print(f"[BOOK ERROR] {e}")

    # Fall back to search
    top_moves = find_top_moves(game_state, valid_moves, engine, top_n=1)
    if top_moves:
        best = top_moves[0]
        print(f"[SEARCH] Best: {best['move']} (score: {best['score']})")
        return best['move']
    return None


def find_top_moves(game_state, valid_moves, engine, top_n=5):
    """Iterative deepening search to find top N moves."""
    global next_move, counter, initial_depth
    counter = 0

    if not valid_moves:
        return []

    start = time.time()
    scores = {}
    best_move_at_depth = None

    for depth in range(1, DEPTH + 1):
        initial_depth = depth
        
        alpha = float("-inf")
        beta = float("inf")
        turn_multiplier = 1 if game_state.white else -1
        
        # Sort by previous iteration's scores
        if depth > 1 and scores:
            valid_moves = sorted(valid_moves, key=lambda m: scores.get(m, float("-inf")), reverse=True)
        else:
            valid_moves = order_moves(valid_moves, game_state, 0, use_see=True)

        # 1. PV Move (Serial Search)
        best_move_node = valid_moves[0]
        game_state.make_move(best_move_node)
        next_moves = game_state.get_valid_moves()
        
        # Exact search for PV node
        score = -negascout(game_state, next_moves, depth - 1, -beta, -alpha, -turn_multiplier, 1)
        game_state.undo_move()
        
        scores[best_move_node] = score
        if score > alpha:
            alpha = score
            best_move_at_depth = best_move_node

        # 2. Remaining Moves (Parallel Search)
        remaining_moves = valid_moves[1:]
        if remaining_moves:
            # Worker function for parallel search
            # Worker function for parallel search
            def search_worker(move):
                # Reset worker-local counter for this task
                reset_counter()
                
                # Clone state for thread safety
                gs_clone = copy.deepcopy(game_state)
                gs_clone.make_move(move)
                nm = gs_clone.get_valid_moves()
                
                # PVS: Null Window Search first
                s = -negascout(gs_clone, nm, depth - 1, -alpha - 1, -alpha, -turn_multiplier, 1)
                
                # Re-search if window failed
                if alpha < s < beta:
                     s = -negascout(gs_clone, nm, depth - 1, -beta, -alpha, -turn_multiplier, 1)
                
                # Return move, score, AND nodes searched by this worker
                return move, s, get_counter()

            # Run in parallel
            search_manager = get_search_manager()
            results = search_manager.parallel_root_search(remaining_moves, search_worker)
            
            # Process results
            global _total_nodes
            for result_item in results:
                # Handle both 2-item (old) and 3-item (new) tuples for compatibility
                if len(result_item) == 3:
                    move, s, nodes = result_item
                    _total_nodes += nodes
                else:
                    move, s = result_item
                
                scores[move] = s
                if s > alpha:
                    alpha = s
                    best_move_at_depth = move

        elapsed = time.time() - start
        print(f"Depth {depth}: {get_total_nodes()} nodes, {elapsed:.2f}s, best={best_move_at_depth} ({alpha})")

    sorted_moves = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    result = []
    for m, s in sorted_moves[:top_n]:
        result.append({'move': m, 'score': s})
            
    return result


# ============================================================================
# QUIESCENCE SEARCH
# ============================================================================
def quiescence(game_state, valid_moves, alpha, beta, turn_multiplier, depth=0):
    """
    Quiescence search - only consider WINNING captures.
    Uses delta pruning and SEE to filter losing captures.
    """
    global counter
    counter += 1
    
    # Max quiescence depth to prevent explosion
    if depth > 8:
        return turn_multiplier * score_board(game_state)
    
    # Stand pat score
    stand_pat = turn_multiplier * score_board(game_state)
    
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    
    # Delta pruning threshold (biggest piece value that could change evaluation)
    DELTA = 900  # Queen value
    if stand_pat + DELTA < alpha:
        return alpha  # No capture can improve alpha enough
    
    # Only search captures with positive SEE
    capture_moves = []
    for m in valid_moves:
        if m.pieceCaptured != "--":
            see_val = see_capture(game_state, m)
            if see_val >= 0:  # Only winning or equal captures
                capture_moves.append((see_val, m))
    
    # Order by SEE value (best captures first)
    capture_moves.sort(reverse=True, key=lambda x: x[0])
    
    for see_val, move in capture_moves:
        game_state.make_move(move)
        next_moves = game_state.get_valid_moves()
        
        score = -quiescence(game_state, next_moves, -beta, -alpha, -turn_multiplier, depth + 1)
        
        game_state.undo_move()
        
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
            
    return alpha


# ============================================================================
# NEGASCOUT (Principal Variation Search)
# ============================================================================
def negascout(game_state, valid_moves, depth, alpha, beta, turn_multiplier, ply):
    """NegaScout algorithm (PVS variant) with check extension."""
    global next_move, counter, initial_depth
    counter += 1

    # Check extension: search 1 ply deeper when in check
    extension = 0
    if game_state.in_check:
        extension = 1

    # Leaf node: enter quiescence search
    if depth + extension <= 0:
        return quiescence(game_state, valid_moves, alpha, beta, turn_multiplier)

    # Order moves with SEE for captures
    valid_moves = order_moves(valid_moves, game_state, ply, use_see=True)

    # No legal moves = checkmate or stalemate
    if not valid_moves:
        if game_state.in_check:
            return -99999 + ply
        return 0

    # Transposition table probe (thread-safe)
    tt = get_transposition_table()
    hash_k = chess_hash.zobrist_key(game_state)
    tt_entry = tt.get(hash_k)
    
    if tt_entry is not None and tt_entry.depth >= depth:
        if tt_entry.flag == "exact":
            return tt_entry.score
        elif tt_entry.flag == "lower" and tt_entry.score > alpha:
            alpha = tt_entry.score
        elif tt_entry.flag == "upper" and tt_entry.score < beta:
            beta = tt_entry.score
        if alpha >= beta:
            return tt_entry.score

    best_score = float("-inf")
    best_move = None

    for i, move in enumerate(valid_moves):
        game_state.make_move(move)
        next_moves = game_state.get_valid_moves()

        if i == 0:
            score = -negascout(game_state, next_moves, depth - 1, -beta, -alpha, -turn_multiplier, ply + 1)
        else:
            score = -negascout(game_state, next_moves, depth - 1, -alpha - 1, -alpha, -turn_multiplier, ply + 1)
            if alpha < score < beta:
                score = -negascout(game_state, next_moves, depth - 1, -beta, -alpha, -turn_multiplier, ply + 1)

        game_state.undo_move()

        if score is None:
            score = float("-inf")
            
        if score > best_score:
            best_score = score
            best_move = move
            if depth == initial_depth:
                next_move = move

        if score > alpha:
            alpha = score
        
        if alpha >= beta:
            update_history(move, depth)
            update_killers(move, ply)
            break

    # Store in TT (thread-safe)
    if best_score <= alpha:
        flag = "upper"
    elif best_score >= beta:
        flag = "lower"
    else:
        flag = "exact"

    tt.put(hash_k, TTEntry(depth=depth, score=best_score, flag=flag, best_move=best_move))

    return best_score


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def export_transposition_table():
    return None


def import_transposition_table():
    return None
