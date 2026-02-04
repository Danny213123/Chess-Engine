#include "board.hpp"
#include <random>
#include <iostream>

namespace v6 {

// =============================================================================
// ZOBRIST INITIALIZATION
// =============================================================================

std::array<std::array<std::array<uint64_t, 64>, 6>, 2> Zobrist::piece_keys;
std::array<uint64_t, 16> Zobrist::castling_keys;
std::array<uint64_t, 65> Zobrist::ep_keys;
uint64_t Zobrist::side_key;

void Zobrist::init() {
    std::mt19937_64 rng(0x1234567890ABCDEFULL);
    
    for (int c = 0; c < 2; ++c) {
        for (int p = 0; p < 6; ++p) {
            for (int sq = 0; sq < 64; ++sq) {
                piece_keys[c][p][sq] = rng();
            }
        }
    }
    
    for (int i = 0; i < 16; ++i) {
        castling_keys[i] = rng();
    }
    
    for (int i = 0; i < 65; ++i) {
        ep_keys[i] = rng();
    }
    
    side_key = rng();
}

// =============================================================================
// BOARD IMPLEMENTATION
// =============================================================================

void Board::reset() {
    pieces.fill(0);
    colors.fill(0);
    piece_on.fill(NO_PIECE);
    color_on.fill(NO_COLOR);
    side_to_move = WHITE;
    castling_rights = WHITE_OO | WHITE_OOO | BLACK_OO | BLACK_OOO;
    ep_square = NO_SQUARE;
    halfmove_clock = 0;
    fullmove_number = 1;
    hash = 0;
}

void Board::put_piece(Square sq, Color c, Piece p) {
    Bitboard bb = square_bb(sq);
    pieces[p] |= bb;
    colors[c] |= bb;
    piece_on[sq] = p;
    color_on[sq] = c;
    hash ^= Zobrist::piece_keys[c][p][sq];
}

void Board::remove_piece(Square sq) {
    Piece p = piece_on[sq];
    Color c = color_on[sq];
    if (p == NO_PIECE) return;
    
    Bitboard bb = square_bb(sq);
    pieces[p] &= ~bb;
    colors[c] &= ~bb;
    piece_on[sq] = NO_PIECE;
    color_on[sq] = NO_COLOR;
    hash ^= Zobrist::piece_keys[c][p][sq];
}

void Board::move_piece(Square from, Square to) {
    Piece p = piece_on[from];
    Color c = color_on[from];
    
    Bitboard from_bb = square_bb(from);
    Bitboard to_bb = square_bb(to);
    Bitboard move_bb = from_bb | to_bb;
    
    pieces[p] ^= move_bb;
    colors[c] ^= move_bb;
    
    piece_on[to] = p;
    color_on[to] = c;
    piece_on[from] = NO_PIECE;
    color_on[from] = NO_COLOR;
    
    hash ^= Zobrist::piece_keys[c][p][from];
    hash ^= Zobrist::piece_keys[c][p][to];
}

void Board::from_fen(const std::string& fen) {
    reset();
    
    std::istringstream ss(fen);
    std::string board_str, side_str, castling_str, ep_str;
    int halfmove = 0, fullmove = 1;
    
    ss >> board_str >> side_str >> castling_str >> ep_str >> halfmove >> fullmove;
    
    // Parse board
    int sq = 56;  // Start at a8
    for (char c : board_str) {
        if (c == '/') {
            sq -= 16;  // Move to next rank
        } else if (c >= '1' && c <= '8') {
            sq += (c - '0');
        } else {
            Color col = (c >= 'A' && c <= 'Z') ? WHITE : BLACK;
            char pc = (col == WHITE) ? c : (c - 32);
            Piece p = NO_PIECE;
            switch (pc) {
                case 'P': p = PAWN; break;
                case 'N': p = KNIGHT; break;
                case 'B': p = BISHOP; break;
                case 'R': p = ROOK; break;
                case 'Q': p = QUEEN; break;
                case 'K': p = KING; break;
            }
            if (p != NO_PIECE) {
                put_piece(sq, col, p);
            }
            sq++;
        }
    }
    
    // Side to move
    side_to_move = (side_str == "w") ? WHITE : BLACK;
    if (side_to_move == BLACK) {
        hash ^= Zobrist::side_key;
    }
    
    // Castling
    castling_rights = 0;
    hash ^= Zobrist::castling_keys[castling_rights];
    for (char c : castling_str) {
        switch (c) {
            case 'K': castling_rights |= WHITE_OO; break;
            case 'Q': castling_rights |= WHITE_OOO; break;
            case 'k': castling_rights |= BLACK_OO; break;
            case 'q': castling_rights |= BLACK_OOO; break;
        }
    }
    hash ^= Zobrist::castling_keys[castling_rights];
    
    // En passant
    if (ep_str != "-" && ep_str.length() >= 2) {
        ep_square = string_to_square(ep_str);
        hash ^= Zobrist::ep_keys[ep_square];
    } else {
        ep_square = NO_SQUARE;
    }
    
    halfmove_clock = halfmove;
    fullmove_number = fullmove;
}

std::string Board::to_fen() const {
    std::string fen;
    
    // Board
    for (int rank = 7; rank >= 0; --rank) {
        int empty = 0;
        for (int file = 0; file < 8; ++file) {
            Square sq = rank * 8 + file;
            Piece p = piece_on[sq];
            if (p == NO_PIECE) {
                empty++;
            } else {
                if (empty > 0) {
                    fen += ('0' + empty);
                    empty = 0;
                }
                char pc = "pnbrqk"[p];
                if (color_on[sq] == WHITE) pc -= 32;
                fen += pc;
            }
        }
        if (empty > 0) fen += ('0' + empty);
        if (rank > 0) fen += '/';
    }
    
    // Side to move
    fen += (side_to_move == WHITE) ? " w " : " b ";
    
    // Castling
    std::string castling;
    if (castling_rights & WHITE_OO) castling += 'K';
    if (castling_rights & WHITE_OOO) castling += 'Q';
    if (castling_rights & BLACK_OO) castling += 'k';
    if (castling_rights & BLACK_OOO) castling += 'q';
    fen += castling.empty() ? "-" : castling;
    
    // En passant
    fen += " ";
    fen += (ep_square == NO_SQUARE) ? "-" : square_to_string(ep_square);
    
    // Halfmove and fullmove
    fen += " " + std::to_string(halfmove_clock);
    fen += " " + std::to_string(fullmove_number);
    
    return fen;
}

void Board::print() const {
    std::cout << "\n  +---+---+---+---+---+---+---+---+\n";
    for (int rank = 7; rank >= 0; --rank) {
        std::cout << (rank + 1) << " |";
        for (int file = 0; file < 8; ++file) {
            Square sq = rank * 8 + file;
            Piece p = piece_on[sq];
            if (p == NO_PIECE) {
                std::cout << "   |";
            } else {
                char pc = "PNBRQK"[p];
                if (color_on[sq] == BLACK) pc += 32;
                std::cout << " " << pc << " |";
            }
        }
        std::cout << "\n  +---+---+---+---+---+---+---+---+\n";
    }
    std::cout << "    a   b   c   d   e   f   g   h\n\n";
    std::cout << "FEN: " << to_fen() << "\n";
}

} // namespace v6
