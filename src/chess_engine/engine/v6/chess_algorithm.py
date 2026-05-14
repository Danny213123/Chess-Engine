"""
V6 Chess Algorithm Adapter
Integrates the V6 C++ engine with the existing GameState interface.
Uses OpenMP parallel search for maximum performance.
"""

import importlib.util
import os
from pathlib import Path
import sys


class V6UnavailableError(RuntimeError):
    """Raised when the requested V6 engine cannot provide a move."""


v6_engine = None
V6_AVAILABLE = False
_LOAD_ERROR = None
_AUTO_BUILD_ATTEMPTED = False


def _load_v6_engine():
    try:
        import v6_engine
        return v6_engine
    except ImportError as original_error:
        v6_dir = Path(__file__).resolve().parent
        for module_path in v6_dir.glob("v6_engine*"):
            if module_path.suffix not in {".so", ".pyd", ".dylib"}:
                continue

            spec = importlib.util.spec_from_file_location("v6_engine", module_path)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules["v6_engine"] = module
            spec.loader.exec_module(module)
            return module

        raise original_error


def reload_engine():
    """Reload the native module after a build or path change."""
    global V6_AVAILABLE, _LOAD_ERROR, v6_engine

    try:
        v6_engine = _load_v6_engine()
        V6_AVAILABLE = True
        _LOAD_ERROR = None
        return v6_engine
    except Exception as error:
        v6_engine = None
        V6_AVAILABLE = False
        _LOAD_ERROR = error
        return None


def ensure_available(auto_build=False):
    """Ensure the native V6 module is available, optionally building it once."""
    global _AUTO_BUILD_ATTEMPTED

    if V6_AVAILABLE and v6_engine is not None:
        return v6_engine

    module = reload_engine()
    if module is not None:
        return module

    if auto_build and not _AUTO_BUILD_ATTEMPTED:
        _AUTO_BUILD_ATTEMPTED = True
        from chess_engine.engine.v6.native_build import V6BuildError, build_v6_native

        try:
            build_v6_native(force=True)
        except V6BuildError as error:
            raise V6UnavailableError(str(error)) from error

        module = reload_engine()
        if module is not None:
            return module

    detail = f": {_LOAD_ERROR}" if _LOAD_ERROR else ""
    raise V6UnavailableError(
        "V6 native engine is not available. Build it with "
        "`node cli/bin/chess-engine.js build v6` or select V6 again after "
        f"installing CMake and a C++17 compiler{detail}."
    )


if reload_engine() is not None:
    print("[V6] C++ Engine loaded successfully!")
else:
    print(f"[V6] Warning: v6_engine module not found ({_LOAD_ERROR}). Run CMake build.")

from chess_engine.engine.v3.chess_opening_book import OpeningBook

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
    engine_module = ensure_available(auto_build=False)
    
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
        move_str, score, depth, nodes, nps = engine_module.find_best_move(
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
        raise RuntimeError(f"V6 search failed: {e}") from e
    
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
    
    raise RuntimeError(f"V6 returned move {move_str!r}, but it was not legal in this position.")


def find_top_moves(game_state, valid_moves, engine, top_n=3):
    """
    Return top N moves for hint system.
    """
    best, stats = find_best_move(game_state, valid_moves, engine)
    if best:
        return [{"move": str(best), "score": stats.get('score', 0)}]
    return []
