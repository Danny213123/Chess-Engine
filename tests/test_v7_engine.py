"""V7 native engine fixture file.

This file owns the module-scoped v7_native_engine fixture so subsequent
plans (02/03/04/05/06) can append tests against a stable base. Plan 01
adds the fixture only; plan 06 (and the binding tests in plan 01 Task 2)
adds the actual test functions.
"""

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails.

    Mirrors V6 (tests/test_v6_native.py lines 6-11). The fixture returns
    the compiled native module so tests can call .Engine(), .perft(), etc.
    directly.
    """
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
