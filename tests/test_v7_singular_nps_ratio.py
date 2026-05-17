"""V7 singular extensions NPS ratio sentinel — Plan 03-03 implementation.

SRCH-08 / Success Criterion #4: singular extensions NPS budget.

This test verifies that enabling singular extensions does not cause a search
explosion (RESEARCH.md Pitfall 2). The NPS ratio between UseSingular=true and
UseSingular=false must remain in [0.9, 1.1] — within 10% either direction.

This test is benchmark-gated: set RUN_BENCHMARKS=1 to execute.
Measurement requires a quiet, single-threaded host.

References:
  RESEARCH.md Pitfall 5 (search-explosion check — NPS must stay within 10%
    of no-singular baseline to avoid blowing the NPS budget on deep re-searches)
  Success Criterion #4: singular-on vs singular-off NPS ratio in [0.9, 1.1]
  D-06 (UseSingular UCI toggle)
"""

from __future__ import annotations

import os
import subprocess
import re
import sys
from pathlib import Path

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Bench depth for NPS ratio test (must be >= 10 for singular to fire meaningfully).
BENCH_DEPTH = 12


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails."""
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")


def _bench_nps_via_engine(engine, use_singular: bool, depth: int) -> int:
    """Run a fixed-depth search and return the NPS (nodes / second).

    Uses the pybind11 Engine directly (not the UCI subprocess), which is
    more reliable on Windows where subprocess + UCI pipe may be unavailable.
    Returns NPS = nodes / (time_ms / 1000). Returns 0 if time_ms == 0.
    """
    engine.new_game()
    engine.set_option("UseSingular", "true" if use_singular else "false")
    # Large time_ms so depth is the binding constraint.
    result = engine.search(STARTPOS_FEN, depth=depth, time_ms=1_000_000_000)
    engine.set_option("UseSingular", "true")  # restore default
    if result.time_ms <= 0:
        return result.nps
    return int(result.nodes * 1000 / result.time_ms)


@pytest.mark.benchmark
@pytest.mark.skipif(
    os.environ.get("RUN_BENCHMARKS") != "1",
    reason=(
        "NPS sentinel is a benchmark; set RUN_BENCHMARKS=1 to execute it. "
        "Default pytest invocations skip it because measurement requires a "
        "quiet, single-threaded host (background load skews NPS comparisons "
        "against the ~10% floor). "
    ),
)
def test_singular_nps_ratio_within_10_percent(v7_native_engine):
    """SRCH-08 / Success Criterion #4: singular-on vs singular-off NPS in [0.9, 1.1].

    Runs two fixed-depth bench searches: one with UseSingular=true, one with
    UseSingular=false. Computes NPS ratio = singular_nps / no_singular_nps.
    Asserts ratio in [0.9, 1.1].

    RESEARCH.md Pitfall 5: singular extensions trigger re-searches at depth-1
    for every position matching the gate (TT beta bound, depth >= 8). If the
    re-search depth is miscalculated, NPS can drop 30-50% — well outside the
    10% budget. This test catches the explosion early.

    Success Criterion #4: this test is mandatory evidence before shipping.
    It is run on the build host (not Windows dev host) as part of the
    tier-2 mini-gauntlet checkpoint (Task 3 / D-05).
    """
    engine = v7_native_engine

    nps_off = _bench_nps_via_engine(engine, use_singular=False, depth=BENCH_DEPTH)
    nps_on  = _bench_nps_via_engine(engine, use_singular=True,  depth=BENCH_DEPTH)

    assert nps_off > 0, (
        f"UseSingular=false: NPS is 0 — search produced no nodes at depth {BENCH_DEPTH}"
    )
    assert nps_on > 0, (
        f"UseSingular=true: NPS is 0 — search produced no nodes at depth {BENCH_DEPTH}"
    )

    ratio = nps_on / nps_off
    assert 0.90 <= ratio <= 1.10, (
        f"Singular extensions changed NPS by {abs(ratio - 1.0):.2%} (> 10% limit).\n"
        f"  NPS(UseSingular=true):  {nps_on:,}\n"
        f"  NPS(UseSingular=false): {nps_off:,}\n"
        f"  Ratio: {ratio:.4f} (must be in [0.90, 1.10])\n"
        f"RESEARCH.md Pitfall 2: check depth gate (>=8), singular margin (2*depth), "
        f"and TT condition (flag==TT_BETA && depth>=depth_now-3)."
    )
