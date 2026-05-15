---
focus: arch
generated: 2026-05-14
---

# Directory Structure

## Top-Level Layout

```
Chess-Engine/
├── src/chess_engine/        # Python package (installed via pyproject.toml)
│   ├── core/                # Domain core: board, movegen, eval, hashing
│   ├── engine/              # Engine versions v1..v6, each its own subpackage
│   ├── server/              # FastAPI HTTP layer + GameManager
│   ├── cli/                 # CLI utilities (perft, benchmark, self-play)
│   └── visualizer/          # Optional pygame desktop visualizer
├── chess-ui/                # React 19 + Vite frontend (separate npm workspace)
│   ├── src/                 # Components, hooks, api client
│   ├── public/              # Static assets
│   └── package.json
├── tests/                   # pytest + unittest test suite
│   └── conftest.py          # Shared fixtures
├── scripts/                 # Build/dev helpers
├── .planning/               # GSD workflow state (this directory)
├── pyproject.toml           # Python project + uv lock
├── uv.lock
└── README.md
```

## Engine Subpackage Layout

Each `src/chess_engine/engine/v{N}/` follows roughly:

```
v3/
├── __init__.py              # exports find_best_move
├── chess_algorithm.py       # search loop (alpha-beta, negamax, etc.)
├── evaluator.py             # static eval
└── (version-specific helpers)
```

V6 is special — it adds `src/` (C++ sources), `CMakeLists.txt`, and `__init__.py` performs a CMake build on first import:

```
v6/
├── __init__.py              # auto-build + load .pyd
├── CMakeLists.txt
├── src/
│   ├── movegen.cpp
│   ├── search.cpp
│   ├── eval.cpp
│   └── bindings.cpp         # pybind11 module definition
└── build/                   # gitignored, output of CMake build
```

## Frontend Layout

```
chess-ui/src/
├── App.jsx                  # Root component
├── main.jsx                 # Vite entry
├── components/              # ChessBoard, EngineSelector, EvalChart, etc.
├── hooks/
│   └── useChessGame.js      # Game state hook, axios calls
├── api/
│   └── client.js            # axios instance, base URL config
└── styles/
```

## Naming Conventions

- **Python files**: `snake_case.py`
- **Python classes**: `PascalCase`
- **Python constants**: `UPPER_SNAKE_CASE`
- **Engine versions**: `v1, v2, v3, v4, v4b, v4c, v5, v5a, v5b, v5c, v5d, v6` — letter suffixes denote experimental forks
- **React components**: `PascalCase.jsx`
- **React hooks**: `useXxx.js`
- **Test files**: `tests/test_*.py`

## Where to Add New Code

| Adding | Location |
|---|---|
| New HTTP endpoint | `src/chess_engine/server/main.py` (route) + `game_manager.py` (logic) |
| New engine version | `src/chess_engine/engine/v{N}/` + register in `GameManager.ai_move` ladder |
| New evaluation kernel | `src/chess_engine/core/evaluator.py` (or version-specific evaluator) |
| New React feature | `chess-ui/src/components/` + wire through `useChessGame` |
| New CLI command | `src/chess_engine/cli/` + entry in `pyproject.toml` `[project.scripts]` |
| New tests | `tests/` (mirror source layout where possible) |

## Key Locations / Hotspots

- `src/chess_engine/server/main.py` — HTTP routes
- `src/chess_engine/server/game_manager.py` — engine dispatch ladder, **edit when adding engine versions**
- `src/chess_engine/core/board.py` — board representation
- `src/chess_engine/core/move_generator.py` — legal move generation
- `src/chess_engine/core/search_info.py` — cooperative cancellation token
- `src/chess_engine/engine/v6/__init__.py` — native module auto-build
- `chess-ui/src/hooks/useChessGame.js` — frontend game state + API calls
- `tests/conftest.py` — shared pytest fixtures
