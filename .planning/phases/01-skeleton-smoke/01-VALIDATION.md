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
| 04-T1   | 04   | 3    | EVAL-01     | T-04-03,T-04-04 | coeffs.json material_mg/_eg per piece present (Pesto) | schema | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_coeffs_json_schema -q` | ✅          | ⬜ pending |
| 04-T1   | 04   | 3    | EVAL-02     | T-04-03,T-04-04 | coeffs.json pst_mg/pst_eg 12×64 tables present (Pesto) | schema | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_coeffs_json_schema -q` | ✅          | ⬜ pending |
| 04-T1   | 04   | 3    | EVAL-03     | T-04-03,T-04-04 | coeffs.json phase_weights present (Pesto) | schema | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_coeffs_json_schema -q` | ✅          | ⬜ pending |
| 04-T1   | 04   | 3    | EVAL-04     | T-04-03,T-04-04 | mobility tables (knight 9, bishop 14, rook 15, queen 28) mg+eg present | schema | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_coeffs_json_schema -q` | ✅          | ⬜ pending |
| 04-T1   | 04   | 3    | EVAL-05     | T-04-03    | bishop_pair_mg/eg present | schema | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_coeffs_json_schema -q` | ✅          | ⬜ pending |
| 04-T1   | 04   | 3    | EVAL-06     | T-04-03    | rook_open_file / rook_semi_open_file present | schema | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_coeffs_json_schema -q` | ✅          | ⬜ pending |
| 04-T1   | 04   | 3    | EVAL-07     | T-04-03    | threat_minor_by_pawn / threat_rook_by_minor / threat_queen_by_rook present | schema | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_coeffs_json_schema -q` | ✅          | ⬜ pending |
| 04-T1   | 04   | 3    | EVAL-08     | T-04-03    | king_attack_table[100] + pawn-structure terms (doubled/isolated/backward/passed) present | schema | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_coeffs_json_schema -q` | ✅          | ⬜ pending |
| 04-T1   | 04   | 3    | EVAL-09     | T-04-03    | tempo_mg / tempo_eg present | schema | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_coeffs_json_schema -q` | ✅          | ⬜ pending |
| 04-T2   | 04   | 3    | EVAL-10     | T-04-03    | eval.cpp reads every weight via v7::coeffs::* (no hardcoded weight literals) | unit/grep | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_eval_terms_use_coeffs -q` | ✅          | ⬜ pending |
| 04-T2   | 04   | 3    | EVAL-11     | T-04-03    | tapered combine `(mg*phase + eg*(24-phase))/24` present in eval.cpp; startpos eval in [-50,+50] | unit+grep | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_eval_startpos_balanced -q && grep -E '\* phase\s*\+\s*\w+\s*\*\s*\(24\s*-\s*phase\)' src/chess_engine/engine/v7/src/eval.cpp` | ✅          | ⬜ pending |
| 04-T1   | 04   | 3    | -          | T-04-04    | gen_coeffs.py deterministic (sorted keys, LF) — defends against tamper-via-codegen-drift | unit | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_coeffs_codegen_deterministic tests/test_v7_eval.py::test_codegen_regenerates_on_change -q` | ✅          | ⬜ pending |
| 04-T1   | 04   | 3    | -          | T-04-03    | src/coeffs.cpp gitignored (D-12) | unit | `python3 -m uv run --group dev pytest tests/test_v7_eval.py::test_coeffs_cpp_gitignored -q` | ✅          | ⬜ pending |
| 05-T1   | 05   | 3    | TB-01       | T-05-05    | Fathom (jdart1) submodule pinned at extern/fathom (.gitmodules + SHA c9c6fef) | structural | `git submodule status src/chess_engine/engine/v7/extern/fathom` | ✅          | ⬜ pending |
| 05-T1   | 05   | 3    | TB-02       | —          | tbconfig.h override on V7 include path BEFORE Fathom; 8 macros redirect to v7_tb_* bridges | structural | `grep -cE 'TB_(PAWN\|KNIGHT\|BISHOP\|ROOK\|QUEEN\|KING)_ATTACKS\|TB_pop_lsb\|TB_popcount' src/chess_engine/engine/v7/include/tbconfig.h` (>=8) | ✅          | ⬜ pending |
| 05-T1   | 05   | 3    | INT-06      | —          | .gitmodules entry for Fathom (jdart1 fork) | structural | `grep -c 'src/chess_engine/engine/v7/extern/fathom' .gitmodules` (>=1) | ✅          | ⬜ pending |
| 05-T2   | 05   | 3    | TB-03       | T-05-06    | set_syzygy_path emits exact D-08 case-1 verbatim log on empty path | subprocess/stderr | `python3 -m uv run --group dev pytest tests/test_v7_syzygy.py::test_set_syzygy_path_empty_logs_message -q` | ✅          | ⬜ pending |
| 05-T2   | 05   | 3    | TB-03       | T-05-06    | set_syzygy_path emits exact D-08 case-2 verbatim log on missing path | subprocess/stderr | `python3 -m uv run --group dev pytest tests/test_v7_syzygy.py::test_set_syzygy_path_missing_logs_message -q` | ✅          | ⬜ pending |
| 05-T2   | 05   | 3    | TB-03       | T-05-06    | set_syzygy_path emits exact D-08 case-3 verbatim log on empty dir | subprocess/stderr | `python3 -m uv run --group dev pytest tests/test_v7_syzygy.py::test_set_syzygy_path_empty_dir_logs_message -q` | ✅          | ⬜ pending |
| 05-T2   | 05   | 3    | TB-03       | T-05-06    | D-07 always-log-never-fail (set_syzygy_path never raises) | subprocess/returncode | `python3 -m uv run --group dev pytest tests/test_v7_syzygy.py::test_set_syzygy_path_never_throws -q` | ✅          | ⬜ pending |
| 05-T2   | 05   | 3    | TB-04       | T-05-07    | probe_root_dtz FULLY IMPLEMENTED — calls tb_probe_root_dtz directly with TbRootMoves output; KRk endpoint reflected via tbhits | unit/reflected | `python3 -m uv run --group dev pytest tests/test_v7_syzygy.py::test_root_dtz_probe_returns_some_when_tables_present -q` (skipped if no SYZYGY_PATH/KRvK) | ✅          | ⬜ pending |
| 05-T2   | 05   | 3    | TB-05       | —          | tb_probe_wdl wired in syzygy.cpp; gated on initialized_/TB_LARGEST/max_pieces_/!in_check/no-castling | code-grep | `grep -nE 'tb_probe_wdl' src/chess_engine/engine/v7/src/syzygy.cpp` | ✅          | ⬜ pending |
| 05-T2   | 05   | 3    | TB-06       | T-05-04    | TB_RESULT_FAILED -> std::nullopt in BOTH probe_wdl and probe_root_dtz (NEVER DRAW / NEVER fabricated DTZ) | code-grep | `grep -cE 'TB_RESULT_FAILED' src/chess_engine/engine/v7/src/syzygy.cpp` (>=2) | ✅          | ⬜ pending |
| 05-T2   | 05   | 3    | TB-07       | —          | tbhits atomic counter starts at 0; exposed via Engine binding | unit | `python3 -m uv run --group dev pytest tests/test_v7_syzygy.py::test_tbhits_starts_zero -q` | ✅          | ⬜ pending |
| 05-T2   | 05   | 3    | TB-08       | —          | syzygy_max_pieces_ defaults to 6; gates min(max_pieces_, TB_LARGEST) | code-grep | `grep -nE 'max_pieces_\s*=\s*6\|std::min<unsigned>.*max_pieces_' src/chess_engine/engine/v7/include/syzygy.hpp src/chess_engine/engine/v7/src/syzygy.cpp` | ✅          | ⬜ pending |
| 05-T2   | 05   | 3    | TB-10       | T-05-01    | KRk smoke probe runs after tb_init; failure -> D-08 case-4 log + tb_free | code-grep + subprocess | `grep -nE 'smoke_probe_krk\|smoke probe failed' src/chess_engine/engine/v7/src/syzygy.cpp` | ✅          | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-01     | T-03-04    | Iterative deepening commits best_move at each completed depth | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_iterative_deepening -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-02     | T-03-02    | Aspiration re-search cap (=4 widenings) prevents wall-clock blowout | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_aspiration_cap -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-13     | T-03-01    | Mate scores survive TT round-trip with correct ply adjustment | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_mate_score_tt -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-14     | T-03-06    | In-tree 3-fold repetition returns DRAW_SCORE via Engine-owned RepStack | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_repetition_in_tree -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-14     | T-03-06    | TT cutoff refused when halfmove_clock >= 80 (50-move guard) | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_50move_tt_cutoff -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-15     | T-03-03    | TimeManager honors per-move budget end-to-end via wall clock | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_time_management_budget -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-15     | T-03-03    | >=10% safety margin clamp enforced at TimeManager.allocate | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_time_management_safety_margin -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | SRCH-15     | T-03-04    | Tight time budget never returns MOVE_NONE (depth 1 always completes) | unit | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_time_management_returns_best_so_far -x` | ✅ | ⬜ pending |
| 03-T2   | 03   | 3    | FOUND-04    | —          | Engine.stop() interrupts active search within 50 ms via SearchInfo.external_stop | unit/latency | `python3 -m uv run --group dev pytest tests/test_v7_search.py::test_cancellation_latency_during_real_search -x` | ✅ | ⬜ pending |
| 06-T1   | 06   | 4    | INT-01      | T-06-01    | GameManager dispatches V7 in 4 points (AVAILABLE_ENGINES + set_engine_version + ai_move + stop_search) | code-grep | `grep -nE '"v7"\|algo_v7' src/chess_engine/server/game_manager.py` (>=4 v7 refs) | ✅ | ⬜ pending |
| 06-T1   | 06   | 4    | INT-02      | —          | React App.jsx has V7 option above V6 in BOTH dropdowns | code-grep / manual | `grep -c 'value="v7"' client/src/App.jsx` (=2); ordering manual | ✅ | ⬜ pending |
| 06-T1   | 06   | 4    | INT-03      | —          | App.jsx build-warning fires for V7 | code-grep | `grep -nE 'ver === "v6" \|\| ver === "v7"' client/src/App.jsx` | ✅ | ⬜ pending |
| 06-T1   | 06   | 4    | INT-04      | —          | cli/src/config.js DEFAULT_CONFIG has v7Built/syzygyPath/syzygyMaxPieces | code-grep | `grep -nE 'v7Built\|syzygyPath\|syzygyMaxPieces' cli/src/config.js` | ✅ | ⬜ pending |
| 06-T1   | 06   | 4    | INT-05      | —          | cli/src/index.js exposes `build v7` mirroring buildV6 + `syzygy download` | code-grep + dry-run | `grep -nE 'buildV7\|syzygyDownload' cli/src/index.js`; `node cli/bin/chess-engine.js syzygy download --dry-run` | ✅ | ⬜ pending |
| 06-T1   | 06   | 4    | TB-09       | T-06-02    | `chess-engine syzygy download` script present with OS-specific default destinations | dry-run | `node cli/bin/chess-engine.js syzygy download --dry-run` | ✅ | ⬜ pending |
| 06-T1   | 06   | 4    | FOUND-07    | T-06-04    | v7_uci binary responds to uci/isready/ucinewgame/position/go depth\|movetime/stop/quit | subprocess | `printf 'uci\nposition startpos\ngo depth 3\nquit\n' \| ./build/v7/v7_uci \| grep -E 'uciok\|bestmove'` | ✅ | ⬜ pending |
| 06-T2   | 06   | 4    | FOUND-04    | —          | GameManager.stop_search closes cancellation chain end-to-end via algo_v7.stop_engine within <500ms | unit/latency | `python3 -m uv run --group dev pytest tests/test_v7_engine.py::test_cancellation_via_gm -q` | ✅ | ⬜ pending |
| 06-T2   | 06   | 4    | INT-08      | —          | V1-V6 pytest regression suite green after V7 additions | regression | `python3 -m uv run --group dev pytest tests/ --ignore=tests/test_v7_engine.py --ignore=tests/test_v7_bindings.py --ignore=tests/test_v7_perft.py --ignore=tests/test_v7_search.py --ignore=tests/test_v7_eval.py --ignore=tests/test_v7_syzygy.py -q` | ✅ | ⬜ pending |
| 06-T2   | 06   | 4    | NPS         | T-06-07    | V7 NPS within ~20% of V6 NPS — CLAUDE.md constraint, default-skip via @pytest.mark.benchmark + RUN_BENCHMARKS=1 gate; cites D-04 (smoke-scope) | benchmark/manual | `RUN_BENCHMARKS=1 python3 -m uv run --group dev pytest tests/test_v7_engine.py::test_nps_sentinel -q` (default pytest invocations SKIP) | ✅ | ⬜ pending |

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
