#pragma once

#include "board.hpp"
#include <vector>

namespace v6 {

// =============================================================================
// MAGIC BITBOARDS FOR SLIDING PIECES
// =============================================================================

struct Magic {
    Bitboard mask;
    Bitboard magic;
    Bitboard* attacks;
    int shift;
    
    Bitboard operator()(Bitboard occupied) const {
        return attacks[((occupied & mask) * magic) >> shift];
    }
};

extern Magic bishop_magics[64];
extern Magic rook_magics[64];

// Pre-computed attack tables
extern Bitboard knight_attacks[64];
extern Bitboard king_attacks[64];
extern Bitboard pawn_attacks[2][64];  // [color][square]

// Initialize magic bitboards
void init_magics();

// =============================================================================
// ATTACK GENERATION
// =============================================================================

inline Bitboard bishop_attacks(Square sq, Bitboard occupied) {
    return bishop_magics[sq](occupied);
}

inline Bitboard rook_attacks(Square sq, Bitboard occupied) {
    return rook_magics[sq](occupied);
}

inline Bitboard queen_attacks(Square sq, Bitboard occupied) {
    return bishop_attacks(sq, occupied) | rook_attacks(sq, occupied);
}

// Pre-computed line between two squares (for pin detection)
extern Bitboard between_bb[64][64];
extern Bitboard line_bb[64][64];

// =============================================================================
// MOVE GENERATION
// =============================================================================

// Move list with small buffer optimization
class MoveList {
public:
    static constexpr int MAX_MOVES = 256;
    
    Move moves[MAX_MOVES];
    int count = 0;
    
    void add(Move m) { moves[count++] = m; }
    void clear() { count = 0; }
    
    Move* begin() { return moves; }
    Move* end() { return moves + count; }
    const Move* begin() const { return moves; }
    const Move* end() const { return moves + count; }
    int size() const { return count; }
    Move operator[](int i) const { return moves[i]; }
};

// Generate all pseudo-legal moves
void generate_all_moves(const Board& board, MoveList& moves);

// Generate only captures and promotions (for quiescence)
void generate_captures(const Board& board, MoveList& moves);

// Generate legal moves only
void generate_legal_moves(const Board& board, MoveList& moves);

// Check if a pseudo-legal move is legal
bool is_legal(const Board& board, Move m);

// =============================================================================
// MOVE ORDERING
// =============================================================================

struct MoveOrder {
    Move move;
    int score;
    
    bool operator<(const MoveOrder& other) const {
        return score > other.score;  // Higher score first
    }
};

// Score moves for ordering (stores scores in the output array)
void score_moves(const Board& board, MoveList& moves, Move tt_move, 
                 const std::array<Move, 64>& killers,
                 const std::array<std::array<int, 64>, 12>& history,
                 int* scores);

} // namespace v6
