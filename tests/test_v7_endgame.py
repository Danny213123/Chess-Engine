"""V7 endgame evaluation tests — Wave 0 stub.

ENDG-02/03/05: opposition, wrong-bishop+rook-pawn draw, fortress detection.
Plan 03-04 implements endgame.cpp with KPK probe, opposition rules,
wrong-bishop draw recognition, and fortress hints (default OFF per D-11).

References: D-11 (UseFortressEval defaults OFF; separate validation gauntlet
inside Plan 03-04 decides ship-default), D-12 (new endgame coefficients in
coeffs.json flow through gen_coeffs.py pipeline).
"""

from __future__ import annotations

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# King opposition: white king on e4, black king on e6 (direct opposition,
# white to move — white LOSES the opposition). Test with both sides to move.
OPPOSITION_FEN_WHITE = "8/8/4k3/8/4K3/8/8/8 w - - 0 1"
OPPOSITION_FEN_BLACK = "8/8/4k3/8/4K3/8/8/8 b - - 0 1"

# Wrong-bishop + rook-pawn: classic draw. White has h-pawn and dark-square bishop.
# Black king heads for h8 corner; the bishop cannot control h8.
WRONG_BISHOP_FEN = "8/8/8/8/8/7B/7P/7K w - - 0 1"

# Fortress-like position: defended king, locked pawn chain, no progress.
# UseFortressEval must be OFF (D-11) by default — test that eval doesn't fire.
FORTRESS_FEN = "8/8/8/3k4/3p4/3P4/3K4/8 w - - 0 1"


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
def test_opposition_white_to_move(v7_native_engine):
    """ENDG-02: opposition penalty applied when white king faces opposition.

    In OPPOSITION_FEN_WHITE (white to move, kings in direct opposition),
    the endgame eval should penalize white's position relative to
    OPPOSITION_FEN_BLACK (black to move — white has the opposition and
    should score higher). Verifies the opposition bonus/penalty in endgame.cpp.
    """
    pass


@pytest.mark.skip(reason="Plan 03-04 will implement; this is a Wave 0 stub")
def test_wrong_bishop_rook_pawn_draw(v7_native_engine):
    """ENDG-03: wrong-bishop + rook-pawn recognized as drawable.

    WRONG_BISHOP_FEN has a h-pawn + dark-square bishop — black king will
    reach h8 regardless. The endgame evaluator should return a score near
    DRAW_SCORE (within some tolerance) rather than a winning advantage for
    white. Verifies the wrong-bishop draw rule in endgame.cpp.
    """
    pass


@pytest.mark.skip(reason="Plan 03-04 will implement; this is a Wave 0 stub")
def test_fortress_detection(v7_native_engine):
    """ENDG-05: fortress detection is default OFF per D-11.

    With UseFortressEval=false (the D-11 default), the fortress scoring
    path in endgame.cpp should not fire. The test verifies:
    1. Score with UseFortressEval=false equals score without fortress (baseline).
    2. Score with UseFortressEval=true differs (fortress eval fires when enabled).
    Both assertions require Plan 03-04 to implement the framework.
    """
    pass
