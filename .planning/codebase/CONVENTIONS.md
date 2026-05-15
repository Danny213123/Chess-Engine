---
focus: quality
generated: 2026-05-14
---

# Code Conventions

## Tooling Status

- **Formatter**: None configured. No `black`, `ruff format`, or `isort` config in `pyproject.toml`.
- **Linter**: None configured. No `ruff`, `flake8`, or `pylint` config.
- **Type checker**: None configured. No `mypy` or `pyright` config.
- **Pre-commit hooks**: Not present (no `.pre-commit-config.yaml`).
- **Frontend**: ESLint config exists in `chess-ui/eslint.config.js` (Vite default), no Prettier.

Style is entirely convention-by-example, not enforced.

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

Mixed styles:
- Some modules use Google-style (`Args:`, `Returns:`)
- Some use plain prose
- Many functions have none

No docstring convention enforced.

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
