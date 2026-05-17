---
phase: 02-gauntlet-harness-early
plan: 04b
subsystem: gauntlet-harness
tags: [gauntlet, cli, sprt, fastchess, deferred-execution]
requires: [02-01, 02-02, 02-03, 02-04a]
provides:
  - tools.gauntlet.main
  - tools.gauntlet.resolve_engines
  - tools.gauntlet.resolve_opening_book
  - tools.gauntlet.run_bench_nps
  - tools.gauntlet.run_fastchess
  - tools.gauntlet.make_run_dir
  - tools.gauntlet.write_summary
  - tools.gauntlet.D9_MESSAGE
  - tools.gauntlet.FORFEIT_WARNING_TEMPLATE
affects: [02-05]
tech_stack:
  added: []
  patterns:
    - stdlib-cli-orchestrator
    - sha256-trust-gate
    - atomic-rename-download
    - windows-safe-iso-timestamp
    - deterministic-json-write
    - cooperative-keyboard-interrupt-summary
key_files:
  created:
    - tools/gauntlet.py
    - tests/test_gauntlet_io.py
  modified: []
decisions:
  - "D-09 enforced as a parser-level absolute: the run subcommand accepts NO flags, the dispatcher ignores the namespace, no environment variable is read. Adding a future bypass requires deliberate code change (not just a CLI invocation)."
  - "investigation_required is computed inside write_summary (not pushed up to the dispatcher) so any caller — sanity, the KeyboardInterrupt partial-summary path, or future runners — gets the flag for free."
  - "resolve_opening_book follows fetch_fastchess's atomic-rename + checksum-mismatch-unlink discipline exactly; future ZIP handling (the real .fetch_fallback.json has an `unzip_entry` field) is a deliberate non-scope of 02-04b — the resolver writes raw bytes per the plan's literal spec. See Deferred Items."
  - "Run subcommand parser exists in argparse with --help text so users discover the deferral via tooling, not by reading source — surfaces the constraint at exactly the moment a user would try to use it."
  - "Engine binary search list shared with tests/test_v7_bindings.py and tests/test_uci_binaries_v6.py (build/Release, build/RelWithDebInfo, build/Debug, build, engine_dir × {.exe, no-ext}) so a built binary discovered by either test is also discovered by the gauntlet runner."
metrics:
  duration_minutes: 16
  completed: 2026-05-17
  tasks: 2
  files: 2
  tests_added: 14
  loc_added: 1100
requirements: [GAUNT-03, GAUNT-06, GAUNT-07]
---

# Phase 02 Plan 04b: Gauntlet I/O CLI Summary

**One-liner:** Shipped `tools/gauntlet.py` — the user-facing argparse CLI that composes 02-04a's pure helpers with subprocess + filesystem I/O for the V6-vs-V6 sanity match, with the V7-vs-V6 SPRT subcommand hard-deferred to Phase 3 (no bypass flag exists) and an investigation_required flag that fires automatically on any time forfeit or unrecognized PGN termination string.

## What Was Built

### tools/gauntlet.py (704 LOC)

Stdlib-only CLI orchestrator. Public surface:

| Symbol | Purpose |
| ------ | ------- |
| `D9_MESSAGE` (str) | Exact literal printed when `gauntlet run` is invoked. Single source of truth for both the BLOCKER-2 fix and the test gate. |
| `FORFEIT_WARNING_TEMPLATE` (str) | `"⚠ {n} time forfeit(s) — investigate before trusting result"` — emitted to stderr by write_summary when investigation_required fires. |
| `OUTPUT_ROOT`, `VENDORED_BOOK`, `FALLBACK_MANIFEST`, `CACHED_BOOK` (Path) | Path constants the resolver and run-dir maker pin against; monkeypatched in tests. |
| `resolve_engines() -> {"v6": Path, "v7": Path}` | Multi-candidate-dir search for `<engine>_uci{.exe,}`; returns absolute paths (§10 Q6); raises `GauntletError` with the searched list on miss. |
| `resolve_opening_book() -> Path` | Vendored A → return; manifest B → SHA256-gated download with atomic `.part` rename; neither → `GauntletError`. |
| `run_bench_nps(uci_binary) -> int` | `position fen <BENCH_FEN>; go movetime <BENCH_MOVETIME_MS>; quit` then parse last `nps N`. Per RESEARCH §8 Option B. |
| `run_fastchess(cmd, log_path) -> str` | No timeout (SPRT runs can be hours); on non-zero exit writes stderr to `log_path` and raises `GauntletError`; lets `KeyboardInterrupt` propagate. |
| `_git_sha()`, `_fastchess_version(path)` | Best-effort; return `"unknown"` on any failure. |
| `make_run_dir(root)` -> Path | ISO `%Y-%m-%dT%H-%M-%SZ` (Windows-safe — colons replaced); `exist_ok=False`. |
| `write_summary(...)` | Composes all dict blocks per RESEARCH §4 + Plan §must_haves.truths; computes investigation_required; deterministic JSON dump (`indent=2, sort_keys=True, ensure_ascii=False`, trailing newline). |
| `main(argv) -> int` | argparse dispatcher: `run` → deferred (always returns 2), `sanity` → full match. Wraps `GauntletError` → exit 1. |

### tests/test_gauntlet_io.py (14 tests, 396 LOC)

| Test | Surface covered |
| ---- | --------------- |
| `test_run_subcommand_deferred` | RC == 2, exact D9_MESSAGE on stderr (BLOCKER-2). |
| `test_run_subcommand_has_no_i_know_flag` | argparse rejects `--i-know` with SystemExit(2) and "unrecognized"/"invalid" stderr (BLOCKER-2). |
| `test_sanity_subcommand_rejects_zero_games` | `--games 0` → non-zero exit + "must be > 0". |
| `test_sanity_subcommand_rejects_negative_games` | `--games -5` → non-zero exit. |
| `test_write_summary_sets_investigation_required_on_forfeit` | `time_forfeits={"v6":1,"v7":0}` → flag True + "1 time forfeit" stderr. |
| `test_write_summary_no_investigation_when_clean` | All-zero forfeits + clean PGN → flag False + no stderr. |
| `test_write_summary_investigation_propagates_from_pgn_parse` | Forfeits zero BUT `pgn_parse["investigation_required"]=True` → flag True (over-flag path). |
| `test_write_summary_schema_keys` | All 12 result-block keys present; sprt null; concurrency=1; nps keys per engine. |
| `test_make_run_dir_iso_format` | Directory name matches `^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$`. |
| `test_make_run_dir_collision_raises` | Frozen-datetime monkeypatch → second call raises `FileExistsError`. |
| `test_resolve_opening_book_vendored` | Vendored present → returns its path; manifest deliberately broken to prove non-consultation. |
| `test_resolve_opening_book_fallback_manifest` | Fake `urlopen` returns deterministic bytes whose sha256 matches manifest; idempotent re-call does not re-download. |
| `test_resolve_opening_book_missing_both_raises` | `GauntletError` with "no opening book" + ".fetch_fallback.json" mention. |
| `test_resolve_opening_book_checksum_mismatch_raises` | Wrong sha → `GauntletError("checksum mismatch")` + no leftover `.part` or canonical cache. |

`pytest -- --io fixture isolation`: an autouse fixture rebinds `g.VENDORED_BOOK`, `g.FALLBACK_MANIFEST`, and `g.CACHED_BOOK` to `tmp_path` defaults so a stray real-tree `tools/books/` cannot leak into a test.

## Acceptance Criteria — Status

| Criterion | Status |
| --- | --- |
| File exists: tools/gauntlet.py, ≥180 lines | ✓ 704 LOC |
| `python3 tools/gauntlet.py run; echo $?` prints "2" | DEFERRED — pytest/python3 unavailable on this host; logic-traced via D9_MESSAGE constant + dispatcher returning literal 2 |
| `python3 tools/gauntlet.py run 2>&1 ... -F "deferred to Phase 3..."` returns 1 | DEFERRED to build host; grep against source returns 1 (D9_MESSAGE literal present) |
| `grep -cF -- "--i-know" tools/gauntlet.py` returns 0 | ✓ 0 |
| `python3 tools/gauntlet.py sanity --games 0` non-zero with "must be > 0" | DEFERRED — `_sanity_subcommand` first statement is `if args.games <= 0: print("--games must be > 0", ...); return 2` |
| `ensure_fastchess()` count ≥ 1 (non-comment) | ✓ 1 |
| `from tools.gauntlet_core import` count ≥ 1 (non-comment) | ✓ 1 |
| `investigation_required` count ≥ 3 (non-comment) | ✓ 10 |
| `.fetch_fallback.json` count ≥ 1 (non-comment) | ✓ 3 |
| `resolve_opening_book` count ≥ 2 (non-comment) | ✓ 4 |
| All public symbols import | DEFERRED to build host; explicit `from tools.gauntlet import` covers every name in the acceptance list |
| tests/test_gauntlet_io.py exists | ✓ 396 LOC |
| `grep -c "def test_"` ≥ 13 | ✓ 14 |
| `grep -F "deferred to Phase 3 (D-09)"` ≥ 1 | ✓ 1 |
| `grep -c "investigation_required"` ≥ 3 | ✓ 11 |
| `grep -c ".fetch_fallback.json"` ≥ 1 | ✓ 4 |

## D9_MESSAGE — Shipped Literal

```python
D9_MESSAGE: str = "V7-vs-V6 SPRT is deferred to Phase 3 (D-09); harness ships V6-vs-V6 sanity only in Phase 2"
```

Stored as a single-line literal so `grep -F` against the source matches verbatim. The test file asserts both substring containment AND exact `g.D9_MESSAGE in captured.err` so any future paraphrase trips two gates.

## investigation_required Flag — Behavior Matrix

| `time_forfeits` sum | `pgn_parse["investigation_required"]` | Output flag | stderr line |
| --- | --- | --- | --- |
| 0 | False | False | (none) |
| ≥ 1 | False | **True** | `⚠ N time forfeit(s) — investigate before trusting result` |
| 0 | **True** | **True** | `⚠ 0 time forfeit(s) — investigate before trusting result` |
| ≥ 1 | True | True | `⚠ N time forfeit(s) — investigate before trusting result` |

All three non-trivial rows are asserted by a dedicated test. Plan 02-05 Task 3's sanity-checkpoint reads `summary["result"]["investigation_required"]` and refuses to auto-approve when True.

## Opening-Book Resolver — Paths Exercised

| Scenario | Test | Behavior |
| --- | --- | --- |
| Vendored `tools/books/8moves_v3.pgn` present | `test_resolve_opening_book_vendored` | Returns `vendored.resolve()`; manifest never opened. |
| Vendored absent, manifest present, sha matches downloaded bytes | `test_resolve_opening_book_fallback_manifest` | `urlopen` invoked once; atomic write to `cache.part` → rename → return `cache.resolve()`. Second call re-uses cache (no second `urlopen`). |
| Neither vendored nor manifest | `test_resolve_opening_book_missing_both_raises` | `GauntletError("no opening book at ... and no ... — Plan 02-03 may not have run")`. |
| Manifest sha mismatches downloaded bytes | `test_resolve_opening_book_checksum_mismatch_raises` | `GauntletError("checksum mismatch ...")`; `.part` unlinked; canonical cache absent. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] First-draft `--i-know` mention in module docstring tripped the BLOCKER-2 grep.**
* **Found during:** Task 1 structural verification (`grep -cF -- "--i-know" tools/gauntlet.py` returned 1).
* **Issue:** Module docstring said "...no `--i-know` escape hatch..." to document the absence — but the grep gate counts ANY occurrence of the literal string.
* **Fix:** Rephrased to "NO bypass flag of any kind and no environment-variable opt-out — the gate is intentionally absolute per BLOCKER-2." Same meaning, no banned substring.
* **Verification:** `grep -cF -- "--i-know" tools/gauntlet.py` → 0.
* **Files modified:** tools/gauntlet.py (1 docstring edit; pre-commit).

**2. [Rule 1 — Bug] First-draft D9_MESSAGE was split across two source lines via Python's implicit string concatenation, breaking the `grep -F` literal gate.**
* **Found during:** Task 1 structural verification (`grep -cF "deferred to Phase 3 (D-09); harness ships V6-vs-V6 sanity only in Phase 2"` returned 0 instead of ≥1).
* **Issue:** `D9_MESSAGE = ("first half " "second half")` produces a correct runtime string but the source-file grep sees two adjacent lines.
* **Fix:** Inlined the literal on a single source line so the full sentence is one grep-able token.
* **Verification:** literal grep returns 1.
* **Files modified:** tools/gauntlet.py (1 constant edit; pre-commit).

### Authentication Gates

None — no external services touched by either task.

### Deferred Items

**1. `.fetch_fallback.json` `unzip_entry` field is currently ignored.** The real-tree manifest (`tools/books/.fetch_fallback.json`, written by Plan 02-03) points at `8moves_v3.pgn.zip` and has an `unzip_entry: "8moves_v3.pgn"` key; my resolver downloads the URL's raw bytes per the plan's literal spec. That means the resolver will mismatch sha when run against the real manifest URL — but the manifest's sha256 is currently the sentinel `PENDING_HUMAN_CHECKPOINT` anyway, so a real-world `gauntlet sanity` run will fail at the human-checkpoint gate before reaching the unzip surface. Adding ZIP-aware extraction is a deliberate non-scope of 02-04b; tracked here for the Plan 02-03 follow-up that lands the real sha256.

**2. Live pytest / python3 execution.** This Windows host has no Python interpreter (only the Microsoft Store stub). Per the orchestrator's `<host_note>`, all `python3 -m uv run --group dev pytest -q tests/test_gauntlet_io.py` invocations are deferred to a build host — mirrors the Plan 02-04a `.continue-here.md` pattern. Verification proceeded via grep-based acceptance gates (all passing) and manual logic trace.

## Known Stubs

None. Every function in `tools/gauntlet.py` ships a full implementation matching the plan's `<behavior>` block — no `pass` bodies, no `raise NotImplementedError`, no hardcoded mock return values.

## Test Pass Count

**14 unit tests** (≥13 required by the acceptance gate). Combined with Plan 02-04a's 27 tests in `tests/test_gauntlet_core.py`, the gauntlet-runner test suite totals **41 tests** (≥31 required by the cross-plan acceptance criterion).

## Verification Limitation

The runtime gates `python3 tools/gauntlet.py run` and `python3 -m uv run --group dev pytest -q tests/test_gauntlet_io.py -x` could NOT be executed inside this worktree — the only `python3` on PATH is the Microsoft Store stub (`Python was not found; run without arguments to install...`). Static gates that DID pass:

* `wc -l tools/gauntlet.py` → 704 (≥180 ✓)
* `grep -cF -- "--i-know" tools/gauntlet.py` → 0 (BLOCKER-2 ✓)
* `grep -cF "deferred to Phase 3 (D-09); harness ships V6-vs-V6 sanity only in Phase 2" tools/gauntlet.py` → 1 (D9_MESSAGE literal ✓)
* `grep -v '^[[:space:]]*#' tools/gauntlet.py | grep -c "ensure_fastchess()"` → 1 (≥1 ✓)
* `grep -v '^[[:space:]]*#' tools/gauntlet.py | grep -c "from tools.gauntlet_core import"` → 1 (≥1 ✓)
* `grep -v '^[[:space:]]*#' tools/gauntlet.py | grep -c "investigation_required"` → 10 (≥3 ✓)
* `grep -v '^[[:space:]]*#' tools/gauntlet.py | grep -c ".fetch_fallback.json"` → 3 (≥1 ✓)
* `grep -v '^[[:space:]]*#' tools/gauntlet.py | grep -c "resolve_opening_book"` → 4 (≥2 ✓)
* `grep -c "def test_" tests/test_gauntlet_io.py` → 14 (≥13 ✓)
* `grep -cF "deferred to Phase 3 (D-09)" tests/test_gauntlet_io.py` → 1 (≥1 ✓)
* `grep -c "investigation_required" tests/test_gauntlet_io.py` → 11 (≥3 ✓)
* `grep -c ".fetch_fallback.json" tests/test_gauntlet_io.py` → 4 (≥1 ✓)

Recommend Plan 02-05's verifier (or any tooled-host re-run) execute `python3 -m uv run --group dev pytest -q tests/test_gauntlet_io.py tests/test_gauntlet_core.py -x` as the runtime gate before driving a real V6-vs-V6 sanity match.

## Self-Check: PASSED

Files:
* FOUND: tools/gauntlet.py (704 lines)
* FOUND: tests/test_gauntlet_io.py (14 test functions, 396 lines)

Commits:
* FOUND: 1ab0339 — feat(02-04b): add tools/gauntlet.py CLI with D-09 hard deferral
* FOUND: 5850477 — test(02-04b): I/O unit tests for tools/gauntlet
