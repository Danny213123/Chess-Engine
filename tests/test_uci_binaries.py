"""Subprocess tests for the V7 (and later V6) UCI standalone binaries.

Phase 2 / Plan 02-01 (GAUNT-02): verify v7_uci accepts the UCI surface
fastchess drives — `setoption name <NAME> value <V>` (silent accept) and
`go wtime W btime B winc I binc J` (time-budget heuristic) — without
regressing Phase 1's `depth N` / `movetime MS` handling.

The V6-side tests land in Plan 02-02 once `v6_uci` exists. Until then
this file covers V7 only.

Test discipline:
  - Each subprocess call is wrapped with `timeout=5.0`; the whole module
    must finish well under 15s.
  - Tests `pytest.skip(...)` when the v7_uci binary isn't on disk so CI
    on hosts without the C++ toolchain stays green.
  - `capture_output=True` keeps stdout / stderr separately inspectable so
    we can assert "no 'unknown' / no error" cleanly. (fastchess merges
    streams; tests do not, deliberately.)
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from chess_engine.engine.v7.native_build import BUILD_DIR, V7_DIR


# --- Binary discovery -------------------------------------------------------


def _find_v7_uci_binary() -> Path | None:
    """Locate v7_uci or v7_uci.exe under the V7 build directory.

    Copied verbatim from tests/test_v7_bindings.py lines 163-184 per the
    Plan 02-01 instruction; the cross-engine generalization (v6_uci
    discovery + a shared helper) happens in Plan 02-02.
    """
    candidate_names = ("v7_uci.exe", "v7_uci")
    candidate_dirs = (
        BUILD_DIR / "Release",
        BUILD_DIR / "RelWithDebInfo",
        BUILD_DIR / "Debug",
        BUILD_DIR,
        V7_DIR,
    )
    for directory in candidate_dirs:
        if not directory.exists():
            continue
        for name in candidate_names:
            candidate = directory / name
            if candidate.exists() and candidate.is_file():
                return candidate
    return None


# --- Shared helper ----------------------------------------------------------


def _run_uci(binary: Path, script: str, timeout: float = 5.0) -> subprocess.CompletedProcess:
    """Drive a UCI binary with the given stdin script and return the result.

    `capture_output=True` keeps stdout / stderr separately inspectable —
    fastchess merges streams in production, but the tests need the
    two-stream form to assert "no error printed".
    """
    return subprocess.run(
        [str(binary)],
        input=script,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def _require_v7_uci() -> Path:
    binary = _find_v7_uci_binary()
    if binary is None:
        pytest.skip(
            "v7_uci binary not found — CMake may not have produced it on this platform"
        )
    return binary


# --- GAUNT-02: setoption silent accept --------------------------------------


def test_v7_uci_setoption() -> None:
    """setoption name Hash value 64 is silently accepted (no error)."""
    binary = _require_v7_uci()
    script = "uci\nsetoption name Hash value 64\nisready\nquit\n"
    result = _run_uci(binary, script)
    combined = (result.stdout + result.stderr).lower()
    assert "readyok" in result.stdout, (
        f"v7_uci did not respond 'readyok' after setoption Hash. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "unknown" not in combined, (
        f"v7_uci printed an 'unknown' diagnostic for setoption Hash. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "error" not in result.stderr.lower(), (
        f"v7_uci printed an error to stderr for setoption Hash. "
        f"stderr={result.stderr!r}"
    )


def test_v7_uci_threads_setoption() -> None:
    """setoption name Threads value 1 is silently accepted (no error)."""
    binary = _require_v7_uci()
    script = "uci\nsetoption name Threads value 1\nisready\nquit\n"
    result = _run_uci(binary, script)
    combined = (result.stdout + result.stderr).lower()
    assert "readyok" in result.stdout
    assert "unknown" not in combined, (
        f"v7_uci printed 'unknown' for setoption Threads. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "error" not in result.stderr.lower()


def test_v7_uci_unknown_setoption() -> None:
    """setoption name SyzygyPath value /tmp is silently accepted (unrecognized name)."""
    binary = _require_v7_uci()
    script = "uci\nsetoption name SyzygyPath value /tmp\nisready\nquit\n"
    result = _run_uci(binary, script)
    combined = (result.stdout + result.stderr).lower()
    assert "readyok" in result.stdout
    assert "unknown" not in combined, (
        f"v7_uci printed 'unknown' for unrecognized setoption. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "error" not in result.stderr.lower()


# --- GAUNT-02: wtime/btime heuristic ----------------------------------------


def test_v7_uci_wtime_btime_respected() -> None:
    """go wtime 1000 btime 1000 winc 0 binc 0 returns bestmove within ~1.5s.

    (1000/30) + 0 ≈ 33ms budget — if the wtime branch is not wired and the
    code falls back to DEFAULT_GO_TIME_MS=5000, the subprocess will take
    ~5s and this test fails on the elapsed bound. The 1.5s ceiling
    generously absorbs process spawn + Engine warmup + Windows scheduling
    jitter while still cleanly catching the 5-second-fallback regression.
    """
    binary = _require_v7_uci()
    script = (
        "uci\n"
        "ucinewgame\n"
        "position startpos\n"
        "go wtime 1000 btime 1000 winc 0 binc 0\n"
        "quit\n"
    )
    start = time.perf_counter()
    result = _run_uci(binary, script, timeout=5.0)
    elapsed = time.perf_counter() - start
    assert "bestmove " in result.stdout, (
        f"v7_uci did not emit a bestmove for wtime/btime go. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert elapsed < 1.5, (
        f"v7_uci took {elapsed:.2f}s under wtime=1000 — looks like the "
        f"5-second DEFAULT_GO_TIME_MS fallback fired instead of the "
        f"(wtime/30)+winc budget. stdout={result.stdout!r}"
    )


# --- Phase 1 back-compat -----------------------------------------------------


def test_v7_uci_depth_backcompat() -> None:
    """go depth 3 still returns a bestmove (Phase 1 depth handling preserved)."""
    binary = _require_v7_uci()
    script = (
        "uci\n"
        "ucinewgame\n"
        "position startpos\n"
        "go depth 3\n"
        "quit\n"
    )
    result = _run_uci(binary, script, timeout=5.0)
    assert "bestmove " in result.stdout, (
        f"v7_uci did not emit a bestmove for depth-3 search. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_v7_uci_movetime_backcompat() -> None:
    """go movetime 200 still returns a bestmove (Phase 1 movetime handling preserved)."""
    binary = _require_v7_uci()
    script = (
        "uci\n"
        "ucinewgame\n"
        "position startpos\n"
        "go movetime 200\n"
        "quit\n"
    )
    start = time.perf_counter()
    result = _run_uci(binary, script, timeout=5.0)
    elapsed = time.perf_counter() - start
    assert "bestmove " in result.stdout, (
        f"v7_uci did not emit a bestmove for movetime=200 search. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    # movetime=200 should finish well under 2s including process spawn;
    # if it took the 5s fallback we have a regression.
    assert elapsed < 2.0, (
        f"v7_uci took {elapsed:.2f}s under movetime=200 — Phase 1 "
        f"movetime handling may have regressed. stdout={result.stdout!r}"
    )
