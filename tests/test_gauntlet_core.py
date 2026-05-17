"""Pure-function unit tests for tools.gauntlet_core (Plan 02-04a).

Coverage:
  * SPRT bounds + concurrency hardcoded per D-12 / D-08a
  * build_fastchess_command argv shape (sanity_mode toggles -sprt)
  * parse_fastchess_stdout — last block wins, verdict from llr vs bounds
  * parse_pgn_terminations — TIME_FORFEIT_PATTERNS + over-flag bucket
  * compute_sanity_verdict — boundary inclusive (D-10)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import gauntlet_core as gc


FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PGN = FIXTURE_DIR / "sample_games.pgn"
SAMPLE_STDOUT = FIXTURE_DIR / "sample_fastchess_output.txt"


# ---------------------------------------------------------------------------
# Constants — D-12 / D-08a / §10 Q1 RESOLVED
# ---------------------------------------------------------------------------


def test_sprt_bounds_hardcoded_d12():
    # elo0=0 elo1=10 alpha=0.05 beta=0.05 — D-12; NEVER read from CLI
    assert gc.SPRT_ELO0 == 0
    assert gc.SPRT_ELO1 == 10
    assert gc.SPRT_ALPHA == 0.05
    assert gc.SPRT_BETA == 0.05


def test_concurrency_hardcoded_d08a():
    assert gc.CONCURRENCY == 1


def test_time_forfeit_patterns_resolved():
    # §10 Q1 RESOLVED — both phrases must appear; case-insensitive substring
    assert "time forfeit" in gc.TIME_FORFEIT_PATTERNS
    assert "on time" in gc.TIME_FORFEIT_PATTERNS


# ---------------------------------------------------------------------------
# build_fastchess_command — RESEARCH §2 literal token order
# ---------------------------------------------------------------------------


def _stub_args(**overrides):
    base = dict(
        fastchess_path=Path("tools/.cache/fastchess"),
        engines={
            "v7": Path("src/chess_engine/engine/v7/build/v7_uci"),
            "v6": Path("src/chess_engine/engine/v6/build/v6_uci"),
        },
        tc="10+0.1",
        hash_mb=64,
        threads=1,
        run_dir=Path("/tmp/gauntlet-run"),
        opening_book_path=Path("tools/books/8moves_v3.pgn"),
        rounds=5000,
        sanity_mode=False,
    )
    base.update(overrides)
    return base


def test_sprt_flags_hardcoded():
    cmd = gc.build_fastchess_command(**_stub_args(sanity_mode=False))
    # elo0=0 elo1=10 alpha=0.05 beta=0.05 — D-12 literal tokens
    assert "-sprt" in cmd
    assert "elo0=0" in cmd
    assert "elo1=10" in cmd
    assert "alpha=0.05" in cmd
    assert "beta=0.05" in cmd


def test_sanity_mode_omits_sprt():
    cmd = gc.build_fastchess_command(**_stub_args(sanity_mode=True))
    assert "-sprt" not in cmd
    # And none of the SPRT bound tokens leak through
    assert not any(t.startswith("elo0=") for t in cmd)
    assert not any(t.startswith("elo1=") for t in cmd)


def test_concurrency_always_one():
    cmd = gc.build_fastchess_command(**_stub_args())
    idx = cmd.index("-concurrency")
    assert cmd[idx + 1] == "1"


def test_default_tc_is_10_plus_0_1():
    cmd = gc.build_fastchess_command(**_stub_args(tc="10+0.1"))
    each_idx = cmd.index("-each")
    assert cmd[each_idx + 1] == "tc=10+0.1"


def test_opening_book_path_passed_through():
    book = Path("/some/book.pgn")
    cmd = gc.build_fastchess_command(**_stub_args(opening_book_path=book))
    assert f"file={book}" in cmd


def test_engine_blocks_emitted_in_order():
    cmd = gc.build_fastchess_command(**_stub_args())
    assert "name=v7" in cmd
    assert "name=v6" in cmd
    # v7 (insertion-order first) must precede v6
    assert cmd.index("name=v7") < cmd.index("name=v6")


def test_pgn_and_log_paths_under_run_dir():
    run_dir = Path("/tmp/gauntlet-run")
    cmd = gc.build_fastchess_command(**_stub_args(run_dir=run_dir))
    assert f"file={run_dir}/games.pgn" in cmd
    assert f"file={run_dir}/fastchess.log" in cmd


# ---------------------------------------------------------------------------
# parse_fastchess_stdout — RESEARCH §4
# ---------------------------------------------------------------------------


def test_parse_fastchess_stdout_extracts_last_block():
    text = SAMPLE_STDOUT.read_text(encoding="utf-8")
    result = gc.parse_fastchess_stdout(text)
    # LAST block: Elo 13.87, LLR 2.90, Games N:4186, Penta [130, 455, 782, 570, 156]
    assert result["elo"] == pytest.approx(13.87)
    assert result["llr"] == pytest.approx(2.90)
    assert result["games"]["n"] == 4186
    assert result["penta"] == [130, 455, 782, 570, 156]


def test_verdict_h1_on_high_llr():
    text = "LLR  | 3.00 (-2.25, 2.89) [0.00, 5.00]\n"
    result = gc.parse_fastchess_stdout(text)
    assert result["verdict"] == "H1"


def test_verdict_h0_on_low_llr():
    text = "LLR  | -3.00 (-2.25, 2.89) [0.00, 5.00]\n"
    result = gc.parse_fastchess_stdout(text)
    assert result["verdict"] == "H0"


def test_verdict_inconclusive_in_between():
    text = "LLR  | 0.50 (-2.25, 2.89) [0.00, 5.00]\n"
    result = gc.parse_fastchess_stdout(text)
    assert result["verdict"] == "inconclusive"


def test_verdict_inconclusive_on_missing_data():
    # Empty input must not raise — parser returns Nones + inconclusive
    result = gc.parse_fastchess_stdout("")
    assert result["verdict"] == "inconclusive"
    assert result["llr"] is None
    assert result["elo"] is None


def test_last_block_wins_with_two_blocks_inline():
    text = (
        "LLR  | 1.00 (-2.25, 2.89) [0.00, 5.00]\n"
        "Elo  | 10.00 +- 9.00 (95%)\n"
        "Games | N: 1000 W: 200 L: 180 D: 620\n"
        "Penta | [10, 20, 30, 40, 50]\n"
        "LLR  | 2.95 (-2.25, 2.89) [0.00, 5.00]\n"
        "Elo  | 14.00 +- 7.00 (95%)\n"
        "Games | N: 2000 W: 500 L: 450 D: 1050\n"
        "Penta | [50, 100, 150, 200, 250]\n"
    )
    result = gc.parse_fastchess_stdout(text)
    assert result["llr"] == pytest.approx(2.95)
    assert result["elo"] == pytest.approx(14.00)
    assert result["games"]["n"] == 2000
    assert result["penta"] == [50, 100, 150, 200, 250]
    assert result["verdict"] == "H1"  # 2.95 >= 2.89


# ---------------------------------------------------------------------------
# parse_pgn_terminations — §10 Q1 RESOLVED contract
# ---------------------------------------------------------------------------


def test_time_forfeit_parse_lowercase():
    result = gc.parse_pgn_terminations(SAMPLE_PGN, ["v6", "v7"])
    # Game 2: [Result "1-0"] [Termination "time forfeit"] — black (v7) lost
    # Game 4: [Result "0-1"] [Termination "on time"]      — white (v7) lost
    # Game 3: [Result "0-1"] [Termination "Time Forfeit"] — white (v7) lost
    # Game 6: [Result "0-1"] [Termination "weird new string"] — over-flag → v7
    assert result["time_forfeits"]["v7"] == 4  # 3 forfeits + 1 over-flag
    assert result["time_forfeits"]["v6"] == 0


def test_time_forfeit_parse_on_time():
    # Same fixture asserts the "on time" string is bucketed as a forfeit
    result = gc.parse_pgn_terminations(SAMPLE_PGN, ["v6", "v7"])
    # The Game 4 "on time" attribution to v7 is already covered by the
    # aggregate count above; assert independently that the patterns tuple
    # is what's actually being matched.
    assert "on time" in gc.TIME_FORFEIT_PATTERNS
    assert result["time_forfeits"]["v7"] >= 1


def test_time_forfeit_case_insensitive():
    # Game 3 uses "Time Forfeit" (mixed case); must still be counted
    result = gc.parse_pgn_terminations(SAMPLE_PGN, ["v6", "v7"])
    # If case-insensitive matching is broken, "Time Forfeit" would fall
    # through to the over-flag bucket — but we'd still see the count, so
    # additionally assert it does NOT appear in unrecognized_terminations.
    assert "Time Forfeit" not in result["unrecognized_terminations"]


def test_other_termination_buckets_separately():
    result = gc.parse_pgn_terminations(SAMPLE_PGN, ["v6", "v7"])
    # Game 5: [Result "1/2-1/2"] [Termination "adjudication"] — draw → loser=None
    # So other_terminations stays zero for both engines but the bucket
    # path itself is exercised. Assert the over-flag fallback wasn't tripped
    # by this string.
    assert "adjudication" not in result["unrecognized_terminations"]


def test_unrecognized_termination_triggers_investigation():
    result = gc.parse_pgn_terminations(SAMPLE_PGN, ["v6", "v7"])
    assert result["investigation_required"] is True
    assert "weird new string" in result["unrecognized_terminations"]


def test_no_forfeits_no_investigation(tmp_path):
    pgn = tmp_path / "clean.pgn"
    pgn.write_text(
        '[Event "clean"]\n'
        '[White "v7"]\n'
        '[Black "v6"]\n'
        '[Result "1-0"]\n'
        '[Termination "normal"]\n'
        "\n"
        "1. e4 e5 1-0\n"
        "\n"
        '[Event "clean"]\n'
        '[White "v6"]\n'
        '[Black "v7"]\n'
        '[Result "0-1"]\n'
        '[Termination "normal"]\n'
        "\n"
        "1. d4 d5 0-1\n",
        encoding="utf-8",
    )
    result = gc.parse_pgn_terminations(pgn, ["v6", "v7"])
    assert result["investigation_required"] is False
    assert result["time_forfeits"] == {"v6": 0, "v7": 0}
    assert result["other_terminations"] == {"v6": 0, "v7": 0}
    assert result["unrecognized_terminations"] == []


def test_engine_names_default_to_zero(tmp_path):
    # Empty PGN — both engine names must still appear as zero keys
    pgn = tmp_path / "empty.pgn"
    pgn.write_text("", encoding="utf-8")
    result = gc.parse_pgn_terminations(pgn, ["v6", "v7"])
    assert result["time_forfeits"] == {"v6": 0, "v7": 0}
    assert result["other_terminations"] == {"v6": 0, "v7": 0}


def test_missing_pgn_raises_gauntlet_error(tmp_path):
    with pytest.raises(gc.GauntletError):
        gc.parse_pgn_terminations(tmp_path / "nope.pgn", ["v6", "v7"])


# ---------------------------------------------------------------------------
# compute_sanity_verdict — D-10 boundary inclusive
# ---------------------------------------------------------------------------


def test_sanity_verdict_boundary_inclusive():
    assert gc.compute_sanity_verdict(0.0) == "PASS"
    assert gc.compute_sanity_verdict(15.0) == "PASS"
    assert gc.compute_sanity_verdict(-15.0) == "PASS"
    assert gc.compute_sanity_verdict(15.01) == "FAIL"
    assert gc.compute_sanity_verdict(-15.01) == "FAIL"


# ---------------------------------------------------------------------------
# collect_per_move_nps — D-13 sentinel input
# ---------------------------------------------------------------------------


def test_collect_per_move_nps_attributes_by_ply_parity():
    # Game 1 in the fixture: White=v7, Black=v6, four moves with nps comments.
    # Plies 1,3 → v7 (white); plies 2,4 → v6 (black). Game 2: White=v6, Black=v7.
    result = gc.collect_per_move_nps(SAMPLE_PGN, ["v6", "v7"])
    # Both engines must have samples > 0 from the annotated games
    assert result["v7"]["samples"] >= 2
    assert result["v6"]["samples"] >= 2
    assert result["v7"]["median"] is not None
    assert result["v6"]["median"] is not None


def test_collect_per_move_nps_empty_when_no_samples(tmp_path):
    pgn = tmp_path / "no_nps.pgn"
    pgn.write_text(
        '[White "v7"]\n[Black "v6"]\n[Result "1-0"]\n\n1. e4 e5 1-0\n',
        encoding="utf-8",
    )
    result = gc.collect_per_move_nps(pgn, ["v6", "v7"])
    assert result["v7"] == {"median": None, "mean": None, "samples": 0}
    assert result["v6"] == {"median": None, "mean": None, "samples": 0}
