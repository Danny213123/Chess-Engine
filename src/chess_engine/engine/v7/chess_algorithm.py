"""
V7 Chess Algorithm Adapter
Integrates the V7 C++ engine with the existing GameState interface.

V7 uses a stateful Engine class (vs V6's free-function binding). This closes
V6's silently-ignored-SearchInfo bug (FOUND-04) by exposing a C++ atomic stop
flag observable from any Python thread without holding the GIL (FOUND-05).
"""

import importlib.util
import os
from pathlib import Path
import sys


class V7UnavailableError(RuntimeError):
    """Raised when the requested V7 engine cannot provide a move."""


v7_engine = None
V7_AVAILABLE = False
_LOAD_ERROR = None
_AUTO_BUILD_ATTEMPTED = False

# Module-level Engine singleton (Open Question 3 resolution: module-singleton
# with explicit per-game reset via new_game()). Lazy-instantiated inside
# find_best_move on first use so import never fails when the native module
# is unbuilt.
_engine = None

_REQUIRED_NATIVE_API = ("Engine", "SearchResult", "perft", "evaluate")


def _validate_native_module(module):
    """Reject stale v7_engine builds that do not match this adapter."""
    missing = [name for name in _REQUIRED_NATIVE_API if not hasattr(module, name)]
    if missing:
        raise V7UnavailableError(
            "Loaded v7_engine is stale or incompatible; missing native binding(s): "
            + ", ".join(missing)
            + ". Rebuild V7 with `node cli/bin/chess-engine.js build v7`."
        )
    return module


def _load_module_from_path(module_path):
    spec = importlib.util.spec_from_file_location("v7_engine", module_path)
    if spec is None or spec.loader is None:
        raise V7UnavailableError(f"Unable to load V7 native module at {module_path}.")

    module = importlib.util.module_from_spec(spec)
    sys.modules["v7_engine"] = module
    try:
        spec.loader.exec_module(module)
        return _validate_native_module(module)
    except Exception:
        sys.modules.pop("v7_engine", None)
        raise


def _load_v7_engine(module_path=None):
    if module_path is not None:
        return _load_module_from_path(Path(module_path))

    try:
        import v7_engine
        try:
            return _validate_native_module(v7_engine)
        except V7UnavailableError:
            sys.modules.pop("v7_engine", None)
            raise
    except ImportError as original_error:
        v7_dir = Path(__file__).resolve().parent
        load_error = original_error
        for module_path in v7_dir.glob("v7_engine*"):
            if module_path.suffix not in {".so", ".pyd", ".dylib"}:
                continue
            try:
                return _load_module_from_path(module_path)
            except Exception as path_error:
                load_error = path_error
                continue

        raise load_error


def reload_engine(module_path=None):
    """Reload the native module after a build or path change."""
    global V7_AVAILABLE, _LOAD_ERROR, v7_engine, _engine

    try:
        v7_engine = _load_v7_engine(module_path)
        V7_AVAILABLE = True
        _LOAD_ERROR = None
        # Drop any stale engine instance; it'll be re-created lazily on
        # the next find_best_move call.
        _engine = None
        return v7_engine
    except Exception as error:
        v7_engine = None
        V7_AVAILABLE = False
        _LOAD_ERROR = error
        _engine = None
        return None


def ensure_available(auto_build=False):
    """Ensure the native V7 module is available, optionally building it once."""
    global _AUTO_BUILD_ATTEMPTED

    if V7_AVAILABLE and v7_engine is not None:
        return v7_engine

    module = reload_engine()
    if module is not None:
        return module

    if auto_build and not _AUTO_BUILD_ATTEMPTED:
        _AUTO_BUILD_ATTEMPTED = True
        from chess_engine.engine.v7.native_build import V7BuildError, build_v7_native

        try:
            build_result = build_v7_native(force=True)
        except V7BuildError as error:
            raise V7UnavailableError(str(error)) from error

        module = reload_engine(build_result.module_path)
        if module is not None:
            return module

    detail = f": {_LOAD_ERROR}" if _LOAD_ERROR else ""
    raise V7UnavailableError(
        "V7 native engine is not available. Build it with "
        "`node cli/bin/chess-engine.js build v7` or select V7 again after "
        f"installing CMake and a C++17 compiler{detail}."
    )


if reload_engine() is not None:
    print("[V7] C++ Engine loaded successfully!")
else:
    print(f"[V7] Warning: v7_engine module not found ({_LOAD_ERROR}). Run CMake build.")


# Default parameters
DEFAULT_TIME_LIMIT = 5000  # 5 seconds in ms
DEFAULT_DEPTH = 6  # D-04: Phase 1 smoke milestone uses fixed depth 6
# TODO(future-plan): re-enable OpeningBook for V7 (V6 uses chess_engine.engine.v3.chess_opening_book.OpeningBook).
# Phase 1 declines the book per research §Pattern note — V7 plays from the
# starting position with no book to keep the smoke test scope minimal.


def _get_or_create_engine():
    """Return the module-level Engine singleton, creating it on first use."""
    global _engine
    if _engine is None:
        module = ensure_available(auto_build=False)
        _engine = module.Engine()
    return _engine


def _native_move_to_uci(move):
    """Decode V7's packed 16-bit native move into UCI notation."""
    try:
        move_value = int(move)
    except (TypeError, ValueError):
        return ""

    if move_value == 0:
        return ""

    from_sq = move_value & 0x3F
    to_sq = (move_value >> 6) & 0x3F
    move_type = (move_value >> 14) & 0x3
    promo_index = (move_value >> 12) & 0x3

    def square_name(square):
        return f"{chr(ord('a') + (square & 7))}{1 + (square >> 3)}"

    uci = square_name(from_sq) + square_name(to_sq)
    if move_type == 1:
        uci += "nbrq"[promo_index]
    return uci


def stop_engine():
    """Flip the C++ atomic stop flag.

    Safe to call from any Python thread WITHOUT holding the GIL on the C++
    side: the binding for Engine.stop() does NOT release the GIL (it's a
    single atomic write), and the search binding DOES release the GIL while
    running — so the search thread observes this flip via the next per-node
    stop poll. Closes FOUND-04 (V6 ignored search_info).

    Wired from GameManager.stop_search() in plan 06.
    """
    if _engine is not None:
        try:
            _engine.stop()
        except Exception:
            # Never raise from a stop path; cancellation must not error.
            pass


def new_game():
    """Reset V7's per-game state (TT, repetition stack, atomic counters).

    Plan 01 ships a stub Engine.new_game() that resets the atomics; plans
    02/03 populate the real TT + rep-stack clears.
    """
    if _engine is not None:
        try:
            _engine.new_game()
        except Exception:
            pass


def find_best_move(game_state, valid_moves, engine, search_info=None):
    """Entry point for V7 engine.

    Args:
        game_state: V3 GameState object
        valid_moves: List of V3 Move objects
        engine: Engine name (for logging / dispatch parity with adapter contract)
        search_info: search_info is accepted for adapter-contract
            compatibility; cancellation for V7 is delivered via
            stop_engine() which flips the C++ atomic — see plan 01
            known_correction in PLAN.md. (FOUND-03 adapter contract;
            wiring of GameManager.stop_search -> stop_engine() lands
            in plan 06.)

    Returns:
        Tuple of (V3 Move object, stats dict)
    """
    module = ensure_available(auto_build=False)
    engine_obj = _get_or_create_engine()

    fen = game_state.get_fen()

    try:
        result = engine_obj.search(fen, depth=DEFAULT_DEPTH, time_ms=DEFAULT_TIME_LIMIT)
    except Exception as e:
        raise RuntimeError(f"V7 search failed: {e}") from e

    # Plan 01 ships a stub Engine.search returning an empty SearchResult.
    # Plan 03 fills in best_move / score / depth / nodes / nps. The adapter
    # tolerates the stub by returning the first valid move so smoke
    # plumbing-tests don't blow up, but plan 03's tests assert real values.
    move_str = ""
    score = 0
    depth = 0
    nodes = 0
    nps = 0
    if result is not None:
        # SearchResult bindings (plan 01 ships a minimal struct; plan 03 expands)
        score = getattr(result, "score", 0)
        depth = getattr(result, "depth", 0)
        nodes = getattr(result, "nodes", 0)
        nps = getattr(result, "nps", 0)
        best_move = getattr(result, "best_move", 0)
        # plan 01: best_move is int (MOVE_NONE=0); plan 02 replaces with v7::Move
        # plan 03 emits a UCI string via SearchResult.pv or via a binding helper.
        # Until then, accept a string-shaped attribute if present.
        if isinstance(best_move, str):
            move_str = best_move
        else:
            move_str = _native_move_to_uci(best_move) or getattr(result, "pv", "") or ""

    stats = {
        "depth": depth,
        "nodes": nodes,
        "time": DEFAULT_TIME_LIMIT / 1000.0,
        "score": score,
        "nps": nps,
        "pv": move_str,
    }

    # 3. Match move string to V3 Move object (mirror V6 lines 162-189)
    chosen_move = None
    if move_str:
        for vm in valid_moves:
            if str(vm) == move_str or str(vm).startswith(move_str):
                chosen_move = vm
                break

        if not chosen_move and len(move_str) >= 4:
            from_sq = move_str[:2]
            to_sq = move_str[2:4]
            from_col = ord(from_sq[0]) - ord("a")
            from_row = 8 - int(from_sq[1])
            to_col = ord(to_sq[0]) - ord("a")
            to_row = 8 - int(to_sq[1])
            for vm in valid_moves:
                if (
                    vm.start_row == from_row
                    and vm.start_col == from_col
                    and vm.end_row == to_row
                    and vm.end_col == to_col
                ):
                    chosen_move = vm
                    break

    if chosen_move:
        return chosen_move, stats

    # Plan 01 stub returns MOVE_NONE — surface a clear error so smoke tests
    # can detect that plan 03's search body is still pending.
    raise RuntimeError(
        f"V7 returned move {move_str!r}, but it was not legal in this position "
        "(plan 01 ships a stub Engine.search; plan 03 implements the real body)."
    )


def find_top_moves(game_state, valid_moves, engine, top_n=3):
    """Return top N moves for hint system."""
    best, stats = find_best_move(game_state, valid_moves, engine)
    if best:
        return [{"move": str(best), "score": stats.get("score", 0)}]
    return []
