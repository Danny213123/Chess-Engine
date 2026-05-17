"""V7 history/counter-move heuristic tests — Wave 0 stub.

SRCH-07: continuation + capture history, counter-move aging.
Plan 03-03 implements continuation history and counter-move indexing and
un-skips these tests.

CAUTION: counter_move is indexed by the side that JUST MOVED (1 - stm),
not the current side to move (stm). Getting this backwards causes counter-move
scores to be applied to the wrong side's quiet moves. See RESEARCH.md Pitfall 7.
"""

from __future__ import annotations

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


@pytest.mark.skip(reason="Plan 03-03 will implement; this is a Wave 0 stub")
def test_history_accumulates_on_beta_cutoff(v7_native_engine):
    """SRCH-07: history[side][from][to] increments on quiet beta-cutoff.

    After a search where a quiet move at (from, to) caused a beta cutoff,
    the history table value for that (side, from, to) triple must be positive.
    Verifies the D-03 Bug #2 fix: history is persistent across alpha_beta
    calls (not reset every call).
    """
    pass


@pytest.mark.skip(reason="Plan 03-03 will implement; this is a Wave 0 stub")
def test_history_aged_on_new_search(v7_native_engine):
    """SRCH-07: history values are halved between search calls (aging).

    After a search populates history[s][f][t] = V, a new Engine::search()
    call must halve all history values before the next iterative_deepening
    (Engine::age_history() per RESEARCH.md A11 and D-03). Verifies that
    old heuristic signal decays without being zeroed completely.
    """
    pass


@pytest.mark.skip(reason="Plan 03-03 will implement; this is a Wave 0 stub")
def test_counter_move_indexed_by_side_that_moved(v7_native_engine):
    """SRCH-07: counter_move indexed by (side_that_moved, from, to) — NOT current STM.

    RESEARCH.md Pitfall 7: a common bug is indexing counter_moves by
    board.side_to_move (the side ABOUT to move) instead of the side that
    just made the move (1 - board.side_to_move). The counter-move heuristic
    responds to the opponent's last move, so the index must be the OPPONENT's
    side and last-move coordinates.

    This test verifies that the counter-move entry at (opponent_side, from, to)
    is populated, not the entry at (our_side, from, to).
    """
    pass
