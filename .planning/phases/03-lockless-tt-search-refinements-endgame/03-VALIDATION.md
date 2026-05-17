---
phase: 3
slug: lockless-tt-search-refinements-endgame
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-17
revised: 2026-05-17
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Populated by gsd-planner from `03-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (Python harness) + standalone C++ TSan executable |
| **Config file** | `pyproject.toml` (pytest), `src/chess_engine/engine/v7/CMakeLists.txt` (TSan target) |
| **Quick run command** | `python3 -m uv run --group dev pytest -q tests/test_v7_*.py` |
| **Full suite command** | `python3 -m uv run --group dev pytest -q && bash scripts/tt_tsan_stress.sh` |
| **Estimated runtime** | ~30s pytest quick / ~90s full (60s TSan + 30s pytest) |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m uv run --group dev pytest -q tests/test_v7_*.py`
- **After every plan wave:** Run full suite (pytest + TSan harness)
- **Before `/gsd-verify-work`:** Full suite + ≥30 Elo gauntlet vs Phase 1 baseline V7
- **Max feedback latency:** 30 seconds (quick) / 90 seconds (full)

---

## Per-Task Verification Map

*Hand-filled from PLAN.md task lists across 03-01..03-06. Test files live flat under `tests/` per Phase 1/2 convention (no `tests/v7/` subdirectory).*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-T1 | 03-01 | 1 | D-01, D-03 (Phase 1 perf bugs) | T-03-01 | SearchInfo pointer wired by Engine; lifetime owned by Engine | unit + grep | `pytest tests/test_v7_search.py tests/test_v7_engine.py -q -x` | yes (existing) | ⬜ pending |
| 03-01-T2 | 03-01 | 1 | D-04 cross-Wave-2 scaffold (non_pawn_material, EngineOptions×12, set_option dispatcher, MovePicker stub) | n/a (scaffolding) | All scaffold pieces compile; existing V7 tests still green | unit + grep | `pytest tests/test_v7_search.py tests/test_v7_engine.py -q -x` | yes (existing) | ⬜ pending |
| 03-01-T3 | 03-01 | 1 | Wave 0 PAR-01..03, SRCH-03..12, ENDG-01..05 | n/a (scaffolding) | All stubs collect under pytest without ImportError | collect-only | `pytest tests/test_v7_tt_lockless.py tests/test_v7_search_refinements.py tests/test_v7_move_picker.py tests/test_v7_history.py tests/test_v7_lmr_depth.py tests/test_v7_singular_nps_ratio.py tests/test_v7_kpk_bitbase.py tests/test_v7_endgame.py tests/test_v7_phase_blend.py --collect-only -q` | created by 03-01-T3 | ⬜ pending |
| 03-01-T4 | 03-01 | 1 | D-02 baseline gauntlet | n/a | summary.json committed to .planning/gauntlets/baseline-phase3/ | checkpoint:human-verify (build host) | manual gauntlet run | created by checkpoint | ⬜ pending |
| 03-02-T1 | 03-02 | 2 | SRCH-03, SRCH-04, SRCH-05 | T-03-02 | Null/LMR/RFP/futility/LMP gated by EngineOptions toggles | unit + grep | `pytest tests/test_v7_search_refinements.py::test_null_move_skipped_in_kp_endgame tests/test_v7_search_refinements.py::test_rfp_prunes_above_margin tests/test_v7_search_refinements.py::test_lmp_late_move_pruning tests/test_v7_search.py tests/test_v7_engine.py -q -x` | tests/test_v7_search_refinements.py | ⬜ pending |
| 03-02-T2 | 03-02 | 2 | SRCH-06, SRCH-11, SRCH-12 | T-03-02 | Staged picker yields canonical order; IIR skips if excluded_move set | unit + grep | `pytest tests/test_v7_move_picker.py tests/test_v7_search_refinements.py::test_iir_reduces_no_tt_move tests/test_v7_search_refinements.py::test_recapture_extension tests/test_v7_search.py tests/test_v7_engine.py -q -x` | tests/test_v7_move_picker.py, tests/test_v7_search_refinements.py | ⬜ pending |
| 03-02-T3 | 03-02 | 2 | D-06 UCI toggles (Tier-1 wiring) | T-03-X1, T-03-X2 | set_option dispatcher rejects malformed values; emits info string | grep + UCI handshake | `pytest tests/test_v7_search.py tests/test_v7_engine.py tests/test_v7_search_refinements.py tests/test_v7_move_picker.py -q -x` + build-host UCI smoke | n/a (extends scaffold) | ⬜ pending |
| 03-02-T4 | 03-02 | 2 | D-05 tier-1 mini-gauntlet | T-03-02 | Elo lower-bound > -10 vs baseline-phase3 | checkpoint:human-verify (build host) | manual gauntlet run | created by checkpoint | ⬜ pending |
| 03-03-T1 | 03-03 | 2 | SRCH-07 (continuation + capture history) | T-03-X3 | History accumulates on cutoff; aged on new_search | unit + grep | `pytest tests/test_v7_history.py tests/test_v7_search.py tests/test_v7_engine.py -q -x` | tests/test_v7_history.py | ⬜ pending |
| 03-03-T2 | 03-03 | 2 | SRCH-08, SRCH-09, SRCH-10 | T-03-02, T-03-X3 | excluded_move TT-probe skip invariant; singular NPS ratio < 10% | unit + benchmark | `pytest tests/test_v7_search_refinements.py tests/test_v7_search.py tests/test_v7_engine.py -q -x` + `RUN_BENCHMARKS=1 pytest tests/test_v7_singular_nps_ratio.py -q -x` | tests/test_v7_singular_nps_ratio.py | ⬜ pending |
| 03-03-T3 | 03-03 | 2 | D-05 tier-2 mini-gauntlet + ProbCut bisection | T-03-X4 | Elo lower-bound > -10; ProbCut default decision committed | checkpoint:human-verify (build host) | manual gauntlet run | created by checkpoint | ⬜ pending |
| 03-04-T1 | 03-04 | 2 | ENDG-01 (KPK codegen + Fathom oracle) | T-03-03 | kpk_bitbase.cpp gitignored; 163,328 positions match Fathom | unit (gitignore) + slow oracle (build host) | `pytest tests/test_v7_kpk_bitbase.py::test_kpk_cpp_gitignored -q -x` | tests/test_v7_kpk_bitbase.py | ⬜ pending |
| 03-04-T2 | 03-04 | 2 | ENDG-02, ENDG-03, ENDG-04, ENDG-05 | T-03-X5, T-03-X6 | Opposition pinned to chessprogramming.org/Opposition; wrong-bishop draws; phase blend monotonic | unit | `pytest tests/test_v7_endgame.py tests/test_v7_phase_blend.py tests/test_v7_search.py tests/test_v7_engine.py -q -x` | tests/test_v7_endgame.py, tests/test_v7_phase_blend.py | ⬜ pending |
| 03-04-T3 | 03-04 | 2 | D-10 KPK oracle + D-11 fortress validation + D-05 endgame mini-gauntlet | T-03-X6, T-03-X7 | 100% Fathom agreement; fortress default decision documented | checkpoint:human-verify (build host) | manual gauntlet runs | created by checkpoint | ⬜ pending |
| 03-05-T1 | 03-05 | 2 | PAR-01, PAR-02 (lockless TT pack/unpack) | T-03-01 | XOR-validated probe/store; relaxed memory order | unit + grep | `pytest tests/test_v7_tt_lockless.py -q -x` | tests/test_v7_tt_lockless.py | ⬜ pending |
| 03-05-T2 | 03-05 | 2 | PAR-03 TSan stress harness | T-03-01 | 16-thread × 60s stress; zero races, zero illegal moves | shell + C++ executable (build host) | `bash scripts/tt_tsan_stress.sh` | scripts/tt_tsan_stress.sh, src/chess_engine/engine/v7/tt_tsan_stress.cpp | ⬜ pending |
| 03-05-T3 | 03-05 | 2 | D-05 lockless TT mini-gauntlet + TSan verdict | T-03-01 | Elo lower-bound > -10; TSan clean | checkpoint:human-verify (build host) | manual gauntlet + TSan run | created by checkpoint | ⬜ pending |
| 03-06-T1 | 03-06 | 3 | Success Criterion #2 (≥30 Elo ship SPRT) | n/a | Full Phase 3 stack vs Phase 1 baseline V7 via SPRT | checkpoint:human-verify (build host) | manual SPRT gauntlet run | created by checkpoint | ⬜ pending |
| 03-06-T2 | 03-06 | 3 | Success Criterion #1 (NPS ≥ 80% of V6) + #4 (singular NPS) | n/a | NPS sentinels green on build host | benchmark | `RUN_BENCHMARKS=1 pytest tests/test_v7_engine.py::test_nps_sentinel tests/test_v7_lmr_depth.py tests/test_v7_singular_nps_ratio.py -q -x` | tests/test_v7_*.py (existing) | ⬜ pending |

---

## Wave 0 Requirements

*Locked in PLAN.md 03-01 Task 2. Paths are flat under `tests/` per Phase 1/2 convention.*

- [x] `tests/test_v7_tt_lockless.py` — Hyatt-Mann XOR probe/store unit tests (PAR-01, PAR-02)
- [x] `tests/test_v7_search_refinements.py` — null-move/LMR/RFP/futility/LMP/IIR/recapture/multicut/singular tests (SRCH-03, SRCH-05, SRCH-09, SRCH-11, SRCH-12)
- [x] `tests/test_v7_move_picker.py` — staged TT/captures/killers/counter/history quiet ordering (SRCH-06)
- [x] `tests/test_v7_history.py` — main/continuation/capture history accumulation + aging + counter-mover invariant (SRCH-07, RESEARCH.md Pitfall 7)
- [x] `tests/test_v7_lmr_depth.py` — RUN_BENCHMARKS=1 sentinel: LMR-on must reach deeper depth at fixed time (SRCH-04, Success Criterion #4)
- [x] `tests/test_v7_singular_nps_ratio.py` — RUN_BENCHMARKS=1 sentinel: `|NPS(singular_on) - NPS(singular_off)| / NPS_off < 0.10` (SRCH-08, Success Criterion #4, Pitfall 5)
- [x] `tests/test_v7_kpk_bitbase.py` — all 163,328 KPK positions vs Fathom oracle + .gitignore assertion (ENDG-01, D-10)
- [x] `tests/test_v7_endgame.py` — opposition, wrong-bishop+rook-pawn, fortress detection (ENDG-02, ENDG-03, ENDG-05)
- [x] `tests/test_v7_phase_blend.py` — monotonicity + startpos=256 + bare-kings=0 (ENDG-04, RESEARCH.md Pitfall 6)
- [x] `scripts/tt_tsan_stress.sh` — shell harness invoking the C++ stress executable (PAR-03)
- [x] `src/chess_engine/engine/v7/tt_tsan_stress.cpp` — 16-thread × 60s probe/store stress driver, zero races (PAR-03, Success Criterion #1)

All 11 paths are created as Wave 0 stubs by Plan 03-01 Task 2 (per its `files_modified` frontmatter). Plans 03-02..05 fill in test bodies; the shell + C++ harness are implemented in full by Plan 03-05.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Head-to-head ≥30 Elo gauntlet vs Phase 1 baseline V7 | Success Criterion #2 | Requires multi-hour gauntlet run via Phase 2 harness; not gated per-commit | `python tools/gauntlet.py run --challenger v7 --baseline-summary .planning/gauntlets/baseline-phase3/summary.json --games <SPRT> --tc 10+0.1 --book tools/8moves_v3.pgn --concurrency 1 --out .planning/gauntlets/ship/` |
| Baseline-phase3 gauntlet (canonical reference) | D-02 | 500-game wall-clock run | Plan 03-01 Task 3 checkpoint |
| Per-tier mini-gauntlets (tier-1, tier-2, endgame, lockless-TT) | D-05 | 200-game wall-clock runs per tier | Plan 03-02 T4 / 03-03 T3 / 03-04 T3 / 03-05 T3 checkpoints |
| Fortress validation gauntlet | D-11 | 500-game scoped run decides UseFortressEval default | Plan 03-04 Task 3 checkpoint |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (per Per-Task Verification Map above)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (checkpoints are interleaved with autonomous tasks; each autonomous task has its own `<automated>` block)
- [x] Wave 0 covers all MISSING references (11 files above; created in 03-01 Task 2)
- [x] No watch-mode flags (pytest invocations use `-q -x` — single-shot)
- [x] Feedback latency < 90s (full suite ≤ 90s per Test Infrastructure table)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (planner pass, revision 1 — Per-Task map hand-filled, paths corrected to flat `tests/test_v7_*.py` layout)
