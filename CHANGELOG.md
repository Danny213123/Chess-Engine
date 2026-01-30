# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  - `main/client/` - React application
  - `main/server/` - FastAPI REST endpoints

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
