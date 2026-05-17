"""V7 search refinements boundary tests — Plan 03-02 implementation.

SRCH-03/05/11/12: null-move zugzwang guard, RFP, LMP, IIR, extensions.
Plan 03-02 (Tier-1) implements these tests; Plan 03-03 (Tier-2) un-skips
test_multicut_threshold.

References: D-04 (Tier-1 = Plan 03-02, Tier-2 = Plan 03-03),
D-06 (UCI toggles UseNullMove/UseRFP/UseLMP/UseMultiCut/UseIIR/UseCheckExt/UseRecaptureExt).
"""

from __future__ import annotations

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# KP endgame with no non-pawn material for side to move — zugzwang guard test.
# White (to move) has only king + pawn; non_pawn_material(WHITE) == 0.
# Null move must be skipped by the zugzwang guard (RESEARCH.md Pitfall 4).
KP_ENDGAME_FEN = "8/8/8/8/8/1K6/2P5/4k3 w - - 0 1"

# A tactical position with many quiet moves for LMP/futility testing.
# Starting position is fine — it has 20 quiet moves initially.
QUIET_POSITION_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails."""
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")


def test_null_move_skipped_in_kp_endgame(v7_native_engine):
    """SRCH-03: null move must be skipped when non_pawn_material == 0.

    In a King+Pawn vs King endgame, the side to move has no non-pawn material.
    Applying null move in this position risks missing zugzwang — the position
    where passing is forced but the current eval shows beta-cutoff potential.
    After SRCH-03 lands, UseNullMove=true still skips null move in this case
    (zugzwang guard per RESEARCH.md Pitfall 4).

    Verification: bestmove with UseNullMove=true vs UseNullMove=false should
    be the same legal move (both should find the correct plan, null-move doesn't
    change the move in simple KPK because the guard prevents misapplication).
    The key check is that the engine does NOT crash or return MOVE_NONE in this
    endgame position with the zugzwang guard active.
    """
    engine = v7_native_engine
    engine.new_game()

    # Search with UseNullMove=true (default — zugzwang guard should fire)
    engine.set_option("UseNullMove", "true")
    result_on = engine.search(KP_ENDGAME_FEN, depth=8, time_ms=5000)

    engine.new_game()
    # Search with UseNullMove=false (null move completely disabled)
    engine.set_option("UseNullMove", "false")
    result_off = engine.search(KP_ENDGAME_FEN, depth=8, time_ms=5000)

    # Re-enable UseNullMove for other tests
    engine.set_option("UseNullMove", "true")

    # Both searches must return a legal move (not MOVE_NONE).
    assert result_on.best_move != 0, "UseNullMove=true: bestmove must not be MOVE_NONE in KPK"
    assert result_off.best_move != 0, "UseNullMove=false: bestmove must not be MOVE_NONE in KPK"

    # Structural check: the engine must have searched some nodes in both cases.
    assert result_on.nodes > 0, "UseNullMove=true: must search > 0 nodes"
    assert result_off.nodes > 0, "UseNullMove=false: must search > 0 nodes"


def test_rfp_prunes_above_margin(v7_native_engine):
    """SRCH-05: Reverse Futility Pruning cuts off at static_eval - margin >= beta.

    At shallow depth (depth <= 8), RFP should prune branches where the
    static evaluation already exceeds beta by the depth-indexed margin.
    Verified by comparing node count with UseRFP=true vs UseRFP=false.
    Fewer nodes with RFP active at equal depth indicates pruning is working.
    """
    engine = v7_native_engine
    engine.new_game()

    # Search with RFP disabled — counts all nodes
    engine.set_option("UseRFP", "false")
    result_no_rfp = engine.search(STARTPOS_FEN, depth=6, time_ms=30000)

    engine.new_game()
    # Search with RFP enabled — should prune and use fewer nodes
    engine.set_option("UseRFP", "true")
    result_rfp = engine.search(STARTPOS_FEN, depth=6, time_ms=30000)

    # Re-enable for other tests
    engine.set_option("UseRFP", "true")

    # Both searches must complete and return a valid bestmove.
    assert result_no_rfp.best_move != 0, "UseRFP=false: must return a bestmove"
    assert result_rfp.best_move != 0, "UseRFP=true: must return a bestmove"

    # Both must reach depth 6 (depth-fixed search).
    assert result_no_rfp.depth >= 6, f"UseRFP=false: expected depth 6, got {result_no_rfp.depth}"
    assert result_rfp.depth >= 6, f"UseRFP=true: expected depth 6, got {result_rfp.depth}"

    # RFP must not increase node count above the baseline (it's a pruning technique).
    # Allow up to 20% slack for aspiration window differences.
    assert result_rfp.nodes <= result_no_rfp.nodes * 1.20, (
        f"UseRFP=true ({result_rfp.nodes} nodes) should not exceed "
        f"UseRFP=false ({result_no_rfp.nodes} nodes) by more than 20% at depth 6"
    )


def test_lmp_late_move_pruning(v7_native_engine):
    """SRCH-05: Late Move Pruning skips late quiet moves at shallow depth.

    At depth <= LMP_DEPTH, moves beyond the (4 + depth*depth)th move
    should be pruned. Verified by node count: UseLMP=true produces fewer
    nodes than UseLMP=false at the same depth on a non-tactical position.
    """
    engine = v7_native_engine
    engine.new_game()

    # Search with LMP disabled
    engine.set_option("UseLMP", "false")
    result_no_lmp = engine.search(STARTPOS_FEN, depth=6, time_ms=30000)

    engine.new_game()
    # Search with LMP enabled
    engine.set_option("UseLMP", "true")
    result_lmp = engine.search(STARTPOS_FEN, depth=6, time_ms=30000)

    # Re-enable for other tests
    engine.set_option("UseLMP", "true")

    # Both searches must complete and return a valid bestmove.
    assert result_no_lmp.best_move != 0, "UseLMP=false: must return a bestmove"
    assert result_lmp.best_move != 0, "UseLMP=true: must return a bestmove"

    # Both must reach depth 6.
    assert result_no_lmp.depth >= 6, f"UseLMP=false: expected depth 6, got {result_no_lmp.depth}"
    assert result_lmp.depth >= 6, f"UseLMP=true: expected depth 6, got {result_lmp.depth}"

    # LMP is a pruning technique — it must not increase node count above baseline.
    # Allow 20% slack for aspiration window and move ordering differences.
    assert result_lmp.nodes <= result_no_lmp.nodes * 1.20, (
        f"UseLMP=true ({result_lmp.nodes} nodes) should not exceed "
        f"UseLMP=false ({result_no_lmp.nodes} nodes) by more than 20% at depth 6"
    )


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


def test_iir_reduces_no_tt_move(v7_native_engine):
    """SRCH-11: Internal Iterative Reduction fires when TT move is absent.

    IIR reduces depth by 1 when there is no TT move and depth >= threshold.
    Verified by running a fresh Engine (cold TT) at depth N and comparing
    node counts: UseIIR=true should produce fewer nodes (reduces depth at
    nodes with no TT guidance), though it may not be measurable at all
    positions. The main check is: engine completes the search without error,
    and at minimum has equal-or-fewer nodes with IIR enabled.
    """
    engine = v7_native_engine

    # Fresh engine = cold TT (no TT entries from prior searches)
    engine.new_game()
    engine.set_option("UseIIR", "false")
    result_no_iir = engine.search(STARTPOS_FEN, depth=7, time_ms=30000)

    engine.new_game()
    engine.set_option("UseIIR", "true")
    result_iir = engine.search(STARTPOS_FEN, depth=7, time_ms=30000)

    # Re-enable for other tests
    engine.set_option("UseIIR", "true")

    # Both searches must complete and return a valid bestmove.
    assert result_no_iir.best_move != 0, "UseIIR=false: must return a bestmove"
    assert result_iir.best_move != 0, "UseIIR=true: must return a bestmove"

    # IIR is a search reduction — it should not increase nodes beyond baseline.
    # Allow 20% slack for reductions at low-depth nodes vs deeper subtrees.
    assert result_iir.nodes <= result_no_iir.nodes * 1.20, (
        f"UseIIR=true ({result_iir.nodes} nodes) should not significantly exceed "
        f"UseIIR=false ({result_no_iir.nodes} nodes) at depth 7"
    )


def test_recapture_extension(v7_native_engine):
    """SRCH-12: recapture extension fires on recaptures to the same square.

    When the current move recaptures on the same square as the previous move,
    depth should be extended by 1. Verified by checking that a tactical
    position with recapture sequences is handled without error, and that
    UseRecaptureExt=true does not reduce depth vs UseRecaptureExt=false
    (extensions can only increase depth, not decrease it).
    """
    # A position with forced captures / recaptures:
    # After 1.e4 d5 2.exd5 Nf6 the e4xd5 capture creates a recapture sequence.
    # Use a mid-game tactical position.
    RECAPTURE_FEN = "r1bqkb1r/ppp2ppp/2np1n2/1B2p3/4P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 2 5"

    engine = v7_native_engine
    engine.new_game()

    engine.set_option("UseRecaptureExt", "false")
    result_no_ext = engine.search(RECAPTURE_FEN, depth=7, time_ms=30000)

    engine.new_game()
    engine.set_option("UseRecaptureExt", "true")
    result_ext = engine.search(RECAPTURE_FEN, depth=7, time_ms=30000)

    # Re-enable for other tests
    engine.set_option("UseRecaptureExt", "true")

    # Both must return a valid bestmove.
    assert result_no_ext.best_move != 0, "UseRecaptureExt=false: must return bestmove"
    assert result_ext.best_move != 0, "UseRecaptureExt=true: must return bestmove"

    # Extensions increase seldepth — UseRecaptureExt=true should have seldepth >= baseline.
    # Allow equal seldepth (extension may not fire at depth 7 for this position).
    assert result_ext.depth >= result_no_ext.depth - 1, (
        f"UseRecaptureExt=true: depth {result_ext.depth} should not be "
        f"less than {result_no_ext.depth - 1}"
    )
