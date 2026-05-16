#pragma once

#include <cstdint>
#include <string>
#include <array>
#include <vector>
#include <cassert>

namespace v7 {

// =============================================================================
// BASIC TYPES
// =============================================================================

using Bitboard = uint64_t;
using Square = int;
using Piece = int;
using Color = int;

// Colors
constexpr Color WHITE = 0;
constexpr Color BLACK = 1;
constexpr Color NO_COLOR = 2;

// Pieces
constexpr Piece PAWN = 0;
constexpr Piece KNIGHT = 1;
constexpr Piece BISHOP = 2;
constexpr Piece ROOK = 3;
constexpr Piece QUEEN = 4;
constexpr Piece KING = 5;
constexpr Piece NO_PIECE = 6;

// Squares
constexpr Square A1 = 0, B1 = 1, C1 = 2, D1 = 3, E1 = 4, F1 = 5, G1 = 6, H1 = 7;
constexpr Square A2 = 8, B2 = 9, C2 = 10, D2 = 11, E2 = 12, F2 = 13, G2 = 14, H2 = 15;
constexpr Square A3 = 16, B3 = 17, C3 = 18, D3 = 19, E3 = 20, F3 = 21, G3 = 22, H3 = 23;
constexpr Square A4 = 24, B4 = 25, C4 = 26, D4 = 27, E4 = 28, F4 = 29, G4 = 30, H4 = 31;
constexpr Square A5 = 32, B5 = 33, C5 = 34, D5 = 35, E5 = 36, F5 = 37, G5 = 38, H5 = 39;
constexpr Square A6 = 40, B6 = 41, C6 = 42, D6 = 43, E6 = 44, F6 = 45, G6 = 46, H6 = 47;
constexpr Square A7 = 48, B7 = 49, C7 = 50, D7 = 51, E7 = 52, F7 = 53, G7 = 54, H7 = 55;
constexpr Square A8 = 56, B8 = 57, C8 = 58, D8 = 59, E8 = 60, F8 = 61, G8 = 62, H8 = 63;
constexpr Square NO_SQUARE = 64;

// =============================================================================
// MOVE ENCODING
// =============================================================================

// Move encoding: 16 bits
// bits 0-5: from square
// bits 6-11: to square
// bits 12-13: promotion piece (0=N, 1=B, 2=R, 3=Q)
// bits 14-15: move type (0=normal, 1=promotion, 2=en passant, 3=castle)

using Move = uint16_t;

constexpr Move MOVE_NONE = 0;

// Move types
constexpr int NORMAL = 0;
constexpr int PROMOTION = 1;
constexpr int EN_PASSANT = 2;
constexpr int CASTLING = 3;

inline constexpr Move make_move(Square from, Square to) {
    return static_cast<Move>(from | (to << 6));
}

inline constexpr Move make_promotion(Square from, Square to, Piece promo) {
    return static_cast<Move>(from | (to << 6) | (promo << 12) | (PROMOTION << 14));
}

inline constexpr Move make_en_passant(Square from, Square to) {
    return static_cast<Move>(from | (to << 6) | (EN_PASSANT << 14));
}

inline constexpr Move make_castling(Square from, Square to) {
    return static_cast<Move>(from | (to << 6) | (CASTLING << 14));
}

inline constexpr Square move_from(Move m) { return m & 0x3F; }
inline constexpr Square move_to(Move m) { return (m >> 6) & 0x3F; }
inline constexpr int move_type(Move m) { return (m >> 14) & 0x3; }
inline constexpr Piece promo_piece(Move m) { return ((m >> 12) & 0x3) + KNIGHT; }

// =============================================================================
// BITBOARD OPERATIONS
// =============================================================================

inline int popcount(Bitboard b) {
#if defined(_MSC_VER)
    return static_cast<int>(__popcnt64(b));
#else
    return __builtin_popcountll(b);
#endif
}

inline int lsb(Bitboard b) {
    assert(b != 0);
#if defined(_MSC_VER)
    unsigned long idx;
    _BitScanForward64(&idx, b);
    return static_cast<int>(idx);
#else
    return __builtin_ctzll(b);
#endif
}

inline int pop_lsb(Bitboard& b) {
    int sq = lsb(b);
    b &= b - 1;
    return sq;
}

inline Bitboard square_bb(Square sq) {
    return 1ULL << sq;
}

// File and rank masks
constexpr Bitboard FILE_A = 0x0101010101010101ULL;
constexpr Bitboard FILE_B = FILE_A << 1;
constexpr Bitboard FILE_C = FILE_A << 2;
constexpr Bitboard FILE_D = FILE_A << 3;
constexpr Bitboard FILE_E = FILE_A << 4;
constexpr Bitboard FILE_F = FILE_A << 5;
constexpr Bitboard FILE_G = FILE_A << 6;
constexpr Bitboard FILE_H = FILE_A << 7;

constexpr Bitboard RANK_1 = 0x00000000000000FFULL;
constexpr Bitboard RANK_2 = RANK_1 << 8;
constexpr Bitboard RANK_3 = RANK_1 << 16;
constexpr Bitboard RANK_4 = RANK_1 << 24;
constexpr Bitboard RANK_5 = RANK_1 << 32;
constexpr Bitboard RANK_6 = RANK_1 << 40;
constexpr Bitboard RANK_7 = RANK_1 << 48;
constexpr Bitboard RANK_8 = RANK_1 << 56;

inline int file_of(Square sq) { return sq & 7; }
inline int rank_of(Square sq) { return sq >> 3; }

inline Bitboard file_bb(Square sq) { return FILE_A << file_of(sq); }
inline Bitboard rank_bb(Square sq) { return RANK_1 << (8 * rank_of(sq)); }

// Shift operations
inline Bitboard shift_north(Bitboard b) { return b << 8; }
inline Bitboard shift_south(Bitboard b) { return b >> 8; }
inline Bitboard shift_east(Bitboard b) { return (b << 1) & ~FILE_A; }
inline Bitboard shift_west(Bitboard b) { return (b >> 1) & ~FILE_H; }
inline Bitboard shift_north_east(Bitboard b) { return (b << 9) & ~FILE_A; }
inline Bitboard shift_north_west(Bitboard b) { return (b << 7) & ~FILE_H; }
inline Bitboard shift_south_east(Bitboard b) { return (b >> 7) & ~FILE_A; }
inline Bitboard shift_south_west(Bitboard b) { return (b >> 9) & ~FILE_H; }

// =============================================================================
// SCORE CONSTANTS
// =============================================================================

constexpr int INFINITY_SCORE = 30000;
constexpr int MATE_SCORE = 29000;
constexpr int DRAW_SCORE = 0;

// Square name conversion
inline std::string square_to_string(Square sq) {
    return std::string(1, 'a' + file_of(sq)) + std::string(1, '1' + rank_of(sq));
}

inline Square string_to_square(const std::string& s) {
    if (s.length() < 2) return NO_SQUARE;
    int file = s[0] - 'a';
    int rank = s[1] - '1';
    if (file < 0 || file > 7 || rank < 0 || rank > 7) return NO_SQUARE;
    return rank * 8 + file;
}

// Move to string
inline std::string move_to_string(Move m) {
    if (m == MOVE_NONE) return "0000";
    std::string s = square_to_string(move_from(m)) + square_to_string(move_to(m));
    if (move_type(m) == PROMOTION) {
        constexpr char promos[] = "nbrq";
        s += promos[promo_piece(m) - KNIGHT];
    }
    return s;
}

} // namespace v7
