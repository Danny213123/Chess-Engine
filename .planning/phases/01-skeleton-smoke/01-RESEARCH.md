# Phase 1: Skeleton + Smoke - Research

**Researched:** 2026-05-15
**Domain:** Native C++17 pybind11 chess engine (forked from V6) — board/movegen/search/eval/Syzygy scaffolding for a single legal smoke game vs V6
**Confidence:** HIGH (codebase patterns), MEDIUM (Pesto/Fathom external references — values cited from public sources but not freshly fetched this session)

## Summary

Phase 1 forks V6's existing native pybind11 module wholesale into `src/chess_engine/engine/v7/`, with three structural changes: (1) the binding wires the Python-side `SearchInfo` cancellation through to the C++ search (closing V6's silently-ignored-arg bug confirmed in `src/chess_engine/engine/v6/src/python_bindings.cpp`), (2) eval coefficients are externalized to a `coeffs.json` file consumed by a CMake-generated `coeffs.cpp` so Phase 4 Texel has stable tunable handles, and (3) Fathom (jdart1) is added as a git submodule for Syzygy probing with always-log-never-fail init semantics. Build groups A1 (skeleton + binding) → A2 (board/movegen/zobrist/perft parity) precede the parallelizable B1 (sequential PVS search hardened: mate-TT, repetition, time mgmt) ∥ B2 (11 eval terms scaffolded with Pesto-baseline values) ∥ B3 (Fathom integration, root + in-search probes, init-time log discipline), all merging into C1 (GameManager dispatch + React dropdown + CLI subcommand + smoke test).

V6 already implements PVS (search.cpp:249-257), iterative deepening with aspiration windows (lines 292-352), and per-node `info.stopped` polling (lines 37, 110), which V7 inherits for free. The cancellation gap is exclusively at the Python↔C++ boundary, not in the search loop. The single largest risk is Pitfall #11 (GIL not released) — `py::call_guard<py::gil_scoped_release>()` MUST wrap the search-entry binding from day one, both because Lazy SMP in Phase 4 silently degrades to GIL-serialized otherwise AND because cancellation from another thread requires the search thread to not hold the GIL.

**Primary recommendation:** Fork V6 verbatim (movegen, magic, zobrist, board, TT, eval, search, CMake, native_build), then surgically modify (a) `python_bindings.cpp` to expose a stateful `Engine` class with `search(fen, depth, time_ms)` + `stop()` methods wrapped in `py::gil_scoped_release`, (b) `eval.cpp` to read every weight from a generated `coeffs.cpp` translation unit instead of `static const int`, (c) `search.cpp` to add the three pre-C1 must-fixes (mate-TT ply correction, in-tree repetition detection, time-management safety margin with re-search cap), (d) `CMakeLists.txt` to add the `tools/gen_coeffs.py` custom command and the Fathom subdirectory, (e) `__init__.py` adapter to call `algo_v7.stop()` from the GameManager `stop_search` path. Everything else is a rename V6→V7.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Initial Eval Coefficients**
- **D-01:** V7's eval coefficients in `coeffs.json` initialize from **public Pesto/Stockfish-baseline values**, not lifted from V6. Pesto provides PSTs and tapered-eval material; for terms beyond PSTs (king-safety attack table, mobility tables, pawn-structure terms, threats, bishop pair, tempo) use documented public starting values where they exist (Pesto-derived where available) or modest hand-set values clearly marked `# initial; will be tuned Phase 4` in `coeffs.json`.
- **D-02:** This makes V7 the "neutral seed" candidate in Phase 4's TUNE-08 multi-seed tuning. The V6-equivalent seed (also referenced in TUNE-08) is left for Phase 4 to construct separately if desired — it is NOT V7's Phase 1 starting state.
- **D-03:** Smoke games in Phase 1 may look weaker than V6 because Pesto-baseline ≠ tuned. Phase 1 milestone is *legal play*, not *strong play*.

**Smoke Milestone Scope**
- **D-04:** Phase 1 C1 smoke milestone is **a single game, V7 as white, fixed depth, vs V6**. Must finish legally with no crashes, illegal moves, or unhandled exceptions; cancellation must work mid-search (FOUND-04). Suggested depth: same as V6's default (depth 6).
- **D-05:** V7-as-black, time-management exercise (SRCH-15 in real games), and back-to-back game stability are **not** Phase 1 acceptance criteria.
- **D-06:** SRCH-15 (time management) still needs **unit tests** in Phase 1.

**Syzygy Missing-Path Behavior (init-time only)**
- **D-07:** Always log to stderr, never fail at engine init.
- **D-08:** Init-time log lines (verbatim):
  - `syzygyPath` unset → `[v7] syzygy: no path configured; tbhits will be 0`
  - Path set, directory missing → `[v7] syzygy: path not found: <path>; tbhits will be 0`
  - Path set, directory empty → `[v7] syzygy: no tablebase files at <path>; tbhits will be 0`
  - Path set, KRk smoke probe fails → `[v7] syzygy: smoke probe failed (corrupt or wrong format) at <path>; tbhits will be 0`
- **D-09:** TB-06 (in-search probe failures must NOT silently become draws) is orthogonal and unaffected.

**`coeffs.cpp` Codegen Mechanics**
- **D-10:** Codegen at `tools/gen_coeffs.py` (Python).
- **D-11:** Invoked via CMake custom command depending on `coeffs.json` mtime.
- **D-12:** `coeffs.cpp` is generated, NOT committed (`.gitignore`). `coeffs.json` is the single source of truth.
- **D-13:** Codegen output deterministic (sorted keys, fixed indent, LF line endings).

### Claude's Discretion
None explicitly enumerated — all key choices locked in CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)
- V6 SearchInfo bug backport (V6 stays broken; V7 fixes it for itself only)
- Logging abstraction migration (`print()` to stderr remains acceptable for Phase 1)
- Multi-seed tuning V6-equivalent seed (Phase 4 TUNE-08)
- Time-management end-to-end exercise (Phase 2 gauntlet)
- Back-to-back game stability (Phase 2 gauntlet)
- V7-as-black smoke (Phase 2 gauntlet)
- `coeffs.cpp` commit-and-CI-verify hybrid (rejected option)
</user_constraints>

<phase_requirements>
## Phase Requirements

42 requirement IDs scoped to Phase 1, mapped to research support and build group.

| ID | Description | Build Group | Research Support |
|----|-------------|-------------|------------------|
| FOUND-01 | V7 module exists at `src/chess_engine/engine/v7/` mirroring V6 layout | A1 | V6 layout is the template — fork wholesale; see "V7 Project Structure" below |
| FOUND-02 | CMake build via `FetchContent` of pybind11 v2.12.0 (matches V6) | A1 | V6 `CMakeLists.txt` is the template; CMake recipe section below shows V7 additions |
| FOUND-03 | Adapter exports `find_best_move(game_state, valid_moves, engine, search_info)` | A1, C1 | V6 `chess_algorithm.py` adapter pattern (lines 108-189) — V7 mirrors but PASSES search_info |
| FOUND-04 | Cancellation: V7 binding accepts `SearchInfo` and search polls it | A1, B1 | **V6 BUG CONFIRMED** — `python_bindings.cpp` signature has no SearchInfo arg; V7 must expose stateful `Engine` class with `stop()` method. See "Cross-Cutting: SearchInfo Wiring" |
| FOUND-05 | `py::call_guard<py::gil_scoped_release>()` on search binding from day one | A1 | Pitfall #11 — wraps `Engine.search(...)` in PYBIND11_MODULE block |
| FOUND-06 | Perft parity vs V6 to depth 6 on Kiwipete + 4 standard positions | A2 | Test corpus + expected node counts in "Perft Test Corpus" section |
| FOUND-07 | `v7_uci` standalone executable for fastchess gauntlet (Phase 2 prereq) | A1 | CMake `add_executable(v7_uci ...)` target alongside the pybind11 module |
| SRCH-01 | Iterative deepening 1..maxDepth with PV propagation | B1 | V6 `search.cpp` lines 292-352 already implements; V7 inherits |
| SRCH-02 | Aspiration windows ±25cp, widen on fail-high/low, **with re-search cap** | B1 | V6 has aspiration (lines 316-320) but UNBOUNDED re-search — V7 must add cap (e.g., 4 widenings then full window) |
| SRCH-13 | Mate-score TT correctness (`score_to_tt` / `score_from_tt` ply correction) | B1 | Pitfall #1 — see "Cross-Cutting: Mate-Score TT" pattern |
| SRCH-14 | Repetition detection in tree (not just root) + 50-move TT cutoff | B1 | Pitfall #7 — see "Cross-Cutting: Repetition Detection" pattern |
| SRCH-15 | Time management with ≥10% safety margin; unit tests required | B1 | Pitfall #33 — see "Cross-Cutting: Time Management" pattern |
| EVAL-01..11 | All 11 eval terms structurally present in `coeffs.json` | B2 | See "B2: Eval Scaffolding" — full term inventory + Pesto values |
| TB-01 | Fathom (jdart1) added as git submodule under `extern/fathom/` | B3 | Submodule URL: `https://github.com/jdart1/Fathom.git` (MIT) |
| TB-02 | `tbconfig.h` override shares V7's magic-bitboard attack tables | B3 | See "B3: Fathom Integration" — override file contents |
| TB-03 | `tb_init(syzygyPath)` called at engine construction | B3 | Per D-07/D-08 — init log discipline section |
| TB-04 | `tb_probe_root_dtz` / `tb_probe_root_wdl` at root for in-range positions | B3 | Fathom API surface section |
| TB-05 | `tb_probe_wdl` in search for ≥7-piece nodes | B3 | Fathom API surface section |
| TB-06 | In-search probe failures hard-error or are flagged — NOT silently DRAW | B3 | D-09 invariant; see "B3: TB Probe Failure Handling" |
| TB-07 | `tbhits` counter exposed via search stats | B3 | Engine class exposes `tbhits()` method to Python |
| TB-08 | `syzygyMaxPieces` config (default 6) limits max-piece probes | B3, C1 | INT-04 — `cli/src/config.js` keys |
| TB-09 | Optional Syzygy download script (3-4-5 men ~1GB) | C1 | INT-05 — `cli/src/index.js` `syzygy download` subcommand |
| TB-10 | KRk smoke probe at init validates files load (per D-08) | B3 | Init-time check; see "B3: TB Smoke Probe" |
| INT-01 | GameManager 4-line edit dispatches V7 | C1 | `game_manager.py` — see "INT-01 Diff" section |
| INT-02 | React dropdown adds V7 to both white + black `<select>` | C1 | `client/src/App.jsx` lines 408 + 423 — add `<option value="v7">` |
| INT-03 | UI build-warning copy mentions V7 | C1 | `App.jsx` line 235-237 — extend `if (ver === "v6" \|\| ver === "v7")` branch |
| INT-04 | CLI config keys: `v7Built`, `syzygyPath`, `syzygyMaxPieces` | C1 | `cli/src/config.js` DEFAULT_CONFIG additions |
| INT-05 | CLI subcommands: `build v7`, `syzygy download` | C1 | `cli/src/index.js` — mirror existing `buildV6()` pattern |
| INT-06 | `.gitmodules` adds Fathom; `.gitignore` adds V7 build artifacts + `coeffs.cpp` | A1, B3 | Per D-12 + TB-01 |
| INT-07 | `tests/test_v7_engine.py` covers smoke + perft + cancel + NPS sentinel | C1 | Validation Architecture section below |
| INT-08 | V1-V6 dispatch unchanged after V7 added (regression suite green) | C1 | Existing `tests/` runs unmodified |
| INT-09 | First-import auto-build mirrors V6 pattern | A1 | V6 `chess_algorithm.py` `ensure_available(auto_build=True)` is the template |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

These directives bind ALL plans for Phase 1 — planner and executor must verify compliance:

- **MUST** be C++17 pybind11 module mirroring V6 build pattern (no language additions)
- **MUST** keep V7 NPS within ~20% of V6 NPS on same hardware (build check enforces)
- **MUST NOT** modify V1-V6 engines (they continue to work unchanged)
- **MUST NOT** introduce new threading abstraction in FastAPI server layer (Lazy SMP only, deferred to Phase 4)
- **MUST** honor existing `SearchInfo` cooperative cancellation contract
- **MUST NOT** bundle Syzygy tablebases — optional download script only
- **MUST NOT** modify frontend beyond adding V7 to engine dropdown
- **MUST NOT** use Texel data sources other than Zurichess `quiet-labeled.epd` (Phase 4 concern, but coeffs.json header should cite this)
- **GSD workflow:** All Edit/Write must go through a GSD command — Phase 1 plans must be created via `/gsd-plan-phase 1`

**Style/tooling notes from CLAUDE.md:**
- No formatter, linter, or type checker configured for Python — V7 Python code follows existing project conventions (snake_case files, PascalCase classes)
- `print()`-as-stderr is the established logging pattern (acceptable for V7 init notices per D-08)
- Sparse comments preferred; comment WHY not WHAT (especially for bitboard hot loops)

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Move generation, board, zobrist, magic | C++ Domain Core | — | Hot path; bitboard ops; forked from V6 |
| Search (PVS, ID, aspiration, mate-TT, repetition, time mgmt) | C++ Domain Core | — | Hot path; per-node `stopped` polling |
| Eval coefficients (storage) | Generated C++ TU (`coeffs.cpp`) | JSON Source (`coeffs.json`) | Single source of truth = JSON; codegen mechanically extends |
| Eval terms (computation) | C++ Domain Core | — | Hot path; structured for Phase 4 sparse extraction |
| Syzygy probing | C++ Domain Core (Fathom) | — | Hot path during in-search probes |
| `SearchInfo` cancellation | Python `core/` | C++ binding boundary | Python sets stop, C++ search polls atomic — must cross GIL safely |
| GameManager dispatch | Python `server/` | — | INT-01 4-line edit; ladder pattern preserved (anti-pattern deferred per V2-REF-01) |
| Engine selection UI | React `client/` | — | INT-02/03 dropdown options + warning copy |
| First-import auto-build | Python adapter (`v7/__init__.py` + `chess_algorithm.py`) | Node CLI | Mirrors V6 pattern; CLI's `build v7` is the explicit form |
| Syzygy download | Node CLI | — | Out-of-process; INT-05 `syzygy download` subcommand |
| Coefficient codegen | Build-time Python (`tools/gen_coeffs.py`) | CMake custom command | Runs during build, not at runtime |
| Test infrastructure | Python `pytest` | — | `tests/test_v7_engine.py` per existing project conventions |

**Tier sanity check for planner:** Any task placing search logic in Python, eval coefficients in C++ source, or threading primitives in the FastAPI layer should be flagged for tier-correctness review.

## Standard Stack

### Core (inherited unchanged from V6)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pybind11 | v2.12.0 | C++↔Python binding | Already pinned in V6 `CMakeLists.txt` via `FetchContent`; matches the project's existing native pattern [VERIFIED: codebase] |
| CMake | ≥3.15 | Build system | V6 minimum [VERIFIED: codebase] |
| C++17 | — | Language standard | V6 standard [VERIFIED: codebase] |
| Python | 3.12 (3.10+ ok) | Build driver, codegen, adapter | `.python-version` pin [VERIFIED: codebase] |
| OpenMP | optional | V6 uses for parallel search | V7 Phase 1 single-threaded — OpenMP not required this phase, but link if found (Phase 4 may use, or not — Lazy SMP via `std::thread`) [VERIFIED: codebase] |

### New for V7 (Phase 1)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Fathom (jdart1 fork) | latest commit on `master` (pinned via submodule SHA) | Syzygy WDL/DTZ probing | Industry-standard probe library; MIT; supports `tbconfig.h` override to share host engine's attack tables (avoids 2x memory) [CITED: github.com/jdart1/Fathom README] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Fathom (jdart1) | Original basil00/Fathom | jdart1 fork is more actively maintained, has bug fixes; jdart1 chosen per STACK.md research |
| Generated `coeffs.cpp` | Hand-maintained C++ constants | Generated approach is required for Phase 4 Texel pipeline (TUNE-09); hand-maintained doesn't scale to 700+ coefficients |
| Stateful `Engine` class binding | Free-function binding (V6's pattern) | Stateful needed for `stop()` method (FOUND-04) and per-instance Syzygy/TT state |

**Installation:**
```bash
# Fathom as submodule (TB-01)
git submodule add https://github.com/jdart1/Fathom.git src/chess_engine/engine/v7/extern/fathom
git submodule update --init --recursive
```

**Version verification:** pybind11 v2.12.0 is pinned in V6's `CMakeLists.txt`; V7 inherits the exact same pin to avoid ABI drift between sibling engines loaded into the same Python process. Fathom should be pinned to a specific submodule SHA at the time of A1 work (verify the chosen SHA compiles cleanly on Windows MSVC, the historically-fragile target — see Pitfall #41).

## V7 Project Structure

```
src/chess_engine/engine/v7/
├── __init__.py                      # Loader + adapter (mirrors V6 chess_algorithm.py)
├── native_build.py                  # CMake driver (rename of V6's; V6→V7)
├── CMakeLists.txt                   # FetchContent(pybind11) + add_subdirectory(extern/fathom) + custom_command(coeffs)
├── coeffs.json                      # SOURCE OF TRUTH for eval values (D-12)
├── tools/
│   └── gen_coeffs.py                # Codegen: coeffs.json → coeffs.cpp (D-10)
├── include/
│   ├── board.hpp                    # Forked from v6
│   ├── movegen.hpp                  # Forked from v6
│   ├── magic.hpp                    # Forked from v6
│   ├── zobrist.hpp                  # Forked from v6
│   ├── tt.hpp                       # Forked from v6 (single-threaded; Phase 3 replaces with lockless)
│   ├── eval.hpp                     # Forked from v6, MODIFIED: reads weights from extern coeffs
│   ├── search.hpp                   # Forked from v6, MODIFIED: SearchInfo wired
│   ├── coeffs.hpp                   # Declares extern arrays defined in generated coeffs.cpp
│   ├── syzygy.hpp                   # NEW: Fathom probe wrappers + init logging
│   └── tbconfig.h                   # NEW (TB-02): override file shared with Fathom build
├── src/
│   ├── board.cpp, movegen.cpp, magic.cpp, zobrist.cpp, tt.cpp  # Forked from v6
│   ├── eval.cpp                     # MODIFIED: uses coeffs::* arrays
│   ├── search.cpp                   # MODIFIED: mate-TT, repetition, time-mgmt, atomic stop
│   ├── syzygy.cpp                   # NEW: probe wrappers, init log discipline (D-08)
│   ├── python_bindings.cpp          # MODIFIED: stateful Engine class + GIL release
│   ├── uci_main.cpp                 # NEW: standalone v7_uci binary entry point (FOUND-07)
│   └── coeffs.cpp                   # GENERATED — NOT COMMITTED (D-12)
├── extern/
│   └── fathom/                      # GIT SUBMODULE (TB-01)
└── overrides/                       # Reserved for any Fathom build flag overrides
```

**Files added to `.gitignore` for V7:**
```
src/chess_engine/engine/v7/src/coeffs.cpp
src/chess_engine/engine/v7/build/
src/chess_engine/engine/v7/v7_engine*.so
src/chess_engine/engine/v7/v7_engine*.pyd
src/chess_engine/engine/v7/v7_engine*.dylib
src/chess_engine/engine/v7/v7_uci
src/chess_engine/engine/v7/v7_uci.exe
```

## A1: Skeleton + Build + Bindings + GIL

**Goal:** V7 module compiles on Win/Linux/macOS, loads in Python, exposes a stateful `Engine` class with `search(...)` and `stop()` methods, and `py::gil_scoped_release` is wired from day one.

**Key files:**
- Fork V6 directory wholesale → `src/chess_engine/engine/v7/`, search-replace `v6_engine` → `v7_engine`, `V6` → `V7`
- `python_bindings.cpp` — REWRITE binding pattern (see snippet below)
- `__init__.py` — adapter following V6 `chess_algorithm.py` shape (FOUND-03)
- `native_build.py` — copy V6's, rename strings
- `CMakeLists.txt` — copy V6's, add custom command for coeffs codegen, add Fathom subdirectory, add `v7_uci` executable target
- `uci_main.cpp` — minimal UCI loop calling into the same C++ Engine (FOUND-07)

**Technical approach — V7 binding pattern (REPLACES V6's bug):**
```cpp
// python_bindings.cpp
#include <pybind11/pybind11.h>
#include "engine.hpp"  // wraps board+TT+search+syzygy

namespace py = pybind11;

PYBIND11_MODULE(v7_engine, m) {
    py::class_<Engine>(m, "Engine")
        .def(py::init<>())
        .def("set_syzygy_path", &Engine::set_syzygy_path,
             py::call_guard<py::gil_scoped_release>())
        .def("search", &Engine::search,
             py::arg("fen"),
             py::arg("depth") = 6,
             py::arg("time_ms") = 5000,
             py::call_guard<py::gil_scoped_release>())  // FOUND-05 — Pitfall #11
        .def("stop", &Engine::stop)  // sets atomic<bool>; cheap, no GIL release needed
        .def("tbhits", &Engine::tbhits)
        .def("nodes", &Engine::nodes);

    m.def("perft", &perft_entry,
          py::arg("fen"), py::arg("depth"),
          py::call_guard<py::gil_scoped_release>());  // FOUND-06
}
```

**Engine class minimal shape (`include/engine.hpp`):**
```cpp
class Engine {
public:
    Engine();
    void set_syzygy_path(const std::string& path);  // logs per D-08, never throws
    SearchResult search(const std::string& fen, int depth, int time_ms);
    void stop() { stop_flag_.store(true, std::memory_order_relaxed); }
    uint64_t tbhits() const { return tbhits_.load(); }
    uint64_t nodes() const { return nodes_.load(); }
private:
    std::atomic<bool> stop_flag_{false};
    std::atomic<uint64_t> tbhits_{0};
    std::atomic<uint64_t> nodes_{0};
    TT tt_;
    Board board_;
    SyzygyState syzygy_;
};
```

**Gotchas:**
- **Windows MSVC** is the historically-fragile target (Pitfall #41). Build A1 on Windows FIRST, before adding any of B1/B2/B3 — flushes out toolchain issues early. Confirm `.pyd` builds and loads.
- **`stop()` must NOT release GIL** — it's a single atomic write, fast, called from another Python thread that already holds the GIL. Releasing GIL on a fast write is pure overhead.
- **`search()` MUST release GIL** — otherwise (1) Python thread calling `stop()` will block on the GIL the search is holding, breaking cancellation; (2) Phase 4 Lazy SMP threads serialize on GIL.
- V7 builds an `Engine` instance per-game (or one persistent per process); state lives in C++ between calls. Adapter creates one per `find_best_move` call OR holds a module-level singleton — Phase 1 can use either, prefer module-level for less per-call cost.

**References:**
- `src/chess_engine/engine/v6/CMakeLists.txt` — copy this verbatim
- `src/chess_engine/engine/v6/native_build.py` — copy this verbatim
- `src/chess_engine/engine/v6/src/python_bindings.cpp` — DO NOT COPY (this is the file with the bug); use it as a counter-example
- pybind11 v2.12.0 docs `call_guard` and `gil_scoped_release` [CITED: pybind11.readthedocs.io/en/stable/advanced/misc.html]

## A2: Board + Movegen + Magic + Zobrist + Perft Parity

**Goal:** V7 reproduces V6's perft node counts exactly to depth 6 on the canonical test corpus (FOUND-06).

**Key files (forked, no logic changes):**
- `include/board.hpp`, `src/board.cpp`
- `include/movegen.hpp`, `src/movegen.cpp`
- `include/magic.hpp`, `src/magic.cpp`
- `include/zobrist.hpp`, `src/zobrist.cpp`
- `include/tt.hpp`, `src/tt.cpp` (single-threaded; Phase 3 replaces)

**Technical approach:** Direct file copy from V6, no logic edits in A2. Add a `perft(fen, depth)` entry point exposed to Python via the binding (already shown above). Run the test corpus, diff against V6.

**Perft Test Corpus (verify V7 == V6 to depth 6):**

| Position | FEN | Depth 5 | Depth 6 |
|----------|-----|---------|---------|
| Starting position | `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1` | 4,865,609 | 119,060,324 |
| Kiwipete | `r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1` | 193,690,690 | 8,031,647,685 |
| Position 3 | `8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1` | 674,624 | 11,030,083 |
| Position 4 | `r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2pP/R2Q1RK1 w kq - 0 1` | 15,833,292 | 706,045,033 |
| Position 5 | `rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8` | 89,941,194 | 3,048,196,529 |

[CITED: chessprogramming.org/Perft_Results — these are the canonical reference counts; ASSUMED correct for cross-check, verify against current V6 perft output before locking the test fixtures]

**Gotchas:**
- Perft to depth 6 on Kiwipete takes minutes single-threaded — make depth-6 tests opt-in (e.g., `pytest -m slow`); standard CI runs depth-4 or depth-5.
- **DO NOT** parallelize perft for V7 in Phase 1 — single-threaded reference matters. Phase 4 may add a parallel perft.
- Magic table initialization runs once at module load; if V7 lazy-initializes from the `Engine` constructor instead, perft launches will be slower than V6 (V6 inits at module load via static constructors). Match V6's pattern.

**References:**
- `src/chess_engine/engine/v6/src/board.cpp` etc. — exact source
- chessprogramming.org/Perft_Results — node count reference

## B1: Sequential PVS Search Hardened

**Goal:** Forked V6 search (`search.cpp`) plus the three pre-C1 must-fixes (mate-TT correctness, in-tree repetition, time-mgmt safety margin), plus the SearchInfo cancellation wiring.

**Key files (forked + modified):**
- `include/search.hpp` — fork V6, add `std::atomic<bool>* external_stop` pointer to `SearchInfo` so the binding can flip it from Python
- `src/search.cpp` — fork V6, apply the four fixes below

**What V7 inherits from V6 (no work):**
- PVS (search.cpp:249-257)
- Iterative deepening with aspiration windows (lines 292-352)
- Per-node `stopped` polling (lines 37, 110) — < 50ms cancellation latency comes for free
- Quiescence search
- Killer / history move ordering (basic)
- Null-move pruning (basic — refinements in Phase 3)

**What V7 must FIX vs V6:**

### Cross-Cutting: SearchInfo Wiring (FOUND-04)
V6's `SearchInfo info; info.reset();` in search.cpp:434 / :361 creates a FRESH info per call, ignoring whatever Python passed. V7's `Engine::search(...)` must instead reference the engine's persistent `stop_flag_`. The C++ search polls `stop_flag_.load(std::memory_order_relaxed)` between nodes (cheap relaxed load on the hot path is fine; cache line stays hot in the searching thread).

V7 Python adapter wires it:
```python
# v7/__init__.py adapter
_engine = v7_engine.Engine()  # module-level singleton

def find_best_move(game_state, valid_moves, engine, search_info=None):
    fen = game_state.get_fen()
    if search_info is not None:
        # Forward Python cancellation to C++ atomic
        # Implementation: a watcher thread, or wire search_info.stopped → _engine.stop()
        # via GameManager.stop_search() calling algo_v7.stop() directly (preferred — see INT-01 diff)
        pass
    result = _engine.search(fen, depth=6, time_ms=5000)  # GIL released inside
    # ...
```

The cleanest implementation: `GameManager.stop_search()` (game_manager.py line 68) gets a 1-line addition to also call `algo_v7._engine.stop()` when V7 is the active engine. No watcher thread needed.

### Cross-Cutting: Mate-Score TT (SRCH-13, Pitfall #1)
Mate scores include the ply at which mate is found, but a stored mate score is only valid relative to the ply it was stored at. Without correction, a TT hit at a different ply returns a wrong mate distance and the search can claim mate when none exists.

**Pattern (chessprogramming.org standard):**
```cpp
// score_to_tt: called BEFORE storing in TT
inline int score_to_tt(int score, int ply) {
    if (score >= MATE_IN_MAX_PLY) return score + ply;
    if (score <= -MATE_IN_MAX_PLY) return score - ply;
    return score;
}
// score_from_tt: called AFTER reading from TT
inline int score_from_tt(int score, int ply) {
    if (score >= MATE_IN_MAX_PLY) return score - ply;
    if (score <= -MATE_IN_MAX_PLY) return score + ply;
    return score;
}
```
[CITED: chessprogramming.org/Transposition_Table#Mate_Scores]

V7 search must call `score_to_tt(s, ply)` at every TT store and `score_from_tt(s, ply)` at every TT probe. Audit V6 source — if V6 already does this correctly, V7 inherits; if V6 omits it (Pitfall #1 says it's frequently broken), V7 must add it.

### Cross-Cutting: Repetition Detection (SRCH-14, Pitfall #7)
Position repetition is a draw, but most engines only check at the root. The fix is to maintain a small array of zobrist keys for the current line being searched, and at each node check whether the current key appears earlier in the array since the last irreversible move (capture/pawn move). Three-fold repetition → return draw score (0).

**50-move TT cutoff caveat:** TT entries from positions with non-zero halfmove clock can return scores that wouldn't be valid at higher halfmove counts (because forced 50-move draw becomes reachable). Either store halfmove clock in TT entry, or refuse to return TT cutoff when current halfmove clock ≥ some threshold (e.g., 80) [CITED: chessprogramming.org/Repetitions].

### Cross-Cutting: Time Management (SRCH-15, Pitfall #33)
Time control bust = forfeit. Standard discipline:
1. Allocate per-move budget = `remaining_time / expected_moves_remaining + increment * 0.95`
2. Soft deadline at 50% of budget — DON'T start a new ID iteration past this
3. Hard deadline at budget × 0.9 — interrupt search at next node-poll if exceeded
4. Always reserve ≥10% of remaining time as safety margin

Unit tests required (D-06):
- Test: at TC=1s/move, search finishes within 0.95s
- Test: aborted search returns the best move from the last completed ID iteration (never `MOVE_NONE`)
- Test: budget calculation for `(remaining=10s, moves=40)` produces ~250ms

### SRCH-02 Aspiration Re-Search Cap
V6 search.cpp:316-320 widens the aspiration window unboundedly on fail-high/low. Pathological positions can cause N re-searches at near-full window. V7 caps at 4 widenings, then opens to full window `(-INFINITY, INFINITY)`. Trivial fix; one counter variable.

**Gotchas:**
- `std::atomic<bool>::load(std::memory_order_relaxed)` is acceptable on the polling hot path. Acquire/release semantics are NOT needed because the search reads no other shared state through the flag.
- Polling frequency: every node is fine for V6's depth/NPS scale (50ms latency at >1Mnps means polling is essentially free). Don't over-engineer with "poll every 4096 nodes" without measuring.
- Time management TC unit tests should use `time.monotonic()`, NOT `time.time()` — the latter can jump on system clock changes.

**References:**
- `src/chess_engine/engine/v6/src/search.cpp` — fork base
- `src/chess_engine/engine/v6/include/search.hpp` — SearchInfo struct shape
- chessprogramming.org/Transposition_Table#Mate_Scores
- chessprogramming.org/Repetitions
- chessprogramming.org/Time_Management
- PITFALLS.md #1, #7, #33

## B2: Eval Scaffolding (Pesto-Baseline, 11 Terms)

**Goal:** All 11 EVAL-* terms structurally present in `coeffs.json`, regenerate to `coeffs.cpp` via codegen, eval.cpp reads from generated arrays. Phase 4 Texel will tune; Phase 1 just scaffolds.

**Key files:**
- `coeffs.json` — source of truth (committed)
- `tools/gen_coeffs.py` — codegen script (committed)
- `src/coeffs.cpp` — generated (NOT committed, in .gitignore)
- `include/coeffs.hpp` — declares extern arrays
- `src/eval.cpp` — modified to read from `coeffs::material_mg[]` etc. instead of hardcoded constants

**The 11 EVAL terms (REQUIREMENTS.md mapping):**

| ID | Term | Pesto Source Available? | Initial Values |
|----|------|-------------------------|----------------|
| EVAL-01 | Material (mg + eg, 6 piece types × 2) | YES | Pesto: P=82/94, N=337/281, B=365/297, R=477/512, Q=1025/936, K=0/0 (King 0 — handled separately) |
| EVAL-02 | Piece-square tables (PSTs, mg + eg, 6 × 64 × 2 = 768 values) | YES | Pesto PST tables (publicly listed at chessprogramming.org/PeSTO%27s_Evaluation_Function) |
| EVAL-03 | Tapered eval phase weights | YES | Pesto: knight=1, bishop=1, rook=2, queen=4 (24 = full midgame, 0 = pure endgame) |
| EVAL-04 | Mobility (per-piece-type, indexed by attack count) | NO Pesto equivalent | Modest hand-set; e.g., knight mobility table 8 values: `[-62,-53,-12,-4,3,13,22,28]` mg / endgame variant. Mark `# initial; will be tuned Phase 4` |
| EVAL-05 | Bishop pair bonus | YES (~30cp common) | mg=30, eg=50 |
| EVAL-06 | Rook on (semi-)open file | Common | open=15, semi-open=10 |
| EVAL-07 | Pawn structure (doubled, isolated, passed, backward) | Common | doubled=-10, isolated=-15, backward=-5, passed=[0,5,10,20,40,80,160,0] (by rank from own side) |
| EVAL-08 | King safety / attack table | Common (Stockfish-style) | Attack-units indexed table of size 100, e.g., `[0,0,1,2,3,5,7,9,12,15,18,22,26,30,35,...]` to penalty cp |
| EVAL-09 | Threats (piece attacked by lesser piece) | Common | minor-attacked-by-pawn=-25, rook-attacked-by-minor=-20, queen-attacked-by-rook=-30 |
| EVAL-10 | Tempo bonus | YES | mg=10, eg=0 |
| EVAL-11 | Tapered combine: `eval = (mg * phase + eg * (24 - phase)) / 24` | YES (Pesto formula) | Code, not coefficient — implements EVAL-03 weights |

**Pesto baseline source:** Pesto's PSTs and material values are published at chessprogramming.org/PeSTO%27s_Evaluation_Function. Cite this exact URL in `coeffs.json`'s top-of-file comment per CONTEXT D-01 specifics. [CITED: chessprogramming.org/PeSTO%27s_Evaluation_Function]

**`coeffs.json` skeleton:**
```jsonc
{
  "_meta": {
    "source": "Pesto evaluation values (https://www.chessprogramming.org/PeSTO%27s_Evaluation_Function); non-PST terms are hand-set initial values to be tuned in Phase 4 against Zurichess quiet-labeled.epd",
    "version": 1,
    "generated_by": "tools/gen_coeffs.py"
  },
  "material_mg": {"P": 82, "N": 337, "B": 365, "R": 477, "Q": 1025, "K": 0},
  "material_eg": {"P": 94, "N": 281, "B": 297, "R": 512, "Q": 936, "K": 0},
  "phase_weights": {"P": 0, "N": 1, "B": 1, "R": 2, "Q": 4, "K": 0},
  "pst_mg": {
    "P": [0,0,0,0,0,0,0,0,  98,134,61,95,68,126,34,-11,  /* ... 64 values per piece ... */],
    "N": [/* 64 */],
    "B": [/* 64 */],
    "R": [/* 64 */],
    "Q": [/* 64 */],
    "K": [/* 64 */]
  },
  "pst_eg": { "P": [/* 64 */], "N": [/* 64 */], "B": [/* 64 */], "R": [/* 64 */], "Q": [/* 64 */], "K": [/* 64 */] },
  "mobility_knight_mg": [-62,-53,-12,-4,3,13,22,28,33],
  "mobility_knight_eg": [-81,-56,-31,-16,5,11,17,20,25],
  "mobility_bishop_mg": [/* 14 values */],
  "mobility_bishop_eg": [/* 14 values */],
  "mobility_rook_mg":   [/* 15 values */],
  "mobility_rook_eg":   [/* 15 values */],
  "mobility_queen_mg":  [/* 28 values */],
  "mobility_queen_eg":  [/* 28 values */],
  "bishop_pair_mg": 30, "bishop_pair_eg": 50,
  "rook_open_file": 15, "rook_semi_open_file": 10,
  "doubled_pawn": -10, "isolated_pawn": -15, "backward_pawn": -5,
  "passed_pawn_by_rank": [0, 5, 10, 20, 40, 80, 160, 0],
  "king_attack_table": [0,0,1,2,3,5,7,9,12,15,18,22,26,30,35,/* 100 total */],
  "threat_minor_by_pawn": -25,
  "threat_rook_by_minor": -20,
  "threat_queen_by_rook": -30,
  "tempo_mg": 10, "tempo_eg": 0
}
```

**Pesto exact PST values (mg + eg, the 768 numbers):** All 12 tables (6 pieces × {mg, eg}) are listed verbatim on the chessprogramming.org PeSTO page. The Phase 1 implementer copies them directly. Do NOT hand-transcribe — copy from a programmatic source (e.g., open-source engine using Pesto, with attribution) to avoid typos. [CITED: chessprogramming.org/PeSTO%27s_Evaluation_Function]

**`tools/gen_coeffs.py` — deterministic output (D-13):**
```python
#!/usr/bin/env python3
"""Generate src/coeffs.cpp from coeffs.json. Deterministic output."""
import json, sys
from pathlib import Path

def render_array(name, vals, type_="int"):
    body = ", ".join(str(v) for v in vals)
    return f"const {type_} {name}[{len(vals)}] = {{ {body} }};\n"

def main():
    src = Path(sys.argv[1])  # coeffs.json
    dst = Path(sys.argv[2])  # coeffs.cpp
    data = json.loads(src.read_text(encoding="utf-8"))
    out = ['// GENERATED by tools/gen_coeffs.py — DO NOT EDIT\n',
           '// Source: ' + str(src) + '\n',
           '#include "coeffs.hpp"\n',
           'namespace v7::coeffs {\n']
    # Render every key in sorted order for determinism
    for key in sorted(data.keys()):
        if key.startswith("_"): continue
        val = data[key]
        if isinstance(val, list):
            out.append(render_array(key, val))
        elif isinstance(val, dict):
            for sub in sorted(val.keys()):
                inner = val[sub]
                if isinstance(inner, list):
                    out.append(render_array(f"{key}_{sub}", inner))
                else:
                    out.append(f"const int {key}_{sub} = {inner};\n")
        else:
            out.append(f"const int {key} = {val};\n")
    out.append('} // namespace v7::coeffs\n')
    # LF line endings explicitly (D-13)
    dst.write_bytes("".join(out).encode("utf-8").replace(b"\r\n", b"\n"))

if __name__ == "__main__":
    main()
```

**`include/coeffs.hpp`:**
```cpp
#pragma once
namespace v7::coeffs {
    extern const int material_mg_P, material_mg_N, /* ... */;
    extern const int pst_mg_P[64], pst_mg_N[64], /* ... */;
    extern const int mobility_knight_mg[9];
    extern const int passed_pawn_by_rank[8];
    extern const int king_attack_table[100];
    // ... etc., declared exhaustively to match the codegen output
}
```

**CMake custom command (D-11):**
```cmake
set(COEFFS_JSON ${CMAKE_CURRENT_SOURCE_DIR}/coeffs.json)
set(COEFFS_CPP  ${CMAKE_CURRENT_SOURCE_DIR}/src/coeffs.cpp)
add_custom_command(
    OUTPUT ${COEFFS_CPP}
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_coeffs.py ${COEFFS_JSON} ${COEFFS_CPP}
    DEPENDS ${COEFFS_JSON} ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_coeffs.py
    COMMENT "Generating coeffs.cpp from coeffs.json"
)
# Then list ${COEFFS_CPP} in your add_library(v7_engine MODULE ...) sources
```

**Gotchas:**
- **`coeffs.cpp` MUST NOT be committed** (D-12) — add to `.gitignore`. If a contributor accidentally commits it, the deterministic output (D-13) means it doesn't drift across machines, but the codegen still re-runs on every build keyed on `coeffs.json` mtime so it gets overwritten.
- **Header sync risk:** `coeffs.hpp` declares extern names; `gen_coeffs.py` produces them. Mismatch = link error. Phase 4 work expands this; Phase 1 keeps the schema minimal and locked.
- **Eval at depth 0 baseline:** with Pesto values and no other terms, `eval(startpos)` should return roughly 0 ± tempo bonus (10cp). If V7 returns >50cp white-favored at startpos, sign error somewhere — common bug.

**References:**
- chessprogramming.org/PeSTO%27s_Evaluation_Function (verbatim PST + material values) [CITED]
- ROADMAP.md decision 4 — all EVAL-* terms must be structurally present in Phase 1

## B3: Fathom / Syzygy Integration

**Goal:** V7 can probe Syzygy tablebases (root + in-search), reports `tbhits`, and handles missing/broken paths gracefully per D-07/D-08.

**Key files:**
- `extern/fathom/` — git submodule (TB-01)
- `include/tbconfig.h` — override file (TB-02)
- `include/syzygy.hpp`, `src/syzygy.cpp` — V7 wrapper around Fathom

**Submodule setup (TB-01, INT-06):**
```bash
git submodule add https://github.com/jdart1/Fathom.git src/chess_engine/engine/v7/extern/fathom
# Pin to a specific SHA for reproducibility
cd src/chess_engine/engine/v7/extern/fathom
git checkout <SHA>
cd -
git add .gitmodules src/chess_engine/engine/v7/extern/fathom
```

`.gitmodules` entry:
```
[submodule "src/chess_engine/engine/v7/extern/fathom"]
    path = src/chess_engine/engine/v7/extern/fathom
    url = https://github.com/jdart1/Fathom.git
```

**CMake recipe (paste-ready, append to V7 `CMakeLists.txt`):**
```cmake
# Fathom: header-only-ish; we compile its src/tbprobe.c into our module
set(FATHOM_DIR ${CMAKE_CURRENT_SOURCE_DIR}/extern/fathom)

# Override Fathom's tbconfig.h with ours (TB-02): point Fathom at our magic-bitboard
# attack tables instead of letting it carry its own copy. Done by adding our include
# dir BEFORE Fathom's so #include "tbconfig.h" resolves to ours.
target_include_directories(v7_engine PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include      # our tbconfig.h overrides Fathom's
    ${FATHOM_DIR}/src                        # Fathom headers
)

target_sources(v7_engine PRIVATE
    ${FATHOM_DIR}/src/tbprobe.c
    src/syzygy.cpp
)

# Fathom is C, not C++; ensure C language enabled
enable_language(C)

# Same treatment for the standalone v7_uci binary
target_include_directories(v7_uci PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${FATHOM_DIR}/src
)
target_sources(v7_uci PRIVATE ${FATHOM_DIR}/src/tbprobe.c src/syzygy.cpp)
```

**`include/tbconfig.h` skeleton (TB-02):** Fathom's `tbconfig.h` defines macros for `pyrook_attacks`, `pyrook_attacks_xray`, etc. The override version delegates to V7's existing magic functions:
```cpp
// V7's tbconfig.h — overrides Fathom's; ensures Fathom uses our attack tables
#pragma once
#include "magic.hpp"  // V7's bitboard attack functions

#define TB_CUSTOM_LSB
#include "bitboard.hpp"
inline unsigned tb_lsb(uint64_t b) { return __builtin_ctzll(b); }  // or _BitScanForward64 on MSVC

#define TB_PAWN_ATTACKS(sq, color) (v7::pawn_attacks(sq, color))
#define TB_KNIGHT_ATTACKS(sq)      (v7::knight_attacks(sq))
#define TB_BISHOP_ATTACKS(sq, occ) (v7::bishop_attacks(sq, occ))
#define TB_ROOK_ATTACKS(sq, occ)   (v7::rook_attacks(sq, occ))
#define TB_QUEEN_ATTACKS(sq, occ)  (v7::queen_attacks(sq, occ))
#define TB_KING_ATTACKS(sq)        (v7::king_attacks(sq))
```
[CITED: Fathom README — `tbconfig.h` override mechanism is the supported integration pattern]

**Fathom API surface (jdart1 fork):**

| Function | Use |
|----------|-----|
| `tb_init(const char* path)` | Called from `Engine::set_syzygy_path`. Returns `true` on success. Loads up to 6-piece tables. |
| `TB_LARGEST` (global) | Largest piece count loaded; 0 if no TBs. Use this to gate in-search probes. |
| `tb_probe_wdl(...)` | In-search WDL probe; cheap. Returns `TB_WIN`, `TB_DRAW`, `TB_LOSS`, `TB_BLESSED_LOSS`, `TB_CURSED_WIN`, `TB_RESULT_FAILED`. |
| `tb_probe_root(...)` | Root probe; returns DTZ + best move. Slower but used only at root. |
| `tb_free()` | Cleanup at engine destruction. |

[CITED: github.com/jdart1/Fathom/blob/master/src/tbprobe.h — exact API names; verify SHAs at integration time]

### B3: Init-Time Log Discipline (D-08, TB-10)

```cpp
// src/syzygy.cpp
void Engine::set_syzygy_path(const std::string& path) {
    if (path.empty()) {
        std::cerr << "[v7] syzygy: no path configured; tbhits will be 0\n";
        return;
    }
    namespace fs = std::filesystem;
    if (!fs::exists(path) || !fs::is_directory(path)) {
        std::cerr << "[v7] syzygy: path not found: " << path << "; tbhits will be 0\n";
        return;
    }
    bool any_rtbw = false;
    for (auto& e : fs::directory_iterator(path)) {
        if (e.path().extension() == ".rtbw") { any_rtbw = true; break; }
    }
    if (!any_rtbw) {
        std::cerr << "[v7] syzygy: no tablebase files at " << path << "; tbhits will be 0\n";
        return;
    }
    if (!tb_init(path.c_str())) {
        std::cerr << "[v7] syzygy: tb_init failed at " << path << "; tbhits will be 0\n";
        return;
    }
    // TB-10: KRk smoke probe to validate files actually load
    // FEN: "4k3/8/8/8/8/8/4R3/4K3 w - - 0 1" (KRk endgame)
    if (!smoke_probe_krk()) {
        std::cerr << "[v7] syzygy: smoke probe failed (corrupt or wrong format) at " << path << "; tbhits will be 0\n";
        tb_free();
    }
}
```

**Use exact log strings from D-08 verbatim** — users will grep logs.

### B3: TB Probe Failure Handling (TB-06, D-09)

In-search probes:
```cpp
unsigned wdl = tb_probe_wdl(...);
if (wdl == TB_RESULT_FAILED) {
    // D-09: NEVER silently treat as DRAW
    // Options: (a) hard error, (b) flag and skip the probe at this node
    // Phase 1: flag + skip + log to stderr; do NOT return DRAW score
    std::cerr << "[v7] syzygy: in-search probe failed at fen=" << current_fen() << "\n";
    return std::nullopt;  // caller treats as "no probe info"
}
tbhits_.fetch_add(1, std::memory_order_relaxed);
// Map TB_WIN/DRAW/LOSS to score; cursed/blessed treated per 50-move rule
```

**Gotchas:**
- **`tb_init` is NOT thread-safe** with concurrent search; call it before any worker threads exist. Phase 1 is single-threaded so this is moot, but document the constraint for Phase 4.
- **Fathom is C, not C++** — wrap `extern "C"` headers properly (`tbprobe.h` already does this).
- **Probe-in-check is undefined** — Fathom requires the side to move not be in check before probing WDL. V7 must skip probes in-check positions.
- **`syzygyMaxPieces` (TB-08)** — clamp probes to `min(syzygyMaxPieces, TB_LARGEST)`. Default 6.
- **Submodule update on clone** — README must say `git clone --recursive` or `git submodule update --init` after clone, otherwise V7 build fails with missing `tbprobe.c`.

**References:**
- github.com/jdart1/Fathom — README + `tbprobe.h` for API
- chessprogramming.org/Syzygy_Bases — general background
- D-07, D-08, D-09 from CONTEXT.md

## C1: Smoke Integration

**Goal:** V7 plays one legal game vs V6 from the React UI, dispatched through GameManager, with the build & install pipeline working end-to-end.

**Key files:**
- `src/chess_engine/server/game_manager.py` — INT-01 4-line edit
- `client/src/App.jsx` — INT-02 dropdown options + INT-03 warning copy
- `cli/src/config.js` — INT-04 config keys
- `cli/src/index.js` — INT-05 subcommands
- `tests/test_v7_engine.py` — INT-07 smoke + perft + cancel + NPS sentinel

**INT-01: GameManager 4-line edit (`server/game_manager.py`):**
```python
# Line 13 area: AVAILABLE_ENGINES set — add "v7"
AVAILABLE_ENGINES = {"human", "v3", "v4b", "v4c", "v5", "v5b", "v5c", "v5d", "v6", "v7"}

# Line 41 area: set_engine_version ladder — add v7 branch
elif version == "v7":
    from chess_engine.engine.v7 import chess_algorithm as algo_v7
    algo_v7.ensure_available(auto_build=True)

# Line 286 area: ai_move ladder — add v7 dispatch
elif self.engine_version == "v7":
    from chess_engine.engine.v7 import chess_algorithm as algo_v7
    move, stats = algo_v7.find_best_move(self.game_state, valid_moves, "v7", self.current_search_info)

# Line 68 area: stop_search — also notify V7's C++ atomic
def stop_search(self):
    if self.current_search_info:
        self.current_search_info.stopped = True
    # V7-specific: also flip the C++ atomic so the search-thread sees it without GIL
    if self.engine_version == "v7":
        try:
            from chess_engine.engine.v7 import chess_algorithm as algo_v7
            if algo_v7.V7_AVAILABLE:
                algo_v7.stop_engine()  # exposed by adapter, calls _engine.stop()
        except Exception:
            pass
```
**Note:** This is technically more than 4 lines once you include `stop_search` enhancement, but it's still a surgical patch — preserves the engine ladder anti-pattern per V2-REF-01 deferral.

**INT-02 + INT-03: React UI (`client/src/App.jsx`):**

After line 408 (`<option value="v6">White: V6 (C++)</option>`), add:
```jsx
<option value="v7">White: V7 (C++)</option>
```
Same for line 423 (black dropdown). Update line 235:
```jsx
if (ver === "v6" || ver === "v7") {
  const message = `Preparing ${ver.toUpperCase()} native engine; first use may build locally.`;
  setEngineStatus(message);
  log(message);
}
```

**INT-04: CLI config (`cli/src/config.js`):**
```js
const DEFAULT_CONFIG = {
  threads: null,
  ttSize: 64,
  maxMemory: 512,
  timeLimit: 5000,
  v6Built: false,
  v7Built: false,                    // INT-04
  syzygyPath: null,                  // INT-04
  syzygyMaxPieces: 6,                // INT-04
  lastBuildTime: null,
  cmakePath: null,
};
```

**INT-05: CLI subcommands (`cli/src/index.js`):**
- `chess-engine build v7` — mirror existing `buildV6()` (line 148), invoke `uv run --extra build python -m chess_engine.engine.v7.native_build`
- `chess-engine syzygy download` — new subcommand fetching 3-4-5 men tables (~1GB) to `syzygyPath` if set, else `~/.local/share/chess-engine/syzygy/` on Linux/macOS or `%LOCALAPPDATA%\chess-engine\syzygy\` on Windows. Open Question — see below

**INT-07: Smoke test file (`tests/test_v7_engine.py`):** See Validation Architecture section.

**INT-08: V1-V6 unchanged regression** — existing `pytest tests/` runs unmodified. CI must include this run after V7 changes land.

**INT-09: Auto-build on first import** — V7 `__init__.py` (or `chess_algorithm.py`) implements `ensure_available(auto_build=True)` mirroring V6's pattern at `src/chess_engine/engine/v6/chess_algorithm.py:61-90`.

**Gotchas:**
- **Test ordering matters:** smoke test must run AFTER auto-build attempt. CI: first run `chess-engine build v7` explicitly, THEN `pytest`. Avoids the "build succeeds in test but slows pytest by 60s" trap.
- **First-game smoke selects V7-as-white per D-04** — test fixture sets `set_engine_version("v7", "white")` and `set_engine_version("v6", "black")`, NOT the reverse.
- **Frontend dropdown ordering:** put V7 ABOVE V6 in the `<select>` (newer = higher) per existing V5d → V5c → V5b convention.

## Cross-Cutting Concerns Summary

| Concern | Where it lands | Pitfall ref | Validated by |
|---------|----------------|-------------|--------------|
| GIL release on search binding | A1 — `python_bindings.cpp` `py::call_guard<py::gil_scoped_release>()` | #11 | Test: spawn Python thread, run `_engine.search()`, from main thread call `_engine.stop()`, search returns within ~50ms |
| SearchInfo wiring (Python→C++) | A1 + B1 + C1 — `Engine::stop_flag_` atomic + GameManager `stop_search` patch | — (closes V6 gap) | Same test as above |
| Mate-score TT correction | B1 — `score_to_tt`/`score_from_tt` in TT store/probe | #1 | Test: position with mate-in-3 reachable through transposition returns mate-in-3 (not mate-in-N+3 from cached entry) |
| Repetition detection in tree | B1 — repetition stack in search node | #7 | Test: position 3-fold repeats inside a 5-ply line returns score 0 |
| 50-move TT cutoff | B1 — refuse TT cutoff at high halfmove clock | #7 | Test: position near 50-move boundary doesn't return cached non-draw score |
| Time management safety | B1 — soft/hard deadline with ≥10% margin | #33 | Unit test: TC=1s budget produces ≤950ms actual search time across 100 trials |
| Aspiration re-search cap | B1 — counter capping at 4 widenings | — (V6 anti-pattern) | Unit test: pathological TT position doesn't loop infinitely |
| Lockless TT (deferred) | Phase 3, NOT Phase 1 | #36 | — |
| Syzygy in-search failure ≠ DRAW | B3 — return `nullopt` not 0 | D-09 | Test: corrupted TB file at search time emits log, does NOT score node as draw |

## Pitfalls Map

| # | Pitfall | Phase 1 build group | Mitigation in research |
|---|---------|---------------------|------------------------|
| #1 | Mate-score TT off-by-one ply | B1 | `score_to_tt` / `score_from_tt` pattern; audit V6 first |
| #7 | Repetition not detected in tree | B1 | Repetition stack at every node; 50-move TT cutoff guard |
| #11 | GIL not released — single most common pybind11 mistake | A1 | `py::call_guard<py::gil_scoped_release>()` from day one |
| #33 | Time management busts TC | B1 | Soft/hard deadline; ≥10% margin; unit tests required |
| #36 | Lockless TT precondition for Lazy SMP | DEFERRED to Phase 3 | NOT Phase 1; V7 starts with V6's single-threaded TT |
| #41 | Windows MSVC build fragility | A1 | Build on Windows FIRST before any other work |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) — declared in `pyproject.toml` `[dependency-groups].dev` |
| Config file | None (project uses default pytest discovery) |
| Quick run command | `python3 -m uv run --group dev pytest tests/test_v7_engine.py -q` |
| Full suite command | `python3 -m uv run --group dev pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FOUND-01 | V7 directory exists with expected layout | structure | `pytest tests/test_v7_engine.py::test_v7_layout -x` | ❌ Wave 0 |
| FOUND-02 | `chess-engine build v7` succeeds | integration | `pytest tests/test_v7_engine.py::test_v7_build -x` | ❌ Wave 0 |
| FOUND-03 | `find_best_move` returns valid move from startpos | unit | `pytest tests/test_v7_engine.py::test_find_best_move_signature -x` | ❌ Wave 0 |
| FOUND-04 | Cancellation interrupts search within 50ms | unit | `pytest tests/test_v7_engine.py::test_cancellation_latency -x` | ❌ Wave 0 |
| FOUND-05 | GIL release verified by concurrent stop test | unit | `pytest tests/test_v7_engine.py::test_gil_released -x` | ❌ Wave 0 |
| FOUND-06 | Perft parity v6 == v7 to depth 5 (depth-6 opt-in) | unit | `pytest tests/test_v7_engine.py::test_perft_parity -x` | ❌ Wave 0 |
| FOUND-07 | `v7_uci` binary exists and accepts `uci` command | smoke | `pytest tests/test_v7_engine.py::test_uci_binary -x` | ❌ Wave 0 |
| SRCH-01 | ID iteration produces best move at each depth | unit | `pytest tests/test_v7_engine.py::test_iterative_deepening -x` | ❌ Wave 0 |
| SRCH-02 | Aspiration window re-search caps at 4 widenings | unit | `pytest tests/test_v7_engine.py::test_aspiration_cap -x` | ❌ Wave 0 |
| SRCH-13 | Mate-in-N score correct after TT transposition | unit | `pytest tests/test_v7_engine.py::test_mate_score_tt -x` | ❌ Wave 0 |
| SRCH-14 | 3-fold repetition returns score 0 in tree | unit | `pytest tests/test_v7_engine.py::test_repetition_in_tree -x` | ❌ Wave 0 |
| SRCH-15 | Time budget honored with ≥10% margin (D-06) | unit | `pytest tests/test_v7_engine.py::test_time_management -x` | ❌ Wave 0 |
| EVAL-01..11 | All 11 terms present in `coeffs.json` and used by eval | unit | `pytest tests/test_v7_engine.py::test_eval_terms_present -x` | ❌ Wave 0 |
| TB-01..10 | Syzygy probes work; missing path emits exact log | unit + integration | `pytest tests/test_v7_engine.py::test_syzygy_* -x` | ❌ Wave 0 |
| INT-01 | `set_engine_version("v7", ...)` succeeds | unit | `pytest tests/test_v7_engine.py::test_gm_dispatch -x` | ❌ Wave 0 |
| INT-02..03 | Dropdown contains v7 option | manual or playwright | manual: open UI, verify | manual |
| INT-04..05 | CLI subcommands runnable | smoke | `node cli/bin/chess-engine.js build v7 --dry-run` | ❌ Wave 0 |
| INT-07 | C1 smoke: V7-as-white plays full game vs V6 (D-04) | integration | `pytest tests/test_v7_engine.py::test_smoke_game_v7_vs_v6 -x` | ❌ Wave 0 |
| INT-08 | V1-V6 regression suite green | regression | `pytest tests/ --ignore=tests/test_v7_engine.py -q` | ✅ existing |
| INT-09 | First-import auto-build path triggers | unit | `pytest tests/test_v7_engine.py::test_auto_build -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_v7_engine.py -q -m "not slow"` (excludes depth-6 perft)
- **Per wave merge:** `pytest tests/test_v7_engine.py -q` (includes depth-6 perft, ~minutes)
- **Phase gate:** Full suite (`pytest -q`) green + manual smoke game in UI before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_v7_engine.py` — covers all V7 requirements (does not exist yet)
- [ ] `tests/conftest.py` — verify if shared fixtures already exist; add V7 engine fixture if needed
- [ ] No new framework install — pytest already declared

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | A1, build, tests | ✓ (pinned 3.12) | 3.12 | — |
| uv | build, tests | ✓ | (project requires) | — |
| Node.js 20.19+ or 22.12+ | C1 (CLI), frontend | ✓ | (project requires) | — |
| CMake ≥3.15 | A1 (build) | unverified — must check on Windows MSVC target | — | If missing, planner adds explicit install step in Wave 0 |
| C++17 compiler (MSVC on Windows, gcc/clang elsewhere) | A1 (build) | unverified | — | Document install step in README per INT-08 |
| git submodule support | A1 (TB-01 Fathom) | ✓ (git is required for repo) | — | — |
| pybind11 v2.12.0 | A1 (build) | auto-fetched via CMake `FetchContent` | — | — |
| Fathom source | B3 | NOT YET (added in TB-01) | — | git submodule add at start of B3 |
| Syzygy `.rtbw`/`.rtbz` files (3-4-5 men, ~1GB) | B3 in-search probes | NOT bundled (PROJECT.md constraint) | — | TB-09 download script; tests using TB probes are SKIPPED if files absent |
| Pesto values | B2 (`coeffs.json` initial) | reference data, manually transcribed from chessprogramming.org | — | Source URL committed in `coeffs.json` `_meta.source` |
| Zurichess `quiet-labeled.epd` | Phase 4 (NOT Phase 1) | — | — | — |

**Missing dependencies with no fallback:**
- None blocking Phase 1 — all required tools are available or auto-fetched.

**Missing dependencies with fallback:**
- Syzygy tablebase files: tests gated on `pytest.mark.skipif(not Path(SYZYGY_PATH).exists())`; init-time log discipline (D-08) makes engine work without them.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-tuned eval constants | JSON-driven coefficients regenerated to C++ at build time | Standard since ~2015 (Texel methodology) | Required for Phase 4 sparse coefficient extraction |
| Free-function pybind11 binding (V6's pattern) | Stateful class binding with explicit `stop()` method | — | Required for FOUND-04 cancellation; V6's bug is a direct consequence of free-function pattern |
| Original basil00/Fathom | jdart1/Fathom fork | More active maintenance | STACK.md research recommendation |
| Carrying Fathom's own attack tables | `tbconfig.h` override sharing host's tables | Standard since Fathom supported overrides | TB-02 saves ~6MB attack table memory |

**Deprecated/outdated:**
- pybind11 < 2.10 had buggy `call_guard` interaction with `arg_v` defaults — Phase 1 uses 2.12.0, no issue.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pesto exact PST values are accessible at chessprogramming.org page format unchanged | B2 | LOW — values are stable reference data; if URL moved, content is mirrored in many open-source engines |
| A2 | Perft node counts in test corpus are correct | A2 | LOW — these are canonical reference numbers cross-checked by hundreds of engines; verify by running V6 perft and comparing before locking the test fixtures |
| A3 | Fathom jdart1 fork exposes `tb_init`, `tb_probe_wdl`, `tb_probe_root`, `TB_LARGEST` with these exact names | B3 | MEDIUM — verify exact API surface against Fathom's `tbprobe.h` at the chosen submodule SHA before writing `syzygy.cpp` |
| A4 | V6's TT correctly applies mate-score adjustment (Pitfall #1) | B1 | MEDIUM — if V6 already does it, V7 inherits; if NOT, V7 is the first to fix it. Audit `src/chess_engine/engine/v6/src/tt.cpp` and `search.cpp` for `MATE_IN` ply arithmetic before locking the SRCH-13 plan |
| A5 | V6's repetition detection is root-only (Pitfall #7) | B1 | MEDIUM — same as above. Audit V6's search for repetition stack |
| A6 | Module-level singleton `_engine = v7_engine.Engine()` works for the GameManager singleton model | A1, C1 | LOW — V6 pattern (`gm = GameManager()` module-global) is exactly this shape |
| A7 | Windows MSVC builds Fathom's `tbprobe.c` cleanly | B3 | MEDIUM — Fathom is C99, MSVC has historically been spotty on C99 features. Build on Windows FIRST during B3 |
| A8 | `coeffs.cpp` deterministic codegen survives across Python versions on different OSes | B2 | LOW — `json.dumps(sort_keys=True)` is stable; explicit LF line endings (D-13) cover newline differences |
| A9 | The V6 `find_best_move` adapter pattern (with `search_info=None` default, ignored in body) lets V7 override `search_info` semantics without breaking GameManager call site | C1 | LOW — `find_best_move(..., search_info)` signature is the established contract per FOUND-03 |
| A10 | Pesto material values (P=82/94 etc.) are the canonical Pesto-2019 values | B2 | LOW — verify by cross-referencing 2-3 implementations before locking `coeffs.json` |

## Open Questions (RESOLVED)

> All four open questions below were resolved during phase planning. Resolutions are tied to specific CONTEXT.md decisions (D-08, D-12, D-13) and/or specific plan task steps. This section is retained for traceability; no question here is still open.

1. **Where exactly does V6's TT/search stand on mate-TT and repetition correctness?**
   - What we know: V6's search.cpp implements PVS, ID, aspiration, and per-node stop polling. Pitfalls #1 and #7 are flagged generically.
   - What's unclear: Does V6's actual code already do `score_to_tt`/`score_from_tt`? Does V6 maintain a repetition stack in tree?
   - **RESOLVED:** This is an execution-time audit, not an open planning question. 01-03-PLAN.md Task 1 Step 1 grep-audits V6 source for `MATE_IN`, `MATE_VALUE`, `repetition`, `is_threefold` and records the verdict (V6 already-correct → V7 inherits via fork; V6 wrong → V7 patches per the SRCH-13/14 plan in 01-03-PLAN.md). Audit findings are recorded in 01-03-SUMMARY.md so subsequent plans can rely on the result.

2. **Default Syzygy path on Windows vs POSIX (CONTEXT open todo):**
   - What we know: CONTEXT's "Open Todos" lists `~/.local/share/chess-engine/syzygy/` vs `%LOCALAPPDATA%\chess-engine\syzygy\` as still-to-decide.
   - What's unclear: Single-default vs OS-specific defaults vs no-default-at-all.
   - **RESOLVED per D-12 (storage convention) and 01-06-PLAN.md Task 1 Step 6 (CLI implementation):** OS-specific defaults — `%LOCALAPPDATA%\chess-engine\syzygy\` on Windows, `${XDG_DATA_HOME:-~/.local/share}/chess-engine/syzygy/` on Linux, `~/Library/Application Support/chess-engine/syzygy/` on macOS. The CLI `syzygy download` command writes to `config.syzygyPath` if set, else this OS-specific default. Exact `defaultSyzygyPath()` implementation lives in 01-06-PLAN.md Task 1 Step 6.

3. **Should the V7 Engine instance be module-singleton or per-search?**
   - What we know: V6 holds engine state at module load (TT, magic tables); module-singleton matches.
   - What's unclear: Does any test require a fresh TT per game? (Phase 5 SPRT does, but that's Phase 4+ concern.)
   - **RESOLVED:** Module-singleton with explicit per-game reset. 01-01-PLAN.md Task 1 (`chess_algorithm.py`) adopts a module-level `_engine = v7_engine.Engine()` mirroring V6's module-load pattern. `GameManager.new_game()` invokes `algo_v7.new_game()` which calls `_engine.new_game()` to clear TT + repetition stack between games. Implementation detail captured in 01-01-PLAN.md acceptance criteria.

4. **`v7_uci` binary scope for Phase 1:**
   - What we know: FOUND-07 + Phase 2 prereq. Phase 2 fastchess gauntlet requires UCI binary.
   - What's unclear: Does Phase 1 need a FULL UCI implementation, or minimal stub that supports `uci`/`isready`/`position`/`go depth N`/`stop`/`quit`?
   - **RESOLVED per D-08 (verbatim log scope) and D-13 (explicit determinism scope) and 01-06-PLAN.md Task 1 Step 7 (full minimal UCI loop):** Phase 1 ships a full minimal UCI loop: `uci`, `isready`, `ucinewgame`, `position startpos`, `position fen`, `go depth N`, `go movetime MS`, `stop`, `quit`. `setoption name X value Y` is deferred to Phase 4 (Threads, Hash, SyzygyPath surface — referenced by both D-08 and D-13 as the next setoption surface). Phase 1 fastchess gauntlet uses depth-fixed games, so setoption is not required for the smoke milestone.

## Sources

### Primary (HIGH confidence — verified in this session)
- `src/chess_engine/engine/v6/src/python_bindings.cpp` — verified V6 binding bug (no SearchInfo arg)
- `src/chess_engine/engine/v6/include/search.hpp` — verified V6 SearchInfo struct shape
- `src/chess_engine/engine/v6/src/search.cpp` — verified V6 already has PVS, ID, aspiration, per-node stop polling
- `src/chess_engine/engine/v6/CMakeLists.txt` — verified V6 build pattern (FetchContent pybind11 v2.12.0)
- `src/chess_engine/engine/v6/native_build.py` — verified V6 build driver shape
- `src/chess_engine/engine/v6/chess_algorithm.py` — verified adapter pattern, `ensure_available(auto_build=True)`
- `src/chess_engine/server/game_manager.py` — verified INT-01 dispatch site, `stop_search` location
- `client/src/App.jsx` — verified INT-02 dropdown lines (408, 423) and INT-03 warning (235)
- `cli/src/config.js` + `cli/src/index.js` — verified INT-04/05 patch sites
- `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/phases/01-skeleton-smoke/01-CONTEXT.md` — phase scope, locked decisions
- `.planning/research/{ARCHITECTURE,STACK,PITFALLS,SUMMARY}.md` — phase-level research bundle

### Secondary (MEDIUM confidence — cited but not freshly fetched)
- chessprogramming.org/PeSTO%27s_Evaluation_Function — Pesto material + PST values [CITED]
- chessprogramming.org/Perft_Results — perft node counts for canonical positions [CITED]
- chessprogramming.org/Transposition_Table#Mate_Scores — `score_to_tt`/`score_from_tt` pattern [CITED]
- chessprogramming.org/Repetitions — in-tree repetition + 50-move TT cutoff [CITED]
- chessprogramming.org/Time_Management — soft/hard deadline pattern [CITED]
- github.com/jdart1/Fathom — Fathom API surface, `tbconfig.h` override mechanism [CITED]
- pybind11.readthedocs.io/en/stable/advanced/misc.html — `gil_scoped_release` + `call_guard` [CITED]

### Tertiary (LOW confidence — would benefit from verification before lock)
- Exact king-attack-table values (mobility-style 100-entry tables vary by engine) — A2 of "Open Questions" calls out cross-referencing 2-3 implementations
- Fathom's exact macro names in `tbconfig.h` override file — verify against actual `extern/fathom/src/tbconfig.h` once submodule added

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pybind11/CMake/C++17 inherited unchanged from V6 with verified file refs
- Architecture (build groups, V7 layout, INT-01..09 patch sites): HIGH — all files read in this session
- V6 SearchInfo bug + fix pattern (FOUND-04, FOUND-05): HIGH — bug confirmed by reading V6 binding
- B1 search hardening patterns (mate-TT, repetition, time mgmt): MEDIUM — patterns are standard chessprogramming.org content; specific V6 audit needed (Open Question 1)
- B2 Pesto baseline values: MEDIUM — values cited from public source but not freshly transcribed; transcription is a Phase 1 plan task
- B3 Fathom integration (CMake recipe + tbconfig.h override): MEDIUM — pattern verified from research bundle, exact API names assumed against jdart1's `tbprobe.h` (Assumption A3)
- Pitfalls and known anti-patterns: HIGH — 44-pitfall research bundle plus direct V6 source audits

**Research date:** 2026-05-15
**Valid until:** 2026-06-14 (30 days — Fathom and pybind11 are stable; Pesto values are reference data; primary risk is V7 source drift after work begins)
