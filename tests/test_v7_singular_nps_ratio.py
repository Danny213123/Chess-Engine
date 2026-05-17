"""V7 singular extensions NPS ratio sentinel — Wave 0 stub.

SRCH-08 / Success Criterion #4: singular extensions NPS budget.
Plan 03-03 implements singular extensions and un-skips this benchmark.

This test is benchmark-gated: set RUN_BENCHMARKS=1 to execute.
Measurement requires a quiet, single-threaded host.

References:
  RESEARCH.md Pitfall 5 (search-explosion check — NPS must stay within 10%
    of no-singular baseline to avoid blowing the NPS budget on deep re-searches)
  Success Criterion #4: singular-on vs singular-off NPS ratio ∈ [0.9, 1.1]
  D-06 (UseSingular UCI toggle)
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
        "NPS sentinel is a benchmark; set RUN_BENCHMARKS=1 to execute it. "
        "Default pytest invocations skip it because measurement requires a "
        "quiet, single-threaded host (background load skews NPS comparisons "
        "against the ~10% floor). "
        "Plan 03-03 will implement the actual assertion."
    ),
)
@pytest.mark.skip(reason="Plan 03-03 will implement; this is a Wave 0 stub")
def test_singular_nps_ratio_within_10_percent(v7_native_engine):
    """SRCH-08 / Success Criterion #4: singular-on vs singular-off NPS ∈ [0.9, 1.1].

    Runs two fixed-depth bench searches: one with UseSingular=true, one with
    UseSingular=false. Computes NPS ratio = singular_nps / no_singular_nps.
    Assert ratio ∈ [0.9, 1.1].

    RESEARCH.md Pitfall 5: singular extensions trigger re-searches at depth-1
    for every position matching the gate (TT beta bound, depth >= 8). If the
    re-search depth is miscalculated, NPS can drop 30-50% — well outside the
    10% budget. This test catches the explosion early.
    """
    pass
