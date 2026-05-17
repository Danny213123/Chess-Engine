# Roadmap: Chess-Engine V7 Milestone

**Created:** 2026-05-15
**Granularity:** standard
**Mode:** standard (Horizontal Layers — engine subsystems are inherently layered, but each phase delivers a coherent vertical capability validated end-to-end)
**Project:** V7 native chess engine — fork of V6, hardened search, Lazy SMP, Texel-tuned HCE, Syzygy probing
**Core Value:** V7 must play stronger chess than V6 in head-to-head gauntlets — measurable strength gain is the one thing that cannot fail.

## Phases

- [ ] **Phase 1: Skeleton + Smoke** - V7 module exists, builds, plays a legal game vs V6 end-to-end (single thread, basic search, scaffolded eval, Syzygy probing, dispatched from UI)
- [ ] **Phase 2: Gauntlet Harness Early** - fastchess-driven V6-vs-V6 sanity probe + V7-vs-V6 mini-gauntlet runs reproducibly with NPS regression check; every later change is gauntlet-validated
- [ ] **Phase 3: Lockless TT + Search Refinements + Endgame** - Hyatt-Mann XOR TT (TSan-stress-passed), full LMR/null/futility/LMP/singular/multi-cut/probcut/IIR stack, in-engine endgame eval with continuous phase blend
- [ ] **Phase 4: Lazy SMP + Texel Tuning** - Multi-thread search scales ≥3× from 1→4 threads with ≥40 Elo gain; eval coefficients Texel-tuned against Zurichess and committed to source
- [ ] **Phase 5: Final Gauntlet + Ship** - ≥2 independent SPRT runs at production thread count show V7 meaningfully stronger than V6; ship verdict pronounced

## Phase Details

### Phase 1: Skeleton + Smoke
**Goal**: V7 native module exists, builds on Windows/Linux/macOS, ports V6's board/movegen/magic/zobrist with perft parity, runs a sequential PVS search with hardened iterative deepening, has eval term scaffolding ready for tuning, integrates Fathom for Syzygy probing, and plays a full game vs V6 end-to-end through the existing React UI.
**Depends on**: Nothing (first phase — forks V6)
**Parallelizable subsystems**: B1 (sequential search) ∥ B2 (eval scaffolding) ∥ B3 (Syzygy integration) — touch disjoint files (`search/`, `eval/`, `syzygy/`); planner should wave-schedule these after A1+A2 land
**Requirements**:
  - Foundation: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, FOUND-07
  - Search (B1 baseline): SRCH-01, SRCH-02, SRCH-13, SRCH-14, SRCH-15
  - Eval (B2 scaffolding — all terms structurally present so Texel can tune them in Phase 4): EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06, EVAL-07, EVAL-08, EVAL-09, EVAL-10, EVAL-11
  - Tablebases (B3): TB-01, TB-02, TB-03, TB-04, TB-05, TB-06, TB-07, TB-08, TB-09, TB-10
  - Integration (C1 smoke): INT-01, INT-02, INT-03, INT-04, INT-05, INT-06, INT-07, INT-08, INT-09
**Success Criteria** (what must be TRUE):
  1. `chess-engine build v7` succeeds on Windows MSVC and produces a loadable `v7_engine.{pyd,so,dylib}` plus a `v7_uci` standalone executable
  2. V7 perft matches V6 to depth 6 on Kiwipete + position 3 + position 4 + starting position
  3. A user opens the React UI, selects V7 for one side and V6 for the other, presses play, and a complete legal game finishes without crashes or illegal moves
  4. Pressing Stop in the UI cancels a V7 search within ~50 ms (cancellation token reaches the C++ search via the new `algo_v7.stop()` contract — closes V6's gap)
  5. With `syzygyPath` set to a 3-4-5 men tablebase directory, `tbhits > 0` is reported in search info for an in-range position; with `syzygyPath` unset, V7 still plays correctly with `tbhits = 0`
  6. V1–V6 engines continue to dispatch and return legal moves after V7 is added (existing pytest suite passes unchanged)
**Plans**: 6 plans
- [x] 01-01-PLAN.md — Wave 1: Fork V6 scaffold + stateful Engine class (FOUND-01/02/03/04/05/07, INT-09)
- [x] 01-02-PLAN.md — Wave 2: Port board/movegen/magic/zobrist + perft parity vs V6 (FOUND-06)
- [x] 01-03-PLAN.md — Wave 3 (B1): Sequential PVS search + 4 hardening patches (SRCH-01/02/13/14/15, FOUND-04)
- [x] 01-04-PLAN.md — Wave 4 (B2): coeffs.json + gen_coeffs.py + eval.cpp scaffolding all 11 EVAL terms (EVAL-01..11)
- [x] 01-05-PLAN.md — Wave 5 (B3): Fathom submodule + tbconfig.h override + syzygy.cpp + D-08 init logs (TB-01..08, TB-10, INT-06)
- [x] 01-06-PLAN.md — Wave 6 (C1): GameManager + React UI + Node CLI + smoke tests + v7_uci (INT-01..05, INT-07/08/09, TB-09, FOUND-07)
**UI hint**: yes

### Phase 2: Gauntlet Harness Early
**Goal**: Stand up the V7-vs-V6 validation infrastructure as soon as Phase 1's smoke milestone is reachable, so every Phase 3/4 change is gauntlet-tested rather than discovered to have regressed at the end. Includes a V6-vs-V6 sanity probe (must return ~0 Elo) before any V7 result is trusted, plus an NPS regression check that fails the build if V7 NPS drops more than 20% vs V6.
**Depends on**: Phase 1 (needs `v7_uci` binary and a working V7 baseline)
**Parallelizable subsystems**: None — single workstream (one harness, one set of scripts)
**Requirements**:
  - Gauntlet harness (F1): GAUNT-01, GAUNT-02, GAUNT-03, GAUNT-04, GAUNT-05, GAUNT-06, GAUNT-07, GAUNT-08
**Success Criteria** (what must be TRUE):
  1. Running the gauntlet script with V6 vs V6 at production options (identical Hash, Threads, TC) returns an Elo difference within ±15 (per D-10 — statistical zero at 200 games; supersedes the earlier ±10 estimate) — sanity probe passes
  2. The exact fastchess command line is persisted in every result file, and re-running the same command on the same hardware reproduces the result within 95% CI
  3. Pentanomial SPRT terminates within ≤5000 games for a clearly-stronger or clearly-weaker engine pair at `elo0=0 elo1=10 alpha=0.05 beta=0.05`
  4. Result aggregator reports time forfeits in a separate column from losses; any forfeit triggers a manual-investigation flag (not silently counted as a loss)
  5. The build fails with a clear error message if V7 NPS on the bench position drops more than 20% vs V6 NPS on the same hardware
**Plans**: 6 plans
- [x] 02-01-PLAN.md — Wave 1: V7 UCI extensions — setoption + wtime/btime parsing (GAUNT-02)
- [x] 02-02-PLAN.md — Wave 1: V6 UCI binary (v6_uci CMake target + uci_main.cpp + tests) (GAUNT-02)
- [x] 02-03-PLAN.md — Wave 1: fetch_fastchess.py + 8moves_v3.pgn vendoring (or fallback manifest) + .gitignore + human checkpoint for SHA256 verification (GAUNT-01, GAUNT-05)
- [x] 02-04a-PLAN.md — Wave 2: tools/gauntlet_core.py pure functions (command builder, stdout/PGN parsers, sanity-verdict) + unit tests (GAUNT-03, GAUNT-06, GAUNT-07)
- [x] 02-04b-PLAN.md — Wave 2: tools/gauntlet.py I/O wrapper (subprocess runner, summary.json writer, run/sanity subcommands, D-09 hard deferral) + I/O tests (GAUNT-03, GAUNT-06, GAUNT-07)
- [ ] 02-05-PLAN.md — Wave 3: NPS regression sentinel + V6-vs-V6 sanity probe checkpoint with investigation_required gate (GAUNT-04, GAUNT-08)

### Phase 3: Lockless TT + Search Refinements + Endgame
**Goal**: Replace V6's single-threaded TT with a Hyatt-Mann XOR lockless TT (gated by a 16-thread × 60-second TSan stress test), add the full modern search refinement stack (LMR with context, adaptive null-move with zugzwang guard, LMP/RFP/futility, killer/history/counter/SEE move ordering, singular extensions, multi-cut, ProbCut, IIR, recapture extensions), and add in-engine endgame knowledge (KPK bitbase, opposition, wrong-bishop+rook-pawn rule, continuous phase blend, optional fortress hints).
**Depends on**: Phase 1 (smoke milestone), Phase 2 (gauntlet harness — every refinement is gauntlet-validated)
**Parallelizable subsystems**: D1 (lockless TT in `tt.cpp`) ∥ D2 (search refinements in `search/`) ∥ D3 (endgame eval in `endgame.cpp`) — disjoint files; planner should wave-schedule. Note that **D1 must complete before Phase 4 E1 (Lazy SMP) starts** — building Lazy SMP on a non-lockless TT is silent corruption (PITFALLS Pitfall 36)
**Requirements**:
  - Lockless TT (D1): PAR-01, PAR-02, PAR-03
  - Search refinements (D2): SRCH-03, SRCH-04, SRCH-05, SRCH-06, SRCH-07, SRCH-08, SRCH-09, SRCH-10, SRCH-11, SRCH-12
  - Endgame eval (D3): ENDG-01, ENDG-02, ENDG-03, ENDG-04, ENDG-05
**Success Criteria** (what must be TRUE):
  1. The lockless TT passes a 16-thread × 60-second random probe/store stress test on Linux/macOS/WSL with TSan enabled, reporting zero data races and zero illegal moves returned
  2. Phase 3 V7 wins a head-to-head gauntlet against the Phase 1 baseline V7 by a clearly measurable Elo margin (≥30 Elo at fixed depth) — confirms LMR/null/futility/etc. are net-positive, not net-negative from off-by-one bugs
  3. KPK test positions (all 163,328 legal positions classified correctly) and the wrong-bishop+rook-pawn drawn-corner test positions return the expected scores; Stockfish-style continuous phase blend produces monotonically-decreasing phase as material is removed
  4. NPS for the singular-extensions-enabled build changes by less than 10% vs singular-disabled (Pitfall 5 search-explosion check passes); LMR-on engine searches deeper at fixed time than LMR-off engine
**Plans**: TBD

### Phase 4: Lazy SMP + Texel Tuning
**Goal**: Turn on the parallelism the codebase has been preparing for, and produce the V7 release artifact (Texel-tuned coefficient JSON committed to source). Lazy SMP runs N `std::thread` workers with per-thread history/killers/counter/continuation/stack and a shared lockless TT, with the GIL released for the entire search. Texel pipeline runs against Zurichess `quiet-labeled.epd` with sparse coefficient extraction, K-factor fit once, train/validation split, multi-seed tuning, and codegen of `coeffs.cpp` from JSON for single-source-of-truth names.
**Depends on**: Phase 3 (E1 hard-depends on D1 lockless TT; E2 depends on Phase 1 EVAL-10/11 coeffs scaffolding and Phase 2 gauntlet to validate)
**Parallelizable subsystems**: E1 (Lazy SMP in `thread_pool.cpp` + `bindings.cpp`) ∥ E2 (Texel in `tune.cpp` + Python tools) — disjoint files; planner should wave-schedule these as two independent workstreams within the phase
**Requirements**:
  - Lazy SMP (E1): PAR-04, PAR-05, PAR-06, PAR-07, PAR-08, PAR-09
  - Texel tuning pipeline (E2): TUNE-01, TUNE-02, TUNE-03, TUNE-04, TUNE-05, TUNE-06, TUNE-07, TUNE-08, TUNE-09, TUNE-10
**Success Criteria** (what must be TRUE):
  1. NPS scaling test: 4-thread NPS is ≥3× single-thread NPS on the bench position (proves GIL is released and Lazy SMP is actually parallel — not GIL-serialized)
  2. Cancellation latency test: calling `algo_v7.stop()` from Python during a deep 4-thread search interrupts within <50 ms (no worker stuck in a long non-polling stretch)
  3. 4-thread V7 vs 1-thread V7 gauntlet shows ≥40 Elo gain (confirms per-thread history/killers/counter divergence is doing real work — not collapsing into lockstep)
  4. One full Texel tuning run produces a non-default `coeffs.json` whose values are reproducible from the Zurichess dataset (K fit once, persisted alongside JSON; train/validation losses both decrease then plateau without divergence)
  5. `eval_quiet(starting_pos)` returns identical values from the Python tuner harness and the C++ search binary on the same coefficient set — proves the codegen single-source-of-truth pipeline is wired correctly (no name mismatches)
  6. Tuned V7 wins a gauntlet vs untuned-V7-with-same-search-stack by a clearly measurable Elo margin
**Plans**: TBD

### Phase 5: Final Gauntlet + Ship
**Goal**: Run the explicit ship-signal gauntlet from PROJECT.md — V7 vs V6 at production thread count, identical Hash/Threads/TC, ≥1000-game pentanomial SPRT, repeated as ≥2 independent runs to rule out variance. Execute the "Looks Done But Isn't" checklist from PITFALLS.md. Update README with Syzygy download note and thread config. Pronounce ship verdict.
**Depends on**: Phase 4 (Lazy SMP + tuned coefficients) and Phase 2 (gauntlet harness)
**Parallelizable subsystems**: None — sequential ship gate
**Requirements**:
  - Ship verdict (G1): GAUNT-09
**Success Criteria** (what must be TRUE):
  1. SPRT terminates with H1 acceptance (V7 stronger than V6 at `elo0=0 elo1=10 alpha=0.05 beta=0.05`) in **at least 2 independent runs** at production thread count, each ≥1000 games, run on plugged-in non-throttled hardware
  2. The V6-vs-V6 sanity probe re-run before each ship gauntlet returns Elo within ±15 (per D-10 — matches Phase 2 tolerance; no environmental drift since Phase 2)
  3. Every item in the PITFALLS.md "Looks Done But Isn't" checklist (16 items) is verified and recorded as passing — Lazy SMP cores hit, TT persists across moves, mate scores correct, repetition draws return 0, Syzygy hits reported, V7 in both UI dropdowns, V1–V6 still work, CLI bench v7 runs
  4. Final result files (containing the exact fastchess command line, pentanomial result, LOS, time-forfeit count, and SPRT verdict) are committed for both independent runs
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Skeleton + Smoke | 0/6 | Planned | - |
| 2. Gauntlet Harness Early | 3/6 | In Progress|  |
| 3. Lockless TT + Search Refinements + Endgame | 0/? | Not started | - |
| 4. Lazy SMP + Texel Tuning | 0/? | Not started | - |
| 5. Final Gauntlet + Ship | 0/? | Not started | - |

## Phase Ordering Decisions

These ordering decisions were made during roadmap creation and bind the planner:

1. **D1 (lockless TT) sits in Phase 3, Lazy SMP (E1, PAR-04..09) sits in Phase 4** — hard ordering driven by PITFALLS.md Pitfall 36. Building Lazy SMP on V6's single-threaded TT silently corrupts entries; the 16-thread TSan stress test (PAR-03) is the gate between Phase 3 and Phase 4 starting E1 work.

2. **Gauntlet harness (GAUNT-01..08) is Phase 2, NOT Phase 5** — driven by PITFALLS.md Pitfall 37 ("Skipping the gauntlet harness early"). Standing up F1 immediately after the C1 smoke milestone means every Phase 3/4 change is gauntlet-validated; deferring it to Phase 5 risks "we shipped, we lost Elo, we don't know which change broke it." GAUNT-09 alone (≥2 independent SPRT runs as the ship verdict) lives in Phase 5.

3. **FOUND-05 (`py::call_guard<py::gil_scoped_release>()`) lands in Phase 1, not Phase 4** — even though the GIL release is what *makes* Lazy SMP parallel, wiring the binding correctly from day one means the smoke milestone in Phase 1 already proves the pattern works. PITFALLS.md Pitfall 11 calls this "the single most common pybind11 mistake"; deferring it to Phase 4 means re-architecting the binding mid-milestone.

4. **All EVAL-* terms (01–11) land in Phase 1, not Phase 4** — even though Texel tuning happens in Phase 4 (E2, TUNE-*), the eval *structure* (every term defined as a tunable coefficient in `coeffs.cpp`) must be in place during Phase 1's B2 scaffolding so that Phase 4's tuner has something to tune. This satisfies the planning constraint "TUNE-* depends on EVAL-10/11 in place first" and extends it: TUNE-* depends on **all** EVAL-* terms being structurally present.

5. **Search hardening (SRCH-01, 02, 13, 14, 15) lands in Phase 1; search refinements (SRCH-03..12) land in Phase 3** — the split is "what must be true for a legal game to be playable" (Phase 1) vs "what makes the engine strong" (Phase 3). Mate-score TT handling (SRCH-13), repetition + 50-move correctness (SRCH-14), and time management (SRCH-15) are pre-C1 must-haves per PITFALLS.md Pitfalls 1, 7, 33; LMR/null/futility/singular/multi-cut/probcut/IIR are explicitly listed as Phase 3 D2 work.

6. **Phase 5 contains a single requirement (GAUNT-09)** — this is intentional. The ship gate is a *decision point*, not a build phase. All implementation work is complete after Phase 4; Phase 5 exists so that "ran the gauntlet" cannot be skipped or conflated with "built the gauntlet harness" (Phase 2).

## Coverage Summary

- Total v1 requirements: **85** (REQUIREMENTS.md footer says 70, but the actual REQ-ID count across all 9 categories is 85 — see Coverage Notes in the structured return)
- Mapped to phases: **85** ✓
- Unmapped: **0**

| Phase | Requirement count |
|-------|-------------------|
| Phase 1 | 42 (FOUND ×7, SRCH ×5, EVAL ×11, TB ×10, INT ×9) |
| Phase 2 | 8 (GAUNT-01..08) |
| Phase 3 | 18 (PAR ×3, SRCH ×10, ENDG ×5) |
| Phase 4 | 16 (PAR ×6, TUNE ×10) |
| Phase 5 | 1 (GAUNT-09) |
| **Total** | **85** |

---
*Roadmap created: 2026-05-15*
*Phase 2 plans revised: 2026-05-16 — split 02-04 into 02-04a (pure) + 02-04b (I/O), added human checkpoint to 02-03 for SHA256 verification, fixed ±10 → ±15 tolerance per D-10, added investigation_required gate to 02-05 Task 3.*
