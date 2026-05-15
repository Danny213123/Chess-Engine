---
focus: quality
generated: 2026-05-14
---

# Testing

## Frameworks

- **Primary**: `pytest` (declared in `pyproject.toml` dev deps)
- **Secondary**: `unittest` — some older test files inherit from `unittest.TestCase`. Both run under `pytest` discovery.
- **HTTP**: `fastapi.testclient.TestClient` for endpoint tests
- **Frontend**: No test framework configured in `chess-ui/package.json` — no Jest, no Vitest, no Playwright.

## Layout

```
tests/
  conftest.py              # Shared fixtures
  test_board.py
  test_move_generator.py
  test_evaluator.py
  test_game_manager.py
  test_server.py           # FastAPI TestClient
  test_engine_v2.py
  test_engine_v3.py
  test_engine_v6.py
  test_perft.py            # Move generation correctness via perft counts
  ... (16 files total, ~89 test functions)
```

## Coverage by Component

| Component | Coverage |
|---|---|
| `core/board.py` | Good |
| `core/move_generator.py` | Good (perft tests) |
| `core/evaluator.py` | Partial |
| `server/main.py` | Partial (TestClient) |
| `server/game_manager.py` | Partial |
| `engine/v2/` | Some |
| `engine/v3/` | Some |
| `engine/v6/` | Some (depends on native build succeeding) |
| `engine/v1, v4, v4b, v4c, v5, v5a..d` | **Essentially untested** |
| `chess-ui/` | Zero |

## Fixtures

`tests/conftest.py` provides shared fixtures — typically a starting `Board`, sample `GameState`, and a `TestClient` for the FastAPI app.

## Patterns

- **Perft tests** verify move generation by counting leaf nodes at fixed depths from known positions (Kiwipete, etc.). These are the most reliable correctness tests in the suite.
- **Engine smoke tests** instantiate an engine and call `find_best_move` on a position, asserting the returned move is legal and within a time budget.
- **Server tests** use `TestClient` to POST `/move`, `/ai-move` and assert response shape.

## Mocking

- `unittest.mock.patch` used sporadically.
- **Stale patch path bug**: `patch("engine.v2.chess_algorithm.DEPTH", 1)` exists in some tests but is a **no-op** because the real import path is `chess_engine.engine.v2.chess_algorithm`. The patch silently does nothing and tests run at full depth — they pass but waste time. Worth fixing during any test cleanup.
- Engines themselves are mostly tested directly (no engine mocking) since the engine *is* the unit under test.

## Coverage Tooling

- **None configured.** No `coverage.py` or `pytest-cov` in dev deps.

## CI

- **No CI pipeline.** No `.github/workflows/`, no GitLab CI, no Jenkins. Tests run on developer machines only.

## Running Tests

```
uv run pytest
uv run pytest tests/test_perft.py
uv run pytest -v
```

## Known Test Issues

1. **Stale `patch()` paths** (see Mocking) — silently no-op in `test_engine_v2.py` and possibly others.
2. **V6 tests fail without native build** — if `pybind11` build has not run, `engine/v6/__init__.py` build step may fail under test runner depending on toolchain availability.
3. **Engines v1/v4/v4b/v4c/v5/v5b/v5c/v5d have no dedicated test files** — regressions in these versions go undetected.
4. **No frontend tests** — `chess-ui` is entirely untested.
