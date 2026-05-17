"""V7 MovePicker staged move ordering tests — Wave 0 stub.

SRCH-06: staged ordering: TT first, SEE-bucketed captures, killers, counter,
history-sorted quiets, bad captures.
Plan 03-02 Task 2 fills in the MovePicker body and un-skips these tests.

Reference: D-06 (UseNullMove / UseLMR toggle scaffold in EngineOptions).
RESEARCH.md Code Examples §"Staged Move Picker".
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


@pytest.mark.skip(reason="Plan 03-02 will implement; this is a Wave 0 stub")
def test_picker_yields_tt_first(v7_native_engine):
    """SRCH-06: MovePicker must yield the TT move before all other moves.

    Given a position with a non-MOVE_NONE TT move, the first call to
    MovePicker::next() must return exactly that TT move, regardless of
    capture/quiet ordering.
    """
    pass


@pytest.mark.skip(reason="Plan 03-02 will implement; this is a Wave 0 stub")
def test_picker_good_captures_before_killers(v7_native_engine):
    """SRCH-06: good captures (SEE >= 0) must precede killers in picker order.

    After the TT move stage, the next non-empty stage for a tactical position
    should yield captures with SEE >= 0 before any quiet killer moves.
    Verified by inspecting the sequence of moves returned by a series of next()
    calls on a position with both captures and killers loaded.
    """
    pass


@pytest.mark.skip(reason="Plan 03-02 will implement; this is a Wave 0 stub")
def test_picker_quiets_history_sorted(v7_native_engine):
    """SRCH-06: quiet moves in S_QUIETS stage must be sorted by history score.

    Given two quiet moves where one has a higher history[side][from][to] value,
    the picker must yield the higher-history move first within the S_QUIETS stage.
    Verifies that the persistent history table (D-03 Bug #2 fix) is actually
    consumed by the staged picker.
    """
    pass
