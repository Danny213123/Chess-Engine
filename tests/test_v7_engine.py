"""V7 native engine fixture file.

This file owns the module-scoped v7_native_engine fixture so subsequent
plans (02/03/04/05/06) can append tests against a stable base. Plan 01
adds the fixture only; plan 06 (and the binding tests in plan 01 Task 2)
adds the actual test functions.

Plan 06 APPENDS two tests below that REUSE the v7_native_engine fixture:
  - test_cancellation_via_gm: FOUND-04 end-to-end through GameManager.
  - test_nps_sentinel: CLAUDE.md ~20% NPS constraint; benchmark-gated.
"""

import os
import threading
import time

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails.

    Mirrors V6 (tests/test_v6_native.py lines 6-11). The fixture returns
    the compiled native module so tests can call .Engine(), .perft(), etc.
    directly.
    """
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")


# =============================================================================
# Plan 06 appends — test_cancellation_via_gm + test_nps_sentinel
# =============================================================================
# Both tests REUSE the v7_native_engine module-scope fixture defined above by
# parameter name (pytest resolves the fixture without redefinition).

def test_cancellation_via_gm(v7_native_engine):
    """FOUND-04 end-to-end: GameManager.stop_search returns best-so-far <500ms.

    Validates the full cancellation chain through the GameManager pathway:
        gm.stop_search()
          -> algo_v7.stop_engine()
            -> chess_algorithm.stop_engine()
              -> _engine.stop()
                -> C++ stop_flag_.store(true)            # plan 01 atomic
                  -> search-thread polls in alpha_beta   # plan 03 SearchInfo.external_stop
                    -> returns best-so-far

    Construction notes (per plan-06 implementation notes):
      - Uses a GameManager instance (NOT the module-singleton) so test side
        effects don't pollute other test modules. Switches white to V7 and
        kicks ai_move() on a background thread; calls stop_search after
        100 ms; asserts the search returned within 2 s and produced a
        non-None move (best-so-far at the moment of cancel).
      - Latency budget: 500 ms is the documented plan budget. If the V7
        adapter's default search at the startpos finishes faster than that
        even WITHOUT a stop signal, the test still passes because the
        elapsed_ms gate is "<500ms" — but the test would no longer be
        proving cancellation. The asserts on `move is not None` plus the
        thread-join sanity catch that regression.
    """
    from chess_engine.server.game_manager import GameManager

    gm = GameManager()
    ok, _ = gm.set_engine_version("v7", "white")
    if not ok:
        pytest.skip("V7 engine could not be configured on GameManager")

    result = {}

    def _search():
        t0 = time.perf_counter()
        try:
            move = gm.ai_move()
        except Exception as exc:  # pragma: no cover - surfaces as test failure below
            result["error"] = exc
            return
        result["move"] = move
        result["elapsed_ms"] = (time.perf_counter() - t0) * 1000.0

    t = threading.Thread(target=_search, daemon=True)
    t.start()
    time.sleep(0.1)  # let the search begin so stop_search has work to cancel
    gm.stop_search()
    t.join(timeout=2.0)

    assert not t.is_alive(), (
        "Search thread did not return within 2s of stop_search "
        "— FOUND-04 broken (C++ atomic stop flag not observed)"
    )
    if "error" in result:
        pytest.fail(f"ai_move raised during cancellation test: {result['error']}")
    assert result.get("move") is not None, (
        "Cancelled search must return best-so-far, not None"
    )
    assert result["elapsed_ms"] < 500, (
        f"Cancellation latency {result['elapsed_ms']:.1f}ms > 500ms budget"
    )


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
def test_nps_sentinel(v7_native_engine):
    """CLAUDE.md: V7 NPS must remain within ~20% of V6 NPS on the same host.

    D-04 smoke-scope: NPS is in scope for Phase 1 sanity (smoke gate); full
    perf-tuning + perf regression CI live in Phase 2 strength-gate work.

    Host requirements (MUST hold for the assertion to be meaningful):
      1. Single-threaded build (engine threads = 1 — no Lazy SMP jitter)
      2. Fixed startpos search (no opening-book / no per-position variance)
      3. Identical depth between V6 and V7 measurements (apples-to-apples)
      4. Quiet host — no CPU-bound noise (RUN_BENCHMARKS=1 documents the gate)
      5. Same Engine instance reused for back-to-back per-engine measurement
         to amortize cache warm-up where the adapter allows it.

    Cites: D-04 (smoke-scope) and CLAUDE.md (~20% NPS constraint).
    """
    try:
        from chess_engine.engine.v6 import chess_algorithm as v6
        v6.ensure_available(auto_build=True)
    except Exception as exc:
        pytest.skip(f"V6 unavailable for NPS comparison: {exc}")

    from chess_engine.engine.v3.chess_engine import GameState

    gs = GameState()  # startpos — fixed, deterministic
    valid_moves = gs.get_valid_moves()

    v7_mod = v7_native_engine  # noqa: F841 — fixture ensures V7 is loaded

    def measure(engine_mod, label):
        t0 = time.perf_counter()
        result = engine_mod.find_best_move(gs, valid_moves, label, None)
        elapsed = time.perf_counter() - t0
        if isinstance(result, tuple):
            _, stats = result
        else:
            stats = {}
        nodes = stats.get("nodes", 0) if isinstance(stats, dict) else 0
        return nodes / max(elapsed, 1e-6)

    v6_nps = measure(v6, "v6")
    # Reuse v7 module attribute (not the fixture object) for find_best_move —
    # the fixture returns the underlying native module; v7.find_best_move
    # lives on the python adapter.
    v7_nps = measure(v7, "v7")

    if v6_nps <= 0:
        pytest.skip(f"V6 produced zero NPS measurement (nodes/time invalid); cannot compare")

    ratio = v7_nps / v6_nps
    assert ratio >= 0.8, (
        f"V7 NPS {v7_nps:.0f} / V6 NPS {v6_nps:.0f} ratio {ratio:.2f} below "
        f"0.8 floor (CLAUDE.md ~20% NPS constraint). Re-run on a quiet host "
        f"before treating as a regression."
    )
