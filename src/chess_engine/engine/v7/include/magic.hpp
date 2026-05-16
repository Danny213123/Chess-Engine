#pragma once

#include "types.hpp"

namespace v7 {

// =============================================================================
// MAGIC BITBOARD STRUCTURES
// =============================================================================

// Magic numbers for bishops and rooks (pre-computed)
extern const Bitboard BISHOP_MAGICS[64];
extern const Bitboard ROOK_MAGICS[64];

// Bit shifts for magic indexing
extern const int BISHOP_SHIFTS[64];
extern const int ROOK_SHIFTS[64];

// Initialize all magic bitboard tables
void init_magics();

// Attack masks (squares that can be attacked, excluding edges)
extern Bitboard BISHOP_MASKS[64];
extern Bitboard ROOK_MASKS[64];

// Attack tables (indexed by magic)
extern Bitboard BISHOP_ATTACKS[64][512];   // 512 = 2^9 (max relevant bits)
extern Bitboard ROOK_ATTACKS[64][4096];    // 4096 = 2^12

} // namespace v7
