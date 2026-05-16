#pragma once

#include "types.hpp"
#include <string>
#include <array>
#include <sstream>

namespace v7 {

// =============================================================================
// BOARD REPRESENTATION
// =============================================================================
//
// NOTE (checker issue #3): Board stays perft-clean — NO history stack is
// declared here. Plan 03 places the per-game position history on the Engine
// class and pushes/pops at the search-wrapper layer, NOT here inside
// make_move/unmake_move.

struct Board {
    // Bitboards for each piece type and color
    std::array<Bitboard, 6> pieces;  // [piece_type] - all pieces of this type
    std::array<Bitboard, 2> colors;  // [color] - all pieces of this color

    // Piece map for quick lookup: what piece is on each square
    std::array<Piece, 64> piece_on;
    std::array<Color, 64> color_on;

    // Game state
    Color side_to_move;
    int castling_rights;  // KQkq = bits 0,1,2,3
    Square ep_square;
    int halfmove_clock;
    int fullmove_number;

    // Zobrist hash
    uint64_t hash;

    // Castling rights masks
    static constexpr int WHITE_OO  = 1;
    static constexpr int WHITE_OOO = 2;
    static constexpr int BLACK_OO  = 4;
    static constexpr int BLACK_OOO = 8;

    Board() { reset(); }

    void reset();
    void from_fen(const std::string& fen);
    std::string to_fen() const;

    // Piece access
    Bitboard occupied() const { return colors[WHITE] | colors[BLACK]; }
    Bitboard empty() const { return ~occupied(); }
    Bitboard pieces_of(Color c, Piece p) const { return pieces[p] & colors[c]; }

    Piece piece_at(Square sq) const { return piece_on[sq]; }
    Color color_at(Square sq) const { return color_on[sq]; }

    // King position
    Square king_square(Color c) const { return lsb(pieces_of(c, KING)); }

    // Move making
    void make_move(Move m);
    void unmake_move(Move m, Piece captured, int prev_castling, Square prev_ep, int prev_halfmove);

    // Attack detection
    bool is_attacked(Square sq, Color by) const;
    bool is_in_check() const { return is_attacked(king_square(side_to_move), Color(1 - side_to_move)); }
    bool gives_check(Move m) const;

    // Utility
    void put_piece(Square sq, Color c, Piece p);
    void remove_piece(Square sq);
    void move_piece(Square from, Square to);

    // Debug
    void print() const;
};

// =============================================================================
// ZOBRIST HASHING
// =============================================================================
//
// Declared inline here in V6; V7 keeps the same surface inside namespace v7
// for verbatim-fork parity. The standalone zobrist.hpp shim header includes
// this file so plan 03's search code can `#include "zobrist.hpp"` to reach
// these symbols (V6 kept zobrist inlined in board.hpp; V7 hoists the
// re-export only — definitions live in board.cpp identically to V6).

struct Zobrist {
    static std::array<std::array<std::array<uint64_t, 64>, 6>, 2> piece_keys;
    static std::array<uint64_t, 16> castling_keys;
    static std::array<uint64_t, 65> ep_keys;  // 64 squares + NO_SQUARE
    static uint64_t side_key;

    static void init();
};

} // namespace v7
