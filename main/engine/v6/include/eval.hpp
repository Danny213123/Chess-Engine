#pragma once

#include "board.hpp"
#include "movegen.hpp"

namespace v6 {

// =============================================================================
// PIECE VALUES (Midgame / Endgame)
// =============================================================================

constexpr int PIECE_VALUES_MG[6] = {100, 320, 330, 500, 900, 20000};
constexpr int PIECE_VALUES_EG[6] = {120, 300, 320, 550, 1000, 20000};

// Legacy - for backward compatibility
constexpr int PIECE_VALUES[6] = {100, 320, 330, 500, 900, 20000};

// =============================================================================
// PIECE-SQUARE TABLES (Midgame / Endgame)
// =============================================================================

extern int PST_MG[6][64];
extern int PST_EG[6][64];

// Legacy PST for backward compat
extern int PST[6][64];

void init_pst();

// =============================================================================
// EVALUATION BONUSES AND PENALTIES
// =============================================================================

// Tempo bonus for side to move
constexpr int TEMPO_BONUS = 10;

// Bishop pair
constexpr int BISHOP_PAIR_BONUS_MG = 30;
constexpr int BISHOP_PAIR_BONUS_EG = 50;

// Mobility weights per piece type
constexpr int MOBILITY_KNIGHT = 4;
constexpr int MOBILITY_BISHOP = 5;
constexpr int MOBILITY_ROOK = 2;
constexpr int MOBILITY_QUEEN = 1;

// Pawn structure
constexpr int DOUBLED_PAWN_PENALTY = -10;
constexpr int ISOLATED_PAWN_PENALTY = -20;
constexpr int BACKWARD_PAWN_PENALTY = -10;

// Passed pawn bonus by rank (from white's perspective, index 0 = rank 1)
// Matches v5d exactly: MG values, EG = MG * 2
constexpr int PASSED_PAWN_BONUS_MG[8] = {0, 10, 20, 40, 60, 100, 150, 0};
constexpr int PASSED_PAWN_BONUS_EG[8] = {0, 20, 40, 80, 120, 200, 300, 0};

// Rook bonuses
constexpr int ROOK_OPEN_FILE_BONUS = 40;
constexpr int ROOK_SEMI_OPEN_FILE_BONUS = 20;
constexpr int ROOK_ON_SEVENTH_MG = 30;
constexpr int ROOK_ON_SEVENTH_EG = 50;

// Knight outpost
constexpr int KNIGHT_OUTPOST_BONUS_MG = 25;
constexpr int KNIGHT_OUTPOST_BONUS_EG = 15;

// Bad bishop penalty (per blocked pawn)
constexpr int BAD_BISHOP_PENALTY_MG = 3;
constexpr int BAD_BISHOP_PENALTY_EG = 5;

// King safety
constexpr int KING_PAWN_SHIELD_MISSING = -10;
constexpr int KING_SEMI_OPEN_FILE = -25;
constexpr int KING_OPEN_FILE = -45;
constexpr int KING_ATTACK_WEIGHT[5] = {0, 10, 20, 40, 80};  // by attacker type

// =============================================================================
// GAME PHASE
// =============================================================================

// Phase values for tapering - based on non-pawn material
constexpr int PHASE_KNIGHT = 320;
constexpr int PHASE_BISHOP = 330;
constexpr int PHASE_ROOK = 500;
constexpr int PHASE_QUEEN = 900;

// Total phase at game start (4*N + 4*B + 4*R + 2*Q)
constexpr int PHASE_TOTAL = 4 * PHASE_KNIGHT + 4 * PHASE_BISHOP +
                            4 * PHASE_ROOK + 2 * PHASE_QUEEN;

// =============================================================================
// BITBOARD MASKS FOR EVALUATION
// =============================================================================

// File masks (already in types.hpp but repeated here for clarity)
extern Bitboard FILE_MASKS[8];
extern Bitboard ADJACENT_FILES[8];
extern Bitboard RANK_MASKS[8];

// Light and dark squares
constexpr Bitboard LIGHT_SQUARES = 0x55AA55AA55AA55AAULL;
constexpr Bitboard DARK_SQUARES = 0xAA55AA55AA55AA55ULL;

// Outpost masks - squares that can be outposts
constexpr Bitboard WHITE_OUTPOST_RANKS = RANK_4 | RANK_5 | RANK_6;
constexpr Bitboard BLACK_OUTPOST_RANKS = RANK_3 | RANK_4 | RANK_5;

// Initialize evaluation tables
void init_eval();

// =============================================================================
// EVALUATION FUNCTIONS
// =============================================================================

// Full evaluation (material + positional + tapered)
int evaluate(const Board& board);

// Material only (for SEE)
int material_value(const Board& board, Color c);

// Static Exchange Evaluation
int see(const Board& board, Move m);

// Get current game phase (0 = endgame, PHASE_TOTAL = opening)
int game_phase(const Board& board);

} // namespace v6
