"""V7 Lazy SMP sentinel tests — PAR-04/05/06/07/08 (Plan 04-01).

Wave 0 scaffolding: tests are EXPECTED TO FAIL until Task 2 lands the
ThreadPool + Worker struct + depth-stagger + Threads UCI option.

Test plan:
  1. test_pool_resizes_to_n         — PAR-04: set_option("Threads", "4") => 3 helpers
  2. test_threads_clamps_to_range   — PAR-04: 0/999/non-int => unchanged + info string
  3. test_worker_state_isolation    — PAR-04/05: 4t and 1t return legal move; no crash
  4. test_depth_stagger_table       — PAR-06: helpers diverge in depth from main
  5. test_nps_scales_3x_4t_vs_1t   — PAR-07: RUN_BENCHMARKS=1 sentinel
  6. test_cancellation_under_4_threads_under_50ms — PAR-08: RUN_BENCHMARKS=1 sentinel
  7. test_existing_single_thread_tests_green — sanity: Threads=1 behavior bit-identical

References: PAR-04, PAR-05, PAR-06, PAR-07, PAR-08 (REQUIREMENTS.md Phase 4);
CONTEXT D-01/D-02/D-03/D-04/D-05/D-16 (04-CONTEXT.md);
PATTERNS Shared Pattern 1 (RUN_BENCHMARKS gate), Shared Pattern 2 (v7_native_engine).
"""

from __future__ import annotations

import os
import threading
import time

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


# =============================================================================
# STARTPOS and STRESS FEN constants
# =============================================================================

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# A tactically dense position that keeps the search busy without being trivially
# forced (used for PAR-08 cancellation latency measurement with Threads=4).
STRESS_FEN = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"


# =============================================================================
# Shared Pattern 2 (CANONICAL) — module-scoped V7 native-engine fixture
# Source: tests/test_v7_tt_lockless.py:34-50 (verbatim copy target)
# =============================================================================

@pytest.fixture(scope="module")
def v7_native_engine():
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")


@pytest.fixture()
def engine(v7_native_engine):
    eng = v7_native_engine.Engine()
    eng.tt_clear()
    return eng


# =============================================================================
# Test 1 — PAR-04: ThreadPool resizes when Threads option is set
# =============================================================================

def test_pool_resizes_to_n(engine):
    """PAR-04: after set_option("Threads", "4") the engine reports Threads=4.

    Wave 0: thread_count() accessor does not yet exist on Engine —
    this test will ERROR or FAIL until Task 2 adds it.
    """
    engine.set_option("Threads", "4")
    assert engine.thread_count() == 4, (
        "thread_count() must equal 4 after set_option(Threads, 4)"
    )
    engine.set_option("Threads", "1")
    assert engine.thread_count() == 1, (
        "thread_count() must return 1 after set_option(Threads, 1)"
    )


# =============================================================================
# Test 2 — PAR-04: Threads option clamps to [1, 256] and warns on bad values
# =============================================================================

def test_threads_clamps_to_range(engine, capsys):
    """PAR-04 / T-04-01: invalid Threads values are rejected with info string.

    Wave 0: set_option accepts Threads but pool_.resize does not exist —
    test will FAIL until Task 2 implements the dispatcher + pool.
    """
    engine.set_option("Threads", "4")  # set a known baseline
    assert engine.thread_count() == 4

    # Threads=0 must be rejected — below minimum [1, 256]
    engine.set_option("Threads", "0")
    out = capsys.readouterr().out
    assert engine.thread_count() == 4, "out-of-range 0 must leave Threads unchanged"
    assert "info string" in out, "rejection must emit an info string"

    # Threads=999 must be rejected — above maximum [1, 256]
    engine.set_option("Threads", "999")
    out = capsys.readouterr().out
    assert engine.thread_count() == 4, "out-of-range 999 must leave Threads unchanged"
    assert "info string" in out, "rejection must emit an info string"

    # Non-integer must be rejected
    engine.set_option("Threads", "not-an-int")
    out = capsys.readouterr().out
    assert engine.thread_count() == 4, "non-integer must leave Threads unchanged"
    assert "info string" in out, "non-integer rejection must emit an info string"

    # Reset to 1 for subsequent tests
    engine.set_option("Threads", "1")


# =============================================================================
# Test 3 — PAR-04/05: Worker state isolation — 4t and 1t both return legal move
# =============================================================================

def test_worker_state_isolation(v7_native_engine):
    """PAR-04/05: search at Threads=4 and Threads=1 both return a legal best_move.

    Wave 0: Engine::search doesn't drive a pool yet — 4t will behave like 1t
    or fail to compile with the pool API. Fail/error is correct for Wave 0.
    """
    eng1 = v7_native_engine.Engine()
    eng1.set_option("Threads", "1")
    r1 = eng1.search(STARTPOS, depth=4, time_ms=1000)
    assert r1.best_move != 0, "Threads=1 must return a legal move (non-zero)"
    nodes_1 = r1.nodes

    eng4 = v7_native_engine.Engine()
    eng4.set_option("Threads", "4")
    r4 = eng4.search(STARTPOS, depth=4, time_ms=1000)
    assert r4.best_move != 0, "Threads=4 must return a legal move (non-zero)"
    nodes_4 = r4.nodes

    # Node count must be monotone-increasing (not zero and not negative)
    assert nodes_1 > 0, "Threads=1 search must visit at least 1 node"
    assert nodes_4 > 0, "Threads=4 search must visit at least 1 node"


# =============================================================================
# Test 4 — PAR-06: Depth-stagger causes helper divergence
# =============================================================================

def test_depth_stagger_table(v7_native_engine):
    """PAR-06: helpers skip certain iteration depths (Berserk-style stagger).

    Proxy: run a 5-second search at Threads=4 and verify that the reported
    depth (main thread's final iteration depth) is not pathologically 1 —
    i.e. the stagger didn't prevent ALL helpers from making progress.

    A full per-worker-depth check requires a debug API not present in Wave 0.
    This test is a structural smoke: if depth-stagger is misconfigured the
    search typically finishes at depth 1 or returns immediately.

    Wave 0: this test may PASS vacuously if Threads=4 falls back to Threads=1
    behavior; it becomes meaningful after Task 2 wires the pool.
    """
    eng = v7_native_engine.Engine()
    eng.set_option("Threads", "4")
    r = eng.search(STARTPOS, depth=8, time_ms=2000)
    # Must finish at depth >= 1 with a legal move; depth stagger must not halt all helpers
    assert r.depth >= 1, f"Depth-stagger blocked all search progress; depth={r.depth}"
    assert r.best_move != 0, "Search must return a legal move"


# =============================================================================
# Test 5 — PAR-07: NPS scaling >= 3.0x (4t / 1t) — RUN_BENCHMARKS=1 gated
# =============================================================================

@pytest.mark.benchmark
@pytest.mark.skipif(
    os.environ.get("RUN_BENCHMARKS") != "1",
    reason=(
        "NPS sentinel is a benchmark; set RUN_BENCHMARKS=1 to execute it. "
        "Default pytest invocations skip it because measurement requires a "
        "quiet, single-threaded host (background load skews NPS comparisons "
        "against the ~20% floor)."
    ),
)
def test_nps_scales_3x_4t_vs_1t(v7_native_engine):
    """PAR-07: 4t NPS must be >= 3.0x 1t NPS on STARTPOS at depth=12/time_ms=5000.

    Build-host gate (Task 3 in 04-01-PLAN.md). RUN_BENCHMARKS=1 required.
    Pass criterion: ratio >= 3.0 (printed).
    """
    def _nps_at(threads: int) -> float:
        eng = v7_native_engine.Engine()
        eng.set_option("Threads", str(threads))
        eng.set_option("Hash", "256")
        r = eng.search(STARTPOS, depth=12, time_ms=5000)
        return float(r.nps)

    nps_1 = _nps_at(1)
    nps_4 = _nps_at(4)
    ratio = nps_4 / nps_1 if nps_1 > 0 else 0.0
    print(f"\nPAR-07: nps_1={nps_1:.0f} nps_4={nps_4:.0f} ratio={ratio:.2f}")
    assert ratio >= 3.0, (
        f"4t/1t NPS ratio {ratio:.2f} < 3.0 threshold "
        f"(nps_1={nps_1:.0f}, nps_4={nps_4:.0f}) — "
        "check GIL release (FOUND-05) and Worker value-typed tables (Pitfall 1)"
    )


# =============================================================================
# Test 6 — PAR-08: Cancellation latency < 50ms with Threads=4 — RUN_BENCHMARKS=1
# =============================================================================

@pytest.mark.benchmark
@pytest.mark.skipif(
    os.environ.get("RUN_BENCHMARKS") != "1",
    reason=(
        "NPS sentinel is a benchmark; set RUN_BENCHMARKS=1 to execute it. "
        "Default pytest invocations skip it because measurement requires a "
        "quiet, single-threaded host (background load skews NPS comparisons "
        "against the ~20% floor)."
    ),
)
def test_cancellation_under_4_threads_under_50ms(v7_native_engine):
    """PAR-08: engine.stop() returns within 50ms wall-clock with Threads=4.

    Build-host gate (Task 3 in 04-01-PLAN.md). RUN_BENCHMARKS=1 required.
    Pass criterion: elapsed_ms < 50.0 (printed).

    Threading pattern: verbatim from tests/test_v7_engine.py:75-105.
    """
    eng = v7_native_engine.Engine()
    eng.set_option("Threads", "4")
    eng.set_option("Hash", "256")

    result_holder: dict = {}

    def search_thread():
        result_holder["r"] = eng.search(STRESS_FEN, depth=30, time_ms=30_000)

    t = threading.Thread(target=search_thread, daemon=True)
    t.start()
    time.sleep(0.5)  # let all 4 workers ramp up

    t0 = time.perf_counter_ns()
    eng.stop()
    t.join(timeout=2.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6

    print(f"\nPAR-08: elapsed_ms={elapsed_ms:.1f}")
    assert not t.is_alive(), "search did not return within 2s of stop()"
    assert elapsed_ms < 50.0, (
        f"cancellation took {elapsed_ms:.1f}ms (threshold 50ms) — "
        "check cancellation poll cadence (must be % 1024 per Pitfall 10)"
    )


# =============================================================================
# Test 7 — Sanity: existing single-thread tests stay green
# =============================================================================

def test_existing_single_thread_tests_green(v7_native_engine):
    """Sanity: Threads=1 (default) behavior is bit-identical to pre-04-01.

    Smoke: run a quick search at Threads=1, verify result fields are populated.
    The full regression is handled by running test_v7_engine.py / test_v7_search.py
    alongside this file (those tests don't set Threads, so they use the default=1).
    """
    eng = v7_native_engine.Engine()
    # Threads defaults to 1 — no set_option needed
    r = eng.search(STARTPOS, depth=4, time_ms=500)
    assert r.best_move != 0, "Threads=1 default search must return a legal move"
    assert r.nodes > 0, "Threads=1 default search must visit nodes"
    assert r.depth >= 1, "Threads=1 default search must reach at least depth 1"
    assert r.nps >= 0, "NPS must be non-negative"
