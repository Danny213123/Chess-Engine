# External Integrations

**Analysis Date:** 2026-05-15

> **Summary:** This is a self-contained desktop/local-first chess engine project. It does not call out to any third-party SaaS APIs, authentication providers, payment processors, or hosted databases. All "integrations" are local: a FastAPI HTTP API, a React frontend that talks to it over `/api`, an optional pybind11 bridge to a C++ engine, optional CUDA via Numba, and an optional FetchContent pull from GitHub at build time.

## APIs & External Services

**Third-Party APIs:** None detected.
- No SDK clients for Stripe, AWS, Supabase, OpenAI, Anthropic, Google Cloud, etc. were found anywhere in `src/`, `client/src/`, or `cli/`.
- No outgoing HTTP calls to public services.

**Internal HTTP API (self-hosted):**
- FastAPI app at `src/chess_engine/server/app.py` exposes:
  - `GET  /api/state` - current `GameStateResponse`.
  - `POST /api/new-game` - reset game.
  - `POST /api/load-fen` - load arbitrary FEN.
  - `POST /api/move` - apply human move (LAN: `start_sq`, `end_sq`, optional `promotion`).
  - `POST /api/ai-move` - run engine search and play best move.
  - `POST /api/hint` - return best moves from optional `start_sq`.
  - `POST /api/engine` - select engine version per color (`v3`, `v4*`, `v5*`, `v6`, or `human`).
  - `POST /api/stop` - cancel an in-flight engine search.
  - `POST /api/undo`, `POST /api/redo` - history navigation.
  - `GET  /api/search-history/export` - download per-move search statistics as JSON attachment.
- Frontend client: `client/src/App.jsx` uses `axios` against relative `/api/*` paths; Vite dev server proxies them to `http://localhost:8000` (`client/vite.config.js`).

## Data Storage

**Databases:** None.
- No SQL or NoSQL client libraries (no SQLAlchemy, sqlite3 usage, asyncpg, motor, redis, etc.) are imported.
- All gameplay state lives in memory in a single `GameManager` instance: `gm = GameManager()` in `src/chess_engine/server/app.py:21`.

**File Storage:**
- Local filesystem only.
- Static assets: chess piece PNGs packaged at `src/chess_engine/images/*.png` (declared in `[tool.setuptools.package-data]` of `pyproject.toml`).
- Zobrist hashing tables: `src/chess_engine/Zobrist_keys.txt` and `src/chess_engine/engine/v1/Zobrist_keys.txt`.
- Frontend production build: `client/dist/` (mounted as static at `/` by `src/chess_engine/server/app.py:212-213`).
- CLI persistent settings: `.chess-engine.json` in the working directory (gitignored). Schema in `cli/src/config.js` (`DEFAULT_CONFIG`).
- Match-analysis export: streamed inline as `application/json` via `/api/search-history/export` (no server-side storage); filename `match_analysis_<timestamp>.json` (`src/chess_engine/server/app.py:202-208`).

**Caching:**
- In-process transposition tables only (e.g. `src/chess_engine/engine/v3/chess_transposition_table.py`, `src/chess_engine/engine/v5*/tt.py`, V6 C++ `src/chess_engine/engine/v6/src/tt.cpp`).
- TT size configurable via `cli/src/config.js` `ttSize` (default 64 MB) and persisted to `.chess-engine.json`.
- No external cache (no Redis, Memcached, etc.).

## Authentication & Identity

**Auth Provider:** None.
- The FastAPI app has no auth middleware, no API keys, no OAuth, no session handling.
- CORS is wide-open: `allow_origins=["*"]`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]` in `src/chess_engine/server/app.py:13-19`. Acceptable for local-only use; not safe to expose publicly.

## Monitoring & Observability

**Error Tracking:** None.
- No Sentry, Rollbar, Bugsnag, Datadog, or similar SDK is imported.
- Errors propagate as `HTTPException` from FastAPI handlers (`src/chess_engine/server/app.py`).

**Logs:**
- Backend: stdout via `print(...)` (e.g. `run_ui.py`) and Uvicorn's default access/error logging.
- Frontend: in-app debug log buffer in `client/src/App.jsx` (`debugLog` state, capped at 100 entries) plus `console.log`.
- No structured logger (no `logging.getLogger`, `loguru`, `pino`, `winston`).
- No log shipping or aggregation.

## CI/CD & Deployment

**Hosting:** Local execution only. No deployment manifests detected.
- No `Dockerfile`, `docker-compose*.yml`, `Procfile`, `vercel.json`, `netlify.toml`, `fly.toml`, `render.yaml`, or Kubernetes manifests are present.
- Production "deploy" path is `python3 -m uv run python run_ui.py`, which serves API + static frontend on `0.0.0.0:8000` (`run_ui.py:103`).

**CI Pipeline:** None checked in.
- No `.github/`, `.gitlab-ci.yml`, `.circleci/`, `azure-pipelines.yml`, or similar configuration is committed.
- `.github` is not present in the repo tree.

## Environment Configuration

**Required env vars:** None for normal operation.
- `CHESS_ENGINE_UV_BOOTSTRAPPED` - Internal flag set automatically by `run_ui.py` to prevent recursive uv re-launch.
- `PYTHONPATH` - Set transiently by the Node CLI (`cli/src/index.js`) to include `<repo>/src` when invoking native build helpers and perft.

**Secrets location:** N/A. No secrets are required.
- `.env` and `.env.*` are gitignored (`.gitignore:22`) but no `.env*` files exist in the working tree.

## Webhooks & Callbacks

**Incoming:** None.
**Outgoing:** None.

## Native / Build-Time Integrations

These are not runtime service integrations, but they are the only places this repo reaches outside itself:

- **pybind11 (Python <-> C++ bridge):**
  - Optional dependency in `[project.optional-dependencies].build` of `pyproject.toml`.
  - Used by `src/chess_engine/engine/v6/src/python_bindings.cpp` to expose the V6 native engine to Python.
  - CMake locates it via `python -m pybind11 --cmakedir` first (`src/chess_engine/engine/v6/CMakeLists.txt:16-24`).

- **GitHub (build-time fetch, only if pybind11 is missing):**
  - `FetchContent_Declare(pybind11 GIT_REPOSITORY https://github.com/pybind/pybind11.git GIT_TAG v2.12.0)` in `src/chess_engine/engine/v6/CMakeLists.txt:31-36`.
  - This is the only outbound network call in the repo, and it only fires during the optional V6 build when pybind11 cannot be found locally.

- **CMake (`>=3.15`):**
  - Located via `shutil.which("cmake")` in `src/chess_engine/engine/v6/native_build.py:117`.

- **Numba CUDA (optional GPU acceleration for V3):**
  - `src/chess_engine/engine/v3/cuda_kernels.py` does `from numba import cuda` inside a try/except; sets `CUDA_AVAILABLE = cuda.is_available()` and degrades gracefully to CPU when CUDA is not installed.
  - `src/chess_engine/engine/v3/cpu_kernels.py` uses `numba` JIT for CPU evaluation kernels.
  - Companion device-selection logic: `src/chess_engine/engine/v3/device.py`.
  - V4b adds an additional GPU service layer: `src/chess_engine/engine/v4b/gpu_service.py`.

- **OpenMP (optional CPU parallelism for V6):**
  - `find_package(OpenMP QUIET)` in `src/chess_engine/engine/v6/CMakeLists.txt:55-58`; linked into `v6_engine` only if found.

- **pygame (optional desktop UI):**
  - `import pygame` in `src/chess_engine/visual.py` and `src/chess_engine/visual_helpers.py`.
  - Installed only via the `visual` extra of `pyproject.toml`.

## Notable Non-Integrations

- **No chess library dependency.** This project implements its own move generation, board representation, and search across `v1`-`v6`; it does not depend on `python-chess`, `chess.js`, Stockfish, or any external engine. (Stockfish was removed; see commit `3140916 chore: modernize repo and remove stockfish`.)
- **No telemetry, no analytics, no crash reporting.**
- **No external opening book or tablebase service.** Opening books are local Python data: `src/chess_engine/engine/v2/chess_opening_book.py`, `src/chess_engine/engine/v3/chess_opening_book.py`.

---

*Integration audit: 2026-05-15*
