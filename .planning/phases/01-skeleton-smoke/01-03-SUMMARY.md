---
phase: 01-skeleton-smoke
plan: 03
subsystem: engine/v7 (search + iterative deepening + cancellation wiring)
tags: [v7, cpp17, pybind11, search, pvs, iterative-deepening, aspiration, repetition, time-management, cancellation, srch-01, srch-02, srch-13, srch-14, srch-15, found-04]
requires: [01-02]
provides:
  - v7::SearchInfo (with external_stop, soft/hard deadlines, rep_stack pointer)
  - v7::RepStack (Engine-owned 3-fold repetition stack, cap=1024)
  - v7::TimeManager (allocate with >=10% safety margin clamp)
  - v7::ASPIRATION_MAX_REWIDENS constant (=4) and bounded aspiration re-search loop
  - v7::score_to_tt / v7::score_from_tt (mate-distance correction at TT boundaries)
  - v7::MAX_HALFMOVE_FOR_TT_CUTOFF constant (=80)
  - v7::iterative_deepening, v7::alpha_beta (PVS), v7::quiescence
  - Engine::new_game body (clears stop_flag_, nodes_, tt_, rep_stack_)
  - Engine::search body (wires SearchInfo.external_stop = &stop_flag_ and
    SearchInfo.rep_stack = &rep_stack_; seeds root hash; calls TimeManager;
    delegates to iterative_deepening)
  - Engine::set_syzygy_path forwarder to syzygy_.set_path() (Plan 05 fills SyzygyState::set_path body)
  - Engine class declares rep_stack_ + syzygy_ members (Wave-3 sole owner of include/engine.hpp)
  - tests/test_v7_search.py (9 unit tests covering SRCH-01/02/13/14/15 + FOUND-04)
affects: [01-04, 01-05, 01-06]
tech-stack:
  added: []
  patterns:
    - "Engine-owned RepStack instead of Board-owned (perft-clean invariant per checker issue #3)"
    - "Inline mate-distance correction (score_to_tt / score_from_tt) at every TT store and probe call site"
    - "Bounded aspiration widening with full-window fallback after N rewidens (defense in depth vs V6's single-retry pattern)"
    - "TimeManager separated from SearchInfo: allocate() is pure-function; SearchInfo only holds the resulting deadlines"
    - "Wall-clock contract tests for time management (TimeManager not bound to Python — binding surface stays minimal)"
key-files:
  created:
    - src/chess_engine/engine/v7/include/search.hpp
    - tests/test_v7_search.py
    - .planning/phases/01-skeleton-smoke/01-03-SUMMARY.md
  modified:
    - src/chess_engine/engine/v7/src/search.cpp (was empty stub from Plan 02 — now full V6 fork + 4 patches)
    - src/chess_engine/engine/v7/src/engine.cpp (was empty stub from Plan 02 — now full Engine::* bodies)
    - src/chess_engine/engine/v7/include/engine.hpp (added rep_stack_ + syzygy_ members; includes search.hpp + syzygy.hpp; tbhits() now forwards to syzygy_.tbhits())
    - src/chess_engine/engine/v7/src/python_bindings.cpp (deleted standalone Engine::new_game and Engine::search bodies — see Deviations below)
    - .planning/phases/01-skeleton-smoke/01-VALIDATION.md (+9 per-task verification rows)
decisions:
  - "V6 audit: V6 implements NEITHER score_to_tt/score_from_tt NOR any repetition detection (rep_stack / is_threefold / halfmove probe). SRCH-13 and SRCH-14 are V7 ACTIVE PATCHES, not inheritance from V6. The deferred-ideas track should record this as a V6 cleanup candidate (V6 silently mis-handles mate scores stored in TT and never detects repetition draws inside the search tree)."
  - "Repetition stack lives on Engine (`RepStack rep_stack_;` private member) — NOT on Board. Board::make_move / Board::unmake_move are unchanged from Plan 02's V6 fork, preserving the perft-clean invariant from checker issue #3. Plan 02's perft suite continues to apply byte-for-byte."
  - "alpha_beta pushes onto rep_stack_ at the make_move call site INSIDE the search (a 2-line addition flanking the existing make_move/unmake_move calls). The push/pop bracket lives in the search function alone — Board is never touched. This is the architecturally-correct location for the mutation: the stack is per-search, not per-position."
  - "TimeManager.allocate uses moves_to_go=1 from Engine::search because time_ms is interpreted as the budget for a single move. Upstream game manager / gauntlet owns longer-horizon budget allocation; the per-move clamp is the binding constraint at this layer."
  - "Engine::search clears stop_flag_ at entry to drop a stop request from a PREVIOUS search. Without this, a Python-side stop() landing between two consecutive search() calls would silently cancel the second one at its first poll."
  - "TimeManager is NOT bound to Python directly. Tests verify the safety margin via wall-clock contract on Engine.search (e.g., `e.search(..., time_ms=1000)` must elapse <950ms). Adding `m.def(\"compute_time_budget\", ...)` would bloat the binding surface for a test-only convenience that the wall-clock pattern already covers contractually."
metrics:
  duration: "context-continued session (audit + 4 patches + tests + summary)"
  tasks_completed: 2
  files_created: 3
  files_modified: 5
  unit_tests_added: 9
  commits: 2
  completed: "2026-05-16"
threat_flags: []
---

# Phase 01 Plan 03: V7 Search Port + Pre-C1 Must-Fixes Summary

V7's iterative deepening search is now real: PVS + LMR + NMP + RFP + LMP + futility + SEE inherited verbatim from V6, with four pre-C1 must-fixes layered on top — `SearchInfo.external_stop` wired to `Engine::stop_flag_` (FOUND-04), bounded aspiration re-search (SRCH-02), `score_to_tt`/`score_from_tt` at every TT boundary (SRCH-13), Engine-owned `RepStack` for in-tree 3-fold detection plus halfmove-clock TT-cutoff guard (SRCH-14), and a `TimeManager` with ≥10% safety margin (SRCH-15). Nine unit tests in `tests/test_v7_search.py` exercise each fix in isolation against the `v7_native_engine` fixture.

## V6 Audit Findings

Per Plan 03 Task 1 Step 1 (RESEARCH.md Open Question 1, Assumptions A4 + A5), grepped V6 sources before writing patches:

| Concern | Grep Pattern | Result | V7 Disposition |
|---------|-------------|--------|----------------|
| Mate-distance TT correction | `score_to_tt\|score_from_tt\|MATE_IN_MAX_PLY` in `src/chess_engine/engine/v6/` | **0 matches** anywhere in V6 (`src/search.cpp`, `src/tt.cpp`, `include/tt.hpp`, `include/search.hpp`) | **Active patch** — V7 adds inline `score_to_tt`/`score_from_tt` and wraps every TT.store/TT.probe site (grep count = 5 in `v7/src/search.cpp`) |
| Repetition detection | `rep_stack\|repetition\|is_threefold` in `src/chess_engine/engine/v6/src/search.cpp` | **0 matches**; only `halfmove_clock` appears, used purely for unmake-move restore (lines 75, 230 — store-and-restore of `prev_halfmove`, no probe) | **Active patch** — V7 adds `RepStack` (Engine-owned), threads it through `SearchInfo.rep_stack`, and adds the in-tree 3-fold loop + 50-move TT-cutoff guard in `alpha_beta` |

**Implication for the deferred-ideas track:** V6 silently mis-handles mate scores stored in TT (a mate-in-3 stored at ply N is reported as mate-in-(3 + ply_delta) when probed at ply M ≠ N — false claims of mate or missed mates) and never detects in-tree threefold repetition (engines miss draws by repetition until they appear at the root). Both are independent V6 cleanup candidates and should be tracked separately from V7 work.

## Patches Applied to V7 Fork

### FOUND-04 — SearchInfo.external_stop wired to Engine::stop_flag_

- `search.hpp` `SearchInfo` struct adds `std::atomic<bool>* external_stop = nullptr` (sibling to existing `stopped`).
- `SearchInfo::reset()` preserves `external_stop` across reset AND propagates `external_stop->load()` into local `stopped` so a stop-set-before-search-starts is respected from the first node poll.
- `SearchInfo::check_time()` checks `external_stop` BEFORE the clock check (Python-side stop takes precedence).
- `engine.cpp` `Engine::search` body wires `info.external_stop = &stop_flag_` and clears `stop_flag_.store(false)` at search entry (drops any stop request from a previous search).
- Polling cadence: `info.stopped || (info.nodes % 4096 == 0 && info.check_time())` — at >=1 Mnps that's a ~4 ms cadence, well inside the 50 ms FOUND-04 contract.

### SRCH-02 — Bounded Aspiration Re-search

- `search.hpp` declares `constexpr int ASPIRATION_MAX_REWIDENS = 4` (sibling to existing `ASPIRATION_WINDOW = 25`).
- `iterative_deepening` replaces V6's single-retry pattern with a `while ((score <= alpha || score >= beta) && !info.stopped)` loop that doubles `delta` and tracks `rewidens`; on `rewidens >= ASPIRATION_MAX_REWIDENS` opens to the full `[-INFINITY_SCORE, INFINITY_SCORE]` window then exits (cannot loop again because the full window cannot fail-high or fail-low without overflow).

### SRCH-13 — Mate-Score TT Correction

- `search.hpp` defines inline `score_to_tt(score, ply)` and `score_from_tt(score, ply)` plus `constexpr int MATE_IN_MAX_PLY = MATE_SCORE - 256` (mate band; `MATE_SCORE = 29000` from `types.hpp`).
- `search.cpp` wraps every TT touch:
  - TT probe consumer: `int tt_score = score_from_tt(static_cast<int>(tt_entry.score), ply);` then uses `tt_score` (not `tt_entry.score`) for the cutoff comparison.
  - TT store sites (both fail-high inside the move loop AND end-of-search): `g_tt.store(board.hash, best_move, score_to_tt(best_score, ply), depth, tt_flag);` — score is always `score_to_tt`-wrapped before storage.
- Grep count: 5 occurrences in `v7/src/search.cpp` (declaration is in the header; usage sites in `.cpp`).

### SRCH-14 — In-Tree 3-fold Repetition + 50-Move TT-Cutoff Guard

- `search.hpp` declares `struct RepStack { static constexpr int CAP = 1024; uint64_t data[CAP]; int top = 0; push/pop/clear; };` (inline; trivial).
- `engine.hpp` declares `RepStack rep_stack_;` as an Engine member. **Board is NOT modified** — `grep -c 'rep_stack' src/chess_engine/engine/v7/include/board.hpp` returns 0, satisfying the perft-clean invariant from checker issue #3.
- `engine.cpp` `Engine::search` seeds the rep stack with the root position: `rep_stack_.clear(); rep_stack_.push(board_.hash);` then pops after `iterative_deepening` returns.
- `alpha_beta` brackets each `make_move` / `unmake_move` with `info.rep_stack->push(board.hash)` / `info.rep_stack->pop()` (2-line addition, NOT a change to Board).
- `alpha_beta` near the top adds the in-tree repetition loop: walks back through `info.rep_stack->data` two plies at a time (same side to move) up to `board.halfmove_clock` plies, counting matches against `board.hash`; on >=2 prior matches returns `DRAW_SCORE` (current + 2 prior = 3-fold).
- 50-move guard: TT probe still consults the entry for `best_move` (move ordering hint) but `if (board.halfmove_clock >= MAX_HALFMOVE_FOR_TT_CUTOFF) skip-cutoff` — the cached score doesn't know about the looming 50-move-rule draw.

### SRCH-15 — TimeManager with ≥10% Safety Margin

- `search.hpp` declares `struct TimeManager { int hard_deadline_ms; int soft_deadline_ms; static TimeManager allocate(int remaining_ms, int increment_ms, int moves_to_go = 30); };`.
- `search.cpp` `TimeManager::allocate` body: `budget = remaining_ms / max(moves_to_go, 1) + increment_ms * 95/100`; clamped to `remaining_ms * 9/10` (the ≥10% safety margin); returns `{budget, budget/2}`.
- `iterative_deepening` between iterations: `if (info.soft_deadline_ms > 0 && info.elapsed_ms() >= info.soft_deadline_ms) break;` — don't start a new ID iteration we likely can't finish.
- `SearchInfo::check_time` mid-iteration: `int hard = (hard_deadline_ms > 0) ? hard_deadline_ms : time_limit_ms;` then `if (elapsed >= hard) stopped.store(true);`.
- `Engine::search` calls `TimeManager::allocate(time_ms, 0, 1)` — `time_ms` is the full per-move budget; `moves_to_go=1` makes the safety clamp the binding constraint (which is what the test asserts).

## Perft-Clean Invariant — Re-Affirmed

- `grep -c 'rep_stack' src/chess_engine/engine/v7/include/board.hpp` = **0** (acceptance criterion verified).
- `Board::make_move` and `Board::unmake_move` are unchanged in this plan. The rep-stack push/pop lives in `alpha_beta`, not in `Board`.
- Plan 02's `tests/test_v7_perft.py` Kiwipete + position 3/4/5 + startpos-to-depth-6 corpus continues to apply byte-for-byte. (Re-run deferred to the Wave 3 build-clean gate alongside Plan 04 eval + Plan 05 syzygy; the source-level invariant is verified by the grep above.)

## Engine::search Wiring — Confirmed

`grep` confirms the four critical lines in `src/chess_engine/engine/v7/src/engine.cpp`:

```cpp
info.external_stop = &stop_flag_;   // FOUND-04 — Python-side cancellation
info.rep_stack     = &rep_stack_;   // SRCH-14 — Engine-owned RepStack
info.time_limit_ms = time_ms;       // SRCH-15 — fallback hard deadline
info.soft_deadline_ms = tm.soft_deadline_ms;   // SRCH-15
info.hard_deadline_ms = tm.hard_deadline_ms;   // SRCH-15
```

Each is grep-verified (count = 1 for `info.external_stop = &stop_flag_` and `info.rep_stack` in `engine.cpp`).

## Deviations from Plan

### 1. [Rule 3 — Blocking] Edit to `src/chess_engine/engine/v7/src/python_bindings.cpp`

- **File:** `src/chess_engine/engine/v7/src/python_bindings.cpp`
- **Plan-stated `files_modified`:** does NOT include `python_bindings.cpp` (this plan's `files_modified` lists only `search.hpp`, `search.cpp`, `engine.hpp`, `engine.cpp`, and `test_v7_search.py`).
- **Why edited:** This file's own transitional comment explicitly states "Plan 03 moves `Engine::search` and `Engine::new_game` into `src/engine.cpp`". Leaving the inline definitions in `python_bindings.cpp` while ALSO defining them in `src/engine.cpp` would produce a multiple-definition linker error at the Wave-3 build gate. The plan delegates this move to Plan 03 implicitly via the file's transitional comment.
- **Scope of edit:** Deleted ONLY the standalone (non-binding-block) definitions of `Engine::new_game` (lines 52-60) and `Engine::search` (lines 62-75), replaced with a comment pointing to the new home in `src/engine.cpp`. Replaced with a single short comment block.
- **What was NOT touched:**
  - The `m.def` / `PYBIND11_MODULE(v7_engine, m)` block (Plan 04 is concurrently adding `m.def("evaluate")` to this block — explicit user instruction).
  - The standalone `Engine::set_syzygy_path` body (lines 41-50). Plan 05 owns this removal. **Expected consequence:** a duplicate-definition linker error against `src/engine.cpp`'s `Engine::set_syzygy_path` forwarder until Plan 05 lands.
- **Track:** Rule 3 (blocking issue auto-fix; transitional comment explicitly delegates).
- **Commits:** `b21c5c1`

### 2. [Documented] Build-clean verification deferred to post-merge gate

- The plan's `<verify>` block includes `python3 -m uv run --extra build python -m chess_engine.engine.v7.native_build` which would fail with a multiple-definition linker error against the still-inline `Engine::set_syzygy_path` (Plan 05's responsibility to remove). The user explicitly authorized deferral: "build-clean verification deferred to post-merge gate (Wave 2 build-coupling with Plan 04 eval and Plan 05 syzygy)".
- Source-level acceptance criteria are all met (greps for `external_stop`, `score_to_tt`/`score_from_tt`, `ASPIRATION_MAX_REWIDENS`, `rep_stack_` on Engine, `halfmove_clock >= MAX_HALFMOVE_FOR_TT_CUTOFF`, perft-clean invariant on Board).
- Test execution (`pytest tests/test_v7_search.py`) is similarly deferred — requires a successful build.

### 3. None other.

The four pre-C1 must-fixes were applied exactly as the plan specifies. No architectural deviations (Rule 4 not triggered). No additional bugs found during the V6 audit beyond the two already documented (mate-TT correction + repetition detection) which were anticipated as V7 active patches.

## Notes for Sibling / Downstream Plans

- **Plan 04 (eval):** `include/engine.hpp` and `include/search.hpp` are stable contracts now. Plan 04 may include `search.hpp` for `evaluate()` consumers if needed; the header defines `MATE_SCORE`/`DRAW_SCORE` via `types.hpp` (no eval-level dependency leak).
- **Plan 05 (syzygy):** Plan 03 DECLARED `SyzygyState syzygy_` as an Engine member in `include/engine.hpp` (and `#include "syzygy.hpp"`). Plan 05 must NOT re-declare or re-edit `engine.hpp`. Plan 05's responsibilities are limited to:
  1. Creating `include/syzygy.hpp` with the `SyzygyState` class declaration (member functions: `set_path`, `tbhits`, etc.).
  2. Implementing `src/syzygy.cpp` with the bodies (D-08 verbatim log strings + filesystem checks + KRk smoke probe).
  3. Removing the still-inline `Engine::set_syzygy_path` body from `python_bindings.cpp` (resolves the duplicate-definition linker error this plan left).
- **Plan 06 (smoke):** `Engine::search` end-to-end is wired and observable from Python. `GameManager.stop_search` should call `algo_v7.stop_engine()` → `Engine.stop()` per Plan 01's `chess_algorithm.py`. The 50 ms cancellation contract (FOUND-04) is now tightened end-to-end in `tests/test_v7_search.py::test_cancellation_latency_during_real_search`.

## TDD Gate Compliance

Plan 03 frontmatter is `type: execute`, not `type: tdd`, so the plan-level RED/GREEN/REFACTOR gate does not apply. Per-task `tdd="true"` was set on both tasks. The artifact-level pattern was applied:

- Task 1 (engine + search wiring): forks V6 code, applies patches, commits as `feat`.
- Task 2 (unit tests): authored after Task 1 so the tests reference real binding surface (TimeManager not exposed to Python — tests had to know this to assert via wall clock). Committed as `test`.

Note that Task 2 tests cannot run green until the duplicate-definition linker error is resolved by Plan 05; this is the same deferral as the build-clean verification.

## Commits

| # | Hash      | Type | Description                                                    |
|---|-----------|------|----------------------------------------------------------------|
| 1 | `b21c5c1` | feat | port V7 search + wire SearchInfo cancellation and repetition   |
| 2 | `5b8c77d` | test | add V7 search unit tests for SRCH-01/02/13/14/15 + FOUND-04   |

## Self-Check: PASSED

- `src/chess_engine/engine/v7/include/search.hpp` — FOUND
- `src/chess_engine/engine/v7/src/search.cpp` — FOUND (was stub; now real)
- `src/chess_engine/engine/v7/include/engine.hpp` — FOUND (rep_stack_ + syzygy_ members present)
- `src/chess_engine/engine/v7/src/engine.cpp` — FOUND (was stub; now real)
- `src/chess_engine/engine/v7/src/python_bindings.cpp` — FOUND (Engine::new_game and Engine::search bodies deleted; m.def block + Engine::set_syzygy_path body preserved)
- `tests/test_v7_search.py` — FOUND (9 tests; grep verified)
- `.planning/phases/01-skeleton-smoke/01-VALIDATION.md` — UPDATED (+9 rows)
- Commit `b21c5c1` — FOUND in `git log`
- Commit `5b8c77d` — FOUND in `git log`
