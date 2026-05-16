# Requirements: Chess-Engine V7 Milestone

**Defined:** 2026-05-15
**Core Value:** V7 must play stronger chess than V6 in head-to-head gauntlets — measurable strength gain is the one thing that cannot fail.

## v1 Requirements

Requirements for the V7 milestone. Each maps to roadmap phases.

### Foundation

- [ ] **FOUND-01**: V7 native C++17 pybind11 module exists at `src/chess_engine/engine/v7/` (mirrors V6 layout)
- [ ] **FOUND-02**: V7 builds via CMake `FetchContent` of pybind11 v2.12.0 on Windows, Linux, macOS (matches V6 build pattern)
- [ ] **FOUND-03**: V7 exposes `find_best_move(game_state, valid_moves, engine, search_info)` matching the existing engine adapter contract
- [ ] **FOUND-04**: V7 honors the Python-side `SearchInfo` cancellation token (closing the V6 gap where it is currently ignored)
- [ ] **FOUND-05**: pybind11 binding wraps the search in `py::call_guard<py::gil_scoped_release>()` from day one
- [ ] **FOUND-06**: V7 ported board / movegen / magic / zobrist achieve perft parity vs V6 to depth 6 on the standard test suite (Kiwipete, position 3, position 4, etc.)
- [ ] **FOUND-07**: A `v7_uci` standalone CMake executable target is built alongside the pybind11 module (for fastchess integration)

### Search

- [ ] **SRCH-01**: PVS-flavored alpha-beta search with qsearch and iterative deepening
- [ ] **SRCH-02**: Aspiration windows with widening on fail-high/fail-low, capped to prevent infinite re-search loops
- [ ] **SRCH-03**: Adaptive null-move pruning (R varies with depth + eval margin) with explicit zugzwang guard (skip in pawn-only endings)
- [ ] **SRCH-04**: Log-table Late Move Reductions (LMR) with context adjustments (PV node, cut node, improving, in-check exclusions; re-search at `depth - 1` on fail-high)
- [ ] **SRCH-05**: Late Move Pruning (LMP), Reverse Futility Pruning (RFP), and Futility Pruning with tuned margins
- [ ] **SRCH-06**: Move ordering uses killer moves + history heuristic + counter-move heuristic + SEE-bucketed captures (good captures / equal captures / bad captures)
- [ ] **SRCH-07**: Continuation history and capture history (stretch within Phase 3)
- [ ] **SRCH-08**: Singular extensions with verification depth, gated to depth ≥ 8
- [ ] **SRCH-09**: Multi-cut pruning at cut nodes (depth ≥ 8) with conservative margins
- [ ] **SRCH-10**: ProbCut (gauntlet-gated — may be skipped if it does not net positive Elo)
- [ ] **SRCH-11**: Internal Iterative Reductions / Internal Iterative Deepening when no TT move is found
- [ ] **SRCH-12**: Check extensions and recapture extensions
- [ ] **SRCH-13**: Mate scores correctly adjusted by ply when stored in and retrieved from the TT (`score_to_tt` / `score_from_tt`)
- [ ] **SRCH-14**: Repetition detection works inside the tree (not only at root) and 50-move TT cutoff is handled correctly
- [ ] **SRCH-15**: Time management leaves at least a 10% safety margin to avoid time forfeits at the configured time control

### Eval

- [ ] **EVAL-01**: Tapered MG/EG evaluation with continuous phase blending (Stockfish-style 0–256 phase value)
- [ ] **EVAL-02**: Piece-Square Tables (PSTs) per piece + phase, stored as Texel-tunable coefficients
- [ ] **EVAL-03**: King safety using attacker-count → `SAFETY_TABLE[]` indexed lookup (not linear)
- [ ] **EVAL-04**: Pawn structure terms: passed, isolated, doubled, backward, connected/phalanx
- [ ] **EVAL-05**: Mobility per piece type (knight, bishop, rook, queen)
- [ ] **EVAL-06**: Bishop pair bonus, knight outpost bonus, rook on open / semi-open file, rook on 7th rank
- [ ] **EVAL-07**: Threats / hanging-piece eval terms (differentiator)
- [ ] **EVAL-08**: Pawn hash table for incremental pawn-structure eval (NPS recovery — helps the 20% budget)
- [ ] **EVAL-09**: Tempo bonus
- [ ] **EVAL-10**: Eval coefficients live in `coeffs.cpp` as the single source of truth, mutable at runtime via `set_coeff(name, val)`
- [ ] **EVAL-11**: `coeffs.cpp` is generated from `coeffs.json` to keep names in lockstep with the Texel pipeline

### Endgame

- [ ] **ENDG-01**: In-engine KPK bitbase (correctly classifies all 163,328 legal KPK positions)
- [ ] **ENDG-02**: Opposition evaluation for K vs K + P endings
- [ ] **ENDG-03**: Wrong-colored bishop + rook-pawn draw recognition (with king-distance check)
- [ ] **ENDG-04**: Continuous phase blending so endgame eval activates smoothly, not by a hard threshold
- [ ] **ENDG-05**: Conservative fortress hints (may be skipped entirely if false-positive rate is high — explicit phase decision point)

### Tablebases

- [ ] **TB-01**: Fathom (jdart1) integrated as a git submodule under `src/chess_engine/engine/v7/extern/fathom/`
- [ ] **TB-02**: Fathom configured via custom `tbconfig.h` override to reuse V7's own magic bitboard attack tables
- [ ] **TB-03**: Root probe uses `tb_probe_root_dtz` for 50-move-rule-aware best-move selection
- [ ] **TB-04**: In-search probe uses `tb_probe_wdl` only, gated by `popcount ≤ TB_LARGEST && halfmove == 0 && castling == 0 && depth ≥ threshold`
- [ ] **TB-05**: KPK in-engine eval short-circuits to Syzygy when in TB range (Syzygy wins on conflict)
- [ ] **TB-06**: Probe failures are detected and never silently treated as draws
- [ ] **TB-07**: Tablebase path is configurable via a `syzygyPath` key in `.chess-engine.json`; platform-aware separator (`;` on Windows, `:` on POSIX)
- [ ] **TB-08**: Optional `chess-engine syzygy download` CLI subcommand fetches 3-4-5 men by default (~1 GB) with `--6men` opt-in (~150 GB); tablebases are NOT bundled in the repo
- [ ] **TB-09**: Default storage path is `%LOCALAPPDATA%\chess-engine\syzygy\` on Windows, `~/.local/share/chess-engine/syzygy/` elsewhere
- [ ] **TB-10**: Init-time smoke test verifies file count + a KRk probe before V7 reports tablebases as active

### Parallelism

- [ ] **PAR-01**: Lockless transposition table using Hyatt-Mann XOR trick (two `std::atomic<uint64_t>` slots: `xkey = key XOR data`, `data`; `memory_order_relaxed`)
- [ ] **PAR-02**: TT entry layout packs move + score + depth + bound + age into 64 bits
- [ ] **PAR-03**: Lockless TT passes a TSan stress test (16 threads × 60 seconds of random probe/store) — run on Linux/macOS/WSL (TSan unavailable on MSVC)
- [ ] **PAR-04**: Lazy SMP thread pool with N `std::thread` workers; per-thread `Board`, `history`, `killers`, `counter-move`, `continuation history`, search stack
- [ ] **PAR-05**: Workers communicate only via the shared TT and a single atomic stop flag — no Python access from worker threads
- [ ] **PAR-06**: Depth-stagger pattern (Berserk-style) on helper threads for search divergence
- [ ] **PAR-07**: NPS scaling test: 4-thread NPS is ≥ 3× single-thread NPS (Lazy-SMP-is-actually-parallel gate; failing this means GIL is held)
- [ ] **PAR-08**: Cancellation latency test: `algo_v7.stop()` from Python interrupts search in < 50 ms
- [ ] **PAR-09**: 4-thread vs 1-thread V7 gauntlet shows ≥ 40 Elo gain (Lazy SMP is doing real work)

### Tuning

- [ ] **TUNE-01**: GediminasMasaitis/texel-tuner vendored under `tools/` (MIT license)
- [ ] **TUNE-02**: `scripts/fetch_tuning_data.py` downloads Zurichess `quiet-labeled.epd` (~725k positions) on demand
- [ ] **TUNE-03**: Position pre-filter drops in-check positions, positions where qsearch result ≠ static eval, and positions inside Syzygy TB range
- [ ] **TUNE-04**: K-factor fit **once** at start via golden-section search; persisted alongside the tuned coefficient JSON
- [ ] **TUNE-05**: Sparse coefficient extraction (only non-zero contributions per position) — required for fast iteration on 725k positions
- [ ] **TUNE-06**: 90/10 train/validation split; validation loss tracked to detect overfit
- [ ] **TUNE-07**: ADAM optimizer with L2 regularization
- [ ] **TUNE-08**: Multi-seed tuning (V6 seed + neutral seed + perturbed seed); gauntlet picks the winner
- [ ] **TUNE-09**: Post-tune, search-margin re-scaling pass (RFP / futility / probcut margins) proportional to the average-eval shift
- [ ] **TUNE-10**: Tuned `coeffs.json` committed to source; `coeffs.cpp` regenerated from it via codegen

### Gauntlet & Validation

- [ ] **GAUNT-01**: fastchess prebuilt binary checked into `tools/` (or fetched by script) for Windows/Linux/macOS
- [ ] **GAUNT-02**: `v7_uci` exposes a minimal UCI surface (uci/isready/setoption/position/go/stop/quit) sufficient for fastchess
- [ ] **GAUNT-03**: Gauntlet script runs V7 vs V6 with **identical** hash size, thread count, and time control; the exact fastchess command is persisted in every result file
- [ ] **GAUNT-04**: V6-vs-V6 sanity probe must return an Elo difference of approximately 0 before any V7-vs-V6 result is trusted
- [ ] **GAUNT-05**: Opening book seeding via `8moves_v3.pgn` (or equivalent balanced book) — gauntlet only, not used at play time
- [ ] **GAUNT-06**: Pentanomial SPRT with `elo0=0 elo1=10 alpha=0.05 beta=0.05` (or documented overrides)
- [ ] **GAUNT-07**: Result aggregator flags time forfeits separately from losses
- [ ] **GAUNT-08**: NPS regression check fails the build if V7 NPS drops more than 20% vs V6 on the same hardware
- [ ] **GAUNT-09**: Ship verdict requires SPRT pass in at least 2 independent runs at production thread count (≥ 1000 games each)

### Integration

- [ ] **INT-01**: `GameManager.ai_move` dispatches V7 (4-line edit: import + `AVAILABLE_ENGINES` entry + `set_engine_version` branch + `ai_move` dispatch with correctly wired `SearchInfo`)
- [ ] **INT-02**: V7 appears as an `<option value="v7">` entry in both engine selectors in `client/src/App.jsx` (white + black)
- [ ] **INT-03**: The "build may take a while" warning in `App.jsx` is updated to mention V7 as well as V6
- [ ] **INT-04**: `cli/src/config.js` gains `v7Built`, `syzygyPath`, `syzygyMaxPieces` keys (with sensible defaults)
- [ ] **INT-05**: `cli/src/index.js` gains `chess-engine build v7` and `chess-engine syzygy download` subcommands
- [ ] **INT-06**: `.gitignore` excludes V7 build artifacts; `.gitmodules` declares the Fathom submodule
- [ ] **INT-07**: `tests/test_v7_engine.py` covers: legal-game smoke test, perft parity, cancellation latency, NPS regression sentinel
- [ ] **INT-08**: V1–V6 engines continue to work unchanged after V7 is added (regression-tested via the existing pytest suite)
- [ ] **INT-09**: V7 plays a full game end-to-end through the existing React UI against V6 (C1 smoke milestone)

## v2 Requirements

Deferred to later milestones. Tracked but explicitly out of the V7 milestone roadmap.

### Strength

- **V2-STR-01**: NNUE (efficiently-updated neural eval) — potential future V8 milestone
- **V2-STR-02**: SPSA self-play tuning for search parameters
- **V2-STR-03**: 7-piece Syzygy support
- **V2-STR-04**: Opening book at play time

### UX

- **V2-UX-01**: In-app gauntlet UI (run V7-vs-V6 matches from the React frontend)
- **V2-UX-02**: Eval breakdown panel (show piece-by-piece eval contributions)
- **V2-UX-03**: Search diagnostics panel (tablebase hit indicator, PV display)
- **V2-UX-04**: MultiPV mode

### Refactor

- **V2-REF-01**: Replace `GameManager` engine string-comparison ladder with a registry dictionary
- **V2-REF-02**: Replace module-global `gm = GameManager()` singleton
- **V2-REF-03**: Consolidate v5 / v5b / v5c / v5d copy-paste forks

## Out of Scope

Explicitly excluded from this milestone. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| NNUE / neural eval | Adds training pipeline + neural infra — deferred to a possible V8 milestone (V2-STR-01) |
| AlphaZero-style MCTS + full-NN | Not aligned with HCE + alpha-beta milestone direction |
| SPSA tuning | Texel only this milestone; SPSA noisier and slower (V2-STR-02) |
| Opening book at play time | Test-suite book for gauntlet is in scope; play-time book is V2-STR-04 |
| Bundled Syzygy tablebases | 6-men is ~150 GB; optional download script only |
| CUDA / GPU acceleration | V7 is CPU/Lazy SMP only; no GPU code paths |
| 7-piece Syzygy | Tablebases prohibitively large; V2-STR-03 |
| MultiPV mode | Out per PROJECT.md (V2-UX-04) |
| UI eval/diagnostics panels | Engine-only milestone; UI work limited to dropdown (V2-UX-02/03) |
| In-app gauntlet UI | Developer tooling (fastchess) is sufficient (V2-UX-01) |
| `GameManager` ladder → registry refactor | Anti-pattern flagged separately; deferred (V2-REF-01) |
| Module-global `gm` singleton replacement | Same as above (V2-REF-02) |
| v5/v5b/v5c/v5d fork consolidation | Separate cleanup track; not folded into V7 (V2-REF-03) |
| Hard ELO target (+50 / +100 / +200) | Gauntlet "meaningfully stronger" is the ship signal |
| Fixed timeline | Quality over speed; ship when gauntlet shows clear improvement |
| Mobile / native app builds | Backend + browser only |
| Multi-user concurrency, persistence, accounts | Single in-process game model retained |

## Traceability

Populated by the roadmapper during ROADMAP.md creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| (filled by roadmapper) | | |

**Coverage:**
- v1 requirements: 70 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 70 ⚠️ (resolved by roadmapper)

---
*Requirements defined: 2026-05-15*
*Last updated: 2026-05-15 after initial definition*
