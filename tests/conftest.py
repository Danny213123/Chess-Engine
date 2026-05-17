"""
Shared pytest fixtures for chess engine tests.
"""


import json
import os
import platform  # noqa: F401  # re-exported for downstream fixtures / future host shaping
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pytest
from chess_engine.engine.v2.chess_engine import GameState, Move


@pytest.fixture
def initial_game():
    """Create a fresh game state with initial position."""
    return GameState()


@pytest.fixture
def empty_board_game():
    """Create a game state with an empty board (only kings)."""
    gs = GameState()
    # Clear the board
    for row in range(8):
        for col in range(8):
            gs.board[row][col] = "--"
    # Place kings at e1 and e8
    gs.board[0][4] = "bK"
    gs.board[7][4] = "wK"
    gs.white_king = (7, 4)
    gs.black_king = (0, 4)
    return gs


def make_move_from_notation(gs, start, end):
    """
    Helper to make a move from algebraic-style notation.
    start/end are tuples like (row, col) where row 0 = rank 8, col 0 = file a.
    """
    valid_moves = gs.get_valid_moves()
    for move in valid_moves:
        if (move.start_row, move.start_col) == start and (move.end_row, move.end_col) == end:
            gs.make_move(move)
            return move
    return None


def find_move(gs, start, end):
    """Find a move in valid moves list without making it."""
    valid_moves = gs.get_valid_moves()
    for move in valid_moves:
        if (move.start_row, move.start_col) == start and (move.end_row, move.end_col) == end:
            return move
    return None


def move_exists(gs, start, end):
    """Check if a move exists in valid moves."""
    return find_move(gs, start, end) is not None


def count_moves_from_square(gs, row, col):
    """Count how many valid moves originate from a square."""
    valid_moves = gs.get_valid_moves()
    return sum(1 for m in valid_moves if m.start_row == row and m.start_col == col)


# Common board setups as fixtures
@pytest.fixture
def scholars_mate_position():
    """Position right before Scholar's Mate."""
    gs = GameState()
    # 1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6??
    moves = [
        ((6, 4), (4, 4)),  # e4
        ((1, 4), (3, 4)),  # e5
        ((7, 5), (4, 2)),  # Bc4
        ((0, 1), (2, 2)),  # Nc6
        ((7, 3), (3, 7)),  # Qh5
        ((0, 6), (2, 5)),  # Nf6??
    ]
    for start, end in moves:
        make_move_from_notation(gs, start, end)
    return gs


@pytest.fixture  
def castling_available_position():
    """Position where castling is available for white."""
    gs = GameState()
    # Clear pieces between king and rooks
    gs.board[7][5] = "--"  # Remove bishop
    gs.board[7][6] = "--"  # Remove knight
    gs.board[7][1] = "--"  # Remove knight
    gs.board[7][2] = "--"  # Remove bishop
    gs.board[7][3] = "--"  # Remove queen
    return gs


@pytest.fixture
def en_passant_position():
    """Position where en passant is possible for white."""
    gs = GameState()
    # Set up white pawn on 5th rank, black pawn just moved 2 squares
    gs.board[6][4] = "--"  # Remove white e pawn from start
    gs.board[3][4] = "wP"  # Place white pawn on e5
    gs.board[1][3] = "--"  # Remove black d pawn from start  
    gs.board[3][3] = "bP"  # Place black pawn on d5 (just moved)
    gs.enpassant_possible = (2, 3)  # d6 is en passant target
    return gs


@pytest.fixture
def checkmate_position():
    """Simple back rank checkmate position."""
    gs = GameState()
    # Clear board
    for row in range(8):
        for col in range(8):
            gs.board[row][col] = "--"
    # Set up back rank mate
    gs.board[7][7] = "wK"  # White king in corner
    gs.board[7][6] = "wP"  # Pawns blocking escape
    gs.board[6][6] = "wP"
    gs.board[6][7] = "wP"
    gs.board[7][0] = "bR"  # Black rook delivering mate
    gs.board[0][4] = "bK"  # Black king
    gs.white_king = (7, 7)
    gs.black_king = (0, 4)
    return gs


@pytest.fixture
def stalemate_position():
    """Position where it's stalemate for white."""
    gs = GameState()
    # Clear board
    for row in range(8):
        for col in range(8):
            gs.board[row][col] = "--"
    # Classic stalemate: king in corner, queen trapping
    gs.board[0][0] = "wK"  # White king trapped
    gs.board[1][2] = "bQ"  # Queen controls escape squares
    gs.board[7][7] = "bK"  # Black king
    gs.white_king = (0, 0)
    gs.black_king = (7, 7)
    return gs


# ---------------------------------------------------------------------------
# Phase 2 shared fixtures (Plan 02-05 Task 1)
#
# Added per Plan 02-05 must_haves.truths: gauntlet_root, summary_json_factory,
# latest_summary_dir, and _find_uci_binary helper. Consumed by
# tests/test_nps_regression.py and tests/test_gauntlet_sanity.py.
#
# IMPORTANT: pre-existing fixtures above are intentionally NOT touched —
# Phase 1 callers (test_v7_bindings.py, test_engine.py, etc.) must keep
# their fixture-scope contract.
# ---------------------------------------------------------------------------


def _find_uci_binary(engine: str) -> Optional[Path]:
    """Locate ``<engine>_uci`` or ``<engine>_uci.exe`` under the engine's build dir.

    Generalizes the per-engine helpers (``_find_v6_uci_binary`` in
    tests/test_uci_binaries_v6.py and ``_find_v7_uci_binary`` in
    tests/test_v7_bindings.py) so callers — including the Plan 02-05
    Task 3 sanity probe — share one search pattern.

    Search order mirrors tools/gauntlet.py:_candidate_uci_paths:
      build/Release, build/RelWithDebInfo, build/Debug, build, <engine_dir>
    × {<engine>_uci.exe, <engine>_uci}

    Returns the first existing file Path, or None when none of the candidates
    exist. Never raises (callers may skip gracefully on None).
    """
    engine_dir = Path("src/chess_engine/engine") / engine
    build_dir = engine_dir / "build"
    candidate_dirs = (
        build_dir / "Release",
        build_dir / "RelWithDebInfo",
        build_dir / "Debug",
        build_dir,
        engine_dir,
    )
    candidate_names = (f"{engine}_uci.exe", f"{engine}_uci")
    for directory in candidate_dirs:
        if not directory.exists():
            continue
        for name in candidate_names:
            candidate = directory / name
            if candidate.exists() and candidate.is_file():
                return candidate
    return None


@pytest.fixture
def gauntlet_root(tmp_path: Path) -> Path:
    """Return a tmp_path subdirectory simulating ``.planning/gauntlets/``.

    Function-scoped so each test gets an isolated tree — the NPS sentinel
    "latest summary" discovery is sensitive to sibling timestamps so cross-
    test bleed would be a real bug source.
    """
    root = tmp_path / "gauntlets"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _default_summary_payload(
    *,
    timestamp: str,
    v7_bench_nps: Optional[int],
    v6_bench_nps: Optional[int],
    verdict: str,
    elo: Optional[float],
    investigation_required: bool,
) -> Dict[str, Any]:
    """Build the Plan 02-04b summary.json schema (mirrors tools.gauntlet.write_summary).

    Kept private so callers go through ``summary_json_factory`` — that way the
    overrides-merge behaviour stays in one place.
    """
    return {
        "schema_version": 1,
        "timestamp_utc": timestamp,
        "engines": {
            "v6": {
                "cmd": "/fake/v6_uci",
                "git_sha": "deadbee",
                "options": {"Hash": 64, "Threads": 1},
            },
            "v7": {
                "cmd": "/fake/v7_uci",
                "git_sha": "deadbee",
                "options": {"Hash": 64, "Threads": 1},
            },
        },
        "tc": "10+0.1",
        "concurrency": 1,
        "openings": {
            "file": "/fake/tools/books/8moves_v3.pgn",
            "format": "pgn",
            "order": "random",
        },
        "sprt": None,
        "fastchess_command": ["/fake/fastchess", "-engine", "..."],
        "fastchess_version": "v1.8.0-alpha",
        "host": {"os": "Linux", "cpu": "x86_64", "cores": 8},
        "result": {
            "verdict": verdict,
            "elo": elo,
            "elo_err": 5.0,
            "elo_ci": 95,
            "llr": None,
            "llr_lower": None,
            "llr_upper": None,
            "games": {"n": 200, "w": 80, "l": 80, "d": 40},
            "penta": [10, 20, 40, 20, 10],
            "time_forfeits": {"v6": 0, "v7": 0},
            "other_terminations": {"v6": 0, "v7": 0},
            "investigation_required": investigation_required,
        },
        "nps": {
            "v6": {
                "bench_nps": v6_bench_nps,
                "median": v6_bench_nps,
                "mean": float(v6_bench_nps) if v6_bench_nps is not None else None,
                "samples": 12 if v6_bench_nps is not None else 0,
            },
            "v7": {
                "bench_nps": v7_bench_nps,
                "median": v7_bench_nps,
                "mean": float(v7_bench_nps) if v7_bench_nps is not None else None,
                "samples": 12 if v7_bench_nps is not None else 0,
            },
        },
    }


@pytest.fixture
def summary_json_factory(gauntlet_root: Path) -> Callable[..., Path]:
    """Return a callable that writes a synthetic summary.json under gauntlet_root.

    Signature::

        make(
            timestamp="2026-05-16T21-00-00Z",
            v7_bench_nps=500_000,
            v6_bench_nps=600_000,
            verdict="H1",
            elo=13.87,
            investigation_required=False,
            **overrides,
        ) -> Path

    The returned Path is ``<gauntlet_root>/<timestamp>/summary.json``. Any
    ``**overrides`` shallow-merge into the top-level dict so a single test
    can flip e.g. ``result`` or ``nps`` to a custom shape.

    The synthesized payload mirrors the Plan 02-04b schema produced by
    :func:`tools.gauntlet.write_summary` — same top-level keys (schema_version,
    timestamp_utc, engines, tc, concurrency, openings, sprt, fastchess_command,
    fastchess_version, host, result, nps), same nested shapes. The
    ``investigation_required`` flag lives at ``summary["result"]["investigation_required"]``
    matching tools/gauntlet.py line 457 and tests/test_gauntlet_io.py line 178.
    """

    def make(
        timestamp: str = "2026-05-16T21-00-00Z",
        v7_bench_nps: Optional[int] = 500_000,
        v6_bench_nps: Optional[int] = 600_000,
        verdict: str = "H1",
        elo: Optional[float] = 13.87,
        investigation_required: bool = False,
        **overrides: Any,
    ) -> Path:
        payload = _default_summary_payload(
            timestamp=timestamp,
            v7_bench_nps=v7_bench_nps,
            v6_bench_nps=v6_bench_nps,
            verdict=verdict,
            elo=elo,
            investigation_required=investigation_required,
        )
        # Shallow merge — caller-overrides win
        for key, value in overrides.items():
            payload[key] = value

        run_dir = gauntlet_root / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)
        summary_path = run_dir / "summary.json"
        summary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return summary_path

    return make


@pytest.fixture
def latest_summary_dir(gauntlet_root: Path) -> Callable[[], Optional[Path]]:
    """Return a callable that yields the lexically-greatest sub-dir of gauntlet_root.

    Mirrors the sentinel's production discovery (``sorted(root.iterdir())[-1]``)
    but as a fixture-callable so a test can re-poll after writing more summaries.
    Returns None when ``gauntlet_root`` has no children — callers use this to
    exercise the "skip on empty" branch.
    """

    def _get() -> Optional[Path]:
        children: List[Path] = sorted(p for p in gauntlet_root.iterdir() if p.is_dir())
        if not children:
            return None
        return children[-1]

    return _get
