---
phase: 2
slug: gauntlet-harness-early
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-16
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from RESEARCH.md §9 (Validation Architecture).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing; uv-managed dev group) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]` — existing) |
| **Quick run command** | `python3 -m uv run --group dev pytest -q tests/test_gauntlet*.py` |
| **Full suite command** | `python3 -m uv run --group dev pytest -q` |
| **Estimated runtime** | ~30s quick / ~2 min full (no `RUN_BENCHMARKS=1`); +30-60 min when sanity probe runs |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m uv run --group dev pytest -q tests/test_gauntlet*.py` (unit/contract tests only — fast)
- **After every plan wave:** Run full suite without `RUN_BENCHMARKS` (still fast — bench/SPRT not exercised)
- **Before `/gsd-verify-work`:** Full suite green; then `RUN_BENCHMARKS=1` pytest must pass (NPS sentinel reads latest `summary.json`)
- **Manual / one-off:** V6-vs-V6 sanity gauntlet (D-10) runs once per harness change — wall-clock 30-60 min, not on every commit
- **Max feedback latency:** 30 seconds for unit tests; bench/SPRT gated behind explicit env var

---

## Per-Task Verification Map

> Populated by the planner once PLAN.md files exist. Each task in every PLAN.md must map here with an automated verify command or a Wave 0 dependency.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD     | TBD  | TBD  | GAUNT-XX    | —          | N/A             | TBD       | TBD               | ❌ W0       | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Per RESEARCH.md §7, three prereq tasks must land before any harness work is meaningful:

- [ ] `v6_uci` CMake target — V6 currently has no standalone UCI binary (only `v6_engine` pybind11 module). fastchess needs a process to spawn.
- [ ] `setoption` parser in `v7_uci` (and new `v6_uci`) — `src/chess_engine/engine/v7/src/uci_main.cpp:207-210` silently drops options; fastchess `Hash`/`Threads` will not propagate without it.
- [ ] `wtime`/`btime` parsing in `v7_uci` — `src/chess_engine/engine/v7/src/uci_main.cpp:184` ignores TC fields; without it every move runs at the hardcoded 5s default regardless of `tc=10+0.1`.

Then for test scaffolding:

- [ ] `tests/test_gauntlet_runner.py` — unit tests for `tools/gauntlet.py` argument wiring and `summary.json` schema
- [ ] `tests/test_fetch_fastchess.py` — checksum cache + OS dispatch
- [ ] `tests/test_nps_regression.py` — extends Phase 1 `test_nps_sentinel`; reads latest `.planning/gauntlets/*/summary.json`
- [ ] `tests/conftest.py` — gauntlet fixture (tmp `.planning/gauntlets/` root, fake `summary.json` factory)

*Pytest infrastructure already exists from Phase 1 — no framework install.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| V6-vs-V6 sanity probe returns Elo within ±15 over 200 games | GAUNT-04 | 30-60 min wall clock; not suitable for CI on every commit | Run `python tools/gauntlet.py sanity --games 200`; inspect `.planning/gauntlets/<ts>/summary.json` Elo field |
| fastchess command line in `summary.json` reproduces a prior run bit-for-bit on same hardware | GAUNT-03 | Reproducibility check spans days/weeks; requires hardware stability | Pick an older `summary.json`, copy the `command` field, re-run, diff results |
| First V7-vs-V6 SPRT verdict | (deferred per D-09) | Blocked on Phase 1 gap-closure (3 perf bugs) | Out of scope for Phase 2 completion |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (incl. `v6_uci`, setoption parser, wtime parser)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s on commit-tier tests
- [ ] `nyquist_compliant: true` set in frontmatter after planner populates the verification map

**Approval:** pending
