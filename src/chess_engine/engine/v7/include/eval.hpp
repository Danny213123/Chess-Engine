#pragma once

#include "board.hpp"

#include <string>

namespace v7 {

// =============================================================================
// V7 EVALUATION (Plan 04)
// =============================================================================
//
// Single entry point: evaluate(board) returns a centipawn score from the
// side-to-move's perspective (positive = good for STM). Implementation
// reads ALL weights via v7::coeffs::* extern symbols (EVAL-10) — Phase 4
// Texel tuning mutates coeffs.json which regenerates src/coeffs.cpp.
//
// EVAL-11 tapered combine formula `(mg * phase + eg * (24 - phase)) / 24`
// lives at the end of evaluate(). Phase is computed from non-king
// material using v7::coeffs::phase_weights_* and capped at 24 (Pesto
// total: 4N + 4B + 4R*2 + 2Q*4 = 24).
//
// The full term list (EVAL-01..11) is implemented in src/eval.cpp:
//   EVAL-01 material (mg + eg)
//   EVAL-02 PSTs (mg + eg, mirrored for black via sq ^ 56)
//   EVAL-03 phase (Pesto piece-phase weights)
//   EVAL-04 mobility (knight/bishop/rook/queen, mg + eg, indexed by attack count)
//   EVAL-05 bishop pair (mg + eg)
//   EVAL-06 rook on open / semi-open file
//   EVAL-07 threats (minor by pawn, rook by minor, queen by rook)
//   EVAL-08 king safety (attack-units table) + pawn structure (doubled/isolated/backward)
//   EVAL-09 tempo (mg + eg)
//   EVAL-10 every weight read from v7::coeffs::*  (no hardcoded constants)
//   EVAL-11 tapered combine

// Full evaluation — returns centipawns from side-to-move's perspective.
// fortress_enabled: value of options.UseFortressEval (D-11); defaults false
// so all call-sites that don't pass the parameter get the default-OFF behavior.
int evaluate(const Board& board, bool fortress_enabled = false);

// Static exchange estimate used by quiescence SEE pruning.
int see(const Board& board, Move m);

// Binding entry: parses a FEN, evaluates, returns the score.
// Python tests + future Phase 4 tuner harness use this.
int evaluate_entry(const std::string& fen);

// compute_phase: return the 0..256 Stockfish-style phase for a given board.
// Used by tests/test_v7_phase_blend.py to verify monotonicity.
// Exposed as a pybind11 binding via python_bindings.cpp.
int compute_phase(const Board& board);

} // namespace v7
