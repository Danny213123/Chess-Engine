# Phase 3: Lockless TT + Search Refinements + Endgame - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 delivers V7's strength step-change: (D1) replace the Phase-1 placeholder TT with a Hyatt-Mann XOR lockless TT (Phase 4 SMP gate per PITFALLS #36), (D2) land the full modern search refinement stack (LMR with context, adaptive null move with zugzwang guard, RFP/futility/LMP, killer/history/counter-move/SEE-bucketed move ordering, singular extensions, multi-cut, ProbCut, IIR/IID, check/recapture extensions — SRCH-03..12), and (D3) add in-engine endgame knowledge (KPK bitbase, opposition, wrong-bishop+rook-pawn, continuous phase blend, optional fortress hints — ENDG-01..05). All work is gated by the Phase 2 gauntlet harness; ship criterion is a ≥30 Elo gain over a freshly-measured fixed-baseline V7.

</domain>

<decisions>
## Implementation Decisions

### Perf-bug sequencing & baseline

- **D-01:** The 3 known Phase 1 perf bugs (engine.cpp:99 depth-cap overwrite, search.cpp:267 killers/history stack-reset, search.cpp `std::vector<Move>` PV alloc — see `memory/project_phase1_known_perf_bugs.md`) are fixed in **Plan 03-01** (first plan of Phase 3). The phase boundary remains Phase 3; no separate Phase 1 gap-closure milestone.
- **D-02:** After Plan 03-01 merges, a **blocking human checkpoint** runs a 500-game V7-vs-V6 gauntlet on a build host. The resulting `summary.json` is persisted as `.planning/gauntlets/baseline/summary.json` (or a clearly-named directory) and becomes the canonical reference for Success Criterion #2 (Phase 3 V7 must beat THIS baseline by ≥30 Elo). All later Phase 3 gauntlets compare against this file.
- **D-03:** Plan 03-01 builds the **production scaffold** that later plans extend — it is NOT a minimal-diff fix:
  - Persistent `killers[][2]` and `history[][]` tables move from per-call stack into `Engine` member state (or per-ply `SearchStack` indexed by ply), mirroring V6's persistent pattern.
  - Triangular PV array allocated once (e.g., `Move pv[MAX_PLY][MAX_PLY]`) and indexed by ply — no per-recursion `std::vector` allocs.
  - `info.depth` contract clarified so iterative_deepening's `info.depth = depth` cannot silently overwrite the caller's max-depth bound.
  - Acceptance: bench NPS ≥ 200k on the standard position (sanity floor; final NPS gate is the per-gauntlet sentinel).

### Refinement landing & gauntlet cadence

- **D-04:** Search refinements are split into **two tiers across two plans**:
  - **Plan 03-02 (proven cheap):** SRCH-03 (adaptive null move + zugzwang guard), SRCH-04 (LMR with context), SRCH-05 (RFP / futility / LMP), SRCH-06 (killers + history + counter-move + SEE-bucketed captures), SRCH-11 (IIR/IID), SRCH-12 (check + recapture extensions).
  - **Plan 03-03 (aggressive):** SRCH-07 (continuation + capture history), SRCH-08 (singular extensions, depth ≥8 with verification), SRCH-09 (multi-cut, depth ≥8), SRCH-10 (ProbCut — explicitly gauntlet-gated, may revert to OFF).
- **D-05:** Mid-Phase-3 validation bar = **non-regression mini-gauntlet** after each tier:
  - 200-game gauntlet vs `baseline.json`. Lower-bound Elo must be > −10 (non-regression).
  - Final Phase 3 ship gate = **500–1000 game pentanomial SPRT** vs `baseline.json` showing ≥30 Elo (Success Criterion #2). Full SPRT params per Phase 2 D-12: `elo0=0 elo1=10 alpha=0.05 beta=0.05`.
  - All gauntlets are blocking human checkpoints on the build host (Windows dev box cannot run them — same pattern as Phase 1/2).
- **D-06:** Each search refinement is exposed as a **UCI option, default ON**: `UseNullMove`, `UseLMR`, `UseRFP`, `UseFutility`, `UseLMP`, `UseSingular`, `UseMultiCut`, `UseProbCut`, `UseIIR`, `UseCheckExt`, `UseRecaptureExt`. Purpose: (a) ablation gauntlets if a tier regresses, (b) Success Criterion #4 evidence (singular-on vs singular-off NPS within 10%; LMR-on vs LMR-off depth at fixed time). Wired through the existing v7_uci `setoption` parser (Plan 02-01).

### Lockless TT (D1)

- **D-07:** Hyatt-Mann lockless TT: **two `std::atomic<uint64_t>` slots per entry** — `xkey = key XOR data`, and `data` (packed). Single entry per bucket (cluster size = 1). Replacement policy: age-then-depth. Multi-slot clusters explicitly deferred — can be added in Phase 4 if SMP hit-rate measurement demands it; not a Phase 3 risk.
- **D-08:** PAR-03 TSan verification = `scripts/tt_tsan_stress.sh` (or equivalent CMake target) that builds a standalone TT-only harness with `-fsanitize=thread` and runs 16 threads × 60 seconds of randomized probe/store. Documented in Phase 3's eventual `.continue-here.md`. Runs on **WSL/Linux/macOS as a blocking human checkpoint at end of Phase 3** — TSan is not available on MSVC. Pattern mirrors Phase 1's deferred build-host gates.
- **D-09:** TT entry packing **inherits V6's 64-bit layout verbatim** from `src/chess_engine/engine/v6/include/tt.hpp` / `src/tt.cpp`. Planner must read V6's actual layout and mirror bit-for-bit (typically: move 16b, score 16b, depth 8b, bound 2b, age 6b, eval/padding 16b — but VERIFY against V6 source). Only structural change vs V6: the entry is wrapped in `std::atomic<uint64_t>` for the Hyatt-Mann XOR contract. No new fields, no widened bit fields.

### Endgame eval (D3)

- **D-10:** **KPK bitbase generation = build-time codegen.** Add `tools/gen_kpk.py` (preferred; mirrors `tools/gen_coeffs.py` pattern from Phase 1 D-10) that computes all 163,328 legal positions and emits `src/chess_engine/engine/v7/src/kpk_bitbase.cpp` containing a packed `static const uint32_t KPK[...]` table (~32 KB). The .cpp output is **gitignored** (mirrors coeffs.cpp pattern per Phase 1 D-12); the .py generator and a deterministic test fixture are committed. Runtime probe = O(1) bit lookup. Acceptance: pytest verifies the lookup matches a known-good reference (e.g., Fathom KPK probe) on all 163,328 positions.
- **D-11:** ENDG-05 (conservative fortress hints): **full framework attempted, behind a UCI toggle that defaults OFF.** Plan 03-04 lands implementation with `UseFortressEval` default OFF — zero gauntlet impact on the Phase 3 SPRT. A separate, scoped validation gauntlet (added inside Plan 03-04 or as a tail task) flips it ON and runs ≥500 games vs default-OFF V7; ship as default-ON only if the gauntlet shows clearly-positive Elo. If validation fails, ship as default-OFF with REQUIREMENTS.md ENDG-05 annotated `[implemented but disabled — fortress validation gauntlet showed regression]`.
- **D-12:** New endgame eval coefficients (opposition value, wrong-bishop-rook-pawn scale, KPK rule bonuses, fortress weights, phase-blend constants for ENDG-04) are **added to `coeffs.json`** with hand-tuned initial values. They flow through the existing `gen_coeffs.py → coeffs.cpp` codegen (Phase 1 D-10 / EVAL-11) so Phase 4 Texel can either tune or pin them. No new hand-tuned C++ `constexpr` constants for endgame terms.

### Claude's Discretion

- Exact plan-to-wave layout — D1 (Plan 03-05 candidate) is file-disjoint (`tt.{hpp,cpp}`) from D2 and D3, so the planner may run D1 in parallel with the 03-02/03-03/03-04 chain. Constraint: 03-01 must land first (baseline scaffold), and the final ship-SPRT (Phase 3 acceptance) runs after all four merge.
- Exact UCI option names so long as `Use<Refinement>` convention is honored.
- Whether `tools/gen_kpk.py` lives at top-level `tools/` or under `src/chess_engine/engine/v7/tools/` (Phase 1 placed `gen_coeffs.py` under the latter — mirror that if no other pressure).
- Exact triangular PV array dimensions (MAX_PLY value) so long as it covers all reachable plies.
- Whether singular extensions / multi-cut / ProbCut share verification helpers or each has its own — implementation detail.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap

- `.planning/REQUIREMENTS.md` — Phase 3 owns SRCH-03..12, ENDG-01..05, PAR-01..03; TUNE-09 references back here (post-Texel margin rescaling)
- `.planning/ROADMAP.md` — Phase 3 success criteria, D1 hard-gate before Phase 4 E1 (Lazy SMP), D1/D2/D3 parallelizable subsystems
- `.planning/PROJECT.md` — constraints (NPS ~20% floor, V1–V6 untouched, classical HCE only, cancellation contract)

### Phase 1 source under modification

- `src/chess_engine/engine/v7/include/{engine,search,tt,eval}.hpp` — current scaffolding
- `src/chess_engine/engine/v7/src/{engine,search,tt,eval,coeffs}.cpp` — code to refactor / replace (search.cpp + engine.cpp heavy in 03-01)
- `src/chess_engine/engine/v7/tools/gen_coeffs.py` — template for `gen_kpk.py` (D-10)
- `src/chess_engine/engine/v6/include/tt.hpp` + `src/chess_engine/engine/v6/src/tt.cpp` — **bit-pack layout to mirror verbatim per D-09**

### Phase 2 outputs Phase 3 consumes

- `.planning/phases/02-gauntlet-harness-early/02-CONTEXT.md` — gauntlet config (D-08 TC=10+0.1 c=1, D-11 8moves_v3.pgn book, D-12 SPRT params)
- `tools/gauntlet.py` + `tools/fetch_fastchess.py` (Phase 2 Plans 03/04a/04b) — runner the new gauntlets invoke
- `.planning/gauntlets/baseline/` (created in Plan 03-01) — canonical baseline summary.json for all Phase 3 comparisons
- `tests/test_nps_regression.py` + `tests/test_gauntlet_sanity.py` — sanity contract the Phase 3 fixes must not break

### Phase 1 outstanding context affecting Phase 3

- `memory/project_phase1_known_perf_bugs.md` — exact line numbers of the 3 perf bugs Plan 03-01 must fix
- `.planning/phases/01-skeleton-smoke/.continue-here.md` — Phase 1 deferred build-host gates that Phase 3 inherits (toolchain still required)
- `memory/project_v6_v7_uci_gaps.md` — `setoption` parsing landed in 02-01; UCI toggles (D-06) plug into that surface

### External references

- Hyatt-Mann lockless TT (XOR trick): standard pattern in Stockfish (`tt.h` / `tt.cpp`); planner should read Stockfish's current TT for reference but Phase 3 does NOT copy code — original implementation per D-07/D-09.
- Pitfalls: Pitfall 36 (Lazy SMP on non-lockless TT = silent corruption — D1 gates Phase 4), Pitfall 5 (singular extensions search-explosion check — Success Criterion #4 NPS budget)
- Stockfish KPK bitbase reference (for D-10 codegen ground truth) — public domain in concept, Phase 3 generates from scratch
- Fathom Syzygy `tb_probe_wdl` for KPK ground-truth validation (D-10 acceptance test)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`tools/gen_coeffs.py` codegen pattern** (Phase 1 Plan 04): identical template for `tools/gen_kpk.py` — same script-emits-.cpp idempotency, same `.gitignore` rule for the emitted artifact.
- **`Engine` member state for persistent search context** (Phase 1 Plan 03's `rep_stack_`, `syzygy_` pattern — see CONTEXT.md/HANDOFF.json Plan 01 decisions): the killers/history relocation in Plan 03-01 should mirror this pattern (add `killers_`, `history_` as Engine members) for consistency.
- **`setoption` UCI parser** (Phase 2 Plan 02-01): the 11 UCI toggles in D-06 plug into this parser; each new option needs an `option name <X> type check default true` declaration and a parse-time branch.
- **Gauntlet harness + sanity probe** (Phase 2 Plans 03/04a/04b/05): Phase 3 generates new gauntlets via `tools/gauntlet.py`; the existing `summary.json` schema + `test_nps_regression.py` sentinel apply unchanged.
- **`coeffs.json` + `gen_coeffs.py` pipeline** (Phase 1 D-10 / EVAL-11): new endgame coefficients per D-12 ride this pipeline — no new codegen needed for them.

### Established Patterns

- **V6 source is reference, not import**: V7's TT layout per D-09 mirrors V6's bit-pack verbatim, but no shared code (CLAUDE.md constraint: V1–V6 untouched).
- **Build-host human checkpoints for runtime gates**: established by Phase 1 `.continue-here.md` and Phase 2 Task 3. Phase 3 baseline gauntlet (D-02), tier gauntlets (D-05), TSan stress (D-08), fortress validation (D-11), and ship SPRT all follow this pattern.
- **UCI options as both shipping config and ablation lever** (new pattern this phase): default ON for refinements, default OFF for risky/unvalidated terms (fortress). Same UCI surface used for production play and gauntlet A/B.

### Integration Points

- **Plan 03-01 → all later 03 plans**: Plan 03-01's scaffold (persistent killers/history, triangular PV, info.depth contract) is the substrate Plans 03-02/03-03 extend. No later plan re-creates this scaffold.
- **Plan 03-05 (TT) ↔ Plan 03-02/03-03 (search)**: search refinements PROBE the TT but don't restructure it. File-disjoint at edit time (`tt.cpp` vs `search.cpp`). Build-coupled at verify time: search.cpp `#include "tt.hpp"` for the API; Plan 03-05 must NOT change the `TTEntry` probe/store API surface used by search.
- **Plan 03-04 (endgame) ↔ Plan 03-02/03-03 (search)**: endgame eval is invoked from `evaluate()`; search refinements consume `evaluate()` results. File-disjoint (`eval.cpp` + new `endgame.cpp` vs `search.cpp`). Coeffs.json schema must be coordinated (Phase 1 D-10 contract holds).
- **D1 (Plan 03-05) → Phase 4 prerequisite**: Lazy SMP cannot start until lockless TT is TSan-verified. Hard gate per ROADMAP and PITFALLS #36.

</code_context>

<specifics>
## Specific Ideas

- Stockfish's TT layout / Hyatt-Mann implementation is the canonical reference for D-07 but **do not copy code** — write V7's own implementation matching V6's bit packing per D-09.
- KPK ground-truth comparison for D-10 acceptance: probe Fathom for all 163,328 KPK positions during `gen_kpk.py` execution and require 100% agreement before the .cpp is emitted. Fastest correct way to avoid hand-rolled bugs.
- Per Pitfall 5 evidence requirement, Success Criterion #4 (singular-on vs singular-off NPS within 10%) needs an explicit test that runs both `UseSingular=true` and `UseSingular=false` on the same bench position and computes the ratio. Add this as a pytest sentinel (gated by `RUN_BENCHMARKS=1` like NPS sentinel).
- "// V6 parity" comments in V7 search are NOT trustworthy as written (per memory: that's how the Phase 1 perf bugs slipped through). Plan 03-01 must verify against V6 source directly for every claim it carries forward.
- Phase 3 ship SPRT uses the same opening book / TC / concurrency as the V6-vs-V6 sanity probe (Phase 2 D-08 + D-10 + D-11) so results are comparable.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-slot TT buckets (4-way cluster)**: deferred from D-07. Add in Phase 4 if SMP hit-rate measurement demonstrates need.
- **Bucket-of-N replacement policy / `TTReplacementPolicy` UCI option**: deferred from D-07. Single age-then-depth policy is Phase 3 scope.
- **Widened TT entry fields (static-eval cache, generation 8b)**: deferred from D-09. Inherit V6's layout verbatim; revisit only if Phase 4 profiling demands.
- **One-plan-per-refinement gauntlet rigor**: rejected in D-04 in favor of tiered approach; if mid-tier mini-gauntlet shows regression, bisect via UCI toggle (D-06), not by replanning.
- **Per-tier full SPRT (instead of mini-gauntlet)**: rejected in D-05; mini-gauntlet + final ship-SPRT is the cadence.
- **Opening book at play time**: V2-STR-04, not Phase 3.
- **MultiPV mode**: V2-UX-04, not Phase 3.
- **Eval breakdown / diagnostics UI**: V2-UX-02/03, not Phase 3.
- **Conservative-only fortress (locked pawn chains only)**: rejected mid-discussion in favor of full ENDG-05 framework behind default-OFF UCI toggle (D-11).

### Reviewed Todos (not folded)

None — `gsd-sdk query todo.match-phase 3` returned no matches.

</deferred>

---

*Phase: 3-Lockless TT + Search Refinements + Endgame*
*Context gathered: 2026-05-17*
