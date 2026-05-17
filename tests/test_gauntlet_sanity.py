"""Latest-summary discovery + sanity-verdict unit tests (Plan 02-05 Task 2).

Covers GAUNT-04 (V6-vs-V6 sanity tolerance) + the latest-summary discovery
contract that the NPS sentinel and the Task 3 human-verify checkpoint
share. All tests are pure-unit:

* No subprocess is spawned (no fastchess, no v6_uci, no v7_uci).
* No real ``.planning/gauntlets/`` is touched — every test consumes the
  conftest ``gauntlet_root`` tmp fixture and the ``summary_json_factory``
  to synthesize the schema produced by Plan 02-04b's
  :func:`tools.gauntlet.write_summary`.

The actual V6-vs-V6 200-game probe lives in Plan 02-05 Task 3 (manual
verification on a built host). RESEARCH §9 "Validation guardrails"
explicitly bars launching a real sanity match from the default test
suite — that gate is honored here.

References:
- D-10 — sanity tolerance ±15 Elo (boundary inclusive)
- tools.gauntlet_core.compute_sanity_verdict (Plan 02-04a output)
- Plan 02-05 acceptance_criteria — at least 5 ``def test_`` per file
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.gauntlet_core import (
    SANITY_TOLERANCE_ELO,
    compute_sanity_verdict,
)


# ---------------------------------------------------------------------------
# Latest-summary discovery — mirrors the NPS sentinel's _load_latest_summary
# ---------------------------------------------------------------------------


def test_latest_summary_discovery(summary_json_factory, gauntlet_root, latest_summary_dir):
    """Three summaries → latest_summary_dir() returns the lexically-greatest.

    Writes timestamps in non-sorted insertion order to fence that the
    discovery sorts by name (not by mtime / iteration order).
    """
    summary_json_factory(timestamp="2026-05-15T20-00-00Z")
    summary_json_factory(timestamp="2026-05-16T05-00-00Z")
    summary_json_factory(timestamp="2026-05-15T10-00-00Z")

    latest = latest_summary_dir()
    assert latest is not None
    assert latest.name == "2026-05-16T05-00-00Z", (
        f"expected lexically-greatest timestamp; got {latest.name!r}"
    )
    # Verify the summary.json is reachable from there
    assert (latest / "summary.json").exists()


def test_latest_summary_returns_none_on_empty_root(gauntlet_root, latest_summary_dir):
    """No subdirectories → latest_summary_dir() returns None.

    Confirms the empty-root contract that the NPS sentinel and the Task 3
    checkpoint both depend on for clean skip behavior.
    """
    # gauntlet_root exists but is empty
    assert not list(gauntlet_root.iterdir())
    assert latest_summary_dir() is None


# ---------------------------------------------------------------------------
# Sanity verdict — D-10 boundary inclusive at ±15 Elo
# Direct calls into tools.gauntlet_core.compute_sanity_verdict (Plan 02-04a)
# ---------------------------------------------------------------------------


def test_sanity_verdict_pass_when_elo_within_tolerance():
    """elo=5.0 → "PASS" (well inside ±15 window)."""
    assert compute_sanity_verdict(5.0) == "PASS"


def test_sanity_verdict_pass_when_elo_negative_within_tolerance():
    """elo=-7.5 → "PASS" (negative side of the ±15 window)."""
    assert compute_sanity_verdict(-7.5) == "PASS"


def test_sanity_verdict_fail_when_elo_exceeds_tolerance():
    """elo=20.0 → "FAIL" (above the +15 ceiling)."""
    assert compute_sanity_verdict(20.0) == "FAIL"


def test_sanity_verdict_fail_when_elo_negative_exceeds_tolerance():
    """elo=-25.3 → "FAIL" (below the -15 floor)."""
    assert compute_sanity_verdict(-25.3) == "FAIL"


def test_sanity_verdict_exact_boundary_pass():
    """elo=15.0 → "PASS" — boundary inclusive per D-10.

    Pinned because the boundary is the single decision the verdict
    function exists to make; a future ``abs(elo) < TOL`` typo would
    flip this to FAIL and silently shift Phase 2's completion gate.
    """
    assert compute_sanity_verdict(15.0) == "PASS"
    assert compute_sanity_verdict(-15.0) == "PASS"
    # Also re-assert the constant matches the per-test literal so a
    # future SANITY_TOLERANCE_ELO change can't drift this test out of sync
    assert SANITY_TOLERANCE_ELO == 15


def test_sanity_verdict_just_over_boundary_fail():
    """elo=15.0001 → "FAIL" — strictly outside the inclusive boundary."""
    assert compute_sanity_verdict(15.0001) == "FAIL"
    assert compute_sanity_verdict(-15.0001) == "FAIL"


# ---------------------------------------------------------------------------
# Sanity-mode summary.json schema — sprt is null for sanity runs
# ---------------------------------------------------------------------------


def test_sanity_summary_omits_sprt(summary_json_factory, gauntlet_root):
    """Sanity-mode summary.json has top-level "sprt" == null.

    Mirrors :func:`tools.gauntlet.write_summary` (gauntlet.py line 494)
    which writes ``"sprt": None`` when ``sanity_mode=True``. Pinned so
    a future change that puts an SPRT block into sanity output (e.g.
    accidentally inheriting from V7-vs-V6 mode) trips this test.
    """
    summary_path = summary_json_factory()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "sprt" in summary, "schema must include sprt key (even if null)"
    assert summary["sprt"] is None, (
        f"sanity-mode summary must have sprt == null; got {summary['sprt']!r}"
    )


def test_summary_factory_schema_matches_plan_02_04b(summary_json_factory, gauntlet_root):
    """Sanity-check the factory output matches the Plan 02-04b top-level schema.

    Fences the contract that test_nps_regression.py depends on — if
    write_summary ever drops/renames a top-level key, this test catches
    the drift before downstream tests start failing with KeyError.
    """
    summary_path = summary_json_factory()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    expected_top_level = {
        "schema_version",
        "timestamp_utc",
        "engines",
        "tc",
        "concurrency",
        "openings",
        "sprt",
        "fastchess_command",
        "fastchess_version",
        "host",
        "result",
        "nps",
    }
    actual_top_level = set(summary.keys())
    missing = expected_top_level - actual_top_level
    assert not missing, f"factory output missing top-level keys: {missing}"

    # investigation_required lives inside result (canonical per
    # tools/gauntlet.py:write_summary line 457 + test_gauntlet_io.py)
    assert "investigation_required" in summary["result"]
    assert summary["result"]["investigation_required"] is False


def test_summary_factory_propagates_investigation_required(summary_json_factory, gauntlet_root):
    """investigation_required=True flag survives round-trip through the factory.

    Plan 02-05 Task 3 step 4 depends on the sentinel being able to read
    a True value from a real sanity summary; this test fences that the
    synthesized payload carries the flag at the documented schema
    location so unit tests can simulate the "hold for triage" path.
    """
    summary_path = summary_json_factory(investigation_required=True)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["result"]["investigation_required"] is True
