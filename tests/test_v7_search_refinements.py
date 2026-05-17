"""V7 search refinements boundary tests — Wave 0 stub.

SRCH-03/05/09/11/12: null-move, RFP, LMP, multi-cut, IIR, extensions.
Plans 03-02 (Tier-1) and 03-03 (Tier-2) implement and un-skip these tests.

References: D-04 (Tier-1 = Plan 03-02, Tier-2 = Plan 03-03),
D-06 (UCI toggles UseNullMove/UseRFP/UseLMP/UseMultiCut/UseIIR/UseCheckExt/UseRecaptureExt).
"""

from __future__ import annotations

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# KP endgame with no non-pawn material for side to move — zugzwang guard test
KP_ENDGAME_FEN = "8/8/8/8/8/1K6/2P5/4k3 w - - 0 1"


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails."""
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")


@pytest.mark.skip(reason="Plan 03-02 will implement; this is a Wave 0 stub")
def test_null_move_skipped_in_kp_endgame(v7_native_engine):
    """SRCH-03: null move must be skipped when non_pawn_material == 0.

    In a King+Pawn vs King endgame, the side to move has no non-pawn material.
    Applying null move in this position risks missing zugzwang — the position
    where passing is forced but the current eval shows beta-cutoff potential.
    After SRCH-03 lands, UseNullMove=true still skips null move in this case
    (zugzwang guard per RESEARCH.md Pitfall 4).
    """
    pass


@pytest.mark.skip(reason="Plan 03-02 will implement; this is a Wave 0 stub")
def test_rfp_prunes_above_margin(v7_native_engine):
    """SRCH-05: Reverse Futility Pruning cuts off at static_eval - margin >= beta.

    At shallow depth (depth <= 5), RFP should prune branches where the
    static evaluation already exceeds beta by the depth-indexed margin
    (RFP_MARGIN[depth]). Verified by comparing node count with UseRFP=true
    vs UseRFP=false (fewer nodes with RFP active at equal depth).
    """
    pass


@pytest.mark.skip(reason="Plan 03-02 will implement; this is a Wave 0 stub")
def test_lmp_late_move_pruning(v7_native_engine):
    """SRCH-05: Late Move Pruning skips late quiet moves at shallow depth.

    At depth <= LMP_DEPTH, moves beyond the (4 + depth*depth)th move
    should be pruned. Verified by node count: UseLMP=true produces fewer
    nodes than UseLMP=false at the same depth on a non-tactical position.
    """
    pass


@pytest.mark.skip(reason="Plan 03-03 will implement; this is a Wave 0 stub")
def test_multicut_threshold(v7_native_engine):
    """SRCH-09: multi-cut prunes when C of M first moves cause beta-cutoff.

    Multi-cut fires at depth >= 8 when at least C (e.g., 3) of the first
    M (e.g., 6) moves cause a null-window beta-cutoff. The remaining moves
    are pruned as probably failing high. Verified by comparing behavior
    with UseMultiCut=true vs false on a forced-mate position where multiple
    moves all exceed beta.
    """
    pass


@pytest.mark.skip(reason="Plan 03-02 will implement; this is a Wave 0 stub")
def test_iir_reduces_no_tt_move(v7_native_engine):
    """SRCH-11: Internal Iterative Reduction fires when TT move is absent.

    IIR reduces depth by 1 when there is no TT move and depth >= threshold.
    Verified by running a fresh Engine (cold TT) at depth N and checking
    that NPS improves relative to a non-IIR engine searching the same depth.
    """
    pass


@pytest.mark.skip(reason="Plan 03-02 will implement; this is a Wave 0 stub")
def test_recapture_extension(v7_native_engine):
    """SRCH-12: recapture extension fires on recaptures to the same square.

    When the current move recaptures on the same square as the previous move,
    depth should be extended by 1. Verified by checking search depth reaches
    deeper on a tactical position where the recapture line is the main line.
    """
    pass
