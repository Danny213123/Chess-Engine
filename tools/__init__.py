"""Top-level ``tools`` package.

Houses out-of-tree developer utilities (binary fetchers, code generators)
that are NOT part of the shipping ``chess_engine`` package surface. Plan
02-03 (Phase 2 gauntlet harness) is the first plan to import from this
package directly (``from tools import fetch_fastchess``); prior usage was
script-only via ``python3 src/chess_engine/engine/v7/tools/gen_coeffs.py``.

Keeping this an explicit (non-PEP-420) package guarantees pytest can
discover ``tests/test_fetch_fastchess.py`` regardless of the host's
implicit-namespace-package behavior.
"""
