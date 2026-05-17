"""I/O-path unit tests for tools.gauntlet (Plan 02-04b).

Coverage scope (the parser/builder/PGN-tally tests live in
tests/test_gauntlet_core.py from Plan 02-04a):

* **D-09 hard deferral (BLOCKER-2).** `main(["run"])` returns 2 with the
  exact :data:`tools.gauntlet.D9_MESSAGE` on stderr; no `--i-know`
  bypass flag exists in argparse.
* **investigation_required wiring (WARNING-3).** :func:`write_summary`
  flips ``summary["result"]["investigation_required"]`` and emits a
  stderr warning when a forfeit count > 0 OR when the upstream
  :func:`parse_pgn_terminations` already raised its own
  ``investigation_required`` (over-flag bucket propagation).
* **resolve_opening_book fallback (WARNING-5).** Vendored path, manifest
  fallback (monkeypatched ``urlopen``), missing-both → GauntletError,
  and the checksum-mismatch path (corrupt ``.part`` is cleaned up).
* **make_run_dir.** Windows-safe ISO format; FileExistsError on
  duplicate timestamp.

All tests are stdlib-only and pure; no real subprocess, no real
network, no real fastchess / v6_uci / v7_uci needed.
"""

from __future__ import annotations

import datetime
import hashlib
import io
import json
import re
from pathlib import Path

import pytest

from tools import gauntlet as g
from tools.gauntlet_core import GauntletError


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def engines_dict(tmp_path: Path) -> dict[str, Path]:
    """Synthetic engine dict — paths only need to be stringifiable.

    write_summary writes them into summary.json as strings; no file is
    ever opened off these paths during the writer test path.
    """
    return {
        "v6": tmp_path / "v6_uci",
        "v7": tmp_path / "v7_uci",
    }


def _baseline_pgn_parse(engines: dict[str, Path]) -> dict:
    """Build a ``parse_pgn_terminations``-shaped dict with all zeros."""
    return {
        "time_forfeits": {name: 0 for name in engines},
        "other_terminations": {name: 0 for name in engines},
        "investigation_required": False,
        "unrecognized_terminations": [],
    }


def _baseline_parsed_result() -> dict:
    """Build a ``parse_fastchess_stdout``-shaped dict with realistic values."""
    return {
        "elo": 1.5,
        "elo_err": 5.0,
        "elo_ci": 95,
        "llr": 0.5,
        "llr_lower": -2.25,
        "llr_upper": 2.89,
        "games": {"n": 40, "w": 12, "l": 11, "d": 17},
        "penta": [2, 5, 8, 4, 1],
        "verdict": "inconclusive",
    }


def _write_summary_with(
    run_dir: Path,
    engines: dict[str, Path],
    *,
    pgn_parse: dict,
    sanity_mode: bool = True,
    parsed_result: dict | None = None,
) -> Path:
    """Thin wrapper so each test states only what it overrides."""
    return g.write_summary(
        run_dir,
        command=["/fake/fastchess", "-engine", "..."],
        engines=engines,
        tc="10+0.1",
        sanity_mode=sanity_mode,
        fastchess_version="v1.8.0-alpha",
        bench_nps={"v6": 500000, "v7": 480000},
        parsed_result=parsed_result if parsed_result is not None else _baseline_parsed_result(),
        pgn_parse_result=pgn_parse,
        per_move_nps={
            "v6": {"median": 510000, "mean": 520000.0, "samples": 12},
            "v7": {"median": 470000, "mean": 475000.0, "samples": 11},
        },
    )


@pytest.fixture(autouse=True)
def _isolate_book(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Default isolation: point the resolver at empty tmp paths.

    Individual tests opt into the vendored or fallback path explicitly via
    monkeypatch. This stops a stray real-tree ``tools/books/8moves_v3.pgn``
    or ``.fetch_fallback.json`` from leaking into a test.
    """
    monkeypatch.setattr(g, "VENDORED_BOOK", tmp_path / "missing_book.pgn")
    monkeypatch.setattr(g, "FALLBACK_MANIFEST", tmp_path / "missing_manifest.json")
    monkeypatch.setattr(g, "CACHED_BOOK", tmp_path / "cache" / "8moves_v3.pgn")


# ---------------------------------------------------------------------------
# D-09 hard deferral (BLOCKER-2)
# ---------------------------------------------------------------------------


def test_run_subcommand_deferred(capsys: pytest.CaptureFixture[str]) -> None:
    """``main(["run"])`` returns 2 with the exact D9 stderr message."""
    rc = g.main(["run"])
    assert rc == 2
    captured = capsys.readouterr()
    assert "deferred to Phase 3 (D-09); harness ships V6-vs-V6 sanity only in Phase 2" in captured.err
    # Exact-match against the module constant so paraphrase drift is caught.
    assert g.D9_MESSAGE in captured.err


def test_run_subcommand_has_no_i_know_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """BLOCKER-2 verification — argparse rejects any bypass flag."""
    with pytest.raises(SystemExit) as exc_info:
        g.main(["run", "--i-know"])
    # argparse errors with exit code 2 and writes to stderr.
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "unrecognized" in captured.err.lower() or "invalid" in captured.err.lower()


# ---------------------------------------------------------------------------
# Sanity subcommand argument validation
# ---------------------------------------------------------------------------


def test_sanity_subcommand_rejects_zero_games(capsys: pytest.CaptureFixture[str]) -> None:
    rc = g.main(["sanity", "--games", "0"])
    assert rc != 0
    assert "must be > 0" in capsys.readouterr().err


def test_sanity_subcommand_rejects_negative_games(capsys: pytest.CaptureFixture[str]) -> None:
    rc = g.main(["sanity", "--games", "-5"])
    assert rc != 0
    assert "must be > 0" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# write_summary — investigation_required wiring (WARNING-3)
# ---------------------------------------------------------------------------


def test_write_summary_sets_investigation_required_on_forfeit(
    tmp_path: Path,
    engines_dict: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Any time-forfeit > 0 trips the flag AND prints the stderr warning."""
    pgn_parse = _baseline_pgn_parse(engines_dict)
    pgn_parse["time_forfeits"] = {"v6": 1, "v7": 0}
    summary_path = _write_summary_with(tmp_path, engines_dict, pgn_parse=pgn_parse)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["result"]["investigation_required"] is True
    err = capsys.readouterr().err
    assert "1 time forfeit" in err


def test_write_summary_no_investigation_when_clean(
    tmp_path: Path,
    engines_dict: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """All-zero forfeits + clean PGN flag → False, no stderr warning."""
    pgn_parse = _baseline_pgn_parse(engines_dict)
    summary_path = _write_summary_with(tmp_path, engines_dict, pgn_parse=pgn_parse)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["result"]["investigation_required"] is False
    err = capsys.readouterr().err
    assert "time forfeit" not in err


def test_write_summary_investigation_propagates_from_pgn_parse(
    tmp_path: Path,
    engines_dict: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Over-flag bucket from gauntlet_core flips the summary flag too."""
    pgn_parse = _baseline_pgn_parse(engines_dict)
    pgn_parse["investigation_required"] = True
    pgn_parse["unrecognized_terminations"] = ["weird new string"]
    # time_forfeits all zero — the flip must come purely from the PGN bucket.
    summary_path = _write_summary_with(tmp_path, engines_dict, pgn_parse=pgn_parse)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["result"]["investigation_required"] is True
    # The stderr warning still fires (n=0 in the template — clear UX that
    # the over-flag bucket caught something even if no forfeit was counted).
    assert "time forfeit" in capsys.readouterr().err


def test_write_summary_schema_keys(
    tmp_path: Path,
    engines_dict: dict[str, Path],
) -> None:
    """Result block contains every key required by Plan 02-04b §must_haves."""
    pgn_parse = _baseline_pgn_parse(engines_dict)
    summary_path = _write_summary_with(tmp_path, engines_dict, pgn_parse=pgn_parse)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    expected_keys = {
        "verdict",
        "elo",
        "elo_err",
        "elo_ci",
        "llr",
        "llr_lower",
        "llr_upper",
        "games",
        "penta",
        "time_forfeits",
        "other_terminations",
        "investigation_required",
    }
    assert expected_keys.issubset(summary["result"].keys())
    # Top-level invariants from must_haves.truths
    assert summary["schema_version"] == 1
    assert summary["concurrency"] == 1  # CONCURRENCY constant
    assert summary["sprt"] is None  # sanity_mode=True
    assert set(summary["nps"].keys()) == set(engines_dict.keys())


# ---------------------------------------------------------------------------
# make_run_dir
# ---------------------------------------------------------------------------


def test_make_run_dir_iso_format(tmp_path: Path) -> None:
    """Windows-safe ISO timestamp; matches r'^\\d{4}-\\d{2}-\\d{2}T\\d{2}-\\d{2}-\\d{2}Z$'."""
    run_dir = g.make_run_dir(tmp_path)
    assert run_dir.is_dir()
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$", run_dir.name), run_dir.name


def test_make_run_dir_collision_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Duplicate-timestamp invocation must raise FileExistsError."""
    fixed = datetime.datetime(2026, 5, 17, 12, 0, 0, tzinfo=datetime.timezone.utc)

    class _FrozenDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return fixed

    monkeypatch.setattr(g.datetime, "datetime", _FrozenDateTime)
    g.make_run_dir(tmp_path)
    with pytest.raises(FileExistsError):
        g.make_run_dir(tmp_path)


# ---------------------------------------------------------------------------
# resolve_opening_book — WARNING-5 / §10 Q3 RESOLVED Path A/B
# ---------------------------------------------------------------------------


def test_resolve_opening_book_vendored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vendored PGN present → return its path; no manifest consulted."""
    vendored = tmp_path / "books" / "8moves_v3.pgn"
    vendored.parent.mkdir(parents=True)
    vendored.write_bytes(b"[Event \"vendored\"]\n[Result \"*\"]\n*\n")
    monkeypatch.setattr(g, "VENDORED_BOOK", vendored)
    # Sabotage the fallback path to prove it's not consulted.
    monkeypatch.setattr(g, "FALLBACK_MANIFEST", tmp_path / "nonexistent.json")

    result = g.resolve_opening_book()
    assert result == vendored.resolve()


def test_resolve_opening_book_fallback_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vendored absent + manifest present + matching sha → cached path returned."""
    payload = b"[Event \"downloaded\"]\n[Result \"*\"]\n*\n" * 4
    sha = hashlib.sha256(payload).hexdigest()
    manifest_path = tmp_path / ".fetch_fallback.json"
    manifest_path.write_text(
        json.dumps({"url": "http://fake.test/book.pgn", "sha256": sha}),
        encoding="utf-8",
    )
    cache_path = tmp_path / "cache" / "8moves_v3.pgn"
    monkeypatch.setattr(g, "VENDORED_BOOK", tmp_path / "missing.pgn")
    monkeypatch.setattr(g, "FALLBACK_MANIFEST", manifest_path)
    monkeypatch.setattr(g, "CACHED_BOOK", cache_path)

    captured_urls: list[str] = []

    class _FakeResponse:
        def __init__(self, data: bytes) -> None:
            self._buf = io.BytesIO(data)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, n: int = -1) -> bytes:
            return self._buf.read(n) if n != -1 else self._buf.read()

    def _fake_urlopen(url: str):
        captured_urls.append(url)
        return _FakeResponse(payload)

    monkeypatch.setattr(g.urllib.request, "urlopen", _fake_urlopen)

    result = g.resolve_opening_book()
    assert result == cache_path.resolve()
    assert cache_path.read_bytes() == payload
    assert captured_urls == ["http://fake.test/book.pgn"]
    # Idempotent fast path: second call must NOT re-download.
    result2 = g.resolve_opening_book()
    assert result2 == cache_path.resolve()
    assert captured_urls == ["http://fake.test/book.pgn"]


def test_resolve_opening_book_missing_both_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither vendored nor manifest → GauntletError mentioning Plan 02-03."""
    monkeypatch.setattr(g, "VENDORED_BOOK", tmp_path / "missing.pgn")
    monkeypatch.setattr(g, "FALLBACK_MANIFEST", tmp_path / "no_manifest.json")
    with pytest.raises(GauntletError) as exc_info:
        g.resolve_opening_book()
    msg = str(exc_info.value)
    assert "no opening book" in msg
    assert ".fetch_fallback.json" in msg


def test_resolve_opening_book_checksum_mismatch_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bad checksum → GauntletError('checksum mismatch') + .part cleaned up."""
    real_payload = b"actual bytes that get downloaded"
    wrong_sha = "0" * 64
    manifest_path = tmp_path / ".fetch_fallback.json"
    manifest_path.write_text(
        json.dumps({"url": "http://fake.test/book.pgn", "sha256": wrong_sha}),
        encoding="utf-8",
    )
    cache_path = tmp_path / "cache" / "8moves_v3.pgn"
    monkeypatch.setattr(g, "VENDORED_BOOK", tmp_path / "missing.pgn")
    monkeypatch.setattr(g, "FALLBACK_MANIFEST", manifest_path)
    monkeypatch.setattr(g, "CACHED_BOOK", cache_path)

    class _FakeResponse:
        def __init__(self, data: bytes) -> None:
            self._buf = io.BytesIO(data)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, n: int = -1) -> bytes:
            return self._buf.read(n) if n != -1 else self._buf.read()

    monkeypatch.setattr(
        g.urllib.request,
        "urlopen",
        lambda url: _FakeResponse(real_payload),
    )

    with pytest.raises(GauntletError) as exc_info:
        g.resolve_opening_book()
    assert "checksum mismatch" in str(exc_info.value)
    # No leftover .part — the failed download must clean up after itself.
    part_path = cache_path.with_suffix(cache_path.suffix + ".part")
    assert not part_path.exists()
    # And no canonical cache file either.
    assert not cache_path.exists()
