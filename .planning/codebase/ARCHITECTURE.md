---
focus: arch
generated: 2026-05-14
---

# Architecture

## High-Level Pattern

Layered client/server with a thin HTTP adapter over a domain core (chess engine + game state).

- **Frontend (SPA)** — React 19 + Vite, talks to backend via REST/JSON over `axios`. No state management library; component-local `useState` + a small custom hook layer.
- **Backend (HTTP)** — FastAPI app exposing game endpoints. Stateful: a single in-process `GameManager` singleton holds the active game.
- **Domain core** — Engine package containing board/move generation, evaluation, search algorithms, and multiple engine versions (v1–v6).
- **Native acceleration (optional)** — V6 uses a pybind11 C++17 module built via CMake `FetchContent`. CUDA acceleration via Numba for V4b GPU service.

## Layers

```
Frontend (chess-ui/)
  React + react-chessboard + recharts
  useChessGame hook -> axios -> backend
        |
        v  HTTP/JSON
HTTP layer (src/chess_engine/server/)
  FastAPI app, CORS middleware
  main.py routes -> GameManager singleton
        |
        v  in-process call
GameManager (src/chess_engine/server/game_manager.py)
  Holds GameState, current engine choice
  Orchestrates AI move via engine adapter
        |
        v  find_best_move(...)
Engine adapters (src/chess_engine/engine/v{1..6}/)
  Each engine exposes find_best_move(game_state, valid_moves, engine[, search_info])
  V6 dispatches to native pybind11 module
        |
        v  uses
Core domain (src/chess_engine/core/)
  Board, GameState, MoveGenerator, evaluator
  Bitboard helpers, Zobrist hashing, transposition tables
```

## Data Flow: AI Move

1. Browser POSTs `/move` (human move) -> `server/main.py`
2. Route handler calls `gm.make_human_move(...)` -> updates `GameState`
3. Browser POSTs `/ai-move` -> handler calls `gm.ai_move(engine_name, depth)`
4. `GameManager.ai_move`:
   - Selects engine module via string-comparison ladder (`if engine == "v1": ...`)
   - Builds a `SearchInfo` for cooperative cancellation
   - Calls `engine.find_best_move(game_state, valid_moves, engine_name, search_info)`
5. Engine searches, returns `(move, eval, stats)`
6. Handler applies move to `GameState`, serializes new board to JSON, returns to client

## Key Abstractions

- **`GameManager`** (`src/chess_engine/server/game_manager.py`) — Singleton holding active game. Module-global `gm = GameManager()` instantiated at import.
- **Engine adapter contract** — Every engine exports `find_best_move(game_state, valid_moves, engine[, search_info])`. The `engine` parameter is the engine name string (legacy), used for routing within multi-version modules.
- **`SearchInfo`** (`src/chess_engine/core/search_info.py`) — Cooperative cancellation token. Engines poll `search_info.stop_requested` between iterations.
- **`Device`** (`src/chess_engine/core/device.py`) — Singleton dispatching CPU vs CUDA paths for vectorized eval kernels.
- **V6 native loader** (`src/chess_engine/engine/v6/__init__.py`) — Auto-builds the C++ pybind11 module on first import via CMake if not already compiled.

## Entry Points

- **HTTP server**: `python -m chess_engine.server.main` (or `uvicorn chess_engine.server.main:app`)
- **Frontend dev**: `cd chess-ui && npm run dev` (Vite dev server, default port 5173)
- **CLI scripts**: `src/chess_engine/cli/` — benchmarking, perft, self-play
- **Pygame visualizer (optional)**: `src/chess_engine/visualizer/main.py` — local desktop GUI
- **Tests**: `pytest tests/` (mixed pytest + unittest)

## Cross-Cutting Concerns

- **Threading model**: Engines run synchronously inside the request thread. `SearchInfo.stop_requested` is the only cancellation primitive — there's no thread pool.
- **CUDA**: Numba `@cuda.jit` kernels in eval paths; falls back to CPU when `Device.use_cuda` is `False`.
- **No middleware stack** beyond CORS (open `*` with credentials — see `CONCERNS.md`).

## Anti-Patterns Identified

1. **Engine string-comparison ladder** in `GameManager.ai_move` — every new engine version requires editing this `if/elif` chain. Should be a registry dict.
2. **Module-global singleton** `gm = GameManager()` at module load — makes testing/multi-game support hard.
3. **`sys.path`-mutating compatibility shims** — older engine modules patch `sys.path` at import to find legacy locations.
4. **Massive copy-paste between v5/v5b/v5c/v5d** — these are forks rather than parameterized variants. Bug fixes must be applied N times.
