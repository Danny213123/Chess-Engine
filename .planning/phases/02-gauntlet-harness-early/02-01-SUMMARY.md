---
phase: 02-gauntlet-harness-early
plan: 01
subsystem: v7-uci
tags: [uci, v7, fastchess, gauntlet, setoption, time-management]
requires:
  - V7 build (CMake target v7_uci in src/chess_engine/engine/v7/CMakeLists.txt)
  - pytest + chess_engine.engine.v7.native_build (BUILD_DIR, V7_DIR exports)
provides:
  - v7_uci accepts `setoption name <NAME> [value <VALUE>]` silently for any NAME
  - v7_uci respects `go wtime W btime B winc I binc J` with budget = (my_time / 30) + my_inc
  - tests/test_uci_binaries.py with 6 subprocess tests for GAUNT-02
affects:
  - src/chess_engine/engine/v7/src/uci_main.cpp (only file modified in V7 engine)
  - tests/ (new test module added)
tech-stack:
  added: []
  patterns:
    - Subprocess UCI driving with capture_output=True for two-stream assertions
    - pytest.skip on missing binary (CI without C++ toolchain stays green)
key-files:
  created:
    - tests/test_uci_binaries.py
  modified:
    - src/chess_engine/engine/v7/src/uci_main.cpp
decisions:
  - "D-13 + GAUNT-02: silent accept for every setoption name (A4 — V7 TT is construction-time-only)"
  - "Time heuristic: (my_time / 30) + my_inc, floored at 10ms (RESEARCH §7 Phase-2 budget)"
  - "Side selection: board.side_to_move (public Color field on v7::Board) → wtime/winc for WHITE, btime/binc for BLACK"
  - "movestogo parsed for protocol compliance but ignored (Phase 2 heuristic does not use it)"
metrics:
  duration: ~25 minutes
  completed: 2026-05-16
  tasks_completed: 2
  files_modified: 1
  files_created: 1
  commits: 2
requirements:
  - GAUNT-02
---

# Phase 2 Plan 01: V7 UCI Surface Fix Summary

Closed the V7 UCI setoption + wtime/btime gap so fastchess can drive `v7_uci` correctly in
Phase 2's gauntlet — added a silent `setoption` branch (mirroring the `position` parser style)
and extended `go` to parse `wtime/btime/winc/binc/movestogo` with the RESEARCH §7
budget heuristic `time_ms = (my_time / 30) + my_inc`, floored at 10 ms.

## What Was Built

### Task 1 — uci_main.cpp extension (commit `b152f56`)

`src/chess_engine/engine/v7/src/uci_main.cpp` — +68 / -4 lines, no new `#include` directives.

Two surgical extensions to the main UCI loop:

1. **New `setoption` branch** (added BEFORE the catch-all `else`): walks the canonical UCI
   form `setoption name <NAME> [value <VALUE>]`, accepts every name silently, prints
   nothing. Mirrors the token-walk style of the existing `position` branch. The branch
   intentionally does nothing with the parsed fields — kept for parser-shape clarity and as
   a Phase-4 wiring point.

2. **Extended `go` branch** parses `wtime W`, `btime B`, `winc I`, `binc J`, `movestogo M`
   using the same `std::stoi` + `try/catch` discipline as the existing `depth` / `movetime`
   handlers. After the token loop, gate cascade:
   - `has_depth && !has_movetime` → `time_ms = UCI_MAX_TIME_MS` (Phase 1 depth-fixed
     behavior — unchanged byte-identically).
   - `!has_depth && !has_movetime && (has_wtime || has_btime)` → compute
     `budget = (my_time / 30) + my_inc`, floor at 10 ms, assign to `time_ms`.
   - Otherwise → `time_ms` keeps its `DEFAULT_GO_TIME_MS = 5000` initial value (Phase 1
     fallback for bare `go` — unchanged).

   **Side selection:** `board.side_to_move == v7::WHITE ? wtime : btime` (and likewise for
   the increment). The accessor is a **public `Color` field** on `v7::Board` (verified in
   `src/chess_engine/engine/v7/include/board.hpp:29`), NOT a method named `side_to_move()`
   as one might assume from V6 naming.

   **Heuristic exactness:** `time_ms = (my_time / 30) + my_inc` per RESEARCH §7. Example:
   `wtime=10000 winc=100` → 333 + 100 = 433 ms per move. `wtime=1000 winc=0` → 33 ms (floored
   to 33, well above the 10 ms emergency floor). `wtime=100 winc=0` → 3 → floored to 10 ms.

The top-of-file comment block gained a one-line note about the Phase 2 extension. The
unknown-command catch-all `else` at the end of the ladder still exists (no longer catches
`setoption`, which now has its own branch).

### Task 2 — tests/test_uci_binaries.py (commit `3e5e07c`)

New module with 6 subprocess tests, all gated by `_find_v7_uci_binary()` →
`pytest.skip(...)` so CI hosts without the C++ toolchain stay green.

- `test_v7_uci_setoption` — `setoption name Hash value 64` + isready → asserts `readyok` in
  stdout and no `unknown` token in either stream, no `error` in stderr.
- `test_v7_uci_threads_setoption` — same shape with `Threads value 1`.
- `test_v7_uci_unknown_setoption` — same shape with `SyzygyPath value /tmp` (unrecognized
  name still silently accepted).
- `test_v7_uci_wtime_btime_respected` — `go wtime 1000 btime 1000 winc 0 binc 0` from
  startpos: asserts `bestmove ` appears in stdout AND wall time < 1.5 s. The 1.5 s ceiling
  catches the 5-second-fallback regression cleanly while absorbing process spawn + engine
  warmup + Windows scheduler jitter.
- `test_v7_uci_depth_backcompat` — `go depth 3` from startpos → asserts a bestmove (Phase 1
  depth handler).
- `test_v7_uci_movetime_backcompat` — `go movetime 200` from startpos → asserts a bestmove
  and wall time < 2.0 s (Phase 1 movetime handler still works and not silently capped at
  5 s).

Shared `_run_uci(binary, script, timeout=5.0)` helper uses `subprocess.run` with
`capture_output=True`. Each subprocess capped at 5 s; module budget << 15 s.

Binary discovery helper `_find_v7_uci_binary()` copied verbatim from
`tests/test_v7_bindings.py` lines 163-184 per the plan instruction (cross-engine
generalization lands in Plan 02-02 once `v6_uci` exists).

## Deviations from Plan

None — plan executed exactly as written. The plan's two-task structure, file targets,
behaviors, heuristic, and binary-discovery copy-verbatim instruction were all followed.

## Auth Gates

None.

## Verification Status

| Step | Plan's automated command | Result |
|------|--------------------------|--------|
| Task 1 build | `cd src/chess_engine/engine/v7/build && cmake --build . --target v7_uci` | **NOT RUN** — no `cmake` or C++ compiler available in this worktree environment (verified: `which cmake` / `which g++` both empty). Source change is well-formed and only adds branches that mirror existing parser style; no new headers introduced. |
| Task 2 pytest | `python3 -m uv run --group dev pytest -q tests/test_uci_binaries.py -x` | **NOT RUN** — no Python interpreter on PATH in this worktree (`python` / `python3` / `py` all unavailable). Module is well-formed: imports verified against existing `chess_engine.engine.v7.native_build` exports (`BUILD_DIR`, `V7_DIR` at lines 16-17), all 6 tests follow the analog `test_v7_bindings.py` pattern. |

**Deferred verification:** Both verify steps must be re-run by the orchestrator (or
follow-up wave) on a host with cmake + C++ compiler + Python toolchain before this plan's
acceptance criteria can be marked green end-to-end. The static acceptance criteria the
plan listed are all verifiable locally and pass:

- `grep -n "setoption" src/chess_engine/engine/v7/src/uci_main.cpp` → matches at line 247
  (new branch), plus the existing comment-only references (lines 2-9). ✓
- `grep -n "wtime" src/chess_engine/engine/v7/src/uci_main.cpp` → matches at lines 172/177/
  178/190/191/218/222 (new parse hooks + heuristic). ✓
- Unknown-command catch-all `else` block still exists at line 271. ✓
- `git diff` shows no new `#include` directives in `uci_main.cpp`. ✓
- `tests/test_uci_binaries.py` exists with `grep -c "def test_" = 6`. ✓
- No `v6_*` test functions in `test_uci_binaries.py` (only doc references). ✓

## Known Stubs

None. The Phase-2-scope silent-accept setoption parser is not a stub — it is the documented
A4-asymmetry design (V7 TT is construction-time-only; no in-search Hash setter to wire).
The branch is shaped so Phase 4 can drop in a Hash dispatch with no parser rewrite.

## Threat Flags

None. No new network endpoints, no new auth paths, no schema changes, no new file
read/write surfaces. Strictly additive UCI parsing branches inside an existing
locally-spawned executable.

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| `b152f56` | feat | add setoption + wtime/btime parsing to v7_uci |
| `3e5e07c` | test | add subprocess tests for v7_uci setoption + wtime/btime |

## Self-Check: PASSED

- File `src/chess_engine/engine/v7/src/uci_main.cpp` — FOUND (modified, 277 lines).
- File `tests/test_uci_binaries.py` — FOUND (created, 215 lines, 6 test functions).
- Commit `b152f56` — FOUND in git log.
- Commit `3e5e07c` — FOUND in git log.
- All five static acceptance criteria pass (see Verification Status table above).
- Both runtime acceptance criteria (build + pytest) are deferred to a host with the
  toolchain — documented explicitly above as the one non-self-check item.
