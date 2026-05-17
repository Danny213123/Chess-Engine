"""V6 UCI binary subprocess tests (Plan 02-02 Task 3).

Mirror of tests/test_uci_binaries.py (Plan 02-01, V7) for the new v6_uci
standalone executable added in Plan 02-02. Covers GAUNT-02 acceptance:
the binary handles the minimal UCI surface fastchess needs (uci,
isready, setoption, position, go movetime / wtime+btime, quit) and
exits cleanly.

INT-08 invariant: test_v6_engine_module_still_loads asserts the pybind11
v6_engine module continues to import after the CMakeLists.txt
modification. This test must PASS (not skip) — a regression in
v6_engine is a hard error per Phase 1 INT-08.

Subprocess-dependent tests skip cleanly when the v6_uci binary has not
been built (toolchain unavailable on the dev host, same gate as Phase 1
deferred verification).
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from chess_engine.engine.v6 import chess_algorithm as v6
from chess_engine.engine.v6.native_build import BUILD_DIR, V6_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_v6_uci_binary() -> Path | None:
    """Locate v6_uci or v6_uci.exe under the V6 build directory.

    Mirrors tests/test_v7_bindings.py::_find_v7_uci_binary search pattern
    (PATTERNS §"Skip-on-missing-binary"). Candidate directories cover
    single-config (build root) and multi-config (Release/RelWithDebInfo/
    Debug) generators.
    """
    candidate_names = ("v6_uci.exe", "v6_uci")
    candidate_dirs = (
        BUILD_DIR / "Release",
        BUILD_DIR / "RelWithDebInfo",
        BUILD_DIR / "Debug",
        BUILD_DIR,
        V6_DIR,
    )
    for directory in candidate_dirs:
        if not directory.exists():
            continue
        for name in candidate_names:
            candidate = directory / name
            if candidate.exists() and candidate.is_file():
                return candidate
    return None


def _run_uci(binary: Path, script: str, timeout: float = 5.0) -> subprocess.CompletedProcess[str]:
    """Run a v6_uci subprocess feeding it `script` on stdin.

    Returns the CompletedProcess with stdout + stderr captured separately
    so individual assertions can target the right stream.
    """
    return subprocess.run(
        [str(binary)],
        input=script,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def _skip_if_no_binary() -> Path:
    binary = _find_v6_uci_binary()
    if binary is None:
        pytest.skip(
            "v6_uci binary not found — CMake may not have produced it on this "
            "platform (toolchain unavailable, or v6_uci target not yet built)"
        )
    return binary


# ---------------------------------------------------------------------------
# INT-08 invariant — must PASS, not skip
# ---------------------------------------------------------------------------


def test_v6_engine_module_still_loads():
    """INT-08 (Phase 1 invariant): v6_engine pybind11 module continues to
    import after the v6_uci CMakeLists addition.

    This test must PASS, not skip — a regression in v6_engine is a hard
    error per the additive-target discipline (PATTERNS §"CMake
    additive-target discipline"). If pytest.skip() fires here, the
    invariant we just declared is unmeasured and the plan must NOT be
    considered complete.
    """
    try:
        module = v6.ensure_available(auto_build=True)
    except v6.V6UnavailableError as error:
        pytest.fail(
            f"INT-08 regression: v6_engine module no longer importable after "
            f"v6_uci CMakeLists addition. Error: {error}"
        )
    assert module is not None
    # Sanity: the module exposes the core functions GameManager relies on.
    assert hasattr(module, "find_best_move"), "v6_engine.find_best_move missing"
    assert hasattr(module, "evaluate"), "v6_engine.evaluate missing"


# ---------------------------------------------------------------------------
# UCI handshake / id name
# ---------------------------------------------------------------------------


def test_v6_uci_id_name():
    """`uci` command outputs `id name V6` and `uciok`."""
    binary = _skip_if_no_binary()
    proc = _run_uci(binary, "uci\nquit\n", timeout=5.0)
    assert "id name V6" in proc.stdout, (
        f"v6_uci did not advertise 'id name V6'. stdout={proc.stdout!r} "
        f"stderr={proc.stderr!r}"
    )
    assert "uciok" in proc.stdout, (
        f"v6_uci did not emit 'uciok'. stdout={proc.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Smoke: position + go movetime returns bestmove
# ---------------------------------------------------------------------------


def test_v6_uci_smoke():
    """`position startpos; go movetime 200` returns a bestmove line."""
    binary = _skip_if_no_binary()
    script = "uci\nposition startpos\ngo movetime 200\nquit\n"
    proc = _run_uci(binary, script, timeout=5.0)
    assert "bestmove " in proc.stdout, (
        f"v6_uci did not emit 'bestmove '. stdout={proc.stdout!r} "
        f"stderr={proc.stderr!r}"
    )


# ---------------------------------------------------------------------------
# setoption: silent accept (Hash / Threads / unknown name)
# ---------------------------------------------------------------------------


def _assert_setoption_silent(binary: Path, option_line: str) -> None:
    """Send a single setoption + isready; assert readyok with no error noise."""
    script = f"uci\n{option_line}\nisready\nquit\n"
    proc = _run_uci(binary, script, timeout=5.0)
    assert "readyok" in proc.stdout, (
        f"setoption broke isready. line={option_line!r} stdout={proc.stdout!r} "
        f"stderr={proc.stderr!r}"
    )
    combined = (proc.stdout + proc.stderr).lower()
    assert "unknown" not in combined, (
        f"setoption produced 'Unknown' output (should be silent). "
        f"line={option_line!r} combined={combined!r}"
    )
    assert "error" not in proc.stderr.lower(), (
        f"setoption produced 'error' on stderr. line={option_line!r} "
        f"stderr={proc.stderr!r}"
    )


def test_v6_uci_setoption_silent():
    """setoption name Hash value 64 is silently accepted (A4 asymmetry)."""
    binary = _skip_if_no_binary()
    _assert_setoption_silent(binary, "setoption name Hash value 64")


def test_v6_uci_threads_setoption():
    """setoption name Threads value 1 is silently accepted."""
    binary = _skip_if_no_binary()
    _assert_setoption_silent(binary, "setoption name Threads value 1")


def test_v6_uci_unknown_setoption():
    """setoption name FooBar value 1 is silently accepted (UCI protocol)."""
    binary = _skip_if_no_binary()
    _assert_setoption_silent(binary, "setoption name FooBar value 1")


# ---------------------------------------------------------------------------
# wtime/btime parsing: must honor TC, not fall back to 5 s default
# ---------------------------------------------------------------------------


def test_v6_uci_wtime_btime():
    """`go wtime 1000 btime 1000 winc 0 binc 0` returns a bestmove within ~1.5s.

    Heuristic: time budget = (my_time / 30) + my_inc = 1000/30 ≈ 33 ms.
    Even with V6's search overhead, total wall clock must be under 1.5 s —
    not the 5 s DEFAULT_GO_TIME_MS fallback. If this fires the 5 s timeout
    or takes > 1.5 s, the wtime parser is broken.
    """
    binary = _skip_if_no_binary()
    script = "position startpos\ngo wtime 1000 btime 1000 winc 0 binc 0\nquit\n"
    start = time.perf_counter()
    proc = _run_uci(binary, script, timeout=5.0)
    elapsed = time.perf_counter() - start
    assert "bestmove " in proc.stdout, (
        f"wtime/btime path did not emit bestmove. stdout={proc.stdout!r} "
        f"stderr={proc.stderr!r}"
    )
    assert elapsed < 1.5, (
        f"wtime/btime path took {elapsed:.2f} s — should be < 1.5 s "
        f"(suggests fallback to 5 s DEFAULT_GO_TIME_MS)"
    )


# ---------------------------------------------------------------------------
# movetime back-compat: existing depth/movetime parser still works
# ---------------------------------------------------------------------------


def test_v6_uci_movetime_backcompat():
    """`go movetime 200` returns a bestmove (movetime path still works)."""
    binary = _skip_if_no_binary()
    script = "ucinewgame\nposition startpos\ngo movetime 200\nquit\n"
    proc = _run_uci(binary, script, timeout=5.0)
    assert "bestmove " in proc.stdout, (
        f"movetime path did not emit bestmove. stdout={proc.stdout!r} "
        f"stderr={proc.stderr!r}"
    )
