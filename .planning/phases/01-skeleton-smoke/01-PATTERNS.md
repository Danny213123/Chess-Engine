# Phase 1: Skeleton + Smoke - Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** 24 new/modified files
**Analogs found:** 22 / 24 (2 net-new with partial analogs only — `coeffs.json` and `tools/gen_coeffs.py`)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/chess_engine/engine/v7/__init__.py` | package-init | n/a | `src/chess_engine/engine/v6/__init__.py` | exact |
| `src/chess_engine/engine/v7/chess_algorithm.py` | adapter | request-response | `src/chess_engine/engine/v6/chess_algorithm.py` | exact |
| `src/chess_engine/engine/v7/native_build.py` | build-driver | batch | `src/chess_engine/engine/v6/native_build.py` | exact |
| `src/chess_engine/engine/v7/CMakeLists.txt` | build-config | n/a | `src/chess_engine/engine/v6/CMakeLists.txt` | exact (with additions) |
| `src/chess_engine/engine/v7/include/board.hpp` | C++ header | n/a | `src/chess_engine/engine/v6/include/board.hpp` | exact (fork) |
| `src/chess_engine/engine/v7/include/movegen.hpp` | C++ header | n/a | `src/chess_engine/engine/v6/include/movegen.hpp` | exact (fork) |
| `src/chess_engine/engine/v7/include/magic.hpp` | C++ header | n/a | `src/chess_engine/engine/v6/include/magic.hpp` | exact (fork) |
| `src/chess_engine/engine/v7/include/zobrist.hpp` | C++ header | n/a | (inline in `v6/include/board.hpp` `types.hpp`) | partial |
| `src/chess_engine/engine/v7/include/tt.hpp` | C++ header | CRUD | `src/chess_engine/engine/v6/include/tt.hpp` | exact (fork) |
| `src/chess_engine/engine/v7/include/eval.hpp` | C++ header | transform | `src/chess_engine/engine/v6/include/eval.hpp` | exact (modified to read coeffs:: externs) |
| `src/chess_engine/engine/v7/include/search.hpp` | C++ header | event-driven | `src/chess_engine/engine/v6/include/search.hpp` | exact (modified — wire external stop) |
| `src/chess_engine/engine/v7/include/coeffs.hpp` | C++ header | n/a | none | NO ANALOG (net-new) |
| `src/chess_engine/engine/v7/include/syzygy.hpp` | C++ header | request-response | none | NO ANALOG (Fathom wrapper, net-new) |
| `src/chess_engine/engine/v7/include/tbconfig.h` | C++ header (override) | n/a | none | NO ANALOG (Fathom override pattern) |
| `src/chess_engine/engine/v7/src/board.cpp` etc. | C++ impl | n/a | `src/chess_engine/engine/v6/src/*.cpp` | exact (fork) |
| `src/chess_engine/engine/v7/src/search.cpp` | C++ search | event-driven | `src/chess_engine/engine/v6/src/search.cpp` | exact + 4 fixes (mate-TT, repetition, time-mgmt, asp cap) |
| `src/chess_engine/engine/v7/src/eval.cpp` | C++ eval | transform | `src/chess_engine/engine/v6/src/eval.cpp` | exact + coeffs:: indirection |
| `src/chess_engine/engine/v7/src/python_bindings.cpp` | binding | request-response | `src/chess_engine/engine/v6/src/python_bindings.cpp` | counter-example (REWRITE) |
| `src/chess_engine/engine/v7/src/syzygy.cpp` | C++ probe wrapper | request-response | none | NO ANALOG (net-new) |
| `src/chess_engine/engine/v7/src/uci_main.cpp` | C++ executable | streaming (stdio) | none in repo | NO ANALOG (net-new; standard UCI loop) |
| `src/chess_engine/engine/v7/src/coeffs.cpp` | C++ generated TU | n/a | none | GENERATED (not committed) |
| `src/chess_engine/engine/v7/coeffs.json` | data | n/a | none | NO ANALOG (net-new SoT) |
| `src/chess_engine/engine/v7/tools/gen_coeffs.py` | codegen | transform | none | NO ANALOG (net-new) |
| `src/chess_engine/server/game_manager.py` | controller | request-response | self (V6 branch at line 353-364) | exact (extend ladder) |
| `client/src/App.jsx` | React component | event-driven | self (V6 dropdown at 408/423, warning at 235) | exact (extend) |
| `cli/src/config.js` | config | n/a | self (line 12-20 DEFAULT_CONFIG) | exact (extend) |
| `cli/src/index.js` | CLI | batch | self (`buildV6` at 148, `build` case at 460-468) | exact (extend) |
| `tests/test_v7_engine.py` etc. | test | n/a | `tests/test_v6_native.py` | exact |
| `.gitignore`, `.gitmodules` | config | n/a | self | extend |

## Pattern Assignments

---

### `src/chess_engine/engine/v7/__init__.py` (package-init)

**Analog:** `src/chess_engine/engine/v6/__init__.py`

**Full contents (1 line):**
```python
# V6 Python package marker
```

V7 mirrors verbatim — change comment to `# V7 Python package marker`. All actual loading lives in `chess_algorithm.py` (per V6 pattern).

---

### `src/chess_engine/engine/v7/chess_algorithm.py` (adapter, request-response)

**Analog:** `src/chess_engine/engine/v6/chess_algorithm.py`

**Loader pattern** (V6 lines 17-58):
```python
v6_engine = None
V6_AVAILABLE = False
_LOAD_ERROR = None
_AUTO_BUILD_ATTEMPTED = False


def _load_v6_engine():
    try:
        import v6_engine
        return v6_engine
    except ImportError as original_error:
        v6_dir = Path(__file__).resolve().parent
        for module_path in v6_dir.glob("v6_engine*"):
            if module_path.suffix not in {".so", ".pyd", ".dylib"}:
                continue
            spec = importlib.util.spec_from_file_location("v6_engine", module_path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules["v6_engine"] = module
            spec.loader.exec_module(module)
            return module
        raise original_error


def reload_engine():
    global V6_AVAILABLE, _LOAD_ERROR, v6_engine
    try:
        v6_engine = _load_v6_engine()
        V6_AVAILABLE = True
        _LOAD_ERROR = None
        return v6_engine
    except Exception as error:
        v6_engine = None
        V6_AVAILABLE = False
        _LOAD_ERROR = error
        return None
```

**Auto-build pattern** (V6 lines 61-90, INT-09):
```python
def ensure_available(auto_build=False):
    global _AUTO_BUILD_ATTEMPTED
    if V6_AVAILABLE and v6_engine is not None:
        return v6_engine
    module = reload_engine()
    if module is not None:
        return module
    if auto_build and not _AUTO_BUILD_ATTEMPTED:
        _AUTO_BUILD_ATTEMPTED = True
        from chess_engine.engine.v6.native_build import V6BuildError, build_v6_native
        try:
            build_v6_native(force=True)
        except V6BuildError as error:
            raise V6UnavailableError(str(error)) from error
        module = reload_engine()
        if module is not None:
            return module
    detail = f": {_LOAD_ERROR}" if _LOAD_ERROR else ""
    raise V6UnavailableError(
        "V6 native engine is not available. Build it with "
        "`node cli/bin/chess-engine.js build v6` or select V6 again after "
        f"installing CMake and a C++17 compiler{detail}."
    )
```

**Module-load smoke print** (V6 lines 93-96):
```python
if reload_engine() is not None:
    print("[V6] C++ Engine loaded successfully!")
else:
    print(f"[V6] Warning: v6_engine module not found ({_LOAD_ERROR}). Run CMake build.")
```

**Adapter contract** (V6 lines 108-189, FOUND-03):
```python
def find_best_move(game_state, valid_moves, engine, search_info=None):
    engine_module = ensure_available(auto_build=False)
    num_threads = DEFAULT_THREADS
    # 1. opening book check (V6 lines 127-135)
    fen_prefix = game_state.get_fen().split(" ")[0]
    book_moves = OPENING_BOOK.get_move(fen_prefix)
    if book_moves:
        for bm in book_moves:
            for vm in valid_moves:
                if str(vm) == bm:
                    empty_stats = {'depth': 0, 'nodes': 0, 'time': 0, 'score': 0, 'nps': 0, 'pv': bm}
                    return vm, empty_stats
    # 2. call C++
    fen = game_state.get_fen()
    try:
        move_str, score, depth, nodes, nps = engine_module.find_best_move(fen, DEFAULT_TIME_LIMIT, num_threads)
        stats = {'depth': depth, 'nodes': nodes, 'time': DEFAULT_TIME_LIMIT/1000.0,
                 'score': score, 'nps': nps, 'pv': move_str}
    except Exception as e:
        raise RuntimeError(f"V6 search failed: {e}") from e
    # 3. match move_str back to V3 Move object (V6 lines 162-189)
    chosen_move = None
    for vm in valid_moves:
        if str(vm) == move_str or str(vm).startswith(move_str):
            chosen_move = vm
            break
    if not chosen_move and len(move_str) >= 4:
        from_sq, to_sq = move_str[:2], move_str[2:4]
        from_col = ord(from_sq[0]) - ord('a'); from_row = 8 - int(from_sq[1])
        to_col   = ord(to_sq[0])   - ord('a'); to_row   = 8 - int(to_sq[1])
        for vm in valid_moves:
            if (vm.start_row == from_row and vm.start_col == from_col and
                vm.end_row == to_row and vm.end_col == to_col):
                chosen_move = vm; break
    if chosen_move:
        return chosen_move, stats
    raise RuntimeError(f"V6 returned move {move_str!r}, but it was not legal in this position.")
```

**V7 deltas vs V6 adapter:**
- Rename all `V6` → `V7`, `v6_engine` → `v7_engine`, `V6BuildError` → `V7BuildError`, `V6UnavailableError` → `V7UnavailableError`.
- Replace free-function call `engine_module.find_best_move(fen, time, threads)` with stateful class:
  ```python
  _engine = v7_engine.Engine()          # module-level singleton (A6 in research)
  result = _engine.search(fen, depth=6, time_ms=DEFAULT_TIME_LIMIT)
  ```
- **Wire `search_info`** (FOUND-04 — V6's bug fix). V6 lines 116-117 docstring says "Optional SearchInfo (not used for V6, has internal control)". V7 must actually use it: either via watcher thread, or — preferred per research §B1 — let `GameManager.stop_search` directly call `algo_v7.stop_engine()`. Adapter exposes:
  ```python
  def stop_engine():
      """Flip the C++ atomic stop flag; safe to call without holding GIL."""
      if _engine is not None:
          _engine.stop()
  ```
- Adapter also exposes `new_game()` that calls `_engine.new_game()` so `GameManager.reset()` can clear V7's TT (Open Question 3).
- Drop `OPENING_BOOK` import if V7 declines the book in Phase 1 (research suggests inheriting it is fine; book moves are a free win).

---

### `src/chess_engine/engine/v7/native_build.py` (build-driver, batch)

**Analog:** `src/chess_engine/engine/v6/native_build.py`

**Constants and suffix detection** (V6 lines 13-34):
```python
PROJECT_ROOT = Path(__file__).resolve().parents[4]
V6_DIR = Path(__file__).resolve().parent
BUILD_DIR = V6_DIR / "build"
MODULE_PREFIX = "v6_engine"

def _module_suffixes() -> tuple[str, ...]:
    if sys.platform == "win32":
        return (".pyd",)
    if sys.platform == "darwin":
        return (".so", ".dylib")
    return (".so",)
```

**Module discovery + run wrapper** (V6 lines 37-83): copy verbatim, rename `V6_DIR`→`V7_DIR`, `MODULE_PREFIX`→`"v7_engine"`, `V6BuildError`→`V7BuildError`.

**Build orchestration** (V6 lines 111-151):
```python
def build_v6_native(force: bool = False) -> V6BuildResult:
    existing_module = find_packaged_module()
    if existing_module and not force:
        return V6BuildResult(module_path=existing_module, built=False)
    cmake_path = shutil.which("cmake")
    if not cmake_path:
        raise V6BuildError("CMake is required to build V6. ...")
    _sync_build_dependencies()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    _run([cmake_path, "..", "-DCMAKE_BUILD_TYPE=Release",
          f"-DPython3_EXECUTABLE={sys.executable}"], BUILD_DIR,
         "Failed to configure the V6 native build with CMake.")
    _run([cmake_path, "--build", ".", "--config", "Release"], BUILD_DIR,
         "Failed to compile the V6 native engine.")
    built_module = _find_built_module()
    if built_module is None:
        raise V6BuildError("V6 build completed, but no v6_engine module was produced.")
    destination = V6_DIR / built_module.name
    if built_module.resolve() != destination.resolve():
        shutil.copy2(built_module, destination)
    return V6BuildResult(module_path=destination, built=True)
```

**Entry point** (V6 lines 154-167): copy verbatim. CLI's `build v7` subcommand will invoke `python -m chess_engine.engine.v7.native_build`.

**V7 deltas:**
- All `V6`/`v6` → `V7`/`v7`.
- Error message inside `V6BuildError`: include note that V7 also requires a git submodule for Fathom — if `extern/fathom/src/tbprobe.c` is missing, raise with `"Run 'git submodule update --init --recursive' first."` (TB-01 INT-06).

---

### `src/chess_engine/engine/v7/CMakeLists.txt` (build-config)

**Analog:** `src/chess_engine/engine/v6/CMakeLists.txt`

**Header block, Python + pybind11 fetch** (V6 lines 1-37): copy verbatim, replace `v6_engine` → `v7_engine`, `project(v6_engine ...)` → `project(v7_engine ...)`.

```cmake
cmake_minimum_required(VERSION 3.15)
project(v7_engine LANGUAGES CXX C)         # NB: add C for Fathom's tbprobe.c

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if (NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

find_package(Python3 COMPONENTS Interpreter Development.Module REQUIRED)
# ... (pybind11 FetchContent block from V6 lines 16-37 verbatim)
```

**Sources list** (V6 lines 39-49):
```cmake
set(V7_SOURCES
    src/board.cpp
    src/eval.cpp
    src/magic.cpp
    src/movegen.cpp
    src/search.cpp
    src/syzygy.cpp                 # NEW (B3)
    src/tt.cpp
    src/python_bindings.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/coeffs.cpp   # GENERATED (D-11)
)

pybind11_add_module(v7_engine MODULE ${V7_SOURCES})
target_include_directories(v7_engine PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
```

**OpenMP optional** (V6 lines 55-58): keep verbatim — research §A1 notes OpenMP is not required in Phase 1 but linking is fine.

**NEW: coeffs codegen custom command (D-10..D-13):**
```cmake
set(COEFFS_JSON ${CMAKE_CURRENT_SOURCE_DIR}/coeffs.json)
set(COEFFS_CPP  ${CMAKE_CURRENT_SOURCE_DIR}/src/coeffs.cpp)
add_custom_command(
    OUTPUT ${COEFFS_CPP}
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_coeffs.py
            ${COEFFS_JSON} ${COEFFS_CPP}
    DEPENDS ${COEFFS_JSON} ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_coeffs.py
    COMMENT "Generating coeffs.cpp from coeffs.json"
    VERBATIM
)
```

**NEW: Fathom subdirectory + tbconfig.h override (TB-01, TB-02):**
```cmake
set(FATHOM_DIR ${CMAKE_CURRENT_SOURCE_DIR}/extern/fathom)
target_include_directories(v7_engine PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include      # MUST precede Fathom: our tbconfig.h wins
    ${FATHOM_DIR}/src
)
target_sources(v7_engine PRIVATE ${FATHOM_DIR}/src/tbprobe.c)
```

**NEW: `v7_uci` standalone executable (FOUND-07):**
```cmake
add_executable(v7_uci
    src/uci_main.cpp
    src/board.cpp src/eval.cpp src/magic.cpp src/movegen.cpp
    src/search.cpp src/syzygy.cpp src/tt.cpp
    ${COEFFS_CPP}
    ${FATHOM_DIR}/src/tbprobe.c
)
target_include_directories(v7_uci PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${FATHOM_DIR}/src
)
if (OpenMP_CXX_FOUND)
    target_link_libraries(v7_uci PRIVATE OpenMP::OpenMP_CXX)
endif()
```

---

### V7 C++ headers / impl files forked verbatim from V6

**Analogs:** `src/chess_engine/engine/v6/include/{board,movegen,magic,tt,types}.hpp` and `src/chess_engine/engine/v6/src/{board,movegen,magic,tt}.cpp`.

**Pattern:** Copy file → search-and-replace `namespace v6 {` → `namespace v7 {`, file-guard macros `V6_*` → `V7_*`, comments `V6` → `V7`. No logic edits in A2.

**Perft entry point** (V6 `python_bindings.cpp` lines 61-88) — keep the same shape:
```cpp
uint64_t perft(const std::string& fen, int depth) {
    ensure_init();
    v7::Board board;
    board.from_fen(fen);
    if (depth == 0) return 1;
    v7::MoveList moves;
    v7::generate_legal_moves(board, moves);
    if (depth == 1) return moves.count;
    uint64_t nodes = 0;
    for (int i = 0; i < moves.count; ++i) {
        v7::Move m = moves[i];
        v7::Piece captured = board.piece_at(v7::move_to(m));
        int prev_castling = board.castling_rights;
        v7::Square prev_ep = board.ep_square;
        int prev_halfmove = board.halfmove_clock;
        board.make_move(m);
        nodes += perft(board.to_fen(), depth - 1);
        board.unmake_move(m, captured, prev_castling, prev_ep, prev_halfmove);
    }
    return nodes;
}
```
*Note this V6 perft re-FENs every node (slow). V7 may keep this shape for parity, then optimize in Phase 4.*

---

### `src/chess_engine/engine/v7/include/search.hpp` (event-driven)

**Analog:** `src/chess_engine/engine/v6/include/search.hpp`

**V6 `SearchInfo` struct** (V6 lines 14-57):
```cpp
struct SearchInfo {
    std::chrono::steady_clock::time_point start_time;
    int time_limit_ms = 5000;
    std::atomic<uint64_t> nodes{0};
    int depth = 0;
    int seldepth = 0;
    int score = 0;
    Move best_move = MOVE_NONE;
    std::atomic<bool> stopped{false};        // KEY — V7 must point at Engine's flag
    int num_threads = 1;
    void reset() { /* sets stopped=false, start_time=now, etc. */ }
    bool check_time() { /* polls clock; sets stopped on timeout */ }
    int elapsed_ms() const { /* ... */ }
};
```

**V7 deltas (FOUND-04):** Add a non-owning pointer to an external atomic so the persistent `Engine::stop_flag_` survives across `info.reset()`:
```cpp
struct SearchInfo {
    // ... V6 fields ...
    std::atomic<bool>* external_stop = nullptr;  // NEW — points at Engine::stop_flag_

    void reset() {
        nodes = 0; depth = 0; seldepth = 0; score = 0;
        best_move = MOVE_NONE;
        // Do NOT clobber external_stop; do NOT reset stopped to false if external is set
        if (external_stop) stopped.store(external_stop->load(std::memory_order_relaxed));
        else               stopped.store(false);
        start_time = std::chrono::steady_clock::now();
    }
    bool check_time() {
        if (stopped) return true;
        if (external_stop && external_stop->load(std::memory_order_relaxed)) {
            stopped = true; return true;
        }
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - start_time).count();
        if (elapsed >= time_limit_ms) { stopped = true; return true; }
        return false;
    }
};
```

**Search constants** (V6 lines 100-117): keep verbatim. Add `constexpr int ASPIRATION_MAX_REWIDENS = 4;` for SRCH-02 cap.

---

### `src/chess_engine/engine/v7/src/search.cpp` (event-driven)

**Analog:** `src/chess_engine/engine/v6/src/search.cpp`

**Per-node stop polling pattern** (V6 lines 34-39 and 110-112):
```cpp
int quiescence(Board& board, int alpha, int beta, SearchInfo& info, int ply) {
    info.nodes.fetch_add(1, std::memory_order_relaxed);
    if (info.stopped || (info.nodes % 4096 == 0 && info.check_time())) {
        return 0;
    }
    // ...
}

int alpha_beta(Board& board, int depth, int alpha, int beta,
               SearchInfo& info, int ply, std::vector<Move>& pv, bool do_null) {
    if (info.stopped || (info.nodes % 4096 == 0 && info.check_time())) {
        return 0;
    }
    // ...
}
```
V7 inherits unchanged. With `external_stop` wired into `check_time()`, Python `_engine.stop()` flips the atomic; next `% 4096 == 0` node returns within ~50ms at 1Mnps.

**PVS core** (V6 lines 240-258): inherit verbatim.

**Iterative deepening + aspiration loop** (V6 lines 292-352) — this is the file V7 must MODIFY for SRCH-02 + SRCH-13 + SRCH-15:
```cpp
SearchResult iterative_deepening(Board& board, SearchInfo& info, bool verbose) {
    // ... V6 setup ...
    for (int depth = 1; depth <= 64 && !info.stopped; ++depth) {
        info.depth = depth;
        pv.clear();
        if (depth >= 4) {
            alpha = result.score - ASPIRATION_WINDOW;
            beta  = result.score + ASPIRATION_WINDOW;
        }
        int score = alpha_beta(board, depth, alpha, beta, info, 0, pv, true);
        // V6 ANTI-PATTERN — unbounded single re-search; V7 must cap (SRCH-02):
        if (score <= alpha || score >= beta) {
            alpha = -INFINITY_SCORE; beta = INFINITY_SCORE;
            score = alpha_beta(board, depth, alpha, beta, info, 0, pv, true);
        }
        // ...
    }
}
```

**V7 SRCH-02 fix shape:**
```cpp
int rewidens = 0;
int delta = ASPIRATION_WINDOW;
while (score <= alpha || score >= beta) {
    if (rewidens >= ASPIRATION_MAX_REWIDENS) {
        alpha = -INFINITY_SCORE; beta = INFINITY_SCORE;
    } else {
        delta *= 2;
        if (score <= alpha) alpha -= delta; else beta += delta;
        ++rewidens;
    }
    score = alpha_beta(board, depth, alpha, beta, info, 0, pv, true);
    if (info.stopped) break;
}
```

**SRCH-13 (mate-TT) shape (insert at every TT store/probe in V6 search.cpp around line 277, 284 and any `TT.probe(...)`):**
```cpp
inline int score_to_tt(int score, int ply) {
    if (score >=  MATE_IN_MAX_PLY) return score + ply;
    if (score <= -MATE_IN_MAX_PLY) return score - ply;
    return score;
}
inline int score_from_tt(int score, int ply) {
    if (score >=  MATE_IN_MAX_PLY) return score - ply;
    if (score <= -MATE_IN_MAX_PLY) return score + ply;
    return score;
}
// On store:
TT.store(board.hash, best_move, score_to_tt(best_score, ply), depth, tt_flag);
// On probe:
int tt_score = score_from_tt(entry.score, ply);
```
**ACTION FOR PLANNER:** First B1 task is to grep V6 `tt.cpp` + `search.cpp` for `MATE` to verify whether V6 already does this. Research Open Question 1 explicitly calls this audit out.

**SRCH-14 (repetition in tree) shape (no V6 analog; net-new pattern):**
```cpp
// In Board or a per-search stack: uint64_t rep_keys[MAX_PLY + 100];
// On make_move: push board.hash; halfmove_clock = (irreversible ? 0 : +1)
// At top of alpha_beta:
if (board.halfmove_clock >= 4) {
    int reps = 0;
    for (int i = board.rep_top - 2; i >= board.rep_top - board.halfmove_clock; i -= 2) {
        if (board.rep_stack[i] == board.hash && ++reps == 2) return 0;  // 3-fold (current + 2 prior)
    }
}
```

**SRCH-15 (time mgmt) shape:** V6's `check_time` only enforces hard deadline at `time_limit_ms`. V7 adds soft deadline:
```cpp
struct TimeManager {
    int hard_deadline_ms;
    int soft_deadline_ms;
    static TimeManager allocate(int remaining_ms, int increment_ms, int moves_to_go = 30) {
        int budget = remaining_ms / std::max(moves_to_go, 1) + (increment_ms * 95 / 100);
        budget = std::min(budget, remaining_ms * 9 / 10);  // ≥10% margin
        return {budget, budget / 2};
    }
};
// In iterative_deepening: between iterations, if info.elapsed_ms() >= soft_deadline, break.
```

---

### `src/chess_engine/engine/v7/src/python_bindings.cpp` (binding, request-response) — **REWRITE**

**Counter-example:** `src/chess_engine/engine/v6/src/python_bindings.cpp` (the file with bug FOUND-04).

**V6 ANTI-PATTERN — what V7 must NOT replicate** (V6 lines 22-41):
```cpp
// V6 BUG: signature has no SearchInfo argument; the Python caller cannot pass cancellation
std::tuple<std::string, int, int, uint64_t, int> find_best_move(
    const std::string& fen,
    int time_limit_ms,
    int num_threads
) {
    ensure_init();
    v6::Board board;
    board.from_fen(fen);
    v6::SearchResult result;
    if (num_threads > 1) {
        result = v6::search_parallel(board, time_limit_ms, num_threads, true);
    } else {
        result = v6::search(board, time_limit_ms, true);
    }
    // ...
}
```
V6's `search()` internally creates `SearchInfo info; info.reset();` (search.cpp:361) — so no Python `SearchInfo` *could* be wired in even if the binding accepted it. The fix requires both binding-level (accept Engine state) and search-level (use that state, see `external_stop` pattern above).

**V6 module block — what V7 keeps shape of** (V6 lines 114-140):
```cpp
PYBIND11_MODULE(v6_engine, m) {
    m.doc() = "V6 Chess Engine - C++ with OpenMP parallel search";
    m.def("find_best_move", &find_best_move,
          "Find best move for a position",
          py::arg("fen"),
          py::arg("time_limit_ms") = 5000,
          py::arg("num_threads") = 4);
    m.def("get_pv", &get_pv, /* ... */);
    m.def("perft", &perft, py::arg("fen"), py::arg("depth"));
    m.def("evaluate", &evaluate_position, py::arg("fen"));
    m.def("count_legal_moves", &count_legal_moves, py::arg("fen"));
}
```

**V7 FIX SHAPE (FOUND-04, FOUND-05, from research §A1):**
```cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "engine.hpp"     // wraps Board + TT + SearchInfo + Syzygy state

namespace py = pybind11;

PYBIND11_MODULE(v7_engine, m) {
    m.doc() = "V7 Chess Engine - C++ with SearchInfo wiring + GIL release";

    py::class_<v7::Engine>(m, "Engine")
        .def(py::init<>())
        .def("set_syzygy_path", &v7::Engine::set_syzygy_path,
             py::arg("path"),
             py::call_guard<py::gil_scoped_release>())              // FOUND-05
        .def("new_game", &v7::Engine::new_game)                     // clears TT, rep stack
        .def("search", &v7::Engine::search,
             py::arg("fen"),
             py::arg("depth")   = 6,
             py::arg("time_ms") = 5000,
             py::call_guard<py::gil_scoped_release>())              // FOUND-05, PITFALL #11
        .def("stop", &v7::Engine::stop)                             // atomic write; no GIL release
        .def("tbhits", &v7::Engine::tbhits)
        .def("nodes",  &v7::Engine::nodes);

    m.def("perft", &v7::perft_entry,
          py::arg("fen"), py::arg("depth"),
          py::call_guard<py::gil_scoped_release>());                // FOUND-06 parity

    m.def("evaluate", &v7::evaluate_entry, py::arg("fen"));
    m.def("count_legal_moves", &v7::count_legal_moves_entry, py::arg("fen"));
}
```

**Critical points (per research §A1 Gotchas):**
- `search()` MUST release GIL — otherwise Python's `stop()` call blocks on GIL, breaking cancellation.
- `stop()` MUST NOT release GIL — it's one atomic write; GIL release on a fast write is pure overhead.
- `tbhits()` / `nodes()` return `uint64_t`; auto-converted by pybind11.

---

### `src/chess_engine/engine/v7/src/syzygy.cpp` + `include/syzygy.hpp` (request-response)

**No analog in repo.** Pattern is freshly-written per research §B3.

**Init log discipline (D-08) — verbatim log strings:**
```cpp
// src/syzygy.cpp
#include "syzygy.hpp"
#include <filesystem>
#include <iostream>
extern "C" {
#include "tbprobe.h"        // Fathom
}

namespace v7 {

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
    if (!smoke_probe_krk()) {
        std::cerr << "[v7] syzygy: smoke probe failed (corrupt or wrong format) at "
                  << path << "; tbhits will be 0\n";
        tb_free();
    }
}

} // namespace v7
```

**In-search probe failure handling (TB-06, D-09):**
```cpp
unsigned wdl = tb_probe_wdl(/* ... */);
if (wdl == TB_RESULT_FAILED) {
    std::cerr << "[v7] syzygy: in-search probe failed at fen=" << board.to_fen() << "\n";
    return std::nullopt;   // NEVER return 0 / DRAW score
}
tbhits_.fetch_add(1, std::memory_order_relaxed);
```

---

### `src/chess_engine/engine/v7/include/tbconfig.h` (Fathom override)

**No repo analog.** Pattern per Fathom README (cited in research §B3). Skeleton:
```cpp
#pragma once
#include "magic.hpp"
#include <cstdint>

#define TB_CUSTOM_LSB
inline unsigned tb_lsb(uint64_t b) {
#if defined(_MSC_VER)
    unsigned long idx; _BitScanForward64(&idx, b); return static_cast<unsigned>(idx);
#else
    return __builtin_ctzll(b);
#endif
}

#define TB_PAWN_ATTACKS(sq, color) (v7::pawn_attacks(sq, color))
#define TB_KNIGHT_ATTACKS(sq)      (v7::knight_attacks(sq))
#define TB_BISHOP_ATTACKS(sq, occ) (v7::bishop_attacks(sq, occ))
#define TB_ROOK_ATTACKS(sq, occ)   (v7::rook_attacks(sq, occ))
#define TB_QUEEN_ATTACKS(sq, occ)  (v7::queen_attacks(sq, occ))
#define TB_KING_ATTACKS(sq)        (v7::king_attacks(sq))
```
CMake `target_include_directories` order ensures V7's `include/` precedes `extern/fathom/src/`, so this file wins over Fathom's default.

---

### `src/chess_engine/engine/v7/coeffs.json` + `tools/gen_coeffs.py` + `include/coeffs.hpp`

**No repo analog.** Patterns ship in research §B2 verbatim (lines 444-540 of RESEARCH.md). Planner / executor should pull those code blocks directly. Key invariants:
- `coeffs.json` top: `"_meta": {"source": "...chessprogramming.org/PeSTO%27s_Evaluation_Function..."}` (D-01 specifics; cite Pesto and Zurichess).
- `gen_coeffs.py`: `json.dumps(..., sort_keys=True, indent=2)`, write `dst.write_bytes(text.encode("utf-8").replace(b"\r\n", b"\n"))` (D-13 deterministic LF).
- `coeffs.hpp`: forward-declare every `extern const int <name>[N];` matching what `gen_coeffs.py` emits — schema must stay locked between the two for the duration of Phase 1.

---

### `src/chess_engine/server/game_manager.py` (controller, request-response) — **EXTEND**

**Self-analog:** V6 dispatch branch at lines 353-364.

**Engine availability set** (lines 13-25):
```python
AVAILABLE_ENGINES = {
    "human", "v2", "v3", "v4", "v4b", "v4c",
    "v5", "v5b", "v5c", "v5d", "v6",
}
```
V7 adds `"v7"` to this set.

**Engine version setter** (lines 41-66, V6 branch lines 47-51):
```python
if ver == "v6":
    try:
        algo_v6.ensure_available(auto_build=True)
    except algo_v6.V6UnavailableError as error:
        return False, f"V6 is unavailable: {error}"
```
V7 mirrors with `algo_v7` / `V7UnavailableError`.

**ai_move ladder V6 dispatch** (lines 353-364):
```python
elif current_engine == "v6":
    try:
        result = algo_v6.find_best_move(self.gs, self.valid_moves, current_engine)
        if isinstance(result, tuple):
            move, stats = result
        else:
            move = result
    except Exception as error:
        self.last_search_stats = None
        print(f"[GameManager] V6 move failed: {error}")
        return None
```
V7 mirrors with two changes: (1) name change, (2) **passes `search_info`** (the V6 bug closure). Note V6 does NOT pass `current_search_info` — V7 must.

**V5 dispatch shape with SearchInfo** (lines 301-313 — closer match for the wiring V7 needs):
```python
elif current_engine == "v5":
     from chess_engine.engine.v5.search import SearchInfo
     self.current_search_info = SearchInfo()
     result = algo_v5.find_best_move(self.gs, self.valid_moves, current_engine,
                                     search_info=self.current_search_info)
     if isinstance(result, tuple):
         move, stats = result
     else:
         move = result
     self.current_search_info = None
```
V7 should follow this V5 shape (SearchInfo import + pass + clear) PLUS the V6 try/except wrapper (since native imports can fail).

**stop_search method** (lines 68-73):
```python
def stop_search(self):
    if self.current_search_info:
        self.current_search_info.stopped = True
        print("[GameManager] Search stop requested")
    return True
```
V7 INT-01 extension: also flip the C++ atomic so the GIL-released search thread observes it.
```python
def stop_search(self):
    if self.current_search_info:
        self.current_search_info.stopped = True
        print("[GameManager] Search stop requested")
    # V7: notify C++ atomic directly — search thread doesn't hold the GIL
    if self.white_engine == "v7" or self.black_engine == "v7":
        try:
            from chess_engine.engine.v7 import chess_algorithm as algo_v7
            if algo_v7.V7_AVAILABLE:
                algo_v7.stop_engine()
        except Exception:
            pass
    return True
```

**reset / load_fen consideration (Open Question 3):** `reset()` (line 75) and `load_fen()` (line 86) call `stop_search()` then re-init game state. V7's adapter should expose `new_game()` that clears TT + repetition stack; planner decides whether `GameManager.reset/load_fen` needs to invoke it.

---

### `client/src/App.jsx` (React component, event-driven) — **EXTEND**

**Self-analog (warning copy, line 232-241):**
```jsx
const switchEngine = async (ver, color) => {
    setEngineSwitching(true);
    setError("");
    if (ver === "v6") {
      const message = "Preparing V6 native engine; first use may build locally.";
      setEngineStatus(message);
      log(message);
    } else {
      setEngineStatus("");
    }
    // ...
};
```
V7 INT-03 fix shape:
```jsx
if (ver === "v6" || ver === "v7") {
  const message = `Preparing ${ver.toUpperCase()} native engine; first use may build locally.`;
  setEngineStatus(message);
  log(message);
}
```

**Self-analog (white dropdown, lines 402-416):**
```jsx
<select value={whiteEngine} onChange={(e) => switchEngine(e.target.value, "white")}
        disabled={engineSwitching}>
  <option value="human">White: Human</option>
  <option value="v6">White: V6 (C++)</option>
  <option value="v5d">White: V5d (5s)</option>
  ...
</select>
```
V7 INT-02: insert `<option value="v7">White: V7 (C++)</option>` immediately ABOVE the V6 line (newest-first convention per research §C1 gotchas).

**Self-analog (black dropdown, lines 417-431):** same edit shape, V7 option above V6 option.

---

### `cli/src/config.js` (config) — **EXTEND**

**Self-analog (lines 12-20):**
```js
const DEFAULT_CONFIG = {
    threads: null,
    ttSize: 64,
    maxMemory: 512,
    timeLimit: 5000,
    v6Built: false,
    lastBuildTime: null,
    cmakePath: null,
};
```
V7 INT-04 additions:
```js
const DEFAULT_CONFIG = {
    threads: null,
    ttSize: 64,
    maxMemory: 512,
    timeLimit: 5000,
    v6Built: false,
    v7Built: false,                  // INT-04
    syzygyPath: null,                // INT-04 (Open Question 2: OS-specific default chosen at runtime, not stored)
    syzygyMaxPieces: 6,              // INT-04 / TB-08
    lastBuildTime: null,
    cmakePath: null,
};
```

---

### `cli/src/index.js` (CLI, batch) — **EXTEND**

**Self-analog (`buildV6` at lines 148-184):**
```js
async function buildV6() {
    printSubHeader('Building V6 C++ Engine');
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    let command = 'uv';
    let args = ['run', '--extra', 'build', 'python', '-m', 'chess_engine.engine.v6.native_build'];
    try {
        execSync('uv --version', { stdio: 'pipe' });
    } catch {
        command = pythonCmd;
        args = ['-m', 'uv', 'run', '--extra', 'build', 'python', '-m', 'chess_engine.engine.v6.native_build'];
    }
    try {
        execFileSync(command, args, {
            cwd: ROOT_DIR,
            stdio: 'inherit',
            env: { ...process.env, PYTHONPATH: path.join(ROOT_DIR, 'src') },
        });
        setConfigValue('v6Built', true);
        setConfigValue('lastBuildTime', new Date().toISOString());
        log('\n' + '═'.repeat(50), colors.green);
        logSuccess('V6 Engine built successfully!');
        log('═'.repeat(50), colors.green);
        return true;
    } catch (error) {
        logError(`Build failed: ${error.message}`);
        return false;
    }
}
```

**V7 INT-05 fix shape — `buildV7`:** copy `buildV6`, replace every `v6` → `v7` (string in args, config key). Then add to the `case 'build':` block at lines 460-468:
```js
case 'build':
    if (args[1] === 'v6') {
        await buildV6();
    } else if (args[1] === 'v7') {
        await buildV7();
    } else if (args[1] === 'client') {
        await buildClient();
    } else {
        logError('Usage: chess-engine build [v6|v7|client]');
    }
    break;
```

**V7 INT-05 `syzygy download` (no direct analog — net-new):** add `case 'syzygy':` mirroring the `case 'build':` shape; subcommand dispatcher inspects `args[1] === 'download'`. The downloader should write to `loadConfig().syzygyPath || <OS-default>`, where OS-default follows research Open Question 2:
- Windows: `path.join(process.env.LOCALAPPDATA, 'chess-engine', 'syzygy')`
- macOS: `path.join(os.homedir(), 'Library', 'Application Support', 'chess-engine', 'syzygy')`
- Linux: `path.join(process.env.XDG_DATA_HOME || path.join(os.homedir(), '.local', 'share'), 'chess-engine', 'syzygy')`

Use the existing `Spinner` class (lines 74-105) and `execWithSpinner` (lines 110-125) for the long-running download.

---

### `tests/test_v7_engine.py` + sibling test files (test)

**Analog:** `tests/test_v6_native.py` (38 lines, full contents shown above).

**Module-scoped fixture with build-and-skip pattern** (V6 lines 6-11):
```python
import pytest
from chess_engine.engine.v6 import chess_algorithm as v6

@pytest.fixture(scope="module")
def v6_native_engine():
    try:
        return v6.ensure_available(auto_build=True)
    except Exception as error:
        pytest.skip(f"V6 native engine unavailable: {error}")
```
V7 mirrors directly: `from chess_engine.engine.v7 import chess_algorithm as v7` + `v7_native_engine` fixture.

**Single-assertion test style** (V6 lines 14-22): each test function exercises one observable. V7 tests (`test_perft_parity`, `test_cancellation_latency`, `test_gil_released`, `test_mate_score_tt`, `test_repetition_in_tree`, `test_time_management`, `test_eval_terms_present`, `test_syzygy_*`, `test_smoke_game_v7_vs_v6`) all follow this shape.

**Mark slow tests opt-in** (research §A2 gotcha): use `@pytest.mark.slow` on depth-6 perft so default CI runs depth-5.

---

## Shared Patterns

### Pattern S1: GIL release on long-running C++ calls (FOUND-05, Pitfall #11)
**Source:** pybind11 docs `call_guard` (cited; no in-repo analog — V6 omits this, which is the bug).
**Apply to:** Every binding method/function in `python_bindings.cpp` whose C++ body runs > ~100µs or that another Python thread may try to interrupt.
```cpp
.def("search", &v7::Engine::search, /* args */,
     py::call_guard<py::gil_scoped_release>())
m.def("perft", &v7::perft_entry, /* args */,
     py::call_guard<py::gil_scoped_release>())
```
**Do NOT** add to `stop()` or other atomic-write methods — pure overhead.

### Pattern S2: Stateful cancellation via atomic-pointer (FOUND-04)
**Source:** V6 `SearchInfo.stopped` (search.hpp:27) + Engine class wrapper (research §A1).
**Apply to:** `include/search.hpp` (SearchInfo gets `external_stop`), `src/search.cpp` (polling reads it), `python_bindings.cpp` (`Engine` class owns the atomic), `chess_algorithm.py` (`stop_engine()` calls `_engine.stop()`), `game_manager.py` (`stop_search` invokes `algo_v7.stop_engine()`).
```cpp
// Hot-path poll, V6 line 110, unchanged in V7:
if (info.stopped || (info.nodes % 4096 == 0 && info.check_time())) return 0;
// V7 check_time additionally consults info.external_stop atomic.
```

### Pattern S3: Auto-build on first import (INT-09)
**Source:** V6 `chess_algorithm.py:61-90` (`ensure_available(auto_build=True)`).
**Apply to:** Every new V7 entry into the native module — `GameManager.set_engine_version` for V7 branch, `tests/test_v7_engine.py` `v7_native_engine` fixture.

### Pattern S4: Stderr `print()` as logging (CONVENTIONS, D-08)
**Source:** `GameManager` lines 56-62, 295, 419; `chess_algorithm.py` lines 94-96, 124, 133, 148.
**Apply to:** Every V7 init log per D-08 (verbatim strings: `[v7] syzygy: no path configured; tbhits will be 0` etc.), every adapter load notice (`[V7] C++ Engine loaded successfully!`), every dispatch-failure line.
Use `std::cerr << "[v7] ..." << "\n"` from C++ and `print(f"[V7] ...")` from Python. Do **not** introduce `logging.getLogger(__name__)` this phase (deferred per CONTEXT).

### Pattern S5: Native-module discovery suffix matrix
**Source:** `native_build.py:29-34` and `chess_algorithm.py:28-42`.
```python
def _module_suffixes() -> tuple[str, ...]:
    if sys.platform == "win32":  return (".pyd",)
    if sys.platform == "darwin": return (".so", ".dylib")
    return (".so",)
```
**Apply to:** V7's `native_build.py` (verbatim), V7's adapter `_load_v7_engine` glob discovery loop. Keep `.gitignore` aligned (`v7_engine*.so`, `v7_engine*.pyd`, `v7_engine*.dylib`).

### Pattern S6: Engine-ladder dispatch with try/except (V2-REF-01 deferred anti-pattern, preserved)
**Source:** `GameManager.ai_move` lines 286-374 (V5/V6 branches both shown).
**Apply to:** V7 ai_move branch. Wrap V7 call in try/except like V6 (lines 355-364) so a native crash returns `None` instead of 500ing the API. Closest hybrid analog is V5 branches (SearchInfo wiring) + V6 branch (try/except guard). V7 needs both.

### Pattern S7: CMake FetchContent for pinned deps
**Source:** V6 `CMakeLists.txt:28-37` (pybind11 v2.12.0).
**Apply to:** V7 CMakeLists.txt — keep the same `FetchContent_Declare(... GIT_TAG v2.12.0)` block verbatim. Do NOT bump pybind11; sibling-engine ABI safety per research §Standard Stack.

### Pattern S8: Deterministic codegen output (D-13)
**No in-repo analog** — new convention.
**Apply to:** `tools/gen_coeffs.py`.
- `json.dumps(..., sort_keys=True, indent=2)` for stability across machines.
- Explicit LF: `dst.write_bytes(text.encode("utf-8").replace(b"\r\n", b"\n"))`.
- Emit a `// GENERATED — DO NOT EDIT` header citing the source JSON.
- Iterate dict keys via `sorted(data.keys())`.

---

## No Analog Found

Files with no close match in the codebase (executor should follow RESEARCH.md patterns directly):

| File | Role | Data Flow | Reason | RESEARCH.md section |
|------|------|-----------|--------|---------------------|
| `src/chess_engine/engine/v7/include/coeffs.hpp` | extern declarations | n/a | Net-new schema; first appearance of generated-coeffs pattern in repo | §B2 |
| `src/chess_engine/engine/v7/include/tbconfig.h` | Fathom override | n/a | First Fathom integration in repo | §B3 |
| `src/chess_engine/engine/v7/include/syzygy.hpp` + `src/syzygy.cpp` | TB probe wrapper | request-response | First TB usage in repo | §B3 (init log + probe failure) |
| `src/chess_engine/engine/v7/src/uci_main.cpp` | standalone UCI binary | streaming | No UCI binary exists yet (V6 only exposes pybind11) | research §A1 + FOUND-07; minimal `uci`/`isready`/`position`/`go depth`/`stop`/`quit` per Open Question 4 |
| `src/chess_engine/engine/v7/coeffs.json` | data | n/a | Net-new SoT | §B2 (Pesto-baseline skeleton lines 444-481 of RESEARCH.md) |
| `src/chess_engine/engine/v7/tools/gen_coeffs.py` | codegen | transform | Net-new | §B2 (deterministic implementation lines 485-525 of RESEARCH.md) |
| `cli/src/index.js syzygy download` subcommand | downloader | batch | No existing `download`-shape subcommand; closest analog is `buildClient` which downloads npm deps implicitly | research §C1 INT-05 + Open Question 2 (OS-specific default paths) |

For all NO-ANALOG files, the planner should reference RESEARCH.md by section rather than treating them as "fork V6 + tweak".

---

## Metadata

**Analog search scope:**
- `src/chess_engine/engine/v6/**` (primary fork source — 21 files)
- `src/chess_engine/engine/v5/search.py` (SearchInfo class shape for adapter cancellation pattern)
- `src/chess_engine/server/game_manager.py` (dispatch ladder, stop_search, set_engine_version)
- `src/chess_engine/core/` (empty — `search_info.py` referenced in CONTEXT does not exist; cancellation contract lives inside per-engine `search.py` files)
- `client/src/App.jsx` (engine selectors + warning copy)
- `cli/src/{config,index}.js` (CLI subcommand + config pattern)
- `tests/test_v6_native.py` (pytest fixture + skip-on-unavailable pattern)

**Files scanned:** 14 read in full, 4 partial reads, 0 re-reads.

**Pattern extraction date:** 2026-05-15

**Notable findings for planner:**
1. **CONTEXT.md references `src/chess_engine/core/search_info.py`** but the file does not exist. The `SearchInfo` class lives per-engine inside `v5/search.py`, `v5b/search.py`, etc. (V6 has its own C++ `SearchInfo` struct in `include/search.hpp`). The "cooperative cancellation contract" is convention, not a shared abstract class. Planner should not assume an importable `chess_engine.core.search_info` exists; V7's Python-side cancellation can either define its own no-op `SearchInfo` stand-in or operate entirely via the C++ atomic + `stop_engine()` adapter helper.
2. **V6 `find_best_move` adapter signature** is `(game_state, valid_moves, engine, search_info=None)` (line 108) and the parameter is documented as "not used for V6, has internal control" (line 117). The FOUND-04 bug is therefore Python-level (parameter accepted but ignored) AND C++-level (no atomic for Python to flip). V7 must fix both.
3. **V6 perft re-FENs every node** (`python_bindings.cpp` line 83: `perft(board.to_fen(), depth - 1)`). This is a slow reference implementation. V7 should keep this for A2 parity to match V6 numbers exactly, then optimize later if needed for tests.
4. **V6 `iterative_deepening` aspiration re-search** (`search.cpp:316-320`) does exactly ONE re-search at full window on fail-high/low. SRCH-02 "unbounded re-search" risk is therefore minimal in practice for V6 — V7's cap (4 widenings then full window) is a defense-in-depth improvement, not a bug fix. Planner can frame SRCH-02 work accordingly.
