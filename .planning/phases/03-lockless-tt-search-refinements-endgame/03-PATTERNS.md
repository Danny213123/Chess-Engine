# Phase 3: Lockless TT + Search Refinements + Endgame — Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 21 (5 modified C++, 3 new C++, 1 modified CMake, 1 new Python tool, 1 new shell script, 10 new test files)
**Analogs found:** 19 / 21 (2 NEW files — `tt_tsan_stress.cpp` driver and `run_tsan_stress.sh` — have no in-repo analog and are marked "NEW — no analog" with closest structural reference)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/chess_engine/engine/v7/src/tt.cpp` (REPLACED, Plan 03-05) | TT data structure (lockless) | pub-sub (atomic xkey/data) | `src/chess_engine/engine/v6/src/tt.cpp` (lines 14-79) | role-match — V6 is single-threaded analog; Hyatt-Mann XOR is a structural addition |
| `src/chess_engine/engine/v7/include/tt.hpp` (MODIFIED, Plan 03-05) | TT header (entry struct, class) | n/a | `src/chess_engine/engine/v6/include/tt.hpp` (lines 13-77) | role-match — bit-layout source of truth (D-09 verbatim) |
| `src/chess_engine/engine/v7/src/search.cpp` (HEAVILY MODIFIED, Plans 03-01/02/03) | search core (PVS + refinements) | request-response (recursive) | itself (current V7 search.cpp) + V6 search.cpp lines 160-280 | self-modification + V6 parity reference |
| `src/chess_engine/engine/v7/include/search.hpp` (MODIFIED, Plan 03-01) | search header (SearchStack, MAX_PLY, UCI toggles) | n/a | itself (current `RepStack` pattern lines 41-48) | self-extension |
| `src/chess_engine/engine/v7/src/engine.cpp` (MODIFIED, Plan 03-01) | Engine glue (search entry, new_game) | request-response | itself (current `Engine::search` lines 54-129) | self-modification |
| `src/chess_engine/engine/v7/include/engine.hpp` (MODIFIED, Plan 03-01) | Engine class header | n/a | itself (lines 71-81 — `rep_stack_` + `tt_` members) | self-extension |
| `src/chess_engine/engine/v7/src/endgame.cpp` (NEW, Plan 03-04) | endgame eval (KPK probe, opposition, fortress) | transform | `src/chess_engine/engine/v7/src/eval.cpp` (full file — namespacing + coeffs access pattern) | role-match — sister TU sharing eval.cpp's coeffs idiom |
| `src/chess_engine/engine/v7/include/endgame.hpp` (NEW, Plan 03-04) | endgame header | n/a | `src/chess_engine/engine/v7/include/eval.hpp` (sibling header structure) | role-match |
| `src/chess_engine/engine/v7/src/eval.cpp` (MODIFIED, Plan 03-04) | eval (phase blend → 0..256, endgame hookup) | transform | itself (lines 410-425 — current phase combine at `/ 24`) | self-modification |
| `src/chess_engine/engine/v7/src/kpk_bitbase.cpp` (NEW, GITIGNORED — emitted by Plan 03-04) | generated data table | n/a | `src/chess_engine/engine/v7/src/coeffs.cpp` (codegen output; gitignored at `.gitignore:74`) | exact codegen pattern |
| `src/chess_engine/engine/v7/tools/gen_kpk.py` (NEW, Plan 03-04) | build-time codegen (Python → C++) | file-I/O + transform | `src/chess_engine/engine/v7/tools/gen_coeffs.py` (full file) | exact — direct sibling |
| `src/chess_engine/engine/v7/CMakeLists.txt` (MODIFIED, Plan 03-04 + Plan 03-05) | build config (KPK custom command + TSan target) | n/a | itself (lines 43-70 coeffs `add_custom_command`; lines 105-130 `v7_uci` exe target) | self-extension |
| `src/chess_engine/engine/v7/tt_tsan_stress.cpp` (NEW, Plan 03-05) | standalone C++ harness (multi-thread TT stress) | event-driven (threads) | **NEW — no analog**; struct/API reference is V6 `TTEntry` + V7 new lockless `TT::probe/store` | none — novel |
| `scripts/tt_tsan_stress.sh` (NEW, Plan 03-05) | shell harness (TSan build + run + exit-code report) | request-response | **NEW — no analog**; closest is `cli/bin/chess-engine.js` argv-dispatch shape (different language) | none — novel |
| `.gitignore` (MODIFIED, Plan 03-04) | config (add `kpk_bitbase.cpp`) | n/a | `.gitignore:74` (existing `src/chess_engine/engine/v7/src/coeffs.cpp` rule) | exact |
| `tests/test_v7_tt_lockless.py` (NEW, Plan 03-05) | pytest unit (probe/store invariants) | request-response | `tests/test_v7_search.py` (V7 native fixture skeleton lines 22-71) | role-match |
| `tests/test_v7_search_refinements.py` (NEW, Plan 03-02/03) | pytest unit (per-refinement boundary tests) | request-response | `tests/test_v7_search.py` (full file — STARTPOS_FEN + native fixture) | exact |
| `tests/test_v7_move_picker.py` (NEW, Plan 03-02) | pytest unit (staged move-pick order) | request-response | `tests/test_v7_search.py` (same fixture pattern) | role-match |
| `tests/test_v7_history.py` (NEW, Plan 03-03) | pytest unit (history/counter aging) | request-response | `tests/test_v7_search.py` (same fixture pattern) | role-match |
| `tests/test_v7_singular_nps_ratio.py` (NEW, Plan 03-03) | benchmark sentinel (RUN_BENCHMARKS gate) | transform | `tests/test_v7_engine.py` lines 108-145 (`test_nps_sentinel`) + `tests/test_nps_regression.py::_assert_nps_ratio` | exact |
| `tests/test_v7_lmr_depth.py` (NEW, Plan 03-02) | benchmark sentinel (RUN_BENCHMARKS gate) | transform | `tests/test_v7_engine.py::test_nps_sentinel` (skipif decorator block) | exact |
| `tests/test_v7_kpk_bitbase.py` (NEW, Plan 03-04) | pytest unit (slow, all-163,328 positions) | transform | `tests/test_v7_eval.py` (codegen + gitignore + native module verification) lines 1-80 | role-match |
| `tests/test_v7_endgame.py` (NEW, Plan 03-04) | pytest unit (opposition, wrong-bishop, fortress) | request-response | `tests/test_v7_eval.py` (eval-result assertions) | role-match |
| `tests/test_v7_phase_blend.py` (NEW, Plan 03-04) | pytest unit (monotonicity) | transform | `tests/test_v7_eval.py` (native fixture + STARTPOS_FEN) | role-match |

> **NOTE — file list scope:** the orchestrator request listed `tests/v7/...` paths, but per the existing layout (verified by `tests/` directory listing) all V7 test files live at `tests/test_v7_*.py` (flat). The planner should use the existing flat path convention; the table above reflects that.

---

## Pattern Assignments

### `src/chess_engine/engine/v7/src/tt.cpp` (TT data structure, lockless) — Plan 03-05

**Analog:** `src/chess_engine/engine/v6/src/tt.cpp` (full file, 81 lines)
**D-09 contract:** mirror V6's bit-pack layout verbatim; only structural change is wrapping the entry in two `std::atomic<uint64_t>` slots for Hyatt-Mann XOR.

**V6 TTEntry layout — bit-pack reference for D-09 (`v6/include/tt.hpp:20-31`):**
```cpp
struct TTEntry {
    uint64_t key;       // Zobrist hash         (8 bytes)
    Move best_move;     // uint16_t             (2 bytes)
    int16_t score;      // mate-adjustable      (2 bytes)
    int8_t  depth;      // search depth         (1 byte)
    uint8_t flag;       // TT_EXACT/ALPHA/BETA  (1 byte, low 2 bits used)
    uint8_t age;        // generation           (1 byte)
                        // pad to 16 bytes
};
```
**V7 pack target (D-09 — fit Move + score + depth + flag + age into `uint64_t` data, key carried via `xkey = key ^ data`):**
- bits 0..15  → Move (uint16_t)
- bits 16..31 → score (int16_t reinterpreted as uint16_t)
- bits 32..39 → depth (int8_t reinterpreted as uint8_t)
- bits 40..47 → flag (uint8_t, low 2 bits used)
- bits 48..55 → age (uint8_t)
- bits 56..63 → padding (zero)

Final struct footprint: `std::atomic<uint64_t> xkey + std::atomic<uint64_t> data` = 16 bytes — identical to V6's `TTEntry` size, so cache-line packing math is preserved.

**Aligned allocation pattern (copy from V6 `tt.cpp:14-37` verbatim, including MSVC `_aligned_malloc` / posix `std::aligned_alloc` switch):**
```cpp
TranspositionTable::TranspositionTable(size_t size_mb) {
    size_t size_bytes = size_mb * 1024 * 1024;
    num_entries = size_bytes / sizeof(TTEntry);

    // Align to cache line (64 bytes)
#ifdef _MSC_VER
    entries = static_cast<TTEntry*>(_aligned_malloc(num_entries * sizeof(TTEntry), 64));
#else
    entries = static_cast<TTEntry*>(std::aligned_alloc(64, num_entries * sizeof(TTEntry)));
#endif
    if (!entries) { throw std::bad_alloc(); }
    clear();
}
```
For the V7 lockless rewrite, the slab type changes from `TTEntry*` to `AtomicEntry*` (or `std::atomic<uint64_t>*` ×2-per-slot), but the `_aligned_malloc` / `aligned_alloc` branch is copy-verbatim.

**Replacement policy pattern (copy logical structure from V6 `tt.cpp:67-79`, modify to age-then-depth per D-07):**
```cpp
// V6 (current — age OR depth OR same-key):
bool should_replace = (stored.key == hash) ||
                      (stored.depth < depth) ||
                      (stored.age != generation);
```
V7 D-07 requires **age-then-depth** (same key always replaces; otherwise prefer different-age; only if same age, compare depth). RESEARCH.md Pattern 1 store snippet captures the canonical decision. Use the V6 read-decide-write structure as the skeleton; substitute the new condition.

**Probe pattern (replace V6's single load with two atomic relaxed loads + XOR check) — RESEARCH.md Pattern 1 supplies the canonical Hyatt-Mann form; V6 lines 45-57 supply the hit/miss counter increment convention:**
```cpp
// V6 reference (replace `stored.key == hash` with `xkey ^ data == hash`):
if (stored.key == hash && stored.flag != TT_NONE) {
    entry = stored;
    hit_count.fetch_add(1, std::memory_order_relaxed);
    return true;
}
miss_count.fetch_add(1, std::memory_order_relaxed);
return false;
```
The `hit_count` / `miss_count` `std::atomic<uint64_t>` field pair (`v6/include/tt.hpp:68-69`) is copy-verbatim.

**`new_search()` and `clear()` API surface (preserve V6 signatures so search.cpp callers are unchanged):**
- `void new_search() { ++generation; }` — `v6/include/tt.hpp:52`
- `void clear() { std::memset(...); hit_count = 0; miss_count = 0; }` — `v6/src/tt.cpp:39-43`. **Caveat:** `memset(0)` on `std::atomic<uint64_t>` is permitted by the standard for trivially-default-constructible atomics, but the planner should add a brief comment confirming this is intentional (TSan stress is the canonical verification).

**Integration callsites that move from `g_tt` → `Engine::tt_` (per Open Question 1 in RESEARCH.md — Plan 03-01 mechanical migration BEFORE 03-05's rewrite lands):**
- `src/chess_engine/engine/v7/src/search.cpp:199` — `g_tt.probe(board.hash, tt_entry)`
- `src/chess_engine/engine/v7/src/search.cpp:366` — `g_tt.store(...)`
- `src/chess_engine/engine/v7/src/search.cpp:375` — `g_tt.store(...)`
- `src/chess_engine/engine/v7/src/search.cpp:492` — `g_tt.new_search()`

All four need a `SearchInfo::tt` non-owning pointer (mirroring `external_stop` / `rep_stack` pattern at `search.hpp:83-86`) wired in `Engine::search` like `info.external_stop = &stop_flag_` (`engine.cpp:84`). The `extern TT g_tt;` declaration at `v7/include/tt.hpp:77` can then be removed; final delete sweep should `grep -rn "g_tt" src/chess_engine/engine/v7/`.

---

### `src/chess_engine/engine/v7/src/search.cpp` (search core, request-response) — Plans 03-01/02/03

**Plan 03-01 self-modification — Bug #1 (info.depth contract, `engine.cpp:99-103` ↔ `search.cpp:398`):**

Current pattern (the bug):
```cpp
// engine.cpp:99-103
int max_depth = std::min(std::max(depth, 1), 64);
info.depth = max_depth;       // intended: upper bound for ID loop
tt_.new_search();
SearchResultFull full = iterative_deepening(board_, info, /*verbose=*/false);

// search.cpp:395-398
int max_depth = (info.depth > 0) ? std::min(info.depth, 64) : 64;
for (int depth = 1; depth <= max_depth && !info.stopped; ++depth) {
    info.depth = depth;       // CLOBBERS the caller's max_depth bound
```
Fix per CONTEXT D-03: add `info.max_depth` separately from `info.depth`. `info.depth` is purely the per-iteration counter; `iterative_deepening` reads `info.max_depth` as the cap. Both engine.cpp and search.cpp change in lockstep.

**Plan 03-01 self-modification — Bug #2 (killers/history per-call stack alloc, `search.cpp:270-273`):**
```cpp
// CURRENT (broken — killers reset every call, defeating the heuristic):
std::array<Move, 64> killers = {};                  // Simplified (V6 parity)
std::array<std::array<int, 64>, 12> history = {};   // Simplified (V6 parity)
int move_scores[256];
score_moves(board, moves, tt_move, killers, history, move_scores);
```
The `// V6 parity` comment is wrong (per RESEARCH.md Anti-Patterns + CONTEXT specifics): V6 has the SAME bug at `v6/src/search.cpp:194-197`. The fix per D-03 is to move killers/history to `Engine` member state (alongside `rep_stack_` at `engine.hpp:77`) and pass via `SearchInfo` pointer (mirroring `RepStack* rep_stack`). After Plan 03-01 lands, the `score_moves(board, moves, tt_move, killers, history, move_scores)` call becomes `score_moves(board, moves, tt_move, ss.killers[ply], engine_history, move_scores)` (or equivalent — exact signature is planner's discretion within the persistent-state contract).

**Plan 03-01 self-modification — Bug #3 (`std::vector<Move> pv` allocs):**

Allocation sites identified in current V7 search.cpp:
- `search.cpp:241` — `std::vector<Move> null_pv;` inside null-move block
- `search.cpp:317` — `std::vector<Move> child_pv;` inside main move loop
- `search.cpp:319/361` — `pv.clear(); pv.push_back(m); pv.insert(...)` PV concat
- `search.cpp:391` — `std::vector<Move> pv;` in `iterative_deepening`

Replace with triangular array on `SearchStack` (RESEARCH.md Pattern 2, copied here for the planner — write from scratch per D-03):
```cpp
constexpr int MAX_PLY = 128;
struct SearchStack {
    Move pv[MAX_PLY][MAX_PLY];
    int  pv_length[MAX_PLY];
    Move killers[MAX_PLY][2];
    Move excluded_move[MAX_PLY] = {};      // Plan 03-03 singular extension
    // ...
};
// On new best move at this ply:
ss.pv[ply][ply] = best_move;
for (int i = ply + 1; i < ss.pv_length[ply + 1]; ++i)
    ss.pv[ply][i] = ss.pv[ply + 1][i];
ss.pv_length[ply] = ss.pv_length[ply + 1];
```
`MAX_PLY = 128` per CONTEXT D-03 "covers all reachable plies" (Assumption A3 in RESEARCH.md).

**Plan 03-02 — Null-move + Zugzwang guard (SRCH-03) — modifies `search.cpp:229-258`:**

Current V7 null-move block (no zugzwang guard, allocates `std::vector<Move> null_pv`):
```cpp
// search.cpp:229-258 — replace entirely per SRCH-03
if (do_null && !in_check && depth >= NULL_MOVE_MIN_DEPTH && static_eval >= beta) {
    // ... (current code; no zugzwang check)
    int reduction = NULL_MOVE_R + depth / 4;     // fixed R formula
    int null_score = -alpha_beta(board, depth - reduction - 1,
                                 -beta, -beta + 1, info, ply + 1, null_pv, false);
    // ...
    if (null_score >= beta) { return beta; }     // no verification at high depth
}
```
Replacement (RESEARCH.md Code Examples §"Adaptive Null-Move", canonical pattern — write from scratch):
- Adaptive `R = 3 + depth/4 + min((static_eval - beta) / 200, 3)`
- `bool zugzwang_risk = (board.non_pawn_material(board.side_to_move) == 0);` guard
- High-depth (`depth >= 12`) verification re-search
- Triangular PV replaces `null_pv` allocation
- `UseNullMove` UCI toggle gate
- **Helper to add:** `board.non_pawn_material(Color)` — not present in V7 board (RESEARCH.md A9); trivial popcount over KNIGHT/BISHOP/ROOK/QUEEN. May exist in V6 — `grep -n "non_pawn" v6/include/board.hpp v6/src/board.cpp` (verified empty in this scan) — so it lands in Plan 03-02 as a small `board.hpp` extension.

**Plan 03-02 — LMR re-search two-level fix (SRCH-04) — modifies `search.cpp:324-332`:**

Current V7 has ONE re-search level (RESEARCH.md Pitfall 3 — known off-by-one risk):
```cpp
// search.cpp:324-332 — one re-search level (incomplete)
if (do_lmr) {
    int reduction = LMR_TABLE[std::min(depth, 63)][std::min(i, 63)];
    score = -alpha_beta(board, depth - 1 - reduction, -alpha - 1, -alpha, ...);
    if (score > alpha) {
        score = -alpha_beta(board, depth - 1, -beta, -alpha, ...);  // full-window
    }
}
```
Replace with canonical two-level (RESEARCH.md Pitfall 3 — verify against current Stockfish/Ethereal before final tuning per A5):
- Step 1: reduced zero-window at `depth - 1 - R`
- Step 2 (if `score > alpha && R > 0`): zero-window re-search at `depth - 1`
- Step 3 (if `score > alpha && score < beta`): full-window re-search at `depth - 1`

`LMR_TABLE` (`search.cpp:32-43`) is **kept verbatim**; the change is the re-search ladder, not the reduction formula. Context-aware adjustments (PV node, improving, in-check exclusions) land alongside; gate behind `UseLMR` UCI toggle.

**Plan 03-02 — Move-ordering (SRCH-06) — modifies `search.cpp:270-273`:**

Adds killers + history + counter-move + SEE-bucketed captures (RESEARCH.md Code Examples §"Staged Move Picker"). The `see(board, m)` function already exists in V7 (`search.cpp:104` — used in qsearch; reuse verbatim per RESEARCH.md "Don't Hand-Roll" table). The staged generator is new code; CONTEXT D's discretion allows splitting into `include/search/move_picker.hpp` + `src/search/move_picker.cpp` or keeping inline.

**Plan 03-03 — Singular extensions (SRCH-08) — modifies move loop in `search.cpp:284-372`:**

RESEARCH.md Code Examples §"Singular Extensions" canonical pattern:
- Gate: `depth >= 8 && m == tt_move && tt_entry.depth >= depth - 3 && tt_entry.flag == TT_BETA && !is_root`
- `excluded_move[ply]` field consulted at move-loop start
- TT probe at top of `alpha_beta` SKIPPED when `excluded_move[ply] != MOVE_NONE`
- Multi-cut (SRCH-09) piggybacks on the same re-search

The `Engine::SearchStack` structure landing in Plan 03-01 must include `Move excluded_move[MAX_PLY]` as a field so Plan 03-03 doesn't restructure the stack.

**Mate-distance correction wrappers (PRESERVE — `search.hpp:213-223`):**
`score_to_tt(score, ply)` and `score_from_tt(score, ply)` are inline in the header. Every TT store/probe must continue to wrap. RESEARCH.md explicitly warns: "Don't move them into TT methods" — they belong to the SEARCH side. Current sites at `search.cpp:366` and `search.cpp:375` use them correctly; new Plan 03-05 TT API must NOT change their call shape.

---

### `src/chess_engine/engine/v7/include/engine.hpp` (Engine class header) — Plan 03-01

**Analog:** itself (current Plan 03 of Phase 1 layout, lines 71-81).

Current member layout:
```cpp
private:
    std::atomic<bool>     stop_flag_{false};
    std::atomic<uint64_t> nodes_{0};

    TT       tt_{64};         // 64MB transposition table (matches V6 default)
    Board    board_;          // single working board; reset per search via from_fen
    RepStack rep_stack_;      // Plan 03 — Engine-owned repetition stack
    SyzygyState syzygy_;
```

Plan 03-01 additions (extend the pattern — `RepStack` is the template):
```cpp
private:
    // ... existing members ...
    SearchStack search_stack_;       // Plan 03-01 — owns triangular PV + per-ply killers/excluded
    int  history_[2][64][64] = {};   // Plan 03-01 — history[side][from][to]
    Move counter_moves_[2][64][64] = {};  // Plan 03-02 — counter_moves[side_that_moved][from][to]
```
History decay on `new_search()` (RESEARCH.md A11) lives in `Engine::new_game` and a new `Engine::age_history()` called from `Engine::search` before `iterative_deepening`. Mirror the pattern at `engine.cpp:38-52` (`new_game` already clears `tt_` and `rep_stack_`).

---

### `src/chess_engine/engine/v7/src/engine.cpp` (Engine glue) — Plan 03-01

**Analog:** itself (current `Engine::search` at lines 54-129).

The `Engine::search` body keeps its current shape (FOUND-04 stop_flag clear, FEN parse, rep_stack seed, SearchInfo wiring, TimeManager allocate) and adds:
- Wire new `SearchInfo::tt` to `&tt_` (mirrors the `external_stop = &stop_flag_` pattern at line 84)
- Wire new `SearchInfo::search_stack` to `&search_stack_` and `SearchInfo::history` / `counter_moves` pointers
- Bug-1 fix: split `info.depth = max_depth` into `info.max_depth = max_depth` (new field); preserve `info.depth = 0` so `iterative_deepening` writes the per-iteration counter cleanly

`Engine::new_game` (lines 38-52) gains:
```cpp
// Plan 03-01 additions:
std::memset(history_, 0, sizeof(history_));
std::memset(counter_moves_, 0, sizeof(counter_moves_));
// SearchStack PV/killers reset is a no-op (stack-owned, reset by search entry).
```
Note: `std::memset(0)` on `Move` arrays is safe because `MOVE_NONE == 0` (types.hpp). Document explicitly to match the V7 commenting style (cf. `engine.cpp:38-52` extended comments).

---

### `src/chess_engine/engine/v7/src/endgame.cpp` (NEW endgame eval) — Plan 03-04

**Analog (sister TU):** `src/chess_engine/engine/v7/src/eval.cpp` (full file).

**Imports / namespace / coeffs-access pattern** (copy verbatim from `eval.cpp:21-30`):
```cpp
#include "endgame.hpp"
#include "coeffs.hpp"
#include "board.hpp"
#include "movegen.hpp"
#include <algorithm>
#include <cstdint>
namespace v7 {
namespace { /* anonymous helpers */ }
```
**EVAL-10 rule (carry over from `eval.cpp:9-13` comment block):** no hardcoded weight constants in this file. All endgame coefficients come from `v7::coeffs::*` extern symbols (per D-12: opposition value, wrong-bishop-rook-pawn scale, KPK rule bonuses, fortress weights, phase-blend constants flow through `coeffs.json`).

**KPK probe shape** (small wrapper around the generated `KPK_BITBASE` table — table emitted by `tools/gen_kpk.py`):
```cpp
// In endgame.cpp (or kpk_probe.cpp helper)
extern const uint8_t KPK_BITBASE[];  // declared in kpk_bitbase.cpp (gitignored)
bool kpk_is_win(Color stm, Square wksq, Square bksq, Square psq) {
    int idx = kpk_index(stm, wksq, bksq, psq);  // RESEARCH.md Pitfall 5 encoding
    return (KPK_BITBASE[idx >> 3] >> (idx & 7)) & 1;
}
```
Reference encoding per RESEARCH.md Pitfall 5: `index = stm | (bksq << 1) | (wksq << 7) | (psq << 13)` with WTM-side normalization (folds black-to-move into the same table).

**Phase 0..256 blend formula** (replaces current `eval.cpp:425` `int final_score = (mg * phase + eg * (24 - phase)) / 24;` — RESEARCH.md Pitfall 6 canonical Stockfish form):
```cpp
int npm = std::clamp(non_pawn_material(WHITE) + non_pawn_material(BLACK),
                     v7::coeffs::endgame_limit, v7::coeffs::midgame_limit);
int phase = ((npm - v7::coeffs::endgame_limit) * 256) /
            (v7::coeffs::midgame_limit - v7::coeffs::endgame_limit);
int score = (mg * phase + eg * (256 - phase)) / 256;
```
`endgame_limit` and `midgame_limit` are NEW coeffs added to `coeffs.json` per D-12.

---

### `src/chess_engine/engine/v7/src/eval.cpp` (MODIFIED) — Plan 03-04

**Analog:** itself, lines 410-425 (current phase blend block).

Surgical change:
1. Replace `phase += popcount(...) * phase_weight(...)` accumulator (eval.cpp:158-160) with `non_pawn_material(WHITE) + non_pawn_material(BLACK)` calculation (helper added in Plan 03-02 for null-move; reused here).
2. Replace `int final_score = (mg_score * phase + eg_score * (24 - phase)) / 24;` (eval.cpp:425) with the 0..256 form above.
3. Insert `endgame_eval(board, mg_score, eg_score, phase)` call between the tempo block (lines 416-422) and the tapered combine — gives the new `endgame.cpp` a hook to inject KPK/opposition/wrong-bishop/fortress adjustments before the final blend.
4. Preserve the STM perspective flip (`return (board.side_to_move == WHITE) ? final_score : -final_score;`) — line 428, unchanged.

---

### `src/chess_engine/engine/v7/tools/gen_kpk.py` (NEW codegen) — Plan 03-04

**Analog:** `src/chess_engine/engine/v7/tools/gen_coeffs.py` (full file — exact sibling).

**Module docstring template** (mirror lines 1-36 of gen_coeffs.py — D-10 cross-references, D-13 determinism contract, "Only the Python stdlib... + numpy" usage note):
```python
"""Codegen: KPK bitbase -> src/kpk_bitbase.cpp.

D-10: this script is the build-time codegen invoked by V7's CMake
add_custom_command (Plan 03-04 task — pre-staged in CMakeLists.txt
alongside the existing coeffs codegen). It enumerates all 163,328 legal
KPK positions, classifies each as WIN/DRAW via canonical BFS, and emits
a C++ translation unit defining `extern const uint8_t KPK_BITBASE[];`
in the v7 namespace.

D-13: output is byte-deterministic across machines and across reruns on
the same input (the BFS is deterministic; the np.packbits ordering is
fixed).

Acceptance: cross-checks against Fathom's tb_probe_wdl for every
position before writing — generator fails non-zero if any disagreement.
"""
```

**Header template + `main(argv)` shape** (copy verbatim style from `gen_coeffs.py:45-58`, `97-131` — single-CLI invocation, Path args, sized output array):
```python
HEADER_TEMPLATE = (
    "// GENERATED by tools/gen_kpk.py — DO NOT EDIT\n"
    "// Source: build-time KPK BFS classification + Fathom cross-check\n"
    "//\n"
    "// Emitted by V7's CMake add_custom_command (D-10). Not committed\n"
    "// to git (D-12 — mirrors coeffs.cpp .gitignore rule).\n"
    "\n"
    '#include "endgame.hpp"\n'
    "#include <cstdint>\n"
    "\n"
    "namespace v7 {\n"
    "\n"
)
FOOTER = "\n} // namespace v7\n"

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write(f"usage: {argv[0]} <output.cpp>\n")
        return 2
    dst = Path(argv[1])
    dst.parent.mkdir(parents=True, exist_ok=True)
    generate(dst)
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

**LF-only write rule (copy from gen_coeffs.py:110):**
```python
# D-13: explicit LF line endings, regardless of host OS.
output_cpp_path.write_bytes(text.encode("utf-8").replace(b"\r\n", b"\n"))
```

**Bit-packing helper (use `numpy.packbits` per RESEARCH.md "Don't Hand-Roll" table):**
```python
import numpy as np
def emit_cpp(table: np.ndarray, out: Path):
    packed = np.packbits(table)  # 163_328 / 8 = 20_416 bytes
    text = ", ".join(f"0x{b:02x}" for b in packed)
    # ... emit "const uint8_t KPK_BITBASE[20416] = { ... };"
```

**Fathom acceptance cross-check** (RESEARCH.md "Don't Hand-Roll" — Fathom vendored Phase 1 Plan 01-05 at `src/chess_engine/engine/v7/extern/fathom/`). The generator imports Fathom via pybind11 if available or calls a thin C wrapper; acceptance fails fast if any disagreement detected before `dst.write_bytes`.

---

### `src/chess_engine/engine/v7/CMakeLists.txt` (MODIFIED) — Plan 03-04 + Plan 03-05

**Analog (for KPK codegen target):** itself, lines 43-70 (the COEFFS_CPP `add_custom_command` block — exact pattern).

Copy-translate to KPK (Plan 03-04):
```cmake
# Mirrors lines 43-70 — Plan 03-04 KPK bitbase codegen.
set(KPK_CPP ${CMAKE_CURRENT_SOURCE_DIR}/src/kpk_bitbase.cpp)
add_custom_command(
    OUTPUT ${KPK_CPP}
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_kpk.py ${KPK_CPP}
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_kpk.py
    COMMENT "Generating kpk_bitbase.cpp via tools/gen_kpk.py"
    VERBATIM
)
```
Add `${KPK_CPP}` to the `V7_SOURCES` list (line 80-92) and to the `v7_uci` add_executable source list (lines 112-124). Pre-staging shape (placeholder write when input absent) mirrors the existing `if(NOT EXISTS ${COEFFS_CPP})` branch at lines 66-69 — but for KPK there is no input file beyond the generator script itself, so the placeholder branch can be omitted (or kept defensive-only with a `placeholder_kpk.cpp` no-op).

**Analog (for TSan executable target, Plan 03-05):** itself, lines 105-130 (the `v7_uci` `add_executable` block).

Copy-pattern with TSan flags scoped only to the new target (RESEARCH.md Open Question 4 — keep the main `v7_engine` build untouched):
```cmake
# Plan 03-05 — TSan stress harness for lockless TT (PAR-03).
# Conditional: only builds when CMAKE_CXX_COMPILER_ID is GNU/Clang
# (TSan unavailable on MSVC — runs on WSL/Linux/macOS only per D-08).
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    add_executable(tt_tsan_stress
        ${CMAKE_CURRENT_SOURCE_DIR}/tt_tsan_stress.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/src/tt.cpp
        # ... minimal TU set to compile tt.cpp standalone ...
    )
    target_include_directories(tt_tsan_stress PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    )
    target_compile_options(tt_tsan_stress PRIVATE -fsanitize=thread -g -O1)
    target_link_options(tt_tsan_stress PRIVATE -fsanitize=thread)
endif()
```
The "additive-target discipline" comment from Phase 2's `v6_uci` block (`v6/CMakeLists.txt:60-68`) applies here verbatim — main `v7_engine` must continue to build unchanged.

---

### `src/chess_engine/engine/v7/tt_tsan_stress.cpp` (NEW standalone harness) — Plan 03-05

**NEW — no analog in repo.** Closest structural reference: V7 `Engine`/`Board` callsites in `engine.cpp` show how `tt_` is used (probe/store/new_search); the harness is its own `main()` that spawns 16 `std::thread`s, each running a tight `(rand_key, rand_data) probe/store` loop for 60 seconds.

**Structural skeleton (write from scratch per CONTEXT D-08, mirroring RESEARCH.md Open Question 4):**
```cpp
// tt_tsan_stress.cpp — PAR-03 stress driver.
// Source-of-truth reference for the data structure under test: V7's new
// lockless TT (src/tt.cpp, lines TBD after Plan 03-05). The harness must
// only ever exercise the public TT::probe / TT::store / TT::new_search
// surface — no peek into internals — so a passing TSan run is evidence
// that the public API is race-free under concurrent multi-thread access.
#include "tt.hpp"
#include <atomic>
#include <chrono>
#include <random>
#include <thread>
#include <vector>

int main() {
    v7::TT tt(64);
    std::atomic<bool> stop{false};
    constexpr int N_THREADS = 16;
    constexpr int DURATION_SEC = 60;
    std::vector<std::thread> workers;
    for (int t = 0; t < N_THREADS; ++t) {
        workers.emplace_back([&tt, &stop, t] {
            std::mt19937_64 rng(0xC0FFEEull + t);
            while (!stop.load(std::memory_order_relaxed)) {
                uint64_t k = rng();
                if (rng() & 1) {
                    v7::TTEntry e;
                    (void)tt.probe(k, e);
                } else {
                    tt.store(k, /*move=*/uint16_t(rng() & 0xFFFF),
                             /*score=*/int16_t(rng() & 0xFFFF),
                             /*depth=*/int8_t(rng() & 0x7F),
                             v7::TT_EXACT);
                }
            }
        });
    }
    std::this_thread::sleep_for(std::chrono::seconds(DURATION_SEC));
    stop.store(true, std::memory_order_relaxed);
    for (auto& w : workers) w.join();
    return 0;  // TSan report on stderr; exit 0 if clean
}
```
**Exit-code contract:** the binary itself always exits 0 on completion. TSan reports go to stderr; the wrapping shell script (`scripts/tt_tsan_stress.sh`) interprets non-empty `WARNING: ThreadSanitizer` output as failure and exits 1.

---

### `scripts/tt_tsan_stress.sh` (NEW shell harness) — Plan 03-05

**NEW — no analog in repo.** No existing shell harness for build+run+report. The script lives at top-level `scripts/` (CONTEXT D-08 wording: `scripts/tt_tsan_stress.sh`); `scripts/` dir does not currently exist (verified by `ls`) and is created by Plan 03-05.

**Structural skeleton (write from scratch — minimal portable bash):**
```bash
#!/usr/bin/env bash
# PAR-03 TSan stress harness for V7 lockless TT.
# Requires: clang or gcc with TSan support (NOT MSVC — runs on
# WSL/Linux/macOS per CONTEXT D-08). Blocking human checkpoint at
# end of Phase 3.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${ROOT}/src/chess_engine/engine/v7/build-tsan"
cmake -S "${ROOT}/src/chess_engine/engine/v7" -B "${BUILD_DIR}" \
      -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_COMPILER=clang++
cmake --build "${BUILD_DIR}" --target tt_tsan_stress -j
# Run harness, capture TSan output. Exit 1 if TSan emits WARNING.
LOG="$(mktemp)"
"${BUILD_DIR}/tt_tsan_stress" 2>"${LOG}"
if grep -q "WARNING: ThreadSanitizer" "${LOG}"; then
    echo "FAIL: TSan reported races" >&2
    cat "${LOG}" >&2
    exit 1
fi
echo "PASS: TSan clean over 16 threads × 60s"
```

---

### `.gitignore` (MODIFIED) — Plan 03-04

**Analog:** existing line 74:
```
src/chess_engine/engine/v7/src/coeffs.cpp
```

Add adjacent:
```
src/chess_engine/engine/v7/src/kpk_bitbase.cpp
```

Plus the TSan build directory (Plan 03-05):
```
src/chess_engine/engine/v7/build-tsan/
```

---

### Test files (Plans 03-01..05)

All Phase 3 V7 unit tests share an **exact analog**: the fixture-skeleton at `tests/test_v7_search.py:22-71` (module-scope `v7_native_engine` fixture, `v7.ensure_available(auto_build=True)`, skip on `V7UnavailableError`).

**Common test-file skeleton (copy verbatim from `test_v7_search.py:17-71`):**
```python
from __future__ import annotations

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7

STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails."""
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
```
Apply to: `test_v7_tt_lockless.py`, `test_v7_search_refinements.py`, `test_v7_move_picker.py`, `test_v7_history.py`, `test_v7_endgame.py`, `test_v7_phase_blend.py`, `test_v7_kpk_bitbase.py`.

**Benchmark-sentinel skeleton (test_v7_singular_nps_ratio.py, test_v7_lmr_depth.py):**

**Analog:** `tests/test_v7_engine.py:108-117` — the canonical `RUN_BENCHMARKS=1` skipif decorator block (also referenced verbatim by `tests/test_nps_regression.py:116-131`).

```python
@pytest.mark.benchmark
@pytest.mark.skipif(
    os.environ.get("RUN_BENCHMARKS") != "1",
    reason=(
        "NPS sentinel is a benchmark; set RUN_BENCHMARKS=1 to execute it. "
        "Default pytest invocations skip it because measurement requires a "
        "quiet, single-threaded host (background load skews NPS comparisons "
        "against the ~20% floor)."
    ),
)
def test_singular_nps_ratio_within_10_percent(v7_native_engine):
    """Pitfall 5 / Success Criterion #4 — UseSingular=on vs off NPS ratio ∈ [0.9, 1.1]."""
    # ... run bench twice with setoption UseSingular=true / false; compute ratio
```
**Helper to reuse:** `_assert_nps_ratio` shape from `tests/test_nps_regression.py:81-113` — same pattern (ratio against floor, skip if missing), adapted for the singular on/off pair.

**KPK acceptance test (`tests/test_v7_kpk_bitbase.py`):**

**Analog:** `tests/test_v7_eval.py:1-80` (codegen-output verification + native module check).

Verifies the emitted `kpk_bitbase.cpp` matches Fathom (via vendored `extern/fathom/`) on all 163,328 positions. May reuse the `EVAL_CPP` / `COEFFS_CPP_PATH` / `GITIGNORE` constants pattern at `test_v7_eval.py:36-43` for KPK paths:
```python
REPO_ROOT = Path(__file__).resolve().parent.parent
V7_DIR = REPO_ROOT / "src" / "chess_engine" / "engine" / "v7"
GEN_SCRIPT = V7_DIR / "tools" / "gen_kpk.py"
KPK_CPP_PATH = "src/chess_engine/engine/v7/src/kpk_bitbase.cpp"
GITIGNORE = REPO_ROOT / ".gitignore"
```
The "gitignored" assertion (RESEARCH §3 + D-12) follows `tests/test_v7_eval.py` `test_coeffs_cpp_gitignored` — runs `git check-ignore` subprocess on the KPK path.

**Shared fixtures already available (NO new conftest additions needed per RESEARCH §"Wave 0 Gaps"):**
- `gauntlet_root` (`tests/conftest.py:201-211`) — used by any new gauntlet-summary tests
- `summary_json_factory` (`tests/conftest.py:285-343`) — synthetic Phase-3 baseline/tier gauntlet summaries
- `_find_uci_binary` (`tests/conftest.py:166-198`) — discover `v7_uci` for setoption-based sentinels
- `latest_summary_dir` (`tests/conftest.py:346-362`) — lexical-greatest discovery for tier gauntlet results

---

## Shared Patterns

### 1. C++ namespace + V6 namespace-rename convention

**Source:** every V7 source file (e.g., `src/chess_engine/engine/v7/include/tt.hpp:7` → `namespace v7 {`)
**Apply to:** all new C++ files in Phase 3 (`endgame.cpp`, `endgame.hpp`, `tt_tsan_stress.cpp`, `kpk_bitbase.cpp`)

Every Phase 3 C++ TU opens with `namespace v7 {` and closes with `} // namespace v7`. Mirrors V6's `namespace v6 {` (`v6/include/tt.hpp:7` / closing line 77). V7's `chess_algorithm` Python module exposes only `v7::Engine` and `v7::perft_entry` — no internal types leak.

### 2. `// V6 parity` comment — TRUSTED but VERIFY

**Source:** present in `search.cpp:11`, `search.cpp:29`, `search.cpp:64`, `search.cpp:181`, `search.hpp:1-14`, `tt.hpp:74` and many more.
**Apply to:** every Plan 03-01 task touching these files.

Per CONTEXT specifics + memory (`project_phase1_known_perf_bugs.md`): "// V6 parity" comments in V7 search are NOT trustworthy as written — that's how the Phase 1 perf bugs slipped through. **Every Plan 03-01 task must `Read` the corresponding V6 source (e.g., `v6/src/search.cpp:194-197` for the killers/history claim) and confirm the parity is intact before proceeding.** Bugs #2 (killers reset) and #3 (`std::vector<Move> child_pv` — V6 line 170/234) are inherited V6 bugs, not V7 regressions — fixing in V7 means deviating from "V6 parity," which is the right call per D-03.

### 3. Aligned-allocation MSVC/posix branch

**Source:** `v6/src/tt.cpp:18-23`
**Apply to:** Plan 03-05 `tt.cpp` (TT slab) — copy verbatim.

```cpp
#ifdef _MSC_VER
    entries = static_cast<TTEntry*>(_aligned_malloc(num_entries * sizeof(TTEntry), 64));
#else
    entries = static_cast<TTEntry*>(std::aligned_alloc(64, num_entries * sizeof(TTEntry)));
#endif
```
And the matching destructor pattern (`v6/src/tt.cpp:31-37`):
```cpp
#ifdef _MSC_VER
    _aligned_free(entries);
#else
    std::free(entries);
#endif
```

### 4. SearchInfo non-owning pointer pattern (for the `tt_` migration)

**Source:** `v7/include/search.hpp:83-86` (`external_stop`, `soft_deadline_ms`, `hard_deadline_ms`, `rep_stack` already follow this) + `v7/src/engine.cpp:84-86` (wiring at search entry)
**Apply to:** Plan 03-01 `g_tt` → `Engine::tt_` migration AND Plan 03-02 history/counter/SearchStack wiring.

Every new shared state owned by `Engine` and accessed by search adds:
1. A non-owning pointer field on `SearchInfo` (mirroring `RepStack* rep_stack = nullptr;`)
2. A wire-up line in `Engine::search` (mirroring `info.rep_stack = &rep_stack_;`)
3. A preserve-across-reset note in `SearchInfo::reset` (mirroring "Do NOT clobber external_stop or rep_stack" at search.hpp:94)

### 5. Build-host deferred gates pattern

**Source:** `.planning/phases/01-skeleton-smoke/.continue-here.md` (Phase 1 precedent) + Phase 2 Task 3 deferred sanity probe (`02-05-SUMMARY.md`)
**Apply to:** Plan 03-01 baseline gauntlet (D-02), tier mini-gauntlets (D-05), TSan stress (D-08), fortress validation (D-11), ship SPRT (D-05).

Every Phase 3 plan that requires a build-host runtime gate documents it in the phase's eventual `.continue-here.md` rather than blocking Windows-host plan completion. Mirror the existing Phase 2 cadence: the plan summary states "deferred to build host — see `.planning/phases/03-.../continue-here.md`".

### 6. Codegen `.gitignore` + emitted-cpp pattern

**Source:** `.gitignore:74` (`src/chess_engine/engine/v7/src/coeffs.cpp`) + `src/chess_engine/engine/v7/CMakeLists.txt:43-70` (add_custom_command + EXISTS-guard placeholder write)
**Apply to:** Plan 03-04 `kpk_bitbase.cpp` codegen.

Every build-time-generated `.cpp` follows the same three-part contract:
1. Generator script under `src/chess_engine/engine/v7/tools/` (Python, stdlib-only or stdlib + numpy)
2. CMake `add_custom_command` with `OUTPUT`/`DEPENDS`/`COMMAND` + `${V7_SOURCES}` listing
3. `.gitignore` entry sibling to existing rules

### 7. UCI option plumbing (D-06 — 11 new toggles)

**Source:** `v7/src/uci_main.cpp:247-269` (setoption handler — Phase 2 Plan 02-01 silent-accept; per CONTEXT D-06 needs real wiring)
**Apply to:** Plans 03-02 / 03-03 / 03-04 (UseNullMove, UseLMR, UseRFP, UseFutility, UseLMP, UseSingular, UseMultiCut, UseProbCut, UseIIR, UseCheckExt, UseRecaptureExt, UseFortressEval).

Current Phase 2 parser at `uci_main.cpp:247-269` is silent-accept ("Phase 2: silent accept... Phase 4 may add..."). Plan 03-02 lifts the silence: parse `name <X> value <true|false>` into `Engine::set_option(name, value)`, which writes the toggle into `Engine::options_` (new struct) read by `alpha_beta` per-call. The existing token-walk skeleton at lines 258-269 is the parser shape to preserve — only the body of the value-discard block changes.

### 8. Mate-distance correction wrappers — TT side-effect-free

**Source:** `v7/include/search.hpp:213-223` (`score_to_tt` / `score_from_tt` inline functions) + callsites at `search.cpp:366` and `search.cpp:375`
**Apply to:** every TT.store / TT.probe wrapper site Plans 03-01..05 might touch (the Plan 03-05 lockless rewrite MUST NOT move these into TT methods).

The contract: the SEARCH side wraps every store with `score_to_tt(best_score, ply)` and every probe consumer with `score_from_tt(entry.score, ply)`. The TT itself stores raw int16_t — no awareness of mate distance. The Plan 03-05 rewrite preserves the `TT::store(hash, move, score, depth, flag)` API exactly so the wrapper calls are unaffected.

---

## No Analog Found

| File | Role | Data Flow | Reason | Closest Reference |
|------|------|-----------|--------|-------------------|
| `src/chess_engine/engine/v7/tt_tsan_stress.cpp` | standalone multi-thread C++ harness | event-driven (threads) | No existing standalone C++ executable in V7 dir besides `uci_main.cpp` (which is request-response, not multi-thread stress). | Data-structure-under-test: V7's new lockless `TT::probe/store` public API (Plan 03-05). API contract reference: V6 `TTEntry` struct at `v6/include/tt.hpp:20-31`. Concurrency primitives: `std::thread`, `std::atomic` (already used elsewhere in V7). |
| `scripts/tt_tsan_stress.sh` | bash harness (build + run + report) | request-response (subprocess) | No existing bash script in the repo (`scripts/` dir does not exist). | Argv-dispatch shape: `cli/bin/chess-engine.js` (different language, but the spawn-subprocess-then-grep-output structure is the closest conceptual analog). For TSan-specific patterns the planner must consult external (Stockfish's `tt_test` or libstdc++ TSan docs) — no in-repo guidance. |

---

## Metadata

**Analog search scope:**
- `src/chess_engine/engine/v6/` (full tree — TT, search, eval, CMake, uci_main)
- `src/chess_engine/engine/v7/` (full tree — current Phase 1+2 source, includes, tools, CMake)
- `tests/` (root — Phase 1 V7 tests + Phase 2 gauntlet/NPS sentinels + conftest fixtures)
- `.gitignore`
- `.planning/phases/02-gauntlet-harness-early/02-PATTERNS.md` (template style reference)
- `tests/conftest.py` (Phase 2 shared fixtures)
- `scripts/` (verified non-existent — Plan 03-05 creates)
- `tools/` (root — gauntlet/fastchess scripts; not modified in Phase 3)

**Files scanned (Read tool):** 13 (CONTEXT.md, RESEARCH.md, v6/include/tt.hpp, v6/src/tt.cpp, v7/include/tt.hpp, v7/src/search.cpp ×3 ranges, v7/src/engine.cpp, v7/include/engine.hpp, v7/include/search.hpp, v7/CMakeLists.txt, v6/CMakeLists.txt, v7/tools/gen_coeffs.py, tests/test_nps_regression.py, tests/conftest.py, tests/test_v7_search.py, tests/test_v7_engine.py, tests/test_v7_eval.py, .planning/phases/02-.../02-PATTERNS.md, v7/src/eval.cpp partial, v6/src/search.cpp partial, v7/src/uci_main.cpp partial)

**Files scanned (Grep tool):** 6 (`coeffs.cpp` / `kpk` / `KPK` in .gitignore; `non_pawn_material` / `popcount` in v6; `score_moves` / `killers` / `history` in v6/search.cpp; `g_tt` + `phase` in v7 src; `score_moves` etc. in v6 search header; `setoption` etc. in v7 uci_main)

**Pattern extraction date:** 2026-05-17
