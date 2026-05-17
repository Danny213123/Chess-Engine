"""RED test for Plan 02-03 Task 1: the fetch_fastchess.py skeleton MUST
refuse to run while the human-checkpoint sentinels are still present.

This file is intentionally named *_skeleton.py to distinguish it from
``tests/test_fetch_fastchess.py`` (Task 4), which lands AFTER the human
checkpoint replaces the sentinels with real values. The skeleton test
exercises the failure path before the constants get filled in; the
Task 4 suite then includes ``test_constants_no_sentinels`` which pins
the post-checkpoint state.

Per Plan 02-03 acceptance criteria for Task 1:
  - ``ensure_fastchess()`` raises SystemExit immediately if any sentinel
    is present, with a message identifying Plan 02-03 Task 2.
"""

from __future__ import annotations

import pytest


def test_skeleton_refuses_to_run_with_sentinels():
    """ensure_fastchess() MUST SystemExit while sentinels are unresolved.

    The PENDING_HUMAN_CHECKPOINT sentinels are the D-02 trust gate: the
    fetcher cannot be allowed to download anything until a human has
    independently verified the per-OS SHA256s. The error message MUST
    reference Plan 02-03 Task 2 so the operator knows where to look.
    """
    # Module import is allowed (constants exist, just hold sentinels).
    from tools import fetch_fastchess as ff

    # Verify the sentinel is present (otherwise this test is meaningless).
    assert ff.FASTCHESS_RELEASE == "PENDING_HUMAN_CHECKPOINT", (
        "Sentinel removed before Task 4 lands the full test suite. "
        "Delete this skeleton test once tests/test_fetch_fastchess.py "
        "ships."
    )

    with pytest.raises(SystemExit) as excinfo:
        ff.ensure_fastchess()

    # Message must reference Plan 02-03 Task 2 so the failure points the
    # operator at the next required action.
    msg = str(excinfo.value)
    assert "02-03" in msg or "Task 2" in msg or "human checkpoint" in msg.lower(), (
        f"SystemExit message must reference Plan 02-03 Task 2 / human "
        f"checkpoint, got: {msg!r}"
    )
