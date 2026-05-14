# Chess Engine

A Python chess engine with multiple engine versions, a FastAPI backend, a React chess UI, and optional V6 C++ acceleration.

## Requirements

- Python 3.12 recommended, Python 3.10+ supported
- [uv](https://docs.astral.sh/uv/)
- Node.js 20.19+ or 22.12+
- npm
- Optional for V6 native engine builds: CMake and a C++17 compiler

Install uv once if you do not already have it:

```bash
python3 -m pip install --user uv
```

## Run The App

From your current folder, enter the repository:

```bash
cd Chess-Engine
```

Start everything:

```bash
python3 -m uv run python run_ui.py
```

That command will:

- Create/use the uv-managed Python environment.
- Install backend Python dependencies from `pyproject.toml`.
- Install frontend npm dependencies if `client/node_modules` is missing.
- Build the React frontend if `client/dist` is missing.
- Start the FastAPI app.
- Open the browser to `http://localhost:8000`.

If the browser does not open automatically, visit:

```text
http://localhost:8000
```

## Frontend Development Mode

Use two terminals.

Terminal 1, start the backend:

```bash
python3 -m uv run python run_ui.py
```

Terminal 2, start Vite:

```bash
npm run dev --prefix client
```

Open:

```text
http://localhost:5173
```

The Vite dev server proxies `/api` requests to `http://localhost:8000`.

## CLI Commands

```bash
node cli/bin/chess-engine.js --help
node cli/bin/chess-engine.js build client
node cli/bin/chess-engine.js start
```

`run-all` builds V6 before starting, so use it only when your C++ build tools are installed:

```bash
node cli/bin/chess-engine.js run-all
```

## Optional V6 Build

Install the native build dependency group:

```bash
python3 -m uv sync --extra build
```

Build the V6 native extension:

```bash
node cli/bin/chess-engine.js build v6
```

If V6 is not built, selecting V6 in the app will try to build it automatically.
If CMake or a C++17 compiler is missing, the app keeps the previous engine selected
and reports the build error.

## Verify Everything

```bash
python3 -m uv run --group dev pytest -q
npm run lint --prefix client
npm run build --prefix client
node cli/bin/chess-engine.js --help
python3 -m uv run python -c "import chess_engine; import chess_engine.server.app"
```

## Python Usage

```python
from chess_engine.engine.v2.chess_engine import GameState

game = GameState()
print(game.get_fen())
print([str(move) for move in game.get_valid_moves()])
```

## Project Layout

- `src/chess_engine/engine/` - Python engines from `v1` through `v6`.
- `src/chess_engine/server/` - FastAPI app and game manager.
- `src/chess_engine/images/` - packaged chess piece assets for the pygame visualizer.
- `client/` - React/Vite frontend.
- `cli/` - Node CLI for building and running the app.
- `tests/` - pytest suite.

Compatibility shims remain for older `engine.*` and `main.*` imports, but new code should import from `chess_engine.*`.

## Troubleshooting

- If `python3 -m uv run python run_ui.py` cannot find uv, install uv with `python3 -m pip install --user uv`.
- If frontend installation fails, confirm Node and npm are installed with `node -v` and `npm -v`.
- If V6 fails to build, install CMake and a C++17 compiler, or use the Python engine versions.
