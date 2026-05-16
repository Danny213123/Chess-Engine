# Phase 1: Skeleton + Smoke - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 1-skeleton-smoke
**Areas discussed:** Initial eval coefficients, Smoke milestone definition, Syzygy missing-path behavior, coeffs.cpp codegen mechanics

---

## Initial Eval Coefficients

| Option | Description | Selected |
|--------|-------------|----------|
| Copy V6's values verbatim | Lift V6's PSTs / mobility / king-safety into coeffs.json. Phase 1 plays at ~V6 strength. Phase 4 tuning Elo delta measured on top of V6 seed. | |
| Public Pesto/Stockfish-baseline values | Use public starting point (Pesto PSTs, classical material). Avoids V6 inheritance; non-V6 baseline. | ✓ |
| Neutral seed (material only) | Material values only; everything else zeroed. V7 plays weak chess in Phase 1; Phase 4 Elo gain unambiguous. | |

**User's choice:** Public Pesto/Stockfish-baseline values.
**Notes:** Pesto provides PSTs and tapered material. For non-PST terms (king-safety attack table, mobility, pawn structure, threats, bishop pair, tempo), use Pesto-derived values where they exist; otherwise modest hand-set values clearly marked `# initial; will be tuned Phase 4` in coeffs.json. This effectively makes V7 the "neutral seed" candidate in Phase 4's TUNE-08 multi-seed run; the V6-equivalent seed is constructed separately in Phase 4 if desired.

---

## Smoke Milestone Definition

| Option | Description | Selected |
|--------|-------------|----------|
| 1 game per color, fixed depth | V7 white vs V6, then V6 vs V7 black. Both must finish legally. Fast, deterministic. Doesn't exercise time management. | |
| 1 game per color, fixed time (e.g. 10s/move) | Same 2-game pair at fixed move time. Exercises SRCH-15. ~10-20 min. | |
| Mini-match: 4 games at fixed TC (alternating colors) | 4 games at short TC. Validates back-to-back game stability. ~15-30 min. | |
| Single game, V7 as white, fixed depth | Bare minimum: 1 game finishes legally. Phase 2's gauntlet covers the rest. | ✓ |

**User's choice:** Single game, V7 as white, fixed depth.
**Notes:** V7-as-black, time-management exercise, and back-to-back stability deferred to Phase 2's gauntlet harness. SRCH-15 (time management) still requires unit tests in Phase 1 — the end-to-end exercise just lives in Phase 2.

---

## Syzygy Missing-Path Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Tiered: silent if unset, log if invalid, fail if smoke probe fails | Three-tier handling. Refuses to lie about a corrupt install. | |
| Always log, never fail | Any TB issue → stderr notice, continue with tbhits=0. Engine always starts. | ✓ |
| Always fail if syzygyPath is set but unusable | Forces users to fix or unset. Cleanest semantics; highest first-time setup friction. | |

**User's choice:** Always log, never fail.
**Notes:** Engine must always start. Init-time stderr lines are spelled out in CONTEXT.md D-08 with one specific message per failure mode (unset / path missing / no .rtbw files / KRk smoke probe fail). TB-06 (in-search probe failures must NOT silently become draws) is an orthogonal in-search invariant — unaffected by init policy.

---

## coeffs.cpp Codegen Mechanics

| Option | Description | Selected |
|--------|-------------|----------|
| tools/gen_coeffs.py via CMake custom command on every build | Auto-regenerates if coeffs.json newer; no manual step. Python already required for pybind11 build. | ✓ |
| tools/gen_coeffs.py manual via npm script | `npm run gen:coeffs` (or CLI subcommand). coeffs.cpp committed; CI verifies sync. | |
| Hybrid: CMake auto + commit generated file | CMake auto-regenerates locally; coeffs.cpp also committed for reproducible builds. CI verifies match. | |

**User's choice:** Python script at tools/gen_coeffs.py, run as a CMake custom command on every build.
**Notes:** coeffs.cpp is generated and gitignored — coeffs.json is the single source of truth. Codegen output must be deterministic (sorted keys, fixed formatting, LF line endings) to avoid drift if a contributor accidentally commits a stale file.

---

## Claude's Discretion

None. All four selected gray areas were explicitly resolved by user choice.

## Deferred Ideas

- V6 SearchInfo bug backport — V7-only fix; V6 stays unchanged (milestone constraint).
- `logging` module migration — project-wide cleanup, not V7 scope.
- TUNE-08 V6-equivalent seed for Phase 4's multi-seed tuning — built separately in Phase 4 if desired.
- Time-management end-to-end exercise, V7-as-black smoke, back-to-back game stability — all Phase 2 gauntlet work.
- "Hybrid: CMake auto + commit generated file" for coeffs.cpp — rejected option; could be revisited if Phase 1 surfaces stale-file friction.
