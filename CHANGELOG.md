# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.1] - 2026-02-05

### Added
- Automatic V6 native module build when selecting V6 from the API/UI.
- V6 opening-development evaluation terms for minor-piece development, center control, castling readiness, and early major-piece movement.
- Regression tests for V6 availability failures and optional native evaluation behavior.

### Changed
- V6 selection now preserves the previous engine if the native build fails.
- V6 native builds now use the shared Python/uv build helper from both the backend and CLI.

### Fixed
- V6 no longer falls back to the first legal move when the native module is missing, errors, or returns an illegal move.
- V6 tempo evaluation now rewards the side to move for both colors.
- V6 parallel search result metadata is initialized deterministically.

## [4.0.0] - 2026-02-04

### Added
- Canonical `src/` package layout under `src/chess_engine/`.
- Compatibility shims for legacy `main.*` and `engine.*` imports.
- Example local configuration file: `.chess-engine.example.json`.
- In-process FastAPI tests using `TestClient`.
- uv project management with `.python-version` and `uv.lock`.

### Changed
- Moved the React/Vite frontend from `main/client/` to `client/`.
- Moved runtime Python code, server code, visual assets, and V6 native sources from `main/` into `src/chess_engine/`.
- Updated package metadata, optional Python extras, Node engine requirements, CLI paths, and README setup instructions.
- Simplified local startup to `python3 -m uv run python run_ui.py`.
- `run_ui.py` now installs missing backend dependencies and builds the frontend automatically when needed.
- Updated search-history export to report only native engine search metrics.
- Moved transposition-table cache writes out of the repository tree.

### Removed
- Removed vendored third-party engine source, binary, wrapper, UI options, backend routes, and evaluation charts.
- Removed tracked machine-local `.chess-engine.json` in favor of ignored local config.
- Removed generated frontend builds, native build outputs, Python cache files, and local packaging artifacts from the tracked tree.

### Fixed
- Server imports no longer load the optional pygame visualizer.
- API engine selection now rejects unsupported engines with HTTP 400.
- Frontend lint errors from callback ordering and unused error state were resolved.
- `.gitignore` now allows required source files such as `CMakeLists.txt` while ignoring generated artifacts.

### Verified
- `python3 -m pytest -q`
- `npm ci --prefix client`
- `npm run lint --prefix client`
- `npm run build --prefix client`
- `node cli/bin/chess-engine.js --help`
- `python3 -c "import chess_engine; import chess_engine.server.app"`

---

## [3.0.0] - 2026-01-30

### Added
- **V3 Engine with GPU/CPU Support**:
  - `device.py` - Automatic CUDA detection with CPU fallback
  - `cuda_kernels.py` - Numba CUDA batch evaluation kernels
  - `parallel_search.py` - Thread pool for parallel root search
  - `chess_transposition_table.py` - Thread-safe TT with RLock

- **Thread Safety**:
  - Thread-local counters for search statistics
  - Locked history and killer move tables
  - Thread-safe transposition table with automatic eviction
  - Support for 15+ CPU threads on multi-core systems

- **GPU Acceleration (CUDA)**:
  - Batch position evaluation kernel
  - Automatic CPU fallback if CUDA unavailable
  - 512MB VRAM budget enforcement
  - Memory usage monitoring

### Dependencies
- Added `numba>=0.63.0` for CUDA support
- Added `llvmlite>=0.46.0` (numba dependency)

---

## [2.0.0] - 2026-01-30

### Added
- **V2 Engine Architecture**: Complete rewrite with modular design
  - `chess_engine.py` - Core game state and move generation
  - `chess_algorithm.py` - Negascout search with SEE, MVV-LVA, killer moves
  - `chess_heuristic_calculation.py` - Comprehensive evaluation function
  - `chess_opening_book.py` - 50+ opening position database
  - `chess_transposition_table.py` - Position caching
  - `chess_hash.py` - Zobrist hashing for position identification

- **Modern Web UI**: React + Vite frontend with FastAPI backend
  - `client/` - React application
  - `src/chess_engine/server/` - FastAPI REST endpoints

- **Comprehensive Evaluation Function**:
  - Material counting (centipawn values)
  - Piece-square tables with tapered evaluation
  - Bishop pair bonus (+50 cp)
  - Rook on open/semi-open files (+15-25 cp)
  - Passed pawn bonuses (up to +150 cp)
  - Pawn structure penalties (doubled/isolated)
  - King safety (pawn shield, castling bonus)

- **Search Enhancements**:
  - Negascout (Principal Variation Search)
  - Quiescence search with SEE pruning
  - Static Exchange Evaluation (SEE)
  - Check extensions
  - MVV-LVA move ordering
  - Killer moves heuristic
  - History heuristic
  - Transposition table with 1M entry limit

- **Test Suite**: 80 comprehensive tests covering:
  - Move generation
  - Special moves (castling, en passant, promotion)
  - Check/checkmate/stalemate detection
  - PGN import/export
  - Algorithm correctness
  - API endpoints

### Changed
- Restructured engine into `v1/` (legacy) and `v2/` (current) directories
- Disabled AI hints for V2 (performance optimization, will re-enable in V3)
- Search depth set to 5 for balanced speed/strength

### Fixed
- Repetition detection bug causing premature search termination
- Transposition table pollution from stale entries
- Move ordering for captures (now uses SEE)

## [1.0.0] - 2025-xx-xx

### Added
- Initial chess engine with basic move generation
- Pygame-based visual interface
- V1 search algorithm with alpha-beta pruning
