# Technology Stack

**Analysis Date:** 2026-05-15

## Languages

**Primary:**
- Python 3.12 (recommended), 3.10+ supported - Engine implementations (`v1`-`v6`), FastAPI server, build tooling. Pin file: `.python-version` (`3.12`). Declared in `pyproject.toml` (`requires-python = ">=3.10"`).
- JavaScript (ES Modules / CommonJS) - React frontend (`client/`) and Node CLI (`cli/`). Node engine constraint: `^20.19.0 || >=22.12.0` (declared in both `package.json` and `client/package.json`).
- C++17 - Optional native V6 chess engine in `src/chess_engine/engine/v6/src/*.cpp` and `src/chess_engine/engine/v6/include/*.hpp`. Bound to Python via pybind11.

**Secondary:**
- JSX - React component files (`client/src/App.jsx`, `client/src/CustomBoard.jsx`, `client/src/main.jsx`).
- CMake - V6 native build configuration (`src/chess_engine/engine/v6/CMakeLists.txt`). Requires CMake >=3.15.

## Runtime

**Environment:**
- Python interpreter (CPython, version pinned to 3.12 via `.python-version`).
- Node.js runtime for the CLI (`cli/bin/chess-engine.js`) and the Vite dev server.
- Browser runtime for the React UI (production build served by FastAPI; dev served by Vite at `http://localhost:5173`).
- Optional CUDA runtime for V3's Numba CUDA kernels (see `src/chess_engine/engine/v3/cuda_kernels.py`); falls back to CPU when CUDA is unavailable.
- Optional OpenMP runtime for V6's C++ engine (`src/chess_engine/engine/v6/CMakeLists.txt` links `OpenMP::OpenMP_CXX` when found).

**Package Manager:**
- Python: uv (declared via `[tool.uv]` in `pyproject.toml`, package mode enabled). Lockfile: `uv.lock` (present, ~267 KB).
- Node (root CLI): npm. Lockfile: not present at repo root for the CLI workspace (no `package-lock.json` next to root `package.json`).
- Node (frontend): npm. Lockfile: `client/package-lock.json` (present).

## Frameworks

**Core (Backend):**
- FastAPI - HTTP API for game state, moves, AI moves, engine selection, undo/redo, and search-history export. Entry: `src/chess_engine/server/app.py`.
- Uvicorn `[standard]` - ASGI server launched by `run_ui.py` (`uvicorn.run("chess_engine.server.app:app", host="0.0.0.0", port=8000)`).
- Pydantic - Request/response models in `src/chess_engine/server/models.py` and inline `BaseModel` classes in `src/chess_engine/server/app.py`.

**Core (Frontend):**
- React 19 (`react`, `react-dom` `^19.2.0`) - SPA in `client/src/App.jsx`.
- Vite 7 (`vite ^7.2.4`, `@vitejs/plugin-react ^5.1.1`) - Dev server and production bundler. Config: `client/vite.config.js` (proxies `/api` to `http://localhost:8000`).
- react-chessboard `^5.8.6` - Chessboard UI primitive (used inside `client/src/CustomBoard.jsx`).
- recharts `^3.7.0` - Search statistics charting (depth, nodes, NPS, time) in the right panel of `client/src/App.jsx`.
- axios `^1.13.4` - HTTP client to the FastAPI backend.

**Testing:**
- pytest - Python test suite in `tests/`. Declared under `[dependency-groups].dev` in `pyproject.toml` and used as `python3 -m uv run --group dev pytest -q` (per `README.md`). Also referenced via `pytest` in the `all` extra.
- httpx - HTTP client for FastAPI test interactions (`[dependency-groups].dev` and `all`).
- requests - General-purpose HTTP client for tests (`[dependency-groups].dev` and `all`).

**Build / Dev:**
- setuptools `>=61.0` + wheel - Python build backend (`[build-system]` in `pyproject.toml`).
- pybind11 - Optional, gates the V6 native build (`[project.optional-dependencies].build` in `pyproject.toml`). CMake locates it via `python -m pybind11 --cmakedir` and falls back to `FetchContent` of `pybind11 v2.12.0` (see `src/chess_engine/engine/v6/CMakeLists.txt`).
- CMake `>=3.15` and a C++17 compiler - Required only for V6 native builds. Driven by `src/chess_engine/engine/v6/native_build.py`.
- ESLint 9 (flat config: `client/eslint.config.js`) with `@eslint/js`, `eslint-plugin-react-hooks ^7.0.1`, `eslint-plugin-react-refresh ^0.4.24`, and `globals ^16.5.0` - Frontend linting (`npm run lint --prefix client`).
- TypeScript types only (`@types/react`, `@types/react-dom`) - No TypeScript source; types installed for editor support.

## Key Dependencies

**Critical (Python, runtime):**
- `fastapi` - Web framework (no version pin; latest resolved via uv).
- `uvicorn[standard]` - ASGI server.
- `pydantic` - Validation/serialization for API models.
- `numpy` - Numerical arrays, used extensively across V3+ engines (e.g. `src/chess_engine/engine/v3/cpu_kernels.py`, `cuda_kernels.py`).
- `numba` - JIT and CUDA acceleration for evaluation kernels (`src/chess_engine/engine/v3/cpu_kernels.py` imports `numba`, `int32`, `float32`, `void`; `cuda_kernels.py` imports `from numba import cuda`).

**Critical (Frontend, runtime):**
- `react ^19.2.0`, `react-dom ^19.2.0`
- `react-chessboard ^5.8.6`
- `recharts ^3.7.0`
- `axios ^1.13.4`

**Optional Extras (declared in `pyproject.toml`):**
- `visual` extra: `pygame` - Powers the legacy desktop visualizer in `src/chess_engine/visual.py` (`import pygame`) and `src/chess_engine/visual_helpers.py`.
- `build` extra: `pybind11` - Required to compile V6 native module.
- `server` extra: same as default runtime deps.
- `all` extra: union of runtime + `pygame`, `httpx`, `pytest`, `requests`.

**Infrastructure / Build:**
- `pybind11` (build extra) - C++ <-> Python bridge for V6 (`src/chess_engine/engine/v6/src/python_bindings.cpp`).
- `setuptools`, `wheel` - Build backend.
- `uv` - Environment and dependency manager; auto-bootstrap logic lives in `run_ui.py` (`ensure_server_dependencies`, `CHESS_ENGINE_UV_BOOTSTRAPPED` env flag).

## Configuration

**Environment:**
- `CHESS_ENGINE_UV_BOOTSTRAPPED` - Internal flag set by `run_ui.py` to avoid recursive uv re-launches.
- `PYTHONPATH` - Set by the Node CLI to `path.join(ROOT_DIR, 'src')` when invoking native build / perft (see `cli/src/index.js`).
- No `.env` file present. `.env*` is in `.gitignore`.

**CLI / Engine Configuration:**
- Default config: `cli/src/config.js` (`DEFAULT_CONFIG`):
  - `threads: null` (auto, falls back to `os.cpus().length`)
  - `ttSize: 64` (MB)
  - `maxMemory: 512` (MB)
  - `timeLimit: 5000` (ms)
  - `v6Built: false`
  - `lastBuildTime: null`
  - `cmakePath: null`
- Persisted to `.chess-engine.json` in the working directory (gitignored).
- Example/template: `.chess-engine.example.json` (mirrors defaults).

**Build:**
- `pyproject.toml` - Python project metadata, dependencies, optional groups, uv config, setuptools package discovery (`where = ["src"]`, includes `chess_engine*`, `engine`, `main`).
- `package.json` (root) - Node CLI entry (`bin: chess-engine`), npm scripts (`start`, `cli`, `build:v6`, `build:client`, `server`, `dev`).
- `client/package.json` - Frontend deps and scripts (`dev`, `build`, `lint`, `preview`).
- `client/vite.config.js` - React plugin and `/api` -> `http://localhost:8000` dev proxy.
- `client/eslint.config.js` - ESLint flat config.
- `src/chess_engine/engine/v6/CMakeLists.txt` - C++17, pybind11 module target `v6_engine`, optional OpenMP linkage.

## Platform Requirements

**Development:**
- Python 3.12 (3.10+ acceptable) plus uv (`python3 -m pip install --user uv`).
- Node.js 20.19+ or 22.12+ and npm.
- Optional: CMake >=3.15 and a C++17 compiler for V6 native builds.
- Optional: NVIDIA GPU with CUDA-capable Numba install for V3 CUDA kernels.
- OS support: Windows (`.pyd` modules; CLI uses `python` on `win32`), macOS (`.so`/`.dylib`), Linux (`.so`) - see `_module_suffixes()` in `src/chess_engine/engine/v6/native_build.py`.

**Production:**
- Single-host Python ASGI deployment via `uvicorn` on `0.0.0.0:8000` (`run_ui.py` line 103). FastAPI mounts the prebuilt `client/dist/` as static assets when present (`src/chess_engine/server/app.py:212`).
- No container, cloud, or PaaS configuration is checked in.
- The same process serves API + static frontend; no separate web server is required.

---

*Stack analysis: 2026-05-15*
