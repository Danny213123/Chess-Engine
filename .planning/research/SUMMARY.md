# Project Research Summary

**Project:** Chess-Engine — V7 milestone (classical HCE engine fork of V6)
**Domain:** Classical alpha-beta chess engine with hand-crafted eval, Lazy SMP, Texel tuning, and Syzygy tablebases
**Researched:** 2026-05-15
**Confidence:** HIGH

## Executive Summary

V7 is **not a green-field engine**: it is a forked, hardened, parallelized, tuned, and tablebase-aware evolution of V6's existing C++17 pybind11 module. V6 already ships magic bitboards, alpha-beta+TT, aspiration windows, null-move (fixed `R=4`), an LMR table, LMP, futility/RFP, and a tapered classical eval. V7's job is to (a) **harden** what's there (PVS audit, adaptive null-move, log-table LMR with context, mate-score TT handling, repetition + 50-move correctness), (b) **add** the things V6 lacks (history/counter-move/continuation history, in-engine endgame eval, Syzygy probing via Fathom, lockless TT), (c) **parallelize** with Lazy SMP under a properly-released GIL, and (d) **tune** every eval coefficient with Texel against Zurichess `quiet-labeled.epd`. The ship signal is a head-to-head V7-vs-V6 gauntlet under SPRT — not an Elo target.

Experts in this space converge on a remarkably narrow recommended stack: **jdart1/Fathom** (the only viable embeddable Syzygy probe), **fastchess** (cutechess-cli successor, soon to power Stockfish's Fishtest), **GediminasMasaitis/texel-tuner** (MIT, drop-in standalone tuner), the **Zurichess quiet-labeled dataset** (~725k positions, the canonical Texel ground truth), and **raw `std::thread` + `std::atomic`** for Lazy SMP with **Hyatt-Mann lockless XOR** TT entries. Pybind11 stays pinned at v2.12.0 and CMake at 3.15 to avoid gratuitous V6-baseline churn. All recommendations are MIT-compatible with the parent repo.

The dominant risks are **silent correctness bugs** rather than design failures: TT mate-score off-by-ones, LMR applied to forcing moves, null-move in zugzwang, lockless-TT torn writes, GIL not released (which secretly serializes Lazy SMP), Syzygy DTZ-vs-WDL confusion, Texel K-factor refit per iteration, and gauntlets run with mismatched hash/threads/TC. The mitigation discipline is also narrow: build the **C1 smoke milestone (V7 plays a legal game vs V6)** as fast as possible, stand up the **gauntlet harness and lockless TT before Lazy SMP**, treat each pitfall in PITFALLS.md as a unit-testable gate, and accept that gauntlet outcome — not "loss decreased" or "feels stronger" — is the only valid validation signal.

## Key Findings

### Recommended Stack

V7 layers a small, tightly-scoped set of new additions onto the V6 baseline. Everything below is detailed in [STACK.md](./STACK.md). The V6 stack (C++17, pybind11 v2.12.0, CMake 3.15, magic bitboards) is **inherited unchanged** — no version bumps, no language bump.

**Core technologies (NEW for V7):**
- **jdart1/Fathom** (git submodule, pinned commit) — Syzygy WDL/DTZ probing for 3-7-men. The only maintained portable Syzygy probe; MIT; thread-safe by default. Avoid `basil00/Fathom` (unmaintained).
- **GediminasMasaitis/texel-tuner** (vendored under `tools/`) — Standalone MIT-licensed Texel tuner with sparse coefficient extraction, Adam, multithreaded. Avoid `peterosterlund2/texel`'s built-in tuner (GPL v3, contaminates the MIT repo).
- **Zurichess `quiet-labeled.epd`** (~725k positions, downloaded by script, NOT bundled) — Canonical Texel ground truth labeled with game results. ROFCHADE reports ~+75-80 Elo from PST/material tuning on this set alone.
- **fastchess** (developer tool, prebuilt binary under `tools/`) — Drop-in cutechess-cli replacement. Pentanomial SPRT, much better high-concurrency stability. Required because UCI is the only protocol it speaks (V7 must therefore expose a `v7_uci` binary alongside the pybind11 module).
- **`std::thread` + `std::atomic` + Hyatt-Mann XOR TT** (no third-party library) — Standard Lazy SMP pattern across Stockfish/Ethereal/Berserk/Weiss. Hand-rolled is the universal choice; do not introduce Boost.Asio or `BS::thread_pool`.
- **Pinned: pybind11 v2.12.0, CMake ≥3.15, C++17** — Match V6 exactly. Pybind11 v3.0 has an ABI break and CMake-var rename that buys V7 nothing.

**Reference engines to study (Lazy SMP):** Berserk (cleanest readable), Ethereal (canonical mid-complexity), Stockfish PR #467 (the original Lazy SMP merge). Realistic Elo gain: ~20-32 Elo from 1→16 threads at fast TC.

**Test position suites (developer-time):** STS (15-chapter strategic), WAC (300 tactical), Bratko-Kopec — all EPD format, useful for regression alongside the gauntlet.

### Expected Features

Detailed in [FEATURES.md](./FEATURES.md). V7 is calibrated to V6's existing surface — most "features" are tightenings rather than net-new additions.

**Must have (table stakes):**
- **Search hardening:** PVS audit, aspiration window re-search-on-fail with widening + cap, adaptive null-move R with zugzwang guard, log-table LMR with context-aware adjustments (PV/cut/improving/in-check exclusions), LMP/RFP/futility tuning, killers + history + counter-moves + SEE-bucketed move ordering, repetition detection inside the tree (not just root), 50-move TT cutoff handling, mate-score ply adjustment in TT.
- **Eval hardening + tuning:** keep V6's tapered MG/EG eval skeleton (PSTs, mobility, pawn structure, king safety, bishop pair, knight outposts, rook on 7th, tempo) but **all coefficients become Texel-tuned**. Add connected/phalanx pawns. Convert king-safety to attack-units → `SAFETY_TABLE[]` indexed lookup.
- **Endgame:** in-engine KPK bitbase + opposition + wrong-bishop+RP rule (basic fortress hints optional and conservative), continuous phase blending.
- **Syzygy:** Fathom integrated; `tb_probe_root_dtz` at root, `tb_probe_wdl` inside search gated by `popcount≤TB_LARGEST && halfmove==0 && castling==0 && depth≥threshold`. Optional download script for 3-4-5 men (default) and 6-men (opt-in, ~150 GB).
- **Texel pipeline:** sparse coefficient vectors, K-factor fit **once** at start, train/validation split, codegen of `coeffs.cpp` from JSON to keep names in single source of truth.
- **Gauntlet harness:** fastchess-driven, V6-vs-V6 sanity probe, identical hash/threads/TC, opening book seeding (`8moves_v3.pgn`), pentanomial SPRT, persisted command line.

**Should have (differentiators):**
- **Search:** singular extensions + multi-cut bolt-on, ProbCut (gauntlet-gated), IIR (cheap, ~10-20 Elo), recapture extensions, continuation history, capture history, aspiration window widening on fail.
- **Eval:** threats / hanging pieces, indexed king-safety table, pawn hash table (5-15% NPS recovery to help the 20% NPS budget), material imbalance corrections.
- **Endgame:** 6-piece Syzygy support (build-flag in Fathom).
- **Tuning:** L1/L2 regularization, ADAM/AdaGrad over vanilla SGD.
- **Lazy SMP** — required by the milestone but listed as a differentiator because it is the parallelism feature, not a base-search heuristic. ~80 Elo at 4 threads, ~120 at 8.

**Defer / Anti-features (explicit "do not build" in V7, all per PROJECT.md "Out of Scope"):**
- NNUE / neural eval, AlphaZero-style MCTS, SPSA self-play tuning.
- Opening book at play time (test-suite book for the gauntlet is a separate, in-scope concern).
- Bundled tablebases in repo or releases.
- MultiPV mode, eval-breakdown UI, in-app gauntlet UI.
- `GameManager` engine-ladder refactor, singleton replacement, v5* fork consolidation.
- CUDA / GPU acceleration (V7 is CPU/Lazy SMP only).
- Hard ELO targets (gauntlet is the ship signal).
- Native UCI binary as a *shipping* artifact (a developer-only `v7_uci` binary IS built, only as a fastchess-driving tool).

### Architecture Approach

Detailed in [ARCHITECTURE.md](./ARCHITECTURE.md). V7 lives at `src/chess_engine/engine/v7/` and **preserves V6's external Python contract verbatim** — `find_best_move(game_state, valid_moves, engine, search_info)` is unchanged. Internally, V7 is a much larger system: ~25 headers, three CMake targets (`v7_engine` Python module, `v7_core` object library, `v7_uci` executable, `fathom` static lib), a Texel-tuner Python script that calls into the same `.so`, and a Python adapter that holds a process-singleton `V7Engine` instance so the TT survives across moves (a ~30 Elo win that V6 currently leaves on the table).

**Major components:**
1. **bindings + Python adapter** — pybind11 surface (`find_best_move`, `stop`, `set_syzygy_path`, `set_coeffs`); releases the GIL via `py::call_guard<py::gil_scoped_release>()` for the entire search; cancellation atomic flipped by a direct `algo_v7.stop()` call from `GameManager.stop_search` (not a watchdog thread). **Important:** V6's binding currently *ignores* the Python `search_info` argument — V7 must close this gap.
2. **thread_pool (Lazy SMP)** — N `std::thread` workers, each with private `Board`, `history`, `killers`, `counter`, search stack; communicate exclusively via the shared TT.
3. **Lockless TT (Hyatt-Mann XOR)** — Two `std::atomic<uint64_t>` fields (`xkey = key XOR data`, `data`), `memory_order_relaxed`, no per-bucket locks. **Must be written before Lazy SMP exists.**
4. **Search subsystem** — PVS-flavored alpha-beta + qsearch + movepicker + history/SEE + LMR/null/futility/LMP + (later) singular/multi-cut/probcut/IIR.
5. **Eval subsystem** — `coeffs.cpp` as single source of truth (non-`constexpr` so Texel can mutate), tapered MG/EG, PSTs + king safety + pawns + mobility + threats; Texel-codegen-friendly.
6. **Endgame module** — KPK bitbase + opposition + wrong-bishop-RP + (conservative) fortress hints + continuous phase. Short-circuits to Syzygy when in TB range (Syzygy wins on conflict).
7. **Syzygy wrapper** — Wraps Fathom (`extern/fathom/` git submodule) with custom `overrides/tbconfig.h` to reuse V7's own attack tables. Init-time file-count + KRk smoke check; platform-aware path separator (`;` Windows, `:` POSIX).
8. **Tune layer** — `tune.cpp` exports `eval_quiet(fen)`, `set_coeff(name,val)`, `get_coeff(name)`; Python tuner runs gradient against the same `.so` (~10⁵ positions/sec, no subprocess boundary).

**Build order (critical path):** A1 skeleton → A2 board/movegen → (B1 search ∥ B2 eval ∥ B3 Syzygy) → **C1 smoke milestone (V7 plays a legal game vs V6)** → (D1 lockless TT ∥ D2 search refinements ∥ D3 endgame) → (E1 Lazy SMP ∥ E2 Texel) → F1 gauntlet → G1 ship. **Parallelizable subsystems:** B1/B2/B3 (touch disjoint files); D1/D2/D3 likewise; E1/E2 likewise. **Hard ordering:** D1 must precede E1; F1 should be stood up *as part of* C1 (not delayed).

**Integration points outside `src/chess_engine/engine/v7/` (verified against the actual repo):** `game_manager.py` (4 lines: import, AVAILABLE_ENGINES entry, set_engine_version branch, ai_move dispatch with proper SearchInfo wiring), `client/src/App.jsx` (two `<option value="v7">` entries — one each for white/black selectors — plus updating the "build may take a while" warning at line 235), `cli/src/config.js` (add `v7Built`, `syzygyPath`, `syzygyMaxPieces`), `cli/src/index.js` (`build v7`, optional `syzygy download`), `pyproject.toml` (no runtime deps changes), `.gitignore` and new `.gitmodules` (Fathom submodule), `tests/test_v7_engine.py`. **Crucially: `app.py` requires no changes** — `/api/engine` is generic.

### Critical Pitfalls

PITFALLS.md enumerates **44 pitfalls** with full phase mapping. The top 7 by Elo cost or milestone risk:

1. **Lockless TT torn writes (Pitfall 9, phase D1)** — Must be implemented with two `std::atomic<uint64_t>` fields and TSan-stress-tested with 16 threads × 60s before E1 Lazy SMP starts. Otherwise: silent illegal-move bugs that take days to track down.
2. **GIL not released → no parallelism (Pitfall 11, phase A1+E1)** — The single most common pybind11 mistake. Wire `py::call_guard<py::gil_scoped_release>()` on the binding from day one. NPS at 4 threads must be ≥3× single-thread; if not, the GIL is the culprit.
3. **History/killer tables shared across Lazy SMP threads (Pitfall 12, phase E1)** — Defeats divergence. Per-thread for history/killers/counter/continuation; shared only for TT and the Syzygy probe cache.
4. **TT mate score not adjusted for ply (Pitfall 1, phase B1)** — Off-by-one in `score_to_tt`/`score_from_tt` produces wrong mate distances, search instability, fake "mate in N" announcements. Must be in place before C1.
5. **Texel K-factor refit per iteration (Pitfall 13, phase E2)** — Breaks the algorithm's contract; coefficients optimize K instead of eval. Fit K once via golden-section search, persist alongside coefficient JSON.
6. **Syzygy DTZ vs WDL confusion (Pitfall 20, phase B3)** — Use `tb_probe_root_dtz` only at root, `tb_probe_wdl` only inside search. Mixing them throws TB wins by violating the 50-move rule.
7. **Gauntlet TC/hash/threads not identical (Pitfall 29, phase F1)** — Run V6-vs-V6 sanity probe first; result must be ~0 Elo. Persist the exact fastchess command in every result file. Pentanomial SPRT, ≥1000 games for ship verdict.

Other notable pitfalls covered in PITFALLS.md but not duplicated here: aspiration infinite re-search, null-move zugzwang, LMR off-by-one applied to forcing moves, singular extension search explosion, probcut/multi-cut margins, repetition handling, 50-move TT cutoff, Texel quiet-position filtering, Texel coefficient name mismatch, Texel local-minimum trap, Texel overfit to Zurichess, search-eval co-tuning shift, Windows Syzygy path separator, KPK-vs-Syzygy contradiction, fortress false positives, time forfeits silently counted, laptop thermal throttling, Lazy SMP non-determinism breaking 1-thread→4-thread tuning transfer, plus 5 project-management/integration pitfalls (NNUE scope creep, V5/V6 refactor mid-milestone, V6 broken by V7 dispatch, MSVC-vs-MinGW build issues, App.jsx engine-list drift, pybind11 import side-effects, V7 missing from CLI bench).

## Implications for Roadmap

The research strongly suggests a **5-phase roadmap** matching the A→G build groups in ARCHITECTURE.md §8 and the pitfall phase-mapping in PITFALLS.md. The C1 smoke milestone is the centerpiece: it converts the project from green-field uncertainty to an iterable baseline. F1 (gauntlet harness) should be stood up *as part of* C1 — not deferred to the end — so every subsequent change is gauntlet-validated.

### Phase 1: Skeleton + Smoke (A1–A2 → B1∥B2∥B3 → C1)
**Rationale:** Get V7 to "plays a legal game vs V6 end-to-end through the existing UI" as fast as possible. This pins down build, dispatch, and integration risks early; everything afterward is incremental. Subsystems B1/B2/B3 are explicitly parallelizable (disjoint files).
**Delivers:** V7 module skeleton (CMake, native_build.py, bindings with `gil_scoped_release` from day one), ported board/movegen/magic/zobrist (perft parity vs V6 to depth 6), sequential search (PVS, qsearch, TT, iterative deepening, hardened aspiration windows, mate-score TT handling, repetition + 50-move correctness, time management with ≥10% safety margin), eval rewrite scaffolding (`coeffs.hpp` ready for tuning), Fathom integration (root DTZ + in-tree WDL with proper gating), V7 dispatched from `GameManager` and selectable in both UI dropdowns, CLI `bench v7` / `perft v7` working.
**Addresses (FEATURES):** Table-stakes search + eval skeleton + Syzygy.
**Avoids (PITFALLS):** 1 (mate-score TT), 2 (aspiration loop), 3 (null-move zugzwang), 7 (repetition), 11 (GIL), 20 (DTZ vs WDL), 21 (probe failure), 22 (excessive probing), 23 (TB validation), 24 (Windows path), 33 (time forfeits), 40 (V6 broken by dispatch), 41 (Windows MSVC build), 42 (App.jsx drift), 43 (pybind11 side-effects), 44 (CLI bench).

### Phase 2: Gauntlet harness early (F1, built during C1)
**Rationale:** Pitfall 37 — "skipping gauntlet harness early — flying blind for weeks" — is a milestone-killer. Stand up F1 as the *validation* tool the moment C1 is reachable, even if hacky. Every subsequent phase regression-tests against it.
**Delivers:** `v7_uci` standalone binary, fastchess invocation script with persisted command-line, V6-vs-V6 sanity probe ("must return ~0 Elo"), opening book (`8moves_v3.pgn`), pentanomial SPRT with documented bounds (`elo0=0 elo1=10 alpha=0.05 beta=0.05`), result aggregator that flags time forfeits separately.
**Uses (STACK):** fastchess, `8moves_v3.pgn`, the v7_uci CMake target.
**Avoids (PITFALLS):** 29 (TC/hash/threads parity), 30 (SPRT misconfigured), 31 (opening book bias), 32 (insufficient game count), 33 (time forfeits as losses), 34 (laptop thermal — environment hygiene).

### Phase 3: Lockless TT + Search Refinements + Endgame (D1∥D2∥D3)
**Rationale:** All three are independent (touch disjoint files: D1=`tt.cpp`, D2=`search/`, D3=`endgame.cpp`). **D1 must complete before E1 starts** (Pitfall 36) — gate this with the 16-thread × 60s TSan stress test from Pitfall 9.
**Delivers:**
- **D1:** Hyatt-Mann XOR TT with two `std::atomic<uint64_t>` slots, 50-move-aware probe behavior, packed entry layout (key XOR data, move/score/depth/bound/age).
- **D2:** Adaptive null-move R + zugzwang guard, log-table LMR with context (PV/cut/improving/in-check exclusions, re-search at depth-1), LMP/RFP/futility margin retune, killers + history + counter-move + (later) continuation history + capture history, IIR, singular extensions + multi-cut bolt-on (depth ≥ 8 gating), ProbCut (gauntlet-gated — may net-zero, accept that), recapture extensions.
- **D3:** Continuous phase blend (Stockfish-style 0-256), KPK bitbase + opposition + wrong-bishop-RP rule (king-distance check), conservative fortress hints (or skip entirely — Stockfish removed theirs), Syzygy short-circuits in-engine endgame eval when in TB range.
**Avoids (PITFALLS):** 4 (LMR off-by-one), 5 (singular explosion), 6 (multi-cut/probcut margins), 8 (50-move TT cutoff), 9 (lockless TT correctness), 25 (KPK vs Syzygy), 26 (phase detection), 27 (fortress false positive), 28 (wrong-bishop rule).

### Phase 4: Lazy SMP + Texel Pipeline (E1∥E2)
**Rationale:** Both depend on prior phases (E1 on D1; E2 on B2 + C1) but are otherwise independent (E1 in `thread_pool.cpp`/`bindings.cpp`, E2 in `tune.cpp`/Python tools). E1 finally turns on the parallelism the project has been preparing for; E2 produces the V7 release artifact (tuned coefficient JSON committed to source).
**Delivers:**
- **E1:** Lazy SMP thread pool, per-thread history/killers/counter/continuation/stack, helper threads with depth-stagger pattern (Berserk-style), atomic stop flag wired from Python via `algo_v7.stop()` called from `GameManager.stop_search`, NPS scaling test (≥3× from 1→4 threads), cancellation latency test (<50ms), 4-thread vs 1-thread Elo gauntlet (≥40 Elo gain).
- **E2:** Texel pipeline against Zurichess `quiet-labeled.epd` with re-filtering (drop in-check, drop where qsearch ≠ eval, drop TB endgames), sparse coefficient extraction, K-factor fit *once* at start (golden-section), train/10%-validation split, multi-seed tuning (V6 seed + neutral seed + perturbed seed; gauntlet picks winner), ADAM optimizer, codegen `coeffs.cpp` from JSON for single-source-of-truth names, post-tune search-margin re-scaling proportional to avg-eval shift.
**Uses (STACK):** GediminasMasaitis/texel-tuner, Zurichess `quiet-labeled.epd`, `std::thread` + `std::atomic` (no Boost/TBB).
**Avoids (PITFALLS):** 10 (cancellation), 11 (GIL — verified here), 12 (per-thread state), 13 (K refit), 14 (non-quiet positions), 15 (coefficient mismatch), 16 (local minimum), 17 (overfit), 18 (phase interpolation), 19 (search-eval co-tuning), 35 (1-thread vs 4-thread tune transfer).

### Phase 5: Final gauntlet + Ship (G1)
**Rationale:** PROJECT.md's explicit ship signal. Gauntlet at production thread count (the count V7 will run at via the UI), AND a sanity-probe at 1 thread, AND a re-run for reproducibility.
**Delivers:** ≥1000-game pentanomial SPRT V7-vs-V6 at fixed TC and identical hash/threads/options, "Looks Done But Isn't" checklist (all 16 items in PITFALLS.md) executed, README updated with Syzygy download note + thread config, V7 declared shipped when SPRT passes ≥2 independent runs.
**Avoids (PITFALLS):** 32 (insufficient game count), 35 (non-determinism), 38 (scope creep — re-read PROJECT.md), 39 (V5/V6 refactor — V7 PRs do not touch other engine dirs).

### Phase Ordering Rationale

- **A1→A2→B/C/D→C1** is a dependency chain (you can't build search without movegen, can't smoke-test without all three subsystems present); **B1/B2/B3 parallelize internally** because they touch disjoint files. F1 is built *during* C1 because PITFALLS.md "Skipping the gauntlet harness early" is one of the most common milestone-killers in this domain.
- **D1 → E1 is hard-ordered.** Building Lazy SMP on a single-threaded TT is the silent-corruption death spiral of Pitfall 36. Gate E1 on D1 with a TSan stress test.
- **D2 and D3 can land in any order relative to E1/E2** as long as the gauntlet is re-run after each landing (the F1-early principle).
- **Texel (E2) must come after eval scaffolding (B2) and the gauntlet (F1)** but is independent of Lazy SMP (E1). Run them in parallel work-streams.
- **G1 is gated by ≥2 independent SPRT runs** — single-result cherry-picking is Pitfall 32 / Validation Mistake "Ship after one good gauntlet".

### Research Flags

Phases likely needing deeper research during planning (suggested `/gsd-research-phase` triggers):

- **Phase 3 → D1 (lockless TT):** Entry packing layout, exact memory ordering for `std::atomic<uint64_t>` halves under V7's specific access patterns, age field semantics across `find_best_move` calls. Hyatt-Mann is well-understood as an algorithm but the bit-packing is a fresh design call. Worth a short focused pass before coding.
- **Phase 3 → D3 (endgame eval):** KPK bitbase generation (offline build) vs precomputed-table-link vs runtime-generation tradeoff (Elo + binary-size implications), exact opposition/wrong-bishop predicates with test positions enumerated, fortress detection — go/no-go decision (Stockfish removed theirs; V7 may also).
- **Phase 4 → E2 (Texel):** Gradient method (finite-difference vs analytic), step size schedule, K-factor exact value for V7's eval scale, convergence criteria, multi-seed strategy, validation-suite choice. The ARCHITECTURE.md research already flagged these as "benefit from a phase-local research pass before coding."

Phases with standard, well-documented patterns (skip research-phase, go straight to planning):

- **Phase 1 (A1/A2/B1/B2/B3/C1):** Mechanical port from V6 + standard textbook search/eval. STACK.md and ARCHITECTURE.md cover everything needed.
- **Phase 2 (F1):** Mechanical fastchess invocation. Sample command lines in STACK.md and PITFALLS.md.
- **Phase 3 → D2 (search refinements):** Each individual technique (LMR/null/futility/LMP/singular/probcut) is exhaustively documented on chessprogramming.org and in the Berserk/Ethereal source. The pitfalls (4, 5, 6) ARE the "research" — make them unit-test gates and code straight from the references.
- **Phase 4 → E1 (Lazy SMP):** Berserk's `src/thread.c` is the recommended reference; the pattern is ~150 lines of `std::thread` + atomic. The pitfalls (10, 11, 12, 35) ARE the "research."
- **Phase 5 (G1):** Re-runs of Phase 2 infrastructure with stricter gates.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All version pins, library identities, license claims, and dataset provenance cross-verified against official repos within the last 12 months. Performance claims (e.g., +75 Elo from Texel, 20-32 Elo from 1→16 threads Lazy SMP) are MEDIUM — order-of-magnitude estimates from individual reports. |
| Features | HIGH | V6 baseline verified directly from `src/chess_engine/engine/v6/include/{search,eval}.hpp`. All "table stakes" / "differentiator" / "anti-feature" calls cross-checked against PROJECT.md scope and chessprogramming.org canonical references. |
| Architecture | HIGH on internal C++ structure / Lazy SMP / Fathom integration; HIGH on integration-points checklist (verified file-by-file against actual repo state); MEDIUM on Python-side cancellation contract (V6 currently *ignores* the Python-side `SearchInfo` token — V7's recommended fix is well-specified but is itself a behavior change worth confirming during planning). |
| Pitfalls | HIGH on search/threading/Texel/Syzygy (well-documented in TalkChess, CPW, Stockfish/Ethereal/Weiss commit history); HIGH on integration pitfalls (verified against `.planning/codebase/` + the actual file state). |

**Overall confidence:** HIGH

### Gaps to Address

- **V6 binding cancellation behavior:** Research found that V6's `python_bindings.cpp` ignores the Python `search_info` argument and constructs its own internal `SearchInfo`. V7's recommended fix (atomic stop flag + `algo_v7.stop()` from `GameManager.stop_search`) is well-specified, but its *behavior change* relative to V6 should be confirmed during Phase 1 planning (does V6's current behavior break anything that V7 wiring would surface?). **Action:** verify in A1 by writing a cancellation-latency test against both V6 and V7.
- **NPS-within-20%-of-V6 budget:** PROJECT.md sets a soft floor of ~20% NPS regression. Texel-tuned eval, Syzygy probing, and lockless TT all cost NPS. The pawn-hash-table and incremental-piece-count differentiators in FEATURES.md are recovery levers but not table-stakes. **Action:** add an NPS regression check to the gauntlet harness (Phase 2/F1) that fails the build if NPS drops >20% even before strength is measured.
- **Tablebase storage path defaults:** ARCHITECTURE.md §6 proposes platform-specific defaults (`~/.local/share/chess-engine/syzygy/` on Linux/macOS, `%LOCALAPPDATA%\chess-engine\syzygy\` on Windows) but leaves the actual choice to the download script. **Action:** confirm during Phase 1 planning of the `cli/src/index.js syzygy download` subcommand.
- **6-piece Syzygy cost-benefit:** PROJECT.md mentions "3-4-5-6 men" but 6-men is ~150 GB of tablebases and very rarely hit in middlegame search. **Action:** treat 6-men as opt-in (download flag), default to 3-4-5; document this in the Phase 1 README.
- **fastchess on Windows:** Windows Defender is known to quarantine `fastchess.exe`. **Action:** document the whitelist requirement in Phase 2 setup.
- **TSan availability on Windows MSVC:** ThreadSanitizer is not available on MSVC; the lockless TT stress test (Pitfall 9) needs a Linux/macOS/WSL run. **Action:** Phase 3 plan must explicitly require WSL or Linux for the D1 → E1 gate.

## Sources

### Primary (HIGH confidence)

Research files (all in this project):
- [STACK.md](./STACK.md) — Library/version recommendations, license analysis, install commands
- [FEATURES.md](./FEATURES.md) — Feature landscape with V6 baseline calibration
- [ARCHITECTURE.md](./ARCHITECTURE.md) — V7 module layout, Lazy SMP + GIL handling, integration points
- [PITFALLS.md](./PITFALLS.md) — 44 pitfalls with phase mapping, "Looks Done But Isn't" checklist
- [.planning/PROJECT.md](../PROJECT.md) — V7 milestone scope, constraints, key decisions

External (full citations in the four research files):
- chessprogramming.org — Lazy SMP, Shared Hash Table, LMR, Singular Extensions, Null Move Pruning, Multi-Cut, ProbCut, Texel's Tuning Method, Syzygy Bases
- Hyatt & Mann (2002) — A Lockless Transposition Table Implementation for Parallel Search
- Stockfish source + PR #467 (original Lazy SMP merge)
- Ethereal source (canonical mid-complexity reference); Berserk source (cleanest readable Lazy SMP)
- jdart1/Fathom (Syzygy probing library, MIT)
- Disservin/fastchess (gauntlet runner, MIT)
- GediminasMasaitis/texel-tuner (standalone Texel tuner, MIT)
- Zurichess `tuner.7z` — `quiet-labeled.epd` ground truth dataset
- pybind11 official docs (GIL section), issues #1446 and #2215

### Secondary (MEDIUM confidence)

- ROFCHADE technical page (+75-80 Elo from Texel on Zurichess — single report)
- University of Oslo MSc thesis on Lazy SMP (academic walkthrough with Elo measurements)
- TalkChess forum threads on Texel pitfalls, Lazy SMP tradeoffs, Syzygy probe gating
- Octavi Font — pybind11 multithreading practical write-up
- Sesse / Lichess Syzygy mirror infrastructure

### Tertiary (LOW confidence)

None — every recommendation in this summary rests on at least HIGH confidence for identity/version and MEDIUM confidence for performance expectations.

---
*Research completed: 2026-05-15*
*Ready for roadmap: yes*
