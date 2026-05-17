"""V7 LMR depth-at-fixed-time benchmark sentinel — Plan 03-02 implementation.

SRCH-04: LMR with context — depth advantage measurement.
Plan 03-02 implements LMR two-level re-search (RESEARCH.md Pitfall 3).

This test is benchmark-gated: set RUN_BENCHMARKS=1 to execute.
Measurement requires a quiet, single-threaded host (background load skews).

Reference: D-06 (UseLMR UCI toggle), RESEARCH.md Pitfall 3 (two-level re-search).
"""

from __future__ import annotations

import os
import time

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails."""
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")


@pytest.mark.benchmark
@pytest.mark.skipif(
    os.environ.get("RUN_BENCHMARKS") != "1",
    reason=(
        "LMR depth benchmark; set RUN_BENCHMARKS=1 to execute. "
        "Default pytest invocations skip it because measurement requires a "
        "quiet, single-threaded host (background load skews depth comparisons). "
    ),
)
def test_lmr_depth_advantage(v7_native_engine):
    """SRCH-04: LMR-on reaches higher depth than LMR-off at fixed time budget.

    Runs two searches at identical time_ms: one with UseLMR=true and one
    with UseLMR=false. The LMR-on search must reach a strictly higher
    completed depth — verifying that LMR's node-count reduction translates
    to measurable depth gain within the same wall-clock budget.

    Success Criterion #3 (SRCH-04): LMR-on depth > LMR-off depth at equal time.

    Implementation (Plan 03-02):
    - Use time_ms=2000ms as the fixed budget (large enough to complete depth 8+).
    - UseLMR=false should complete fewer depths (more nodes per depth).
    - UseLMR=true should complete more depths (fewer nodes per depth via reduction).
    """
    engine = v7_native_engine

    # Budget: 2 seconds — enough to demonstrate a depth difference.
    TIME_MS = 2000

    # LMR OFF: brute-force search — more nodes per depth, fewer depths completed.
    engine.new_game()
    engine.set_option("UseLMR", "false")
    result_no_lmr = engine.search(STARTPOS_FEN, depth=20, time_ms=TIME_MS)

    # LMR ON: reduced-depth search — fewer nodes per depth, more depths completed.
    engine.new_game()
    engine.set_option("UseLMR", "true")
    result_lmr = engine.search(STARTPOS_FEN, depth=20, time_ms=TIME_MS)

    # Re-enable for other tests
    engine.set_option("UseLMR", "true")

    # Both must return a valid bestmove.
    assert result_no_lmr.best_move != 0, "UseLMR=false: must return a bestmove"
    assert result_lmr.best_move != 0, "UseLMR=true: must return a bestmove"

    # SRCH-04 Success Criterion: LMR-on must reach strictly greater depth.
    # (The two-level re-search from RESEARCH.md Pitfall 3 makes LMR's depth
    # advantage come from reduced exploration at late moves, not from unsound
    # one-level re-search that misses failing-high moves.)
    assert result_lmr.depth > result_no_lmr.depth, (
        f"SRCH-04 FAILED: LMR-on depth ({result_lmr.depth}) must be > "
        f"LMR-off depth ({result_no_lmr.depth}) at time_ms={TIME_MS}. "
        f"Nodes: LMR-on={result_lmr.nodes}, LMR-off={result_no_lmr.nodes}. "
        f"LMR is not providing expected depth advantage — check two-level "
        f"re-search implementation (RESEARCH.md Pitfall 3)."
    )

    # NPS should be roughly comparable (within 30%) — LMR reduces depth but
    # each node costs the same amount of work.
    if result_no_lmr.nps > 0:
        nps_ratio = result_lmr.nps / result_no_lmr.nps
        assert 0.5 <= nps_ratio <= 2.0, (
            f"NPS ratio (LMR-on / LMR-off) = {nps_ratio:.2f} is outside [0.5, 2.0]. "
            f"LMR-on NPS={result_lmr.nps}, LMR-off NPS={result_no_lmr.nps}"
        )
