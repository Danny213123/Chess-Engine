---
focus: concerns
generated: 2026-05-14
---

# Concerns

Technical debt, fragile areas, security issues, and known bugs. Triaged by impact.

## Architecture / Maintainability

### Engine version sprawl (HIGH)
12+ engine subpackages (`v1, v2, v3, v4, v4b, v4c, v5, v5a, v5b, v5c, v5d, v6`) with substantial copy-paste between v5 family. Bug fixes must be applied N times. Many versions are essentially abandoned but still loadable via the `GameManager` ladder.
- **Files**: `src/chess_engine/engine/v*/`
- **Suggested fix**: Decide which engines are "supported" (probably v3, v6, maybe v4b for GPU) and archive the rest. Replace string-comparison ladder with a registry dict.

### String-comparison engine dispatch (MEDIUM)
`GameManager.ai_move` selects the engine via an `if/elif` ladder on the engine name. Every new engine requires editing this method.
- **File**: `src/chess_engine/server/game_manager.py`
- **Fix**: Engine registry dict `ENGINES = {"v3": v3.find_best_move, ...}`.

### Module-global singletons (MEDIUM)
`gm = GameManager()` instantiated at module load. Same for `Device`. Makes multi-game support and unit testing harder.
- **Files**: `src/chess_engine/server/game_manager.py`, `src/chess_engine/core/device.py`
- **Fix**: Construct in FastAPI app factory or via dependency injection.

### Legacy compatibility shims (LOW-MEDIUM)
Several engine modules mutate `sys.path` at import time to find legacy locations. Brittle, surprising, and breaks tooling.
- **Files**: scattered across older `engine/v*/` modules

## Logging / Observability

### `print()` as logging (MEDIUM)
~70 `print()` calls in production code paths (engines, GameManager, server). The `logging` module is not configured. No log levels, no structured logs, no way to silence noisy engine output in production.
- **Fix**: Configure `logging` in `server/main.py`, replace prints incrementally.

## Threading / Concurrency

### V4b GPU service stop() deadlock risk (HIGH)
The V4b GPU service `stop()` method has potential deadlock conditions when canceling an in-flight CUDA kernel — depends on whether the CUDA stream completes before the joining thread times out.
- **File**: `src/chess_engine/engine/v4b/` (gpu service module)
- **Fix**: Audit cancellation path; consider a timeout-with-force-kill fallback.

### Synchronous engine in request thread (MEDIUM)
Engines run inline in the FastAPI request handler. Long searches block the event loop worker thread. Multiple concurrent `/ai-move` requests serialize.
- **Fix**: Move engine work to a process pool (engines are CPU-bound; threads do not help due to GIL except where Numba releases it).

## Security

### CORS open to `*` with credentials (HIGH)
`CORSMiddleware` allows all origins (`*`) AND credentials. Browsers reject this combination on real cross-origin requests, but it indicates intent that is wrong for any deployment beyond localhost.
- **File**: `src/chess_engine/server/main.py` (CORS setup)
- **Fix**: Restrict `allow_origins` to known frontend origins; only enable `allow_credentials` if cookies/auth are actually used.

### Server binds to 0.0.0.0 by default (MEDIUM)
Default uvicorn binding exposes the API on all interfaces. Fine for containers behind a reverse proxy; risky on a dev laptop on a public Wi-Fi.
- **Fix**: Default to `127.0.0.1`; require explicit `--host 0.0.0.0` for non-local serving.

### No auth (LOW for current scope)
There is no auth on any endpoint. Acceptable for a single-player local app; flag if multi-user deployment is ever considered.

## Error Handling

### Bare except: blocks (MEDIUM)
Several legacy engine modules use bare `except:` which swallows `KeyboardInterrupt` and `SystemExit`. Makes Ctrl-C unreliable during long searches.
- **Fix**: Replace with `except Exception:` at minimum.

## Performance

### V6 native build on first import (MEDIUM)
`engine/v6/__init__.py` triggers a CMake build the first time it is imported. First request after a fresh checkout can take 30s+ silently. No build caching strategy beyond CMake own incremental build.
- **Fix**: Move build to an explicit `make` target or a post-install hook in `pyproject.toml`.

### Numba JIT warmup latency (LOW)
First call to any `@njit`-decorated function pays JIT compilation cost (~1–5s). Affects first `/ai-move` after server start.
- **Fix**: Warm up JIT functions during app startup (call them once on dummy inputs).

## Known TODOs in Code

### V6 history scores not integrated (MEDIUM)
`src/chess_engine/engine/v6/src/movegen.cpp:423` — TODO marker, history-heuristic scores computed but not used by move ordering. Costs some search efficiency.

## Testing Gaps

See `TESTING.md` for full breakdown. Highlights:
- Engines v1/v3/v4/v4b/v4c/v5/v5b/v5c/v5d essentially untested
- Stale `patch()` paths silently no-op
- Zero frontend tests
- No CI

## Build / Tooling

- No formatter, linter, type checker, pre-commit hooks, or CI configured (see `CONVENTIONS.md`).
- No Dockerfile, no deployment manifests.
- Frontend `chess-ui/` is a separate npm workspace not integrated with Python tooling — `uv` will not install/build it.
