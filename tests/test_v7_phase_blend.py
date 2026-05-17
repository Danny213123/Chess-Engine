"""V7 phase blend monotonicity test — Wave 0 stub.

ENDG-04: 0..256 continuous phase blend monotonicity.
Plan 03-04 replaces the current `(mg * phase + eg * (24 - phase)) / 24`
formula with the Stockfish-style 0..256 form and un-skips this test.

PITFALL: phase must change monotonically as pieces are captured — each
capture reduces total non_pawn_material, which must reduce phase (toward
endgame). If phase is not monotonic (e.g., due to clamping bugs), the
final score can become non-monotonic in material, leading to search
instability near the blend boundaries.
Reference: RESEARCH.md Pitfall 6.
"""

from __future__ import annotations

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Positions with progressively less material — used to test phase monotonicity.
# Starting from middlegame (many pieces) to endgame (few pieces).
FULL_MATERIAL_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
HALF_MATERIAL_FEN = "r1bqkb1r/pppppppp/8/8/8/8/PPPPPPPP/R1BQKB1R w KQkq - 0 1"
ENDGAME_FEN = "4k3/pppppppp/8/8/8/8/PPPPPPPP/4K3 w - - 0 1"
PURE_ENDGAME_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails."""
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")


@pytest.mark.skip(reason="Plan 03-04 will implement; this is a Wave 0 stub")
def test_monotonic_phase_across_captures(v7_native_engine):
    """ENDG-04: phase value decreases monotonically as material is removed.

    Evaluates a sequence of positions with progressively less non-pawn material.
    The computed phase (accessible via a hypothetical eval_phase() binding or
    inferred from the mg/eg blend ratio) must decrease monotonically from
    midgame_limit to endgame_limit as pieces are removed.

    RESEARCH.md Pitfall 6: the 0..256 formula
        phase = clamp(npm, eg_limit, mg_limit)
        phase = (npm - eg_limit) * 256 / (mg_limit - eg_limit)
    must use std::clamp to prevent out-of-range values that would invert
    the monotonicity when npm < eg_limit (pure king endgames).
    """
    pass
