<!-- GSD:project-start source:PROJECT.md -->
## Project

**Chess-Engine**

A chess-playing application with a FastAPI backend, React 19 frontend, and a family of in-house chess engines (V1–V6) ranging from pure-Python to a native C++17 pybind11 module with optional CUDA and OpenMP acceleration. This milestone (V7) introduces a new, meaningfully stronger engine that beats V6 in head-to-head play while remaining selectable from the existing UI.

**Core Value:** V7 must play stronger chess than V6 in head-to-head gauntlets — measurable strength gain is the one thing that cannot fail.

### Constraints

- **Tech stack**: V7 must be a C++17 pybind11 module mirroring V6's build pattern. No new language additions; no replacement for FastAPI / React.
- **Performance**: V7 NPS must remain within roughly 20% of V6 NPS on the same hardware so UI responsiveness is preserved.
- **Validation**: Strength must be demonstrated by head-to-head gauntlet vs V6 — no other shipping criterion overrides this.
- **Repo size**: Syzygy tablebases are not bundled. Only an optional download script may be checked in.
- **UI surface**: Frontend changes are limited to adding V7 to the engine dropdown.
- **Tuning data**: Use the public Zurichess quiet-labeled set as the Texel ground truth. No proprietary or self-play data this milestone.
- **Compatibility**: V1–V6 engines must continue to work unchanged after V7 is added.
- **Concurrency**: Parallel search uses Lazy SMP only; do not introduce a new threading abstraction in the FastAPI server layer.
- **Cancellation**: V7 must honor the existing `SearchInfo` cooperative cancellation contract.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12 (recommended), 3.10+ supported - Engine implementations (`v1`-`v6`), FastAPI server, build tooling. Pin file: `.python-version` (`3.12`). Declared in `pyproject.toml` (`requires-python = ">=3.10"`).
- JavaScript (ES Modules / CommonJS) - React frontend (`client/`) and Node CLI (`cli/`). Node engine constraint: `^20.19.0 || >=22.12.0` (declared in both `package.json` and `client/package.json`).
- C++17 - Optional native V6 chess engine in `src/chess_engine/engine/v6/src/*.cpp` and `src/chess_engine/engine/v6/include/*.hpp`. Bound to Python via pybind11.
- JSX - React component files (`client/src/App.jsx`, `client/src/CustomBoard.jsx`, `client/src/main.jsx`).
- CMake - V6 native build configuration (`src/chess_engine/engine/v6/CMakeLists.txt`). Requires CMake >=3.15.
## Runtime
- Python interpreter (CPython, version pinned to 3.12 via `.python-version`).
- Node.js runtime for the CLI (`cli/bin/chess-engine.js`) and the Vite dev server.
- Browser runtime for the React UI (production build served by FastAPI; dev served by Vite at `http://localhost:5173`).
- Optional CUDA runtime for V3's Numba CUDA kernels (see `src/chess_engine/engine/v3/cuda_kernels.py`); falls back to CPU when CUDA is unavailable.
- Optional OpenMP runtime for V6's C++ engine (`src/chess_engine/engine/v6/CMakeLists.txt` links `OpenMP::OpenMP_CXX` when found).
- Python: uv (declared via `[tool.uv]` in `pyproject.toml`, package mode enabled). Lockfile: `uv.lock` (present, ~267 KB).
- Node (root CLI): npm. Lockfile: not present at repo root for the CLI workspace (no `package-lock.json` next to root `package.json`).
- Node (frontend): npm. Lockfile: `client/package-lock.json` (present).
## Frameworks
- FastAPI - HTTP API for game state, moves, AI moves, engine selection, undo/redo, and search-history export. Entry: `src/chess_engine/server/app.py`.
- Uvicorn `[standard]` - ASGI server launched by `run_ui.py` (`uvicorn.run("chess_engine.server.app:app", host="0.0.0.0", port=8000)`).
- Pydantic - Request/response models in `src/chess_engine/server/models.py` and inline `BaseModel` classes in `src/chess_engine/server/app.py`.
- React 19 (`react`, `react-dom` `^19.2.0`) - SPA in `client/src/App.jsx`.
- Vite 7 (`vite ^7.2.4`, `@vitejs/plugin-react ^5.1.1`) - Dev server and production bundler. Config: `client/vite.config.js` (proxies `/api` to `http://localhost:8000`).
- react-chessboard `^5.8.6` - Chessboard UI primitive (used inside `client/src/CustomBoard.jsx`).
- recharts `^3.7.0` - Search statistics charting (depth, nodes, NPS, time) in the right panel of `client/src/App.jsx`.
- axios `^1.13.4` - HTTP client to the FastAPI backend.
- pytest - Python test suite in `tests/`. Declared under `[dependency-groups].dev` in `pyproject.toml` and used as `python3 -m uv run --group dev pytest -q` (per `README.md`). Also referenced via `pytest` in the `all` extra.
- httpx - HTTP client for FastAPI test interactions (`[dependency-groups].dev` and `all`).
- requests - General-purpose HTTP client for tests (`[dependency-groups].dev` and `all`).
- setuptools `>=61.0` + wheel - Python build backend (`[build-system]` in `pyproject.toml`).
- pybind11 - Optional, gates the V6 native build (`[project.optional-dependencies].build` in `pyproject.toml`). CMake locates it via `python -m pybind11 --cmakedir` and falls back to `FetchContent` of `pybind11 v2.12.0` (see `src/chess_engine/engine/v6/CMakeLists.txt`).
- CMake `>=3.15` and a C++17 compiler - Required only for V6 native builds. Driven by `src/chess_engine/engine/v6/native_build.py`.
- ESLint 9 (flat config: `client/eslint.config.js`) with `@eslint/js`, `eslint-plugin-react-hooks ^7.0.1`, `eslint-plugin-react-refresh ^0.4.24`, and `globals ^16.5.0` - Frontend linting (`npm run lint --prefix client`).
- TypeScript types only (`@types/react`, `@types/react-dom`) - No TypeScript source; types installed for editor support.
## Key Dependencies
- `fastapi` - Web framework (no version pin; latest resolved via uv).
- `uvicorn[standard]` - ASGI server.
- `pydantic` - Validation/serialization for API models.
- `numpy` - Numerical arrays, used extensively across V3+ engines (e.g. `src/chess_engine/engine/v3/cpu_kernels.py`, `cuda_kernels.py`).
- `numba` - JIT and CUDA acceleration for evaluation kernels (`src/chess_engine/engine/v3/cpu_kernels.py` imports `numba`, `int32`, `float32`, `void`; `cuda_kernels.py` imports `from numba import cuda`).
- `react ^19.2.0`, `react-dom ^19.2.0`
- `react-chessboard ^5.8.6`
- `recharts ^3.7.0`
- `axios ^1.13.4`
- `visual` extra: `pygame` - Powers the legacy desktop visualizer in `src/chess_engine/visual.py` (`import pygame`) and `src/chess_engine/visual_helpers.py`.
- `build` extra: `pybind11` - Required to compile V6 native module.
- `server` extra: same as default runtime deps.
- `all` extra: union of runtime + `pygame`, `httpx`, `pytest`, `requests`.
- `pybind11` (build extra) - C++ <-> Python bridge for V6 (`src/chess_engine/engine/v6/src/python_bindings.cpp`).
- `setuptools`, `wheel` - Build backend.
- `uv` - Environment and dependency manager; auto-bootstrap logic lives in `run_ui.py` (`ensure_server_dependencies`, `CHESS_ENGINE_UV_BOOTSTRAPPED` env flag).
## Configuration
- `CHESS_ENGINE_UV_BOOTSTRAPPED` - Internal flag set by `run_ui.py` to avoid recursive uv re-launches.
- `PYTHONPATH` - Set by the Node CLI to `path.join(ROOT_DIR, 'src')` when invoking native build / perft (see `cli/src/index.js`).
- No `.env` file present. `.env*` is in `.gitignore`.
- Default config: `cli/src/config.js` (`DEFAULT_CONFIG`):
- Persisted to `.chess-engine.json` in the working directory (gitignored).
- Example/template: `.chess-engine.example.json` (mirrors defaults).
- `pyproject.toml` - Python project metadata, dependencies, optional groups, uv config, setuptools package discovery (`where = ["src"]`, includes `chess_engine*`, `engine`, `main`).
- `package.json` (root) - Node CLI entry (`bin: chess-engine`), npm scripts (`start`, `cli`, `build:v6`, `build:client`, `server`, `dev`).
- `client/package.json` - Frontend deps and scripts (`dev`, `build`, `lint`, `preview`).
- `client/vite.config.js` - React plugin and `/api` -> `http://localhost:8000` dev proxy.
- `client/eslint.config.js` - ESLint flat config.
- `src/chess_engine/engine/v6/CMakeLists.txt` - C++17, pybind11 module target `v6_engine`, optional OpenMP linkage.
## Platform Requirements
- Python 3.12 (3.10+ acceptable) plus uv (`python3 -m pip install --user uv`).
- Node.js 20.19+ or 22.12+ and npm.
- Optional: CMake >=3.15 and a C++17 compiler for V6 native builds.
- Optional: NVIDIA GPU with CUDA-capable Numba install for V3 CUDA kernels.
- OS support: Windows (`.pyd` modules; CLI uses `python` on `win32`), macOS (`.so`/`.dylib`), Linux (`.so`) - see `_module_suffixes()` in `src/chess_engine/engine/v6/native_build.py`.
- Single-host Python ASGI deployment via `uvicorn` on `0.0.0.0:8000` (`run_ui.py` line 103). FastAPI mounts the prebuilt `client/dist/` as static assets when present (`src/chess_engine/server/app.py:212`).
- No container, cloud, or PaaS configuration is checked in.
- The same process serves API + static frontend; no separate web server is required.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Tooling Status
- **Formatter**: None configured. No `black`, `ruff format`, or `isort` config in `pyproject.toml`.
- **Linter**: None configured. No `ruff`, `flake8`, or `pylint` config.
- **Type checker**: None configured. No `mypy` or `pyright` config.
- **Pre-commit hooks**: Not present (no `.pre-commit-config.yaml`).
- **Frontend**: ESLint config exists in `chess-ui/eslint.config.js` (Vite default), no Prettier.
## Python — Naming
- **Files / modules**: `snake_case.py` (e.g., `move_generator.py`, `chess_algorithm.py`)
- **Classes**: `PascalCase` (e.g., `GameManager`, `SearchInfo`, `Board`)
- **Functions / methods**: `snake_case` (e.g., `find_best_move`, `make_human_move`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEPTH`, `MAX_PLY`, `INFINITY`)
- **Private**: leading underscore `_helper` (used inconsistently)
## Python — Imports
- **Star imports are pervasive** in legacy modules: `from .bitboard_helpers import *`. New code should avoid this — it pollutes namespaces and breaks tooling.
- Some modules mutate `sys.path` at import time (compatibility shims for older engine versions). Avoid extending this pattern.
- Standard ordering (stdlib → third-party → local) followed loosely; not enforced.
## Python — Type Hints
- **Partial coverage**. Newer modules (`server/`, parts of `core/`) use type hints; older engines (`v1`, `v2`, parts of `v3`) have none.
- No `from __future__ import annotations` consistency.
- `mypy` is not run, so type hints are advisory only.
## Python — Docstrings
- Some modules use Google-style (`Args:`, `Returns:`)
- Some use plain prose
- Many functions have none
## Python — Error Handling
- `try/except` used pragmatically; **bare `except:` blocks appear in legacy engine code** — these silently swallow all errors including KeyboardInterrupt. Should be `except Exception:` at minimum.
- HTTP layer raises `HTTPException` with appropriate status codes.
- Engine layer prefers returning sentinel values (e.g., `None` move) over raising.
## Python — Patterns
- **Singletons via module-global instances**: `gm = GameManager()` at module load, `device = Device()`. Hard to mock in tests.
- **String-based dispatch**: `if engine == "v1": ...` ladder in `GameManager.ai_move`. New engines require editing the ladder.
- **Numba JIT**: `@njit` decorators on hot paths in core eval; `@cuda.jit` for GPU kernels in v4b.
- **Dataclasses**: Used for `SearchInfo` and a few other value types; not consistent across the codebase.
## Logging vs Print
- **`print()` used as logging throughout production paths** — engines, GameManager, server. Roughly 70 occurrences across non-test code. The `logging` module is not configured.
- For new code, prefer `logging.getLogger(__name__)` over `print()`.
## Frontend — JavaScript / React
- **Components**: `PascalCase.jsx`, function components with hooks (no class components).
- **Hooks**: `useXxx.js`, prefix `use` enforced by ESLint react-hooks rule.
- **State**: Local `useState` + custom hooks (e.g., `useChessGame`). No Redux/Zustand.
- **Side effects**: `useEffect` with explicit dependency arrays.
- **API calls**: Centralized in `chess-ui/src/api/client.js` (axios instance). Components call hooks, not axios directly.
- **Styles**: Plain CSS files colocated with components. No CSS modules, no Tailwind, no styled-components.
- **Imports**: ES modules, `.jsx` extension on JSX-containing files.
## Async
- **Backend**: FastAPI route handlers are mostly synchronous (`def`, not `async def`). Engine search is CPU-bound and blocks the request thread.
- **Frontend**: `async/await` with `try/catch`; loading state managed via `useState`.
## Comments
- Sparse. Hot loops in engine code occasionally have comments explaining bitboard tricks or move-ordering heuristics — these are valuable, keep them.
- Avoid commentary on what the code does; prefer comments on *why* (especially around perf hacks).
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## High-Level Pattern
- **Frontend (SPA)** — React 19 + Vite, talks to backend via REST/JSON over `axios`. No state management library; component-local `useState` + a small custom hook layer.
- **Backend (HTTP)** — FastAPI app exposing game endpoints. Stateful: a single in-process `GameManager` singleton holds the active game.
- **Domain core** — Engine package containing board/move generation, evaluation, search algorithms, and multiple engine versions (v1–v6).
- **Native acceleration (optional)** — V6 uses a pybind11 C++17 module built via CMake `FetchContent`. CUDA acceleration via Numba for V4b GPU service.
## Layers
```
```
## Data Flow: AI Move
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
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
