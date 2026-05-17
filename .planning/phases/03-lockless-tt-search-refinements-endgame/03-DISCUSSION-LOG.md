# Phase 3: Lockless TT + Search Refinements + Endgame - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 3-Lockless TT + Search Refinements + Endgame
**Areas discussed:** Perf-bug sequencing, Refinement landing + gauntlet cadence, TT redesign vs port-with-XOR, Endgame eval architecture

---

## Perf-bug sequencing

### Q1 — Where do the 3 Phase 1 perf-bug fixes land?

| Option | Description | Selected |
|--------|-------------|----------|
| Gap-closure plan BEFORE Phase 3 | Build-host detour first; clean baseline for Phase 3 measurements | |
| First plan of Phase 3 (03-01) | Make perf-fix Plan 01 of Phase 3; gauntlet after to lock baseline | ✓ |
| Fold silently into the search refactor | No separate fix step — search refactor naturally replaces this code | |

**User's choice:** Plan 03-01 (first plan of Phase 3).

### Q2 — Should we run a gauntlet immediately after 03-01?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — blocking checkpoint after 03-01 | 500-game gauntlet, persist as baseline.json | ✓ |
| No — use last Phase 2 sanity-probe summary as baseline | Skip dedicated baseline run | |
| Yes — but mini-gauntlet (200 games) and store as baseline.json | Smaller but ~±25 Elo CI | |

**User's choice:** Blocking 500-game checkpoint, persisted as baseline.

### Q3 — How should 03-01 handle killers/history and PV scaffolding?

| Option | Description | Selected |
|--------|-------------|----------|
| Build the production scaffold in 03-01 | Persistent killers/history, triangular PV, info.depth contract | ✓ |
| Minimal-diff fix in 03-01, refactor in later plans | Smallest possible fix; later plans pay refactor tax | |

**User's choice:** Build production scaffold (substrate for 03-02/03-03 refinements).

---

## Refinement landing + gauntlet cadence

### Q1 — Plan grouping for 10 search refinements?

| Option | Description | Selected |
|--------|-------------|----------|
| Two tiers: proven first, aggressive second | 03-02 = SRCH-03/04/05/06/11/12; 03-03 = SRCH-07/08/09/10 | ✓ |
| One plan per refinement (~10 plans) | 10× build-host detours | |
| Single big-bang plan with UCI-toggle A/B | One implementation plan + A/B matrix exercise | |

**User's choice:** Two tiers.

### Q2 — Mid-Phase-3 validation bar?

| Option | Description | Selected |
|--------|-------------|----------|
| Mini-gauntlet ≥0 Elo (non-regression) | 200g per tier; final 500–1000g SPRT at phase end | ✓ |
| Mini-gauntlet +20 Elo per tier | Stricter; needs ~500–1000g per tier | |
| Full SPRT after each tier | Most rigorous; hours–overnight per tier | |

**User's choice:** Non-regression mini-gauntlet per tier; full SPRT at phase end.

### Q3 — Per-feature UCI toggles?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, default ON — toggles for diagnostics only | 11 UCI options (`UseLMR`, `UseSingular`, etc.) | ✓ |
| Only for SRCH-08 (singular) and SRCH-04 (LMR) | Strictly minimum needed for Success Criterion #4 | |
| No toggles — always-on | Violates Success Criterion #4 | |

**User's choice:** Full toggle set, default ON.

---

## TT redesign vs port-with-XOR

### Q1 — TT bucket structure?

| Option | Description | Selected |
|--------|-------------|----------|
| Two atomic<u64> slots: xkey + data, single entry | Pure Hyatt-Mann, Stockfish/Berserk-validated | ✓ |
| 4-way bucket (cluster) from day one | Higher hit rate at thread counts; ~3× complexity | |
| Single-entry buckets, design replacement policy now | Pluggable policy via UCI option | |

**User's choice:** Single-entry Hyatt-Mann; multi-slot deferred.

### Q2 — TSan verification recipe?

| Option | Description | Selected |
|--------|-------------|----------|
| WSL recipe + manual human-checkpoint | `scripts/tt_tsan_stress.sh`; deferred to WSL/Linux/macOS | ✓ |
| Same as above + pytest Python-thread stress | Weaker signal but always-runnable | |
| Skip TSan; rely on code review | Would amend PAR-03 | |

**User's choice:** WSL human-checkpoint, matching Phase 1/2 pattern.

### Q3 — TT entry packing?

| Option | Description | Selected |
|--------|-------------|----------|
| Inherit V6's bit-pack layout verbatim | Mirror move/score/depth/bound/age fields; wrap in atomic<u64> | ✓ |
| Redesign packing for Phase 3 needs | Add static-eval cache, widened age, new bound flags | |

**User's choice:** Inherit V6 verbatim.

---

## Endgame eval architecture

### Q1 — KPK bitbase generation?

| Option | Description | Selected |
|--------|-------------|----------|
| Build-time codegen → static const array | `tools/gen_kpk.py` → `kpk_bitbase.cpp` (~32 KB); mirrors coeffs.cpp pattern | ✓ |
| Startup-time generation in C++ | ~10–100ms init cost; no committed blob | |
| Compile-time constexpr generation | Stresses MSVC constexpr depth; risky | |

**User's choice:** Build-time codegen, mirroring `gen_coeffs.py` pattern.

### Q2 — ENDG-05 (fortress hints) go/no-go?

| Option | Description | Selected |
|--------|-------------|----------|
| Skip ENDG-05 — mark Done-by-Deferral | Amend REQUIREMENTS.md ENDG-05 to skipped | |
| Ship a minimal hint: OCB draw scaling only | ~30 LOC; conservative | |
| Full ENDG-05 — attempt the general framework | High false-positive risk, against requirement's escape hatch | ✓ |

**User's choice:** Full ENDG-05 framework (against initial recommendation — safety net captured in Q3).

### Q3 — ENDG-05 safety net?

| Option | Description | Selected |
|--------|-------------|----------|
| Behind a UCI toggle, default OFF until validated | `UseFortressEval` default OFF; separate validation gauntlet | ✓ |
| Ship default ON; gauntlet catches regression at Phase 3 end | Risks burning the entire ship SPRT on a fortress regression | |
| Conservative scope: only locked-pawn-chain detection | Partial ENDG-05 | |

**User's choice:** Default OFF + scoped validation gauntlet.

### Q4 — New endgame eval coefficients in Texel pipeline?

| Option | Description | Selected |
|--------|-------------|----------|
| Add to coeffs.json now — Phase 4 Texel tunes them | Flow through existing gen_coeffs.py pipeline | ✓ |
| Hand-tune in C++ constants — outside Texel | Faster Phase 3; Phase 4 can't joint-optimize | |
| KPK + opposition in coeffs.json; fortress hand-tuned | Split per term | |

**User's choice:** All endgame coefficients in coeffs.json.

---

## Claude's Discretion

- Exact plan-to-wave parallelism (D1 vs D2/D3 sequencing) — planner's call given file-disjoint constraint
- UCI option naming details so long as `Use<Refinement>` convention is honored
- `tools/gen_kpk.py` location (top-level `tools/` vs `src/chess_engine/engine/v7/tools/`)
- Triangular PV `MAX_PLY` value
- Whether singular/multi-cut/ProbCut share verification helpers

## Deferred Ideas

- Multi-slot TT buckets (4-way cluster) — Phase 4 if measurement demands
- Bucket-of-N replacement policy + UCI option — Phase 4 if measurement demands
- Widened TT entry fields (eval cache, generation 8b) — Phase 4 if profiling demands
- One-plan-per-refinement rigor — rejected in favor of tiered approach
- Per-tier full SPRT — rejected in favor of mini-gauntlet + final-SPRT cadence
- Conservative-only fortress (locked pawn chains) — rejected in favor of full framework default-OFF
- Opening book at play time (V2-STR-04), MultiPV (V2-UX-04), eval UI (V2-UX-02/03) — all out of milestone
