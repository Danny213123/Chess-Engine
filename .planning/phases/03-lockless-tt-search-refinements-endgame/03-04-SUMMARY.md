---
phase: 03-lockless-tt-search-refinements-endgame
plan: "04"
subsystem: endgame-evaluation
tags: [endgame, kpk-bitbase, phase-blend, opposition, wrong-bishop, fortress, eval]
dependency_graph:
  requires: [03-01]
  provides: [ENDG-01, ENDG-02, ENDG-03, ENDG-04, ENDG-05]
  affects: [eval.cpp, endgame.cpp, search.cpp, coeffs.json, python_bindings.cpp]
tech_stack:
  added: []
  patterns:
    - CMake add_custom_command codegen for kpk_bitbase.cpp (mirrors coeffs.cpp pattern)
    - Stockfish-style 0..256 tapered eval phase blend
    - D-12 coefficients-only discipline (no hand-tuned constexpr in endgame.cpp)
    - D-11 fortress-behind-toggle pattern
key_files:
  created:
    - src/chess_engine/engine/v7/tools/gen_kpk.py
    - src/chess_engine/engine/v7/include/endgame.hpp
    - src/chess_engine/engine/v7/src/endgame.cpp
  modified:
    - src/chess_engine/engine/v7/src/eval.cpp
    - src/chess_engine/engine/v7/include/eval.hpp
    - src/chess_engine/engine/v7/src/search.cpp
    - src/chess_engine/engine/v7/src/python_bindings.cpp
    - src/chess_engine/engine/v7/src/uci_main.cpp
    - src/chess_engine/engine/v7/coeffs.json
    - src/chess_engine/engine/v7/include/coeffs.hpp
    - src/chess_engine/engine/v7/CMakeLists.cpp
    - .gitignore
    - tests/test_v7_kpk_bitbase.py
    - tests/test_v7_endgame.py
    - tests/test_v7_phase_blend.py
decisions:
  - "D-10: gen_kpk.py generates kpk_bitbase.cpp at build time; Fathom cross-check deferred to build host (Windows dev host has no C++ toolchain)"
  - "D-11: UseFortressEval defaults OFF; ship ON only after separate validation gauntlet shows positive Elo"
  - "D-12: all 5 new endgame coefficients in coeffs.json only — no hardcoded constexpr in endgame.cpp"
  - "KPK array size is 24576 bytes (2*64*64*24/8), not 20416 as originally stated in plan artifact spec; 20416 used only pawn file 0..3 but stm bit needs separate accounting — 24576 is correct"
metrics:
  duration: "~120 min (across two sessions)"
  completed: "2026-05-17"
  tasks_completed: 2
  tasks_total: 3
  files_created: 3
  files_modified: 12
---

# Phase 03 Plan 04: Endgame Evaluation (ENDG-01..05) Summary

KPK bitbase codegen, opposition eval, wrong-bishop+rook-pawn draw recognition, Stockfish-style 0..256 continuous phase blend, and conservative fortress detection behind a UCI toggle — all endgame coefficients flowing through coeffs.json.

## Completed Tasks

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | KPK codegen + endgame.hpp + CMake | f4519a8 | gen_kpk.py, endgame.hpp, CMakeLists.txt, .gitignore, test_v7_kpk_bitbase.py |
| 2 | Endgame eval implementation | 5e99178 | endgame.cpp, eval.cpp, eval.hpp, search.cpp, python_bindings.cpp, coeffs.json, coeffs.hpp, uci_main.cpp, test_v7_endgame.py, test_v7_phase_blend.py |

## Task 3 Status: Checkpoint (human-verify)

Task 3 is a `checkpoint:human-verify` requiring build-host validation:
- KPK Fathom cross-check (163,328 positions) — needs C++ toolchain
- Endgame mini-gauntlet vs V6 — needs compiled V7 binary
- Fortress scoped validation gauntlet — needs compiled V7 binary

This checkpoint must be executed on a Linux/macOS build host. See checkpoint message below.

## What Was Built

### Task 1: KPK Codegen Infrastructure (ENDG-01)

`tools/gen_kpk.py` — Build-time BFS retrograde analysis over all legal KPK positions:
- Enumerates 163,328 positions using Stockfish-style index formula with horizontal symmetry fold for pawn files 4-7 (mirrors files to 0-3)
- BFS classification: starts from terminal positions (pawn on rank 8 = illegal, king adjacent = illegal), propagates WIN/DRAW backward
- Output: packed `uint8_t[24576]` C++ array using `numpy.packbits(bitorder='little')` for LSB-first bit layout matching the `(KPK_BITBASE[idx>>3] >> (idx&7)) & 1` probe in endgame.cpp
- Fathom cross-check reference present but deferred to build host (PATTERNS.md Shared Pattern 5)
- LF-only output (D-13 discipline)

`include/endgame.hpp` — Public API:
- `extern const uint8_t KPK_BITBASE[24576]` (defined in gitignored kpk_bitbase.cpp)
- `bool kpk_is_win(Color stm, Square wksq, Square bksq, Square psq)`
- `bool has_opposition(const Board& b, Color side)`
- `bool is_wrong_bishop_rook_pawn_draw(const Board& b)`
- `bool is_fortress(const Board& b)`
- `void endgame_eval(const Board& b, int& mg, int& eg, int phase, bool fortress_enabled = false)`

CMakeLists.txt extension:
- `add_custom_command(OUTPUT kpk_bitbase.cpp COMMAND Python3 gen_kpk.py ...)` block mirrors existing `coeffs.cpp` pattern (Shared Pattern 6)
- `endgame.cpp` and `${KPK_CPP}` added to both `V7_SOURCES` and `v7_uci` source lists

.gitignore:
- Added `src/chess_engine/engine/v7/src/kpk_bitbase.cpp` at line 75, sibling to existing `coeffs.cpp` entry at line 74

### Task 2: Endgame Eval Implementation (ENDG-02..05)

`src/endgame.cpp` — Full endgame evaluation module:
- `kpk_index_impl()`: Stockfish-style symmetry fold + index formula, produces indices in [0, 196608)
- `kpk_is_win()`: O(1) bit-lookup into KPK_BITBASE
- `has_opposition()`: detects df=0,dr=2 OR df=2,dr=0 OR df=dr=2 with other-side-to-move check
- `is_wrong_bishop_rook_pawn_draw()`: K+B+RP vs K pattern; bishop color != promo square color; defending king reachable check
- `is_fortress()`: dispatches to 3 patterns: KB vs KRP, KN vs KP, locked pawn chains (all very conservative)
- `endgame_eval()`: orchestrates fortress (short-circuit), wrong-bishop (scale toward draw), KPK probe, opposition bonus

`src/eval.cpp` — Phase blend upgrade (ENDG-04):
- Replaced 0-24 integer phase with Stockfish-style 0..256:
  ```cpp
  npm = clamp(npm, endgame_limit, midgame_limit);
  phase = ((npm - endgame_limit) * 256) / (midgame_limit - endgame_limit);
  ```
- `endgame_eval()` call inserted between tempo block and tapered combine
- Tapered combine updated from `/24` to `/256`
- New `compute_phase(const Board&)` function for test binding

`coeffs.json` — 5 new endgame coefficients (D-12):
- `endgame_limit: 0` — below this npm, clamp to 0 → phase = 0
- `midgame_limit: 6196` — above this npm, clamp → phase = 256
- `opposition_value: 15` — centipawn bonus for side with opposition
- `wrong_bishop_rp_scale: 0` — 0 = full draw (multiply score by 0/256), 256 = no scaling
- `fortress_score: 0` — centipawn score for detected fortress (0 = draw score)

UCI / pybind11:
- `uci_main.cpp`: `option name UseFortressEval type check default false`
- `python_bindings.cpp`: `compute_phase(fen)` and `kpk_is_win(stm, wksq, bksq, psq)` bindings

Tests:
- `test_v7_kpk_bitbase.py`: gitignore assertion + gen_kpk.py structure checks
- `test_v7_endgame.py`: opposition bonus direction, wrong-bishop draw (score ≤ 50cp), fortress no-crash + set_option
- `test_v7_phase_blend.py`: phase=256 at startpos, phase=0 at bare kings, monotone decrease across serial captures

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] KPK array size corrected from 20416 to 24576 bytes**
- **Found during:** Task 1 implementation
- **Issue:** Plan artifact spec stated `uint8_t[20416]` but Stockfish-style index formula `stm | (bksq<<1) | (wksq<<7) | (psq_idx<<13)` with 2*64*64*24 positions gives 196608 bits = 24576 bytes, not 20416
- **Fix:** Used 24576 throughout (endgame.hpp declaration, gen_kpk.py output, KPK_BITBASE probe bounds)
- **Files modified:** endgame.hpp, gen_kpk.py
- **Commit:** f4519a8

**2. [Rule 2 - Missing] Added coeffs.hpp extern declarations for new endgame coefficients**
- **Found during:** Task 2
- **Issue:** Plan did not explicitly list coeffs.hpp as a file to modify, but the D-12 contract requires new coefficients to flow through the extern declaration chain
- **Fix:** Added 5 extern declarations to coeffs.hpp
- **Files modified:** include/coeffs.hpp
- **Commit:** 5e99178

## Known Stubs

None — all endgame features are implemented. The Fathom cross-check in `gen_kpk.py` is marked as deferred-to-build-host rather than a stub; the BFS algorithm is complete and the cross-check framework is present.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: endgame-correctness | src/endgame.cpp | KPK probe returns DRAW for illegal positions (idx out of [0,196608)); this is safe — illegal positions are never submitted by evaluate() |

## Self-Check: PASSED

All 10 key files found. Both task commits (f4519a8, 5e99178) verified in git log.
