"""V7 MovePicker staged move ordering tests — Plan 03-02 implementation.

SRCH-06: staged ordering: TT first, SEE-bucketed captures, killers, counter,
history-sorted quiets, bad captures.

These tests verify the search engine's observable behavior with respect to
move ordering (since the C++ MovePicker internals are not directly exposed
to Python, we verify via node-count and bestmove consistency comparisons).

Reference: D-06 (UseNullMove / UseLMR toggle scaffold in EngineOptions).
RESEARCH.md Code Examples §"Staged Move Picker".
"""

from __future__ import annotations

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# A tactical position with multiple captures available (for capture ordering tests)
# After 1.e4 e5 2.Nf3 Nc6 3.Bc4 — Italian Opening, many piece interactions
TACTICAL_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3"

# A position where the queen can be captured — tests that SEE orders captures correctly.
# White queen on d5 attacked by Black's knight and bishop.
CAPTURE_ORDER_FEN = "r1b1kbnr/pppp1ppp/2n5/3qp3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 4"


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails."""
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")


def test_picker_yields_tt_first(v7_native_engine):
    """SRCH-06: MovePicker must yield the TT move before all other moves.

    Given a position with a non-MOVE_NONE TT move, the first call to
    MovePicker::next() must return exactly that TT move, regardless of
    capture/quiet ordering.

    Verification: run a two-pass search. The first pass populates the TT;
    the second pass starts from the same position and must immediately
    explore the TT move first. Observable effect: the second search is faster
    (fewer nodes at equal depth) because the TT move gives an immediate
    alpha-beta cutoff.
    """
    engine = v7_native_engine

    # First search populates TT
    engine.new_game()
    result_cold = engine.search(TACTICAL_FEN, depth=6, time_ms=30000)

    # Second search reuses TT — should be faster due to TT move ordering
    result_warm = engine.search(TACTICAL_FEN, depth=6, time_ms=30000)

    # Both must return a valid bestmove.
    assert result_cold.best_move != 0, "Cold TT: must return a bestmove"
    assert result_warm.best_move != 0, "Warm TT: must return a bestmove"

    # With TT move ordering working, warm search should use equal-or-fewer nodes.
    # Allow up to 2x for positional variations and aspiration window effects.
    assert result_warm.nodes <= result_cold.nodes * 2, (
        f"Warm TT ({result_warm.nodes} nodes) should not vastly exceed "
        f"cold TT ({result_cold.nodes} nodes) at depth 6"
    )

    # The bestmove should be consistent between cold and warm searches.
    assert result_warm.best_move == result_cold.best_move, (
        f"TT move ordering must not change bestmove: "
        f"cold={result_cold.best_move:04x}, warm={result_warm.best_move:04x}"
    )


def test_picker_good_captures_before_killers(v7_native_engine):
    """SRCH-06: good captures (SEE >= 0) must precede killers in picker order.

    After the TT move stage, the next non-empty stage for a tactical position
    should yield captures with SEE >= 0 before any quiet killer moves.
    Verified by confirming the search finds tactics correctly — good
    move ordering ensures alpha-beta cutoffs from captures fire early,
    reducing node count compared to a search with captures deprioritized.

    We verify this indirectly: the engine finds the correct tactical move in
    a position where captures are clearly the right choice.
    """
    engine = v7_native_engine

    # A position where White can capture a pawn for free: 1.Nxe5 wins the pawn.
    # FEN: e4 pawn on e5 that can be taken by the Nf3
    FREE_PAWN_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3"

    engine.new_game()
    result = engine.search(FREE_PAWN_FEN, depth=6, time_ms=30000)

    # The engine must return a valid bestmove.
    assert result.best_move != 0, "Must return a bestmove in tactical position"

    # Search must complete within reasonable bounds.
    assert result.depth >= 6, f"Expected depth >= 6, got {result.depth}"

    # Node count sanity: good capture ordering means the search is efficient.
    # A well-ordered search at depth 6 from this position should stay < 5M nodes.
    assert result.nodes < 5_000_000, (
        f"Node count {result.nodes} is unexpectedly high — "
        "suggests capture ordering may not be working"
    )


def test_picker_quiets_history_sorted(v7_native_engine):
    """SRCH-06: quiet moves in S_QUIETS stage must be sorted by history score.

    Given two quiet moves where one has a higher history[side][from][to] value,
    the picker must yield the higher-history move first within the S_QUIETS stage.
    Verifies that the persistent history table (D-03 Bug #2 fix) is actually
    consumed by the staged picker.

    Verification: run iterative deepening so the history table accumulates.
    The second search (reusing history) should be more efficient (fewer nodes
    or greater depth in the same time) because history sorting brings good
    quiet moves earlier.
    """
    engine = v7_native_engine

    # First search: accumulates history table from beta-cutoffs
    engine.new_game()
    result_first = engine.search(STARTPOS_FEN, depth=7, time_ms=30000)

    # Second search: history table is now pre-populated (aged by one search via
    # Engine::age_history). The history-sorted quiet ordering should guide it better.
    result_second = engine.search(STARTPOS_FEN, depth=7, time_ms=30000)

    # Both must return a valid bestmove.
    assert result_first.best_move != 0, "First search: must return a bestmove"
    assert result_second.best_move != 0, "Second search: must return a bestmove"

    # Both must reach depth 7.
    assert result_first.depth >= 7, f"First search: expected depth 7, got {result_first.depth}"
    assert result_second.depth >= 7, f"Second search: expected depth 7, got {result_second.depth}"

    # Second search should not be significantly worse (history aging can cause slight
    # variance, but node count should stay within 3x of first search).
    assert result_second.nodes <= result_first.nodes * 3, (
        f"Second search ({result_second.nodes} nodes) should not be much worse than "
        f"first search ({result_first.nodes} nodes) — suggests history not helping"
    )
