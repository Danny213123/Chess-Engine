"""
V6 Chess Algorithm Adapter
Integrates the V6 C++ engine with the existing GameState interface.
Uses OpenMP parallel search for maximum performance.
"""

import os
import sys

# Add v6 directory to path for the compiled module
v6_dir = os.path.dirname(os.path.abspath(__file__))
if v6_dir not in sys.path:
    sys.path.insert(0, v6_dir)

# Try to import the compiled engine
try:
    import v6_engine
    V6_AVAILABLE = True
    print("[V6] C++ Engine loaded successfully!")
except ImportError as e:
    V6_AVAILABLE = False
    print(f"[V6] Warning: v6_engine module not found ({e}). Run CMake build.")

from main.engine.v3.chess_opening_book import OpeningBook

# Opening book
OPENING_BOOK = OpeningBook()

# Default parameters
DEFAULT_TIME_LIMIT = 5000  # 5 seconds in ms
DEFAULT_THREADS = os.cpu_count() or 4  # Use all available CPU threads


def find_best_move(game_state, valid_moves, engine, search_info=None):
    """
    Entry point for V6 engine.
    
    Args:
        game_state: V3 GameState object
        valid_moves: List of V3 Move objects
        engine: Engine name (for logging)
        search_info: Optional SearchInfo (not used for V6, has internal control)
    
    Returns:
        Tuple of (V3 Move object, stats dict)
    """
    if not V6_AVAILABLE:
        print("[V6] Engine not available, using first legal move")
        empty_stats = {'depth': 0, 'nodes': 0, 'time': 0, 'score': 0, 'nps': 0, 'pv': ''}
        return valid_moves[0] if valid_moves else None, empty_stats
    
    num_threads = DEFAULT_THREADS
    print(f"[V6] C++ Engine with OpenMP Parallel Search ({num_threads} threads)")
    
    # 1. Check opening book first
    fen_prefix = game_state.get_fen().split(" ")[0]
    book_moves = OPENING_BOOK.get_move(fen_prefix)
    if book_moves:
        for bm in book_moves:
            for vm in valid_moves:
                if str(vm) == bm:
                    print(f"[BOOK] {vm}")
                    empty_stats = {'depth': 0, 'nodes': 0, 'time': 0, 'score': 0, 'nps': 0, 'pv': bm}
                    return vm, empty_stats
    
    # 2. Get FEN and call C++ engine
    fen = game_state.get_fen()
    
    try:
        # Returns (move_str, score, depth, nodes, nps)
        move_str, score, depth, nodes, nps = v6_engine.find_best_move(
            fen,
            DEFAULT_TIME_LIMIT,
            num_threads
        )
        
        print(f"[V6] Best: {move_str} ({score} cp) depth={depth} nodes={nodes:,} nps={nps:,}")
        
        stats = {
            'depth': depth,
            'nodes': nodes,
            'time': DEFAULT_TIME_LIMIT / 1000.0,
            'score': score,
            'nps': nps,
            'pv': move_str
        }
        
    except Exception as e:
        print(f"[V6] Error: {e}")
        empty_stats = {'depth': 0, 'nodes': 0, 'time': 0, 'score': 0, 'nps': 0, 'pv': ''}
        return valid_moves[0] if valid_moves else None, empty_stats
    
    # 3. Match move string to V3 Move object
    chosen_move = None
    for vm in valid_moves:
        if str(vm) == move_str or str(vm).startswith(move_str):
            chosen_move = vm
            break
    
    if not chosen_move:
        # Try matching by coordinates
        if len(move_str) >= 4:
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
    
    print(f"[V6] Warning: Could not match move {move_str}, using first legal")
    return (valid_moves[0], stats) if valid_moves else (None, stats)


def find_top_moves(game_state, valid_moves, engine, top_n=3):
    """
    Return top N moves for hint system.
    """
    best, stats = find_best_move(game_state, valid_moves, engine)
    if best:
        return [{"move": str(best), "score": stats.get('score', 0)}]
    return []
