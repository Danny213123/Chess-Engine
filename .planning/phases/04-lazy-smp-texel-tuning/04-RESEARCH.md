# Phase 4: Lazy SMP + Texel Tuning - Research

**Researched:** 2026-05-17
**Domain:** Parallel chess search (Lazy SMP via std::thread) + Texel coefficient tuning (vendored C++ tuner against Zurichess quiet-labeled set)
**Confidence:** HIGH for E1 (codebase fully read, Phase 3 scaffold in place); MEDIUM for E2 (texel-tuner upstream layout claims tagged `[ASSUMED]` — planner must verify against upstream README before vendoring)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Lazy SMP architecture (E1)**

- **D-01:** Persistent thread pool with condition-variable wake. Workers are created once at `Engine` construction and parked on a cv; `search()` posts work and joins. Matches Stockfish/Ethereal pattern; lowest per-search latency. Cv/mutex/state-machine cost is justified vs spawn-per-search because gauntlet runs hundreds of `go` commands per process.
- **D-02:** New `include/thread_pool.hpp` + `src/thread_pool.cpp`. `ThreadPool pool_` is an `Engine` member. Each worker owns a `Worker` struct holding: `Board board_copy`, `int history[2][64][64]`, `Move killers[MAX_PLY][2]`, `Move counter_moves[2][64][64]`, `int continuation_history[2][6][64][2][6][64]`, `int capture_history[2][6][64][6]`, `SearchStack search_stack`. **All the per-thread tables already exist on `Engine` from Phase 3 D-03** — Plan 04-01 lifts them into the `Worker` struct verbatim; `Engine` keeps a single `Worker` as worker[0] for the main thread so the existing single-threaded code path stays alive.
- **D-03:** Divergence pattern = **Berserk-style depth-stagger only** (PAR-06). Helper threads start iterative deepening with a skip pattern (e.g. helper-N skips depth-N early iterations or uses an offset schedule). Per-thread heuristic state divergence (history/killers/counter/continuation) — already designed-in per Phase 3 D-03 — supplies the rest. No root-move shuffling this phase.
- **D-04:** New UCI option `Threads` — **default 1, min 1, max 256**. UI stays single-threaded by default; gauntlets set `Threads=4` (or 8) via `setoption`.
- **D-05 [implied]:** Workers communicate only via the shared TT and the `Engine::stop_flag_` atomic — PAR-05 literal.

**Texel pipeline (E2)**

- **D-06:** Vendor `GediminasMasaitis/texel-tuner` under `tools/texel-tuner/` per TUNE-01.
- **D-07:** New `v7_eval_static` CMake target — `v7_engine`, `v7_uci`, AND `texel-tuner` all link this. Pitfall 15 structurally impossible.
- **D-08:** One-time `tools/filter_quiet_positions.py` emits `tools/.cache/quiet-labeled.filtered.epd`. Drops in-check, qsearch≠eval, popcount ≤ TB_LARGEST. Checksummed.
- **D-09:** K-factor fit **once** via golden-section search in `K ∈ [0.5, 2.0]`, persisted in `coeffs.json` under `_meta.K`. 2 seeds: Pesto-baseline + neutral-zeros. Seed 3 (perturbed) only if seeds 1+2 co-basin (within 5%).

**Validation gauntlets & ship gates**

- **D-10:** PAR-09 (4t vs 1t ≥40 Elo) self-play gauntlet on post-Lazy-SMP V7 binary BEFORE Texel work starts. Same params as Phase 3 D-05 (10+0.1 TC, c=1, 8moves_v3.pgn, pentanomial SPRT `elo0=0 elo1=10`).
- **D-11:** Success Criterion #6 (tuned V7 beats untuned V7) stays inside Phase 4 — ≥500-game blocking-checkpoint mini-gauntlet.
- **D-12:** TUNE-09 post-tune margin rescaling 4-step procedure (avg-|eval| ratio → scale RFP/futility/ProbCut → mini-gauntlet ≥200 games, lower-bound Elo ≥ −10).
- **D-13:** TUNE-10 ship gate = blocking human checkpoint on build host. Seed-decider gauntlet (each-pair round-robin) → human commits winning seed's `coeffs.json` + `_meta.K`.

**Plan layout**

- **D-14:** E1 → PAR-09 → E2 → SC#6 sequential ordering.
- **D-15:** 4 plans:
  - 04-01 Lazy SMP implementation (PAR-04..08)
  - 04-02 PAR-09 self-play gauntlet
  - 04-03 Texel pipeline (TUNE-01..08)
  - 04-04 TUNE-09 margin rescale + SC#6 + TUNE-10 ship-checkpoint
- **D-16:** PAR-07/08 are pytest sentinels gated by `RUN_BENCHMARKS=1` — do NOT block structural plan-checker.

### Claude's Discretion

- Exact `Worker` struct field layout / read-only init sharing (so long as PAR-05 honored at runtime).
- Exact depth-stagger schedule (Berserk `[0,1,0,1,2,2,3,3,...]` or Stockfish pattern — both PAR-06-compliant).
- cv-wake state machine inside `ThreadPool` or split into `ThreadPool` + `WorkerBarrier`.
- Static lib name (`v7_eval_static` / `v7eval` / `v7_eval_lib`).
- `tools/filter_quiet_positions.py` top-level or under `tools/texel/`.
- ADAM hyperparameters (β1, β2, lr) — upstream defaults OK unless loss curves stall.
- Seed-decider round-robin shape (so long as PAR-09 ≥500 games and SC#6 ≥500 games are not blurred).
- `python_bindings.cpp` signature timing (GIL release already wired from FOUND-05).

### Deferred Ideas (OUT OF SCOPE)

- Root-move shuffling for divergence
- Spawn-per-search thread model
- Pure-Python tuner
- Auto-commit on best-loss-seed
- 3rd perturbed seed unconditionally
- `Threads` default = hardware_concurrency
- 6-plan layout
- Parallel E1 ∥ E2 waves
- SPSA tuning of search params
- Root-split / YBW parallel search
- OpenMP threading layer

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PAR-04 | N std::thread workers atop shared TT | E1 §1 (Worker struct, ThreadPool); Phase 3 lockless TT is hard precondition |
| PAR-05 | Workers communicate only via TT + stop_flag | E1 §1 (no shared mutable state in Worker); engine.hpp inventory |
| PAR-06 | Berserk-style depth-stagger divergence | E1 §2 (skip-schedule pattern) |
| PAR-07 | NPS scaling ≥3× (1t → 4t) sentinel | E1 §5 (RUN_BENCHMARKS sentinel; same bench position as Phase 1/2) |
| PAR-08 | Cancellation latency <50 ms across N threads | E1 §6 (per-worker stop_flag poll; cadence guidance from Pitfall 10) |
| PAR-09 | 4t vs 1t self-play ≥40 Elo pentanomial SPRT | E1 §7 (build-host gauntlet pattern; un-defer tools/gauntlet.py run) |
| TUNE-01 | Vendor texel-tuner under tools/ | E2 §1 (upstream MIT; pin SHA in `.texel-tuner.sha`) |
| TUNE-02 | Fetch Zurichess quiet-labeled.epd | E2 §2 (fetch_fastchess.py template) |
| TUNE-03 | Filter pre-tuning: in-check, qsearch≠eval, TB-range | E2 §3 (one-time filter; cached + checksummed) |
| TUNE-04 | K-factor fit once via golden-section | E2 §4 (golden-section in K∈[0.5,2.0]; persist in `_meta.K`) |
| TUNE-05 | Sparse coefficient extraction | E2 §5 (upstream feature; enable in vendor config) |
| TUNE-06 | 90/10 train/val split | E2 §6 (deterministic split via seed; report val loss curve) |
| TUNE-07 | ADAM + L2 regularization | E2 §7 (upstream defaults; L2 weight = 1e-6 starting point) |
| TUNE-08 | Multi-seed driver (Pesto + neutral-zeros + conditional perturbed) | E2 §8 (driver shell + per-seed output dirs) |
| TUNE-09 | Post-tune margin rescaling | E2 §9 (4-step D-12 procedure; mini-gauntlet ≥200 games) |
| TUNE-10 | Ship gate: human commits winning coeffs.json | Cross-cutting §2 (build-host human checkpoint pattern) |

</phase_requirements>

## Summary

Phase 4 has two file-disjoint workstreams executed sequentially (D-14). E1 (Lazy SMP) is **structurally low-risk**: every per-thread table (`history_`, `counter_moves_`, `continuation_history_`, `capture_history_`, `search_stack_`) already exists as a member of `Engine` from Phase 3 03-01 D-03 — Plan 04-01's mechanical work is to lift these into a `Worker` struct and replicate per thread, then add the ThreadPool, depth-stagger schedule, and `Threads` UCI option. The lockless Hyatt-Mann XOR TT is already in place from Phase 3 03-05, and FOUND-05's `py::call_guard<py::gil_scoped_release>()` is already wired on every long-running binding. **The one true hard precondition is the PAR-03 TSan 16t×60s gate, currently deferred in `.planning/phases/03-lockless-tt-search-refinements-endgame/.continue-here.md`**; that must clear on the build host before Plan 04-01 merges.

E2 (Texel) has **higher unknown surface**: the vendoring layout for `GediminasMasaitis/texel-tuner` (eval interface, build glue, sparse-extraction toggle) was not verifiable from this Windows host without network calls beyond the budget of this research pass. The plan-checker should treat E2 vendoring decisions as needing first-touch verification against the upstream README during 04-03 implementation. The CMake architecture (`v7_eval_static` linked by `v7_engine` + `v7_uci` + `texel-tuner`) eliminates the Pitfall-15 class of bugs structurally — same `.o` files in every consumer.

**Primary recommendation:** Plan exactly as D-15 specifies (4 plans, sequential). For 04-01, expect roughly 1-day mechanical lift of Engine state into Worker + ~half-day ThreadPool + ~half-day depth-stagger + ~half-day Threads UCI option + sentinels. For 04-03, plan to spend the first task **verifying texel-tuner upstream layout** before any vendoring — the assumptions in this research can become wrong if upstream restructured since training cutoff.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Parallel search worker management | C++ engine module (v7_engine) | — | Threading lives entirely inside the native module per CLAUDE.md ("no new threading abstraction in FastAPI server layer") |
| GIL release for parallel search | pybind11 binding layer | — | `py::call_guard<py::gil_scoped_release>` at the m.def site (FOUND-05); workers never touch Python |
| Cancellation signaling | Python (`/api/stop` route) → C++ atomic | FastAPI route | Python writes `stop_flag_` via `Engine::stop()` (no GIL guard — single atomic write); C++ workers poll |
| UCI `Threads` option dispatch | v7_uci binary | C++ Engine::set_option | UCI parser already exists in `src/uci_main.cpp`; `set_option` dispatcher exists in Engine |
| Texel tuning driver | Vendored C++ tool (`tools/texel-tuner/`) | Python shell script (multi-seed loop) | C++ tuner does heavy lifting; Python wrapper just iterates seeds + cache mgmt |
| Eval coefficient SSoT | `coeffs.json` (committed source) | `coeffs.cpp` (generated, gitignored) | Phase 1 D-10 already established; tuner writes coeffs.json + gen_coeffs.py codegens |
| Static eval linkage | `v7_eval_static` CMake target | — | New target in CMakeLists; v7_engine + v7_uci + texel-tuner all link it (D-07) |
| Gauntlet orchestration (PAR-09, SC#6, seed-decider, rescale-verify) | `tools/gauntlet.py` | fastchess binary | Phase 2 infrastructure unchanged; new invocations only |
| Build-host human checkpoint | `.continue-here.md` pattern | git commit gate | Phase 1/2/3 established; PAR-09 + TUNE-10 follow identically |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| std::thread / std::atomic / std::condition_variable | C++17 stdlib | Worker pool + lockless TT memory ordering | No external dep; matches V6 "no Boost.Asio, no BS::thread_pool" constraint `[VERIFIED: PROJECT.md]` |
| pybind11 | 2.12.0 (from Phase 1 CMakeLists FetchContent) | Python ↔ C++ binding with `py::call_guard<py::gil_scoped_release>` | Phase 1 standard; already wired `[VERIFIED: src/python_bindings.cpp]` |
| GediminasMasaitis/texel-tuner | latest release SHA at vendoring time | C++ Texel tuning driver | MIT-licensed, sparse extraction, ADAM built-in `[ASSUMED — planner must verify against upstream README at 04-03 Task 1]` |
| fastchess (Disservin) | from Phase 2 02-03 `fetch_fastchess.py` | Gauntlet runner for PAR-09 + SC#6 + seed-decider | Phase 2 standard `[VERIFIED: tools/fetch_fastchess.py]` |
| Zurichess quiet-labeled.epd | static dataset | Texel training data (~725k positions) | TUNE-02 literal; PROJECT.md constraint `[VERIFIED: PROJECT.md]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python `argparse` + `pathlib` + `hashlib` | stdlib | `fetch_tuning_data.py` + `filter_quiet_positions.py` shells | Match Phase 2 fetch_fastchess.py idiom |
| pytest + `RUN_BENCHMARKS=1` env gate | from `pyproject.toml` dev group | PAR-07 NPS scaling + PAR-08 cancellation-latency sentinels | Phase 1/2 RUN_BENCHMARKS pattern |
| Berserk reference (search.c, thread.c) | public GitHub source | depth-stagger pattern read-only reference | Plan 04-01 design step; do NOT copy |
| Stockfish ThreadPool reference | public GitHub source | cv-wake state machine read-only reference | Plan 04-01 design step; GPL — DO NOT copy code |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| std::thread + cv-wake pool | OpenMP `#pragma omp parallel` | Rejected — PROJECT.md "no new threading abstraction" + Lazy SMP needs persistent state per worker, OpenMP fork-join is wrong shape |
| std::thread + cv-wake pool | spawn-per-search threads | Rejected D-01 — spawn cost wastes ~ms at short TCs; gauntlets run hundreds of `go` per process |
| Vendored C++ texel-tuner | Pure-Python tuner | Rejected D-06 — 725k × hundreds of iters × 2 seeds = "weekend vs overnight" speed gap |
| Berserk depth-stagger | Root-move shuffling | Rejected D-03 — extra TT-contamination risk; depth-stagger is simpler + Ethereal/Berserk-proven |
| 4-plan layout | 6-plan layout | Rejected D-15 — compact shape reflects file-disjoint workstreams |
| Sequential E1 → E2 | Parallel E1 ∥ E2 | Rejected D-14 — TUNE-09 + SC#6 need stable post-SMP binary as measurement reference |

**Installation:**

```bash
# No new Python packages — all infra already in pyproject.toml dev group.
# Texel tuner vendored as source under tools/texel-tuner/ — no pip install.
# CMake already builds v7_engine; Phase 4 adds v7_eval_static + links texel-tuner.
```

**Version verification:** texel-tuner upstream SHA pinning happens at 04-03 Task 1; planner records the verified SHA in `tools/.cache/.texel-tuner.sha`. No npm packages involved.

## Architecture Patterns

### System Architecture Diagram

```
                       Phase 4 — End-to-End Data Flow
                       ════════════════════════════════

E1 LAZY SMP (Plan 04-01)                E2 TEXEL TUNING (Plan 04-03)
─────────────────────────               ──────────────────────────────

   FastAPI /api/move                       fetch_tuning_data.py
          │                                          │
          ▼                                          ▼  (Zurichess raw EPD)
   GameManager.ai_move                       tools/.cache/quiet-labeled.epd
          │                                          │
          ▼                                          ▼
   v7_engine.Engine.search(fen,depth,time_ms)   filter_quiet_positions.py
          │                                          │  (drop in-check, qsearch≠eval, TB-range)
          ▼ (GIL released here — FOUND-05)           ▼
   ┌─────────────────────────┐                  tools/.cache/quiet-labeled.filtered.epd
   │ Engine::search          │                  ┌────────────┴────────────┐
   │                         │                  │                         │
   │   ThreadPool.post()─────┼─┐                ▼                         ▼
   │                         │ │      golden-section K-fit      ADAM+L2 multi-seed driver
   │   (parks main on cv)    │ │      (K ∈ [0.5, 2.0])          (Pesto + neutral-zeros)
   └─────────────────────────┘ │              │                         │
                               ▼              ▼                         ▼
                     ┌─────────────────┐   coeffs.json _meta.K     per-seed coeffs candidates
                     │ Worker[0..N-1]  │              │                  │
                     │                 │              └────────┬─────────┘
                     │ Berserk depth-  │                       ▼
                     │ stagger schedule│              seed-decider gauntlet
                     │                 │              (round-robin via tools/gauntlet.py)
                     │ Per-thread:     │                       │
                     │  Board copy     │                       ▼
                     │  history[][][]  │              [BLOCKING HUMAN CHECKPOINT]
                     │  killers[][]    │              ─────────────────────────────
                     │  counter[][][]  │              Human reviews summary.json,
                     │  cont_hist[6D]  │              commits winning coeffs.json
                     │  cap_hist[4D]   │              + _meta.K + _meta.seed_choice
                     │  SearchStack    │                       │
                     │                 │                       ▼
                     │ Shared (refs):  │              gen_coeffs.py codegens
                     │   tt_ ────────────┐            coeffs.cpp (gitignored)
                     │   stop_flag_ ─────│┐                    │
                     │   options_       ││                     ▼
                     │   syzygy_        ││            v7_eval_static rebuild
                     │                 ││             │
                     │  poll stop every││             ▼
                     │  N nodes        ││    v7_engine, v7_uci, texel-tuner
                     └─────────────────┘│             all re-link
                              │         │             │
                              ▼         │             ▼
                       Lockless XOR TT  │      SC#6 mini-gauntlet
                       (Phase 3 03-05)──┘      (tuned vs untuned, ≥500 games)
                              │                       │
                              ▼                       ▼
                     join → worker[0] result    TUNE-09 margin rescale
                              │                 (avg-|eval| ratio →
                              ▼                  RFP/futility/ProbCut scale)
                     SearchResult (best_move,           │
                       score, depth, nodes, nps)         ▼
                              │                  rescale-verify mini-gauntlet
                              ▼                  (≥200 games, lower-bound ≥ −10 Elo)
                     pybind11 → Python                  │
                              │                          ▼
                              ▼                  Ship: commit final coeffs.json
                     UI / gauntlet runner
```

### Recommended Project Structure

```
src/chess_engine/engine/v7/
├── include/
│   ├── thread_pool.hpp         # NEW (04-01) — ThreadPool + Worker struct
│   ├── engine.hpp              # MODIFIED (04-01) — lift per-thread tables into Worker
│   ├── search.hpp              # MODIFIED (04-01) — SearchInfo gains worker_id; cancel poll per-worker
│   ├── search/options.hpp      # MODIFIED (04-01) — add `int Threads = 1;`
│   └── eval.hpp                # MODIFIED (04-03) — add `eval_quiet()` alias for SC#5
├── src/
│   ├── thread_pool.cpp         # NEW (04-01) — cv-wake state machine
│   ├── engine.cpp              # MODIFIED (04-01) — Engine::search posts to pool, joins, picks worker[0] result
│   ├── search.cpp              # MODIFIED (04-01) — replace `Engine&` self-refs with `Worker&`
│   ├── uci_main.cpp            # MODIFIED (04-01) — declare `option name Threads type spin default 1 min 1 max 256`
│   ├── python_bindings.cpp     # MAYBE MODIFIED (04-01) — set_option already exposed; no signature change needed
│   └── coeffs.cpp              # GENERATED — re-emitted by gen_coeffs.py when tuner writes coeffs.json
├── CMakeLists.txt              # MODIFIED (04-03) — add v7_eval_static target; relink v7_engine + v7_uci against it
├── coeffs.json                 # MODIFIED (04-03/04) — _meta.K + _meta.seed_choice + tuned values
└── tools/
    └── gen_coeffs.py           # UNCHANGED — already skips `_`-prefixed keys

tools/
├── fetch_tuning_data.py        # NEW (04-03) — Zurichess fetch, mirrors fetch_fastchess.py
├── filter_quiet_positions.py   # NEW (04-03) — one-time qsearch + in-check + TB-range filter
├── texel-tuner/                # NEW (04-03) — vendored C++ tuner (MIT)
│   └── (upstream layout)       # planner verifies during 04-03 Task 1
├── tune_v7.py                  # NEW (04-03) — multi-seed driver shell
├── rescale_margins.py          # NEW (04-04) — D-12 step 1+2: avg-|eval| ratio computation
├── gauntlet.py                 # MODIFIED (04-02) — un-defer/wrap `run` for self-play V7-vs-V7
└── .cache/
    ├── quiet-labeled.epd                # raw Zurichess
    ├── quiet-labeled.filtered.epd       # post-filter
    └── .texel-tuner.sha                 # pinned upstream SHA

tests/
├── test_v7_lazy_smp.py         # NEW (04-01) — PAR-07 NPS scaling sentinel + PAR-08 cancel sentinel (RUN_BENCHMARKS=1)
├── test_v7_threads_option.py   # NEW (04-01) — Threads UCI/set_option contract test (always-on)
└── test_v7_eval_quiet_parity.py # NEW (04-03) — SC#5 startpos parity Python tuner ↔ v7_engine.evaluate

.planning/gauntlets/
├── phase4-par09/
├── phase4-seeds/
├── phase4-rescale/
└── phase4-sc6/
```

### Pattern 1: cv-wake ThreadPool state machine

**What:** Persistent workers parked on a condition variable; main thread sets a generation counter and broadcasts; workers wake, do work, signal completion, park again.

**When to use:** Lazy SMP where every `go` command launches N parallel searches and short TC dominates (10+0.1).

**Sketch (V7-original, not copied — Stockfish is GPL):**

```cpp
// Source: design transcribed from public Stockfish ThreadPool architecture
//         (https://github.com/official-stockfish/Stockfish/blob/master/src/thread.h)
//         NOT a code copy — V7 implements its own MIT-clean version.
class ThreadPool {
  std::vector<std::thread> threads_;
  std::vector<std::unique_ptr<Worker>> workers_;
  std::mutex                mtx_;
  std::condition_variable   cv_start_;
  std::condition_variable   cv_done_;
  std::atomic<int>          active_count_{0};
  std::atomic<uint64_t>     generation_{0};
  std::atomic<bool>         shutting_down_{false};

public:
  void resize(int n);              // creates n-1 helpers; worker[0] = main thread
  void start_search(const SearchSpec& spec);   // posts to all helpers + runs main inline
  void wait_for_all();             // main parks on cv_done_ until active_count_ == 0
  void shutdown();                 // shutting_down_ = true; broadcast; join all

private:
  void helper_loop(Worker& w);     // for (;;) park on cv_start_; if shutdown break; run; --active; notify cv_done_
};
```

**Confidence:** HIGH (pattern is canonical Stockfish/Ethereal/Berserk).

### Pattern 2: Berserk-style depth-stagger

**What:** Helper threads skip certain early iterative-deepening iterations so they diverge naturally from main.

**When to use:** Any Lazy SMP implementation where root-shuffling is rejected (D-03).

**Sketch (the canonical skip-pattern array shape):**

```cpp
// Reference: Berserk thread.c uses a static array indexed by (worker_id, depth)
//            of {skip_size, skip_phase} pairs. The canonical published pattern is:
//   SkipDepths[20] = {1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7, 7, 7};
//   SkipPhases[20] = {0, 1, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2};
// Helper i, depth d: if ((d + SkipPhases[i % 20]) % SkipDepths[i % 20] != 0) skip.
// `[ASSUMED]` — planner should fetch Berserk's current thread.c at 04-01 to verify
// the exact arrays; the shape (modulo 20, paired skip/phase) is canonical but the
// numeric values may have been retuned upstream since training cutoff.
```

**Confidence:** MEDIUM (shape verified across multiple top-engine references; exact constants `[ASSUMED]`).

### Pattern 3: Per-worker SearchInfo + cancellation poll

**What:** Each worker owns a `SearchInfo` with a pointer to the shared `stop_flag_`; polls every N nodes.

**Sketch:**

```cpp
// In Worker:
struct Worker {
  // ... per-thread tables ...
  SearchInfo info;            // info.external_stop = &engine.stop_flag_  (shared)
  uint64_t   nodes = 0;
};

// In search.cpp alpha_beta / quiescence — replace `Engine&` self-refs with `Worker&`:
if (w.info.stopped ||
    (w.nodes & 1023) == 0 && w.info.check_time()) {     // 1024-node poll per Pitfall 10
  return 0;
}
```

**Current code (search.cpp:174, :79) polls every 4096 nodes.** Pitfall 10 recommends 1024 for sub-50ms latency under SMP. Plan 04-01 should tighten to 1024 — or measure with PAR-08 sentinel first and tighten only if 50ms gate fails. `[VERIFIED: src/search.cpp]`

### Pattern 4: `v7_eval_static` static lib (D-07)

**What:** Single static library bundling eval.cpp + coeffs.cpp + endgame.cpp + types.cpp (and movegen if eval depends on attack tables). Three consumers link it: `v7_engine` (pybind11), `v7_uci` (standalone), `texel-tuner` (vendored).

**Why:** Makes Pitfall 15 (tuner reads X, search uses Y) structurally impossible — same `.o` in every binary.

**Sketch:**

```cmake
# In src/chess_engine/engine/v7/CMakeLists.txt — Plan 04-03 sole owner
add_library(v7_eval_static STATIC
  src/eval.cpp
  src/coeffs.cpp         # generated by gen_coeffs.py via existing add_custom_command
  src/endgame.cpp
  src/types.cpp
  src/board.cpp          # if eval calls into board state
  src/movegen.cpp        # if eval references attack tables
)
target_include_directories(v7_eval_static PUBLIC include)
target_compile_features(v7_eval_static PUBLIC cxx_std_17)

# Existing v7_engine — refactor to link static lib instead of compiling eval.cpp directly:
pybind11_add_module(v7_engine MODULE
  src/python_bindings.cpp
  # other non-eval sources
)
target_link_libraries(v7_engine PRIVATE v7_eval_static)

# Existing v7_uci — same:
add_executable(v7_uci src/uci_main.cpp ...)
target_link_libraries(v7_uci PRIVATE v7_eval_static)

# Vendored tuner (under tools/texel-tuner/):
add_subdirectory(${CMAKE_SOURCE_DIR}/tools/texel-tuner)
target_link_libraries(texel-tuner PRIVATE v7_eval_static)
```

**Confidence:** HIGH for the pattern; MEDIUM for which `.cpp` files belong in the lib (eval's transitive deps need to be re-checked at 04-03 Task 2).

### Anti-Patterns to Avoid

- **Spawning threads per `go` command:** rejected D-01; loses ~ms per search at short TC, dominates gauntlet wall-clock.
- **Sharing history/killers across threads:** Pitfall 12. Each `Worker` owns its own; pointers to shared state ONLY for TT + stop_flag + options + syzygy.
- **Holding the GIL during search:** Pitfall 11. Already mitigated (FOUND-05); do NOT remove `py::call_guard<py::gil_scoped_release>()`.
- **Polling cancellation every 4096 nodes under SMP:** Pitfall 10 says 1024. Current code at 4096 — tighten when PAR-08 sentinel runs.
- **Tuner calling eval via a separate copy of eval.cpp:** Pitfall 15. The whole point of `v7_eval_static` (D-07) is to make this impossible.
- **Re-fitting K per iteration:** Pitfall 13. Fit once, persist in `_meta.K`.
- **Including in-check or non-quiet positions in the tuner input:** Pitfall 14. `filter_quiet_positions.py` enforces.
- **Tuning mg/eg separately:** Pitfall 18. Loss includes phase blend; both terms updated each iteration.
- **Shipping tuned coeffs without margin rescale:** Pitfall 19 / D-12. Eval magnitude shift breaks RFP/futility/ProbCut margins.
- **Copying Stockfish ThreadPool code:** GPL contamination. Read for pattern, implement clean.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| C++ thread pool with task queue | Custom work-stealing queue | std::thread + cv + per-worker generation counter (cv-wake pattern) | Lazy SMP work is "broadcast N copies of same job", not work-stealing — simpler primitive suffices |
| Texel coefficient tuner | Pure-Python ADAM loop | Vendor `GediminasMasaitis/texel-tuner` (D-06) | 725k × hundreds of iters × 2 seeds — speed gap is decisive |
| Sparse coefficient extraction | Custom extractor walking eval.cpp | texel-tuner upstream feature | TUNE-05 literal; upstream already handles |
| Quiet position filter | Custom heuristic (only "no captures") | Stockfish-style `qsearch(pos) != eval(pos)` check (Pitfall 14) | Captures-only misses pins/skewers; qsearch is canonical |
| K-factor optimization | Grid search or hill-climbing | Golden-section search in `[0.5, 2.0]` | Unimodal sigmoid loss; golden-section converges in ~30 evals |
| Gauntlet runner | Custom match driver | `tools/gauntlet.py` (Phase 2 02-04) + fastchess backend | Already paid for; PAR-09 + SC#6 are new invocations not new code |
| EPD checksumming / fetch idempotency | Custom retry loop | Mirror `tools/fetch_fastchess.py` (Phase 2 02-03) | SHA256 sentinel + atomic-rename + .part file pattern already paid for |
| Codegen for `coeffs.cpp` | Manual edits | `gen_coeffs.py` already in place + CMake `add_custom_command` | Re-fires automatically on coeffs.json change |
| GIL release wrapper | Manual `py::gil_scoped_release` in C++ | `py::call_guard<py::gil_scoped_release>()` at m.def site | Already wired Phase 1 FOUND-05 — do NOT change |
| Cancellation primitive | Custom condition variable + mutex | Single `std::atomic<bool> stop_flag_` polled per N nodes | Already present in Engine; Python writes via `engine.stop()` |

**Key insight:** Phase 4's principle is **lift, don't redesign**. Every primitive (per-thread tables, lockless TT, gauntlet runner, codegen pipeline, fetch+checksum pattern, GIL release, EngineOptions dispatcher, RUN_BENCHMARKS sentinels, build-host checkpoint pattern) was either built or scaffolded in Phases 1–3. The Phase 4 plans are mechanical wiring jobs, not green-field design.

## Common Pitfalls

### Pitfall 1: Worker per-thread tables silently share via reference

**What goes wrong:** Refactor accidentally puts `history_`, `killers_` etc. inside Worker as references to Engine state, not values. Workers stomp each other → search collapses to single-thread NPS regardless of `Threads` value.

**Why it happens:** Phase 3 03-01 D-03 designed the tables on `Engine` (single-threaded layout). The mechanical lift to `Worker` MUST be value-typed copies, not references.

**How to avoid:** PAR-09 (4t vs 1t ≥40 Elo) is the gate that catches this — but expensive. Earlier signal: PAR-07 NPS sentinel — if NPS ratio < 1.5× when `Threads=4`, suspect shared state.

**Warning signs:** Helper threads finish near-identical iteration counts to main; TSan reports data races on history table addresses.

### Pitfall 2: Depth-stagger schedule too aggressive — helpers waste work

**What goes wrong:** Skip pattern with high modulo (e.g., skip every 5 depths) → helpers spend most time at shallow depths, never contribute deep insight to TT.

**Why it happens:** Misreading Berserk pattern — the canonical skip is small (modulo 2-7).

**How to avoid:** Mirror Berserk's actual SkipDepths/SkipPhases arrays (planner fetches at 04-01); start with helpers skipping ~30-40% of iterations max.

**Warning signs:** TT-hit rate on helper writes very low; PAR-09 fails to reach 40 Elo.

### Pitfall 3: Cancellation latency >50ms despite atomic stop_flag

**What goes wrong:** Workers poll only every 4096 nodes (current code). At ~3 Mnps that's 1.3ms — well under 50ms. But helper threads may be deep in qsearch evaluating a long capture chain without crossing the poll boundary.

**Why it happens:** Quiescence path also polls every 4096 nodes; under a degenerate position the chain can run 20k+ nodes.

**How to avoid:** Tighten to 1024 nodes (Pitfall 10 recommendation). Add poll inside qsearch too (already there at search.cpp:79 — verify the cadence change applies). PAR-08 sentinel runs with `Threads=4` and a stress position.

**Warning signs:** PAR-08 measures >50ms median; PAR-08 outliers >200ms.

### Pitfall 4: `v7_eval_static` re-link races with codegen

**What goes wrong:** Tuner writes `coeffs.json` → `gen_coeffs.py` regenerates `coeffs.cpp` → CMake doesn't re-build `v7_eval_static` because the timestamp comparison sees no change to `.cpp` (regenerated file is byte-identical to old).

**Why it happens:** gen_coeffs.py emits deterministic LF output; if values happen to be identical, no rebuild.

**How to avoid:** This is the **correct** behavior (no spurious rebuild). Real risk goes the other way: ensure CMake's `add_custom_command` for coeffs.cpp DEPENDS on coeffs.json so any change triggers regen. Verify with `touch coeffs.json && make` — should rebuild.

**Warning signs:** Tuned coefficients don't affect engine behavior despite coeffs.json on disk being updated.

### Pitfall 5: PAR-09 fails — bisection between SMP bug and config bug

**What goes wrong:** 4t-vs-1t self-play shows <40 Elo gain. Could be: helpers wasting work (depth-stagger too aggressive), shared mutable state (Pitfall 1), TT contention (Phase 3 TSan should have caught), insufficient hash, or short TC noise.

**Why it happens:** Many possible causes; PAR-09 is a leaf test that just reports the verdict.

**How to avoid:** Plan 04-02 should run PAR-09 **with `Hash=256` and TC=10+0.1**, AND collect per-thread node-count diagnostics. If Elo low: re-run with `Threads=2` first to bisect. If 2t-vs-1t looks OK but 4t-vs-1t doesn't, suspect TT contention (revisit Phase 3 D-07 sizing).

**Warning signs:** Helper threads report near-identical node counts to main; SPRT lower-bound stays below 0.

### Pitfall 6: Texel converges but gauntlet shows regression (Pitfall 17 manifested)

**What goes wrong:** Both seeds converge to low validation loss, but tuned binary loses SC#6 mini-gauntlet.

**Why it happens:** Validation loss ≠ playing strength. Zurichess set is positional-heavy; tactical Elo can drop if eval gives up tactical-relevant terms (e.g. mobility, king safety) to fit positional ones.

**How to avoid:** D-13 ship gate is the human checkpoint exactly for this. SC#6 is the truth signal. If both seeds fail SC#6, accept the loss and revert to Pesto-baseline + only ship the SMP gain.

**Warning signs:** Val loss flat or rising for both seeds; tuned coeffs.json shows wild swings in king-safety / mobility weights.

### Pitfall 7: Post-tune margin rescale ratio drifts the eval magnitude further than expected

**What goes wrong:** TUNE-09 step 3 scales RFP/futility/ProbCut margins by `ratio = avg_eval_after / avg_eval_before`. If ratio is >1.5 or <0.7, the margin change is large enough to drive new pruning bugs.

**Why it happens:** Tuner may genuinely change eval magnitude substantially; D-12 has no clamp.

**How to avoid:** Add a soft check in `rescale_margins.py` — if `ratio` falls outside [0.7, 1.5], flag for human review before applying. The rescale-verify mini-gauntlet (≥200 games, lower-bound ≥ −10 Elo) is the safety net.

**Warning signs:** Rescale-verify shows lower-bound < −10 Elo → revert to unscaled.

### Pitfall 8: PAR-03 TSan gate still deferred → Plan 04-01 merges without TSan signal

**What goes wrong:** Phase 3 03-05's TSan stress-test is plumbed but the runtime gate is deferred to build host (`.continue-here.md` Gate 7). If Plan 04-01 merges before that gate clears, an undiscovered TT race becomes a Lazy SMP race.

**Why it happens:** Build host is offline; humans forget; sequential dependency not enforced in code.

**How to avoid:** Plan 04-01's PLAN.md MUST list "PAR-03 TSan 16t×60s gate cleared on build host" as a hard precondition. Plan-checker should reject 04-01 PLAN if this prereq is unstated. CI gate, if it exists, should block too.

**Warning signs:** TSan reports data races during PAR-09 stress run; intermittent search-result hash mismatches across runs.

## Code Examples

### Example 1: Worker struct field layout (Plan 04-01)

```cpp
// Source: lifted verbatim from existing Engine fields in include/engine.hpp
//         (Phase 3 03-01 D-03). VERIFIED via Read tool.
namespace v7 {

struct Worker {
    // Per-thread search state — value-typed copies, NOT references
    Board       board_copy;
    RepStack    rep_stack;
    SearchStack search_stack;
    int  history[2][64][64] = {};
    Move counter_moves[2][64][64] = {};
    int  continuation_history[2][6][64][2][6][64] = {};  // ~2.3 MB per worker
    int  capture_history[2][6][64][6] = {};               // ~18 KB

    // Per-worker bookkeeping
    SearchInfo info;            // info.external_stop -> shared Engine::stop_flag_
    uint64_t   nodes = 0;
    int        worker_id = 0;   // 0 = main thread; 1..N-1 = helpers

    // Shared state (raw pointers — Worker does NOT own)
    TT*                    shared_tt = nullptr;
    std::atomic<bool>*     shared_stop = nullptr;
    const EngineOptions*   shared_options = nullptr;
    SyzygyState*           shared_syzygy = nullptr;
};

} // namespace v7
```

### Example 2: Threads UCI option declaration (Plan 04-01)

```cpp
// In src/uci_main.cpp `uci` handler (currently lines 119-139)
// Add to the option list:
std::cout << "option name Threads type spin default 1 min 1 max 256\n";

// EngineOptions in include/search/options.hpp — add field:
struct EngineOptions {
    // ... existing fields ...
    int Threads = 1;        // NEW — D-04
};

// Engine::set_option dispatcher in src/engine.cpp — add case:
if (name == "Threads") {
    int n;
    try { n = std::stoi(value); } catch (...) {
        std::cout << "info string Threads requires integer\n"; return;
    }
    if (n < 1 || n > 256) {
        std::cout << "info string Threads out of range [1,256]\n"; return;
    }
    options_.Threads = n;
    pool_.resize(n);       // resize the ThreadPool to match
    return;
}
```

### Example 3: PAR-07 NPS scaling sentinel (Plan 04-01)

```python
# tests/test_v7_lazy_smp.py — RUN_BENCHMARKS=1 gated
import os
import pytest
from chess_engine.engine.v7 import v7_engine

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_BENCHMARKS") != "1",
    reason="benchmark — set RUN_BENCHMARKS=1 to run"
)

BENCH_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

def _nps_at(threads: int) -> float:
    e = v7_engine.Engine()
    e.set_option("Threads", str(threads))
    e.set_option("Hash", "256")
    r = e.search(BENCH_FEN, depth=12, time_ms=5000)
    return r.nps

def test_nps_scales_3x_4t_vs_1t():
    nps_1 = _nps_at(1)
    nps_4 = _nps_at(4)
    ratio = nps_4 / nps_1
    assert ratio >= 3.0, f"4t/1t NPS ratio {ratio:.2f} < 3.0 (1t={nps_1:.0f}, 4t={nps_4:.0f})"
```

### Example 4: PAR-08 cancellation latency sentinel (Plan 04-01)

```python
# tests/test_v7_lazy_smp.py
import threading
import time

def test_cancellation_under_4_threads_under_50ms():
    e = v7_engine.Engine()
    e.set_option("Threads", "4")
    e.set_option("Hash", "256")

    result_holder = {}
    def search_thread():
        result_holder["r"] = e.search(STRESS_FEN, depth=30, time_ms=30_000)

    t = threading.Thread(target=search_thread)
    t.start()
    time.sleep(0.5)   # let workers ramp up

    t0 = time.perf_counter_ns()
    e.stop()
    t.join(timeout=2.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6

    assert not t.is_alive(), "search did not return within 2s of stop()"
    assert elapsed_ms < 50.0, f"cancellation took {elapsed_ms:.1f}ms (threshold 50ms)"
```

### Example 5: Golden-section K-fit (Plan 04-03)

```python
# In tuner driver — runs ONCE, result persisted to coeffs.json._meta.K
import math

PHI = (1 + math.sqrt(5)) / 2
INV_PHI = 1 / PHI

def fit_k(eval_loss_at_k, lo=0.5, hi=2.0, tol=1e-4):
    """Golden-section search; eval_loss_at_k(k) -> float (MSE on filtered EPD)."""
    a, b = lo, hi
    c = b - (b - a) * INV_PHI
    d = a + (b - a) * INV_PHI
    while abs(b - a) > tol:
        if eval_loss_at_k(c) < eval_loss_at_k(d):
            b = d
        else:
            a = c
        c = b - (b - a) * INV_PHI
        d = a + (b - a) * INV_PHI
    return (a + b) / 2
```

### Example 6: TUNE-09 margin rescale arithmetic (Plan 04-04)

```python
# tools/rescale_margins.py
import json
import statistics
import chess

def avg_abs_eval(positions, eval_fn):
    return statistics.mean(abs(eval_fn(p)) for p in positions)

def rescale(margins_before: dict, ratio: float) -> dict:
    """Scale RFP / futility / ProbCut margin constants by avg-|eval| ratio."""
    if not (0.7 <= ratio <= 1.5):
        print(f"WARN: ratio {ratio:.3f} outside [0.7, 1.5] — flag for human review")
    return {k: int(round(v * ratio)) for k, v in margins_before.items()}

# Step 1+2: compute ratio on held-out 1000-position subset
positions = load_held_out_subset(n=1000)
before = avg_abs_eval(positions, eval_untuned)
after  = avg_abs_eval(positions, eval_tuned)
ratio = after / before

# Step 3: rescale
new_margins = rescale(load_current_margins(), ratio)
write_back_to_search_constants_or_coeffs_json(new_margins)

# Step 4: gauntlet validates (handled by tools/gauntlet.py invocation, ≥200 games,
#         lower-bound Elo must be ≥ −10)
```

### Example 7: eval_quiet parity test (SC#5, Plan 04-03)

```python
# tests/test_v7_eval_quiet_parity.py — always-on (no RUN_BENCHMARKS gate)
from chess_engine.engine.v7 import v7_engine
# from tools.texel-tuner harness import python_eval_quiet (Python-side mirror)

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

def test_eval_quiet_startpos_parity():
    c_side = v7_engine.evaluate(STARTPOS)
    py_side = python_eval_quiet(STARTPOS)   # reads same coeffs.json + same eval code via tuner
    assert c_side == py_side, f"eval mismatch: C={c_side} Py={py_side} (Pitfall 15)"
```

## Runtime State Inventory

Phase 4 has **no rename/refactor scope** — it adds new files (thread_pool.{hpp,cpp}, tools/texel-tuner/, tools/fetch_tuning_data.py, tools/filter_quiet_positions.py, tools/tune_v7.py, tools/rescale_margins.py, v7_eval_static target) and **modifies existing files in-place** without renaming any identifiers, files, or services. The Runtime State Inventory section is **not applicable**.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no rename | — |
| Live service config | None — no rename | — |
| OS-registered state | None — no rename | — |
| Secrets/env vars | None — only `RUN_BENCHMARKS=1` (already existing pattern, not introduced) | — |
| Build artifacts | Tuner-emitted `coeffs.json` triggers existing `gen_coeffs.py` codegen → `coeffs.cpp` (already gitignored per Phase 1 D-12). CMake `add_custom_command` already wires this. | None — pipeline is the SSoT |

**Verification:** Plan 04-01 lifts Engine fields into Worker — this is a refactor, not a rename. All field names (`history_`, `counter_moves_`, etc.) keep their identifiers; only their containing struct changes. No stored data, no external service, no env var changes.

## Environment Availability

Phase 4 has critical external dependencies. This host (Windows, current research session) lacks the full toolchain — same condition as Phase 1's `.continue-here.md`. Plan 04-01..04 all execute against the build host (D-13, D-11 patterns).

| Dependency | Required By | Available (current host) | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 + uv | All test gates, all tuner driver scripts | ✗ | — | Build host has it |
| CMake ≥3.15 + C++17 compiler (MSVC / clang / g++) | v7_eval_static, v7_engine, v7_uci, vendored texel-tuner | ✗ | — | Build host has it (per Phase 1 expectations) |
| fastchess binary | PAR-09, SC#6, seed-decider, rescale-verify gauntlets | ✗ | — | `tools/fetch_fastchess.py` from Phase 2 02-03 lands it on build host |
| Internet access (for Zurichess EPD + texel-tuner upstream + fastchess release) | One-time fetches in 04-03 / Phase 2 | ✓ on build host expected | — | Pre-stage offline if needed |
| Git | All commits, vendoring | ✓ | — | — |
| ~5 GB free disk for tuning artifacts (filtered EPD + per-seed outputs + gauntlet PGNs) | 04-03 / 04-04 | unknown | — | Document in 04-03 PLAN; clean up `tools/.cache/` between runs |

**Missing dependencies with no fallback (current host):**
- Python 3.12, CMake, C++ compiler — all Phase 4 plans require build host execution (same constraint as Phase 1). Plans 04-01 through 04-04 must follow the `.continue-here.md` pattern: structural code lands here, runtime gates clear on build host.

**Missing dependencies with fallback:**
- fastchess — fetched on first gauntlet run via `tools/fetch_fastchess.py` (Phase 2 02-03).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (declared `[dependency-groups].dev` in pyproject.toml) |
| Config file | none — root-level pytest auto-discovery against `tests/` |
| Quick run command | `python3 -m uv run --group dev pytest tests/test_v7_lazy_smp.py tests/test_v7_threads_option.py tests/test_v7_eval_quiet_parity.py -q` |
| Full suite command | `python3 -m uv run --group dev pytest -q` |
| Benchmark-gated command | `RUN_BENCHMARKS=1 python3 -m uv run --group dev pytest tests/test_v7_lazy_smp.py -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PAR-04 | N workers exist when Threads=N | unit | `pytest tests/test_v7_threads_option.py::test_pool_resizes_to_n -x` | ❌ Wave 0 (Plan 04-01) |
| PAR-05 | Workers share only TT + stop_flag (smoke: setting Threads doesn't break single-thread tests) | unit | `pytest tests/test_v7_engine.py -x` (regression) | ✅ (existing tests must stay green) |
| PAR-06 | Depth-stagger active (helper depth profile differs from main) | unit | `pytest tests/test_v7_lazy_smp.py::test_helper_depth_stagger -x` | ❌ Wave 0 (Plan 04-01) |
| PAR-07 | NPS scaling ≥3× (1t → 4t) on bench FEN | sentinel (RUN_BENCHMARKS) | `RUN_BENCHMARKS=1 pytest tests/test_v7_lazy_smp.py::test_nps_scales_3x_4t_vs_1t -x` | ❌ Wave 0 (Plan 04-01) |
| PAR-08 | Cancellation <50ms with Threads=4 | sentinel (RUN_BENCHMARKS) | `RUN_BENCHMARKS=1 pytest tests/test_v7_lazy_smp.py::test_cancellation_under_4_threads_under_50ms -x` | ❌ Wave 0 (Plan 04-01) |
| PAR-09 | 4t vs 1t self-play ≥40 Elo pentanomial SPRT (≥500 games) | manual-only (gauntlet on build host) | `python3 tools/gauntlet.py run --phase phase4-par09 --threads-a 4 --threads-b 1 --tc 10+0.1 --games 1000 --book 8moves_v3.pgn --pentanomial` | ❌ Plan 04-02 |
| TUNE-01 | texel-tuner vendored, builds against v7_eval_static | unit | `pytest tests/test_v7_texel_build.py::test_texel_tuner_builds -x` (CMake build smoke) | ❌ Wave 0 (Plan 04-03) |
| TUNE-02 | Zurichess EPD fetch is idempotent + checksummed | unit | `pytest tests/test_v7_tuning_data.py::test_fetch_idempotent -x` | ❌ Wave 0 (Plan 04-03) |
| TUNE-03 | Filter drops in-check / qsearch≠eval / TB-range positions | unit | `pytest tests/test_v7_tuning_data.py::test_filter_drops_expected -x` | ❌ Wave 0 (Plan 04-03) |
| TUNE-04 | K-fit golden-section converges to stable K | unit | `pytest tests/test_v7_texel_kfit.py::test_k_fit_converges -x` (uses a 1k-position fixture) | ❌ Wave 0 (Plan 04-03) |
| TUNE-05 | Sparse extraction extracts at least N nonzero gradient buckets | unit | `pytest tests/test_v7_texel_sparse.py::test_sparse_extraction_smoke -x` | ❌ Wave 0 (Plan 04-03) |
| TUNE-06 | 90/10 split is deterministic given seed | unit | `pytest tests/test_v7_texel_split.py::test_split_deterministic -x` | ❌ Wave 0 (Plan 04-03) |
| TUNE-07 | ADAM+L2 loss curve monotone-non-increasing on training set | manual-only (build host) | `python3 tools/tune_v7.py --seed pesto --max-iters 50 --verify-loss-decreases` | ❌ Plan 04-03 |
| TUNE-08 | Multi-seed driver writes per-seed output dirs | unit | `pytest tests/test_v7_texel_seeds.py::test_driver_writes_per_seed_dirs -x` | ❌ Wave 0 (Plan 04-03) |
| TUNE-09 | Margin rescale: ratio computed, scaled constants written, gauntlet lower-bound ≥ −10 Elo | manual-only (build host gauntlet) | `python3 tools/rescale_margins.py && python3 tools/gauntlet.py run --phase phase4-rescale --games 200` | ❌ Plan 04-04 |
| TUNE-10 | Human commits winning seed's coeffs.json + _meta.K (HUMAN CHECKPOINT) | manual-only (human) | (no command — human reviews summary.json + `git add coeffs.json && git commit`) | ❌ Plan 04-04 |
| SC#5 | eval_quiet(startpos) parity Python tuner ↔ v7_engine.evaluate | unit | `pytest tests/test_v7_eval_quiet_parity.py::test_eval_quiet_startpos_parity -x` | ❌ Wave 0 (Plan 04-03) |
| SC#6 | Tuned V7 beats untuned V7, ≥500-game mini-gauntlet | manual-only (build host gauntlet) | `python3 tools/gauntlet.py run --phase phase4-sc6 --binary-a v7_uci_tuned --binary-b v7_uci_untuned --games 500 --pentanomial` | ❌ Plan 04-04 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_v7_lazy_smp.py tests/test_v7_threads_option.py tests/test_v7_eval_quiet_parity.py -q` (skip RUN_BENCHMARKS sentinels)
- **Per wave merge:** `pytest -q` (full suite — Phase 1-3 regression remains green)
- **Build-host gates (before phase-gate):** `RUN_BENCHMARKS=1 pytest tests/test_v7_lazy_smp.py -q` + all manual gauntlet commands above
- **Phase gate:** All RUN_BENCHMARKS sentinels pass + PAR-09 SPRT verdict pass + TUNE-10 commit landed + SC#6 SPRT verdict pass before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_v7_lazy_smp.py` — PAR-07 NPS scaling + PAR-08 cancellation sentinels (Plan 04-01)
- [ ] `tests/test_v7_threads_option.py` — Threads UCI/set_option contract test (Plan 04-01)
- [ ] `tests/test_v7_eval_quiet_parity.py` — SC#5 parity (Plan 04-03)
- [ ] `tests/test_v7_texel_build.py` — texel-tuner CMake build smoke (Plan 04-03)
- [ ] `tests/test_v7_tuning_data.py` — fetch idempotency + filter correctness (Plan 04-03)
- [ ] `tests/test_v7_texel_kfit.py` — K-fit convergence on fixture (Plan 04-03)
- [ ] `tests/test_v7_texel_sparse.py` — sparse extraction smoke (Plan 04-03)
- [ ] `tests/test_v7_texel_split.py` — deterministic 90/10 split (Plan 04-03)
- [ ] `tests/test_v7_texel_seeds.py` — multi-seed driver output (Plan 04-03)
- [ ] No framework install needed — pytest already in `[dependency-groups].dev`

## Project Constraints (from CLAUDE.md)

- **Tech stack lock:** V7 must be a C++17 pybind11 module mirroring V6 — no language additions, no replacement for FastAPI/React. Phase 4 honors via std::thread (no Boost, no third-party thread lib) and pybind11 (unchanged from Phase 1).
- **Performance floor:** V7 NPS ~20% of V6 — TUNE-09 margin rescale must NOT degrade NPS below floor. Plan 04-04 should re-run Phase 2's NPS regression sentinel after rescale.
- **Validation:** Strength is the ship signal — SC#6 + PAR-09 are the truth signals; loss curves are diagnostic only.
- **Repo size:** Syzygy NOT bundled. Same applies to Zurichess EPD — `tools/fetch_tuning_data.py` downloads to `tools/.cache/` (gitignored).
- **UI surface:** Phase 4 makes no UI changes. `Threads` UCI option doesn't surface in dropdown — it's a gauntlet-only knob.
- **Compatibility:** V1-V6 unchanged after Phase 4. Confirmed — no V1-V6 file is in Phase 4 scope.
- **Concurrency:** Lazy SMP only; no FastAPI threading abstraction. Phase 4 puts all threading inside the v7 C++ module; FastAPI `GameManager.ai_move` continues calling `find_best_move` synchronously.
- **Cancellation:** Honor existing `SearchInfo` contract. Phase 4 per-worker `SearchInfo` points to shared `Engine::stop_flag_` — contract preserved.
- **GSD workflow:** Edits go through `/gsd-execute-phase 4` (or `/gsd-quick` for doc tweaks). Research file is itself written via the research workflow.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Locked TT (mutex per bucket) | Lockless Hyatt-Mann XOR TT | Phase 3 03-05 (V7) | Lazy SMP becomes safe at scale; PAR-03 TSan gate is the proof |
| Spawn-per-search threads | Persistent cv-wake pool | Stockfish ~2010, Ethereal/Berserk ~2017+ | Lower per-search latency at short TC; standard pattern |
| Python tuner (slow) | Vendored C++ texel-tuner | Standard practice in modern HCE | 10-50× speedup for 725k-position tuning |
| Captures-only "quiet" filter | qsearch-equality filter | Stockfish-era refinement | Captures pins/skewers; better tuning fidelity |
| Per-iteration K refit | One-time K-fit, persisted | Pitfall 13 / community consensus | Avoids basin drift across iterations |
| Single-seed tuning | Multi-seed sanity check | Pitfall 16 community consensus | Catches local-min convergence |
| Eval-only tuning (no margin rescale) | Co-tune eval + rescale margins | Pitfall 19 lessons | Avoids latent pruning regressions from eval-magnitude shift |

**Deprecated/outdated:**

- Spawn-per-search threading — superseded by persistent pool (D-01).
- Root-move shuffling as primary divergence — superseded by depth-stagger + per-thread heuristic divergence (D-03).
- Single-seed Texel runs — superseded by multi-seed driver (D-09).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `GediminasMasaitis/texel-tuner` upstream is MIT-licensed | Standard Stack | Re-license check at vendoring; planner verifies on 04-03 Task 1 |
| A2 | texel-tuner upstream has built-in sparse coefficient extraction (TUNE-05) | E2 §5, Don't Hand-Roll | If absent, 04-03 must add it OR descope TUNE-05 to "best-effort" |
| A3 | texel-tuner exposes a C++ eval-injection seam so v7_eval_static can be linked | D-07, Pattern 4 | If absent, 04-03 needs an adapter shim — adds ~1-task complexity |
| A4 | Berserk SkipDepths/SkipPhases canonical arrays are `{1,1,2,2,2,3,3,3,4,4,4,5,5,5,6,6,6,7,7,7}` / `{0,1,0,1,2,0,1,2,0,1,2,0,1,2,0,1,2,0,1,2}` | Pattern 2, Code Example | Plan 04-01 fetches Berserk's current `thread.c` at design time and verifies; numeric values may have been retuned upstream |
| A5 | Stockfish ThreadPool's cv-wake design is canonical and pattern-extractable without GPL contamination (design only, no code) | Pattern 1 | Read for design; implement clean. Risk is contributor accidentally copying code — code review at 04-01 must verify. |
| A6 | Zurichess `quiet-labeled.epd` is still hosted at `https://bitbucket.org/zurichess/tuner/src/master/quiet-labeled.epd` | Standard Stack | Pre-stage download URL; if dead, find mirror (community-mirrored on multiple chess-programming sites) |
| A7 | Polling cancellation every 1024 nodes (Pitfall 10 recommendation) is sufficient for <50ms latency at SMP | Pitfall 3, Pattern 3 | PAR-08 sentinel is the empirical check; tighten to 512 if 1024 insufficient |
| A8 | `avg_eval_after / avg_eval_before` ratio (D-12 step 1+2) will fall in roughly [0.85, 1.15] for a healthy tune | Pitfall 7 | Rescale-verify mini-gauntlet (≥200 games) is the safety net; soft warn if outside [0.7, 1.5] |
| A9 | gen_coeffs.py + CMake `add_custom_command` correctly re-fires on coeffs.json change with no spurious rebuild | Pitfall 4 | Verify with `touch coeffs.json && make` smoke test in 04-03 |
| A10 | ADAM defaults from texel-tuner upstream (typically β1=0.9, β2=0.999, lr=1.0 for Texel) are acceptable starting points | TUNE-07 | Loss-curve diagnostic in 04-03 Task X; tune only if stall observed |

## Open Questions

1. **Where does the `Threads` value flow through the binding?**
   - What we know: `Engine::set_option("Threads", "4")` is the clean path; v7_uci already routes setoption correctly.
   - What's unclear: Whether `python_bindings.cpp` needs ANY new binding (e.g., a `set_threads` shortcut) or whether all callers go through `set_option`. CONTEXT D-04 implies set_option only.
   - Recommendation: NO new binding. Python callers use `engine.set_option("Threads", "4")`. Confirms minimal surface change to python_bindings.cpp.

2. **Where does the rescaled margin live — coeffs.json or search constants?**
   - What we know: RFP/futility/ProbCut margin constants currently live in search source (e.g. as `const int RFP_MARGIN_PER_DEPTH`).
   - What's unclear: D-12 doesn't say whether the rescale writes to coeffs.json (with new `_meta.margins`) or patches the C++ constants directly.
   - Recommendation: Add to coeffs.json (`_meta.margins`) so the codegen pipeline emits them — keeps SSoT discipline. Plan 04-04 owns the schema extension.

3. **Does Plan 04-01 modify Engine::search signature or stay compatible?**
   - What we know: Existing signature is `Engine::search(fen, depth, time_ms) -> SearchResult`.
   - What's unclear: Whether the pool internally posts work to all helpers when `Threads > 1` (signature unchanged) or whether a new entry point exists.
   - Recommendation: Keep signature stable. Internal change only — `Engine::search` reads `options_.Threads`, posts to pool, joins, returns worker[0] result.

4. **Should PAR-09 use Hash=64 (UI default) or Hash=256 (gauntlet default)?**
   - What we know: Phase 2 gauntlets used Hash=64. Lazy SMP gains scale with TT size.
   - What's unclear: Which is the canonical gauntlet config for PAR-09.
   - Recommendation: Hash=64 to match Phase 2 (apples-to-apples gauntlet config); document explicitly in Plan 04-02. If Elo borderline, re-run with Hash=256 as diagnostic.

5. **Does the vendored texel-tuner need its own CMakeLists or does CMake `add_subdirectory(tools/texel-tuner)` Just Work?**
   - What we know: Upstream is C++ with its own CMake setup `[ASSUMED]`.
   - What's unclear: Whether upstream's CMake gracefully consumes an externally-defined `v7_eval_static` target.
   - Recommendation: 04-03 Task 1 (verify upstream layout) is the first thing the executor agent does; treat as one of the highest-priority knowledge gaps.

6. **What does PAR-03 TSan gate actually report when Lazy SMP runs?**
   - What we know: PAR-03 TSan harness exists (Phase 3 03-05); runtime gate is deferred on build host.
   - What's unclear: Whether the harness covers the search path that workers actually traverse (not just probe/store).
   - Recommendation: When PAR-03 clears on build host, extend the harness in Plan 04-01 Wave 0 to run Engine::search with `Threads=16` under TSan for a short duration. Catches any new races introduced by the worker refactor.

## Recommended Plan Shape

D-15 specifies 4 plans. This research confirms that shape and lists each plan's expected scope:

### Plan 04-01: Lazy SMP implementation

**Files:** `include/thread_pool.hpp`, `src/thread_pool.cpp` (new); `include/engine.hpp`, `src/engine.cpp`, `src/search.cpp`, `include/search.hpp`, `include/search/options.hpp`, `src/uci_main.cpp` (modified); `python_bindings.cpp` (maybe — only if set_option needs new arg handling — research says NO).

**Tasks (suggested):**
- T1: Define `Worker` struct + ThreadPool skeleton (parking, broadcast). No depth-stagger yet.
- T2: Lift Engine's per-thread tables into Worker. Refactor `engine.cpp` + `search.cpp` to use `Worker&` instead of `Engine&` for the per-thread accesses.
- T3: Engine::search posts to pool, joins, returns worker[0] result. Single-thread mode still works (Threads=1 = main only, no helpers spawned).
- T4: Berserk depth-stagger schedule + per-worker iterative deepening entry.
- T5: `Threads` UCI option + EngineOptions field + set_option dispatcher + uci handler declaration.
- T6: Tighten cancellation poll to 1024 nodes (or measure-then-tighten under PAR-08).
- T7: Write `test_v7_lazy_smp.py` (PAR-07, PAR-08) + `test_v7_threads_option.py` (PAR-04 contract). Skip RUN_BENCHMARKS gate so structural CI sees them.

**Hard precondition:** PAR-03 TSan gate cleared on build host (Phase 3 .continue-here.md Gate 7).

**Requirements satisfied:** PAR-04, PAR-05, PAR-06, PAR-07, PAR-08.

### Plan 04-02: PAR-09 self-play gauntlet

**Files:** `tools/gauntlet.py` (modified — un-defer `run` for self-play V7-vs-V7); `.planning/phases/04-lazy-smp-texel-tuning/.continue-here.md` (new — build-host gate).

**Tasks (suggested):**
- T1: Un-defer / parameterize `tools/gauntlet.py run` for self-play (same binary, different `Threads=` setoption).
- T2: Add invocation recipe + expected output schema to `.continue-here.md` (build-host gate).
- T3 (HUMAN, build host): Run PAR-09 SPRT, paste summary.json result, document Elo lower bound.

**Requirements satisfied:** PAR-09.

### Plan 04-03: Texel pipeline

**Files:** `tools/texel-tuner/` (vendored — new); `tools/fetch_tuning_data.py`, `tools/filter_quiet_positions.py`, `tools/tune_v7.py` (new); `src/chess_engine/engine/v7/CMakeLists.txt` (modified — add v7_eval_static target); `include/eval.hpp` (modified — alias `eval_quiet`); `tests/test_v7_eval_quiet_parity.py`, `tests/test_v7_texel_*.py` (new); `coeffs.json` (modified — `_meta.K` added after tuning).

**Tasks (suggested):**
- T1: Vendor texel-tuner — pin SHA in `tools/.cache/.texel-tuner.sha`. Verify upstream layout / eval seam / sparse extraction (closes open questions 5).
- T2: Refactor CMakeLists for `v7_eval_static` target; link v7_engine + v7_uci + vendored tuner against it.
- T3: `fetch_tuning_data.py` (mirror fetch_fastchess.py pattern) + `filter_quiet_positions.py` (in-check, qsearch≠eval, TB-range filters).
- T4: K-fit golden-section + persist `_meta.K` in coeffs.json.
- T5: Multi-seed driver (`tune_v7.py`) — Pesto + neutral-zeros + conditional perturbed. ADAM+L2 defaults. 90/10 train/val split (deterministic seed).
- T6: SC#5 parity test (`test_v7_eval_quiet_parity.py`) + tuner build smoke + fetch/filter tests + K-fit test + split-deterministic test + seed-driver test.
- T7 (HUMAN, build host): Run multi-seed tunes, document loss curves, choose seed.

**Hard precondition:** Plan 04-02 PAR-09 gauntlet passed (D-14 ordering).

**Requirements satisfied:** TUNE-01, TUNE-02, TUNE-03, TUNE-04, TUNE-05, TUNE-06, TUNE-07, TUNE-08, SC#5.

### Plan 04-04: TUNE-09 margin rescale + SC#6 + TUNE-10 ship

**Files:** `tools/rescale_margins.py` (new); `coeffs.json` (modified — `_meta.margins`); `.planning/phases/04-lazy-smp-texel-tuning/.continue-here.md` (modified — append SC#6 + TUNE-10 gates).

**Tasks (suggested):**
- T1: `rescale_margins.py` — compute avg-|eval| ratio on held-out 1000-position subset; scale RFP/futility/ProbCut margins; write to coeffs.json `_meta.margins` (or patch search constants — see open question 2).
- T2: Seed-decider gauntlet recipe in `.continue-here.md` (round-robin of all tuned seeds, e.g. 500 games per pair).
- T3: Rescale-verify mini-gauntlet recipe (≥200 games, lower-bound Elo ≥ −10).
- T4: SC#6 mini-gauntlet recipe (tuned vs untuned, ≥500 games).
- T5 (HUMAN, build host): Run gauntlets, review summary.json, commit winning seed's `coeffs.json` + `_meta.K` + `_meta.seed_choice` + `_meta.tuning_run`.

**Hard precondition:** Plan 04-03 multi-seed tuning complete (D-14 ordering).

**Requirements satisfied:** TUNE-09, TUNE-10, SC#6.

**Sanity check vs D-15:** All 16 phase requirements + SC#5 + SC#6 map to the 4 plans. No requirement orphaned, no plan empty. Matches D-15 exactly.

## Security Domain

`security_enforcement` is not set in `.planning/config.json`. Treating as enabled. Phase 4 is a native-engine workstream with no new internet-facing endpoints; the applicable surface is narrow.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in V7 surface |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | No new endpoints |
| V5 Input Validation | yes (narrow) | `Engine::set_option("Threads", value)` parses int — bounds-check `[1, 256]` per D-04. Reject non-int with `info string`. |
| V6 Cryptography | yes (narrow) | SHA256 sentinel files for `fetch_tuning_data.py` use Python `hashlib.sha256` (stdlib — do NOT hand-roll). Mirror `fetch_fastchess.py` exactly. |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| `Threads=999999` triggers std::thread spawn explosion → OOM / OS thread cap | Denial of service | D-04: clamp to `[1, 256]` in set_option dispatcher; reject out-of-range with `info string`. |
| Tampered tuning EPD (man-in-the-middle Zurichess fetch) → poisoned coefficients | Tampering | SHA256 sentinel in `fetch_tuning_data.py` matches Phase 2 02-03 pattern (cached `.sha256` checksum compared on each fetch); abort on mismatch. |
| Tampered vendored texel-tuner (compromised GitHub release) | Tampering | Pin upstream SHA in `tools/.cache/.texel-tuner.sha`. Plan 04-03 Task 1 records the verified SHA. Future updates require explicit SHA bump in a commit. |
| Data race in lockless TT under SMP → silent search-result corruption | Tampering | Phase 3 03-05 lockless XOR TT + PAR-03 TSan 16t×60s gate (Pitfall 36). Hard precondition for Plan 04-01. |
| `gen_coeffs.py` shell injection via tuner-emitted coeffs.json values | Tampering / Information disclosure | gen_coeffs.py emits to fixed path with no shell calls (verified — pure Python file write). Tuner output validated as JSON before codegen. |

## Sources

### Primary (HIGH confidence — verified via Read tool against this codebase)

- `.planning/phases/04-lazy-smp-texel-tuning/04-CONTEXT.md` — D-01..D-16 (locked decisions, Claude's discretion, deferred)
- `.planning/REQUIREMENTS.md` — Phase 4 owns PAR-04..09 + TUNE-01..10
- `.planning/ROADMAP.md` — Phase 4 success criteria #1..#6
- `.planning/PROJECT.md` — constraints (Lazy SMP only, NPS floor, etc.)
- `.planning/research/PITFALLS.md` — Pitfalls 10-19 (Phase 4 specific) + Pitfall 36 (TSan precondition)
- `src/chess_engine/engine/v7/include/engine.hpp` — per-thread tables already on Engine from Phase 3 03-01 D-03
- `src/chess_engine/engine/v7/include/tt.hpp` — lockless Hyatt-Mann XOR TT (16-byte AtomicEntry, memory_order_relaxed)
- `src/chess_engine/engine/v7/src/python_bindings.cpp` — `py::call_guard<py::gil_scoped_release>` already wired on all heavy-ops
- `src/chess_engine/engine/v7/src/uci_main.cpp` — setoption parser + wtime/btime parsing already present (memory hint #2 outdated)
- `src/chess_engine/engine/v7/src/search.cpp` — cancellation poll at lines 174, 79 (4096-node cadence)
- `src/chess_engine/engine/v7/CMakeLists.txt` — current target structure (v7_engine, v7_uci, tt_tsan_stress); v7_eval_static is the new addition
- `src/chess_engine/engine/v7/coeffs.json` + `tools/gen_coeffs.py` — codegen pipeline (skips `_`-prefixed keys; deterministic LF output)
- `src/chess_engine/engine/v7/include/eval.hpp` — `evaluate()` + `evaluate_entry()`; `eval_quiet()` does NOT exist yet (Plan 04-03 adds)
- `tools/gauntlet.py` — current `run` subcommand deferred; Plan 04-02 un-defers
- `tools/fetch_fastchess.py` — template pattern for `fetch_tuning_data.py`
- `tests/test_v7_engine.py` — RUN_BENCHMARKS NPS sentinel pattern
- `.planning/phases/01-skeleton-smoke/.continue-here.md` — build-host gate template
- `.planning/phases/02-gauntlet-harness-early/02-CONTEXT.md` — TC=10+0.1, c=1, 8moves_v3.pgn, pentanomial SPRT params
- `.planning/phases/03-lockless-tt-search-refinements-endgame/.continue-here.md` — PAR-03 TSan gate (hard precondition for Plan 04-01)
- `.planning/phases/03-lockless-tt-search-refinements-endgame/03-05-SUMMARY.md` — TSan plumbing complete, runtime gate deferred

### Secondary (MEDIUM confidence — community/canonical chess-programming references)

- Berserk depth-stagger pattern — shape (SkipDepths/SkipPhases arrays, modulo 20) is canonical across Berserk/Ethereal/Stockfish-derivatives; exact constants `[ASSUMED]` and must be re-verified at 04-01 design time against current upstream `thread.c`
- Stockfish ThreadPool cv-wake pattern — canonical across modern engines (Ethereal, Berserk, Koivisto all share the shape); design transcription only — GPL forbids code copy
- Stockfish-style quiet-position filter (`qsearch(p) != eval(p)`) — Pitfall 14 in PITFALLS.md, community standard
- Golden-section search for K-fit — Pitfall 13, mathematically optimal for unimodal loss in a bounded interval

### Tertiary (LOW confidence — `[ASSUMED]`, needs runtime verification at execution)

- texel-tuner upstream architecture (eval injection seam, sparse extraction API, ADAM defaults, CMake interop) — A1..A3, A10 in Assumptions Log
- Berserk SkipDepths/SkipPhases exact numeric arrays — A4
- Zurichess EPD URL still live — A6
- 1024-node cancellation poll sufficient at SMP — A7 (PAR-08 sentinel is the empirical check)
- Avg-|eval| ratio falls in [0.85, 1.15] for healthy tune — A8 (rescale-verify gauntlet is safety net)

## Metadata

**Confidence breakdown:**

- E1 Lazy SMP design: **HIGH** — every primitive verified in current codebase via Read tool; Phase 3 03-01 D-03 already laid the per-thread scaffold.
- E1 depth-stagger constants: **MEDIUM** — pattern shape canonical; exact array values `[ASSUMED]` and must be re-fetched at 04-01 design time.
- E2 texel-tuner integration: **MEDIUM** — vendoring decision and CMake architecture are sound; upstream layout details `[ASSUMED]` and must be verified at 04-03 Task 1.
- Gauntlet infra: **HIGH** — Phase 2 02-03/04 outputs verified in current codebase; PAR-09 and SC#6 are new invocations of existing infra.
- Codegen pipeline: **HIGH** — gen_coeffs.py read; `_`-prefix skip verified at line 103.
- Pitfalls 10-19: **HIGH** — read in full from PITFALLS.md.
- PAR-03 TSan precondition: **HIGH** — deferred status confirmed via Phase 3 `.continue-here.md`.

**Research date:** 2026-05-17
**Valid until:** 2026-06-14 (30 days — stable domain; only texel-tuner upstream churn or Berserk re-tune would invalidate)
