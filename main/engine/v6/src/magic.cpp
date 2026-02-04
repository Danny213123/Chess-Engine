#include "magic.hpp"
#include "movegen.hpp"

namespace v6 {

// =============================================================================
// MAGIC NUMBERS (Pre-computed)
// =============================================================================

const Bitboard BISHOP_MAGICS[64] = {
    0x0002020202020200ULL, 0x0002020202020000ULL, 0x0004010202000000ULL, 0x0004040080000000ULL,
    0x0001104000000000ULL, 0x0000821040000000ULL, 0x0000410410400000ULL, 0x0000104104104000ULL,
    0x0000040404040400ULL, 0x0000020202020200ULL, 0x0000040102020000ULL, 0x0000040400800000ULL,
    0x0000011040000000ULL, 0x0000008210400000ULL, 0x0000004104104000ULL, 0x0000002082082000ULL,
    0x0004000808080800ULL, 0x0002000404040400ULL, 0x0001000202020200ULL, 0x0000800802004000ULL,
    0x0000800400A00000ULL, 0x0000200100884000ULL, 0x0000400082082000ULL, 0x0000200041041000ULL,
    0x0002080010101000ULL, 0x0001040008080800ULL, 0x0000208004010400ULL, 0x0000404004010200ULL,
    0x0000840000802000ULL, 0x0000404002011000ULL, 0x0000808001041000ULL, 0x0000404000820800ULL,
    0x0001041000202000ULL, 0x0000820800101000ULL, 0x0000104400080800ULL, 0x0000020080080080ULL,
    0x0000404040040100ULL, 0x0000808100020100ULL, 0x0001010100020800ULL, 0x0000808080010400ULL,
    0x0000820820004000ULL, 0x0000410410002000ULL, 0x0000082088001000ULL, 0x0000002011000800ULL,
    0x0000080100400400ULL, 0x0001010101000200ULL, 0x0002020202000400ULL, 0x0001010101000200ULL,
    0x0000410410400000ULL, 0x0000208208200000ULL, 0x0000002084100000ULL, 0x0000000020880000ULL,
    0x0000001002020000ULL, 0x0000040408020000ULL, 0x0004040404040000ULL, 0x0002020202020000ULL,
    0x0000104104104000ULL, 0x0000002082082000ULL, 0x0000000020841000ULL, 0x0000000000208800ULL,
    0x0000000010020200ULL, 0x0000000404080200ULL, 0x0000040404040400ULL, 0x0002020202020200ULL
};

const Bitboard ROOK_MAGICS[64] = {
    0x0080001020400080ULL, 0x0040001000200040ULL, 0x0080081000200080ULL, 0x0080040800100080ULL,
    0x0080020400080080ULL, 0x0080010200040080ULL, 0x0080008001000200ULL, 0x0080002040800100ULL,
    0x0000800020400080ULL, 0x0000400020005000ULL, 0x0000801000200080ULL, 0x0000800800100080ULL,
    0x0000800400080080ULL, 0x0000800200040080ULL, 0x0000800100020080ULL, 0x0000800040800100ULL,
    0x0000208000400080ULL, 0x0000404000201000ULL, 0x0000808010002000ULL, 0x0000808008001000ULL,
    0x0000808004000800ULL, 0x0000808002000400ULL, 0x0000010100020004ULL, 0x0000020000408104ULL,
    0x0000208080004000ULL, 0x0000200040005000ULL, 0x0000100080200080ULL, 0x0000080080100080ULL,
    0x0000040080080080ULL, 0x0000020080040080ULL, 0x0000010080800200ULL, 0x0000800080004100ULL,
    0x0000204000800080ULL, 0x0000200040401000ULL, 0x0000100080802000ULL, 0x0000080080801000ULL,
    0x0000040080800800ULL, 0x0000020080800400ULL, 0x0000020001010004ULL, 0x0000800040800100ULL,
    0x0000204000808000ULL, 0x0000200040008080ULL, 0x0000100020008080ULL, 0x0000080010008080ULL,
    0x0000040008008080ULL, 0x0000020004008080ULL, 0x0000010002008080ULL, 0x0000004081020004ULL,
    0x0000204000800080ULL, 0x0000200040008080ULL, 0x0000100020008080ULL, 0x0000080010008080ULL,
    0x0000040008008080ULL, 0x0000020004008080ULL, 0x0000800100020080ULL, 0x0000800041000080ULL,
    0x00FFFCDDFCED714AULL, 0x007FFCDDFCED714AULL, 0x003FFFCDFFD88096ULL, 0x0000040810002101ULL,
    0x0001000204080011ULL, 0x0001000204000801ULL, 0x0001000082000401ULL, 0x0001FFFAABFAD1A2ULL
};

const int BISHOP_SHIFTS[64] = {
    58, 59, 59, 59, 59, 59, 59, 58,
    59, 59, 59, 59, 59, 59, 59, 59,
    59, 59, 57, 57, 57, 57, 59, 59,
    59, 59, 57, 55, 55, 57, 59, 59,
    59, 59, 57, 55, 55, 57, 59, 59,
    59, 59, 57, 57, 57, 57, 59, 59,
    59, 59, 59, 59, 59, 59, 59, 59,
    58, 59, 59, 59, 59, 59, 59, 58
};

const int ROOK_SHIFTS[64] = {
    52, 53, 53, 53, 53, 53, 53, 52,
    53, 54, 54, 54, 54, 54, 54, 53,
    53, 54, 54, 54, 54, 54, 54, 53,
    53, 54, 54, 54, 54, 54, 54, 53,
    53, 54, 54, 54, 54, 54, 54, 53,
    53, 54, 54, 54, 54, 54, 54, 53,
    53, 54, 54, 54, 54, 54, 54, 53,
    52, 53, 53, 53, 53, 53, 53, 52
};

// Attack tables
Bitboard BISHOP_MASKS[64];
Bitboard ROOK_MASKS[64];
Bitboard BISHOP_ATTACKS[64][512];
Bitboard ROOK_ATTACKS[64][4096];

// Magic structures
Magic bishop_magics[64];
Magic rook_magics[64];

// =============================================================================
// SLIDING PIECE ATTACK GENERATION (for initialization)
// =============================================================================

static Bitboard sliding_attacks(Square sq, Bitboard occupied, const int deltas[4]) {
    Bitboard attacks = 0;
    for (int i = 0; i < 4; ++i) {
        int delta = deltas[i];
        int s = sq + delta;
        while (s >= 0 && s < 64 && 
               std::abs(file_of(s) - file_of(s - delta)) <= 1) {
            attacks |= square_bb(s);
            if (occupied & square_bb(s)) break;
            s += delta;
        }
    }
    return attacks;
}

static Bitboard bishop_attacks_slow(Square sq, Bitboard occupied) {
    static const int deltas[4] = {9, 7, -9, -7};
    return sliding_attacks(sq, occupied, deltas);
}

static Bitboard rook_attacks_slow(Square sq, Bitboard occupied) {
    static const int deltas[4] = {8, 1, -8, -1};
    return sliding_attacks(sq, occupied, deltas);
}

static Bitboard init_mask(Square sq, bool is_rook) {
    Bitboard mask = is_rook ? rook_attacks_slow(sq, 0) : bishop_attacks_slow(sq, 0);
    // Remove edges (they don't affect attacks)
    if (file_of(sq) != 0) mask &= ~FILE_A;
    if (file_of(sq) != 7) mask &= ~FILE_H;
    if (rank_of(sq) != 0) mask &= ~RANK_1;
    if (rank_of(sq) != 7) mask &= ~RANK_8;
    return mask;
}

// =============================================================================
// MAGIC BITBOARD INITIALIZATION
// =============================================================================

void init_magics() {
    // Initialize knight/king/pawn attack tables
    extern void init_move_tables();
    init_move_tables();
    
    // Initialize Zobrist keys
    Zobrist::init();
    
    // Initialize evaluation PST
    extern void init_pst();
    init_pst();
    
    // Initialize LMR table
    extern void init_lmr_table();
    init_lmr_table();
    
    // Initialize bishop magics
    for (int sq = 0; sq < 64; ++sq) {
        BISHOP_MASKS[sq] = init_mask(sq, false);
        
        bishop_magics[sq].mask = BISHOP_MASKS[sq];
        bishop_magics[sq].magic = BISHOP_MAGICS[sq];
        bishop_magics[sq].shift = BISHOP_SHIFTS[sq];
        bishop_magics[sq].attacks = BISHOP_ATTACKS[sq];
        
        // Fill attack table for all occupancy patterns
        Bitboard mask = BISHOP_MASKS[sq];
        int bits = popcount(mask);
        
        for (int i = 0; i < (1 << bits); ++i) {
            // Generate occupancy from index
            Bitboard occ = 0;
            Bitboard temp = mask;
            for (int j = 0; j < bits; ++j) {
                int bit = pop_lsb(temp);
                if (i & (1 << j)) {
                    occ |= square_bb(bit);
                }
            }
            
            int idx = static_cast<int>((occ * BISHOP_MAGICS[sq]) >> BISHOP_SHIFTS[sq]);
            BISHOP_ATTACKS[sq][idx] = bishop_attacks_slow(sq, occ);
        }
    }
    
    // Initialize rook magics
    for (int sq = 0; sq < 64; ++sq) {
        ROOK_MASKS[sq] = init_mask(sq, true);
        
        rook_magics[sq].mask = ROOK_MASKS[sq];
        rook_magics[sq].magic = ROOK_MAGICS[sq];
        rook_magics[sq].shift = ROOK_SHIFTS[sq];
        rook_magics[sq].attacks = ROOK_ATTACKS[sq];
        
        Bitboard mask = ROOK_MASKS[sq];
        int bits = popcount(mask);
        
        for (int i = 0; i < (1 << bits); ++i) {
            Bitboard occ = 0;
            Bitboard temp = mask;
            for (int j = 0; j < bits; ++j) {
                int bit = pop_lsb(temp);
                if (i & (1 << j)) {
                    occ |= square_bb(bit);
                }
            }
            
            int idx = static_cast<int>((occ * ROOK_MAGICS[sq]) >> ROOK_SHIFTS[sq]);
            ROOK_ATTACKS[sq][idx] = rook_attacks_slow(sq, occ);
        }
    }
}

} // namespace v6
