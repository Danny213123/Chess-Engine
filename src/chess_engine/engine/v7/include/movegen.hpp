#pragma once

#include "board.hpp"
#include <vector>

namespace v7 {

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

// Score moves for ordering (stores scores in the output array).
// Plan 03-01 D-03: killers and history are now persistent Engine-owned state
// (Bug #2 fix). ply_killers points to killers[ply][2] in SearchStack;
// history is the 3-D Engine::history_[2][64][64] pointer (non-owning).
// counter_move_ptr passed for future Plan 03-02 counter-move scoring
// (currently received but not yet scored — see TODO comment in movegen.cpp).
void score_moves(const Board& board, MoveList& moves, Move tt_move,
                 const Move* ply_killers,           // killers[ply][0..1]
                 const int (*history)[64][64],      // history[2][64][64] — side/from/to
                 const Move* counter_move_ptr,      // TODO Plan 03-02: counter-move score
                 int* scores);

} // namespace v7
