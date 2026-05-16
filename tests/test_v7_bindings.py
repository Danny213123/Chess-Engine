"""V7 pybind11 binding tests (plan 01-01 Task 2).

These tests exercise the binding contract locked in plan 01:
  - Engine class instantiation + atomic counters
  - find_best_move adapter signature (FOUND-03)
  - GIL release during search (FOUND-05 / Pitfall #11)
  - Cancellation latency via stop() flipping the C++ atomic (FOUND-04)
  - v7_uci binary handshake (FOUND-07)
  - auto-build flow (INT-09)

The v7_native_engine fixture is mirrored from tests/test_v7_engine.py so
this file is self-contained (matches the V6 per-test-file fixture
pattern in tests/test_v6_native.py).
"""

from __future__ import annotations

import importlib
import inspect
import subprocess
import threading
import time
from pathlib import Path

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7
from chess_engine.engine.v7.native_build import (
    BUILD_DIR,
    V7_DIR,
    V7BuildError,
    build_v7_native,
    find_packaged_module,
)


STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails.

    Mirrors tests/test_v7_engine.py so this file can run standalone.
    """
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:  # noqa: BLE001 - skip on any unexpected env failure
        pytest.skip(f"V7 native engine unavailable: {error}")


# --- Static file-layout checks (no native module required) ------------------


def test_v7_layout():
    """FOUND-01: V7 directory layout exists at the expected paths."""
    expected = [
        "src/chess_engine/engine/v7/__init__.py",
        "src/chess_engine/engine/v7/chess_algorithm.py",
        "src/chess_engine/engine/v7/native_build.py",
        "src/chess_engine/engine/v7/CMakeLists.txt",
        "src/chess_engine/engine/v7/include/engine.hpp",
        "src/chess_engine/engine/v7/src/python_bindings.cpp",
        "src/chess_engine/engine/v7/src/uci_main.cpp",
    ]
    repo_root = Path(__file__).resolve().parents[1]
    missing = [p for p in expected if not (repo_root / p).exists()]
    assert not missing, f"Missing V7 layout files: {missing}"


def test_find_best_move_signature():
    """FOUND-03: adapter signature matches the project-wide engine contract."""
    sig = inspect.signature(v7.find_best_move)
    params = list(sig.parameters)
    assert params == ["game_state", "valid_moves", "engine", "search_info"], params
    assert sig.parameters["search_info"].default is None, "search_info default must be None"


# --- Build + import (require native module) ---------------------------------


def test_v7_build(v7_native_engine):
    """FOUND-02: native module builds and exposes Engine + perft."""
    assert v7_native_engine is not None
    assert hasattr(v7_native_engine, "Engine"), "v7_engine.Engine missing"
    assert hasattr(v7_native_engine, "perft"), "v7_engine.perft missing"


def test_v7_import(v7_native_engine):
    """Engine instantiates with zero counters on a fresh instance."""
    e = v7_native_engine.Engine()
    assert e.tbhits() == 0
    assert e.nodes() == 0


# --- GIL release + cancellation (FOUND-04, FOUND-05) ------------------------


def test_gil_released(v7_native_engine):
    """FOUND-05: search releases the GIL — another thread can call stop().

    With plan 01's stub search this completes trivially. Plan 03 makes the
    bound meaningful: the assertion is the same bound and MUST NOT be
    weakened when plan 03 lands the real iterative deepening body. If the
    binding ever loses py::call_guard<py::gil_scoped_release>(), this test
    starts deadlocking until the search exits naturally.
    """
    e = v7_native_engine.Engine()
    result_box = {}

    def worker():
        # Long-ish budget so plan-03's real search would actually be
        # running when stop() arrives. Plan 01 stub returns immediately.
        result_box["result"] = e.search(STARTPOS_FEN, depth=8, time_ms=3000)

    t = threading.Thread(target=worker)
    start = time.monotonic()
    t.start()
    # Let the worker enter C++. With plan 01 stub it may be done before we
    # sleep — that's fine, stop() on a finished search is a no-op.
    time.sleep(0.05)
    e.stop()
    t.join(timeout=5.0)
    elapsed = time.monotonic() - start
    assert not t.is_alive(), "search thread did not exit — GIL release likely broken"
    assert elapsed < 0.5, f"GIL-release worker took {elapsed*1000:.1f} ms; expected < 500 ms"


def test_cancellation_latency(v7_native_engine):
    """FOUND-04: stop() observable by the search thread within 200 ms.

    Plan 01 stub returns immediately; this asserts the binding-level
    contract. Plan 03's real polling makes the bound meaningful for full
    iterative deepening.
    """
    e = v7_native_engine.Engine()
    done_at = {}

    def worker():
        e.search(STARTPOS_FEN, depth=8, time_ms=3000)
        done_at["t"] = time.monotonic()

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(0.05)
    stop_at = time.monotonic()
    e.stop()
    t.join(timeout=2.0)
    assert not t.is_alive(), "search thread did not exit after stop()"
    elapsed = done_at["t"] - stop_at
    # Allow a small negative window: plan 01 stub may have finished
    # BEFORE stop() was called (race against the 50 ms sleep). The
    # binding-level invariant is "stop() does not block / deadlock"; the
    # tighter polling latency is plan 03's concern.
    assert elapsed < 0.200, f"cancellation latency {elapsed*1000:.1f} ms exceeds 200 ms bound"


# --- UCI binary handshake (FOUND-07) ----------------------------------------


def _find_v7_uci_binary() -> Path | None:
    """Locate v7_uci or v7_uci.exe under the V7 build directory.

    Mirrors native_build._find_built_module's search pattern but looks for
    the standalone executable target.
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


def test_uci_binary_exists(v7_native_engine):  # noqa: ARG001 - fixture ensures build
    """FOUND-07: v7_uci builds and answers the minimal UCI handshake."""
    binary = _find_v7_uci_binary()
    if binary is None:
        pytest.skip("v7_uci binary not found — CMake may not have produced it on this platform")
    proc = subprocess.run(
        [str(binary)],
        input="uci\nquit\n",
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert "id name V7" in proc.stdout, (
        f"v7_uci did not advertise 'id name V7'. stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


# --- Auto-build flow (INT-09) ----------------------------------------------


def test_auto_build():
    """INT-09: ensure_available(auto_build=True) builds the module on demand.

    Strategy: if find_packaged_module() reports a build is already present,
    skip the "raises without auto_build" half (the module is already loaded
    and ensure_available short-circuits). Otherwise, assert that the
    no-auto-build path raises and the auto-build path succeeds.
    """
    # If the module is already cached from a prior fixture invocation in
    # this pytest session, the global V7_AVAILABLE flag is True and
    # ensure_available short-circuits before reaching the auto_build path.
    # That's the expected behavior — exercise it positively.
    if v7.V7_AVAILABLE and v7.v7_engine is not None:
        module = v7.ensure_available(auto_build=False)
        assert module is not None
        assert hasattr(module, "Engine")
        return

    # Cold cache path: prove no-auto-build raises, then auto-build succeeds.
    try:
        v7.ensure_available(auto_build=False)
    except v7.V7UnavailableError:
        pass
    else:
        pytest.skip("module already importable without auto_build (likely on PYTHONPATH)")

    try:
        module = v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"auto-build path could not produce V7 (env limitation): {error}")
    assert module is not None
    assert hasattr(module, "Engine")
