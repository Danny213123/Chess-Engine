---
phase: "01"
plan: "01"
subsystem: v7-engine
tags: [scaffold, pybind11, gil-release, search-info]
requires:
  - V6 build pattern (src/chess_engine/engine/v6/CMakeLists.txt, native_build.py)
  - pybind11 v2.12.0 (FetchContent)
  - CMake >= 3.15, C++17 compiler
provides:
  - chess_engine.engine.v7 package (adapter, build driver, CMakeLists)
  - v7::Engine C++ class with std::atomic stop_flag_ / tbhits_ / nodes_
  - v7_engine pybind11 module (PYBIND11_MODULE entry point)
  - v7_uci standalone binary (minimal UCI handshake)
  - find_best_move adapter signature compatible with GameManager
affects:
  - .gitignore (V7 build artifacts block added)
  - tests/ (test_v7_engine.py, test_v7_bindings.py)
tech-stack:
  added:
    - C++17 pybind11 v2.12.0 (FetchContent from existing V6 pattern)
  patterns:
    - Stateful pybind11 class binding (vs V6 free-function)
    - py::call_guard<py::gil_scoped_release>() on long-running methods
    - std::atomic<bool> stop flag observable across the GIL boundary
    - Module-singleton Engine via _get_or_create_engine() lazy init
key-files:
  created:
    - src/chess_engine/engine/v7/__init__.py
    - src/chess_engine/engine/v7/chess_algorithm.py
    - src/chess_engine/engine/v7/native_build.py
    - src/chess_engine/engine/v7/CMakeLists.txt
    - src/chess_engine/engine/v7/include/engine.hpp
    - src/chess_engine/engine/v7/src/python_bindings.cpp
    - src/chess_engine/engine/v7/src/uci_main.cpp
    - tests/test_v7_engine.py
    - tests/test_v7_bindings.py
  modified:
    - .gitignore
decisions:
  - V7 ships its own SearchInfo pattern (C++ atomic stop flag) instead of
    consuming src/chess_engine/core/search_info.py. The Python adapter's
    find_best_move(..., search_info=None) parameter is accepted for
    adapter-contract compatibility but NOT polled — cancellation flows via
    stop_engine() flipping engine.stop() (FOUND-04 closure).
  - GIL released on Engine.search / set_syzygy_path / perft_entry; NOT
    released on Engine.stop (single atomic write, must be cheap to call
    from another Python thread already holding the GIL).
  - V7 declines OpeningBook for the phase 1 smoke milestone (research
    Pattern note); plays from startpos with no book.
  - CMakeLists project declared with `LANGUAGES CXX C` from day one so
    plan 05 can drop in Fathom's C tbprobe.c without re-declaring.
  - SUMMARY.md NOT updating STATE.md / ROADMAP.md per parallel-worktree
    orchestrator contract (orchestrator owns those writes after wave
    completes).
metrics:
  completed: 2026-05-16
  duration: single-wave parallel execution
  tasks: 2
  files-created: 9
  files-modified: 1
---

# Phase 1 Plan 1: V7 Skeleton + pybind11 Binding Contract Summary

Scaffold the V7 C++17 pybind11 engine with a stateful Engine class that
closes V6's silently-ignored-SearchInfo bug (FOUND-04) by exposing a C++
std::atomic stop flag observable from another Python thread without
deadlocking on the GIL (FOUND-05).

## What Was Built

### Task 1 — V7 package + build driver (commit `1c411c2`)

- `src/chess_engine/engine/v7/__init__.py` — package marker
- `src/chess_engine/engine/v7/chess_algorithm.py` — Python adapter with
  module-singleton `_engine`, `find_best_move(..., search_info=None)`
  matching the project-wide adapter contract (FOUND-03), `stop_engine()`
  flipping the C++ atomic, `new_game()` resetting per-game state,
  `ensure_available(auto_build=False)` for on-demand CMake builds (INT-09).
  Drops V6's OpeningBook wiring (research Pattern note).
- `src/chess_engine/engine/v7/native_build.py` — V7BuildError +
  V7BuildResult dataclass; `build_v7_native(force=False)` driving CMake
  configure + build; `find_packaged_module()` for fast-path module
  discovery; Fathom partial-checkout diagnostic surfacing
  `"Run 'git submodule update --init --recursive' first..."` ready for
  plan 05.
- `src/chess_engine/engine/v7/CMakeLists.txt` — `project(v7_engine
  LANGUAGES CXX C)` (C added for plan 05's Fathom tbprobe.c),
  `FetchContent_Declare(pybind11 GIT_TAG v2.12.0)`, V7_SOURCES with 4
  explicit `TODO(plan-NN):` markers for plans 02/03/04/05 to append their
  .cpp files. `pybind11_add_module(v7_engine MODULE ${V7_SOURCES})` and
  `add_executable(v7_uci src/uci_main.cpp)`. Optional OpenMP block
  mirrored verbatim from V6.
- `.gitignore` — appended `# V7 build artifacts` block (coeffs.cpp,
  build/, v7_engine*.so/pyd/dylib, v7_uci, v7_uci.exe).
- `tests/test_v7_engine.py` — module-scoped fixture
  `v7_native_engine` calling `ensure_available(auto_build=True)`; skips
  the module gracefully when the build environment is not present
  (matches V6 fixture pattern in `tests/test_v6_native.py`).

### Task 2 — Engine binding contract + UCI handshake stub (commit `1ef8f85`)

- `src/chess_engine/engine/v7/include/engine.hpp` — `v7::Engine` class
  with `std::atomic<bool> stop_flag_`, `std::atomic<uint64_t> tbhits_`,
  `std::atomic<uint64_t> nodes_`; `SearchResult` struct with
  best_move/score/depth/nodes/nps; forward-declared `TT`, `Board`,
  `SyzygyState` so engine.hpp does not pull in plan 02/05 subsystem
  headers that do not exist yet; free-function `perft_entry()`
  declaration.
- `src/chess_engine/engine/v7/src/python_bindings.cpp` — REWRITE of
  V6's free-function pattern into a stateful `py::class_<v7::Engine>`.
  Three sites carry `py::call_guard<py::gil_scoped_release>()`: `search`,
  `set_syzygy_path`, `perft_entry`. `stop()` intentionally has NO
  call_guard (single atomic write, must be cheap to call from a Python
  thread already holding the GIL). Stub bodies live in the same TU for
  plan 01 only — plans 02/03/05 will move them into their own .cpp
  files and append to V7_SOURCES. `set_syzygy_path` emits D-08 verbatim
  log strings (`[v7] syzygy: no path configured; tbhits will be 0` /
  `[v7] syzygy: path not found: <p>; tbhits will be 0`).
- `src/chess_engine/engine/v7/src/uci_main.cpp` — minimal handshake
  (`uci` → `id name V7` + `id author ...` + `uciok`; `isready` →
  `readyok`; `quit` → exit 0; other commands → `info string V7 phase 1
  stub - command ignored: <line>`). Satisfies FOUND-07 existence check
  and Phase 2 fastchess prereq. Plan 06 expands with `position`, `go`,
  `stop`, `ucinewgame`.
- `tests/test_v7_bindings.py` — 8 tests covering FOUND-01..FOUND-07 +
  INT-09: layout, build, import, adapter signature, GIL release,
  cancellation latency, v7_uci handshake, auto-build flow. Local
  fixture mirrors `tests/test_v7_engine.py` so this file is
  self-contained (V6-style per-test-file fixture pattern).

## Engine Class Contract (locked for plans 02–06)

```cpp
namespace v7 {
struct SearchResult { int best_move; int score; int depth;
                      uint64_t nodes; int nps; };
class Engine {
public:
  void set_syzygy_path(const std::string&);
  void new_game();
  SearchResult search(const std::string& fen, int depth, int time_ms);
  void stop();                       // atomic, NO GIL release on binding
  uint64_t tbhits() const;
  uint64_t nodes() const;
private:
  std::atomic<bool>     stop_flag_;
  std::atomic<uint64_t> tbhits_;
  std::atomic<uint64_t> nodes_;
};
uint64_t perft_entry(const std::string&, int);
}
```

Plans 02/03/05 fill the bodies behind this surface. Callers (Python
adapter, GameManager dispatch, UCI loop) MUST NOT need changes when
those plans land — that is the point of locking the contract now.

## Decisions Made

1. **SearchInfo handling.** V7 closes FOUND-04 with a C++-side atomic
   stop flag, not by polling Python's `SearchInfo.stop_requested`. The
   adapter still accepts `search_info=None` for contract parity. Wiring
   `GameManager.stop_search()` → `v7.chess_algorithm.stop_engine()`
   lands in plan 06 (UCI loop + dispatch).
2. **stop() does NOT release the GIL.** Releasing on a single
   `std::atomic` store would add a round-trip release/acquire cycle for
   no benefit; the search thread already released the GIL inside
   `search()`, so the calling thread can write the stop flag while still
   holding the GIL (FOUND-05 + Pitfall #11).
3. **Stub bodies live in `python_bindings.cpp` for plan 01 only.** The
   4 TODO markers in `CMakeLists.txt` document exactly where plans
   02/03/04/05 append their real .cpp files — the binding TU does not
   become a god-object as the engine grows.
4. **V7 declines the OpeningBook for phase 1.** Research note;
   re-enabling is a deliberate future-plan decision tracked inline in
   `chess_algorithm.py`.
5. **CMake `LANGUAGES CXX C` from day one.** Plan 05's Fathom drop-in
   (`extern/fathom/src/tbprobe.c`) needs C; declaring it now keeps the
   plan-05 diff small.

## Deviations from Plan

None — plan executed as written. The known_correction documented in
PLAN.md (V7 ships its own SearchInfo pattern instead of creating
`src/chess_engine/core/search_info.py`) is the plan-time decision, not
an execution-time deviation.

## Consumer Notes for Plans 02–06

- **Plan 02 (board / movegen / magic / tt):** Add `board.cpp`,
  `movegen.cpp`, `magic.cpp`, `tt.cpp` under V7_SOURCES at the
  `# TODO(plan-02):` marker in CMakeLists.txt. Populate `Engine::board_`
  and `Engine::tt_` private members (currently commented out in
  engine.hpp). Real `perft_entry()` body replaces the `return 0;` stub.
- **Plan 03 (search):** Add `search.cpp` at the `# TODO(plan-03):`
  marker. Real iterative deepening body replaces `Engine::search`'s
  `nodes_.fetch_add(1)` stub. MUST poll `stop_flag_.load(memory_order_
  relaxed)` between plies. The `test_gil_released` /
  `test_cancellation_latency` bounds in `tests/test_v7_bindings.py`
  become meaningful — DO NOT WEAKEN them when the real body lands.
- **Plan 04 (eval + Texel coeffs):** Add `eval.cpp` + generated
  `src/coeffs.cpp` (gitignored) at the `# TODO(plan-04):` marker.
- **Plan 05 (Syzygy / Fathom):** Add `syzygy.cpp` and Fathom
  subdirectory at the `# TODO(plan-05):` marker. Real `set_syzygy_path`
  body replaces the D-08 stub but MUST keep the verbatim log strings
  (callers and CONCERNS.md test on them).
- **Plan 06 (UCI loop + GameManager dispatch):** Expand `uci_main.cpp`
  to handle `position`, `go depth N`, `go movetime MS`, `stop`,
  `ucinewgame`. Wire `GameManager.stop_search()` →
  `v7.chess_algorithm.stop_engine()` in the engine-string ladder.

## Build / Platform Notes

- Environment limitation: the executor environment for this plan had
  neither Python nor CMake installed (`python3` → "not found", `cmake`
  → "not found"). Verification of plan 01 was therefore structural
  (file presence, regex-level binding contract checks against
  `python_bindings.cpp`: exactly 3 `py::call_guard<py::gil_scoped_
  release>` occurrences, `.def("stop", &v7::Engine::stop)` matches the
  PLAN-mandated whitespace, `id name V7` present in `uci_main.cpp`).
  The build + pytest run will execute when the orchestrator merges the
  worktree into the main repo and runs in a Python/CMake-equipped env.
- Cross-platform build paths assumed by `native_build._find_built_
  module()`: `build/Release` (Windows MSBuild multi-config),
  `build/RelWithDebInfo`, `build/Debug`, `build/`, `V7_DIR/` (packaged
  module fast-path). Mirrors V6 search order.

## Known Stubs

These are intentional plan-01 stubs called out in PLAN.md and
documented inline so the verifier and downstream plans can see them:

- `Engine::search` returns `SearchResult{}` with `MOVE_NONE` and bumps
  `nodes_` by 1 (enough to give `test_gil_released` observable work
  without depending on real movegen). Plan 03 lands the real body.
- `Engine::set_syzygy_path` logs D-08 stub strings only; plan 05 adds
  real filesystem checks + `tb_init` + KRk smoke probe.
- `perft_entry` returns 0; plan 02 wires the real perft backed by the
  ported movegen.
- `uci_main.cpp` only answers `uci`, `isready`, `quit`; all other
  commands respond with the `info string V7 phase 1 stub ...`
  acknowledgement. Plan 06 implements the full loop.
- `chess_algorithm.find_best_move` raises `RuntimeError` if
  `MOVE_NONE` is returned — surfaces the missing plan-03 implementation
  loudly rather than silently picking the first legal move.

All stubs are documented inline with `plan 0N` references so a future
reader can grep for the plan number that resolves each one.

## TDD Gate Compliance

Plan 01-01 frontmatter is `type: scaffold` (not `tdd`); no RED/GREEN
gate sequence is required. Tests in `tests/test_v7_bindings.py` and
`tests/test_v7_engine.py` were authored alongside the scaffold to lock
the binding contract for plans 02–06.

## Self-Check: PASSED

- All 9 created files present on disk (verified via `[ -f ]` per file)
- `.planning/phases/01-skeleton-smoke/01-01-SUMMARY.md` present
- Task 1 commit `1c411c2` present in `git log --oneline --all`
- Task 2 commit `1ef8f85` present in `git log --oneline --all`
- No unintended file deletions in either commit
  (`git diff --diff-filter=D HEAD~1 HEAD` empty)
