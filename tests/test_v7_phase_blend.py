"""V7 phase blend monotonicity test — Plan 03-04 implementation.

ENDG-04: 0..256 continuous phase blend monotonicity.
Plan 03-04 replaces the old `(mg * phase + eg * (24 - phase)) / 24`
formula with the Stockfish-style 0..256 form and verifies three invariants
from the Behavior block:
  1. phase at startpos == 256 (full midgame; max non_pawn_material)
  2. phase at bare-kings == 0 (full endgame; npm == 0 <= endgame_limit)
  3. phase decreases monotonically as pieces are serially captured

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

# Bare-kings FEN: only kings remain. npm == 0 → phase must clamp to 0.
BARE_KINGS_FEN = "8/4k3/8/8/8/8/4K3/8 w - - 0 1"

# FEN sequence with decreasing non-pawn material (plan Behavior block).
# Each position removes one pair of symmetric pieces relative to the previous,
# so npm strictly decreases at each step.
#
# Full material: 2Q + 4R + 4B + 4N per side → all non-pawn pieces present
# (startpos npm = 2*900 + 4*500 + 4*330 + 4*320 = 1800+2000+1320+1280 = 6400
#  which is > midgame_limit=6196 → clamped to 6196 → phase=256)
#
# Step 1: remove both queens (2×900 = 1800 less) → npm drops significantly
# FEN: startpos minus both queens (d1 and d8 empty).
STEP1_NO_QUEENS = (
    "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1"
)
# Step 2: additionally remove one pair of rooks (a-file rooks) → npm lower
STEP2_NO_QUEENS_LESS_ROOKS = (
    "1nb1kbn1/pppppppp/8/8/8/8/PPPPPPPP/1NB1KBN1 w - - 0 1"
)
# Step 3: additionally remove one pair of bishops → npm lower still
STEP3_FEW_PIECES = (
    "1n2k1n1/pppppppp/8/8/8/8/PPPPPPPP/1N2K1N1 w - - 0 1"
)
# Step 4: only kings + pawns (no non-pawn material at all) → npm == 0 → phase == 0
STEP4_KINGS_PAWNS = (
    "4k3/pppppppp/8/8/8/8/PPPPPPPP/4K3 w - - 0 1"
)


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails."""
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")


# =============================================================================
# Test 1: startpos phase == 256
# =============================================================================

def test_phase_at_startpos_is_256(v7_native_engine):
    """ENDG-04: compute_phase(startpos) == 256 (full midgame).

    Behavior block assertion:
    "compute_phase(STARTPOS_FEN) == 256"

    startpos npm = 2*Q + 4*R + 4*B + 4*N (both sides) which exceeds
    midgame_limit (6196). The clamp binds npm to midgame_limit, giving
    phase = (midgame_limit - endgame_limit) * 256 / (midgame_limit - endgame_limit) = 256.
    """
    module = v7_native_engine
    if not hasattr(module, "compute_phase"):
        pytest.skip("compute_phase() binding not available")

    phase = module.compute_phase(STARTPOS_FEN)
    assert isinstance(phase, int), "compute_phase() must return int"
    assert phase == 256, (
        f"Startpos phase should be 256 (full midgame) but got {phase}. "
        f"Check clamp(npm, endgame_limit, midgame_limit) logic."
    )


# =============================================================================
# Test 2: bare-kings phase == 0
# =============================================================================

def test_phase_at_bare_kings_is_0(v7_native_engine):
    """ENDG-04: compute_phase(bare_kings) == 0 (full endgame).

    Behavior block assertion:
    "compute_phase('8/4k3/8/8/8/8/4K3/8 w - - 0 1') == 0"

    No non-pawn material → npm == 0 ≤ endgame_limit (0). Clamp binds to 0.
    phase = (0 - 0) * 256 / (6196 - 0) = 0.
    """
    module = v7_native_engine
    if not hasattr(module, "compute_phase"):
        pytest.skip("compute_phase() binding not available")

    phase = module.compute_phase(BARE_KINGS_FEN)
    assert isinstance(phase, int), "compute_phase() must return int"
    assert phase == 0, (
        f"Bare-kings phase should be 0 (full endgame) but got {phase}. "
        f"Check std::clamp with endgame_limit lower bound."
    )


# =============================================================================
# Test 3: phase decreases monotonically across captures
# =============================================================================

def test_monotonic_phase_across_captures(v7_native_engine):
    """ENDG-04: phase decreases monotonically as non-pawn material is removed.

    Behavior block assertion (plan 03-04 Task 2):
    "For the serial-capture FEN sequence, compute_phase() is non-increasing
     at each step."

    Verifies that the Stockfish-style
        npm = clamp(npm_raw, endgame_limit, midgame_limit)
        phase = (npm - endgame_limit) * 256 / (midgame_limit - endgame_limit)
    formula produces a strictly non-increasing phase as material is stripped.

    If phase is not monotone (e.g., due to endgame_limit / midgame_limit
    misconfiguration or integer overflow), the tapered-eval blend can
    produce score discontinuities — RESEARCH.md Pitfall 6.
    """
    module = v7_native_engine
    if not hasattr(module, "compute_phase"):
        pytest.skip("compute_phase() binding not available")

    fens = [
        STARTPOS_FEN,         # npm >= midgame_limit → phase = 256
        STEP1_NO_QUEENS,      # npm significantly lower
        STEP2_NO_QUEENS_LESS_ROOKS,
        STEP3_FEW_PIECES,
        STEP4_KINGS_PAWNS,    # npm == 0 → phase = 0
    ]

    phases = [module.compute_phase(fen) for fen in fens]

    # Verify all phases are valid integers in [0, 256]
    for i, p in enumerate(phases):
        assert isinstance(p, int), f"compute_phase() must return int (step {i})"
        assert 0 <= p <= 256, (
            f"Phase out of range at step {i}: {p}. "
            f"Expected [0, 256]. FEN: {fens[i]}"
        )

    # Verify monotone non-increasing
    for i in range(len(phases) - 1):
        assert phases[i] >= phases[i + 1], (
            f"Phase not monotonically non-increasing at step {i} → {i+1}: "
            f"{phases[i]} < {phases[i+1]}. "
            f"FEN[{i}]: {fens[i]}\n"
            f"FEN[{i+1}]: {fens[i+1]}\n"
            f"Full sequence: {phases}"
        )

    # Boundary checks
    assert phases[0] == 256, (
        f"First step (startpos) should have phase=256 but got {phases[0]}"
    )
    assert phases[-1] == 0, (
        f"Last step (kings+pawns only) should have phase=0 but got {phases[-1]}"
    )
