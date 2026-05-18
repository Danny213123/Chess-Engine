---
phase: 4
slug: lazy-smp-texel-tuning
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-17
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Two file-disjoint workstreams (E1 Lazy SMP, E2 Texel pipeline) sequenced E1 → PAR-09 → E2 → SC#6 per CONTEXT D-14.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (Python harness for sentinels + bindings tests) + CTest (C++ unit shims, optional) + custom gauntlet runner (tools/gauntlet.py) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` (existing) |
| **Quick run command** | `python3 -m uv run --group dev pytest tests/v7/ -q -m "not benchmark and not gauntlet"` |
| **Full suite command** | `python3 -m uv run --group dev pytest tests/v7/ -q` (excludes benchmark + gauntlet markers) |
| **Benchmark suite** | `RUN_BENCHMARKS=1 python3 -m uv run --group dev pytest tests/v7/ -q -m benchmark` (PAR-07/PAR-08 sentinels — build host only) |
| **Gauntlet suite** | Invoked from `.continue-here.md` on build host, NOT in CI (PAR-09, seed-decider, SC#6, TUNE-09 rescale-verify) |
| **Estimated runtime — quick** | ~30 s (Python sentinels + binding smoke) |
| **Estimated runtime — full** | ~60 s (adds eval_quiet parity + tune harness smoke) |
| **Estimated runtime — benchmark** | ~5 min (NPS scaling + cancellation latency on build host) |
| **Estimated runtime — gauntlet** | hours-to-days per gauntlet (out of feedback loop; checkpoint-gated) |

---

## Sampling Rate

- **After every task commit:** Run **quick** suite (`pytest -m "not benchmark and not gauntlet"`).
- **After every plan wave:** Run **full** suite.
- **Before `/gsd-verify-work`:** Full suite green + applicable benchmark sentinels run (RUN_BENCHMARKS=1).
- **Before phase exit:** All four gauntlet checkpoints (PAR-09, seed-decider, SC#6, optional TUNE-09 rescale-verify) committed in `.continue-here.md` artifacts.
- **Max feedback latency:** ~60 s for non-benchmark sampling.

---

## Per-Task Verification Map

> Task IDs are illustrative; the planner finalizes them. Each plan covers the requirements listed.
> "W0" indicates Wave 0 scaffolding the test depends on.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-W0 | 04-01 | 0 | infra | — | n/a | scaffold | `pytest --collect-only tests/v7/test_lazy_smp.py` | ❌ W0 | ⬜ pending |
| 04-01-T1 | 04-01 | 1 | PAR-04 | — | Worker struct owns per-thread tables; helpers do not share | unit (C++ via pybind smoke) | `pytest tests/v7/test_lazy_smp.py::test_worker_state_isolation -q` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | PAR-05 | — | Workers communicate only via TT + stop_flag (no other shared state) | static / grep assertion | `pytest tests/v7/test_lazy_smp.py::test_no_shared_state -q` | ❌ W0 | ⬜ pending |
| 04-01-T3 | 04-01 | 1 | PAR-06 | — | Depth-stagger skip pattern applied; helper-N skips per Berserk-style table | unit | `pytest tests/v7/test_lazy_smp.py::test_depth_stagger_table -q` | ❌ W0 | ⬜ pending |
| 04-01-T4 | 04-01 | 1 | PAR-04 (Threads UCI option) | T-04-01 | `setoption name Threads value N` clamps to [1,256] and warns on invalid | integration | `pytest tests/v7/test_uci_threads.py -q` | ❌ W0 | ⬜ pending |
| 04-01-T5 | 04-01 | 2 | PAR-07 | — | 4t NPS ≥ 3.0× 1t NPS on bench position | benchmark sentinel | `RUN_BENCHMARKS=1 pytest tests/v7/test_nps_scaling.py -q -m benchmark` | ❌ W0 | ⬜ pending |
| 04-01-T6 | 04-01 | 2 | PAR-08 | — | `engine.stop()` from Python interrupts 4t deep search within <50 ms wall-clock | benchmark sentinel | `RUN_BENCHMARKS=1 pytest tests/v7/test_cancellation_4t.py -q -m benchmark` | ❌ W0 | ⬜ pending |
| 04-02-T1 | 04-02 | 1 | PAR-09 | — | 4t-V7 vs 1t-V7 self-play ≥40 Elo (pentanomial SPRT elo0=0 elo1=10) | gauntlet (manual checkpoint) | `tools/gauntlet.py --config gauntlets/phase4-par09.yaml` then human commits summary.json | ❌ W0 | ⬜ pending |
| 04-03-W0 | 04-03 | 0 | infra | — | n/a | scaffold | `pytest --collect-only tests/v7/test_texel_pipeline.py` | ❌ W0 | ⬜ pending |
| 04-03-T1 | 04-03 | 1 | TUNE-01 | — | texel-tuner vendored under tools/texel-tuner/ with pinned SHA recorded | filesystem assertion | `pytest tests/v7/test_texel_vendoring.py -q` | ❌ W0 | ⬜ pending |
| 04-03-T2 | 04-03 | 1 | TUNE-02 | — | `tools/fetch_tuning_data.py` idempotent, checksummed, OS-agnostic | unit | `pytest tests/v7/test_fetch_tuning_data.py -q` | ❌ W0 | ⬜ pending |
| 04-03-T3 | 04-03 | 1 | TUNE-03 | — | `filter_quiet_positions.py` drops `is_check`, `qsearch≠eval`, `popcount≤TB_LARGEST` | unit | `pytest tests/v7/test_quiet_filter.py -q` | ❌ W0 | ⬜ pending |
| 04-03-T4 | 04-03 | 2 | TUNE-04 | — | K fit once via golden-section in [0.5, 2.0], persisted in `coeffs.json _meta.K` | unit | `pytest tests/v7/test_k_fit.py -q` | ❌ W0 | ⬜ pending |
| 04-03-T5 | 04-03 | 2 | TUNE-05 | — | Sparse coefficient extraction enabled (vendored texel-tuner feature) | integration | `pytest tests/v7/test_sparse_extraction.py -q` | ❌ W0 | ⬜ pending |
| 04-03-T6 | 04-03 | 2 | TUNE-06 | — | 90/10 train/val split deterministic from seed; both losses decrease then plateau | unit | `pytest tests/v7/test_train_val_split.py -q` | ❌ W0 | ⬜ pending |
| 04-03-T7 | 04-03 | 2 | TUNE-07 | — | ADAM + L2 regularization wired; defaults documented | integration | `pytest tests/v7/test_adam_l2.py -q` | ❌ W0 | ⬜ pending |
| 04-03-T8 | 04-03 | 3 | TUNE-08 | — | Multi-seed driver runs Pesto + neutral-zeros (+ conditional perturbed); per-seed outputs in tools/.cache/tune-results/ | integration | `pytest tests/v7/test_multi_seed.py -q` | ❌ W0 | ⬜ pending |
| 04-03-T9 | 04-03 | 3 | SC#5 (eval parity) | — | `eval_quiet(STARTPOS)` returns identical value from Python tuner harness and v7_engine.evaluate() | integration | `pytest tests/v7/test_eval_quiet_parity.py -q` | ❌ W0 | ⬜ pending |
| 04-03-T10 | 04-03 | 1 | TUNE-01 (CMake) | — | `v7_eval_static` target builds; v7_engine + v7_uci + texel-tuner all link it | build assertion | `cmake --build build --target v7_eval_static && pytest tests/v7/test_eval_static_link.py -q` | ❌ W0 | ⬜ pending |
| 04-04-T1 | 04-04 | 1 | TUNE-09 | — | `avg_eval_after / avg_eval_before` computed; RFP/futility/ProbCut margins rescaled | unit | `pytest tests/v7/test_margin_rescale.py -q` | ❌ W0 | ⬜ pending |
| 04-04-T2 | 04-04 | 2 | TUNE-09 (rescale verify) | — | rescaled vs unscaled ≥200-game mini-gauntlet; lower-bound Elo ≥ −10 | gauntlet (manual checkpoint) | `tools/gauntlet.py --config gauntlets/phase4-rescale.yaml` | ❌ W0 | ⬜ pending |
| 04-04-T3 | 04-04 | 2 | TUNE-08 (seed decider) | — | Seed-decider round-robin (≥500 games per pair) picks winning seed | gauntlet (manual checkpoint) | `tools/gauntlet.py --config gauntlets/phase4-seeds.yaml` | ❌ W0 | ⬜ pending |
| 04-04-T4 | 04-04 | 3 | SC#6 | — | Tuned-V7 vs untuned-V7 ≥500-game mini-gauntlet, clearly measurable Elo margin | gauntlet (manual checkpoint) | `tools/gauntlet.py --config gauntlets/phase4-sc6.yaml` | ❌ W0 | ⬜ pending |
| 04-04-T5 | 04-04 | 3 | TUNE-10 | — | Human-checkpoint commit of winning `coeffs.json` + `_meta.K` to source | manual gate | git diff src/chess_engine/engine/v7/coeffs.json verified by human | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/v7/test_lazy_smp.py` — Worker isolation, no-shared-state, depth-stagger table (covers PAR-04, PAR-05, PAR-06)
- [ ] `tests/v7/test_uci_threads.py` — Threads setoption clamp + invalid-value warning (PAR-04 UCI surface)
- [ ] `tests/v7/test_nps_scaling.py` — RUN_BENCHMARKS=1 gated NPS scaling sentinel (PAR-07)
- [ ] `tests/v7/test_cancellation_4t.py` — RUN_BENCHMARKS=1 gated cancellation latency sentinel (PAR-08)
- [ ] `tests/v7/test_texel_vendoring.py` — texel-tuner SHA pin assertion (TUNE-01)
- [ ] `tests/v7/test_fetch_tuning_data.py` — Zurichess fetch idempotence + checksum (TUNE-02)
- [ ] `tests/v7/test_quiet_filter.py` — quiet-position filter unit tests (TUNE-03)
- [ ] `tests/v7/test_k_fit.py` — golden-section K convergence + persistence in coeffs.json _meta.K (TUNE-04)
- [ ] `tests/v7/test_sparse_extraction.py` — sparse mode round-trip via vendored tuner (TUNE-05)
- [ ] `tests/v7/test_train_val_split.py` — deterministic 90/10 split, loss curve monotonicity (TUNE-06)
- [ ] `tests/v7/test_adam_l2.py` — ADAM hyperparam wiring + regularization unit (TUNE-07)
- [ ] `tests/v7/test_multi_seed.py` — multi-seed driver smoke (TUNE-08)
- [ ] `tests/v7/test_eval_quiet_parity.py` — Python ↔ C++ eval parity on startpos (SC#5)
- [ ] `tests/v7/test_eval_static_link.py` — v7_eval_static linkage smoke for v7_engine + v7_uci + texel-tuner (Pitfall 15)
- [ ] `tests/v7/test_margin_rescale.py` — ratio computation + constant patching unit (TUNE-09)
- [ ] `tests/v7/conftest.py` — shared fixtures: tmp_coeffs_json, build_host_marker, RUN_BENCHMARKS gate
- [ ] `gauntlets/phase4-par09.yaml` + `gauntlets/phase4-seeds.yaml` + `gauntlets/phase4-sc6.yaml` + `gauntlets/phase4-rescale.yaml` — gauntlet configs (Phase 2 D-08/11/12 params: TC=10+0.1, c=1, 8moves_v3.pgn, pentanomial SPRT elo0=0 elo1=10 alpha=0.05 beta=0.05, Hash=64)
- [ ] pytest markers `benchmark` and `gauntlet` registered in pyproject.toml `[tool.pytest.ini_options].markers`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PAR-09 4t-vs-1t ≥40 Elo gauntlet | PAR-09 | ≥500-game pentanomial SPRT takes hours; build host only | `tools/gauntlet.py --config gauntlets/phase4-par09.yaml`; review `.planning/gauntlets/phase4-par09/summary.json`; commit checkpoint to `04-02/.continue-here.md` |
| Seed-decider round-robin | TUNE-08 | Multi-seed × ≥500 games per pair takes days | `tools/gauntlet.py --config gauntlets/phase4-seeds.yaml`; review summary; commit winning seed `coeffs.json` |
| TUNE-09 rescale-verify | TUNE-09 | ≥200-game mini-gauntlet on build host | `tools/gauntlet.py --config gauntlets/phase4-rescale.yaml`; lower-bound Elo ≥ −10 |
| SC#6 tuned-vs-untuned | SC#6 | ≥500-game mini-gauntlet on build host | `tools/gauntlet.py --config gauntlets/phase4-sc6.yaml`; clearly measurable Elo margin |
| TUNE-10 ship-commit | TUNE-10 | Human-checkpoint gate per CONTEXT D-13 | Developer reviews summary.json, commits winning `coeffs.json` + `_meta.K`, tags `.continue-here.md` complete |
| PAR-03 TSan 16t×60s gate cleared (PRECONDITION) | (Phase 3 carry-over) | Build host, requires hours of TSan stress | Verified BEFORE Plan 04-01 starts; status in `.planning/phases/03-*/.continue-here.md` Gate 7 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (gauntlet tasks marked manual-only with explicit checkpoint pattern)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (gauntlet runs are checkpoint-gated, not in inner loop)
- [ ] Wave 0 covers all MISSING references (test files + gauntlet YAMLs + pytest markers)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60 s for non-benchmark sampling
- [ ] PAR-07/PAR-08 benchmarks gated by RUN_BENCHMARKS=1 (do not block structural plan-checker)
- [ ] All four gauntlets reference shared Phase 2 SPRT params (no per-phase drift)
- [ ] PAR-03 TSan precondition documented as hard prereq for Plan 04-01 merge
- [ ] `nyquist_compliant: true` set in frontmatter once Wave 0 lands and sentinels are green

**Approval:** pending
