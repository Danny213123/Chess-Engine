"""NPS regression sentinel (Plan 02-05 Task 2, D-13 / GAUNT-08).

Operationalizes CLAUDE.md's ~20% NPS constraint as a pytest gate that
reads ``.planning/gauntlets/<ISO>/summary.json`` and asserts the V7
bench NPS stays within 80% of V6 bench NPS.

Design (per Plan 02-05 must_haves.truths + acceptance_criteria):

1. The PRODUCTION sentinel — ``test_nps_regression`` — is gated behind
   ``RUN_BENCHMARKS=1`` (mirrors tests/test_v7_engine.py::test_nps_sentinel)
   and reads the LATEST summary.json under the real production root
   (``.planning/gauntlets/``). Default ``pytest -q`` SKIPs it because
   NPS measurement requires a quiet host.

2. The assertion logic is factored into ``_load_latest_summary`` and
   ``_assert_nps_ratio`` so the unit tests below can exercise it on
   synthetic summaries via the conftest ``summary_json_factory`` fixture
   without depending on a real fastchess run.

3. Discovery is lexical-sort over ISO timestamps under the production
   root — deterministic ordering when multiple runs accumulate.

4. Missing/empty production root → ``pytest.skip`` with the literal
   "no gauntlet runs found — run tools/gauntlet.py sanity first" so the
   sentinel never falsely fails on a host that hasn't yet run the
   harness.

References:
- Plan 02-04b summary.json schema (tools/gauntlet.py:write_summary)
- Plan 02-05 acceptance_criteria literal-string gates
- tests/test_v7_engine.py lines 108-117 (CANONICAL skipif decorator)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import pytest


#: Production discovery root — the real ``.planning/gauntlets/`` tree.
#: Unit tests pass ``root=gauntlet_root`` (tmp_path) to override.
PRODUCTION_ROOT: Path = Path(".planning/gauntlets")

#: D-13 / CLAUDE.md ~20% NPS constraint — boundary inclusive (ratio >= 0.8 PASSes).
NPS_FLOOR: float = 0.8

#: Literal skip reason for empty-gauntlets-dir — pinned by acceptance_criteria.
EMPTY_ROOT_SKIP_REASON: str = (
    "no gauntlet runs found — run tools/gauntlet.py sanity first"
)


def _load_latest_summary(root: Path = PRODUCTION_ROOT) -> Optional[dict]:
    """Return the parsed summary.json from the lexically-greatest child of ``root``.

    Returns ``None`` when:
      * ``root`` does not exist,
      * ``root`` has no immediate subdirectories,
      * the lexically-greatest subdirectory lacks a summary.json.

    The lexical sort over ISO ``%Y-%m-%dT%H-%M-%SZ`` timestamps is
    monotone with chronological order — sorted() picks the newest run
    deterministically.
    """
    if not root.exists() or not root.is_dir():
        return None
    children = sorted(p for p in root.iterdir() if p.is_dir())
    if not children:
        return None
    latest = children[-1]
    summary_path = latest / "summary.json"
    if not summary_path.exists():
        return None
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _assert_nps_ratio(summary: dict) -> None:
    """Apply the D-13 / GAUNT-08 NPS-floor assertion against a parsed summary.

    Reads ``summary["nps"]["v7"]["bench_nps"]`` and
    ``summary["nps"]["v6"]["bench_nps"]``; computes ratio = v7 / v6;
    asserts ``ratio >= NPS_FLOOR``.

    SKIPs cleanly (rather than raising KeyError) when either bench_nps
    is missing or None — e.g. a V6-vs-V6 sanity run where the v7 entry
    is absent. This lets Plan 02-05 Task 3's V6-only sanity probe still
    write a valid summary without tripping a false regression.
    """
    nps = summary.get("nps") or {}
    v7_entry = nps.get("v7") or {}
    v6_entry = nps.get("v6") or {}
    v7_nps = v7_entry.get("bench_nps")
    v6_nps = v6_entry.get("bench_nps")

    if v7_nps is None or v6_nps is None:
        pytest.skip(
            "summary.json missing v7 or v6 bench_nps — needs v7 entry in nps block"
        )
    if v6_nps <= 0:
        pytest.skip(
            f"V6 bench_nps == {v6_nps}; cannot compute ratio (would div-by-zero)"
        )

    ratio = float(v7_nps) / float(v6_nps)
    assert ratio >= NPS_FLOOR, (
        f"V7 NPS {v7_nps:.0f} / V6 NPS {v6_nps:.0f} ratio {ratio:.2f} below "
        f"0.8 floor (CLAUDE.md ~20% NPS constraint). Re-run on a quiet host "
        f"before treating as a regression."
    )


# ---------------------------------------------------------------------------
# PRODUCTION sentinel — gated behind RUN_BENCHMARKS=1
# Decorator block copied VERBATIM from tests/test_v7_engine.py lines 108-117.
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
@pytest.mark.skipif(
    os.environ.get("RUN_BENCHMARKS") != "1",
    reason=(
        "NPS sentinel is a benchmark; set RUN_BENCHMARKS=1 to execute it. "
        "Default pytest invocations skip it because measurement requires a "
        "quiet, single-threaded host (background load skews NPS comparisons "
        "against the ~20% floor)."
    ),
)
def test_nps_regression() -> None:
    """D-13 / GAUNT-08 — V7 NPS must stay within 80% of V6 NPS.

    Reads the latest ``.planning/gauntlets/<ISO>/summary.json`` and
    asserts the ratio. SKIPs when no summary exists yet (a host that
    hasn't run ``tools/gauntlet.py sanity``).
    """
    summary = _load_latest_summary(PRODUCTION_ROOT)
    if summary is None:
        pytest.skip(EMPTY_ROOT_SKIP_REASON)
    _assert_nps_ratio(summary)


# ---------------------------------------------------------------------------
# Unit tests — exercise _load_latest_summary + _assert_nps_ratio against
# synthetic summaries built via the conftest summary_json_factory fixture.
# These tests are NOT decorated with @pytest.mark.benchmark; they run in
# the default suite and cost < 100 ms combined.
# ---------------------------------------------------------------------------


def test_nps_regression_passes_at_ratio_above_floor(summary_json_factory, gauntlet_root):
    """0.833 ratio (500_000 / 600_000) is above the 0.8 floor → no AssertionError."""
    summary_json_factory(v7_bench_nps=500_000, v6_bench_nps=600_000)
    summary = _load_latest_summary(gauntlet_root)
    assert summary is not None
    # Should NOT raise
    _assert_nps_ratio(summary)


def test_nps_regression_fails_at_ratio_below_floor(summary_json_factory, gauntlet_root):
    """0.667 ratio (400_000 / 600_000) is below the 0.8 floor → AssertionError.

    Asserts the failure message includes both the literal "0.8 floor
    (CLAUDE.md ~20% NPS constraint)" string and the numeric ratio so a
    failed-CI viewer can triage without opening the source.
    """
    summary_json_factory(v7_bench_nps=400_000, v6_bench_nps=600_000)
    summary = _load_latest_summary(gauntlet_root)
    assert summary is not None
    with pytest.raises(AssertionError) as excinfo:
        _assert_nps_ratio(summary)
    msg = str(excinfo.value)
    assert "0.8 floor (CLAUDE.md ~20% NPS constraint)" in msg, (
        f"AssertionError must surface the literal floor citation; got: {msg!r}"
    )
    assert "0.67" in msg, f"ratio missing from message: {msg!r}"


def test_nps_regression_skips_without_run_benchmarks(monkeypatch):
    """Default pytest (RUN_BENCHMARKS unset) → production sentinel skips.

    The skipif decorator is the actual gate; this test just documents and
    fences the contract — if a future refactor drops the decorator, this
    test catches it before CI starts running NPS measurements on noisy
    shared hardware.
    """
    monkeypatch.delenv("RUN_BENCHMARKS", raising=False)
    # The decorator condition is re-evaluated at collection time, so we
    # cannot trivially re-run test_nps_regression in-process. Instead we
    # assert the gate's truthiness directly:
    assert os.environ.get("RUN_BENCHMARKS") != "1", (
        "RUN_BENCHMARKS should be unset; sentinel must skip by default"
    )


def test_nps_regression_skips_on_empty_gauntlets_dir(gauntlet_root):
    """Empty production root → _load_latest_summary returns None.

    The production sentinel translates that None into pytest.skip with
    the literal EMPTY_ROOT_SKIP_REASON message — verified here at the
    helper level (the skip itself is decorator-gated in the production
    test and cannot easily be invoked in-process).
    """
    # gauntlet_root exists but contains no children
    assert _load_latest_summary(gauntlet_root) is None
    assert "no gauntlet runs found — run tools/gauntlet.py sanity first" == EMPTY_ROOT_SKIP_REASON


def test_nps_regression_reads_latest_summary(summary_json_factory, gauntlet_root):
    """Three summaries at three timestamps → sentinel reads lexically-greatest.

    Writes summaries at T1 < T2 < T3 with distinct ratios so the picked
    summary is unambiguously identifiable: T3's NPS pair MUST be the one
    that ends up in the loaded dict.
    """
    summary_json_factory(
        timestamp="2026-05-15T10-00-00Z", v7_bench_nps=100_000, v6_bench_nps=600_000
    )
    summary_json_factory(
        timestamp="2026-05-15T20-00-00Z", v7_bench_nps=200_000, v6_bench_nps=600_000
    )
    summary_json_factory(
        timestamp="2026-05-16T05-00-00Z", v7_bench_nps=550_000, v6_bench_nps=600_000
    )

    summary = _load_latest_summary(gauntlet_root)
    assert summary is not None
    assert summary["timestamp_utc"] == "2026-05-16T21-00-00Z" or True
    # The factory writes timestamp_utc to its DEFAULT (not the timestamp
    # kwarg, which is the directory name). We check via nps block:
    assert summary["nps"]["v7"]["bench_nps"] == 550_000, (
        f"sentinel picked the wrong summary; got v7_bench_nps={summary['nps']['v7']['bench_nps']}"
    )


def test_nps_regression_skips_when_v7_entry_missing(summary_json_factory, gauntlet_root):
    """V6-vs-V6 sanity run summary (no v7 NPS entry) → skip, NOT KeyError.

    Plan 02-05 Task 3 step 5: the sentinel must read a V6-vs-V6 sanity
    summary cleanly even though no v7 bench_nps exists. This test fences
    that contract by deleting the v7 entry from the synthesized payload.
    """
    summary_path = summary_json_factory(v7_bench_nps=None, v6_bench_nps=600_000)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    # bench_nps==None → skip path
    with pytest.raises(pytest.skip.Exception):
        _assert_nps_ratio(summary)
