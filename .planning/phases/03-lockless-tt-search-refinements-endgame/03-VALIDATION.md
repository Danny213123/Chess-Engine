---
phase: 3
slug: lockless-tt-search-refinements-endgame
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-17
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
| **Quick run command** | `python3 -m uv run --group dev pytest -q tests/v7/` |
| **Full suite command** | `python3 -m uv run --group dev pytest -q && bash tests/v7/run_tsan_stress.sh` |
| **Estimated runtime** | ~30s pytest quick / ~90s full (60s TSan + 30s pytest) |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m uv run --group dev pytest -q tests/v7/`
- **After every plan wave:** Run full suite (pytest + TSan harness)
- **Before `/gsd-verify-work`:** Full suite + ≥30 Elo gauntlet vs Phase 1 baseline V7
- **Max feedback latency:** 30 seconds (quick) / 90 seconds (full)

---

## Per-Task Verification Map

*Populated by the planner from PLAN.md task IDs after Step 8.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | ⬜ pending |

---

## Wave 0 Requirements

*From RESEARCH.md § Wave 0 Gaps. Final list locked in PLAN.md 03-01.*

- [ ] `tests/v7/test_tt_lockless_invariants.py` — Hyatt-Mann XOR probe/store unit tests (PAR-01..03)
- [ ] `tests/v7/test_search_refinements.py` — LMR/null/LMP/RFP/futility unit tests (SRCH-03..08)
- [ ] `tests/v7/test_move_ordering.py` — killer/history/counter/SEE ordering tests (SRCH-09..12)
- [ ] `tests/v7/test_singular_extensions.py` — singular gating + multi-cut + ProbCut (SRCH-07, SRCH-11)
- [ ] `tests/v7/test_kpk_bitbase.py` — all 163,328 KPK positions vs Fathom oracle (ENDG-01)
- [ ] `tests/v7/test_endgame_opposition.py` — opposition + wrong-bishop+rook-pawn (ENDG-02, ENDG-03)
- [ ] `tests/v7/test_phase_blend.py` — monotonicity of Stockfish-style phase blend (ENDG-04)
- [ ] `tests/v7/test_fortress_hints.py` — optional fortress detection (ENDG-05)
- [ ] `tests/v7/sentinel_lmr_depth_vs_time.py` — LMR-on must reach deeper depth at fixed time (Success Criterion #4)
- [ ] `tests/v7/sentinel_singular_nps_ratio.py` — `|NPS(singular_on) - NPS(singular_off)| / NPS_off < 0.10` (Success Criterion #4, Pitfall 5)
- [ ] `tests/v7/run_tsan_stress.sh` + `src/chess_engine/engine/v7/tt_tsan_stress.cpp` — 16-thread × 60s stress, zero races, zero illegal moves (Success Criterion #1)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Head-to-head ≥30 Elo gauntlet vs Phase 1 baseline V7 | Success Criterion #2 | Requires multi-hour gauntlet run via Phase 2 harness; not gated per-commit | `python -m chess_engine.cli.gauntlet --challenger v7-phase3 --baseline v7-phase1 --target-elo 30 --confidence 0.95` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (11 files above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s (full suite)
- [ ] `nyquist_compliant: true` set in frontmatter after planner pass

**Approval:** pending
