"""V7 LMR depth-at-fixed-time benchmark sentinel — Wave 0 stub.

SRCH-04: LMR with context — depth advantage measurement.
Plan 03-02 implements LMR two-level re-search (RESEARCH.md Pitfall 3)
and un-skips this benchmark.

This test is benchmark-gated: set RUN_BENCHMARKS=1 to execute.
Measurement requires a quiet, single-threaded host (background load skews).

Reference: D-06 (UseLMR UCI toggle), RESEARCH.md Pitfall 3 (two-level re-search).
"""

from __future__ import annotations

import os

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
        "Plan 03-02 will implement the actual assertion."
    ),
)
@pytest.mark.skip(reason="Plan 03-02 will implement; this is a Wave 0 stub")
def test_lmr_depth_advantage(v7_native_engine):
    """SRCH-04: LMR-on reaches higher depth than LMR-off at fixed time budget.

    Runs two searches at identical time_ms: one with UseLMR=true and one
    with UseLMR=false. The LMR-on search must reach a strictly higher
    completed depth — verifying that LMR's node-count reduction translates
    to measurable depth gain within the same wall-clock budget.

    Success Criterion #3 (SRCH-04): LMR-on depth > LMR-off depth at equal time.
    """
    pass
