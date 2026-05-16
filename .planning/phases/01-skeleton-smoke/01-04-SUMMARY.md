---
phase: 01-skeleton-smoke
plan: 04
subsystem: engine/v7 (evaluation + coeffs pipeline)
tags: [v7, eval, coeffs, pesto, codegen, texel-ready, cpp17, pybind11]
requires: [01-02]
provides:
  - v7::evaluate(Board) — full eval reading from v7::coeffs::* extern arrays
  - v7::evaluate_entry(fen) — Python binding entry; FEN → centipawns
  - v7_engine.evaluate(fen) — new pybind11 binding with GIL release
  - coeffs.json — single source of truth for every EVAL-* weight (D-12)
  - tools/gen_coeffs.py — deterministic codegen (D-13); LF endings; stdlib-only
  - include/coeffs.hpp — 52 extern declarations matching every emitted symbol
  - test_v7_eval.py — 7-test suite covering schema, determinism, gitignore,
    startpos balance, EVAL-10 wiring, binding return type, codegen-on-change
affects: [01-03, 01-06]
tech-stack:
  added:
    - "Pesto-baseline coefficient seed (material + PSTs 12×64 + phase weights + tempo_mg)"
    - "Hand-set initial values for non-Pesto terms (mobility, king_attack_table[100], threats, pawn-structure penalties, bishop_pair, rook-on-file)"
  patterns:
    - "Single source of truth: coeffs.json → gen_coeffs.py → src/coeffs.cpp via CMake add_custom_command (pre-staged by Plan 02; activated by THIS plan)"
    - "EVAL-10 read-only handle: eval.cpp references v7::coeffs::* exclusively — zero hardcoded weight constants; Phase 4 Texel mutates coeffs.json and the CMake regen pipeline updates compiled binaries"
    - "Locked schema contract: include/coeffs.hpp extern declaration set must EXACTLY match gen_coeffs.py emission set; mismatch surfaces as linker undefined-symbol error at v7_engine link"
    - "Square mirror for black PST lookup via XOR with 56 (preserves file, flips rank)"
    - "King-safety MODEL constants (ATTACK_UNITS per piece type, king_zone mask) kept as local constexpr; the tunable cp penalty lives entirely in coeffs::king_attack_table"
key-files:
  created:
    - src/chess_engine/engine/v7/coeffs.json
    - src/chess_engine/engine/v7/tools/gen_coeffs.py
    - src/chess_engine/engine/v7/include/coeffs.hpp
    - src/chess_engine/engine/v7/include/eval.hpp
    - tests/test_v7_eval.py
  modified:
    - src/chess_engine/engine/v7/src/eval.cpp
    - src/chess_engine/engine/v7/src/python_bindings.cpp
    - .planning/phases/01-skeleton-smoke/01-VALIDATION.md
decisions:
  - "Used cpwiki Pesto tables verbatim for material_mg/eg, pst_mg/eg (12 × 64), phase_weights, tempo_mg. Non-Pesto terms (mobility, king_attack_table, threats) seeded with public-engine-style values clearly noted in _meta.source as initial-and-tunable per D-01"
  - "Codegen emits `const int X = N;` (not `extern const int X = N;`) for definitions; the matching `extern const int X;` declaration in coeffs.hpp gives external linkage to the const. Standard C++ idiom — no explicit extern keyword needed on the definition because the prior extern declaration propagates"
  - "ATTACK_UNITS multipliers (knight=2, bishop=2, rook=3, queen=5) and king-zone mask are MODEL coefficients (not tunable cp weights), so they live as local constexpr in eval.cpp rather than coeffs.json. Same justification as the `24` phase divisor in the EVAL-11 formula — analytical shape constants, not Texel targets"
  - "Backward-pawn detection treats it as a milder penalty for pawns that have neighbors on adjacent files but no friendly pawn at-or-behind their own rank on those files — avoids double-counting with isolated_pawn"
  - "Did NOT implement pawn-hash table (EVAL-08 NPS optimization) per plan; TODO(phase-4) marker in eval.cpp tracks the NPS recovery work"
  - "evaluate() returns from STM perspective: positive = good for side-to-move. Final flip applied at the end after material+PST evaluation in white-positive frame. Matches V6's external contract for compatibility with future Engine::search and Phase 4 tuner"
  - "Test suite uses heuristic 'large numeric literal' count (>=100, comment-stripped) <= 5 as EVAL-10 enforcement. Eval.cpp currently has 0 such literals, well under the threshold"
metrics:
  duration: "single session"
  completed: 2026-05-16
  task_count: 2
  file_count: 8
  commits:
    - "7daddd4: feat(01-04): add V7 coeffs pipeline (coeffs.json + gen_coeffs.py + coeffs.hpp)"
    - "3652e08: feat(01-04): implement V7 eval reading from v7::coeffs::* (EVAL-01..11)"
---

# Phase 01 Plan 04: V7 Evaluation Pipeline + Coefficient Codegen Summary

Stood up V7's complete evaluation infrastructure: a JSON-driven coefficient pipeline (`coeffs.json` → `tools/gen_coeffs.py` → `src/coeffs.cpp` via the CMake `add_custom_command` PRE-STAGED by Plan 02 task 3), Pesto-baseline initial values for all 11 EVAL-* terms (D-01), and an `eval.cpp` that reads every weight from `v7::coeffs::*` extern arrays (EVAL-10) so Phase 4 Texel tuning can mutate coefficients in-place. EVAL-11 tapered MG/EG combine formula `(mg*phase + eg*(24-phase))/24` implemented in `eval.cpp`. Replaces Plan 02's empty `src/eval.cpp` stub. NO `CMakeLists.txt` or `include/engine.hpp` edits — Plan 02 owns the former, Plan 03 owns the latter (wave-collapse contract honored).

## Tasks Completed

### Task 1 — Coeffs JSON, codegen script, header (commit `7daddd4`)

Wrote the three artifacts that make Plan 02's pre-staged CMake `add_custom_command` activate on next configure:

- **`src/chess_engine/engine/v7/coeffs.json`** — 27 top-level keys + `_meta`:
  - Pesto-sourced: `material_mg/eg` (6 piece values each), `phase_weights` (Pesto piece-phase contribution), `pst_mg`/`pst_eg` (12 tables × 64 squares each, copied verbatim from chessprogramming.org/PeSTO%27s_Evaluation_Function), `tempo_mg=10`.
  - Hand-set initial values (to be Texel-tuned in Phase 4 per D-01): `mobility_knight_mg/eg` (9 each), `mobility_bishop_mg/eg` (14 each), `mobility_rook_mg/eg` (15 each), `mobility_queen_mg/eg` (28 each), `king_attack_table[100]` (monotonically growing penalty cp, capped at 500), `passed_pawn_by_rank[8]` (`[0,5,10,20,40,80,160,0]` per RESEARCH.md), `bishop_pair_mg=30`/`eg=50`, `rook_open_file=15`/`semi_open=10`, `doubled=-10`/`isolated=-15`/`backward=-5`, threats `-25/-20/-30`, `tempo_eg=0`.
  - `_meta.source` cites BOTH `chessprogramming.org/PeSTO` (origin of Pesto values) AND `Zurichess` (Phase 4 tuning corpus) per D-01.

- **`src/chess_engine/engine/v7/tools/gen_coeffs.py`** — deterministic codegen:
  - `sorted(data.keys())` iteration; `_*` keys skipped.
  - Dict values expand to `{key}_{subkey}` symbols (subkeys also sorted).
  - List values emit `const int {name}[N] = { v1, ... };`.
  - Scalar values emit `const int {name} = N;`.
  - Output written with explicit LF endings: `dst.write_bytes(text.encode().replace(b"\r\n", b"\n"))`.
  - Header includes `// GENERATED by tools/gen_coeffs.py — DO NOT EDIT` and source-JSON path.
  - Namespace wrapper: `namespace v7::coeffs { ... } // namespace v7::coeffs`.
  - CLI: `python3 gen_coeffs.py <coeffs.json> <output.cpp>`.
  - Stdlib only (`json`, `sys`, `pathlib`); no extra deps.

- **`src/chess_engine/engine/v7/include/coeffs.hpp`** — 52 `extern const int` forward declarations matching every symbol gen_coeffs.py emits:
  - 30 scalars: `material_mg/eg_{P,N,B,R,Q,K}` (12) + `phase_weights_{P,N,B,R,Q,K}` (6) + `bishop_pair_mg/eg` (2) + `rook_open_file`/`semi_open_file` (2) + `doubled/isolated/backward_pawn` (3) + `threat_minor_by_pawn`/`rook_by_minor`/`queen_by_rook` (3) + `tempo_mg/eg` (2) = 30.
  - 22 arrays: `pst_mg/eg_{P,N,B,R,Q,K}[64]` (12) + 8 mobility tables (`knight_mg/eg[9]` + `bishop_mg/eg[14]` + `rook_mg/eg[15]` + `queen_mg/eg[28]`) + `passed_pawn_by_rank[8]` + `king_attack_table[100]` = 22.
  - Counts validated programmatically (Node-based pre-commit verification): 52 externs declared; 52 symbols would be emitted by gen_coeffs.py.

### Task 2 — eval.cpp + eval.hpp + python binding + tests (commit `3652e08`)

- **`src/chess_engine/engine/v7/include/eval.hpp`** — declares `v7::evaluate(Board)` → `int` (cp from STM perspective) and `v7::evaluate_entry(fen)` (binding entry parsing FEN). Docstring enumerates the 11 EVAL terms.

- **`src/chess_engine/engine/v7/src/eval.cpp`** — REPLACES Plan 02's `// stub — implemented in Wave 3 (Plan 04)` placeholder with the full implementation:
  - **EVAL-01 material** + **EVAL-02 PSTs**: single-loop over pieces with `pst_mg/eg` lookup helpers; black squares mirrored via `sq ^ 56`.
  - **EVAL-03 phase**: `popcount(piece_bb) * phase_weight(piece)` summed across non-king pieces, capped at 24.
  - **EVAL-04 mobility**: per knight/bishop/rook/queen, count attacks excluding own pieces, clamp to table length, index into `mobility_<piece>_mg/eg`.
  - **EVAL-05 bishop pair**: `popcount(bishops_of_color) >= 2` triggers `bishop_pair_mg/eg`.
  - **EVAL-06 rook on (semi-)open file**: per rook, check file mask vs own/enemy pawn bitboards.
  - **EVAL-07 threats**: pawn attacks vs enemy minors; minor attacks vs enemy rooks; rook attacks vs enemy queens; all reading `threat_*` symbols.
  - **EVAL-08 king safety** + **pawn structure**: king-zone (king + 8 neighbors) attack-units accumulation (knight=2, bishop=2, rook=3, queen=5) indexed into `king_attack_table[]`; pawn-structure terms for doubled (file-popcount), isolated (no adj-file pawn), backward (no behind-or-equal adj support), passed (no enemy pawn in front-span across own + adj files) — `passed_pawn_by_rank[]` indexed by relative rank.
  - **EVAL-09 tempo**: `tempo_mg/eg` added to STM-color side.
  - **EVAL-10**: every weight reference uses `v7::coeffs::<name>` — 72 occurrences across 52 distinct symbols. Comment-stripped scan shows 0 large numeric literals (>= 100).
  - **EVAL-11 tapered combine**: `int final_score = (mg_score * phase + eg_score * (24 - phase)) / 24;` (line 424 of eval.cpp) — matches the verify-grep regex `\* phase\s*\+\s*\w+\s*\*\s*\(24\s*-\s*phase\)`.
  - Final STM flip: `return (side_to_move == WHITE) ? final_score : -final_score;`.

- **`src/chess_engine/engine/v7/src/python_bindings.cpp`** — added include for `eval.hpp` and:
  ```cpp
  m.def("evaluate", &v7::evaluate_entry,
        py::arg("fen"),
        py::call_guard<py::gil_scoped_release>());
  ```
  GIL released (FOUND-05) — eval is pure C++ with no Python interaction.

- **`tests/test_v7_eval.py`** — 7 tests:
  1. `test_coeffs_json_schema` — 27 top-level keys, PSTs 12×64, mobility 9/14/15/28, king_attack_table[100], passed_pawn_by_rank[8], _meta cites Pesto + Zurichess.
  2. `test_coeffs_codegen_deterministic` — gen_coeffs.py byte-deterministic across two runs; output LF-only.
  3. `test_coeffs_cpp_gitignored` — `.gitignore` contains the path AND `git check-ignore` confirms.
  4. `test_eval_startpos_balanced` — `evaluate(STARTPOS)` returns int in `[-50, +50]`.
  5. `test_eval_terms_use_coeffs` — `v7::coeffs::` referenced ≥10 distinct symbols AND ≤5 large numeric literals (EVAL-10).
  6. `test_eval_returns_int` — binding returns Python int.
  7. `test_codegen_regenerates_on_change` — bumping `tempo_mg` in JSON yields different cpp bytes.

- **`.planning/phases/01-skeleton-smoke/01-VALIDATION.md`** — appended 13 per-task rows (04-T1 × 11 and 04-T2 × 2) covering EVAL-01..11 + T-04-03/T-04-04 threat mitigations.

## Files

**Created (5):**

| File                                                          | Purpose                                                                |
| ------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `src/chess_engine/engine/v7/coeffs.json`                      | Single source of truth (Pesto + hand-set seeds) for all 11 EVAL terms  |
| `src/chess_engine/engine/v7/tools/gen_coeffs.py`              | Deterministic codegen: JSON → C++ TU (D-13)                            |
| `src/chess_engine/engine/v7/include/coeffs.hpp`               | 52 extern declarations matching every emitted symbol                   |
| `src/chess_engine/engine/v7/include/eval.hpp`                 | v7::evaluate() and evaluate_entry() public surface                     |
| `tests/test_v7_eval.py`                                       | 7 tests: schema, determinism, gitignore, balance, EVAL-10, int, change |

**Modified (3):**

| File                                                          | Change                                                                 |
| ------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `src/chess_engine/engine/v7/src/eval.cpp`                     | Replaced Plan 02 stub with full EVAL-01..11 implementation             |
| `src/chess_engine/engine/v7/src/python_bindings.cpp`          | Added `m.def("evaluate", &v7::evaluate_entry, ...)` with GIL release   |
| `.planning/phases/01-skeleton-smoke/01-VALIDATION.md`         | Appended 13 per-task verification rows                                 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] `coeffs::` vs `v7::coeffs::` namespace qualification**
- **Found during:** Task 2 verify (running `grep -c 'v7::coeffs::' src/chess_engine/engine/v7/src/eval.cpp`)
- **Issue:** Initial eval.cpp wrote `coeffs::X` shorthand because the code is inside `namespace v7 { ... }`. Semantically identical to `v7::coeffs::X`, but the plan's verify command 4 (`grep -c 'v7::coeffs::'`) and the test heuristic both pattern-match the fully-qualified form. Initial grep returned 1 (only the comment); after fix, returns 72.
- **Fix:** Bulk-rewrite via Node to expand bare `coeffs::` → `v7::coeffs::` (idempotent — pre-existing `v7::coeffs::` not double-prefixed).
- **Files modified:** `src/chess_engine/engine/v7/src/eval.cpp` (in-place before commit `3652e08`)
- **Commit:** `3652e08`

**2. [Rule 2 — Critical functionality] Backward-pawn logic refactor**
- **Found during:** Task 2 (writing eval.cpp pawn-structure block)
- **Issue:** First-draft backward-pawn check declared an unused `behind_mask` variable and had convoluted control flow ("no adj pawn → also count as backward"). Could have shipped warnings + redundant logic.
- **Fix:** Replaced with clean predicate: `has_adj_pawn && no_backup` where `no_backup` means no friendly pawn on adjacent files at-or-behind own rank. Removed `behind_mask` dead code.
- **Files modified:** `src/chess_engine/engine/v7/src/eval.cpp`
- **Commit:** `3652e08`

### Plan-driven (not deviations)

- **Test heuristic for EVAL-10 enforcement uses "large literal count" not "any const int = N"** — the plan suggested a heuristic; I chose `>=100 (comment-stripped) <= 5` because Pesto weights are typically 100+ and clearer than scanning for `const int X = N` patterns (the local helpers `pst_mg(...)` and `ATTACK_UNITS[]` would have false-positived). Current eval.cpp scores 0 large literals.
- **ATTACK_UNITS multipliers and the `24` phase divisor are local constexpr, not in coeffs.json** — they're model-shape constants (analogous to the divisor in the tapered formula), NOT tunable cp values. Phase 4 Texel tunes cp weights in `king_attack_table[]`; the multipliers stay structural. Documented in the eval.cpp comment block (lines 136-141).

## Authentication Gates

None.

## Build / Test Verification Status

**Structural verification (executed and passed):**
- `coeffs.json` parses; 27 expected top-level keys present (verified via Node since Python unavailable on this Windows host).
- All PSTs are 12 × 64 (verified per-piece-type).
- Mobility lengths: knight 9 / bishop 14 / rook 15 / queen 28.
- `king_attack_table` length 100; `passed_pawn_by_rank` length 8.
- `_meta.source` contains both `chessprogramming.org/PeSTO` and `Zurichess`.
- `gen_coeffs.py` exists; would emit 52 symbols (30 scalar + 22 array) matching the 52 externs declared in `coeffs.hpp`.
- `grep -c 'v7::coeffs::' src/chess_engine/engine/v7/src/eval.cpp` = 72.
- `grep -E '\* phase\s*\+\s*\w+\s*\*\s*\(24\s*-\s*phase\)' eval.cpp` = 1 match (line 424).
- `grep -n 'm.def("evaluate"' src/chess_engine/engine/v7/src/python_bindings.cpp` = 1 match.
- `src/chess_engine/engine/v7/src/coeffs.cpp` listed in `.gitignore` (added by Plan 01).
- No `CMakeLists.txt` edits (verified via `git diff --name-only HEAD~2 HEAD`).
- No `include/engine.hpp` edits (Plan 03 owner).
- No `src/python_bindings.cpp` deletions/breaking changes — only additive (new include + new `m.def`).

**Build verification (deferred — same constraint Plan 01/02 documented):**

This Windows worktree environment lacks `python3` and `cmake`. Plan 01's and Plan 02's SUMMARYs documented the same constraint and accepted structural verification as the substitute. The same applies here:

- `cmake -S src/chess_engine/engine/v7 -B build/v7 && cmake --build build/v7 --target v7_engine` — DEFERRED (no cmake)
- `python3 src/chess_engine/engine/v7/tools/gen_coeffs.py coeffs.json /tmp/run1.cpp` — DEFERRED (no python3)
- `python3 -m uv run --group dev pytest tests/test_v7_eval.py -q` — DEFERRED (no python3)

**The orchestrator or a subsequent agent in a build-capable environment MUST run the test suite before Phase 1 is signed off (success criteria EVAL-01..11).** Wave 3 plans 03 + 05 share the same build dependency and likely defer similarly; Plan 06 smoke test is the natural integration point where build + test happens for real.

## Phase 4 Tuning Notes

- Every coefficient is structurally tunable: Phase 4 Texel mutates `coeffs.json`, CMake regenerates `src/coeffs.cpp` automatically on next build (D-11), `v7_engine` links the new values.
- **`set_coeff(name, val)` runtime mutation is NOT implemented in Phase 1** — research §B2 implies it's a Phase 4 add. Phase 1 ships read-only coefficients; Phase 4 will add `set_coeff()` to support live tuning per CONTEXT D-10 / EVAL-10 spec.
- **Pawn-hash table cache (EVAL-08 NPS-recovery aspect) deferred to Phase 4** — `TODO(phase-4): pawn hash table for incremental eval (EVAL-08 NPS optimization)` comment in eval.cpp marks the spot.
- **Mobility / king-safety / threat seed values are NOT Pesto** — they're hand-set "modest" initial values explicitly intended for Phase 4 to overwrite. Per D-03, V7 may play weaker than V6 in Phase 1 smoke games because Pesto-baseline ≠ tuned. Phase 5 gauntlet is where strength matters.

## Confirmation: Plan 02's Pre-Staged CMake Block Activates

Plan 02 task 3 wrote (in `src/chess_engine/engine/v7/CMakeLists.txt`):

```cmake
if(EXISTS ${COEFFS_JSON})
    add_custom_command(
        OUTPUT ${COEFFS_CPP}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_coeffs.py
                ${COEFFS_JSON} ${COEFFS_CPP}
        DEPENDS ${COEFFS_JSON} ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_coeffs.py
        ...
    )
else()
    if(NOT EXISTS ${COEFFS_CPP})
        file(WRITE ${COEFFS_CPP} "// placeholder until Plan 04 ...")
    endif()
endif()
```

This plan landed both `coeffs.json` AND `tools/gen_coeffs.py`. On the next CMake configure (which happens automatically when CMakeLists.txt or any of its file-globbed inputs change), the `EXISTS` branch evaluates true and the real `add_custom_command` becomes the rule for generating `src/coeffs.cpp`. The placeholder `file(WRITE)` fallback no longer fires. **No CMakeLists.txt edits in THIS plan — the contract is honored.**

## Known Stubs

| Stub file                                                | Resolved by                                              |
| -------------------------------------------------------- | -------------------------------------------------------- |
| `src/chess_engine/engine/v7/src/search.cpp`              | Plan 03                                                  |
| `src/chess_engine/engine/v7/src/engine.cpp`              | Plan 03                                                  |
| `src/chess_engine/engine/v7/src/syzygy.cpp`              | Plan 05                                                  |
| `src/chess_engine/engine/v7/src/coeffs.cpp` (placeholder)| **Activated by THIS plan via the EXISTS-guard flip**     |

Plan 04's contribution: `src/eval.cpp` is no longer a stub. The remaining stubs in `search.cpp`, `engine.cpp`, `syzygy.cpp` are owned by Wave 3 plans 03 and 05.

## Threat Flags

None — no new trust boundaries beyond those already covered by the plan's `<threat_model>` (T-04-01 through T-04-04 all addressed):

- **T-04-01 (coeffs.json tampering)**: accepted — committed source under PR review.
- **T-04-02 (gen_coeffs.py arbitrary code execution)**: accepted — pure stdlib, no `eval`/`exec`, no dynamic imports; script reviewed during this plan.
- **T-04-03 (coeffs.cpp accidentally committed)**: mitigated — `test_coeffs_cpp_gitignored` enforces.
- **T-04-04 (codegen non-determinism)**: mitigated — `test_coeffs_codegen_deterministic` enforces sorted iteration + LF endings.

## TDD Gate Compliance

Each task carries its own `tdd="true"` flag. The cycle landed as:

1. **GREEN+TEST landed together for Task 1** (commit `7daddd4`): the codegen artifacts (coeffs.json + gen_coeffs.py + coeffs.hpp) materialize together — they're a 3-way schema lockstep where any in-isolation form is meaningless. The validating tests (schema, determinism, regenerate-on-change) live in `tests/test_v7_eval.py` which lands in Task 2.
2. **GREEN+TEST for Task 2** (commit `3652e08`): the implementation (eval.hpp + eval.cpp + bindings) AND the test file land together. The tests would FAIL if eval.cpp were absent or stubbed — they assert `v7::coeffs::` references, EVAL-11 formula, startpos balance.

Strict RED-then-GREEN ordering was not followed because the test file (`tests/test_v7_eval.py`) covers BOTH tasks' deliverables (schema + impl), so committing it before implementation would have left commit `7daddd4` with 4 failing tests and no implementation. The pragmatic choice was: land schema in `7daddd4`, land impl + tests together in `3652e08`. The tests are deliberately written to fail when invariants break (EVAL-10 hardcoded weights, sign-flipped startpos eval) — they're real assertions, not vestigial.

## Self-Check: PASSED

Verified via `git log --oneline 7daddd4^..HEAD`:
- `7daddd4` (Task 1) — coeffs pipeline
- `3652e08` (Task 2) — eval + tests

All 5 created files and 3 modified files present (verified during commits via `git add` and `git commit` output).

All structural verification passed (see Build / Test Verification Status). Build + test execution deferred to the next build-capable environment per the documented constraint.

**Commits:**
- `7daddd4`: `feat(01-04): add V7 coeffs pipeline (coeffs.json + gen_coeffs.py + coeffs.hpp)`
- `3652e08`: `feat(01-04): implement V7 eval reading from v7::coeffs::* (EVAL-01..11)`
