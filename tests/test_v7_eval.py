"""V7 evaluation pipeline tests (Plan 04).

Covers the entire coeffs.json → src/coeffs.cpp → src/eval.cpp pipeline:

1. test_coeffs_json_schema — all 27 EVAL-* top-level keys present with
   correct shapes (PSTs 12×64, mobility 9/14/15/28, king_attack_table[100],
   passed_pawn_by_rank[8], _meta cites Pesto + Zurichess).
2. test_coeffs_codegen_deterministic — running gen_coeffs.py twice on the
   same input produces byte-identical output with no CRLF (D-13).
3. test_coeffs_cpp_gitignored — src/coeffs.cpp is in .gitignore and is
   recognized as ignored by `git check-ignore` (D-12).
4. test_eval_startpos_balanced — evaluate(STARTPOS) returns int in
   [-50, +50] cp (a large favor either way indicates sign error or
   missing term).
5. test_eval_terms_use_coeffs — eval.cpp references v7::coeffs::* at
   least 10 times and contains no hardcoded weight literals (EVAL-10).
6. test_eval_returns_int — binding returns a Python int.
7. test_codegen_regenerates_on_change — modifying coeffs.json and
   rerunning gen_coeffs.py produces a different output (proves codegen
   actually reads the JSON, not a cached version).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Repo root from this test file: tests/ → ../
REPO_ROOT = Path(__file__).resolve().parent.parent
V7_DIR = REPO_ROOT / "src" / "chess_engine" / "engine" / "v7"
COEFFS_JSON = V7_DIR / "coeffs.json"
GEN_SCRIPT = V7_DIR / "tools" / "gen_coeffs.py"
EVAL_CPP = V7_DIR / "src" / "eval.cpp"
COEFFS_CPP_PATH = "src/chess_engine/engine/v7/src/coeffs.cpp"
GITIGNORE = REPO_ROOT / ".gitignore"

STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

EXPECTED_TOP_KEYS = {
    "material_mg", "material_eg", "phase_weights",
    "pst_mg", "pst_eg",
    "mobility_knight_mg", "mobility_knight_eg",
    "mobility_bishop_mg", "mobility_bishop_eg",
    "mobility_rook_mg", "mobility_rook_eg",
    "mobility_queen_mg", "mobility_queen_eg",
    "bishop_pair_mg", "bishop_pair_eg",
    "rook_open_file", "rook_semi_open_file",
    "doubled_pawn", "isolated_pawn", "backward_pawn",
    "passed_pawn_by_rank", "king_attack_table",
    "threat_minor_by_pawn", "threat_rook_by_minor", "threat_queen_by_rook",
    "tempo_mg", "tempo_eg",
}


# Try to import V7 native module — tests that need it use the fixture.
try:
    from chess_engine.engine.v7 import chess_algorithm as v7  # type: ignore
except Exception:  # pragma: no cover - import guard
    v7 = None


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use; skip module if build fails."""
    if v7 is None:
        pytest.skip("V7 module not importable")
    try:
        return v7.ensure_available(auto_build=True)
    except Exception as error:  # pragma: no cover
        pytest.skip(f"V7 native engine unavailable: {error}")


# =============================================================================
# Test 1: schema
# =============================================================================

def test_coeffs_json_schema():
    """All 27 EVAL-* top-level keys present with correct shapes (EVAL-01..11)."""
    assert COEFFS_JSON.is_file(), f"missing: {COEFFS_JSON}"
    data = json.loads(COEFFS_JSON.read_text(encoding="utf-8"))

    # Top-level keys
    keys = set(data.keys()) - {"_meta"}
    missing = EXPECTED_TOP_KEYS - keys
    extra = keys - EXPECTED_TOP_KEYS
    assert not missing, f"missing keys: {sorted(missing)}"
    assert not extra, f"unexpected extra keys: {sorted(extra)}"

    # Material / phase: 6 piece keys each
    for k in ("material_mg", "material_eg", "phase_weights"):
        assert set(data[k].keys()) == {"P", "N", "B", "R", "Q", "K"}, (
            f"{k} sub-keys: {set(data[k].keys())}"
        )

    # PSTs: 12 tables × 64
    for k in ("pst_mg", "pst_eg"):
        assert set(data[k].keys()) == {"P", "N", "B", "R", "Q", "K"}
        for sub, vals in data[k].items():
            assert isinstance(vals, list), f"{k}.{sub} must be a list"
            assert len(vals) == 64, f"{k}.{sub} length {len(vals)} != 64"

    # Mobility tables
    assert len(data["mobility_knight_mg"]) == 9
    assert len(data["mobility_knight_eg"]) == 9
    assert len(data["mobility_bishop_mg"]) == 14
    assert len(data["mobility_bishop_eg"]) == 14
    assert len(data["mobility_rook_mg"]) == 15
    assert len(data["mobility_rook_eg"]) == 15
    assert len(data["mobility_queen_mg"]) == 28
    assert len(data["mobility_queen_eg"]) == 28

    # King attack table + passed-pawn-by-rank
    assert len(data["king_attack_table"]) == 100
    assert len(data["passed_pawn_by_rank"]) == 8

    # _meta.source citations
    src_meta = data["_meta"]["source"]
    assert "chessprogramming.org/PeSTO" in src_meta, (
        "_meta.source must cite chessprogramming.org/PeSTO (D-01)"
    )
    assert "Zurichess" in src_meta, (
        "_meta.source must mention Zurichess as Phase 4 tuning corpus (D-01)"
    )


# =============================================================================
# Test 2: codegen determinism
# =============================================================================

def _run_codegen(out_path: Path) -> None:
    """Invoke gen_coeffs.py via subprocess on COEFFS_JSON → out_path."""
    result = subprocess.run(
        [sys.executable, str(GEN_SCRIPT), str(COEFFS_JSON), str(out_path)],
        check=True,
        capture_output=True,
    )
    assert out_path.is_file(), f"codegen did not produce {out_path}: {result.stderr!r}"


def test_coeffs_codegen_deterministic():
    """gen_coeffs.py is byte-deterministic; output uses LF endings (D-13)."""
    assert GEN_SCRIPT.is_file(), f"missing: {GEN_SCRIPT}"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        out1 = tmp_path / "run1.cpp"
        out2 = tmp_path / "run2.cpp"
        _run_codegen(out1)
        _run_codegen(out2)

        data1 = out1.read_bytes()
        data2 = out2.read_bytes()
        assert data1 == data2, "gen_coeffs.py output is NOT byte-deterministic"
        assert b"\r\n" not in data1, "CRLF found in codegen output (must be LF only)"

        # Sanity: namespace + header present
        text = data1.decode("utf-8")
        assert "namespace v7::coeffs {" in text
        assert "} // namespace v7::coeffs" in text
        assert "GENERATED by tools/gen_coeffs.py" in text


# =============================================================================
# Test 3: src/coeffs.cpp is gitignored
# =============================================================================

def test_coeffs_cpp_gitignored():
    """src/coeffs.cpp must be in .gitignore (D-12 — generated, never committed)."""
    assert GITIGNORE.is_file()
    ignore_text = GITIGNORE.read_text(encoding="utf-8")
    assert COEFFS_CPP_PATH in ignore_text, (
        f".gitignore does not list {COEFFS_CPP_PATH} (D-12)"
    )

    # git check-ignore confirms the rule actually fires (cwd = repo root).
    # Some CI environments may not have git on PATH; gate on availability.
    if shutil.which("git") is None:
        pytest.skip("git not on PATH — skipping check-ignore assertion")

    proc = subprocess.run(
        ["git", "check-ignore", COEFFS_CPP_PATH],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    # check-ignore exits 0 if path IS ignored, 1 if NOT ignored
    assert proc.returncode == 0, (
        f"git check-ignore says {COEFFS_CPP_PATH} is NOT ignored "
        f"(stdout={proc.stdout!r}, stderr={proc.stderr!r})"
    )


# =============================================================================
# Test 4: eval(startpos) is balanced
# =============================================================================

def test_eval_startpos_balanced(v7_native_engine):
    """Pesto baseline + symmetric startpos should be near 0 cp (allow tempo)."""
    module = v7_native_engine
    score = module.evaluate(STARTPOS_FEN)
    assert isinstance(score, int)
    assert -50 <= score <= 50, (
        f"startpos eval too far from balanced: {score} cp — likely sign error "
        f"or missing term in eval.cpp"
    )


# =============================================================================
# Test 5: eval.cpp uses v7::coeffs::* (no hardcoded weights)
# =============================================================================

def test_eval_terms_use_coeffs():
    """eval.cpp reads every weight via v7::coeffs::* (EVAL-10)."""
    assert EVAL_CPP.is_file(), f"missing: {EVAL_CPP}"
    text = EVAL_CPP.read_text(encoding="utf-8")

    # Must reference the namespace
    assert "v7::coeffs::" in text, (
        "eval.cpp must reference v7::coeffs:: extern symbols (EVAL-10)"
    )

    # Distinct symbol references — covers all term families
    refs = set(re.findall(r"v7::coeffs::\w+|coeffs::\w+", text))
    # Allow short-form `coeffs::` because v7::coeffs is opened via using namespace
    # (or directly used without v7:: prefix when inside `namespace v7 {`).
    # Strip the `v7::` prefix variants for counting.
    symbols = {r.replace("v7::coeffs::", "").replace("coeffs::", "") for r in refs}
    assert len(symbols) >= 10, (
        f"eval.cpp references only {len(symbols)} distinct coeffs symbols "
        f"(expected >= 10 for all term families): {sorted(symbols)}"
    )

    # No hardcoded weight constants (EVAL-10). Heuristic: count integer
    # literals >= 50 outside comments and strings. Pesto weights are
    # typically 100+ (pawn=100, etc.) — fewer than 5 such literals leaves
    # room for loop bounds (256 moves, 64 squares, etc.) and the phase
    # divisor (24).
    # Strip C++ comments first
    stripped = re.sub(r"//[^\n]*", "", text)
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
    large_literals = re.findall(r"\b\d{3,}\b", stripped)  # 3+ digit ints (>= 100)
    assert len(large_literals) <= 5, (
        f"eval.cpp contains {len(large_literals)} large numeric literals — "
        f"weights must come from coeffs::* not hardcoded: {large_literals}"
    )


# =============================================================================
# Test 6: binding returns int
# =============================================================================

def test_eval_returns_int(v7_native_engine):
    """evaluate(fen) returns a Python int."""
    module = v7_native_engine
    r = module.evaluate(STARTPOS_FEN)
    assert isinstance(r, int), f"evaluate returned {type(r).__name__}, expected int"


# =============================================================================
# Test 7: codegen re-runs on input change
# =============================================================================

def test_codegen_regenerates_on_change():
    """Modifying coeffs.json (tempo_mg 10 → 11) produces a different cpp."""
    assert GEN_SCRIPT.is_file()
    original = json.loads(COEFFS_JSON.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        json_a = tmp_path / "a.json"
        json_b = tmp_path / "b.json"
        cpp_a = tmp_path / "a.cpp"
        cpp_b = tmp_path / "b.cpp"

        # Baseline copy
        json_a.write_text(json.dumps(original, sort_keys=True, indent=2),
                          encoding="utf-8")
        # Bump tempo_mg
        modified = json.loads(json.dumps(original))  # deep copy
        modified["tempo_mg"] = int(modified.get("tempo_mg", 10)) + 1
        json_b.write_text(json.dumps(modified, sort_keys=True, indent=2),
                          encoding="utf-8")

        subprocess.run(
            [sys.executable, str(GEN_SCRIPT), str(json_a), str(cpp_a)],
            check=True, capture_output=True,
        )
        subprocess.run(
            [sys.executable, str(GEN_SCRIPT), str(json_b), str(cpp_b)],
            check=True, capture_output=True,
        )

        a = cpp_a.read_bytes()
        b = cpp_b.read_bytes()
        assert a != b, (
            "gen_coeffs.py output did NOT change after coeffs.json edit — "
            "codegen is not reading the JSON"
        )
