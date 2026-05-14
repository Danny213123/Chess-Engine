"""
V5b Chess Algorithm Adapter
Integrates the V5b bitboard engine with the existing GameState interface.
Enhanced with deeper search and aggressive pruning.
"""

import time
from typing import Optional

from chess_engine.engine.v5b.board import BoardState
from chess_engine.engine.v5b.search import search, get_best_move
from chess_engine.engine.v5b.move_gen import move_to_string, generate_legal_moves
from chess_engine.engine.v3.chess_opening_book import OpeningBook

# Opening book
OPENING_BOOK = OpeningBook()

# Default search parameters - V5b uses more time for deeper search
DEFAULT_TIME_LIMIT = 3.0  # seconds per move (increased from 2.0)
DEFAULT_DEPTH = 12  # increased from 8


def find_best_move(game_state, valid_moves, engine, search_info=None):
    """
    Entry point for V5b engine.

    Args:
        game_state: V3 GameState object
        valid_moves: List of V3 Move objects
        engine: Engine name (for logging)
        search_info: Optional SearchInfo for external stop control

    Returns:
        V3 Move object representing the best move
    """
    print(f"[V5b] Bitboard Engine - Deep Search with Aggressive Pruning")

    # 1. Check opening book first
    fen = game_state.get_fen().split(" ")[0]
    book_moves = OPENING_BOOK.get_move(fen)
    if book_moves:
        for bm in book_moves:
            for vm in valid_moves:
                if str(vm) == bm:
                    print(f"[BOOK] {vm}")
                    return vm

    # 2. Convert to V4d BoardState
    board = BoardState()
    board.from_fen(game_state.get_fen())

    # 3. Run V5b search with optional external search_info
    start = time.time()
    best_move_encoded, stats = search(board, time_limit=DEFAULT_TIME_LIMIT, verbose=True, search_info=search_info)
    elapsed = time.time() - start

    if best_move_encoded == 0:
        print("[V5b] WARNING: No move found, using first legal move")
        # Return empty stats if no move
        empty_stats = {'depth': 0, 'nodes': 0, 'time': elapsed, 'score': 0, 'nps': 0, 'pv': ''}
        return valid_moves[0] if valid_moves else None, empty_stats
    
    # 4. Convert V4d move back to V3 Move
    move_str = move_to_string(best_move_encoded)
    score = stats['score']
    print(f"[V5b] Best: {move_str} ({score} cp) in {elapsed:.2f}s")
    
    # Find matching V3 move
    chosen_move = None
    for vm in valid_moves:
        if str(vm) == move_str or str(vm).startswith(move_str):
            chosen_move = vm
            break
            
    if not chosen_move:
        # Try matching by coordinates... (existing logic)
        from_sq = move_str[:2]
        to_sq = move_str[2:4]
        
        from_col = ord(from_sq[0]) - ord('a')
        from_row = 8 - int(from_sq[1])
        to_col = ord(to_sq[0]) - ord('a')
        to_row = 8 - int(to_sq[1])
        
        for vm in valid_moves:
            if (vm.start_row == from_row and vm.start_col == from_col and
                vm.end_row == to_row and vm.end_col == to_col):
                chosen_move = vm
                break
    
    if chosen_move:
        return chosen_move, stats

    print(f"[V5b] Warning: Could not match move {move_str}, using first legal")
    empty_stats = {'depth': 0, 'nodes': 0, 'time': elapsed, 'score': 0, 'nps': 0, 'pv': ''}
    return (valid_moves[0], empty_stats) if valid_moves else (None, empty_stats)


def find_top_moves(game_state, valid_moves, engine, top_n=3):
    """
    Return top N moves for hint system.
    Currently simplified - just returns best move.
    """
    best = find_best_move(game_state, valid_moves, engine)
    if best:
        return [{"move": str(best), "score": 0}]
    return []
