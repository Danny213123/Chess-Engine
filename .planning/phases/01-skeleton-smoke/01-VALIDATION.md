---
phase: 1
slug: skeleton-smoke
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing — see `tests/`, configured via `pyproject.toml` `[dependency-groups].dev`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python3 -m uv run --group dev pytest tests/test_v7_engine.py -q` |
| **Full suite command** | `python3 -m uv run --group dev pytest -q` |
| **Estimated runtime** | ~30 seconds (quick), ~120 seconds (full incl. perft) |

---

## Sampling Rate

- **After every task commit:** Run quick command for the touching plan's test file
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Populated by the planner during plan generation. Each PLAN.md task with an `<automated>` verify clause must add a row here referencing the requirement IDs from ROADMAP.md §Phase 1 (FOUND-01..07, SRCH-01/02/13/14/15, EVAL-01..11, TB-01..10, INT-01..09).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD     | TBD  | TBD  | TBD         | —          | —               | TBD       | TBD               | ❌ W0       | ⬜ pending |
| 02-T2   | 02   | 2    | FOUND-06    | T-02-01    | V7 perft matches V6 perft on canonical 5-position corpus | unit/parity | `python3 -m uv run --group dev pytest tests/test_v7_perft.py -q -m "not slow"` | ✅          | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-01     | T-03-04    | Iterative deepening commits best_move at each completed depth | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_iterative_deepening -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-02     | T-03-02    | Aspiration re-search cap (=4 widenings) prevents wall-clock blowout | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_aspiration_cap -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-13     | T-03-01    | Mate scores survive TT round-trip with correct ply adjustment | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_mate_score_tt -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-14     | T-03-06    | In-tree 3-fold repetition returns DRAW_SCORE via Engine-owned RepStack | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_repetition_in_tree -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-14     | T-03-06    | TT cutoff refused when halfmove_clock >= 80 (50-move guard) | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_50move_tt_cutoff -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-15     | T-03-03    | TimeManager honors per-move budget end-to-end via wall clock | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_time_management_budget -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-15     | T-03-03    | >=10% safety margin clamp enforced at TimeManager.allocate | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_time_management_safety_margin -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-15     | T-03-04    | Tight time budget never returns MOVE_NONE (depth 1 always completes) | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_time_management_returns_best_so_far -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | FOUND-04    | —          | Engine.stop() interrupts active search within 50 ms via SearchInfo.external_stop | unit/latency | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_cancellation_latency_during_real_search -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_v7_engine.py` — stubs for INT-07 (legal-game smoke, perft parity, cancellation latency, NPS sentinel)
- [ ] `tests/test_v7_perft.py` — stubs for FOUND-06 (Kiwipete + position 3 + position 4 + starting position to depth 6)
- [ ] `tests/test_v7_search.py` — stubs for SRCH-01/02/13/14/15 (PVS correctness, mate-score TT, repetition, time management unit tests)
- [ ] `tests/test_v7_syzygy.py` — stubs for TB-01..10 (init-time log lines per D-08, KRk smoke probe, in-search probe failure handling)
- [ ] `tests/test_v7_bindings.py` — stubs for FOUND-04, FOUND-05 (SearchInfo wired through, GIL released)
- [ ] No new framework install — pytest already present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full UI smoke: open React UI, select V7 vs V6, press play, observe legal complete game | Success Criterion 3 (D-04 C1 milestone) | End-to-end browser interaction — no Selenium harness in this milestone | 1) `npm run dev --prefix client` and `python -m chess_engine.server.app` 2) Select V7 (white), V6 (black), depth 6 3) Press play, observe move-by-move 4) Game must finish without crashes or illegal moves |
| Press Stop mid-search, observe ≤50 ms cancellation | Success Criterion 4 (FOUND-04) | UI-driven cancellation latency observed manually; the unit test covers the C++ contract | Same setup as above; during V7's turn press Stop and visually confirm responsiveness |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
