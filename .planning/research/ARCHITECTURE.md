# Architecture Research

**Domain:** V7 chess engine (C++17 pybind11 module, Lazy SMP, Texel-tuned HCE, Syzygy)
**Researched:** 2026-05-15
**Confidence:** HIGH on internal C++ structure / Lazy SMP / Fathom integration; MEDIUM on the Python-side cancellation contract (V6 currently uses an internal C++ `SearchInfo` and ignores the Python-side token — V7 should fix this); HIGH on the integration-points checklist (verified against the existing repo).

---

## 1. System Overview

V7 lives at `src/chess_engine/engine/v7/` and presents the **same external contract as V6**: a `find_best_move(game_state, valid_moves, engine, search_info)` Python function that internally calls a pybind11 C++ module. Internally it is a much larger system.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ EXISTING (unchanged by V7 except for thin adds)                              │
│  React UI ──► FastAPI app.py ──► GameManager ──► algo_v7.find_best_move(...) │
└──────────────────────────────────────────────────────────────────────────────┘
                                                            │
                                                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ V7 PYTHON ADAPTER  (src/chess_engine/engine/v7/)                             │
│  __init__.py          chess_algorithm.py       native_build.py               │
│  (auto-build hook)    (FEN ↔ Move marshalling) (CMake driver, .pyd/.so/.dylib)│
└──────────────────────────────────────────────────────────────────────────────┘
                                                            │ pybind11 boundary
                                                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ V7 NATIVE MODULE  (v7_engine.{pyd,so,dylib})                                 │
│                                                                              │
│  ┌────────────────────────────┐   ┌────────────────────────────────────────┐ │
│  │ BINDINGS LAYER             │   │ TUNE LAYER (optional, same .so)        │ │
│  │ python_bindings.cpp        │   │ tune.cpp  ◄── exposes eval_quiet()/    │ │
│  │  - find_best_move(fen,…)   │   │             gradient hooks for Texel   │ │
│  │  - stop()                  │   └────────────────────────────────────────┘ │
│  │  - perft(), evaluate()     │                                              │
│  └────────────┬───────────────┘                                              │
│               ▼                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ ORCHESTRATION                                                        │   │
│  │  search/thread_pool.cpp   (Lazy SMP master, spawns N std::threads)   │   │
│  │  search/search.cpp        (per-thread iterative deepening)           │   │
│  │  search/search_info.hpp   (atomic stop flag, shared stats, time mgr) │   │
│  └────────────┬─────────────────────────────────────────────────────────┘   │
│               ▼                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ SEARCH SUBSYSTEM            │ EVAL SUBSYSTEM         │ ENDGAME       │   │
│  │  search/alpha_beta.cpp      │  eval/eval.cpp         │  eval/        │   │
│  │  search/quiescence.cpp      │  eval/psqt.cpp         │   endgame.cpp │   │
│  │  search/movepicker.cpp      │  eval/king_safety.cpp  │   (KPK,       │   │
│  │  search/history.cpp         │  eval/pawns.cpp        │    opposition,│   │
│  │  search/see.cpp             │  eval/mobility.cpp     │    fortress)  │   │
│  │  (LMR/null/futility/LMP/    │  eval/coeffs.hpp       │               │   │
│  │   singular/multi-cut/probcut)│ (Texel-tunable consts)│               │   │
│  └────────────┬────────────────┴───────────┬────────────┴───────┬──────┘   │
│               ▼                            ▼                    ▼          │
│  ┌──────────────────┐   ┌────────────────────┐   ┌──────────────────────┐  │
│  │ TT (LOCKLESS)    │   │ BOARD / MOVEGEN    │   │ SYZYGY PROBE         │  │
│  │ search/tt.cpp    │   │ board/board.cpp    │   │ syzygy/syzygy.cpp    │  │
│  │ Hyatt-Mann XOR,  │   │ board/movegen.cpp  │   │ wraps Fathom         │  │
│  │ shared by all    │   │ board/magic.cpp    │   │ tb_probe_root /      │  │
│  │ threads          │   │ board/zobrist.cpp  │   │ tb_probe_wdl         │  │
│  └──────────────────┘   └────────────────────┘   └──────────┬───────────┘  │
│                                                              ▼              │
│                                                    ┌─────────────────────┐  │
│                                                    │ extern/fathom/      │  │
│                                                    │  tbprobe.c          │  │
│                                                    │  + custom tbconfig.h│  │
│                                                    └─────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Boundaries

| Component | Owns | Depends on | Notes |
|---|---|---|---|
| **bindings** (`python_bindings.cpp`) | pybind11 module surface, `SearchInfo` ↔ Python flag bridge | thread_pool, syzygy (init), tt (init) | Releases GIL via `py::gil_scoped_release` for the duration of `find_best_move`; never touches Python objects from worker threads. |
| **thread_pool** (`thread_pool.{hpp,cpp}`) | Lazy SMP coordination, owns N `std::thread`, owns shared `SearchInfo` | search, tt, time manager | Master thread spawns N-1 helper threads, all run iterative deepening on their own private board copy of the root position. |
| **search** (`search.cpp`, `alpha_beta.cpp`, `quiescence.cpp`, `movepicker.cpp`) | Per-thread negamax tree, pruning, extensions | eval, tt, history, syzygy, board | Polls `SearchInfo::stopped` at every node; calls Syzygy probe at root and inside the tree (WDL only deep, DTZ only at root). |
| **history / killers** (`history.{hpp,cpp}`) | Per-thread history heuristic, killers, counter-moves | (none) | **Per-thread** state — drives Lazy SMP divergence. Do NOT share. |
| **eval** (`eval/`, `coeffs.hpp`) | Static evaluation, phase blending, Texel-tunable parameters | board, endgame | All tunable constants live in one place (`coeffs.hpp` or `coeffs.cpp`) so Texel can mutate them. |
| **endgame** (`endgame.cpp`) | KPK bitbases, opposition, fortress hints, phase detection | board | Compile-time KPK table or generated at startup; called from `eval` when phase = endgame. |
| **tt** (`tt.cpp`) | Shared transposition table | (none — leaf) | Lockless via Hyatt-Mann XOR trick. Single allocation, all threads probe/store concurrently. |
| **board / movegen / magic / zobrist** | Board representation, legal moves, attack tables, hashing | (none — leaf) | Inherits V6's magic bitboard implementation; minimal changes expected. |
| **syzygy** (`syzygy.{hpp,cpp}`) | Fathom wrapper, path resolution, init/teardown | board (for piece counts), Fathom C lib | Single TB instance loaded at module init from path provided by Python. |
| **tune** (`tune.cpp`, optional pybind11 export) | Quiet-eval entry point + coefficient getters/setters for Texel | eval | Built into the same `.so` so Python tuner can call `v7_engine.eval_quiet(fen)` and `v7_engine.set_coeffs([...])`. |
| **extern/fathom** | Vendored Fathom source (tbprobe.c + headers + custom tbconfig.h) | (none) | Built as static lib via small wrapper `CMakeLists.txt`, linked into `v7_engine`. |

---

## 3. Recommended File-Level Layout

```
src/chess_engine/engine/v7/
├── __init__.py                  # auto-build trigger (mirrors v6)
├── chess_algorithm.py           # find_best_move adapter (Python ↔ pybind11)
├── native_build.py              # CMake driver — V7-specific copy, NOT shared with v6
├── CMakeLists.txt
├── README.md                    # build instructions, Syzygy download note
├── include/
│   ├── types.hpp                # Move, Square, Color, Piece, Bitboard
│   ├── board.hpp
│   ├── magic.hpp
│   ├── movegen.hpp
│   ├── zobrist.hpp
│   ├── search.hpp
│   ├── search_info.hpp          # atomic stop, time mgr, per-thread stats
│   ├── thread_pool.hpp
│   ├── movepicker.hpp
│   ├── history.hpp              # killers, history, counter-moves (per-thread)
│   ├── see.hpp                  # static exchange eval
│   ├── eval.hpp
│   ├── coeffs.hpp               # all Texel-tunable parameters in one place
│   ├── psqt.hpp
│   ├── king_safety.hpp
│   ├── pawns.hpp
│   ├── mobility.hpp
│   ├── endgame.hpp
│   ├── tt.hpp
│   ├── syzygy.hpp
│   └── tune.hpp                 # Texel-facing exports
├── src/
│   ├── board.cpp
│   ├── magic.cpp
│   ├── movegen.cpp
│   ├── zobrist.cpp
│   ├── search.cpp               # iterative deepening, aspiration windows
│   ├── alpha_beta.cpp           # negamax + LMR/null/futility/LMP/singular/probcut
│   ├── quiescence.cpp
│   ├── movepicker.cpp
│   ├── history.cpp
│   ├── see.cpp
│   ├── thread_pool.cpp          # Lazy SMP master + helpers
│   ├── eval.cpp                 # tapered eval composition
│   ├── coeffs.cpp               # default values for Texel-tunable params
│   ├── psqt.cpp
│   ├── king_safety.cpp
│   ├── pawns.cpp
│   ├── mobility.cpp
│   ├── endgame.cpp              # KPK, opposition, fortress hints
│   ├── tt.cpp                   # Hyatt-Mann XOR lockless TT
│   ├── syzygy.cpp               # Fathom wrapper
│   ├── tune.cpp                 # quiet-eval entry, coeff get/set
│   ├── python_bindings.cpp
│   ├── perft.cpp                # kept from v6 for testing
│   └── bench.cpp                # kept from v6 for benchmarking
├── extern/
│   └── fathom/                  # git submodule of jdart1/Fathom
│       ├── (upstream files)
│       └── CMakeLists.txt       # small wrapper we author
├── overrides/
│   └── tbconfig.h               # custom Fathom config (added to include path BEFORE extern/fathom/src)
├── tools/                       # NOT bundled in the .so
│   ├── texel_tuner.py           # imports v7_engine.eval_quiet, runs gradient
│   ├── download_syzygy.py       # optional helper script
│   └── uci_main.cpp             # standalone UCI binary (separate target)
└── build/                       # gitignored, CMake output
```

### Layout rationale

- **`include/` + `src/` retained from V6** — V6's flat `include/` worked at 7 files; V7 will have ~25 headers but they're still all in one namespace and the search/eval split is conceptual, not modular. Resist deep nesting (`search/`, `eval/` subfolders) — it adds CMake noise without benefit at this scale, and the existing codebase map documents `board / movegen / magic / search / eval / tt / types` as the V6 convention. Stay consistent.
- **`extern/fathom/` as a git submodule, not `FetchContent`** — Syzygy probing is a hard dependency for V7 and Fathom upstream is small (~5 files); a pinned submodule is reproducible offline, while `FetchContent` adds first-build network risk. V6 already uses `FetchContent` for pybind11 (which is much larger and more standard) — that pattern is fine for pybind11 but not for Fathom.
- **`overrides/tbconfig.h`** — standard Fathom integration trick. Fathom includes `tbconfig.h` with angle brackets, so an override directory placed earlier in the include path silently replaces it. Lets us define `TB_KING_ATTACKS`, `TB_KNIGHT_ATTACKS`, etc., in terms of V7's own magic bitboards so we don't carry duplicate attack tables.
- **`tune.cpp` inside the same `.so`** — exposing `eval_quiet(fen) → int` and `set_coeffs(list)` from the same module avoids a subprocess boundary and means Texel can run a million evals/second from Python. The alternative (external binary reading a coefficient header at startup) requires a recompile per iteration, which is intolerable for Texel's gradient loop.
- **`tools/uci_main.cpp` as a separate CMake target** — fastchess and other gauntlet tools speak UCI, not pybind11. A second CMake target (`add_executable(v7_uci tools/uci_main.cpp $<TARGET_OBJECTS:v7_core>)`) gives us a UCI binary "for free" by linking the same object library used by the pybind11 module.
- **`native_build.py` — V7-specific copy, not shared** — V6's script is 167 lines and hard-codes `MODULE_PREFIX = "v6_engine"`, `V6_DIR`, etc. Trying to parameterize it for both V6 and V7 introduces import-time coupling between two engines that should remain independent. Copy + rename (`v6_engine` → `v7_engine`, `V6_DIR` → `V7_DIR`, `V6BuildError` → `V7BuildError`); the duplication is a one-time cost. **Do not factor a shared `_native_build_base.py`** — that's exactly the kind of cross-engine coupling the existing codebase concerns flag.

---

## 4. Architectural Patterns

### Pattern 1: Lazy SMP master/helper with shared lockless TT

**What:** N `std::thread` workers, each running iterative deepening from the root with its own board copy and its own history/killers. They communicate exclusively via the shared TT.

**When to use:** Always for V7's parallel search (this is the milestone's choice).

**Trade-offs:**
- (+) ~100 Elo for free at 4 threads, scales reasonably to 16. ([Shared Hash Table](https://www.chessprogramming.org/Shared_Hash_Table))
- (+) Very little code change vs single-threaded — main complexity is the thread pool and lockless TT.
- (−) Non-deterministic results (same position, same time → different best move possible). Mitigation: bench with fixed depth, not fixed time.
- (−) NPS sublinear in thread count due to TT contention; NPS-per-thread drops as N grows.

**Sketch:**
```cpp
// thread_pool.cpp
SearchResult ThreadPool::search(const Board& root, int time_ms, int n) {
    info_.reset();
    info_.time_limit_ms = time_ms;
    info_.start_time = clock::now();
    workers_.clear();
    for (int i = 1; i < n; ++i) {
        workers_.emplace_back([this, root, i] {     // copy of root
            Board b = root;
            iterative_deepening(b, info_, /*helper=*/true, /*tid=*/i);
        });
    }
    Board b = root;
    SearchResult r = iterative_deepening(b, info_, /*helper=*/false, /*tid=*/0);
    info_.stopped.store(true);                       // signal helpers
    for (auto& t : workers_) t.join();
    return r;
}
```

### Pattern 2: Hyatt-Mann lockless TT

**What:** Store `key XOR data` instead of `key`. Probe XORs back and verifies. Torn writes produce a key mismatch and are silently rejected. ([Hyatt & Mann 2002](https://www.chessprogramming.org/Shared_Hash_Table))

**When to use:** Always once threads > 1.

**Trade-offs:**
- (+) Zero locks, zero space overhead, two-line code change vs single-threaded TT.
- (−) Probabilistic — undetected corruption possible at the rate of natural Zobrist collisions, which is empirically tolerable.
- (!) **V6 currently has a single-threaded TT despite OpenMP search** — this is a latent bug under contention. V7 must rewrite (not "evolve in place") because the entry layout changes (key field becomes `key ^ packed_data`).

**Sketch:**
```cpp
// tt.cpp
struct TTEntry {
    std::atomic<uint64_t> xkey;   // = key ^ data
    std::atomic<uint64_t> data;   // packed: move | score | depth | flag | age
};
void store(uint64_t key, uint64_t data) {
    auto& e = table[key & mask];
    e.xkey.store(key ^ data, std::memory_order_relaxed);
    e.data.store(data,        std::memory_order_relaxed);
}
bool probe(uint64_t key, uint64_t& out) {
    auto& e = table[key & mask];
    uint64_t d = e.data.load(std::memory_order_relaxed);
    if (e.xkey.load(std::memory_order_relaxed) == (key ^ d)) { out = d; return true; }
    return false;
}
```

### Pattern 3: Cooperative cancellation across the GIL boundary

**What:** Python's `SearchInfo.stop_requested` (existing dataclass in `core/search_info.py` per the codebase map) must propagate to all C++ search threads.

**When to use:** Required by the V7 milestone (preserve cancellation contract).

**The problem:** V6's binding (`python_bindings.cpp:22-41`) **ignores** the Python `search_info` argument entirely and constructs its own internal C++ `SearchInfo` from scratch — meaning V6's `/api/stop` button only works because `GameManager.stop_search` flips a Python-side flag that nothing reads on the V6 path. (V6 does have `info.stopped` internally, but Python can't reach it.) V7 must close this gap.

**Recommended pattern:**

```cpp
// python_bindings.cpp
class V7Engine {
    std::atomic<bool> stop_{false};
    ThreadPool pool_;
public:
    py::tuple find_best_move(const std::string& fen, int ms, int threads) {
        stop_.store(false);
        Board b; b.from_fen(fen);
        SearchResult r;
        {
            py::gil_scoped_release no_gil;            // workers may not touch Python
            r = pool_.search(b, ms, threads, stop_);  // pool wires stop_ into SearchInfo
        }
        return py::make_tuple(move_to_string(r.best_move), r.score, r.depth, r.nodes, r.nps());
    }
    void stop() { stop_.store(true); }                // cheap, GIL-held
};
PYBIND11_MODULE(v7_engine, m) {
    py::class_<V7Engine>(m, "V7Engine")
        .def(py::init<>())
        .def("find_best_move", &V7Engine::find_best_move,
             py::call_guard<py::gil_scoped_release>())   // belt-and-suspenders
        .def("stop", &V7Engine::stop);
}
```

Python adapter then holds a process-level `_engine = v7_engine.V7Engine()` instance, and `chess_algorithm.find_best_move` polls `search_info.stop_requested` in a sentinel thread that calls `_engine.stop()` if set — OR (cleaner) `GameManager.stop_search` calls `algo_v7.stop()` directly. The `py::gil_scoped_release` is critical because the worker threads may NOT acquire the GIL — they only touch C++ state. ([pybind11 docs — Misc / GIL](https://pybind11.readthedocs.io/en/stable/advanced/misc.html))

**Trade-offs:**
- (+) Standard pattern, well-documented in pybind11 community.
- (+) Stateful `V7Engine` object also lets us persist the TT across moves (huge Elo win — V6 currently rebuilds TT per move).
- (−) Singleton-ish at the Python adapter level; need to be careful about reentrancy if the FastAPI app ever processes overlapping AI move requests (today it doesn't — `GameManager` is single-game).

### Pattern 4: Texel coefficients in a single header + module export

**What:** All tunable eval parameters live in `coeffs.cpp` (defined non-`constexpr` so they can be mutated at runtime), declared `extern` in `coeffs.hpp`. The pybind11 module exports `get_coeff(name)`, `set_coeff(name, value)`, and `eval_quiet(fen)`. The Texel tuner script is pure Python: it loads the Zurichess EPD, computes the gradient by finite-differences against `eval_quiet`, and writes the converged values to a JSON file the next build embeds.

**When to use:** Required for any tuning workflow that wants more than one iteration per recompile.

**Trade-offs:**
- (+) Tuner runs ~10⁵ positions/sec without a process boundary.
- (+) Final values live in source (committed JSON → C++ initializer at build time), so distribution is unchanged.
- (−) Coefficients are no longer `constexpr` → small loss of compiler optimization in eval. Acceptable; gain from tuning swamps it.

---

## 5. Data Flow

### Request flow under Lazy SMP

```
[POST /api/ai-move]
    ↓
[FastAPI handler] ── (request thread, sync) ──► [GameManager.ai_move]
                                                     │
                                                     ▼
[GameManager constructs SearchInfo]
[GameManager calls algo_v7.find_best_move(gs, valid_moves, "v7", search_info)]
    ↓
[chess_algorithm.py]:
  1. (optional) opening book lookup
  2. fen = gs.get_fen()
  3. spawn watchdog thread that polls search_info.stop_requested
       and calls _engine.stop() when set
  4. (move_str, score, depth, nodes, nps) = _engine.find_best_move(fen, ms, threads)
    ↓
[python_bindings.cpp::find_best_move]:
  py::gil_scoped_release  ← GIL DROPPED HERE
  pool.search(board, ms, threads, stop_atomic)
    ↓
[thread_pool.cpp::search]:
                  ┌─────────────────────────────────────┐
  spawns N-1 ─►  │ helper threads: iterative_deepening │  shared TT (lockless)
  std::thread    │ each with own Board copy +          │  ◄── all probe/store
                 │ own history / killers               │
                 └─────────────────────────────────────┘
  master thread also runs iterative_deepening
                  │
                  ▼
[search.cpp::iterative_deepening]:
  for depth = 1..MAX:
    if info.stopped.load() break          ← polls stop atomic
    score = aspiration_search(depth)
    update info.best_move
    if syzygy_root_hit: break             ← short-circuits if TB-resolvable
    ↓
[alpha_beta.cpp::search]:
  every node:
    if (++info.nodes & 4095) == 0 && info.check_time() return 0
    tt_probe                              ← shared TT
    null move? futility? LMP? RFP?
    move loop (movepicker order):
      see prune?
      lmr reduction?
      recurse
    tt_store                              ← shared TT (XOR'd key)
    ↓
[returns SearchResult]
    ↓
[python_bindings] reacquires GIL implicitly on scope exit, returns tuple
    ↓
[chess_algorithm.py] joins watchdog, matches move_str → V3 Move object, returns
    ↓
[GameManager] applies move, updates SAN history, returns state
    ↓
[FastAPI] serializes JSON, returns to React UI
```

### Key invariants

1. **No worker thread ever touches a Python object.** The GIL is released for the whole search; workers only manipulate C++ state. This is what makes Lazy SMP actually parallel under CPython. ([Octavi Font — pybind11 multithreading](https://octavifs.com/post/pybind11-multithreading-parallellism-python/))
2. **Stop signal is a single `std::atomic<bool>`** owned by the binding object, observed by every worker through `SearchInfo`. Writes from Python (via `engine.stop()`) are observed by workers within one node-poll interval (typically <1ms).
3. **TT survives across `find_best_move` calls** because the `V7Engine` instance is a process-singleton at the Python adapter layer. Aging field in TT entries handles staleness across moves.
4. **Per-thread state never crosses thread boundaries.** History tables, killers, the search stack, and the board copy are all stack/heap allocations owned by one thread.

---

## 6. Integration Points (Outside `src/chess_engine/engine/v7/`)

These are every place outside the V7 module that must change. Verified against the actual repo state.

| File | Change | Why |
|---|---|---|
| `src/chess_engine/server/game_manager.py` | (1) Add `from chess_engine.engine.v7 import chess_algorithm as algo_v7` (line ~11); (2) add `"v7"` to `AVAILABLE_ENGINES` (line ~24); (3) add `if ver == "v7": algo_v7.ensure_available(auto_build=True)` in `set_engine_version` (mirroring v6 at lines 47–50); (4) add `elif current_engine == "v7":` branch in `ai_move` (after the v6 branch at line ~353) — must construct/pass the `current_search_info` so cancellation works (V6 doesn't, V7 fixes this). | Engine ladder is the documented anti-pattern but not in scope to fix this milestone. |
| `client/src/App.jsx` | Add two `<option value="v7">` entries — one to the white selector (around line 408) and one to the black selector (around line 423). Update the `if (ver === "v6")` "build may take a while" warning at line 235 to also fire for `"v7"`. | The frontend has no API call enumerating engines; the dropdown options are hardcoded JSX. **No new API endpoint needed** — the existing `/api/engine` accepts any version string `GameManager` accepts. |
| `cli/src/config.js` | Add new keys to `DEFAULT_CONFIG`: `v7Built: false`, `syzygyPath: null`, `syzygyMaxPieces: 6`. | Config schema lives here; persisted to `.chess-engine.json` per `INTEGRATIONS.md`. |
| `cli/src/index.js` | Add `chess-engine build v7` subcommand (mirrors existing v6 build command) that invokes `python -m chess_engine.engine.v7.native_build`. Optionally add `chess-engine syzygy download <path>` driving `tools/download_syzygy.py`. | Existing CLI already has `build v6`; pattern is one-to-one. |
| `pyproject.toml` | No changes required for runtime (V7 uses the same `pybind11` build extra V6 already declares). Optionally add a `[project.scripts]` entry for the Texel tuner (`chess-engine-tune-v7 = "chess_engine.engine.v7.tools.texel_tuner:main"`). | Build dependencies are unchanged. |
| `.gitignore` | Add `src/chess_engine/engine/v7/build/`, `src/chess_engine/engine/v7/v7_engine*.so`, `*.pyd`, `*.dylib` (mirroring whatever exclusion v6 has). | Build artifacts must not be committed. |
| `.gitmodules` (new) | Register `src/chess_engine/engine/v7/extern/fathom` → `https://github.com/jdart1/Fathom` at a pinned commit. | Submodule for Syzygy probing. |
| `tests/` | Add `tests/test_v7_engine.py` — perft sanity, TT correctness under threads, Syzygy probe smoke test, Texel `eval_quiet` round-trip. | Existing test layout per `STRUCTURE.md`. |
| `README.md` | Brief V7 section: how to build, optional Syzygy download note, threads config. | Documentation hygiene. |
| `src/chess_engine/server/app.py` | **No changes.** `/api/engine` is generic; `/api/ai-move` calls `gm.ai_move()` which dispatches; no V6-specific endpoint exists. Confirmed. | — |
| `chess-ui/src/CustomBoard.jsx` and other client files | **No changes.** Only `App.jsx` references engine names. | — |

### Tablebase storage path

Decision: **store in the user's home directory by default, configurable via `.chess-engine.json`**.

- Config key: `syzygyPath` (string, nullable). Default `null` → V7 starts with TBs disabled.
- Suggested platform defaults the download script offers (NOT auto-applied):
  - Linux/macOS: `~/.local/share/chess-engine/syzygy/`
  - Windows: `%LOCALAPPDATA%\chess-engine\syzygy\`
- The `chess-engine syzygy download` CLI command resolves the path, downloads (or rsyncs from lichess mirrors) the user-chosen man-count (default 5), and writes the path back into `.chess-engine.json`.
- `algo_v7.find_best_move` reads `syzygyPath` from config at first call and passes it to `_engine.set_syzygy_path(...)` exactly once per process.

---

## 7. Cancellation + Threading Interaction (Detailed)

### The core question

V6's existing `SearchInfo` (`src/chess_engine/core/search_info.py` per the codebase map; the actual file appears not to be at that exact path but the pattern is documented) is a Python object with a `stop_requested` flag (or `stopped` per the V6 binding). With Lazy SMP spawning 4–16 C++ threads, how do they observe the Python flag?

### The answer

**They don't directly.** The Python flag lives on the Python side; C++ threads observe a sibling `std::atomic<bool>` that the pybind11 binding flips on demand.

```
Python side                 Binding boundary             C++ side
───────────                 ────────────────             ────────
SearchInfo.stop_requested  ◄── Python sets ──►  V7Engine.stop_atomic ◄── workers poll ──► break
        │
        └── poller thread ──► engine.stop() ──┘
            (or GameManager.stop_search calls algo_v7.stop directly)
```

There are two reasonable wirings:

1. **GameManager-direct wiring (preferred, simpler):**
   When `GameManager.stop_search()` runs, after setting `current_search_info.stopped = True` it also calls `algo_v7.stop()` if the active engine is V7. This adds 3 lines to `GameManager.stop_search` but no threads.

2. **Watchdog thread wiring (more general):**
   `algo_v7.find_best_move` spawns a tiny Python `threading.Thread` that polls `search_info.stop_requested` every 50ms and calls `_engine.stop()` if set. More general (works without modifying GameManager beyond the dispatch ladder) but adds a thread per AI move.

**Recommendation: option 1.** GameManager already has special-case branches per engine (the documented anti-pattern); adding a `if current_engine == "v7": algo_v7.stop()` line in `stop_search` is consistent with the existing pattern and avoids the watchdog thread.

### GIL interaction

- **`find_best_move` releases the GIL via `py::gil_scoped_release`** for the entire search duration. All N C++ worker threads therefore run truly in parallel, no GIL contention. ([pybind11 GIL docs](https://pybind11.readthedocs.io/en/stable/advanced/misc.html))
- **Worker threads must NEVER acquire the GIL.** They only touch C++ state (board copies, TT, history). If they ever need to log to Python, do it via a thread-safe C++ buffer flushed by the main thread after `pool.search()` returns.
- **`engine.stop()` does NOT release the GIL** — it just stores into an atomic, returns immediately. Cheap and safe to call from a Python request handler.
- **No nested GIL issue** because FastAPI's request thread holds the GIL only outside `pool.search()`. While search runs, the request thread is blocked in C++ with the GIL released; another Python thread (the FastAPI ThreadPoolExecutor handling `/api/stop`) can run, acquire the GIL, and call `engine.stop()`.

### FastAPI thread + V7 worker threads

FastAPI runs sync handlers in a `ThreadPoolExecutor`. So:

- `/api/ai-move` handler thread → calls `pool.search()` → blocks → spawns N C++ workers → all run in parallel.
- `/api/stop` handler thread → runs concurrently because the AI thread released the GIL → calls `gm.stop_search()` → flips Python flag + calls `algo_v7.stop()` → atomic store observed by C++ workers within ~1ms (next node poll).
- After search: C++ workers join, master returns, `gil_scoped_release` destructor reacquires GIL, binding returns the tuple. Clean.

**The only real concern is the `gil_scoped_release` daemon-thread crash documented in pybind11 issue [#2215](https://github.com/pybind/pybind11/issues/2215)** — if the Python interpreter shuts down mid-search (e.g., Ctrl-C uvicorn), `gil_scoped_release`'s destructor may segfault. Mitigation: register an atexit hook that calls `_engine.stop()` and waits briefly. Acceptable risk for a local dev tool.

---

## 8. Build Order & Parallelizable Subsystems

The phase roadmap should respect these dependency edges. Each row is a unit that can be built and tested in isolation; rows in the same group are parallelizable.

| Group | Subsystem | Depends on | Parallelizable with | Smoke test |
|---|---|---|---|---|
| **A1** | Module skeleton (CMakeLists.txt, native_build.py, __init__.py, chess_algorithm.py, python_bindings.cpp returning random move) | — (just fork v6) | — | `find_best_move(fen)` returns *some* legal move |
| **A2** | Board + movegen + magic + zobrist | A1 | — | Perft matches V6 perft to depth 6 |
| **B1** | Sequential search (negamax + qsearch + TT + iterative deepening) | A2 | B2, B3 | V7 (1 thread) plays a legal game vs V6 |
| **B2** | Eval rewrite (PSTs + king safety + pawn structure + mobility + tapered eval + coeffs.hpp scaffolding) | A2 | B1, B3 | `evaluate(starting_pos) == 0`; symmetry tests pass |
| **B3** | Syzygy integration (Fathom vendor + tbconfig.h + syzygy.cpp wrapper) | A2 | B1, B2 | `syzygy.probe_root` returns correct WDL for KRk position |
| **C1** | **MILESTONE: V7 plays a game (single-thread, classical eval, optional Syzygy)** | B1 + B2 + B3 | — | `/api/engine` accepts "v7", a UI battle V7 vs V6 completes |
| **D1** | Lockless TT (rewrite tt.cpp with Hyatt-Mann XOR) | C1 | D2, D3 | TT correctness test under 8 threads (no torn-data bugs) |
| **D2** | Search refinements (LMR, null-move tuning, futility, LMP, singular extensions, multi-cut, probcut) | C1 | D1, D3 | Strength gain vs C1 baseline at fixed depth |
| **D3** | Endgame eval (KPK, opposition, fortress, phase detection) | C1 | D1, D2 | KPK positions solved; bishops-of-opposite-color drawn correctly |
| **E1** | Lazy SMP thread pool (thread_pool.cpp, per-thread history/killers, GIL release in bindings, cancellation atomic wired to Python) | D1 | E2 | NPS scales >2× from 1 → 4 threads; `/api/stop` cancels promptly |
| **E2** | Texel tuning pipeline (tune.cpp exports, texel_tuner.py, Zurichess loader, gradient loop, JSON → C++ codegen) | B2 + C1 | E1 | One full tuning iteration produces non-default coeffs JSON |
| **F1** | Gauntlet harness (UCI binary tools/uci_main.cpp, fastchess invocation script, result aggregator) | C1 | — | V7-default vs V6 mini-gauntlet (e.g., 50 games) reports a pentanomial |
| **G1** | **SHIP MILESTONE: V7-tuned vs V6 gauntlet shows meaningful Elo gain** | E1 + E2 + F1 | — | Gauntlet result is the explicit ship signal in PROJECT.md |

### Critical path

```
A1 → A2 → (B1 ∥ B2 ∥ B3) → C1 → (D1 ∥ D2 ∥ D3) → (E1 ∥ E2) → F1 → G1
```

The **C1 milestone (V7 plays a legal game end-to-end)** is the minimum viable smoke. After C1, every later subsystem can be developed and gauntleted independently against the C1 baseline. Phases D and E especially can run in parallel since they touch disjoint files (D1/D2 in `search/` and `tt.cpp`; D3 in `endgame.cpp`; E1 in `thread_pool.cpp`/`bindings.cpp`; E2 in `tune.cpp`/Python tools).

### What can be flagged as "may need its own research phase"

- **D1 (lockless TT):** torn-data behavior under concurrent stores has subtle correctness edges; the Hyatt-Mann scheme is well-understood but the entry packing layout is a new design decision.
- **D3 (endgame eval):** KPK bitbase generation vs lookup table choice has Elo + binary-size implications worth a focused investigation.
- **E2 (Texel):** the gradient method (finite-difference vs analytic), step size, K-tuning, and convergence criteria are all decisions that benefit from a phase-local research pass before coding.

The other phases are mechanical applications of well-documented techniques and shouldn't need fresh research at phase time.

---

## 9. Anti-Patterns to Avoid

### Anti-Pattern 1: Sharing the V6 `tt.cpp` between V6 and V7

**What people do:** Refactor `tt.cpp` to a shared utility. **Why wrong:** V6's TT is single-threaded; V7's must be lockless. They're fundamentally different data structures masquerading as the same name. **Do instead:** Copy V6's `tt.cpp` into V7 and rewrite. V6 is frozen; the duplication is one-time.

### Anti-Pattern 2: Launching threads with `std::thread` while still holding the GIL

**What people do:** Forget `py::gil_scoped_release` because "the C++ code doesn't touch Python." **Why wrong:** Without releasing, every `std::thread::join` waits while the GIL is held → other Python threads (including the `/api/stop` handler) can't run → cancellation appears broken. **Do instead:** Always wrap the entire blocking C++ region in `py::gil_scoped_release` (either via `call_guard` or scoped object). ([pybind11 issue #1446](https://github.com/pybind/pybind11/issues/1446))

### Anti-Pattern 3: Sharing history/killer tables across Lazy SMP threads

**What people do:** "TT is shared, so why not history too?" **Why wrong:** Shared history defeats the divergence that makes Lazy SMP work — threads converge to the same lines and stop covering more of the tree. **Do instead:** History, killers, counter-moves, and continuation-history are strictly per-thread. Only the TT is shared.

### Anti-Pattern 4: Storing Texel coefficients as `constexpr`

**What people do:** Keep eval constants `constexpr` for compiler optimization. **Why wrong:** Texel needs to mutate them at runtime; `constexpr` forces a recompile per gradient step (~1000× slower). **Do instead:** Plain `extern` ints/arrays in `coeffs.cpp`. Compiler optimization loss is ~1–2% NPS, gain from tuning is much more.

### Anti-Pattern 5: Using `FetchContent` for Fathom

**What people do:** Mirror V6's `FetchContent` pybind11 pattern for Fathom. **Why wrong:** Fathom is small, rarely changes, and tablebase probing is a hard build dependency for V7 — first-build network failure is unacceptable. `FetchContent` for pybind11 is fine because pybind11 is also commonly installed via pip. **Do instead:** Vendor Fathom as a git submodule pinned to a specific commit. ([jdart1/Fathom](https://github.com/jdart1/Fathom))

### Anti-Pattern 6: Constructing a fresh `V7Engine` per `find_best_move` call

**What people do:** Build the engine object inside the function for "isolation." **Why wrong:** TT is rebuilt every move, losing the cross-move learning that gives ~30 Elo. **Do instead:** Module-level singleton in `chess_algorithm.py`, persists for the process lifetime.

### Anti-Pattern 7: Hard-coding Syzygy path in C++

**What people do:** `#define SYZYGY_PATH "/home/me/syzygy"` in the source. **Why wrong:** Breaks reproducible builds and forces per-user recompiles. **Do instead:** Pass path from Python (read from `.chess-engine.json`); call `_engine.set_syzygy_path(...)` once at startup; Fathom's `tb_init(path)` is the entry point.

---

## 10. Build-System Specifics

A few discrete decisions that matter for the V7 `CMakeLists.txt`:

- **Target naming:** `v7_engine` (Python module), `v7_core` (object library used by both module and UCI binary), `v7_uci` (executable), `fathom` (vendored static lib). Clean separation lets the UCI binary skip pybind11.
- **Install paths:** `pybind11_add_module(... NO_EXTRAS)` if needed to avoid pybind11 stripping `RTLD_LAZY` symbols; in practice V6's defaults work, V7 inherits.
- **RPATH on macOS:** pybind11 modules need `INSTALL_RPATH "@loader_path"` if you ever link a separate `.dylib` (we don't — everything's static into the module). No change vs V6.
- **`.pyd` vs `.so` suffix:** pybind11's `pybind11_add_module` handles this automatically (uses `Python3_MODULE_EXTENSION`). V6's `native_build.py` already searches for `.pyd` on Windows, `.so` on Linux, `.so`/`.dylib` on macOS — the V7 copy inherits this behavior unchanged.
- **Build types:** Force `Release` by default exactly as V6 does (lines 9–11 of V6 CMakeLists.txt). Add a `V7_LTO` option for `INTERPROCEDURAL_OPTIMIZATION` — measurable NPS win on GCC/Clang.
- **OpenMP:** Drop it. V7 uses `std::thread` for Lazy SMP; OpenMP was V6's parallel approach but `std::thread` gives explicit control over thread lifetime that the cancellation contract requires. Keep `find_package(OpenMP QUIET)` out of V7.
- **Standard:** C++17 (matches V6). `std::atomic<uint64_t>::is_always_lock_free` is available — assert it at compile time so we fail loud on weird platforms.

---

## 11. Quality Gate Verification

- [x] **Components clearly defined with boundaries** — see §2 (table of 11 components, each with explicit owns/depends-on).
- [x] **Data flow direction explicit (under Lazy SMP)** — see §5 (request flow diagram + 4 invariants).
- [x] **Build order implications noted, with parallelizable subsystems flagged** — see §8 (dependency table + critical-path diagram + parallelism callouts).
- [x] **Integration points outside the V7 module enumerated explicitly** — see §6 (10-row file-by-file change table, all paths verified against the actual repo).
- [x] **Python/C++ GIL + threading interaction addressed** — see §7 (cancellation wiring, GIL release, FastAPI thread interaction, daemon-thread crash mitigation).

---

## Sources

- [Shared Hash Table — Chessprogramming wiki](https://www.chessprogramming.org/Shared_Hash_Table) — Hyatt-Mann XOR trick canonical reference (HIGH)
- [Lazy SMP and "lazy cluster" experiments — TalkChess](https://talkchess.com/viewtopic.php?t=64824) — empirical Elo gains, locking-vs-lockless tradeoffs (HIGH)
- [Transposition table and multithreaded search — TalkChess](https://talkchess.com/viewtopic.php?t=76483) — practitioner notes on TT + threads (MEDIUM)
- [Lockless Transposition Tables — Binary Debt](https://binarydebt.wordpress.com/2013/09/29/lockless-transposition-tables/) — code-level walkthrough of the XOR scheme (MEDIUM)
- [pybind11 docs — Miscellaneous (GIL section)](https://pybind11.readthedocs.io/en/stable/advanced/misc.html) — official `gil_scoped_release` / `gil_scoped_acquire` reference (HIGH)
- [pybind11 issue #1446 — Blocking destructors and the GIL](https://github.com/pybind/pybind11/issues/1446) — Worker + atomic flag + join deadlock pattern (HIGH)
- [pybind11 issue #2215 — gil_scoped_release in daemon threads](https://github.com/pybind/pybind11/issues/2215) — interpreter-shutdown crash mitigation (MEDIUM)
- [pybind11 multithreading parallelism in Python — Octavi Font](https://octavifs.com/post/pybind11-multithreading-parallellism-python/) — measured 24-thread scaling with/without GIL release (MEDIUM)
- [jdart1/Fathom — maintained Syzygy probing library](https://github.com/jdart1/Fathom) — primary integration target (HIGH)
- [basil00/Fathom — original Fathom](https://github.com/basil00/Fathom) — historical reference (HIGH)
- [Fathom README — tbconfig.h override mechanism](https://github.com/jdart1/Fathom/blob/master/README.md) — official integration recipe (HIGH)
- `.planning/codebase/ARCHITECTURE.md` — V6 layered architecture, anti-patterns (HIGH, in-repo)
- `.planning/codebase/STRUCTURE.md` — engine subpackage layout convention (HIGH, in-repo)
- `.planning/codebase/INTEGRATIONS.md` — `.chess-engine.json` schema, native build chain (HIGH, in-repo)
- `src/chess_engine/engine/v6/CMakeLists.txt`, `native_build.py`, `python_bindings.cpp`, `include/search.hpp` — V6 reference for the patterns V7 inherits or replaces (HIGH, in-repo)
- `src/chess_engine/server/game_manager.py`, `client/src/App.jsx`, `cli/src/config.js` — verified integration touch-points (HIGH, in-repo)

---
*Architecture research for: V7 native chess engine module*
*Researched: 2026-05-15*
