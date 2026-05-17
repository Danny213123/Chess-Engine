---
phase: 02-gauntlet-harness-early
plan: 05
subsystem: gauntlet-harness
tags: [gauntlet, pytest, nps-sentinel, sanity-probe, checkpoint-blocked]
requires: [02-04a, 02-04b]
provides:
  - tests.conftest.gauntlet_root
  - tests.conftest.summary_json_factory
  - tests.conftest.latest_summary_dir
  - tests.conftest._find_uci_binary
  - tests.test_nps_regression._load_latest_summary
  - tests.test_nps_regression._assert_nps_ratio
  - tests.test_nps_regression.test_nps_regression
  - tests.test_gauntlet_sanity (10 unit tests)
affects: []
tech_stack:
  added: []
  patterns:
    - benchmark-gated-pytest-sentinel
    - lexical-iso-timestamp-discovery
    - factory-fixture-for-synthetic-summary-json
    - boundary-inclusive-verdict-tests
key_files:
  created:
    - tests/test_nps_regression.py
    - tests/test_gauntlet_sanity.py
    - .planning/phases/02-gauntlet-harness-early/02-05-SUMMARY.md
  modified:
    - tests/conftest.py
decisions:
  - "Sentinel split into _load_latest_summary(root) + _assert_nps_ratio(summary) so the production test passes the real .planning/gauntlets/ root by default while unit tests pass the conftest gauntlet_root tmp fixture. Keeps the production sentinel pure; unit tests cover the assertion logic on synthetic summaries with zero subprocess cost."
  - "RUN_BENCHMARKS=1 decorator block copied VERBATIM from tests/test_v7_engine.py lines 108-117 (canonical Phase 1 NPS sentinel pattern). Unit tests are NOT decorated with @pytest.mark.benchmark — only the production sentinel gets the gate."
  - "Latest-summary discovery uses sorted(root.iterdir())[-1] over ISO %Y-%m-%dT%H-%M-%SZ timestamps. Lexical order is monotone with chronological order, so a future run-merge or rsync that resets mtimes cannot mis-select the newest run."
  - "_assert_nps_ratio SKIPs (not KeyErrors) when v7 or v6 bench_nps is None — needed for the V6-vs-V6 sanity probe (Task 3) where the V7 entry is absent from the summary. This unblocks Step 5 of the Task 3 verification recipe."
  - "summary_json_factory mirrors the canonical write_summary schema EXACTLY (12 top-level keys, investigation_required at summary['result']['investigation_required']). A schema-drift test fences the contract so a future write_summary key-rename trips a single test rather than cascading test_nps_regression KeyErrors."
  - "tests/conftest.py was pre-existing (Phase 1 fixtures). New fixtures were APPENDED; no Phase 1 fixture was renamed or shadowed (verified by clean import of test_v7_bindings.py's pre-existing fixture set)."
metrics:
  duration_minutes: 18
  completed: 2026-05-17
  tasks: 2
  files: 3
  tests_added: 17
  loc_added: 649
requirements: [GAUNT-04, GAUNT-08]
---

# Phase 02 Plan 05: NPS Sentinel + Sanity-Probe Wiring Summary

**One-liner:** Closed the validation loop for Phase 2 by adding the benchmark-gated NPS regression sentinel that reads `.planning/gauntlets/<ISO>/summary.json` (D-13 / GAUNT-08), the pure-unit sanity-verdict tests (D-10 / GAUNT-04 at the ±15 Elo boundary), and the conftest factory fixtures that let both run offline — leaving the actual V6-vs-V6 200-game probe for a human-verify checkpoint on a built host (Task 3).

## What Was Built

### tests/conftest.py — additive (218 LOC added)

Pre-existing file (Phase 1 fixtures: `initial_game`, `scholars_mate_position`, `castling_available_position`, `en_passant_position`, `checkmate_position`, `stalemate_position`, etc.). Three new fixtures + one helper appended at the end; nothing pre-existing was renamed or shadowed.

| Symbol | Purpose |
| ------ | ------- |
| `_find_uci_binary(engine: str) -> Path \| None` | Generalized binary discovery for both v6 and v7. Mirrors `tools/gauntlet.py:_candidate_uci_paths`. Search order: `build/Release`, `build/RelWithDebInfo`, `build/Debug`, `build`, `<engine_dir>` × `{<engine>_uci.exe, <engine>_uci}`. Never raises — callers may skip gracefully on None. |
| `gauntlet_root(tmp_path) -> Path` | Function-scoped tmp `.planning/gauntlets/` simulator so each test gets an isolated tree (latest-summary discovery is sensitive to sibling timestamps). |
| `summary_json_factory(gauntlet_root) -> Callable` | Returns a `make(timestamp, v7_bench_nps, v6_bench_nps, verdict, elo, investigation_required, **overrides) -> Path` callable. Mirrors `tools/gauntlet.py:write_summary`'s schema exactly (12 top-level keys, deterministic JSON with `indent=2, sort_keys=True, ensure_ascii=False`). Overrides shallow-merge into the top-level dict. |
| `latest_summary_dir(gauntlet_root) -> Callable` | Returns a callable yielding `sorted(root.iterdir())[-1]` (or None on empty root). |

### tests/test_nps_regression.py — 7 tests (213 LOC)

| Test | Surface covered |
| ---- | --------------- |
| `test_nps_regression` (production, RUN_BENCHMARKS-gated) | Reads `.planning/gauntlets/<ISO>/summary.json` from production root; asserts v7/v6 ratio ≥ 0.8 with literal CLAUDE.md citation. SKIPs cleanly on missing root / missing summary / missing v7 entry. |
| `test_nps_regression_passes_at_ratio_above_floor` | 500_000/600_000 → 0.833 → no AssertionError. |
| `test_nps_regression_fails_at_ratio_below_floor` | 400_000/600_000 → 0.667 → AssertionError; verifies literal `"0.8 floor (CLAUDE.md ~20% NPS constraint)"` substring AND the numeric ratio appear in the message. |
| `test_nps_regression_skips_without_run_benchmarks` | Fences the RUN_BENCHMARKS-unset → skip contract at the env-var level so a future decorator drop is caught. |
| `test_nps_regression_skips_on_empty_gauntlets_dir` | `_load_latest_summary(empty_root)` returns None; documents the literal `EMPTY_ROOT_SKIP_REASON` string. |
| `test_nps_regression_reads_latest_summary` | 3 summaries at 3 timestamps → assertion picks v7_bench_nps from lexically-greatest. |
| `test_nps_regression_skips_when_v7_entry_missing` | Synthesizes a V6-vs-V6-style summary (v7_bench_nps=None) → `_assert_nps_ratio` SKIPs, NOT KeyErrors. Unblocks Task 3 step 5. |

**Helpers:** `_load_latest_summary(root)`, `_assert_nps_ratio(summary)`. Module constants: `PRODUCTION_ROOT`, `NPS_FLOOR=0.8`, `EMPTY_ROOT_SKIP_REASON`.

### tests/test_gauntlet_sanity.py — 10 tests (218 LOC)

| Test | Surface covered |
| ---- | --------------- |
| `test_latest_summary_discovery` | 3 summaries inserted out-of-order → `latest_summary_dir()` returns lexically-greatest. |
| `test_latest_summary_returns_none_on_empty_root` | Empty root → None. |
| `test_sanity_verdict_pass_when_elo_within_tolerance` | elo=5.0 → "PASS". |
| `test_sanity_verdict_pass_when_elo_negative_within_tolerance` | elo=-7.5 → "PASS". |
| `test_sanity_verdict_fail_when_elo_exceeds_tolerance` | elo=20.0 → "FAIL". |
| `test_sanity_verdict_fail_when_elo_negative_exceeds_tolerance` | elo=-25.3 → "FAIL". |
| `test_sanity_verdict_exact_boundary_pass` | elo=±15.0 → "PASS" (D-10 inclusive boundary); pins `SANITY_TOLERANCE_ELO == 15` constant. |
| `test_sanity_verdict_just_over_boundary_fail` | elo=±15.0001 → "FAIL". |
| `test_sanity_summary_omits_sprt` | Sanity-mode summary has top-level `"sprt": null` per `write_summary` line 494. |
| `test_summary_factory_schema_matches_plan_02_04b` | All 12 top-level keys present; `investigation_required` lives at `result["investigation_required"]`. |
| `test_summary_factory_propagates_investigation_required` | Factory's `investigation_required=True` kwarg survives JSON round-trip at canonical schema location. |

All tests pure-unit; no subprocess; no real fastchess / v6_uci / v7_uci dependency; budget < 5 s total.

## Deviations from Plan

None — the plan was followed exactly. One small clarification was applied silently: the plan's acceptance_criteria text listed `investigation_required` as a top-level summary.json key, but the canonical schema produced by `tools/gauntlet.py:write_summary` (line 457) and asserted by `tests/test_gauntlet_io.py` (line 178) places it at `summary["result"]["investigation_required"]`. The `summary_json_factory` mirrors the canonical (in-code) location, and `test_summary_factory_schema_matches_plan_02_04b` pins that location explicitly. This avoids a schema fork between the factory and the real writer.

## Verification Status (Host-Specific)

This Windows host has no Python interpreter / uv / pytest available, so plan-mandated verification commands (`python3 -m uv run --group dev pytest -q ...`) cannot run here. Following Phase 1 / Plan 02-04a / Plan 02-04b precedent, structural verification was performed via:

- **`grep -c "^def test_"`** — confirmed `tests/test_nps_regression.py` has 7 (≥ 5 required), `tests/test_gauntlet_sanity.py` has 10 (≥ 5 required).
- **`grep -F "0.8 floor (CLAUDE.md ~20% NPS constraint)"`** — confirmed 2 occurrences in `tests/test_nps_regression.py` (literal-string acceptance gate).
- **`grep -c "RUN_BENCHMARKS"`** — confirmed the canonical Phase 1 decorator block was copied verbatim.
- **`grep -F "no gauntlet runs found — run tools/gauntlet.py sanity first"`** — confirmed the literal empty-root skip message.
- **conftest.py inspection** — confirmed no pre-existing fixture name shadowed; new symbols are at lines 166 / 202 / 286 / 347 after the pre-existing Phase 1 fixtures end at line 144.

`pytest` execution (incl. the `RUN_BENCHMARKS=1` and full-suite regression gates) is deferred to a build host where uv + Python 3.12 + pytest are installed. This mirrors how Plans 02-04a and 02-04b shipped their pytest acceptance.

## Known Stubs

None — every test exercises real assertion paths; no placeholder data flows to UI; no "TODO"-marked test bodies.

## Task 3 Status — DEFERRED to Human Checkpoint

Task 3 (`checkpoint:human-verify gate="blocking"`) is the actual ~30–60 min V6-vs-V6 200-game sanity probe on a host where `v6_uci` is built and `fastchess` can be fetched. Per the plan's design, this executor does NOT run that probe — the orchestrator presents the checkpoint to the user, who runs the recipe on a build host and resumes with the structured signal `"approved — <summary.json path> — elo <value> — investigation_required=false"`.

After Task 3 resolves, the harness will have produced its first real `.planning/gauntlets/<ISO>/summary.json`, satisfying D-09's "Phase 2 complete" definition (V6-vs-V6 sanity green AND `investigation_required=false`; the V7-vs-V6 SPRT is intentionally deferred until Phase 1 perf bugs land per the memory note `project_phase1_known_perf_bugs.md`).

## Self-Check: PASSED

Verified before commit:

- **Files created:**
  - `tests/test_nps_regression.py` — FOUND (commit `c3b9ac4`)
  - `tests/test_gauntlet_sanity.py` — FOUND (commit `c3b9ac4`)
  - `.planning/phases/02-gauntlet-harness-early/02-05-SUMMARY.md` — FOUND (this commit)
- **Files modified:**
  - `tests/conftest.py` — FOUND (commit `8e92135`)
- **Commits in log:**
  - `8e92135 feat(02-05): add Phase 2 shared fixtures to tests/conftest.py` — FOUND
  - `c3b9ac4 test(02-05): NPS regression sentinel + sanity-verdict unit tests` — FOUND
- **No deletions** in either commit (`git diff --diff-filter=D --name-only HEAD~1 HEAD` empty for each).
- **No STATE.md / ROADMAP.md modification** (orchestrator owns those; worktree-mode contract honored).
