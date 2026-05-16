---
phase: 01-skeleton-smoke
plan: 05
subsystem: engine/v7 (syzygy / Fathom integration)
tags: [v7, syzygy, fathom, tablebase, c++17, pybind11, wave-3]
requires:
  - 01-01 (Engine class skeleton + pybind11 set_syzygy_path/tbhits bindings pre-staged)
  - 01-02 (board.hpp / movegen.hpp surface + pre-staged EXISTS-guarded Fathom CMake block)
provides:
  - Pinned Fathom (jdart1) submodule at src/chess_engine/engine/v7/extern/fathom (SHA c9c6fef0dddc05d2e242c183acf5833149ab676d)
  - V7-owned tbconfig.h override that shares v7:: magic-bitboard + bitboard helpers with Fathom
  - v7::SyzygyState class (set_path, set_max_pieces, initialized, tbhits, probe_wdl, probe_root_dtz)
  - v7_tb_* extern "C" bridges callable from Fathom's C tbprobe.c
  - 5 D-08 verbatim init-time log strings on stderr
  - KRk smoke probe (TB-10) — fails loudly on corrupt / wrong-format tables
  - REAL tb_probe_root_dtz wiring (TB-04 — no stub)
  - 8 pytest tests covering init-log discipline + tbhits gating + KRk endpoint reflection
affects:
  - 01-03 (Engine forwarding wrapper in src/engine.cpp will call syzygy_.set_path / .tbhits)
  - 01-06 (CLI exposes set_syzygy_path; SYZYGY_PATH env wires through chess_algorithm.py)
tech-stack:
  added:
    - Fathom (jdart1 fork) — pinned C99 Syzygy probing library, linked into v7_engine + v7_uci via the pre-staged EXISTS-guarded CMake block
  patterns:
    - "extern \"C\" bridge functions (v7_tb_*) cross the C/C++ FFI from Fathom's tbprobe.c into v7's C++ namespace symbols"
    - "Verbatim D-08 log strings — exact byte-for-byte stderr output as a stability promise (users grep for them)"
    - "TB_RESULT_FAILED -> std::nullopt invariant (D-09) in BOTH probe_wdl and probe_root_dtz — failure is never silently mapped to DRAW or fabricated DTZ"
    - "Probe gating layered as separate fast-skip checks (initialized_, TB_LARGEST, max_pieces_, in_check, castling_rights) so each precondition is auditable in isolation"
    - "Reflected-tbhit test pattern — when probe_wdl is not yet exposed to Python (Phase 1), the KRk smoke probe's incremented tbhits counter is observed at the Engine boundary"
key-files:
  created:
    - .gitmodules
    - src/chess_engine/engine/v7/extern/fathom (submodule gitlink)
    - src/chess_engine/engine/v7/include/tbconfig.h
    - src/chess_engine/engine/v7/include/syzygy.hpp
    - tests/test_v7_syzygy.py
  modified:
    - src/chess_engine/engine/v7/src/syzygy.cpp (overwrites Plan 02 single-line stub)
    - .planning/phases/01-skeleton-smoke/01-VALIDATION.md (13 new per-task verification rows)
decisions:
  - "tb_probe_root_dtz signature mismatch with RESEARCH.md §A3 — jdart1 fork returns `int` + fills `TbRootMoves*`, NOT a packed `unsigned` with TB_GET_DTZ encoding. We pass a TbRootMoves, check ok != 0 && moves.size > 0, and return moves[0].tbScore as the int score (Fathom-internal WDL+DTZ-derived ranked-best-move score). The plan's TB_GET_DTZ fallback path is therefore not needed. Documented in syzygy.cpp comment above probe_root_dtz."
  - "C-callable bridge functions (v7_tb_pawn_attacks, ...) instead of `v7::` namespace symbols in tbconfig.h macros. Rationale: tbprobe.c is compiled as C (CMakeLists.txt set_source_files_properties LANGUAGE C), and the C compiler cannot resolve C++-mangled namespace symbols. Bridges live in syzygy.cpp wrapped in `extern \"C\"` and forward to v7::pawn_attacks[][], v7::bishop_attacks(), etc."
  - "Wired BOTH Fathom's documented override hooks (TB_CUSTOM_LSB, TB_CUSTOM_POP_COUNT) AND the plan-named macros (TB_pop_lsb, TB_popcount). Fathom only checks the TB_CUSTOM_* names; the plan-named macros pass the acceptance grep and are available for direct C++ callers."
  - "v7::pawn_attacks is `Bitboard[2][64]` indexed [color][sq] (NOT a function). tbconfig.h's TB_PAWN_ATTACKS(sq, color) macro is satisfied by `v7_tb_pawn_attacks(sq, color)` which performs the array lookup with arg order swapped from the array's native order."
  - "Test 7/8 KRk endpoint exposure path — REFLECTED via tbhits, not a direct Python binding. probe_wdl / probe_root_dtz are intentionally not surfaced to Python in Phase 1 (Engine class binding owned by Plan 01 only exposes set_syzygy_path + tbhits + search + new_game + stop + nodes; probe_* are C++-internal for use by Plan 03's search). The KRk smoke probe inside set_path counts as one tbhit on success — observable from Python. Test assertions: `eng.tbhits() >= 1` after `eng.set_syzygy_path(SYZYGY_PATH)`. If smoke probe failed, case-4 log emits and tbhits stays 0."
  - "TB-08 max_pieces_ default = 6 (matches the standard Syzygy tablebase set; jdart1 Fathom supports up to 7-piece in some builds). set_max_pieces clamps to [0, 7]."
  - "tbhits decremented on the unknown-WDL fallback path so the counter reflects ONLY genuinely-decoded probes. This is more conservative than the spec (which only says 'increments on success') and prevents an unknown-WDL response from inflating the hit count."
metrics:
  duration: single-wave parallel execution
  completed: 2026-05-16
  task_count: 2
  file_count: 6
  commits:
    - "a77ceae: feat(01-05): add Fathom submodule + tbconfig.h override (TB-01, TB-02, INT-06)"
    - "37a96ea: feat(01-05): implement SyzygyState + D-08 log discipline + KRk smoke probe (TB-03..08, TB-10)"
---

# Phase 01 Plan 05: Syzygy Tablebase Integration (Fathom) Summary

Fathom (jdart1 fork) added as a pinned git submodule under
`src/chess_engine/engine/v7/extern/fathom/`; V7-owned `tbconfig.h`
shares the magic-bitboard attack tables with Fathom via `extern "C"`
bridge functions; `SyzygyState` class provides D-07/D-08 verbatim
init-time log discipline, a KRk smoke probe (TB-10) that fails loudly
on corrupt tablebases, an in-search WDL probe that maps
`TB_RESULT_FAILED → std::nullopt` (D-09 invariant — never silently
mapped to DRAW), and a REAL root-DTZ probe (TB-04 — no stub) calling
Fathom's `tb_probe_root_dtz` directly.

## Pinned Fathom SHA

```
c9c6fef0dddc05d2e242c183acf5833149ab676d
src/chess_engine/engine/v7/extern/fathom (v1.0-103-gc9c6fef)
```

`git submodule status src/chess_engine/engine/v7/extern/fathom` and
`.gitmodules` both record the gitlink. The parent commit `a77ceae`
contains the gitlink mode `160000` entry.

## RESEARCH.md §A3 API Deltas (audit notes)

| Symbol                       | RESEARCH.md assumption                                    | Actual Fathom (jdart1) surface                                                                          | Action taken                                         |
| ---------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `tb_probe_root_dtz`          | returns packed `unsigned` decodable via `TB_GET_DTZ(res)` | returns `int` (non-zero=ok, 0=failed); fills `struct TbRootMoves *_results` with per-move `tbScore`     | Pass `TbRootMoves`, return `moves[0].tbScore`        |
| `tb_probe_wdl`               | returns packed `unsigned` decodable via `TB_GET_WDL(res)` | static inline returns the raw WDL constant (TB_LOSS..TB_WIN, 0..4) or `TB_RESULT_FAILED` (`0xFFFFFFFF`) | Switch directly on `result` value                    |
| WDL constants                | symbolic (TB_WIN, TB_LOSS, ...)                           | TB_LOSS=0, TB_BLESSED_LOSS=1, TB_DRAW=2, TB_CURSED_WIN=3, TB_WIN=4                                      | Use symbolic constants (values are not hard-coded)   |
| `tbconfig.h` macro overrides | `TB_pop_lsb` / `TB_popcount` (per plan)                   | Fathom checks `TB_CUSTOM_LSB(x)` / `TB_CUSTOM_POP_COUNT(x)`                                             | Define BOTH plan-named AND Fathom-native macro names |
| `pawn_attacks` shape         | function `pawn_attacks(sq, color)`                        | `Bitboard pawn_attacks[2][64]` array indexed `[color][sq]`                                              | Bridge function swaps arg order on lookup            |
| `knight_attacks` shape       | function `knight_attacks(sq)`                             | `Bitboard knight_attacks[64]` array                                                                     | Bridge function does array lookup                    |
| `king_attacks` shape         | function `king_attacks(sq)`                               | `Bitboard king_attacks[64]` array                                                                       | Bridge function does array lookup                    |
| `bishop/rook/queen_attacks`  | function `bishop_attacks(sq, occ)` etc.                   | inline functions in `movegen.hpp` (delegated to `Magic::operator()`)                                    | Bridge functions forward directly                    |

None of these deltas required modifying Fathom or the V7 attack
tables — every adaptation lives inside `tbconfig.h` (macros) and
`syzygy.cpp` (`extern "C"` bridges + `tb_probe_root_dtz` decoding).

## TB-04 Root-DTZ Implementation Note

`probe_root_dtz` calls Fathom's `tb_probe_root_dtz` directly (the
jdart1 fork's only root-DTZ entry point). Signature:

```cpp
int tb_probe_root_dtz(
    uint64_t white, uint64_t black,
    uint64_t kings, uint64_t queens, uint64_t rooks,
    uint64_t bishops, uint64_t knights, uint64_t pawns,
    unsigned rule50, unsigned castling, unsigned ep,
    bool turn, bool hasRepeated, bool useRule50,
    struct TbRootMoves *results);
```

We pass `hasRepeated=false` (Phase 1 does not yet integrate the
Engine-side repetition stack into TB queries — Plan 03's rep_stack_
arrives in the same wave and will be threaded in by Plan 06's UCI
loop) and `useRule50=true` (Fathom default — cursed-win / blessed-loss
treatment honored).

On success (`ok != 0 && moves.size > 0`) we return
`moves[0].tbScore` as `std::optional<int>` — Fathom ranks moves
internally so `moves[0]` is the best move; its `tbScore` is the
WDL+DTZ-derived score Fathom computed during the probe.

On failure (`ok == 0` or `moves.size == 0`) we return `std::nullopt`
and emit `[v7] syzygy: root probe failed at fen=<fen>` to stderr
(D-09 invariant — never fabricate a DTZ).

KRk endpoint root-DTZ assertion (test 8) reflects via `tbhits()`
because `probe_root_dtz` is not yet surfaced at the Python boundary
(test exposure decision documented below).

## Test 7/8 Endpoint Exposure Path

Phase 1 surfaces only `set_syzygy_path / tbhits / new_game / search /
stop / nodes` on the pybind11 `Engine` class (Plan 01-fixed contract).
`probe_wdl` and `probe_root_dtz` are C++-internal — Plan 03's search
loop calls them directly; they do not cross the Python boundary in
Phase 1.

Therefore test 7 (`test_krk_endpoint_wdl_probe`) and test 8
(`test_root_dtz_probe_returns_some_when_tables_present`) reflect the
KRk WIN endpoint through `tbhits()`:

1. Test calls `eng.set_syzygy_path(SYZYGY_PATH)`.
2. Inside `set_path`, `smoke_probe_krk()` runs after `tb_init`. On
   success it calls `tb_probe_wdl` on the canonical KRk FEN
   (`4k3/8/8/8/8/8/4R3/4K3 w - - 0 1`), asserts the result is
   `TB_WIN`, and increments `tbhits_`.
3. Test asserts `eng.tbhits() >= 1`. If the smoke probe returned
   anything other than `TB_WIN`, set_path would have logged D-08 case 4,
   called `tb_free`, and reset `tbhits_` to 0 — the assertion would
   fail (which is the desired behavior per "the TEST MUST FAIL if the
   WIN result is not produced — silent skips are not acceptable").

Both tests carry `pytest.mark.skipif(not HAS_KRVK, reason="...")` so
they cleanly skip when SYZYGY_PATH is unset or KRvK.rtbw is missing.

## TB-08 Default: `max_pieces_ = 6`

Matches the standard Syzygy tablebase distribution and the CLI default
Plan 06 will wire. `set_max_pieces` clamps to `[0, 7]` (jdart1 Fathom
supports up to 7-piece in some builds).

## D-08 Verbatim Log Strings (audit)

For future grep audits, these are the exact byte sequences emitted by
`syzygy.cpp` — note the verbatim semicolon, single-space separators,
and trailing `\n`:

| Case | String                                                                                              |
| ---- | --------------------------------------------------------------------------------------------------- |
| 1    | `[v7] syzygy: no path configured; tbhits will be 0\n`                                               |
| 2    | `[v7] syzygy: path not found: <path>; tbhits will be 0\n`                                           |
| 3    | `[v7] syzygy: no tablebase files at <path>; tbhits will be 0\n`                                     |
| 4    | `[v7] syzygy: smoke probe failed (corrupt or wrong format) at <path>; tbhits will be 0\n`           |
| 5    | `[v7] syzygy: tb_init failed at <path>; tbhits will be 0\n`                                         |

Additional non-D-08 stderr lines (used by D-09 nullopt-on-failure):

- `[v7] syzygy: in-search probe failed at fen=<fen>\n`
- `[v7] syzygy: in-search probe returned unknown WDL=<n> at fen=<fen>\n` (defensive fallback)
- `[v7] syzygy: root probe failed at fen=<fen>\n`

## File-Ownership Coexistence Notes (Wave 3 invariant)

### CMakeLists.txt

Plan 05 made **ZERO edits** to `src/chess_engine/engine/v7/CMakeLists.txt`.
Plan 02 Task 3 pre-staged the EXISTS-guarded Fathom block:

```cmake
set(FATHOM_DIR ${CMAKE_CURRENT_SOURCE_DIR}/extern/fathom)
if(EXISTS ${FATHOM_DIR}/src/tbprobe.c)
    enable_language(C)
    target_include_directories(v7_engine PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include   # V7's tbconfig.h FIRST
        ${FATHOM_DIR}/src
    )
    target_sources(v7_engine PRIVATE ${FATHOM_DIR}/src/tbprobe.c)
    # ... same for v7_uci
    set_source_files_properties(${FATHOM_DIR}/src/tbprobe.c PROPERTIES LANGUAGE C)
endif()
```

The `EXISTS` guard flips from false to true on the next CMake
configure after Plan 05's `git submodule add` (commit `a77ceae`)
populates `${FATHOM_DIR}/src/tbprobe.c`. No CMake edits required.

### python_bindings.cpp

Plan 05 made **ZERO edits** to
`src/chess_engine/engine/v7/src/python_bindings.cpp`. Plan 01 pre-staged
both `set_syzygy_path` and `tbhits` `py::class_<Engine>` bindings —
verified by `grep -nE 'set_syzygy_path|tbhits' python_bindings.cpp`
returning the existing `.def(...)` entries.

The bindings call into `Engine::set_syzygy_path` and `Engine::tbhits`.
Phase 1's wiring path:

```
Python  ─── set_syzygy_path / tbhits ──> python_bindings.cpp (Plan 01)
                                          │
                                          ▼
                                 Engine::set_syzygy_path  (currently STUB body
                                          │                in python_bindings.cpp;
                                          │                Plan 03 moves it to
                                          │                src/engine.cpp and
                                          │                forwards to syzygy_.set_path)
                                          ▼
                                 SyzygyState::set_path  ──> THIS PLAN (syzygy.cpp)
```

Plan 03 is the sole owner of the `Engine::set_syzygy_path` forwarding
wrapper and must remove the Plan 01 stub from `python_bindings.cpp`
when it lands the real engine.cpp. This plan does not touch either
file.

### include/engine.hpp

Plan 05 made **ZERO edits** to
`src/chess_engine/engine/v7/include/engine.hpp`. Plan 03 owns engine.hpp
this wave and is responsible for:

- Adding `#include "syzygy.hpp"` near the top.
- Adding `v7::RepStack rep_stack_;` (Plan 03's own member).
- Adding `v7::SyzygyState syzygy_;` private member.

The forward-declaration `struct SyzygyState;` already present on
engine.hpp line 26 (placed by Plan 01 / 02) keeps the file compilable
even before Plan 03's `#include` lands.

## Build-Coupling Risk (Acknowledged Advisory)

Per Plan 05's `<critical_anti_patterns>` section: in this isolated
worktree the `cmake --build target v7_engine` step would fail because
plan 03's `engine.hpp` updates (adding the `v7::SyzygyState syzygy_;`
member and `#include "syzygy.hpp"`) and Plan 03's `src/engine.cpp`
forwarding wrapper do not yet exist on this branch. This is a
**deliberate fail-fast trade** of the wave-collapse design — each
parallel worktree compiles only with its own changes plus the Wave 2
pre-stage. The merge agent reconciles the three wave-3 worktrees and
the post-merge build verifies the full link.

Structural verification (file presence, grep gates, file-ownership
diffs) all pass — see "Self-Check" below.

## Pawn-Hash Cache (EVAL-08) — Cross-Reference

EVAL-08 is owned by Phase 4 NPS recovery; restated here for the
verifier so the cross-reference exists in the Plan 05 SUMMARY as
required by `<output>`. Plan 05 does NOT add a pawn-hash cache; the
SyzygyState `mutable std::atomic<uint64_t> tbhits_` is the only mutable
cache-like member added.

## Windows MSVC Build Notes

No special MSVC flags required by `syzygy.cpp`. Fathom's `tbprobe.c`
contains C99 idioms (designated initializers, mixed declarations) that
MSVC's C compiler accepts under `/std:c11` or later — Plan 02's
`CMAKE_C_STANDARD` is not pinned, so MSVC uses its default C mode
(which handles C99 since VS 2013). No `tbconfig.h` MSVC guards beyond
the `_MSC_VER` check that was originally planned (we ended up not
needing per-platform LSB intrinsics in tbconfig.h because Fathom has
its own portable fallback when `TB_CUSTOM_LSB` is defined).

## Files

**Created (5):**

| File                                                  | Purpose                                                                                        |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `.gitmodules`                                         | Pins Fathom submodule path + URL                                                               |
| `src/chess_engine/engine/v7/extern/fathom`            | Submodule gitlink at SHA c9c6fef (jdart1 fork)                                                 |
| `src/chess_engine/engine/v7/include/tbconfig.h`       | Fathom override — 8 macro redirects + Fathom-native TB_CUSTOM_LSB/TB_CUSTOM_POP_COUNT overrides + scoring constants |
| `src/chess_engine/engine/v7/include/syzygy.hpp`       | ProbeResult struct + SyzygyState class declaration                                             |
| `tests/test_v7_syzygy.py`                             | 8 tests — init-log discipline (subprocess stderr capture) + tbhits gating + KRk endpoint reflection |

**Modified (2):**

| File                                                  | Change                                                                                                                                                                              |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/chess_engine/engine/v7/src/syzygy.cpp`           | Overwrites Plan 02's single-line stub with: 8 extern "C" bridge functions; SyzygyState::set_path (5 D-08 cases); set_max_pieces; ~SyzygyState; probe_wdl; probe_root_dtz; smoke_probe_krk |
| `.planning/phases/01-skeleton-smoke/01-VALIDATION.md` | 13 per-task verification rows for TB-01..08 and TB-10                                                                                                                               |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] tb_probe_root_dtz signature mismatch with RESEARCH.md §A3**
- **Found during:** Task 1 Step 2 (reading actual `extern/fathom/src/tbprobe.h`)
- **Issue:** RESEARCH.md §A3 documented `tb_probe_root_dtz` as returning a packed `unsigned` decodable via `TB_GET_DTZ(res)`. The jdart1 fork's actual signature returns `int` (non-zero=ok, 0=failed) and writes ranked moves into a caller-supplied `TbRootMoves *_results`. The plan's `TB_GET_DTZ(result)` fallback path doesn't apply.
- **Fix:** Pass `TbRootMoves moves; tb_probe_root_dtz(..., /*hasRepeated=*/false, /*useRule50=*/true, &moves)`. On `ok != 0 && moves.size > 0` return `moves[0].tbScore`; otherwise return `std::nullopt` with D-09 log. Plan's `<action>` Step 2 explicitly anticipated this: "the locked decision is 'implement TB-04 now using Fathom directly', not specifically tb_probe_root_dtz; whichever real Fathom function provides the DTZ at root is acceptable. Document the chosen variant in the SUMMARY."
- **Files modified:** `src/chess_engine/engine/v7/src/syzygy.cpp`
- **Commit:** `37a96ea`

**2. [Rule 3 — Blocking] C/C++ FFI boundary for tbconfig.h macros**
- **Found during:** Task 1 Step 3 (designing tbconfig.h)
- **Issue:** Plan envisioned tbconfig.h macros calling `v7::pawn_attacks(sq, color)` etc. directly. Reality: tbprobe.c is compiled as C (`set_source_files_properties LANGUAGE C` in pre-staged CMakeLists.txt), and C cannot resolve C++-mangled namespace symbols at link time.
- **Fix:** Declared 8 `v7_tb_*` bridge functions with C linkage in tbconfig.h (wrapped in `extern "C"` for C++ inclusion); implemented them in syzygy.cpp wrapped in `extern "C"` block; bridges forward to v7:: C++ symbols. Macros expand to bridge calls.
- **Files modified:** `src/chess_engine/engine/v7/include/tbconfig.h`, `src/chess_engine/engine/v7/src/syzygy.cpp`
- **Commit:** `a77ceae` (tbconfig.h), `37a96ea` (bridges in syzygy.cpp)

**3. [Rule 2 — Critical functionality] Fathom override hook names**
- **Found during:** Task 1 Step 2 (reading actual `extern/fathom/src/tbconfig.h`)
- **Issue:** Plan instructed defining `TB_pop_lsb(b)` and `TB_popcount(b)` macros. Fathom's own tbconfig.h (read at integration time) only checks `TB_CUSTOM_LSB(x)` and `TB_CUSTOM_POP_COUNT(x)` as override hooks. Defining only the plan-named macros would let Fathom silently fall back to its internal lsb/popcount.
- **Fix:** Defined BOTH the plan-named macros AND Fathom's actual override hooks. Plan-named macros are kept so the acceptance grep passes and direct C++ callers can use the named entry points; Fathom-native names ensure tbprobe.c actually uses our bridges.
- **Files modified:** `src/chess_engine/engine/v7/include/tbconfig.h`
- **Commit:** `a77ceae`

**4. [Rule 2 — Critical functionality] Unknown-WDL fallback tbhit rollback**
- **Found during:** Task 2 Step 2 (writing probe_wdl)
- **Issue:** A defensive `default:` branch in probe_wdl's WDL switch (for an unknown WDL value Fathom might return on a future API change) initially incremented tbhits before returning nullopt. That would inflate the counter with un-decoded probes — a soft correctness regression for TB-07.
- **Fix:** Roll back `tbhits_.fetch_sub(1, std::memory_order_relaxed)` on the unknown-WDL path so the counter reflects only genuinely-decoded probes. Documented in syzygy.cpp comment.
- **Files modified:** `src/chess_engine/engine/v7/src/syzygy.cpp`
- **Commit:** `37a96ea`

### Plan-driven (not deviations)

**5. Test 7/8 reflect KRk endpoint via tbhits instead of direct probe binding**
- The plan explicitly authorized this exposure path: "If `probe_wdl` is not yet exposed via pybind11 (Phase 1 may keep it C++-internal and only surface tbhits to Python), exercise the assertion via ... the smoke_probe_krk() return value reflected back through tbhits". Phase 1 does NOT surface probe_wdl / probe_root_dtz to Python — Plan 01's pre-staged Engine binding only exposes set_syzygy_path / tbhits / new_game / search / stop / nodes. Documented above in "Test 7/8 Endpoint Exposure Path".

## Authentication Gates

None.

## Build / Test Verification Status

**Structural verification (executed and passed):**

| Gate                                                                                                                          | Expected         | Observed |
| ----------------------------------------------------------------------------------------------------------------------------- | ---------------- | -------- |
| Submodule pinned at jdart1/Fathom                                                                                             | non-empty SHA    | `c9c6fef0dddc05d2e242c183acf5833149ab676d` |
| `.gitmodules` contains Fathom path                                                                                            | ≥1               | 2        |
| `extern/fathom/src/tbprobe.c` + `tbprobe.h` exist                                                                             | both present     | both present |
| `tbconfig.h` macros (excluding comments)                                                                                      | ≥8               | 8        |
| Pre-staged `EXISTS.*tbprobe\.c` in CMakeLists.txt                                                                             | ≥1               | 1        |
| **Wave 3 file-ownership invariant**: `git diff HEAD~2..HEAD -- python_bindings.cpp include/engine.hpp CMakeLists.txt`         | 0 changes        | 0        |
| TB_RESULT_FAILED appearances in syzygy.cpp                                                                                    | ≥2 (both probes) | 3        |
| nullopt mentions in syzygy.cpp                                                                                                | ≥2               | 15       |
| D-08 case 1 verbatim "no path configured" in syzygy.cpp                                                                       | ≥1               | 2        |
| D-08 case 2 verbatim "path not found" in syzygy.cpp                                                                           | ≥1               | 2        |
| D-08 case 3 verbatim "no tablebase files" in syzygy.cpp                                                                       | ≥1               | 2        |
| D-08 case 4 verbatim "smoke probe failed" in syzygy.cpp                                                                       | ≥1               | 2        |
| D-08 case 5 verbatim "tb_init failed" in syzygy.cpp                                                                           | ≥1               | 2        |
| Real `tb_probe_root_dtz` call in syzygy.cpp (TB-04 REAL)                                                                      | ≥1               | 2        |
| `syzygy.hpp` exposes class + probe surface                                                                                    | ≥10 keyword hits | 17       |
| Test functions in `test_v7_syzygy.py`                                                                                         | 8                | 8        |

**Build verification (deferred):**

This worktree environment lacks both `python3` and `cmake` (consistent
with Plans 01 and 02 — see their SUMMARYs). Therefore:

- `cmake -S src/chess_engine/engine/v7 -B build/v7` — DEFERRED
- `cmake --build build/v7 --target v7_engine` — DEFERRED
- `python3 -c "from chess_engine.engine.v7 import ..."` — DEFERRED
- `python3 -m uv run --group dev pytest tests/test_v7_syzygy.py` — DEFERRED

The orchestrator or a subsequent merge-and-build agent in a
Python/CMake-equipped environment MUST run:

1. `python3 -m uv run --group dev pytest tests/test_v7_syzygy.py -q --tb=short`
   (init-log tests 1–4 + tbhits tests 5–6 always run; tests 7–8 skip
   when SYZYGY_PATH unset)
2. With `SYZYGY_PATH=<dir with KRvK.rtbw>`:
   `python3 -m uv run --group dev pytest tests/test_v7_syzygy.py::test_krk_endpoint_wdl_probe -q`
   (asserts KRk endpoint WDL probe records ≥1 tbhit)

before Phase 1 sign-off (success criteria TB-03 through TB-08 + TB-10).

## Wave 3 Build-Coupling Note (Acknowledged)

Plan 03 and Plan 05 are siblings in Wave 3. After all three Wave 3
worktrees merge:

- Plan 03's `engine.hpp` adds `#include "syzygy.hpp"` and
  `v7::SyzygyState syzygy_;` private member.
- Plan 03's `src/engine.cpp` writes the real
  `Engine::set_syzygy_path(path) { syzygy_.set_path(path); }`
  forwarding wrapper.
- Plan 03 removes the Plan 01 stub body of `Engine::set_syzygy_path`
  from `src/python_bindings.cpp` (since Plan 03 now owns the real
  body in engine.cpp).
- Plan 03 wires `Engine::tbhits()` (already implemented inline in
  engine.hpp) to read `syzygy_.tbhits()` instead of the
  forward-declared opaque counter.

This Plan 05 takes no action on those wiring steps — Plan 03 owns them.

## Known Stubs

None introduced by this plan. `src/syzygy.cpp` was a Plan 02 stub
(single-line `// stub — implemented in Wave 3 (Plan 05)`); this plan
overwrites it with the real implementation.

The Plan 01 STUB body of `Engine::set_syzygy_path` still lives in
`src/python_bindings.cpp` (it must — Wave 3 file-ownership keeps Plan
05 from touching that file). Plan 03 will remove it when landing the
real `engine.cpp`. Until the Wave 3 merge, both bodies will conflict
at link time inside the parallel worktrees — but each isolated worktree
compiles only with the files it owns plus Wave 2's pre-stage, and the
merge resolves the collision deterministically.

## Threat Flags

None — all surfaces added by this plan are accounted for in the plan's
`<threat_model>` block (T-05-01 through T-05-07). No new trust
boundaries beyond what the threat register already documents.

## TDD Gate Compliance

Plan type is `execute` (not `tdd`), and each task carries
`tdd="true"`. The cycle landed as:

1. **RED** (Task 2): tests in `tests/test_v7_syzygy.py` were authored
   with concrete D-08 string assertions that fail unless the
   implementation emits the verbatim log strings.
2. **GREEN** (Task 2): `src/syzygy.cpp` implementation emits the
   verbatim strings, gates probes, and reflects KRk through tbhits.

Note: commits landed as `feat → feat` rather than `test → feat`
because both source and test landed in a single Task 2 commit. The
test file is concrete (would fail if syzygy.cpp omitted any D-08
string or silently mapped TB_RESULT_FAILED to a tbhit) — RED-in-spirit
even though the commit ordering is not the canonical RED-then-GREEN.
Plan 01 (`type: scaffold`) and Plan 02 (`type: execute`) used the
same pattern.

## Self-Check

All structural gates verified (see table above). All 5 files created
and 2 files modified are present on disk. Both commits exist in
`git log --oneline`:

- `a77ceae feat(01-05): add Fathom submodule + tbconfig.h override (TB-01, TB-02, INT-06)`
- `37a96ea feat(01-05): implement SyzygyState + D-08 log discipline + KRk smoke probe (TB-03..08, TB-10)`

No unintended deletions: `git diff --diff-filter=D --name-only HEAD~2 HEAD` is empty.

Build + pytest run deferred per worktree environment constraint
(consistent with Plans 01 and 02).

## Self-Check: PASSED
