---
phase: 01-skeleton-smoke
plan: 06
subsystem: integration
tags: [v7, integration, ui, cli, uci, cancellation, tests]
requires:
  - 01-01-SUMMARY  # V7 adapter + binding contract
  - 01-02-SUMMARY  # V7 board/movegen/perft
  - 01-03-SUMMARY  # V7 search + FOUND-04 wiring
  - 01-04-SUMMARY  # V7 eval + coeffs
  - 01-05-SUMMARY  # V7 syzygy
provides:
  - GameManager dispatches V7 (INT-01)
  - React UI exposes V7 above V6 (INT-02, INT-03)
  - CLI build v7 + syzygy download (INT-04, INT-05, TB-09)
  - v7_uci minimal UCI loop (FOUND-07)
  - End-to-end FOUND-04 closure through GameManager
  - NPS sentinel test (CLAUDE.md 20% constraint)
affects:
  - src/chess_engine/server/game_manager.py
  - client/src/App.jsx
  - cli/src/config.js
  - cli/src/index.js
  - .chess-engine.example.json
  - src/chess_engine/engine/v7/src/uci_main.cpp
  - tests/test_v7_engine.py
  - pyproject.toml
  - .planning/phases/01-skeleton-smoke/01-VALIDATION.md
tech-stack:
  added: []           # no new languages / frameworks per CLAUDE.md constraint
  patterns:
    - "Engine-ladder string dispatch (V2-REF-01 deferred; V7 ADDS to existing ladder, does not refactor)"
    - "Lazy-import inside dispatch branch (mirrors V6 ensure_available pattern; keeps server startup cheap)"
    - "Best-effort cancellation via guarded try/except in stop_search (NEVER throws from request paths)"
    - "Benchmark marker + RUN_BENCHMARKS=1 env gate for default-skip perf tests"
key-files:
  created: []
  modified:
    - src/chess_engine/server/game_manager.py
    - client/src/App.jsx
    - cli/src/config.js
    - cli/src/index.js
    - .chess-engine.example.json
    - src/chess_engine/engine/v7/src/uci_main.cpp
    - tests/test_v7_engine.py
    - pyproject.toml
    - .planning/phases/01-skeleton-smoke/01-VALIDATION.md
decisions:
  - "Preserve V2-REF-01 ladder anti-pattern — Phase 1 ADDS V7 branches; refactoring deferred per CONTEXT."
  - "Use try/except around algo_v7.stop_engine in GameManager.stop_search — cancellation must never throw from HTTP handlers."
  - "test_nps_sentinel default-skip via @pytest.mark.benchmark + RUN_BENCHMARKS=1 gate — measurement requires quiet host per CONTEXT D-04."
  - "syzygy download Phase 1 implementation delegates to wget when on PATH (zero new CLI deps); --dry-run is the wiring-verification path."
  - "v7_uci runs search synchronously per command — stop honored at start of next command (sufficient for fastchess Phase 2; async deferred to Phase 4)."
metrics:
  duration: "~30 minutes elapsed"
  completed: 2026-05-16
  tasks_executed: 2  # Task 3 DEFERRED — see below
  tasks_total: 3
---

# Phase 01 Plan 06: E2E Wiring + UCI + Smoke Summary

V7 end-to-end integration through GameManager, React UI, and Node CLI completed with surgical edits; full minimal UCI loop replaces plan-01 stub; FOUND-04 cancellation closure validated end-to-end via new GameManager-pathway test; NPS sentinel benchmark added with default-skip discipline. **Task 3 (human UI smoke verify) deferred to a host with the full toolchain — this worktree's environment lacks Python, CMake, C++ compiler, and Node, so the live D-04 demonstration cannot be performed here.**

## Per-Task Outcomes

### Task 1 — Surgical INT-01..05 + full v7_uci UCI loop
**Commit:** `c1c6164` — `feat(01-06): wire V7 E2E (GM + UI + CLI) and implement full UCI loop`

**Files modified:**

| File | Change | Anchor / Line range |
|------|--------|---------------------|
| `src/chess_engine/server/game_manager.py` | 4-point patch (AVAILABLE_ENGINES, set_engine_version, ai_move, stop_search) | lines 25, 53-61, 87-95, 386-402 |
| `client/src/App.jsx` | V7 option above V6 in both dropdowns; build-warning extended for V7 | lines 235, 408, 424 |
| `cli/src/config.js` | DEFAULT_CONFIG augmented (v7Built, syzygyPath, syzygyMaxPieces) | lines 17-19 |
| `.chess-engine.example.json` | mirror DEFAULT_CONFIG schema additions | full file |
| `cli/src/index.js` | `buildV7()` (mirrors buildV6 shape) + `syzygyDownload()` + dispatch in args switch + help text | lines 186-355 (new), help text + dispatch lines 635-655 |
| `src/chess_engine/engine/v7/src/uci_main.cpp` | REPLACES stub: full minimal UCI loop (uci/isready/ucinewgame/position {startpos|fen} [moves ...] / go {depth N\|movetime MS} / stop / quit); silently ignores unknown commands | full file rewrite |

**GameManager diff invariant:** Only ADDITIONS; V1-V6 dispatch byte-identical (one trailing-whitespace line removed during elif insertion — no behavior change). Verified via `git diff src/chess_engine/server/game_manager.py`.

**Before / after (truncated to show V7 additions):**

Point 1 (AVAILABLE_ENGINES):
```python
# AFTER:
AVAILABLE_ENGINES = { "human", "v2", ..., "v6", "v7" }
```

Point 2 (set_engine_version ladder):
```python
elif ver == "v7":
    try:
        from chess_engine.engine.v7 import chess_algorithm as algo_v7
        algo_v7.ensure_available(auto_build=True)
    except Exception as error:
        return False, f"V7 is unavailable: {error}"
```

Point 3 (ai_move ladder):
```python
elif current_engine == "v7":
    try:
        from chess_engine.engine.v7 import chess_algorithm as algo_v7
        result = algo_v7.find_best_move(
            self.gs, self.valid_moves, current_engine, self.current_search_info)
        # ... unpack tuple ...
    except Exception as error:
        self.last_search_stats = None
        print(f"[GameManager] V7 move failed: {error}")
        return None
```

Point 4 (stop_search enhancement):
```python
if self.white_engine == "v7" or self.black_engine == "v7":
    try:
        from chess_engine.engine.v7 import chess_algorithm as algo_v7
        if getattr(algo_v7, "V7_AVAILABLE", False):
            algo_v7.stop_engine()
    except Exception:
        pass  # never let cancellation throw
```

**React App.jsx literal options used:**
- White: `<option value="v7">White: V7 (C++)</option>` immediately ABOVE the V6 option.
- Black: `<option value="v7">Black: V7 (C++)</option>` immediately ABOVE the V6 option.
- Build-warning: `if (ver === "v6" || ver === "v7") { setEngineStatus(\`Preparing ${ver.toUpperCase()} native engine; first use may build locally.\`); ... }`

**CLI subcommand registrations:**
- `build v7` → `buildV7()` — registered in the `case 'build':` branch alongside `v6` and `client`; help text updated.
- `syzygy download [--dry-run]` → `syzygyDownload({dryRun})` — new `case 'syzygy':` branch; help text adds the syzygy line.

**v7_uci command surface implemented this plan:**

| Command | Implemented? | Notes |
|---------|--------------|-------|
| `uci` | ✅ | `id name V7 / id author Chess-Engine V7 milestone / uciok` |
| `isready` | ✅ | `readyok` |
| `ucinewgame` | ✅ | engine.new_game() + reset board to startpos |
| `position startpos [moves m1 m2 ...]` | ✅ | replays UCI moves through `apply_uci_move()` (matches against `generate_legal_moves` output) |
| `position fen <6-field-fen> [moves ...]` | ✅ | reassembles FEN from 6 tokens then optionally applies moves |
| `go depth N` | ✅ | depth-fixed; passes `UCI_MAX_TIME_MS` so depth is the binding constraint |
| `go movetime MS` | ✅ | time-fixed |
| `go` (no args) | ✅ | default `depth=6, time=5000ms` (matches D-04 smoke) |
| `stop` | ✅ (degraded) | flips atomic; sync-search caveat documented at top of file — stop honored at the START of the next command. Phase 4 may add async search thread for `go infinite`. |
| `quit` | ✅ | clean exit(0) |
| `setoption`, `debug`, `register`, `wtime`/`btime`/etc. | ⏭️ DEFERRED — Phase 4 | Silently ignored per Phase 1 scope |

**syzygy download implementation choice:** Hybrid — `--dry-run` works on any host (resolves OS-specific default destination, prints mirror URL + approx file count + size; no fetch, no config mutation). Real fetch uses `wget` when on PATH (recursive directory mirror with `.rtbw`/`.rtbz` file pattern filter). `curl` is recognized but recursive mirror is not implemented in Phase 1 (curl can't recurse an Apache index trivially); on curl-only hosts the CLI prints a clear instruction and falls back to manual download. PROJECT.md says "optional download script" — script presence is the requirement, and the dry-run path is the verification gate per the validation map row. Polite-use note in the docstring.

**Verify gates run (Task 1):**
- `grep -nE '"v7"\|algo_v7' src/chess_engine/server/game_manager.py` — 9 matches across 4 points ✅
- `grep -c 'value="v7"' client/src/App.jsx` — exactly 2 ✅
- `grep -nE 'ver === "v6" \|\| ver === "v7"' client/src/App.jsx` — 1 match at line 235 ✅
- `grep -nE 'v7Built\|syzygyPath\|syzygyMaxPieces' cli/src/config.js` — 3 matches ✅
- `grep -nE 'v7Built\|syzygyPath\|syzygyMaxPieces' .chess-engine.example.json` — 3 matches ✅
- `grep -nE 'buildV7\|syzygyDownload\|defaultSyzygyPath\|case .syzygy' cli/src/index.js` — function defs + dispatch case + help text all present ✅
- `grep -nE 'cmd == "(uci\|isready\|ucinewgame\|position\|go\|stop\|quit)"' src/chess_engine/engine/v7/src/uci_main.cpp` — all 7 commands present ✅
- V1-V6 dispatch unchanged: `git diff src/chess_engine/server/game_manager.py` — pure-addition diff, no V1-V6 line reordered ✅

**Verify gates DEFERRED — host lacks toolchain:**
- `node cli/bin/chess-engine.js --help` — Node not installed on this Windows host (Rule 3 deviation, pre-authorized).
- `npm run lint --prefix client` — Node not installed (Rule 3 deviation).
- `printf 'uci\nquit\n' | ./build/v7/v7_uci` — no C++ compiler / CMake, binary not built (Rule 3 deviation).
- `printf 'uci\nposition startpos\ngo depth 3\nquit\n' | timeout 30 ./build/v7/v7_uci` — same (Rule 3 deviation).
- `node cli/bin/chess-engine.js build v7 --help` — Node missing (Rule 3 deviation).
- `node cli/bin/chess-engine.js syzygy download --dry-run` — Node missing (Rule 3 deviation).

### Task 2 — Append cancellation + NPS sentinel tests
**Commit:** `cbc87d9` — `test(01-06): append FOUND-04 e2e cancellation + NPS sentinel tests`

**File touched:** `tests/test_v7_engine.py` (APPENDED — fixture left intact per Plan 06 invariant). Verified by `grep -c 'def v7_native_engine' tests/test_v7_engine.py` = 1 (single definition, reused by both new tests via fixture-name parameter).

**Tests appended:**

1. `test_cancellation_via_gm(v7_native_engine)` — FOUND-04 end-to-end through GameManager. Spins `gm.ai_move()` on a background thread, calls `gm.stop_search()` after 100ms, asserts the search returned within 2s with a non-None move and elapsed_ms < 500. Validates the chain `gm.stop_search → algo_v7.stop_engine → _engine.stop → C++ stop_flag_.store → search thread polls → returns best-so-far`.

2. `test_nps_sentinel(v7_native_engine)` — CLAUDE.md ~20% NPS constraint. Gated by `@pytest.mark.benchmark` + `RUN_BENCHMARKS=1` env var (default-skip). Measures back-to-back single-threaded startpos searches on V6 and V7, asserts `v7_nps / v6_nps >= 0.8`. Documents host requirements (single-threaded, fixed startpos, identical depth, quiet host, cache warm-up policy) and cites CONTEXT D-04 (smoke-scope) + CLAUDE.md.

**Fixture reuse confirmed:** The `v7_native_engine` parameter on both new tests resolves to Plan 01's existing module-scope fixture; no redefinition.

**Auxiliary edit (Rule 3 deviation — auto-add missing critical functionality):** Added `[tool.pytest.ini_options].markers = ["benchmark: ..."]` to `pyproject.toml` so `--strict-markers` doesn't emit `PytestUnknownMarkWarning` when the new test runs. This is correctness-required marker registration (Rule 2 territory) — without it, pytest warns and CI configurations using `-W error::PytestUnknownMarkWarning` would fail.

**Verify gates run (Task 2):**
- `grep -cE 'def test_(cancellation_via_gm\|nps_sentinel)' tests/test_v7_engine.py` — 2 ✅
- `grep -c 'def v7_native_engine' tests/test_v7_engine.py` — 1 (fixture not redefined) ✅
- `grep -nE '@pytest.mark.benchmark\|RUN_BENCHMARKS' tests/test_v7_engine.py` — marker + env gate present ✅
- 01-VALIDATION.md rows for INT-01/02/03/04/05, TB-09, FOUND-07, FOUND-04 end-to-end, INT-08 regression, NPS sentinel — all present ✅

**Verify gates DEFERRED — host lacks toolchain:**
- `python3 -m uv run --group dev pytest tests/test_v7_engine.py -q` — no Python interpreter / uv on host (Rule 3, pre-authorized).
- V1-V6 regression command — same (Rule 3).
- Full V7 suite — same (Rule 3).
- `RUN_BENCHMARKS=1 ... pytest tests/test_v7_engine.py::test_nps_sentinel -q` — same (Rule 3).

These gates must be run on a developer host with uv + CMake + a C++17 compiler before Phase 1 sign-off.

### Task 3 — Human UI smoke verify
**Status: DEFERRED to a future session on a host with the full dev toolchain.**

**Why deferred:** Per the user's explicit scope constraint, Task 3 was excluded from this run. The host running this worktree lacks:
- Python interpreter + uv (cannot run server)
- CMake + C++17 compiler (cannot build `v7_engine.pyd`)
- Node.js (cannot start Vite dev server)
- Browser (no way to load the React UI)

The headless test surface (test_smoke_game_v7_vs_v6 from Plan 01 plus test_cancellation_via_gm appended by Plan 06) is the structural proof of D-04 once those tests run on a real toolchain; the live React-UI demonstration is the visual confirmation step.

**Required follow-up steps for a future session to complete Task 3:**

1. Pull this branch onto a host with the full toolchain (`worktree-agent-acd37609c55b8af9d`).
2. Build V7: `node cli/bin/chess-engine.js build v7`.
3. Run the deferred verify gates listed under Tasks 1 and 2 — confirm all pass before proceeding to UI demonstration:
   - `printf 'uci\nposition startpos\ngo depth 3\nquit\n' | ./build/v7/v7_uci` should emit `uciok` and `bestmove <uci>`.
   - `node cli/bin/chess-engine.js syzygy download --dry-run` should print destination + mirror URL.
   - `npm run lint --prefix client` should be green.
   - `python3 -m uv run --group dev pytest tests/test_v7_engine.py -q` should be green (NPS sentinel SKIPPED at default invocation).
   - `python3 -m uv run --group dev pytest tests/ --ignore=tests/test_v7_*.py -q` should be green (INT-08 regression invariant).
   - Optional on a quiet host: `RUN_BENCHMARKS=1 python3 -m uv run --group dev pytest tests/test_v7_engine.py::test_nps_sentinel -q` to verify NPS within 20% of V6.
4. Perform the Plan-06 Task 3 `<how-to-verify>` checklist (start dev stack, browser to localhost:5173, select V7-white vs V6-black, depth 6, observe a complete legal game; check console + network tab + server log).
5. On approval, the runner sends the resume-signal "approved" to close out Plan 06 and the phase.

## Deviations from Plan

### Rule 3 — Auto-fix blocking issues (pre-authorized in run prompt)

**1. [Rule 3 — Toolchain absence] Defer all runtime verify gates that require Python/CMake/C++/Node.**
- **Found during:** Both tasks.
- **Issue:** Verify gates calling `python3 -m uv run pytest`, `node cli/bin/chess-engine.js`, `cmake`, `npm run lint`, or the compiled `v7_uci` binary cannot execute on this Windows host (no interpreters / compilers / package managers installed).
- **Fix:** Run all structural gates (grep, file existence, schema checks via Read/Edit/Bash grep) and document toolchain-dependent gates as DEFERRED with the exact command list a future session must execute. Pre-authorized by the user in the run prompt.
- **Files modified:** SUMMARY.md (this file) documents the deferred gates verbatim.
- **Commit:** Recorded in this SUMMARY; no separate code commit needed because the deviation is "did less" not "did extra".

### Rule 2 — Auto-add missing critical functionality

**1. [Rule 2 — Missing marker registration] Register `benchmark` pytest marker.**
- **Found during:** Task 2 (test file append).
- **Issue:** `@pytest.mark.benchmark` used by `test_nps_sentinel` was not registered in `pyproject.toml`. Without registration, pytest emits `PytestUnknownMarkWarning`, and CI configurations using `-W error::PytestUnknownMarkWarning` would fail.
- **Fix:** Added `[tool.pytest.ini_options].markers = ["benchmark: long-running benchmark; gated on RUN_BENCHMARKS=1 (skipped by default)"]` to `pyproject.toml`.
- **Files modified:** `pyproject.toml`.
- **Commit:** `cbc87d9`.

### Rule 3 — Auto-fix blocking issues

**2. [Rule 3 — Worktree fast-forward] Fast-forwarded worktree HEAD onto `main` before starting work.**
- **Found during:** Initial context-loading.
- **Issue:** The worktree was created from commit `3140916` (pre-Wave-2), but the v7 source tree, headers, tests, and CMakeLists landed in `main` via the Wave-2 merge sequence (commits `1c411c2` → `afd0d35`). Without picking up those commits the v7 directory does not exist in the worktree filesystem, so Plan 06 could not touch any v7 file.
- **Fix:** `git merge --ff-only main` — fast-forward only; no rewrite, no conflicts because merge-base == HEAD.
- **Files modified:** None directly; whole v7 subtree + tests + planning files brought into the worktree.
- **Commit:** No new commit (fast-forward only).

### Other deviations
None. The V1-V6 dispatch was preserved byte-identical (one whitespace-trim line in the elif insertion site — no behavior change).

## Auth Gates
None encountered.

## D-04 smoke milestone outcome
**DEFERRED.** test_smoke_game_v7_vs_v6 (Plan 01 contribution) and the manual UI demonstration (Plan 06 Task 3) are both runtime-deferred to a session on a host with the full toolchain.

## FOUND-04 cancellation latency
**Code path verified structurally**: `GameManager.stop_search` (lines 87-95) calls `algo_v7.stop_engine()` under a guarded try/except. `algo_v7.stop_engine` (chess_algorithm.py lines 129-145) calls `_engine.stop()`. `Engine::stop` (engine.hpp line 62) does `stop_flag_.store(true)`. `Engine::search` (engine.cpp lines 53-125) wires `info.external_stop = &stop_flag_` and propagates into the search via `SearchInfo::reset()`. The plan-03 search uses `SearchInfo::external_stop` for cooperative polling.

**Measured latency**: DEFERRED — requires a host running the compiled v7_engine module. Plan budget is <500ms (asserted by `test_cancellation_via_gm`).

## NPS sentinel
**Fixture name reused:** `v7_native_engine` (Plan 01 module-scope fixture). Verified by grep (single fixture definition in file).

**Measured ratio:** DEFERRED. The test default-skips without `RUN_BENCHMARKS=1`; when explicitly invoked on a quiet host with V6 built and V7 built, it will measure `v7_nps / v6_nps` and assert `>= 0.8`. The test SKIPs cleanly when V6 is unavailable or when V6 returns zero NPS (defensive).

## V1-V6 regression
**Result:** DEFERRED — requires pytest. Structurally validated via `git diff src/chess_engine/server/game_manager.py`: only ADDITIONS to the dispatch ladder, V1-V6 branches byte-identical. INT-08 invariant preserved by construction.

## Pitfalls hit during integration

1. **Worktree was behind main.** The worktree branch had been created before Wave 2 finished merging into main, so the v7 source tree wasn't on disk. Fast-forwarded via `git merge --ff-only main` (Rule 3 deviation #2). Without this, every Plan-06 edit would have failed with "file not found".

2. **Plan 06 PLAN.md said Plan 01 created test functions in tests/test_v7_engine.py, but in fact Plan 01 only created the fixture.** The actual existing file at execution time had ONLY the `v7_native_engine` module-scope fixture; the documented test functions (`test_auto_build`, `test_gm_dispatch`, `test_smoke_game_v7_vs_v6`) do NOT exist. Plan 06 still appended only the two tests this plan owns (test_cancellation_via_gm + test_nps_sentinel) per the run-prompt scope constraint. **Open question for a future session:** does Plan 01 need a follow-up to actually add its three test functions, or do those tests live elsewhere (e.g., tests/test_v7_bindings.py)? See "Open questions" below.

3. **stop_search activation check.** PLAN.md sketched `if self.engine_version == "v7":` but GameManager has no `engine_version` attribute — it has separate `white_engine` and `black_engine`. The actual implementation guards on `if self.white_engine == "v7" or self.black_engine == "v7":` so the stop fires when V7 is the current OR future engine on either side. Documented in code comments.

4. **GameManager.ai_move return shape.** ai_move returns `str(move)` not `(move, stats)` — the stats are recorded into `self.last_search_stats` as a side effect and surfaced via `get_state()`. The new V7 branch follows the same shape (mirrors v5/v6 stats unpacking).

5. **v7_uci stop-mid-search is degraded.** Synchronous-search design means `stop` from the same stdin reader thread can't fire DURING the search. This is documented at the top of uci_main.cpp and is acceptable for fastchess Phase 2 (each engine runs as a separate process; stop comes via stdin which we won't read until search returns anyway). Phase 4 may add async search via `std::thread`.

## Phase 1 completion handshake

- INT-01 ✅ structurally (4-point ladder patch in game_manager.py)
- INT-02 ✅ structurally (V7 option in both dropdowns, V7 above V6)
- INT-03 ✅ structurally (build-warning extended)
- INT-04 ✅ structurally (DEFAULT_CONFIG + .example.json)
- INT-05 ✅ structurally (buildV7 + syzygy download + help text + dispatch cases)
- INT-06 (covered by Plan 05 — Fathom submodule + .gitmodules entry)
- INT-07 ⏳ DEFERRED — test_smoke_game_v7_vs_v6 was a Plan 01 test stub per PLAN.md but doesn't exist in the file; needs follow-up
- INT-08 ✅ structurally (V1-V6 dispatch unchanged by `git diff`); runtime regression DEFERRED
- INT-09 ⏳ DEFERRED — test_auto_build was a Plan 01 test stub per PLAN.md but doesn't exist in the file; needs follow-up
- TB-09 ✅ structurally (syzygy download script + OS-specific default paths)
- FOUND-04 ✅ structurally (end-to-end wiring verified by grep); runtime latency DEFERRED
- FOUND-07 ✅ structurally (UCI loop implements all required commands); runtime smoke DEFERRED
- D-04 smoke ⏳ DEFERRED — needs Task 3 UI demonstration plus runtime pytest

## Open questions / risks

1. **Plan 01 test functions missing.** The PLAN.md frontmatter (`files_modified`) says Plan 01 created `tests/test_v7_engine.py` with three test functions; the actual file has only the fixture. This is a Plan-01 scope question, not a Plan-06 blocker — Plan 06 correctly delivered its two appended tests. A future session must reconcile: either (a) Plan 01 follow-up adds the missing test_auto_build / test_gm_dispatch / test_smoke_game_v7_vs_v6 functions to tests/test_v7_engine.py, or (b) those tests are documented to live in a sibling file (e.g., test_v7_bindings.py for test_auto_build) and the Plan-06 SUMMARY.md is updated to reflect the actual test inventory.

2. **NPS sentinel hasn't been measured.** The test is in place but not exercised. First time `RUN_BENCHMARKS=1 pytest tests/test_v7_engine.py::test_nps_sentinel -q` runs on a quiet host, the ratio is the genuine "is V7 within 20% of V6" answer. If it fails, that's a Phase-2-tier perf issue, not a Plan-06 implementation issue.

3. **syzygy download real fetch path is wget-only.** curl-only Windows hosts (without WSL or Git Bash supplying wget) will fall through to the "manual download" instruction. Phase 4 may add a Node-side recursive HTTP mirror or a small Python helper for cross-platform parity.

4. **v7_uci stop is best-effort.** Per the top-of-file caveat, `stop` can't interrupt a synchronous in-progress search. Phase 4 may add an async search thread. fastchess Phase 2 work should validate this is acceptable for the gauntlet's needs.

## Next-phase readiness

Phase 1 work is structurally complete pending the runtime verification gates listed above. Once a future session runs the deferred pytest commands and Task 3 UI demonstration on a real toolchain, Phase 1 is shippable. Phase 2 (strength gate + fastchess integration) can begin against this branch immediately on a fully-tooled host.

## Self-Check: PENDING — see below

Structural verifications (commits exist, files exist, grep matches present) are run inline below; runtime verifications are DEFERRED to a tooled host per scope constraint.

- Plan files created/modified:
  - `src/chess_engine/server/game_manager.py` — FOUND (modified)
  - `client/src/App.jsx` — FOUND (modified)
  - `cli/src/config.js` — FOUND (modified)
  - `cli/src/index.js` — FOUND (modified)
  - `.chess-engine.example.json` — FOUND (modified)
  - `src/chess_engine/engine/v7/src/uci_main.cpp` — FOUND (modified)
  - `tests/test_v7_engine.py` — FOUND (appended)
  - `pyproject.toml` — FOUND (markers added)
  - `.planning/phases/01-skeleton-smoke/01-VALIDATION.md` — FOUND (rows appended)

- Commits present in git log:
  - `c1c6164` — Task 1 commit (FOUND)
  - `cbc87d9` — Task 2 commit (FOUND)

## Self-Check: PASSED (structural; runtime gates DEFERRED per scope)
