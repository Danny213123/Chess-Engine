"""V7 KPK bitbase codegen tests — Wave 0 stub.

ENDG-01: KPK bitbase generation and Fathom cross-check.
Plan 03-04 implements gen_kpk.py, the CMake codegen target, and
un-skips these tests.

References: D-10 (build-time codegen via tools/gen_kpk.py, mirrors
gen_coeffs.py pattern), D-12 (kpk_bitbase.cpp gitignored),
RESEARCH.md Pitfall 5 (KPK encoding — stm | bksq<<1 | wksq<<7 | psq<<13).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

REPO_ROOT = Path(__file__).resolve().parent.parent
V7_DIR = REPO_ROOT / "src" / "chess_engine" / "engine" / "v7"
GEN_SCRIPT = V7_DIR / "tools" / "gen_kpk.py"
KPK_CPP_PATH = "src/chess_engine/engine/v7/src/kpk_bitbase.cpp"
GITIGNORE = REPO_ROOT / ".gitignore"


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails."""
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")


@pytest.mark.skip(
    reason="slow; Plan 03-04 will implement — exhaustive 163,328-position Fathom cross-check"
)
def test_all_positions_match_fathom(v7_native_engine):
    """ENDG-01: all 163,328 KPK positions agree with Fathom tb_probe_wdl.

    Calls gen_kpk.py to generate the bitbase (if not already generated),
    then probes all 163,328 legal KPK positions via the C++ API and compares
    each result against Fathom's tb_probe_wdl output. Requires 100% agreement
    before the bitbase is considered valid (D-10 acceptance criterion).

    This test is slow (~seconds for the BFS + probe loop) — skipped by default.
    """
    pass


@pytest.mark.skip(reason="Plan 03-04 will implement; this is a Wave 0 stub")
def test_kpk_cpp_gitignored(v7_native_engine):
    """D-12: kpk_bitbase.cpp must be listed in .gitignore (mirrors coeffs.cpp).

    The generated C++ output is a build artifact and must not be committed.
    Verifies the .gitignore entry exists using `git check-ignore` (mirrors
    tests/test_v7_eval.py::test_coeffs_cpp_gitignored pattern).
    """
    pass
