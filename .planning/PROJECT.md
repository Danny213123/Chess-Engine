# Chess-Engine

## What This Is

A chess-playing application with a FastAPI backend, React 19 frontend, and a family of in-house chess engines (V1–V6) ranging from pure-Python to a native C++17 pybind11 module with optional CUDA and OpenMP acceleration. This milestone (V7) introduces a new, meaningfully stronger engine that beats V6 in head-to-head play while remaining selectable from the existing UI.

## Core Value

V7 must play stronger chess than V6 in head-to-head gauntlets — measurable strength gain is the one thing that cannot fail.

## Requirements

### Validated

<!-- Inferred from existing codebase map (.planning/codebase/). These are shipped capabilities relied upon today. -->

- ✓ FastAPI backend exposes game state, moves, AI moves, engine selection, undo/redo, search history — existing
- ✓ React 19 + Vite frontend with `react-chessboard` UI, recharts search stats, axios client — existing
- ✓ In-process `GameManager` singleton orchestrates human + AI moves — existing
- ✓ Engines V1–V6 selectable via dropdown; each implements `find_best_move(game_state, valid_moves, engine[, search_info])` — existing
- ✓ V6 native C++17 engine (magic bitboards, alpha-beta search, transposition table, classical eval) built via pybind11 + CMake `FetchContent`, optional OpenMP — existing
- ✓ `SearchInfo` cooperative cancellation token polled by engines — existing
- ✓ `Device` singleton dispatching CPU vs CUDA paths for vectorized eval — existing
- ✓ pytest test suite, CLI scripts for benchmarking / perft / self-play — existing

### Active

<!-- V7 milestone scope. All hypotheses until shipped + validated by gauntlet. -->

- [ ] V7 engine implemented as a fork of V6's native C++ pybind11 module under `src/chess_engine/engine/v7/`
- [ ] V7 search overhaul: refined pruning/reductions (LMR, null-move, futility, LMP), selectivity extensions (singular, check, recapture), aspiration windows + iterative deepening hardening, and advanced techniques (multi-cut, probcut)
- [ ] V7 parallel search via Lazy SMP (multiple threads sharing the transposition table)
- [ ] V7 improved classical HCE: better PSTs, king safety, pawn structure, mobility — tuned via Texel against the Zurichess quiet-labeled dataset
- [ ] V7 endgame understanding: phase detection + endgame-specific eval terms (KPK, opposition, basic fortress hints)
- [ ] Syzygy tablebase integration (3-4-5-6 men) probed in search, with an optional download script — no tablebases bundled in the repo
- [ ] V7 selectable from the React engine dropdown alongside V1–V6 (no other frontend work)
- [ ] V7 NPS stays within ~20% of V6 NPS on the same hardware (responsiveness floor)
- [ ] V7 wins a head-to-head gauntlet against V6 at fixed time control by a meaningful margin (no hard ELO floor; gauntlet result is the ship signal)
- [ ] Texel tuning pipeline established (reproducible from the Zurichess dataset)
- [ ] Gauntlet harness established (V7 vs V6 self-play at fixed TC, result aggregation)

### Out of Scope

- NNUE / neural evaluation — explicitly deferred; this milestone is classical HCE only. NNUE may be a later V8 milestone.
- AlphaZero-style full-NN + MCTS engine — out of scope; not aligned with HCE + alpha-beta direction.
- SPSA / self-play tuning — Texel only this milestone; SPSA can be added later if the dataset proves insufficient.
- Consolidating the v5/v5b/v5c/v5d copy-paste forks — flagged as a separate cleanup, not folded into V7. Tracked for a future refactor milestone.
- Replacing the `GameManager` string-comparison engine ladder with a registry — adjacent anti-pattern, not blocking V7. Defer.
- Replacing the module-global `gm = GameManager()` singleton — same as above.
- Opening book integration — out of scope. V7 plays from the starting position with no book.
- Bundling Syzygy tablebases in the repo or releases — only an optional download script; users opt in.
- New UI features beyond the V7 dropdown entry (no diagnostics panels, no in-app gauntlet UI, no eval breakdowns).
- Hard ELO target (+50 / +100 / +200) — replaced by gauntlet "meaningfully stronger" judgement.
- Fixed timeline — quality over speed; ship when gauntlet shows clear improvement.
- Mobile / native app builds — backend + browser only.
- Multi-user concurrency, persistence, accounts — single in-process game model is retained.

## Context

- Brownfield project with a current codebase map at `.planning/codebase/` (ARCHITECTURE, STACK, STRUCTURE, CONVENTIONS, CONCERNS, INTEGRATIONS, TESTING — generated 2026-05-14/15). New work should respect documented patterns.
- V6 is the current strongest engine and the baseline V7 must beat. It uses magic bitboards, alpha-beta with TT, and a classical eval — V7 will fork this and evolve it rather than starting from scratch.
- The codebase contains identified anti-patterns documented in ARCHITECTURE.md (engine-name `if/elif` ladder in `GameManager`, module-global singleton, `sys.path`-mutating shims, v5* copy-paste forks). These are knowingly NOT addressed by this milestone — V7 is engine-only.
- Build system: V7 will reuse the V6 CMake + pybind11 + `FetchContent` pattern. CUDA is not a target (V7 is CPU/OpenMP-style parallel via Lazy SMP).
- Testing baseline: existing pytest suite + CLI bench/perft tools. The Texel pipeline and the V7-vs-V6 gauntlet harness are new infrastructure this milestone must build.
- Tuning data: Zurichess quiet-labeled set is the chosen public dataset (~750k positions). No self-play augmentation this milestone.
- Endgame play improvement is split into two complementary pieces: external knowledge (Syzygy probing) and in-engine knowledge (phase-aware eval). Both required.

## Constraints

- **Tech stack**: V7 must be a C++17 pybind11 module mirroring V6's build pattern. No new language additions; no replacement for FastAPI / React.
- **Performance**: V7 NPS must remain within roughly 20% of V6 NPS on the same hardware so UI responsiveness is preserved.
- **Validation**: Strength must be demonstrated by head-to-head gauntlet vs V6 — no other shipping criterion overrides this.
- **Repo size**: Syzygy tablebases are not bundled. Only an optional download script may be checked in.
- **UI surface**: Frontend changes are limited to adding V7 to the engine dropdown.
- **Tuning data**: Use the public Zurichess quiet-labeled set as the Texel ground truth. No proprietary or self-play data this milestone.
- **Compatibility**: V1–V6 engines must continue to work unchanged after V7 is added.
- **Concurrency**: Parallel search uses Lazy SMP only; do not introduce a new threading abstraction in the FastAPI server layer.
- **Cancellation**: V7 must honor the existing `SearchInfo` cooperative cancellation contract.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fork V6 native C++ pybind11 module as the V7 starting point | Preserves V6's strength baseline (magic bitboards, TT, alpha-beta) and reuses the proven CMake + pybind11 build path | — Pending |
| Classical HCE (no NNUE) for V7 | Lower scope, no training infra needed, builds on V6's existing eval mental model; NNUE deferred to a possible V8 | — Pending |
| Texel tuning on the Zurichess quiet-labeled dataset | Industry-standard dataset, well-documented gradient method, no self-play infra required this milestone | — Pending |
| Lazy SMP for parallel search | Standard modern technique, big strength gain on multi-core, fits a shared transposition table cleanly | — Pending |
| Both Syzygy tablebases AND in-engine endgame eval | Tablebases give exact play near material; in-engine eval handles everything outside tablebase range | — Pending |
| Syzygy via optional download script (not bundled) | 6-men tablebases are ~150GB — bundling is infeasible; user opt-in keeps the repo clean | — Pending |
| Gauntlet result is the ship signal (no fixed ELO target) | Avoids arbitrary thresholds; "meaningfully stronger than V6" is the actual goal | — Pending |
| NPS within ~20% of V6 (soft floor) | Keeps the UI responsive; allows new eval/search cost so long as strength rises faster than NPS falls | — Pending |
| v5* fork consolidation and `GameManager` cleanup deferred | Keeps V7 milestone focused on engine strength; cleanup is a separate refactor track | — Pending |
| No UI work beyond adding V7 to the dropdown | Engine-only milestone; UI improvements (diagnostics, gauntlet UI, eval breakdown) are deferred | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-15 after initialization (V7 milestone)*
