# Phase 3: Lockless TT + Search Refinements + Endgame - Research

**Researched:** 2026-05-17
**Domain:** C++17 chess-engine search internals — lockless transposition table, modern alpha-beta refinements, endgame evaluation
**Confidence:** HIGH on V6/V7 source structure (verified by direct read); HIGH on CONTEXT.md decisions (cited verbatim); MEDIUM on canonical Stockfish/Ethereal patterns (training knowledge — `[ASSUMED]` where not cross-checked against V6 source).

## Summary

Phase 3 is the V7 strength step-change. It has three parallelizable subsystems — **D1** (Hyatt-Mann lockless TT in `tt.cpp`), **D2** (full modern search refinement stack in `search.cpp` / new `search/` helpers), and **D3** (endgame eval in new `endgame.cpp`). The CONTEXT.md `<decisions>` block already locks all the high-stakes choices (perf-bug fix in Plan 03-01, two-tier refinement landing, age-then-depth single-slot TT, KPK build-time codegen, fortress default-OFF, ENDG coefficients via `coeffs.json`). This research's job is **not** to re-open those decisions but to give the planner the concrete formulas, off-by-one watch-points, and per-refinement gauntlet expectations needed to write tasks that ship correctly the first time.

**Primary recommendation:** Plan 03-01 must land **before** anything else and must rebuild the search scaffold (persistent killers/history on `Engine`, triangular PV array indexed by ply, `info.depth` contract fix) — not a minimal-diff patch. Without this, every D2 refinement layered on top inherits broken move ordering and PV allocator pressure, and the per-tier gauntlets will show false regressions that bisect to the wrong commit.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** The 3 known Phase 1 perf bugs (engine.cpp:99 depth-cap overwrite, search.cpp:267 killers/history stack-reset, search.cpp `std::vector<Move>` PV alloc) are fixed in **Plan 03-01** (first plan of Phase 3). Phase boundary remains Phase 3; no separate Phase 1 gap-closure milestone.
- **D-02:** After Plan 03-01 merges, a **blocking human checkpoint** runs a 500-game V7-vs-V6 gauntlet on a build host. The resulting `summary.json` is persisted as `.planning/gauntlets/baseline/summary.json` (or a clearly-named directory) and becomes the canonical reference for Success Criterion #2 (Phase 3 V7 must beat THIS baseline by ≥30 Elo). All later Phase 3 gauntlets compare against this file.
- **D-03:** Plan 03-01 builds the **production scaffold** that later plans extend:
  - Persistent `killers[][2]` and `history[][]` tables on `Engine` member state (or per-ply `SearchStack` indexed by ply).
  - Triangular PV array allocated once (e.g., `Move pv[MAX_PLY][MAX_PLY]`) and indexed by ply — no per-recursion `std::vector` allocs.
  - `info.depth` contract clarified so `iterative_deepening`'s `info.depth = depth` cannot silently overwrite the caller's max-depth bound.
  - Acceptance: bench NPS ≥ 200k on the standard position (sanity floor; final NPS gate is the per-gauntlet sentinel).
- **D-04:** Search refinements split into **two tiers across two plans**:
  - **Plan 03-02 (proven cheap):** SRCH-03 (adaptive null move + zugzwang guard), SRCH-04 (LMR with context), SRCH-05 (RFP/futility/LMP), SRCH-06 (killers + history + counter-move + SEE-bucketed captures), SRCH-11 (IIR/IID), SRCH-12 (check + recapture extensions).
  - **Plan 03-03 (aggressive):** SRCH-07 (continuation + capture history), SRCH-08 (singular extensions, depth ≥8 with verification), SRCH-09 (multi-cut, depth ≥8), SRCH-10 (ProbCut — explicitly gauntlet-gated, may revert to OFF).
- **D-05:** Mid-Phase-3 validation bar = **non-regression mini-gauntlet** after each tier (200-game gauntlet vs `baseline.json`, lower-bound Elo > −10). Final Phase 3 ship gate = **500–1000 game pentanomial SPRT** vs `baseline.json` showing ≥30 Elo. SPRT params: `elo0=0 elo1=10 alpha=0.05 beta=0.05`. All gauntlets are blocking human checkpoints on the build host.
- **D-06:** Each search refinement exposed as a **UCI option, default ON**: `UseNullMove`, `UseLMR`, `UseRFP`, `UseFutility`, `UseLMP`, `UseSingular`, `UseMultiCut`, `UseProbCut`, `UseIIR`, `UseCheckExt`, `UseRecaptureExt`. Plugs into the v7_uci `setoption` parser (Plan 02-01).
- **D-07:** Hyatt-Mann lockless TT — **two `std::atomic<uint64_t>` slots per entry**: `xkey = key XOR data`, and `data` (packed). Single entry per bucket (cluster size = 1). Replacement policy: **age-then-depth**. Multi-slot clusters explicitly deferred to Phase 4.
- **D-08:** PAR-03 TSan verification = `scripts/tt_tsan_stress.sh` (or CMake target) that builds a standalone TT-only harness with `-fsanitize=thread` and runs 16 threads × 60 seconds of randomized probe/store. Runs on **WSL/Linux/macOS as blocking human checkpoint at end of Phase 3** — TSan unavailable on MSVC.
- **D-09:** TT entry packing **inherits V6's 64-bit layout verbatim** from `src/chess_engine/engine/v6/include/tt.hpp` / `src/tt.cpp`. Planner must read V6's actual layout and mirror bit-for-bit. Only structural change: entry wrapped in `std::atomic<uint64_t>` for the Hyatt-Mann XOR contract. No new fields, no widened bit fields.
- **D-10:** **KPK bitbase generation = build-time codegen.** Add `tools/gen_kpk.py` (mirrors `tools/gen_coeffs.py`) that computes all 163,328 legal positions and emits `src/chess_engine/engine/v7/src/kpk_bitbase.cpp` containing a packed `static const uint32_t KPK[...]` table (~32 KB). The .cpp output is **gitignored**; the .py generator and a deterministic test fixture are committed. Runtime probe = O(1) bit lookup. Acceptance: pytest verifies the lookup matches Fathom KPK probe on all 163,328 positions.
- **D-11:** ENDG-05 (conservative fortress hints): **full framework attempted, behind a UCI toggle that defaults OFF.** Plan 03-04 lands implementation with `UseFortressEval` default OFF. Separate scoped validation gauntlet (added in Plan 03-04 or as tail task) flips it ON and runs ≥500 games vs default-OFF V7; ship default-ON only if gauntlet shows clearly-positive Elo. If validation fails, ship default-OFF with REQUIREMENTS.md ENDG-05 annotated `[implemented but disabled — fortress validation gauntlet showed regression]`.
- **D-12:** New endgame eval coefficients (opposition value, wrong-bishop-rook-pawn scale, KPK rule bonuses, fortress weights, phase-blend constants for ENDG-04) added to `coeffs.json` with hand-tuned initial values. They flow through the existing `gen_coeffs.py → coeffs.cpp` codegen. No new hand-tuned C++ `constexpr` constants for endgame terms.

### Claude's Discretion

- Exact plan-to-wave layout — D1 (Plan 03-05 candidate) is file-disjoint (`tt.{hpp,cpp}`) from D2 and D3, so the planner may run D1 in parallel with the 03-02/03-03/03-04 chain. Constraint: 03-01 must land first; final ship-SPRT runs after all four merge.
- Exact UCI option names so long as `Use<Refinement>` convention is honored.
- Whether `tools/gen_kpk.py` lives at top-level `tools/` or under `src/chess_engine/engine/v7/tools/` (Phase 1 placed `gen_coeffs.py` under the latter — mirror).
- Exact triangular PV array dimensions (`MAX_PLY` value) so long as it covers all reachable plies.
- Whether singular extensions / multi-cut / ProbCut share verification helpers or each has its own.

### Deferred Ideas (OUT OF SCOPE)

- Multi-slot TT buckets (4-way cluster) — deferred to Phase 4.
- Bucket-of-N replacement policy / `TTReplacementPolicy` UCI option — deferred.
- Widened TT entry fields (static-eval cache, generation 8b) — deferred.
- One-plan-per-refinement gauntlet rigor — rejected in favor of tiered approach (D-04/D-05).
- Per-tier full SPRT (instead of mini-gauntlet) — rejected.
- Opening book at play time — V2-STR-04.
- MultiPV mode — V2-UX-04.
- Eval breakdown / diagnostics UI — V2-UX-02/03.
- Conservative-only fortress (locked pawn chains only) — rejected in favor of D-11 full framework default-OFF.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PAR-01 | Lockless TT (Hyatt-Mann XOR, two `std::atomic<uint64_t>` slots, `memory_order_relaxed`) | D1 section: full xkey/data encoding spec + memory-order rationale |
| PAR-02 | TT entry packs move + score + depth + bound + age into 64 bits | D1 section: bit layout mirrors V6 verbatim per D-09 (verified by reading `v6/include/tt.hpp` lines 20-31) |
| PAR-03 | TSan stress test (16 threads × 60s) passes on Linux/macOS/WSL | D1 section: harness spec (RNG seed, probe/store mix, exit-code contract) |
| SRCH-03 | Adaptive null-move pruning + zugzwang guard | D2 §3.1: R = 3 + depth/4 + min((eval-beta)/200, 3); skip if `non_pawn_material(side_to_move) == 0` |
| SRCH-04 | LMR with context (PV node / cut node / improving / in-check exclusions; re-search at depth-1) | D2 §3.2: log-table base + context adjustments; verified re-search protocol |
| SRCH-05 | LMP + RFP + Futility with tuned margins | D2 §3.3: margin tables, depth-gated conditions |
| SRCH-06 | Move ordering: killers + history + counter-move + SEE-bucketed captures | D2 §3.4: scoring brackets and counter-move table layout |
| SRCH-07 | Continuation + capture history (stretch in Phase 3) | D2 §3.5: 4-ply continuation table dims, capture history indexing |
| SRCH-08 | Singular extensions (depth ≥ 8, verification re-search) | D2 §3.6 + Pitfall 5: search-explosion NPS check |
| SRCH-09 | Multi-cut at cut nodes (depth ≥ 8) | D2 §3.7: M=6 moves, C=3 cuts, R=depth/2 |
| SRCH-10 | ProbCut (gauntlet-gated; may revert to OFF) | D2 §3.8: depth ≥ 5, margin, verification |
| SRCH-11 | IIR / IID when no TT move found | D2 §3.9: IIR reduce-by-1 at PV/cut nodes when `tt_move == MOVE_NONE && depth ≥ 4` |
| SRCH-12 | Check + recapture extensions | D2 §3.10: extension already present for check (search.cpp:182-184); recapture is +1 when capture-on-same-square |
| ENDG-01 | KPK bitbase (all 163,328 legal positions) | D3 §4.1: codegen, packed `uint32_t[5104]`, symmetry-folded |
| ENDG-02 | Opposition eval for K vs K+P | D3 §4.2: opposition table + direct opposition detection |
| ENDG-03 | Wrong-bishop + rook-pawn draw (king-distance check) | D3 §4.3: file/color-of-promotion-square detection |
| ENDG-04 | Continuous (Stockfish-style 0–256) phase blend | D3 §4.4: monotonicity check + formula |
| ENDG-05 | Conservative fortress hints (default-OFF per D-11) | D3 §4.5: pattern set + validation gauntlet |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **C++17 + pybind11 only.** No new language additions. V7 mirrors V6 build pattern (CMake `FetchContent` of pybind11 v2.12.0).
- **NPS within ~20% of V6.** Enforced by Phase 2 NPS sentinel (`tests/test_nps_regression.py`). Phase 3 must not break this.
- **V1–V6 untouched.** V6 source is reference only — no shared code, no imports across version folders.
- **Lazy SMP only for parallelism.** No new threading abstraction in FastAPI layer.
- **Cooperative cancellation via `SearchInfo`.** Already wired (`external_stop` pointer in `v7/include/search.hpp`).
- **No bare `except:` blocks** in new Python codegen scripts (CLAUDE.md conventions).
- **No `print()` for new code** — but existing V7 search uses `std::cout` for `info` lines, which is the UCI-required surface and stays.
- **GSD workflow enforcement:** All work goes through `/gsd-execute-phase`. Do not edit outside it.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Lockless TT data structure | C++ engine (D1) | — | Pure in-engine concurrency primitive; no Python / UCI / pybind11 surface change |
| TSan stress harness | Build tooling (`scripts/`) | C++ standalone binary | Lives outside the pybind11 module — separate CMake target so TSan flags don't poison the main build |
| Search refinements (LMR/NMP/etc.) | C++ engine `search.cpp` | UCI surface (toggles per D-06) | UCI options forward through `v7_uci` (Phase 2 Plan 02-01 parser) — do NOT plumb through Python `Engine` API |
| Move-ordering state (killers/history/counter) | C++ `Engine` member or per-ply `SearchStack` | — | Per-thread in Phase 4; in Phase 3 single-threaded, lives on `Engine` mirroring V6 |
| KPK bitbase data | Build-time codegen (`tools/gen_kpk.py`) | C++ `endgame.cpp` runtime probe | Generation is offline Python; runtime is O(1) C++ bit lookup; matches `gen_coeffs.py` pattern |
| Endgame eval terms | C++ `endgame.cpp` (new) | `coeffs.json` + codegen | Coefficients flow through Phase-1 codegen (D-12); C++ code reads `v7::coeffs::*` externs |
| Fortress detection | C++ `endgame.cpp` behind UCI toggle | Validation gauntlet | Default OFF — pattern of "implement but don't enable" so SPRT isn't contaminated |

## Standard Stack

### Core (already in repo — verified by `ls src/chess_engine/engine/v7/`)

| Component | Source | Purpose | Why Standard |
|-----------|--------|---------|--------------|
| C++17 + pybind11 v2.12.0 | `src/chess_engine/engine/v7/CMakeLists.txt` | Native engine + Python binding | Mirrors V6; FOUND-01/02 |
| `<atomic>` (libstdc++/libc++/MSVC STL) | `<atomic>` | Lockless TT primitive | Standard C++17; no Boost.Atomic needed |
| `std::aligned_alloc` / `_aligned_malloc` | tt.cpp existing pattern | 64-byte cache-line aligned TT slab | Already used in V6/V7 TT — extend, don't replace |
| `fastchess` (Phase 2 vendored) | `tools/` | Gauntlet runner | Already integrated by Phase 2 Plan 02-03 |
| `Fathom` (jdart1) | `src/chess_engine/engine/v7/extern/fathom/` (Plan 01-05) | KPK ground-truth oracle for `gen_kpk.py` acceptance test | Phase 1 already vendored; reuse `tb_probe_wdl` for KPK validation per D-10 |

### Supporting

| Component | Purpose | When to Use |
|-----------|---------|-------------|
| `python_chess` (pytest tests already use it) | KPK position enumeration in `gen_kpk.py` | Generator script — Python-side legality check + Zobrist hashing |
| `numpy` (existing dep) | Packing the 163,328-position table efficiently in the generator | Use `np.packbits` or manual bit-pack to emit ~20.4KB `uint8_t[]` in the .cpp |
| pytest with `RUN_BENCHMARKS=1` gate | NPS sentinels (existing pattern from Phase 2 Plan 02-05) | New Phase 3 sentinels (singular on/off NPS ratio) follow this gate |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hyatt-Mann XOR (D-07) | Per-bucket spinlock | Spinlocks add 30-50ns per probe and hurt NPS; XOR trick is industry standard (Stockfish, Ethereal, Berserk all use it). **Already locked by D-07.** |
| Single-slot bucket (D-07) | 4-way cluster (Stockfish-style) | 4-way reduces collisions but doubles probe cost. **Locked single-slot per D-07; defer to Phase 4 if SMP measurements demand.** |
| KPK build-time codegen (D-10) | Runtime BFS in C++ at engine startup | Runtime BFS adds 100-500ms to every Engine() construction. **Locked codegen per D-10.** |
| KPK build-time codegen (D-10) | Pre-baked .bin checked into repo | Binary blobs are anti-pattern for source review; codegen is text-diffable. **Locked codegen.** |
| Stockfish-style 0-256 phase (D-04 ENDG-04) | V6's `phase / 24` 0-24 integer scale | 0-256 gives smoother blend (no integer-truncation cliffs). V7 current eval at `eval.cpp:424` uses 0-24 — Plan 03-04 widens to 0-256. |

**Installation:** No new package installs. Everything is already in `pyproject.toml` extras (`build` group has `pybind11`; `dev` has `pytest`).

**Version verification:** Skipped — Phase 3 adds no new external deps per CLAUDE.md constraint and per CONTEXT.md decisions.

## Architecture Patterns

### System Architecture Diagram

```
                  ┌─────────────────────┐
                  │ Python: Engine()    │ (v7/__init__.py)
                  └────────┬────────────┘
                           │ search(fen, depth, time_ms)
                           ▼
            ┌──────────────────────────────────┐
            │ C++ Engine::search (engine.cpp)  │  ← Plan 03-01 fixes info.depth bug
            │  - reset stop_flag_              │
            │  - board_.from_fen               │
            │  - rep_stack_.push(root_hash)    │
            │  - TimeManager::allocate         │
            │  - tt_.new_search()              │
            └────────┬─────────────────────────┘
                     │
                     ▼
            ┌──────────────────────────────────┐
            │ iterative_deepening (search.cpp) │
            │  - aspiration window loop        │
            │  - per-depth alpha_beta call     │
            │  - soft-deadline ID gate         │
            └────────┬─────────────────────────┘
                     │
                     ▼
            ┌────────────────────────────────────────┐
            │ alpha_beta (search.cpp) — REFINEMENTS  │
            │  ┌─────────────────────────────────┐   │
            │  │ Plan 03-02 (tier 1, default ON) │   │
            │  │  - IIR (depth-1 if no TT move)  │◄──┼── SRCH-11
            │  │  - RFP                          │◄──┼── SRCH-05
            │  │  - Adaptive null-move + ZW guard│◄──┼── SRCH-03
            │  │  - LMP (depth ≤ 8, late moves)  │◄──┼── SRCH-05
            │  │  - Move-pick: TT/SEE/killer/    │   │
            │  │    history/counter              │◄──┼── SRCH-06
            │  │  - LMR with context             │◄──┼── SRCH-04
            │  │  - Futility (frontier nodes)    │◄──┼── SRCH-05
            │  │  - Check/recapture extensions   │◄──┼── SRCH-12
            │  └─────────────────────────────────┘   │
            │  ┌─────────────────────────────────┐   │
            │  │ Plan 03-03 (tier 2, aggressive) │   │
            │  │  - Continuation/capture history │◄──┼── SRCH-07
            │  │  - Singular extensions (d≥8)    │◄──┼── SRCH-08
            │  │  - Multi-cut (d≥8)              │◄──┼── SRCH-09
            │  │  - ProbCut (d≥5, gauntlet-gated)│◄──┼── SRCH-10
            │  └─────────────────────────────────┘   │
            └────────┬───────────────────────┬───────┘
                     │ probe / store         │ evaluate()
                     ▼                       ▼
        ┌────────────────────────┐  ┌──────────────────────────┐
        │ Lockless TT (Plan 03-05)│  │ evaluate (eval.cpp)      │
        │ tt.cpp / tt.hpp         │  │  + endgame() (NEW)       │
        │  - xkey = key ^ data    │  │  ┌─────────────────────┐ │
        │  - probe: load xkey,    │  │  │ Plan 03-04 endgame  │ │
        │    load data, check     │  │  │  - KPK lookup       │ │
        │    (xkey^data == key)   │  │  │  - opposition       │ │
        │  - store: pack data,    │  │  │  - wrong-bishop+RP  │ │
        │    xkey = key^data,     │  │  │  - 0-256 phase blend│ │
        │    relaxed atomic stores│  │  │  - fortress (OFF)   │ │
        └────────────────────────┘  │  └─────────────────────┘ │
                                    └──────────────────────────┘
```

Reader trace: a Python `engine.search(fen, depth=10, time_ms=5000)` call flows through `Engine::search` → `iterative_deepening` → `alpha_beta` (recursive), which probes the lockless TT, calls `evaluate()` (which may delegate to `endgame()`), and stores back into the TT. The UCI surface (`v7_uci` binary) takes the same `Engine::search` path with options toggling the `Use<Refinement>` flags.

### Recommended Project Structure

```
src/chess_engine/engine/v7/
├── include/
│   ├── tt.hpp              # MODIFIED (Plan 03-05): atomic xkey/data slots, packed data field
│   ├── search.hpp          # MODIFIED (Plan 03-01): SearchStack, UCI toggle flags, MAX_PLY
│   ├── search/             # NEW (optional split — Claude's discretion per CONTEXT)
│   │   ├── move_picker.hpp # Staged move generator (TT → captures(SEE) → killers → quiets)
│   │   └── history.hpp     # killers/history/counter/continuation tables
│   ├── endgame.hpp         # NEW (Plan 03-04): KPK probe, opposition, wrong-bishop, phase blend
│   └── engine.hpp          # MODIFIED (Plan 03-01): add killers_, history_, search_stack_ members
├── src/
│   ├── tt.cpp              # REPLACED (Plan 03-05): Hyatt-Mann XOR encoding
│   ├── search.cpp          # HEAVILY MODIFIED (03-01, 03-02, 03-03)
│   ├── search/             # NEW (optional)
│   │   ├── move_picker.cpp
│   │   └── history.cpp
│   ├── endgame.cpp         # NEW (Plan 03-04)
│   ├── eval.cpp            # MODIFIED (Plan 03-04): 0-256 phase blend, endgame() hookup
│   ├── kpk_bitbase.cpp     # NEW, GITIGNORED (emitted by tools/gen_kpk.py)
│   └── engine.cpp          # MODIFIED (Plan 03-01): wire SearchStack, fix info.depth contract
└── tools/
    ├── gen_coeffs.py       # EXISTS (Phase 1)
    └── gen_kpk.py          # NEW (Plan 03-04): emits kpk_bitbase.cpp

scripts/
└── tt_tsan_stress.sh       # NEW (Plan 03-05): TSan harness driver
```

### Pattern 1: Hyatt-Mann XOR Lockless TT

**What:** Encode the entry as two 64-bit words: `xkey = key XOR data` and `data` (packed move+score+depth+flag+age). A reader loads both relaxed, computes `xkey XOR data`, and accepts the entry **iff** the result equals the Zobrist key. A torn write (one word from old, other from new) produces a key mismatch and is silently treated as a miss.

**When to use:** Multi-threaded TT access where lock-free correctness matters but exact entry consistency does not (TT misses are recoverable; corrupt move data returned to search is not).

**Example (verified pattern, not copied code — write from scratch per D-09):**

```cpp
// Source: ASSUMED canonical Hyatt-Mann pattern (Stockfish tt.h, Crafty origin).
// NOT verified against current Stockfish source — write V7's own implementation.

struct AtomicEntry {
    std::atomic<uint64_t> xkey;   // key XOR data
    std::atomic<uint64_t> data;   // packed: move|score|depth|flag|age
};

// Bit layout (mirror V6's verbatim per D-09):
//   bits  0..15 : Move      (uint16_t)
//   bits 16..31 : score     (int16_t — cast to uint16_t for packing)
//   bits 32..39 : depth     (int8_t  — cast to uint8_t for packing)
//   bits 40..47 : flag      (uint8_t, low 2 bits used)
//   bits 48..55 : age       (uint8_t)
//   bits 56..63 : padding   (matches V6's struct tail; keep 0)
// NOTE: V6's struct has separate fields (key, best_move, score, depth, flag,
//   age). V7 packs them into one uint64_t. Verify layout sizes match (V6's
//   struct TTEntry is 16 bytes incl. key; V7's atomic version is also 16
//   bytes: xkey (8) + data (8) — identical footprint).

inline uint64_t pack(Move m, int16_t score, int8_t depth, uint8_t flag, uint8_t age) {
    return  uint64_t(uint16_t(m))
         | (uint64_t(uint16_t(score)) << 16)
         | (uint64_t(uint8_t(depth))  << 32)
         | (uint64_t(flag & 0x3)      << 40)
         | (uint64_t(age)             << 48);
}

bool probe(uint64_t key, TTEntry& out) const {
    const AtomicEntry& e = entries[index(key)];
    uint64_t d  = e.data.load(std::memory_order_relaxed);
    uint64_t xk = e.xkey.load(std::memory_order_relaxed);
    if ((xk ^ d) != key) return false;          // torn or miss
    out = unpack(d);
    return out.flag != TT_NONE;
}

void store(uint64_t key, Move m, int score, int depth, TTFlag flag) {
    AtomicEntry& e = entries[index(key)];
    // Age-then-depth replacement: read current data, decide, then write.
    // Race-safe: worst case is two threads both decide-to-replace simultaneously;
    // the survivor's xkey^data still satisfies the probe invariant.
    uint64_t cur_data = e.data.load(std::memory_order_relaxed);
    uint64_t cur_xkey = e.xkey.load(std::memory_order_relaxed);
    uint64_t cur_key  = cur_xkey ^ cur_data;
    TTEntry  cur      = unpack(cur_data);
    bool replace = (cur_key == key) ||
                   (cur.age != generation) ||
                   (cur.depth <= depth);
    if (!replace) return;
    uint64_t new_data = pack(m, int16_t(score), int8_t(depth), uint8_t(flag), generation);
    e.data.store(new_data,         std::memory_order_relaxed);
    e.xkey.store(key ^ new_data,   std::memory_order_relaxed);
}
```

**Memory order:** `memory_order_relaxed` is correct for both loads and stores. The xkey-vs-data validation IS the synchronization. No acquire/release needed because we don't depend on side effects in other memory. PAR-01 says relaxed explicitly. `[ASSUMED — canonical Stockfish pattern; verify against current Stockfish tt.h before final implementation]`

**Store order matters:** Store `data` first, then `xkey`. A concurrent reader who loads `data` first and `xkey` second sees one of: (old xkey, old data) → consistent; (old xkey, new data) → mismatch → miss; (new xkey, new data) → consistent. The reverse order (xkey then data) allows (new xkey, old data) → mismatch → miss, which is also safe, but the convention is data-then-xkey to match "the xkey is the commit." `[ASSUMED]`

### Pattern 2: Triangular PV Array (replaces `std::vector<Move>`)

**What:** A fixed-size 2D array indexed by `[ply][offset]` plus a `pv_length[ply]` parallel array. Each ply copies its child's PV into its own slot, prepending the chosen move. Zero allocations per call.

**When to use:** Replace the `std::vector<Move>& pv` parameter throughout `alpha_beta` and `iterative_deepening` (Bug #3 from `project_phase1_known_perf_bugs.md`).

**Example (canonical pattern):**

```cpp
// Source: ASSUMED canonical pattern (Stockfish, Ethereal, Berserk).
constexpr int MAX_PLY = 128;  // covers practical game length + search depth

struct SearchStack {
    Move pv[MAX_PLY][MAX_PLY];   // triangular table; [ply][i] valid for i < pv_length[ply]
    int  pv_length[MAX_PLY];
    Move killers[MAX_PLY][2];    // 2 killers per ply (slot 0 = most recent)
    // ... other per-ply state (static_eval cache, move_count, etc.)
};

// In alpha_beta(ply):
ss.pv_length[ply] = ply;  // empty PV at this ply
// On finding a new best move at this ply:
ss.pv[ply][ply] = best_move;
for (int i = ply + 1; i < ss.pv_length[ply + 1]; ++i)
    ss.pv[ply][i] = ss.pv[ply + 1][i];
ss.pv_length[ply] = ss.pv_length[ply + 1];
```

**Gotcha:** `MAX_PLY = 64` is the smallest value that fits "deepest realistic search"; `MAX_PLY = 128` gives headroom for extensions (singular + check + recapture can stack 3-4 ply per node). Recommend `MAX_PLY = 128` per CONTEXT D-03's "covers all reachable plies." `[ASSUMED]`

### Pattern 3: Persistent Killers / History on Engine

**What:** Move `killers[][2]` and `history[][]` from per-call stack storage to `Engine` member state. Resets on `new_game()`, decays on `new_search()`.

**Why:** Bug #2 from memory: current V7 search.cpp:270-271 stack-allocates these every call, defeating the heuristic entirely. CONTEXT D-03 makes this Plan 03-01's first job.

**Layout:**

```cpp
// In Engine class (engine.hpp):
class Engine {
    // ...
    SearchStack search_stack_;       // owns pv/pv_length/killers per-ply
    int history_[2][64][64] = {};    // history[side][from][to]
    Move counter_moves_[2][64][64] = {};  // counter_moves[side][prev_from][prev_to]
};
```

**History aging:** On `new_search()`, divide all entries by 2 (or by 4 for stronger decay). Prevents stale dominance across moves. `[ASSUMED — canonical pattern]`

### Anti-Patterns to Avoid

- **`std::vector<Move> pv` parameters anywhere in the search:** Bug #3 — allocator-bound at ~3k NPS. The triangular PV array MUST replace every occurrence.
- **Per-call stack-allocated killers/history:** Bug #2 — `std::array<Move, 64> killers = {};` at search.cpp:270 means killers never accumulate. Killers must live in `SearchStack` per-ply.
- **`info.depth = depth` inside iterative_deepening clobbers caller's max:** Bug #1 — `Engine::search` writes `info.depth = max_depth` (intended as upper bound), then `iterative_deepening` overwrites at every iteration (`info.depth = depth` at search.cpp:398). Use a separate `info.max_depth` field; `info.depth` is purely the current-iteration counter.
- **Trusting "// V6 parity" comments:** Per CONTEXT specifics: "// V6 parity" comments in V7 search are NOT trustworthy as written (that's how the Phase 1 perf bugs slipped through). Verify against V6 source directly for every claim Plan 03-01 carries forward.
- **Storing mate scores in TT without ply correction:** Already handled by `score_to_tt` / `score_from_tt` (SRCH-13, search.hpp:213-223). New TT path (Plan 03-05) must keep these wrappers — they are NOT inherent to the TT, they are inherent to the SEARCH side. Don't move them into TT methods.
- **Hand-rolling a phase calculator instead of a tunable coeff:** Per D-12, phase blend constants go in `coeffs.json`. Don't add `constexpr` phase weights to `endgame.cpp`.
- **Skipping zugzwang guard in null-move:** Pitfall — null-move in pawn-only endgames blunders into lost positions. Required check: `non_pawn_material(side_to_move) > 0` before allowing null move.
- **Replacing TT entry unconditionally:** Bug — destroys depth-N work for depth-1 quiescence stores. Replacement policy MUST consult age and depth (CONTEXT D-07).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| KPK position classification | Hand-written rules (king-vs-king + pawn special cases) | Build-time BFS in `gen_kpk.py` validated against Fathom (D-10) | All 163,328 positions; even strong engines have historically had bugs in hand-rolled KPK |
| Zobrist hashing for KPK generator | New Zobrist tables in Python | Reuse the C++ Zobrist via pybind11 OR use `python_chess.Board.transposition_key()` | Avoids a second source of hash truth |
| Bit-packing arithmetic for KPK table | Manual `bytearray` shifts | `numpy.packbits` over a boolean array | Vectorized, well-tested, easier to inspect |
| Phase-blend smoothing | Linear interpolation by hand | Stockfish 0-256 formula: `phase = ((npm - EG_LIMIT) * 256) / (MG_LIMIT - EG_LIMIT)`, clamped | Canonical, monotonic, no integer-truncation cliffs |
| SEE (Static Exchange Evaluator) | New implementation | The `see(board, m)` function already exists in V7 (search.cpp:104, used in qsearch) | Already inherits from V6; reuse |
| TT bit layout | New design from scratch | Mirror V6's `tt.hpp:20-31` verbatim per D-09 | Pre-decided; one less variable in gauntlet bisection |
| Lockless TT primitives | Spinlocks / mutex per bucket | Hyatt-Mann XOR (D-07) — two `std::atomic<uint64_t>` per slot, relaxed memory order | Industry standard; spinlocks add ~30-50ns per probe and tank NPS |
| Counter-move tables | "Last move played" search-info field | Dedicated `counter_moves[side][prev_from][prev_to] = Move` table | Stored history is the heuristic — needs persistence across calls |
| Singular-extension verification | New search entry point | Re-enter `alpha_beta` with reduced depth and exclusion window — `excluded_move` field in SearchStack | Standard pattern; avoid forking the search function |

**Key insight:** Every domain in this phase has been done correctly by 50+ open-source engines. The strength gain comes from getting the off-by-ones right, not from novel algorithms. The CONTEXT explicitly says "do not copy Stockfish code" — but the reference implementations are valid for verifying the formula and the boundary conditions.

## Runtime State Inventory

This phase modifies search algorithms and adds new evaluation terms. There is no migration / rename / refactor of stored data. The standard rename inventory is mostly N/A.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — V7 has no persistent stores between runs other than the in-memory TT (cleared per `new_game`). | None |
| Live service config | None — engine is in-process; no external services. | None |
| OS-registered state | None. | None |
| Secrets/env vars | `RUN_BENCHMARKS=1` already used by Phase 2 NPS sentinel. Phase 3 adds NPS sentinels (singular on/off ratio) that reuse the same gate — no new env vars. | Reuse existing |
| Build artifacts | `src/chess_engine/engine/v7/build/` — must be rebuilt after `tt.cpp` / `search.cpp` / new `endgame.cpp` changes. **NEW:** `src/chess_engine/engine/v7/src/kpk_bitbase.cpp` is generated and gitignored (per D-10). Plan must add it to `.gitignore` mirroring the existing `coeffs.cpp` rule. | (a) Document rebuild requirement in plan acceptance; (b) verify `.gitignore` entry added |

**Verified by:** Direct `grep` of `.gitignore` for existing `coeffs.cpp` rule pattern (matches the D-10 convention) and inspection of `v7/src/` showing no persistent state files.

## Common Pitfalls

### Pitfall 1: Building Lazy SMP on a non-lockless TT (PITFALLS #36) — D1 ORDERING GATE

**What goes wrong:** Phase 4's E1 (Lazy SMP) shipped before D1's TSan-verified lockless TT silently corrupts entries — torn writes return phantom moves that fail legality checks (best case) or return illegal moves to the UCI surface (worst case).

**Why it happens:** V6's TT is single-threaded by assumption (no atomics on the data fields). Multi-thread access to it without the XOR encoding produces visibly correct hit-rates but wrong move data on a fraction of probes.

**How to avoid:** D1 (Plan 03-05) MUST complete with TSan green BEFORE Phase 4 E1 starts. CONTEXT D-08 makes this a blocking human checkpoint at end of Phase 3. **Planner must explicitly assert this in the Phase 3 acceptance criteria.**

**Warning signs:** Mid-search illegal-move assertions; flaky gauntlet results that move with thread count; "engine returned bestmove that is not in the legal move list" in fastchess logs.

### Pitfall 2: Singular Extensions Search Explosion (PITFALLS #5)

**What goes wrong:** Singular extensions can multiply the tree size 2-5× if the singular test fires too often, blowing the NPS budget and net-negating Elo despite "looking right."

**Why it happens:** The singular search is itself a recursive `alpha_beta` call at `depth/2 - 1` with a narrow `(s - margin, s - margin + 1)` window — if `margin` is too small or `depth_gate` is too low, every PV node triggers it and the tree explodes.

**How to avoid:**
- Gate at `depth >= 8` (CONTEXT D-04 SRCH-08).
- Require `tt_entry.depth >= depth - 3` AND `tt_entry.flag == TT_BETA` (only test moves the TT believes are good).
- Use a margin of `singular_margin = 2 * depth` (canonical Stockfish).
- **Mandatory test:** Build pytest sentinel `tests/test_v7_singular_nps_ratio.py` gated by `RUN_BENCHMARKS=1` that runs the bench position twice (UseSingular=true then false) and asserts the NPS ratio stays in [0.9, 1.1]. This is Success Criterion #4. Use the same NPS-reading pattern as Phase 2 Plan 02-05's `_assert_nps_ratio`.

**Warning signs:** Mid-tier gauntlet shows depth-at-fixed-time regression; `info` output shows seldepth jumping > 20 plies above nominal depth.

### Pitfall 3: LMR Off-by-One in Re-Search

**What goes wrong:** After a reduced search returns `score > alpha`, the re-search depth is wrong (either `depth - 1` or `depth - reduction - 1`), silently losing strength.

**Why it happens:** Two conventions co-exist: (a) full-window re-search at `depth - 1` (canonical Stockfish), (b) zero-window re-search at full depth then PV re-search. Mixing them is the off-by-one.

**How to avoid:** Canonical pattern (per Ethereal/Berserk/SF):
```
// Reduced zero-window:
score = -ab(depth - 1 - R, -alpha-1, -alpha);
if (score > alpha && R > 0) {
    // Zero-window re-search at FULL depth:
    score = -ab(depth - 1, -alpha-1, -alpha);
}
if (score > alpha && score < beta) {
    // Full-window re-search at FULL depth (PV):
    score = -ab(depth - 1, -beta, -alpha);
}
```
Current V7 search.cpp:324-332 has only ONE re-search level — needs the two-level pattern above per SRCH-04. `[ASSUMED]`

**Warning signs:** Mini-gauntlet at Plan 03-02 merge shows depth-at-fixed-time regression vs Plan 03-01; LMR-on vs LMR-off depth comparison favors LMR-off (Success Criterion #4 would fail).

### Pitfall 4: Null-Move Zugzwang Detection

**What goes wrong:** Null-move in king-and-pawn endgames returns fail-high incorrectly — zugzwang positions have no good move, but null-move assumes a free pass is at least as good as the best legal move.

**Why it happens:** The null-move assumption "I'd rather play a real move than pass" breaks when every real move loses (zugzwang).

**How to avoid:**
```cpp
// Skip null move if side-to-move has only king + pawns (no major/minor pieces).
bool zugzwang_risk = (board.non_pawn_material(board.side_to_move) == 0);
if (do_null && !in_check && !zugzwang_risk && depth >= 3 && static_eval >= beta) { ... }
```
V7 currently has NO zugzwang guard (search.cpp:230). SRCH-03 adds this.

**Warning signs:** Engine plays a losing endgame move that quick perft rejects; bug presents as "engine bestmove allows immediate mate in K+P endgame."

### Pitfall 5: KPK Bitbase Encoding / Symmetry

**What goes wrong:** Generator produces 163,328 entries but the lookup function indexes wrong (e.g., forgets the side-to-move bit, mirrors black-to-move incorrectly, or fails to fold the symmetry).

**Why it happens:** KPK has 64*64*48*2 = 393,216 raw position tuples, but symmetry (white king on a-d files, pawn-mirroring) folds this to 163,328. The encoding scheme MUST match between generator and probe.

**How to avoid:**
- **Reference encoding (Stockfish-style):** index = `stm | (bksq << 1) | (wksq << 7) | (psq << 13)`, with the pawn-side WTM normalization that folds black-to-move into the same table by swapping piece colors.
- **Acceptance test (CONTEXT D-10):** Probe every one of the 163,328 enumerated positions through BOTH the new bitbase AND Fathom's `tb_probe_wdl` (KPK is 3-men, always in tablebase range). Require 100% agreement. Test lives in `tests/test_v7_kpk_bitbase.py`.

**Warning signs:** Endgame eval returns +VICTORY in known drawn positions or vice versa; pytest test_v7_kpk_bitbase fails at specific symmetry-edge positions (h-file pawn, kings adjacent).

### Pitfall 6: Stockfish Phase Blend Monotonicity

**What goes wrong:** Phase value oscillates (goes up after a piece capture) due to a sign error in the formula, causing eval to flip between MG and EG mid-game.

**Why it happens:** The formula `phase = ((npm - EG_LIMIT) * 256) / (MG_LIMIT - EG_LIMIT)` requires `npm` (non-pawn material) decreasing monotonically as pieces are captured. Forgetting to clamp at [0, 256] or using `MG - npm` instead of `npm - EG` flips the sign.

**How to avoid:**
- Canonical Stockfish formula (verify in test):
  ```cpp
  int npm = std::clamp(non_pawn_material(WHITE) + non_pawn_material(BLACK),
                       ENDGAME_LIMIT, MIDGAME_LIMIT);
  int phase = ((npm - ENDGAME_LIMIT) * 256) / (MIDGAME_LIMIT - ENDGAME_LIMIT);
  // phase = 256 at opening (full material), 0 at bare-king endgame
  int score = (mg * phase + eg * (256 - phase)) / 256;
  ```
- **Monotonicity test (CONTEXT Success Criterion #3):** `tests/test_v7_phase_blend.py` walks a starting position through serial captures and asserts `phase` is monotonically non-increasing at every step.

**Warning signs:** Eval suddenly becomes more "midgame" after a queen trade.

### Pitfall 7: Counter-Move Indexing by Wrong Side

**What goes wrong:** Counter-move table indexed by current side-to-move instead of the side that played the previous move. Result: counter never fires.

**Why it happens:** `counter_moves[side][prev_from][prev_to]` — `side` here is the side that PLAYED the previous move, not the side to move at the current node.

**How to avoid:** Document this explicitly in `counter_moves` declaration comment. Plan 03-02 task acceptance should include a unit test that plays move `e2-e4 → e7-e5` and asserts that after `e7-e5`, the counter-move probe `counter_moves[WHITE][e2][e4]` returns `e7-e5`.

### Pitfall 8: TT Probe Returns Stale Move That's Now Illegal

**What goes wrong:** Lockless TT returns a TTEntry whose `best_move` was legal at store time but is illegal at probe time (different position with same hash collision, or move encoding mismatch after a refactor).

**Why it happens:** Hyatt-Mann XOR catches torn writes BUT NOT hash collisions. Engine MUST validate the move is in the current position's legal move list before playing it.

**How to avoid:** When using a TT move for ordering, no validation needed (a bogus move just sorts wrong, no correctness impact). When returning a TT move as `bestmove` at root, MUST validate against the legal move list. V7 currently does this implicitly because the root entry is committed only after a full alpha_beta returns — but ensure Plan 03-05's new probe path preserves this invariant.

**Warning signs:** fastchess "illegal move" error mid-gauntlet; appears non-deterministically.

## Code Examples

### Adaptive Null-Move with Zugzwang Guard (SRCH-03)

```cpp
// Source: [ASSUMED] canonical Ethereal/Berserk pattern.
// Replaces V7 search.cpp:229-258 do-null block.

bool zugzwang_risk = (board.non_pawn_material(board.side_to_move) == 0);

if (UseNullMove && do_null && !in_check && !zugzwang_risk
    && depth >= NULL_MOVE_MIN_DEPTH && static_eval >= beta) {

    // Adaptive R: base 3 + depth/4 + min((eval - beta) / 200, 3)
    int R = 3 + depth / 4 + std::min((static_eval - beta) / 200, 3);

    Color us = board.side_to_move;
    board.side_to_move = Color(1 - us);
    board.hash ^= Zobrist::side_key;
    Square saved_ep = board.ep_square;
    if (board.ep_square != NO_SQUARE) {
        board.hash ^= Zobrist::ep_keys[board.ep_square];
        board.ep_square = NO_SQUARE;
    }

    int null_score = -alpha_beta(board, depth - R - 1,
                                 -beta, -beta + 1, info, ply + 1, ss, false);

    board.side_to_move = us;
    board.hash ^= Zobrist::side_key;
    if (saved_ep != NO_SQUARE) {
        board.ep_square = saved_ep;
        board.hash ^= Zobrist::ep_keys[saved_ep];
    }

    if (info.stopped) return 0;

    if (null_score >= beta) {
        // Verification at high depth to avoid zugzwang misclassification:
        if (depth >= 12) {
            int verify = alpha_beta(board, depth - R - 1, beta - 1, beta,
                                    info, ply, ss, false);
            if (verify >= beta) return beta;
            // else: fall through to normal search
        } else {
            return beta;
        }
    }
}
```

`board.non_pawn_material(side)` is a new helper Plan 03-02 must add to `board.hpp` / `board.cpp`. It counts `popcount(KNIGHT|BISHOP|ROOK|QUEEN of that side) * piece_value`. May reuse V6's helper if one exists — check `v6/include/board.hpp`. `[ASSUMED — verify V6 source]`

### Singular Extensions Verification (SRCH-08)

```cpp
// Source: [ASSUMED] canonical Stockfish singular-extension pattern.
// Inside the move loop, BEFORE making move `m`:

int extension = 0;
if (UseSingular && depth >= 8 && m == tt_move
    && tt_entry.depth >= depth - 3
    && tt_entry.flag == TT_BETA
    && std::abs(tt_entry.score) < MATE_IN_MAX_PLY
    && !is_root) {

    int singular_beta   = tt_entry.score - 2 * depth;
    int singular_depth  = (depth - 1) / 2;

    // Re-search EXCLUDING the TT move:
    ss.excluded_move[ply] = tt_move;
    int singular_score = alpha_beta(board, singular_depth,
                                     singular_beta - 1, singular_beta,
                                     info, ply, ss, false);
    ss.excluded_move[ply] = MOVE_NONE;

    if (singular_score < singular_beta) {
        extension = 1;          // Extend the TT move; it's "singularly best"
    } else if (singular_beta >= beta) {
        // Multi-cut: a non-TT move also failed high above beta
        return singular_beta;   // (multi-cut piggybacks here per SRCH-09)
    }
}
// Apply extension when computing child depth: `depth - 1 + extension`
```

The `excluded_move` field in SearchStack must be CONSULTED at the move loop's start (skip the move if it equals `excluded_move[ply]`). Critically: the TT probe at top of `alpha_beta` MUST be SKIPPED when `excluded_move[ply] != MOVE_NONE` — otherwise the cached score from the un-excluded search is returned and the singular test is meaningless. `[ASSUMED]`

### Staged Move Picker Skeleton (SRCH-06)

```cpp
// Source: [ASSUMED] canonical staged generator pattern.
// Returns moves in order: TT, good captures (SEE>=0), killers, counter, history-sorted quiets.
// Avoids generating quiets at all if a cutoff happens during captures.

enum Stage { S_TT, S_GEN_CAPTURES, S_GOOD_CAPTURES, S_KILLERS, S_COUNTER,
             S_GEN_QUIETS, S_QUIETS, S_BAD_CAPTURES, S_DONE };

class MovePicker {
    Stage stage_ = S_TT;
    Move tt_move_, killers_[2], counter_;
    MoveList captures_, quiets_, bad_captures_;
    int cap_idx_ = 0, quiet_idx_ = 0;
public:
    Move next(Board& b);  // returns MOVE_NONE at S_DONE
};
```

The good-captures bucket uses `see(board, m) >= 0` (SRCH-06 — `see` already exists in V7 search.cpp:104). Bad captures land last so they're tried only after quiets fail. `[ASSUMED]`

### KPK Generator Sketch (D-10)

```python
# tools/gen_kpk.py — source: [ASSUMED] canonical KPK BFS pattern.
# Mirrors src/chess_engine/engine/v7/tools/gen_coeffs.py for invocation style.
import chess, numpy as np, sys
from pathlib import Path

def index_pos(wksq: int, bksq: int, psq: int, stm: int) -> int:
    """Symmetry-fold: pawn always white, white-king on files a-d via mirror."""
    # ... canonical index formula here; total = 163,328
    ...

def classify_all() -> np.ndarray:
    """BFS from terminal positions; returns bool[163_328] (True = WIN for WTM stm)."""
    # ... iterative classification ...
    return result

def emit_cpp(table: np.ndarray, out: Path):
    packed = np.packbits(table)  # 163_328 / 8 = 20_416 bytes
    text = ", ".join(f"0x{b:02x}" for b in packed)
    out.write_text(
        "// AUTO-GENERATED by tools/gen_kpk.py — do not edit.\n"
        "// Mirrors gen_coeffs.cpp .gitignore pattern (D-10/D-12).\n"
        "#include <cstdint>\n"
        "namespace v7 {\n"
        f"const uint8_t KPK_BITBASE[{len(packed)}] = {{ {text} }};\n"
        "}\n"
    )

if __name__ == "__main__":
    table = classify_all()
    # Acceptance: probe each position through Fathom and assert agreement.
    # ...
    emit_cpp(table, Path(sys.argv[1]))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| V6's single-threaded TT (`stored.key == hash` plain load) | Hyatt-Mann lockless XOR with `std::atomic<uint64_t>` | Phase 3 D1 | Required for Phase 4 Lazy SMP correctness |
| V6's V7-as-stack `killers={}` per call | Persistent `Engine::search_stack_.killers[ply][2]` | Phase 3 Plan 03-01 | Move-ordering heuristic actually works; +Elo at no NPS cost |
| `std::vector<Move> pv` allocated per recursive call | Triangular `Move pv[MAX_PLY][MAX_PLY]` on SearchStack | Phase 3 Plan 03-01 | NPS recovers from ~3k to 200k+ (Phase 1 perf-bug fix) |
| V6's `NULL_MOVE_R = 4` constant | Adaptive R = 3 + depth/4 + min((eval-beta)/200, 3) | Phase 3 Plan 03-02 (SRCH-03) | +15-25 Elo per ablation studies in similar engines |
| V6's `LMR_REDUCTION_LIMIT = 3` plain | Context-aware LMR (PV/cut/improving/in-check modulation) | Phase 3 Plan 03-02 (SRCH-04) | +20-40 Elo |
| V6's TT move + MVV-LVA only | TT + SEE-bucketed + killers + counter + history | Phase 3 Plan 03-02 (SRCH-06) | +30-60 Elo |
| Hard phase threshold (0-24 integer scale in current V7 eval.cpp:424) | Stockfish-style 0-256 continuous blend | Phase 3 Plan 03-04 (ENDG-04) | Smoother eval transitions; +5-10 Elo |

**Deprecated/outdated:**

- V7's `extern TT g_tt;` global instance (tt.hpp:77): retained for legacy but Plan 03-05 should consider whether to delete it. CONTEXT D-09 inherits V6 layout but the global is just a free-function holdover. Engine class uses `Engine::tt_`; Plan 03-05 may safely drop `g_tt` if no caller is left. Verify with `grep -rn "g_tt\|::g_tt" src/chess_engine/engine/v7/` before deleting. Currently used at search.cpp:199, 366, 375, 492 — these all need to migrate to `info.tt` (a new SearchInfo field pointing at the Engine's tt_) when Plan 03-05 lands. **This is the main Plan 03-05 ↔ Plan 03-02/03-03 integration risk**.

## Assumptions Log

> Many algorithm formulas in this document come from training knowledge of canonical chess-engine patterns (Stockfish, Ethereal, Berserk). These are NOT verified against current upstream source in this session. Planner / implementer should consult one current open-source engine before final tuning constants.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Hyatt-Mann store order is data-then-xkey (the xkey is the commit) | Pattern 1 | Reader could see (new xkey, old data) → mismatch → miss (still safe, just suboptimal hit rate). LOW risk. |
| A2 | `memory_order_relaxed` is sufficient for both load and store | Pattern 1, Pitfall 1 | If wrong, torn writes go undetected → illegal moves to UCI. **HIGH risk — must verify with current Stockfish tt.cpp.** |
| A3 | MAX_PLY = 128 covers all reachable plies including extensions | Pattern 2 | Stack overflow / array OOB if extensions exceed it. MEDIUM risk — verify against current SF MAX_PLY (probably 246). |
| A4 | Counter-move table indexed by `[side_that_just_moved][prev_from][prev_to]` | Pitfall 7 | Indexing by wrong side means counter never fires. Heuristic silently does nothing. MEDIUM risk. |
| A5 | LMR two-level re-search (zero-window at full depth, then full-window) | Pitfall 3 | Wrong re-search depth = silent strength loss, possibly negating LMR entirely. **HIGH risk — verify against current Ethereal/Berserk.** |
| A6 | KPK encoding `index = stm \| (bksq << 1) \| (wksq << 7) \| (psq << 13)` with pawn-side normalization | Pitfall 5 | Wrong index → entire bitbase is unusable. Acceptance test (D-10) catches this — LOW risk in practice. |
| A7 | Stockfish phase formula `phase = ((npm - EG_LIMIT) * 256) / (MG_LIMIT - EG_LIMIT)` | Pitfall 6 | Monotonicity test catches the obvious sign error. LOW risk. |
| A8 | Singular extension margin = `2 * depth` and gate at `depth >= 8` with TT_BETA flag | Code Examples §SE | Wrong margin → Pitfall 2 search explosion. MEDIUM risk — verify against current SF singular.cpp. |
| A9 | `non_pawn_material(side)` helper exists in V6 board or is trivial to add | Code Examples §NMP | If not in V6, Plan 03-02 adds it — trivial. LOW risk. |
| A10 | V6's TT entry layout is the bit-packing per the V6 struct read (key, move, score, depth, flag, age = ~16 bytes incl. key) | Pattern 1 bit layout | V6's struct is non-packed in V6 (separate fields, no bit-packing). V7's atomic version packs them into one uint64_t. Sizes match (16 bytes total per slot). **LOW-MEDIUM risk — planner must verify exact field widths from V6 source before coding.** |
| A11 | History aging on `new_search()` divides by 2 | Pattern 3 | Wrong decay = stale history dominates new positions. LOW risk. |
| A12 | `g_tt` can be safely deleted in Plan 03-05 if all callers migrated to `Engine::tt_` | State of the Art | If a caller is missed, build fails loudly (good failure mode). LOW risk. |

**Recommendation:** Before Plan 03-05 (TT) or Plan 03-03 (singular/multi-cut/probcut) execution, the implementer should `git clone` or fetch current Stockfish/Ethereal source and verify A2, A5, A8 against the live implementation. The training-time formulas are very likely correct, but "very likely" is not the right bar for the Phase 4 hard-gate.

## Open Questions

1. **Should D1 (Plan 03-05 TT) run in parallel with D2 (Plans 03-02/03-03 search) or strictly sequentially?**
   - What we know: CONTEXT lists D1 as file-disjoint from D2/D3 (`tt.cpp` vs `search.cpp`).
   - What's unclear: D2 plans `#include "tt.hpp"` and use the probe/store API. CONTEXT D-09 says "TT entry packing inherits V6's 64-bit layout verbatim... No new fields." If Plan 03-05 preserves the public API (`probe(hash, entry) -> bool`, `store(hash, move, score, depth, flag)`), D2 plans never need to know about the lockless rewrite. **But** the `g_tt` global vs `Engine::tt_` member migration is a callsite change — search.cpp:199, 366, 375 will need to switch from `g_tt.probe/store` to a member access.
   - Recommendation: Planner should treat the `g_tt` → `Engine::tt_` migration as a pre-D1 mechanical change inside Plan 03-01 (the scaffold plan). After 03-01 merges, both 03-02/03-03 (calling `engine.tt_`) and 03-05 (rewriting `tt.cpp` internals) can proceed in parallel.

2. **Should `endgame.cpp` be a new file or a section appended to `eval.cpp`?**
   - What we know: CONTEXT D-04/D-12 don't specify; the existing `eval.cpp` is already 425+ lines.
   - Recommendation: Make it a new `endgame.cpp` + `endgame.hpp` — clean separation for the KPK probe + opposition + wrong-bishop + fortress block. `eval.cpp` calls `endgame_eval(board, mg_score, eg_score, phase)` as a final pass. Easier code review, no merge conflict with Plan 04 Texel work (TUNE-* modifies `coeffs.json` but not `eval.cpp` structure).

3. **What's the canonical baseline gauntlet directory naming?**
   - What we know: CONTEXT D-02 says `.planning/gauntlets/baseline/summary.json` "(or a clearly-named directory)."
   - Recommendation: Use `.planning/gauntlets/baseline-phase3/summary.json` so future phases can have their own baselines without naming collision. Phase 5 will want its own `baseline-ship/`. Document the chosen path in Plan 03-01's acceptance.

4. **Does the TSan stress harness need its own minimal CMake target or can it reuse the main one with conditional flags?**
   - What we know: CONTEXT D-08 says `scripts/tt_tsan_stress.sh` "(or equivalent CMake target)."
   - Recommendation: Separate `tt_tsan_stress` CMake executable target that links only tt.cpp + a minimal driver `tests/tt_tsan_main.cpp`. Avoids polluting the main `v7_engine.{pyd,so}` build with `-fsanitize=thread`. The harness driver spawns 16 std::threads, each doing 60s of `(rand_key, rand_data)` probe/store pairs, then exits 0 on no TSan reports.

5. **Should the per-refinement UCI toggles (D-06) default ON in the production build but OFF in the bench build (so NPS sentinel measures the cheapest path)?**
   - What we know: D-06 says "default ON" without distinguishing build types.
   - Recommendation: Always default ON, including in bench. The NPS sentinel's purpose is to detect regression — if the refinement stack adds 15% NPS overhead vs baseline, that's information we want surfaced, not suppressed. Singular-on vs singular-off sentinel (Success Criterion #4) runs the comparison explicitly via setoption commands.

6. **Where does the fortress UCI option live in the SPRT comparison?**
   - What we know: D-11 says fortress defaults OFF; separate ≥500-game gauntlet flips it ON.
   - Unclear: Does the Phase 3 ship-SPRT (D-05, ≥30 Elo vs baseline) run with `UseFortressEval=false`? Implied yes (fortress doesn't run by default), but worth pinning.
   - Recommendation: Plan 03-04 documents explicitly: ship-SPRT runs default UCI (fortress OFF). Fortress validation runs as a separate, scoped gauntlet AFTER ship-SPRT passes, regardless of outcome.

## Environment Availability

Phase 3 has no NEW external dependencies — all tools were vendored in Phases 1-2.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| C++17 compiler (clang/gcc/MSVC) | All Phase 3 plans | Build host only (Windows dev box has none per `.continue-here.md`) | — | Deferred to build host; mirrors Phase 1/2 pattern |
| CMake ≥ 3.15 | Build | Build host only | — | Deferred |
| `-fsanitize=thread` (TSan) | D1 stress test (D-08) | WSL/Linux/macOS only — TSan NOT available on MSVC | — | Run on WSL or build-host Linux (CONTEXT D-08 makes this an explicit deferred gate) |
| `fastchess` | Per-tier mini-gauntlets, ship-SPRT | Build host only | Vendored in Phase 2 Plan 02-03 | None — gauntlets defer to build host |
| Python 3.12 + `python_chess` | `tools/gen_kpk.py` | Build host only | — | Deferred |
| `numpy` | `tools/gen_kpk.py` packing | Already in pyproject.toml | per uv.lock | — |
| `Fathom` library | KPK acceptance test ground-truth (D-10) | Vendored Phase 1 Plan 01-05 | jdart1 fork | — |

**Missing dependencies with no fallback:** None — all gates are documented as build-host deferred per Phase 1/2 precedent.

**Missing dependencies with fallback:** TSan on Windows → run on WSL (CONTEXT D-08).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (declared `[dependency-groups].dev` in `pyproject.toml`) |
| Config file | None — uses pytest defaults; conftest.py at `tests/conftest.py` (Phase 1 + Phase 2 fixtures) |
| Quick run command | `python3 -m uv run --group dev pytest tests/test_v7_*.py -q -x` |
| Full suite command | `python3 -m uv run --group dev pytest -q` |
| Benchmark gate | `RUN_BENCHMARKS=1` environment variable (Phase 1 + Phase 2 pattern) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PAR-01 | Lockless TT compiles and stores/probes correctly single-threaded | unit | `pytest tests/test_v7_tt_lockless.py::test_probe_store_roundtrip -x` | ❌ Wave 0 |
| PAR-02 | TT entry packs/unpacks 64-bit data lossless | unit | `pytest tests/test_v7_tt_lockless.py::test_pack_unpack_invariant -x` | ❌ Wave 0 |
| PAR-03 | TSan stress harness runs 16t×60s with zero races | manual (build host) | `bash scripts/tt_tsan_stress.sh` (exit 0 = pass) | ❌ Wave 0 (script + CMake target) |
| SRCH-03 | Null-move skipped when `non_pawn_material(stm) == 0` | unit | `pytest tests/test_v7_search_refinements.py::test_null_move_skipped_in_kp_endgame -x` | ❌ Wave 0 |
| SRCH-04 | LMR-on engine searches deeper than LMR-off at fixed time | benchmark | `RUN_BENCHMARKS=1 pytest tests/test_v7_lmr_depth.py::test_lmr_depth_advantage -x` | ❌ Wave 0 |
| SRCH-05 | RFP / futility / LMP each prune correctly at gate-depth | unit | `pytest tests/test_v7_search_refinements.py::test_rfp_prunes_above_margin -x` | ❌ Wave 0 |
| SRCH-06 | Move picker yields TT → good captures → killers → counter → quiets → bad captures | unit | `pytest tests/test_v7_move_picker.py -x` | ❌ Wave 0 |
| SRCH-07 | Continuation/capture history accumulate and decay | unit | `pytest tests/test_v7_history.py -x` | ❌ Wave 0 |
| SRCH-08 | Singular-on vs singular-off NPS ratio within [0.9, 1.1] (Pitfall 5, Success Criterion #4) | benchmark | `RUN_BENCHMARKS=1 pytest tests/test_v7_singular_nps_ratio.py -x` | ❌ Wave 0 |
| SRCH-09 | Multi-cut returns beta only when ≥3 of first 6 moves fail high | unit | `pytest tests/test_v7_search_refinements.py::test_multicut_threshold -x` | ❌ Wave 0 |
| SRCH-10 | ProbCut gauntlet shows ≥0 Elo or option defaults to false | manual (build host) | Tier-2 mini-gauntlet (CONTEXT D-04) | ❌ Wave 0 (gauntlet config) |
| SRCH-11 | IIR reduces depth by 1 when `tt_move == MOVE_NONE && depth >= 4` at PV/cut nodes | unit | `pytest tests/test_v7_search_refinements.py::test_iir_reduces_no_tt_move -x` | ❌ Wave 0 |
| SRCH-12 | Recapture extension fires only when capture-on-same-square as previous | unit | `pytest tests/test_v7_search_refinements.py::test_recapture_extension -x` | ❌ Wave 0 |
| ENDG-01 | KPK bitbase agrees with Fathom on all 163,328 positions | unit (slow) | `pytest tests/test_v7_kpk_bitbase.py::test_all_positions_match_fathom -x` | ❌ Wave 0 |
| ENDG-02 | Opposition eval returns + for side with opposition in known position | unit | `pytest tests/test_v7_endgame.py::test_opposition_white_to_move -x` | ❌ Wave 0 |
| ENDG-03 | Wrong-bishop + rook-pawn returns DRAW_SCORE in canonical drawn position | unit | `pytest tests/test_v7_endgame.py::test_wrong_bishop_rook_pawn_draw -x` | ❌ Wave 0 |
| ENDG-04 | Phase value monotonically non-increasing across serial captures (Pitfall 6) | unit | `pytest tests/test_v7_phase_blend.py::test_monotonic -x` | ❌ Wave 0 |
| ENDG-05 | Fortress detection identifies canonical fortress positions (default-OFF — test verifies code path) | unit | `pytest tests/test_v7_endgame.py::test_fortress_detection -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python3 -m uv run --group dev pytest tests/test_v7_*.py -q -x` (excludes benchmark-gated, runs in < 60s)
- **Per wave merge:** Full suite — `python3 -m uv run --group dev pytest -q` + `RUN_BENCHMARKS=1 pytest tests/test_v7_singular_nps_ratio.py tests/test_v7_lmr_depth.py tests/test_v7_engine.py::test_nps_regression` (benchmarks)
- **Per tier merge (03-02 and 03-03):** Above PLUS the 200-game mini-gauntlet (D-05) — blocking human checkpoint on build host
- **Phase gate (end of Phase 3):** Full suite green + TSan stress green + 500-1000 game ship-SPRT showing ≥30 Elo vs `baseline-phase3/summary.json`

### Wave 0 Gaps

Phase 3 introduces a substantial new test surface. All of the following need to land before or during Phase 3:

- [ ] `tests/test_v7_tt_lockless.py` — covers PAR-01, PAR-02 (probe/store roundtrip, pack/unpack invariant, replacement policy)
- [ ] `tests/test_v7_search_refinements.py` — covers SRCH-03/05/09/11/12 (per-refinement boundary tests)
- [ ] `tests/test_v7_move_picker.py` — covers SRCH-06 (staged generation order)
- [ ] `tests/test_v7_history.py` — covers SRCH-07 (history/counter accumulation and aging)
- [ ] `tests/test_v7_lmr_depth.py` — covers SRCH-04 (benchmark-gated depth comparison)
- [ ] `tests/test_v7_singular_nps_ratio.py` — covers SRCH-08 Success Criterion #4 (benchmark-gated NPS ratio)
- [ ] `tests/test_v7_kpk_bitbase.py` — covers ENDG-01 (all-163,328 Fathom comparison; slow ~30s)
- [ ] `tests/test_v7_endgame.py` — covers ENDG-02/03/05 (canonical drawn/won/fortress positions)
- [ ] `tests/test_v7_phase_blend.py` — covers ENDG-04 (monotonicity)
- [ ] `scripts/tt_tsan_stress.sh` + `tests/tt_tsan_main.cpp` + CMake target — covers PAR-03
- [ ] No new fixtures needed in `tests/conftest.py` — Phase 1 and Phase 2 fixtures (`gauntlet_root`, `summary_json_factory`, `_find_uci_binary`, `latest_summary_dir`) cover all Phase 3 needs.

## Security Domain

Phase 3 is an in-engine algorithmic phase with no network surface, no user input, no persistence. ASVS-relevant attack surface is essentially zero. The only "security" concern is the UCI surface: `setoption name <X> value <Y>` parsing must reject malformed input without crashing. This is already handled by Phase 2 Plan 02-01's setoption parser; new toggles (D-06) plug into the existing parser and inherit its validation.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (UCI setoption surface) | Existing v7_uci parser (Phase 2 Plan 02-01) — new D-06 toggles inherit |
| V6 Cryptography | no | — |

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed `setoption` value (e.g., `value asdf` for a boolean) | Tampering | Existing parser rejects non-`true`/`false` for `check` type options — inherit |
| Buffer overflow in TT (large hash size) | DoS | `aligned_alloc` already bounds-checks via `bad_alloc` throw (tt.cpp:24-26); inherit |

## Sources

### Primary (HIGH confidence — directly verified this session)

- `src/chess_engine/engine/v7/include/tt.hpp` (verified by Read tool) — current V7 TT structure
- `src/chess_engine/engine/v7/src/tt.cpp` (verified by Read tool) — current V7 TT impl
- `src/chess_engine/engine/v7/include/search.hpp` (verified by Read tool) — current SearchInfo, LMR table, time manager
- `src/chess_engine/engine/v7/src/search.cpp` (verified by Read tool) — current alpha_beta, qsearch, ID; THIS file is where Plan 03-01 perf bugs live (lines 267-275 killers/history, 241/317/319/361 std::vector PV)
- `src/chess_engine/engine/v7/src/engine.cpp` (verified by Read tool) — current Engine::search; THIS file is where Plan 03-01 perf bug #1 lives (line 102-103 max_depth → info.depth contract)
- `src/chess_engine/engine/v7/include/engine.hpp` (verified by Read tool) — Engine class with rep_stack_, tt_, etc.
- `src/chess_engine/engine/v6/include/tt.hpp` (verified by Read tool) — V6 TT struct (8 bytes payload after the 8-byte key)
- `src/chess_engine/engine/v6/src/tt.cpp` (verified by Read tool) — V6 TT impl (age-then-depth replacement, modulo indexing, aligned alloc)
- `.planning/phases/03-lockless-tt-search-refinements-endgame/03-CONTEXT.md` (verified by Read) — all D-01..D-12 decisions cited verbatim in `<user_constraints>`
- `.planning/REQUIREMENTS.md` (verified by Read) — SRCH-03..12, ENDG-01..05, PAR-01..03 wording
- `.planning/ROADMAP.md` (verified by Read) — Phase 3 success criteria, D1 hard-gate before Phase 4 E1
- `memory/project_phase1_known_perf_bugs.md` (verified by Read at `~/.claude/projects/.../memory/`) — exact line numbers + descriptions of 3 perf bugs
- `.planning/phases/02-gauntlet-harness-early/02-05-SUMMARY.md` (verified by Read) — Phase 2 NPS sentinel + sanity probe fixtures available for reuse

### Secondary (MEDIUM confidence — pattern verified by Phase 1/Phase 2 precedent)

- `tools/gen_coeffs.py` pattern → `tools/gen_kpk.py` pattern (Phase 1 D-10 codegen invariants)
- `RUN_BENCHMARKS=1` gate pattern from `tests/test_v7_engine.py` → copy-verbatim for new singular NPS / LMR depth sentinels
- `tests/conftest.py` Phase 2 fixtures (gauntlet_root, summary_json_factory, latest_summary_dir, _find_uci_binary) → reusable as-is for Phase 3 gauntlet scaffolding tests

### Tertiary (LOW confidence — training knowledge only, flagged in Assumptions Log)

- Stockfish/Ethereal/Berserk canonical patterns for: Hyatt-Mann XOR exact store order (A1, A2), LMR re-search structure (A5), singular extension margins (A8), KPK bitbase encoding (A6), phase blend formula (A7), null-move adaptive R formula, counter-move indexing (A4), MAX_PLY value (A3). **Implementer should consult one current open-source engine before final tuning constants.**

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — entirely in-repo, no new deps, verified by direct file reads
- V6 → V7 TT layout (D-09): HIGH for sizes (verified V6 struct ~16 bytes); MEDIUM for exact field widths in V7's packed version (V6 struct doesn't bit-pack — V7 must pack into uint64_t; layout choice is V7's per A10)
- Architecture: HIGH — CONTEXT.md locks all major decisions, verified by direct read
- Pitfalls: MEDIUM-HIGH — Pitfalls 1, 2, 6 are explicitly named in CONTEXT/PITFALLS.md (HIGH); 3, 4, 5, 7, 8 are training-knowledge canonical patterns (MEDIUM)
- Algorithm formulas (LMR, NMP R, singular margin, KPK encoding, phase blend): MEDIUM — canonical Stockfish/Ethereal/Berserk patterns, NOT verified against current upstream source this session. See Assumptions Log A2/A5/A8.

**Research date:** 2026-05-17
**Valid until:** 2026-06-17 (30 days — Phase 3 algorithms are stable; canonical patterns rarely shift)
