#include "eval.hpp"
#include "movegen.hpp"
#include <algorithm>
#include <cstdlib>

namespace v6 {

// =============================================================================
// PIECE-SQUARE TABLES
// =============================================================================

int PST_MG[6][64];
int PST_EG[6][64];
int PST[6][64];  // Legacy

// Midgame PST values (from white's perspective, a8=0, h1=63 after flip)
static constexpr int PAWN_PST_MG[64] = {
     0,   0,   0,   0,   0,   0,   0,   0,
    50,  50,  50,  50,  50,  50,  50,  50,
    10,  10,  20,  30,  30,  20,  10,  10,
     5,   5,  10,  25,  25,  10,   5,   5,
     0,   0,   0,  20,  20,   0,   0,   0,
     5,  -5, -10,   0,   0, -10,  -5,   5,
     5,  10,  10, -20, -20,  10,  10,   5,
     0,   0,   0,   0,   0,   0,   0,   0
};

static constexpr int PAWN_PST_EG[64] = {
     0,   0,   0,   0,   0,   0,   0,   0,
    80,  80,  80,  80,  80,  80,  80,  80,
    50,  50,  50,  50,  50,  50,  50,  50,
    30,  30,  30,  30,  30,  30,  30,  30,
    20,  20,  20,  20,  20,  20,  20,  20,
    10,  10,  10,  10,  10,  10,  10,  10,
     5,   5,   5,   5,   5,   5,   5,   5,
     0,   0,   0,   0,   0,   0,   0,   0
};

static constexpr int KNIGHT_PST_MG[64] = {
   -50, -40, -30, -30, -30, -30, -40, -50,
   -40, -20,   0,   0,   0,   0, -20, -40,
   -30,   0,  10,  15,  15,  10,   0, -30,
   -30,   5,  15,  20,  20,  15,   5, -30,
   -30,   0,  15,  20,  20,  15,   0, -30,
   -30,   5,  10,  15,  15,  10,   5, -30,
   -40, -20,   0,   5,   5,   0, -20, -40,
   -50, -40, -30, -30, -30, -30, -40, -50
};

static constexpr int BISHOP_PST_MG[64] = {
   -20, -10, -10, -10, -10, -10, -10, -20,
   -10,   0,   0,   0,   0,   0,   0, -10,
   -10,   0,   5,  10,  10,   5,   0, -10,
   -10,   5,   5,  10,  10,   5,   5, -10,
   -10,   0,  10,  10,  10,  10,   0, -10,
   -10,  10,  10,  10,  10,  10,  10, -10,
   -10,   5,   0,   0,   0,   0,   5, -10,
   -20, -10, -10, -10, -10, -10, -10, -20
};

static constexpr int ROOK_PST_MG[64] = {
     0,   0,   0,   0,   0,   0,   0,   0,
     5,  10,  10,  10,  10,  10,  10,   5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
     0,   0,   0,   5,   5,   0,   0,   0
};

static constexpr int QUEEN_PST_MG[64] = {
   -20, -10, -10,  -5,  -5, -10, -10, -20,
   -10,   0,   0,   0,   0,   0,   0, -10,
   -10,   0,   5,   5,   5,   5,   0, -10,
    -5,   0,   5,   5,   5,   5,   0,  -5,
     0,   0,   5,   5,   5,   5,   0,  -5,
   -10,   5,   5,   5,   5,   5,   0, -10,
   -10,   0,   5,   0,   0,   0,   0, -10,
   -20, -10, -10,  -5,  -5, -10, -10, -20
};

static constexpr int KING_PST_MG[64] = {
   -30, -40, -40, -50, -50, -40, -40, -30,
   -30, -40, -40, -50, -50, -40, -40, -30,
   -30, -40, -40, -50, -50, -40, -40, -30,
   -30, -40, -40, -50, -50, -40, -40, -30,
   -20, -30, -30, -40, -40, -30, -30, -20,
   -10, -20, -20, -20, -20, -20, -20, -10,
    20,  20,   0,   0,   0,   0,  20,  20,
    20,  30,  10,   0,   0,  10,  30,  20
};

static constexpr int KING_PST_EG[64] = {
   -50, -40, -30, -20, -20, -30, -40, -50,
   -30, -20, -10,   0,   0, -10, -20, -30,
   -30, -10,  20,  30,  30,  20, -10, -30,
   -30, -10,  30,  40,  40,  30, -10, -30,
   -30, -10,  30,  40,  40,  30, -10, -30,
   -30, -10,  20,  30,  30,  20, -10, -30,
   -30, -30,   0,   0,   0,   0, -30, -30,
   -50, -30, -30, -30, -30, -30, -30, -50
};

// =============================================================================
// EVALUATION MASKS
// =============================================================================

Bitboard FILE_MASKS[8];
Bitboard ADJACENT_FILES[8];
Bitboard RANK_MASKS[8];

void init_eval() {
    // Initialize file masks
    for (int f = 0; f < 8; ++f) {
        FILE_MASKS[f] = FILE_A << f;
    }

    // Initialize adjacent file masks
    ADJACENT_FILES[0] = FILE_MASKS[1];
    ADJACENT_FILES[7] = FILE_MASKS[6];
    for (int f = 1; f < 7; ++f) {
        ADJACENT_FILES[f] = FILE_MASKS[f-1] | FILE_MASKS[f+1];
    }

    // Initialize rank masks
    for (int r = 0; r < 8; ++r) {
        RANK_MASKS[r] = RANK_1 << (r * 8);
    }
}

void init_pst() {
    // First init evaluation masks
    init_eval();

    for (int sq = 0; sq < 64; ++sq) {
        // PST arrays are from white's perspective, rank 8 at top (index 0-7)
        // We need to flip for internal representation (a1=0)
        int flip_sq = sq ^ 56;  // Flip vertically

        // Midgame
        PST_MG[PAWN][sq] = PAWN_PST_MG[flip_sq];
        PST_MG[KNIGHT][sq] = KNIGHT_PST_MG[flip_sq];
        PST_MG[BISHOP][sq] = BISHOP_PST_MG[flip_sq];
        PST_MG[ROOK][sq] = ROOK_PST_MG[flip_sq];
        PST_MG[QUEEN][sq] = QUEEN_PST_MG[flip_sq];
        PST_MG[KING][sq] = KING_PST_MG[flip_sq];

        // Endgame (use midgame for most pieces, special for pawns and king)
        PST_EG[PAWN][sq] = PAWN_PST_EG[flip_sq];
        PST_EG[KNIGHT][sq] = KNIGHT_PST_MG[flip_sq];
        PST_EG[BISHOP][sq] = BISHOP_PST_MG[flip_sq];
        PST_EG[ROOK][sq] = 0;  // Rooks don't have positional preferences in endgame
        PST_EG[QUEEN][sq] = QUEEN_PST_MG[flip_sq];
        PST_EG[KING][sq] = KING_PST_EG[flip_sq];

        // Legacy PST (midgame)
        PST[PAWN][sq] = PST_MG[PAWN][sq];
        PST[KNIGHT][sq] = PST_MG[KNIGHT][sq];
        PST[BISHOP][sq] = PST_MG[BISHOP][sq];
        PST[ROOK][sq] = PST_MG[ROOK][sq];
        PST[QUEEN][sq] = PST_MG[QUEEN][sq];
        PST[KING][sq] = PST_MG[KING][sq];
    }
}

// =============================================================================
// COMPREHENSIVE EVALUATION
// =============================================================================

int evaluate(const Board& board) {
    int score_mg = 0;
    int score_eg = 0;
    int phase = 0;

    Bitboard white_occ = board.colors[WHITE];
    Bitboard black_occ = board.colors[BLACK];
    Bitboard all_occ = board.occupied();

    Bitboard white_pawns = board.pieces_of(WHITE, PAWN);
    Bitboard black_pawns = board.pieces_of(BLACK, PAWN);

    // King squares (used in multiple places)
    Square w_king_sq = board.king_square(WHITE);
    Square b_king_sq = board.king_square(BLACK);

    // =========================================================================
    // MATERIAL + PST
    // =========================================================================
    for (int p = PAWN; p <= KING; ++p) {
        // White pieces
        Bitboard white_pieces = board.pieces_of(WHITE, Piece(p));
        Bitboard bb = white_pieces;
        while (bb) {
            int sq = pop_lsb(bb);
            score_mg += PIECE_VALUES_MG[p] + PST_MG[p][sq];
            score_eg += PIECE_VALUES_EG[p] + PST_EG[p][sq];

            // Accumulate phase based on piece values
            if (p >= KNIGHT && p <= QUEEN) {
                phase += PIECE_VALUES_MG[p];
            }
        }

        // Black pieces (flip PST)
        Bitboard black_pieces = board.pieces_of(BLACK, Piece(p));
        bb = black_pieces;
        while (bb) {
            int sq = pop_lsb(bb);
            int flip_sq = sq ^ 56;  // Mirror for black
            score_mg -= PIECE_VALUES_MG[p] + PST_MG[p][flip_sq];
            score_eg -= PIECE_VALUES_EG[p] + PST_EG[p][flip_sq];

            if (p >= KNIGHT && p <= QUEEN) {
                phase += PIECE_VALUES_MG[p];
            }
        }
    }

    // =========================================================================
    // BISHOP PAIR
    // =========================================================================
    if (popcount(board.pieces_of(WHITE, BISHOP)) >= 2) {
        score_mg += BISHOP_PAIR_BONUS_MG;
        score_eg += BISHOP_PAIR_BONUS_EG;
    }
    if (popcount(board.pieces_of(BLACK, BISHOP)) >= 2) {
        score_mg -= BISHOP_PAIR_BONUS_MG;
        score_eg -= BISHOP_PAIR_BONUS_EG;
    }

    // =========================================================================
    // MOBILITY (affects both midgame and endgame)
    // =========================================================================

    // Knight mobility (MG only, matches v5d)
    Bitboard bb = board.pieces_of(WHITE, KNIGHT);
    while (bb) {
        int sq = pop_lsb(bb);
        Bitboard attacks = knight_attacks[sq] & ~white_occ;
        int mob = popcount(attacks);
        score_mg += mob * MOBILITY_KNIGHT;
    }
    bb = board.pieces_of(BLACK, KNIGHT);
    while (bb) {
        int sq = pop_lsb(bb);
        Bitboard attacks = knight_attacks[sq] & ~black_occ;
        int mob = popcount(attacks);
        score_mg -= mob * MOBILITY_KNIGHT;
    }

    // Bishop mobility (MG only, matches v5d)
    bb = board.pieces_of(WHITE, BISHOP);
    while (bb) {
        int sq = pop_lsb(bb);
        Bitboard attacks = bishop_attacks(sq, all_occ) & ~white_occ;
        int mob = popcount(attacks);
        score_mg += mob * MOBILITY_BISHOP;
    }
    bb = board.pieces_of(BLACK, BISHOP);
    while (bb) {
        int sq = pop_lsb(bb);
        Bitboard attacks = bishop_attacks(sq, all_occ) & ~black_occ;
        int mob = popcount(attacks);
        score_mg -= mob * MOBILITY_BISHOP;
    }

    // Rook mobility (MG only, matches v5d)
    bb = board.pieces_of(WHITE, ROOK);
    while (bb) {
        int sq = pop_lsb(bb);
        Bitboard attacks = rook_attacks(sq, all_occ) & ~white_occ;
        int mob = popcount(attacks);
        score_mg += mob * MOBILITY_ROOK;
    }
    bb = board.pieces_of(BLACK, ROOK);
    while (bb) {
        int sq = pop_lsb(bb);
        Bitboard attacks = rook_attacks(sq, all_occ) & ~black_occ;
        int mob = popcount(attacks);
        score_mg -= mob * MOBILITY_ROOK;
    }

    // =========================================================================
    // ROOK BONUSES
    // =========================================================================

    // White rooks
    bb = board.pieces_of(WHITE, ROOK);
    while (bb) {
        int sq = pop_lsb(bb);
        int file = file_of(sq);
        int rank = rank_of(sq);
        Bitboard f_mask = FILE_MASKS[file];

        // Open file (no pawns)
        if (!(white_pawns & f_mask) && !(black_pawns & f_mask)) {
            score_mg += ROOK_OPEN_FILE_BONUS;
            score_eg += ROOK_OPEN_FILE_BONUS / 2;
        }
        // Semi-open file (no friendly pawns)
        else if (!(white_pawns & f_mask)) {
            score_mg += ROOK_SEMI_OPEN_FILE_BONUS;
            score_eg += ROOK_SEMI_OPEN_FILE_BONUS / 2;
        }

        // Rook on 7th rank
        if (rank == 6) {  // Rank 7 (0-indexed)
            score_mg += ROOK_ON_SEVENTH_MG;
            score_eg += ROOK_ON_SEVENTH_EG;
        }
    }

    // Black rooks
    bb = board.pieces_of(BLACK, ROOK);
    while (bb) {
        int sq = pop_lsb(bb);
        int file = file_of(sq);
        int rank = rank_of(sq);
        Bitboard f_mask = FILE_MASKS[file];

        // Open file
        if (!(white_pawns & f_mask) && !(black_pawns & f_mask)) {
            score_mg -= ROOK_OPEN_FILE_BONUS;
            score_eg -= ROOK_OPEN_FILE_BONUS / 2;
        }
        // Semi-open file
        else if (!(black_pawns & f_mask)) {
            score_mg -= ROOK_SEMI_OPEN_FILE_BONUS;
            score_eg -= ROOK_SEMI_OPEN_FILE_BONUS / 2;
        }

        // Rook on 2nd rank (7th from black's perspective)
        if (rank == 1) {
            score_mg -= ROOK_ON_SEVENTH_MG;
            score_eg -= ROOK_ON_SEVENTH_EG;
        }
    }

    // =========================================================================
    // KNIGHT OUTPOSTS
    // =========================================================================

    // White knights
    bb = board.pieces_of(WHITE, KNIGHT);
    while (bb) {
        int sq = pop_lsb(bb);
        Bitboard sq_bb = square_bb(sq);
        int rank = rank_of(sq);
        int file = file_of(sq);

        // In enemy territory (ranks 5-7 for white, which is rank 4-6 in 0-indexed)
        if (rank >= 4) {
            // Check if protected by a pawn
            Bitboard pawn_defenders = pawn_attacks[BLACK][sq] & white_pawns;
            if (pawn_defenders) {
                // Check if cannot be attacked by enemy pawns
                Bitboard ahead_files = FILE_MASKS[file];
                if (file > 0) ahead_files |= FILE_MASKS[file - 1];
                if (file < 7) ahead_files |= FILE_MASKS[file + 1];

                // Mask for ranks ahead of the knight
                Bitboard ahead_ranks = 0;
                for (int r = rank + 1; r < 8; ++r) {
                    ahead_ranks |= RANK_MASKS[r];
                }

                if (!(black_pawns & ahead_files & ahead_ranks)) {
                    score_mg += KNIGHT_OUTPOST_BONUS_MG;
                    score_eg += KNIGHT_OUTPOST_BONUS_EG;
                }
            }
        }
    }

    // Black knights
    bb = board.pieces_of(BLACK, KNIGHT);
    while (bb) {
        int sq = pop_lsb(bb);
        int rank = rank_of(sq);
        int file = file_of(sq);

        // In enemy territory (ranks 2-4 for black, which is rank 1-3 in 0-indexed)
        if (rank <= 3) {
            // Check if protected by a pawn
            Bitboard pawn_defenders = pawn_attacks[WHITE][sq] & black_pawns;
            if (pawn_defenders) {
                // Check if cannot be attacked by enemy pawns
                Bitboard ahead_files = FILE_MASKS[file];
                if (file > 0) ahead_files |= FILE_MASKS[file - 1];
                if (file < 7) ahead_files |= FILE_MASKS[file + 1];

                // Mask for ranks behind the knight (from black's perspective)
                Bitboard behind_ranks = 0;
                for (int r = 0; r < rank; ++r) {
                    behind_ranks |= RANK_MASKS[r];
                }

                if (!(white_pawns & ahead_files & behind_ranks)) {
                    score_mg -= KNIGHT_OUTPOST_BONUS_MG;
                    score_eg -= KNIGHT_OUTPOST_BONUS_EG;
                }
            }
        }
    }

    // =========================================================================
    // BAD BISHOPS
    // =========================================================================

    // White bishops
    bb = board.pieces_of(WHITE, BISHOP);
    while (bb) {
        int sq = pop_lsb(bb);
        // Check if on light or dark square
        bool on_light = (square_bb(sq) & LIGHT_SQUARES) != 0;
        int blocked_pawns;
        if (on_light) {
            blocked_pawns = popcount(white_pawns & LIGHT_SQUARES);
        } else {
            blocked_pawns = popcount(white_pawns & DARK_SQUARES);
        }
        score_mg -= blocked_pawns * BAD_BISHOP_PENALTY_MG;
        score_eg -= blocked_pawns * BAD_BISHOP_PENALTY_EG;
    }

    // Black bishops
    bb = board.pieces_of(BLACK, BISHOP);
    while (bb) {
        int sq = pop_lsb(bb);
        bool on_light = (square_bb(sq) & LIGHT_SQUARES) != 0;
        int blocked_pawns;
        if (on_light) {
            blocked_pawns = popcount(black_pawns & LIGHT_SQUARES);
        } else {
            blocked_pawns = popcount(black_pawns & DARK_SQUARES);
        }
        score_mg += blocked_pawns * BAD_BISHOP_PENALTY_MG;
        score_eg += blocked_pawns * BAD_BISHOP_PENALTY_EG;
    }

    // =========================================================================
    // PAWN STRUCTURE (matches v5d exactly)
    // =========================================================================

    // White pawns - doubled, isolated, passed, connected
    bb = white_pawns;
    while (bb) {
        int sq = pop_lsb(bb);
        int file = file_of(sq);
        int rank = rank_of(sq);
        Bitboard f_mask = FILE_MASKS[file];

        // Doubled pawns - penalty for each pawn on a file with multiple pawns (v5d style)
        if (popcount(white_pawns & f_mask) > 1) {
            score_mg += DOUBLED_PAWN_PENALTY;
            score_eg += DOUBLED_PAWN_PENALTY;
        }

        // Isolated pawns (no friendly pawns on adjacent files)
        if (!(white_pawns & ADJACENT_FILES[file])) {
            score_mg += ISOLATED_PAWN_PENALTY;
            score_eg += ISOLATED_PAWN_PENALTY;
        }

        // Connected pawns (supported by another pawn)
        Bitboard pawn_defenders = pawn_attacks[BLACK][sq] & white_pawns;
        if (pawn_defenders) {
            score_mg += 5 + rank;  // Connected bonus increases with rank
            score_eg += 5 + rank;
        }

        // Passed pawns (no enemy pawns ahead on file or adjacent files)
        Bitboard check_mask = f_mask | ADJACENT_FILES[file];
        Bitboard ahead_ranks = 0;
        for (int r = rank + 1; r < 8; ++r) {
            ahead_ranks |= RANK_MASKS[r];
        }

        if (!(black_pawns & check_mask & ahead_ranks)) {
            score_mg += PASSED_PAWN_BONUS_MG[rank];
            score_eg += PASSED_PAWN_BONUS_EG[rank];

            // Bonus for king proximity to passed pawn in endgame
            int pawn_advance_sq = sq + 8;  // Square in front of pawn
            if (pawn_advance_sq < 64) {
                int dist_our_king = std::max(std::abs(file_of(w_king_sq) - file),
                                             std::abs(rank_of(w_king_sq) - (rank + 1)));
                int dist_their_king = std::max(std::abs(file_of(b_king_sq) - file),
                                               std::abs(rank_of(b_king_sq) - (rank + 1)));
                score_eg += (dist_their_king - dist_our_king) * 5;
            }
        }
    }

    // Black pawns - isolated, passed, connected
    bb = black_pawns;
    while (bb) {
        int sq = pop_lsb(bb);
        int file = file_of(sq);
        int rank = rank_of(sq);
        Bitboard f_mask = FILE_MASKS[file];

        // Isolated pawns
        if (!(black_pawns & ADJACENT_FILES[file])) {
            score_mg -= ISOLATED_PAWN_PENALTY;
            score_eg -= ISOLATED_PAWN_PENALTY;
        }

        // Connected pawns
        Bitboard pawn_defenders = pawn_attacks[WHITE][sq] & black_pawns;
        if (pawn_defenders) {
            score_mg -= 5 + (7 - rank);
            score_eg -= 5 + (7 - rank);
        }

        // Passed pawns (from black's perspective)
        Bitboard check_mask = f_mask | ADJACENT_FILES[file];
        Bitboard behind_ranks = 0;
        for (int r = 0; r < rank; ++r) {
            behind_ranks |= RANK_MASKS[r];
        }

        if (!(white_pawns & check_mask & behind_ranks)) {
            score_mg -= PASSED_PAWN_BONUS_MG[7 - rank];
            score_eg -= PASSED_PAWN_BONUS_EG[7 - rank];

            // King proximity bonus for black's passed pawn
            int pawn_advance_sq = sq - 8;
            if (pawn_advance_sq >= 0) {
                int dist_our_king = std::max(std::abs(file_of(b_king_sq) - file),
                                             std::abs(rank_of(b_king_sq) - (rank - 1)));
                int dist_their_king = std::max(std::abs(file_of(w_king_sq) - file),
                                               std::abs(rank_of(w_king_sq) - (rank - 1)));
                score_eg -= (dist_their_king - dist_our_king) * 5;
            }
        }
    }

    // =========================================================================
    // KING SAFETY
    // =========================================================================

    // White king safety (only matters in middlegame when king is on back ranks)
    if (w_king_sq < 16) {  // King on ranks 1-2
        int k_file = file_of(w_king_sq);
        int start_f = std::max(0, k_file - 1);
        int end_f = std::min(7, k_file + 1);

        for (int f = start_f; f <= end_f; ++f) {
            Bitboard f_mask = FILE_MASKS[f];

            // Check for open/semi-open files near king
            if (!(white_pawns & f_mask)) {
                if (black_pawns & f_mask) {
                    score_mg += KING_SEMI_OPEN_FILE;
                } else {
                    score_mg += KING_OPEN_FILE;
                }
            }
            // Missing pawn shield
            else if (!(white_pawns & f_mask & (RANK_2 | RANK_3))) {
                score_mg += KING_PAWN_SHIELD_MISSING;
            }
        }
    }

    // Black king safety
    if (b_king_sq >= 48) {  // King on ranks 7-8
        int k_file = file_of(b_king_sq);
        int start_f = std::max(0, k_file - 1);
        int end_f = std::min(7, k_file + 1);

        for (int f = start_f; f <= end_f; ++f) {
            Bitboard f_mask = FILE_MASKS[f];

            if (!(black_pawns & f_mask)) {
                if (white_pawns & f_mask) {
                    score_mg -= KING_SEMI_OPEN_FILE;
                } else {
                    score_mg -= KING_OPEN_FILE;
                }
            }
            else if (!(black_pawns & f_mask & (RANK_6 | RANK_7))) {
                score_mg -= KING_PAWN_SHIELD_MISSING;
            }
        }
    }

    // =========================================================================
    // TAPERED EVALUATION
    // =========================================================================

    if (phase > PHASE_TOTAL) phase = PHASE_TOTAL;

    int mg_weight = phase;
    int eg_weight = PHASE_TOTAL - phase;

    int score = (score_mg * mg_weight + score_eg * eg_weight) / PHASE_TOTAL;

    // Tempo bonus
    score += TEMPO_BONUS;

    // Return score relative to side to move
    return board.side_to_move == WHITE ? score : -score;
}

// =============================================================================
// MATERIAL VALUE
// =============================================================================

int material_value(const Board& board, Color c) {
    int value = 0;
    for (int p = PAWN; p <= QUEEN; ++p) {
        value += popcount(board.pieces_of(c, Piece(p))) * PIECE_VALUES[p];
    }
    return value;
}

// =============================================================================
// STATIC EXCHANGE EVALUATION
// =============================================================================

int see(const Board& board, Move m) {
    Square from = move_from(m);
    Square to = move_to(m);

    Piece attacker = board.piece_at(from);
    Piece victim = board.piece_at(to);

    if (victim == NO_PIECE) {
        // En passant or non-capture
        if (move_type(m) == EN_PASSANT) {
            return PIECE_VALUES[PAWN];
        }
        return 0;
    }

    int value = PIECE_VALUES[victim];

    // Simple SEE: if attacker is worth less than or equal to victim, good capture
    if (PIECE_VALUES[attacker] <= value) {
        return value;
    }

    // More valuable attacker - estimate conservatively
    return value - PIECE_VALUES[attacker] / 2;
}

// =============================================================================
// GAME PHASE
// =============================================================================

int game_phase(const Board& board) {
    int phase = 0;
    for (Color c : {WHITE, BLACK}) {
        phase += popcount(board.pieces_of(c, KNIGHT)) * PHASE_KNIGHT;
        phase += popcount(board.pieces_of(c, BISHOP)) * PHASE_BISHOP;
        phase += popcount(board.pieces_of(c, ROOK)) * PHASE_ROOK;
        phase += popcount(board.pieces_of(c, QUEEN)) * PHASE_QUEEN;
    }
    return phase;
}

} // namespace v6
