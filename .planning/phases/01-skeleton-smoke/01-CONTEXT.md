# Phase 1: Skeleton + Smoke - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

V7 native C++17 pybind11 module exists at `src/chess_engine/engine/v7/` (forked from V6), builds cross-platform via CMake `FetchContent` of pybind11 v2.12.0, achieves perft parity vs V6 to depth 6, runs a sequential PVS search with hardened iterative deepening (mate-score TT correctness, repetition detection, time management), has every eval term (EVAL-01..11) structurally present in `coeffs.cpp` (generated from `coeffs.json`) so Phase 4 Texel can tune them, integrates Fathom (jdart1) as a git submodule for Syzygy probing, releases the GIL at the binding boundary, honors the `SearchInfo` cancellation token (closing V6's gap), and plays a complete legal game vs V6 end-to-end through the existing React UI (single-game smoke milestone).

Phase 1 ends with the C1 smoke milestone passing: a single fixed-depth game with V7-as-white vs V6 finishes legally with no crashes, dispatched from the unchanged `GameManager` ladder + React dropdown.

</domain>

<decisions>
## Implementation Decisions

### Initial Eval Coefficients
- **D-01:** V7's eval coefficients in `coeffs.json` initialize from **public Pesto/Stockfish-baseline values**, not lifted from V6. Pesto provides PSTs and tapered-eval material; for terms beyond PSTs (king-safety attack table, mobility tables, pawn-structure terms, threats, bishop pair, tempo) use documented public starting values where they exist (Pesto-derived where available) or modest hand-set values clearly marked `# initial; will be tuned Phase 4` in `coeffs.json`.
- **D-02 [informational]:** This makes V7 the "neutral seed" candidate in Phase 4's TUNE-08 multi-seed tuning. The V6-equivalent seed (also referenced in TUNE-08) is left for Phase 4 to construct separately if desired — it is NOT V7's Phase 1 starting state.
- **D-03 [informational]:** Smoke games in Phase 1 may look weaker than V6 because Pesto-baseline ≠ tuned. That is expected and acceptable — the Phase 1 milestone is *legal play*, not *strong play*. Strength is measured starting Phase 2 (gauntlet harness) and validated in Phase 5.

### Smoke Milestone Scope
- **D-04:** Phase 1's C1 smoke milestone is **a single game, V7 as white, fixed depth, vs V6**. Must finish legally with no crashes, illegal moves, or unhandled exceptions; cancellation must work mid-search (FOUND-04). Suggested depth: same as V6's default (depth 6).
- **D-05 [informational]:** V7-as-black, time-management exercise (SRCH-15 in real games), and back-to-back game stability are **not** Phase 1 acceptance criteria — Phase 2's gauntlet harness is the first place these are validated.
- **D-06:** SRCH-15 (time management) still needs **unit tests** in Phase 1 (must not bust at the configured TC, must keep ≥10% safety margin). The unit tests live; the end-to-end exercise is Phase 2.

### Syzygy Missing-Path Behavior (init-time only)
- **D-07:** **Always log to stderr, never fail at engine init**, regardless of why tablebases are unavailable. The engine must always start.
- **D-08:** The init-time log line must be specific and one-line:
  - `syzygyPath` unset → `[v7] syzygy: no path configured; tbhits will be 0`
  - Path set, directory missing → `[v7] syzygy: path not found: <path>; tbhits will be 0`
  - Path set, directory empty / no `.rtbw` files → `[v7] syzygy: no tablebase files at <path>; tbhits will be 0`
  - Path set, files present, TB-10 KRk smoke probe fails → `[v7] syzygy: smoke probe failed (corrupt or wrong format) at <path>; tbhits will be 0`
- **D-09:** TB-06 (in-search probe failures must NOT silently become draws) is an orthogonal **in-search** invariant and is unaffected by init behavior. In-search probe failures still hard-error or are detected and reported — they never quietly return WDL=DRAW.

### `coeffs.cpp` Codegen Mechanics
- **D-10:** Codegen script lives at **`tools/gen_coeffs.py`** (Python — already a build-time dep via pybind11, so no extra cost).
- **D-11:** Invoked via a **CMake custom command** in V7's `CMakeLists.txt` that depends on `coeffs.json`. If `coeffs.json` is newer than `coeffs.cpp` (or `coeffs.cpp` is missing), regenerate before compiling. No manual step required.
- **D-12:** **`coeffs.cpp` is generated, not committed.** It is added to `.gitignore` for the V7 directory. `coeffs.json` is the single source of truth. CI builds invoke the codegen automatically as part of the build.
- **D-13:** Codegen output is deterministic and stable (sorted keys, fixed formatting) so accidental committed copies don't drift across developer machines if a contributor mis-stages it.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project / Milestone Scope
- `.planning/PROJECT.md` — V7 milestone scope, core value, constraints, and out-of-scope list (defines what V7 is and is not)
- `.planning/REQUIREMENTS.md` §Foundation, §Search (SRCH-01/02/13/14/15), §Eval, §Tablebases, §Integration — the 42 requirements scoped to Phase 1
- `.planning/ROADMAP.md` §Phase 1 — phase goal, success criteria, parallelizable subsystems (B1∥B2∥B3 after A1+A2)

### Research Bundle
- `.planning/research/SUMMARY.md` — synthesized recommendations across stack/features/architecture/pitfalls
- `.planning/research/STACK.md` — Fathom (jdart1) MIT, fastchess MIT, GediminasMasaitis/texel-tuner MIT, Zurichess dataset choice rationale
- `.planning/research/ARCHITECTURE.md` — proposed V7 file layout mirroring V6, build-order groups (A1→A2→B1∥B2∥B3→C1), critical V6 SearchInfo bug to fix in V7
- `.planning/research/PITFALLS.md` — 44 pitfalls; Phase-1-relevant: #1 (mate-score TT off-by-one), #7 (repetition not in tree), #11 (GIL not released — single most common pybind11 mistake), #33 (time management busts TC), #36 (lockless TT precondition for SMP — Phase 3+ only, NOT Phase 1)

### Codebase Maps (existing patterns V7 must respect)
- `.planning/codebase/ARCHITECTURE.md` — `GameManager` engine ladder dispatch contract (V7 plugs in via 4-line edit, INT-01); `find_best_move(game_state, valid_moves, engine, search_info)` adapter contract; `SearchInfo` cooperative cancellation
- `.planning/codebase/STACK.md` — Python 3.12, CMake ≥3.15, pybind11 v2.12.0 (matches V6)
- `.planning/codebase/CONVENTIONS.md` — Python naming, no formatter/linter configured, ESLint flat config in `client/`, `print()` as logging (acceptable for V7 stderr probe-init notices)
- `.planning/codebase/STRUCTURE.md` — package layout under `src/chess_engine/`, tests under `tests/`, CLI under `cli/`, frontend under `client/`
- `.planning/codebase/TESTING.md` — pytest conventions for `tests/test_v7_engine.py` (INT-07)
- `.planning/codebase/INTEGRATIONS.md` — `cli/src/config.js` defaults, `cli/src/index.js` subcommand pattern (INT-04, INT-05)

### V6 Reference Implementation (V7 forks this)
- `src/chess_engine/engine/v6/CMakeLists.txt` — V7's `CMakeLists.txt` mirrors this; FOUND-02
- `src/chess_engine/engine/v6/native_build.py` — V7's `native_build.py` mirrors this; CLI `chess-engine build v7` invokes it (INT-05)
- `src/chess_engine/engine/v6/__init__.py` — V7's loader pattern + `find_best_move` adapter
- `src/chess_engine/engine/v6/src/python_bindings.cpp` — **READ FIRST** — contains the bug FOUND-04 must fix in V7 (Python-side `SearchInfo` argument ignored). V7's bindings.cpp must wire it through and wrap search in `py::call_guard<py::gil_scoped_release>()` (FOUND-05).
- `src/chess_engine/engine/v6/src/*.cpp` and `include/*.hpp` — board, movegen, magic, zobrist, TT, eval, search to be ported with perft parity (FOUND-06)
- `src/chess_engine/server/game_manager.py` — `ai_move` ladder; INT-01 4-line edit lands here
- `src/chess_engine/core/search_info.py` — cancellation contract V7 must honor
- `client/src/App.jsx` — engine selectors (INT-02) + "build may take a while" warning (INT-03)
- `cli/src/config.js`, `cli/src/index.js` — INT-04, INT-05 entry points

### External (vendored / fetched)
- Fathom (jdart1, MIT) — Syzygy probing; will be added as git submodule under `src/chess_engine/engine/v7/extern/fathom/` (TB-01)
- pybind11 v2.12.0 — fetched via CMake `FetchContent` (matches V6 pin)
- Pesto evaluation values — public source for D-01 initial coefficients; specific URL/source documented in `coeffs.json` header comment

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **V6 native module** at `src/chess_engine/engine/v6/` — V7's starting point; whole-tree fork (movegen, magic, zobrist, board, TT, eval, search, bindings, CMake, native_build).
- **`SearchInfo`** at `src/chess_engine/core/search_info.py` — V7 honors this contract (closes V6 gap).
- **`Device`** at `src/chess_engine/core/device.py` — not used by V7 (V7 is CPU-only Lazy SMP later; no CUDA).
- **`GameManager.ai_move`** ladder at `src/chess_engine/server/game_manager.py` — INT-01 plugs V7 in via the same string-comparison pattern V6 uses (anti-pattern preserved per V2-REF-01 deferral).
- **CLI subcommand pattern** at `cli/src/index.js` — `chess-engine build v6` becomes the template for `build v7` and `syzygy download`.
- **React engine selectors** at `client/src/App.jsx` — two `<select>` elements (white + black); INT-02 adds `<option value="v7">` to both.

### Established Patterns
- **Engine adapter contract:** `find_best_move(game_state, valid_moves, engine, search_info)` — V7 must export this signature exactly (FOUND-03).
- **CMake `FetchContent` of pybind11 v2.12.0** — V7's CMakeLists.txt mirrors V6's; CMake ≥3.15, C++17, OpenMP optional. CUDA explicitly NOT a target for V7.
- **Native module auto-build on first import** — V6's `__init__.py` invokes `native_build.py` if the `.pyd`/`.so`/`.dylib` is missing. V7 follows the same pattern; `INT-03` updates the UI warning to mention V7's build cost too.
- **`print()` as stderr logging** — acceptable in legacy code; V7 init-time Syzygy notices (D-08) follow this. Don't introduce a new logging abstraction this milestone.

### Integration Points
- `GameManager.ai_move` ← V7 import + AVAILABLE_ENGINES + set_engine_version + dispatch (INT-01, 4 lines)
- `client/src/App.jsx` ← V7 dropdown options + warning copy update (INT-02, INT-03)
- `cli/src/config.js` ← `v7Built`, `syzygyPath`, `syzygyMaxPieces` keys with defaults (INT-04)
- `cli/src/index.js` ← `build v7`, `syzygy download` subcommands (INT-05)
- `tests/test_v7_engine.py` ← legal-game smoke + perft parity + cancellation latency + NPS regression sentinel (INT-07)
- `.gitignore` ← V7 build artifacts including generated `coeffs.cpp` (D-12); `.gitmodules` ← Fathom submodule (INT-06)

</code_context>

<specifics>
## Specific Ideas

- **Init-time Syzygy log lines** are spelled out verbatim in D-08 — copy them, don't paraphrase. Each variant must include the specific reason and the literal `tbhits will be 0` so users can grep logs.
- **`coeffs.json` header comment** must cite the public source for each initial value family (Pesto for PSTs/material, etc.) per D-01 + D-02. Future contributors and Phase 4 tuner runs need to know what they're seeing as the starting point.
- **Codegen output formatting** must be deterministic (D-13): sorted keys, fixed indentation, fixed line endings. Use `json.dumps(..., sort_keys=True, indent=2)` and write LF line endings explicitly.
- **Pesto sourcing:** Pesto's PSTs and material values are public domain / well-documented at chessprogramming.org; cite the page in `coeffs.json` header. For non-PST terms with no Pesto equivalent (king-safety attack table, threats), use modest hand-set values and mark them clearly.

</specifics>

<deferred>
## Deferred Ideas

- **V6 SearchInfo bug backport** — V7 fixes the ignored-`SearchInfo` argument; V6 is left unchanged per the milestone constraint "V1–V6 engines must continue to work unchanged after V7 is added." If users want V6 cancellation, that's a separate refactor track (not V7).
- **Logging abstraction** — `print()`-as-stderr is preserved in Phase 1 per CONVENTIONS. A real `logging.getLogger(__name__)` migration is project-wide cleanup, not V7 scope.
- **Multi-seed tuning V6-equivalent seed (TUNE-08)** — Phase 4 work; Phase 1 only ships the Pesto-baseline seed.
- **Time management end-to-end exercise** — Phase 2's gauntlet, not Phase 1.
- **Back-to-back game stability** — Phase 2's gauntlet (mini-match), not Phase 1.
- **V7-as-black smoke** — Phase 2's gauntlet, not Phase 1.
- **`coeffs.cpp` commit-and-CI-verify hybrid** (rejected option from area 4) — could be revisited if generated-on-build proves to slow CI down or causes a stale-`coeffs.cpp` debugging friction; not adopted now.

</deferred>

---

*Phase: 1-Skeleton + Smoke*
*Context gathered: 2026-05-15*
