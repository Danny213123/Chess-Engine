#include "movegen.hpp"
#include "magic.hpp"
// NOTE: V6 includes "eval.hpp" here for PIECE_VALUES used by score_moves.
// Plan 04 lands V7's eval.hpp; until then we inline the V6 PIECE_VALUES
// table locally so movegen.cpp compiles without coupling to eval.hpp.
// When Plan 04 adds eval.hpp, this local definition will need to be moved
// or guarded; Plan 04's task includes a one-line cleanup of this anchor.
// Source values mirror V6 eval.hpp PIECE_VALUES[6] exactly.
#include <algorithm>

namespace v7 {

// Local copy of V6 eval.hpp PIECE_VALUES (verbatim) — see note above.
static constexpr int PIECE_VALUES[6] = {100, 320, 330, 500, 900, 20000};

// Attack tables
Bitboard knight_attacks[64];
Bitboard king_attacks[64];
Bitboard pawn_attacks[2][64];
Bitboard between_bb[64][64];
Bitboard line_bb[64][64];

// =============================================================================
// INITIALIZE ATTACK TABLES
// =============================================================================

static void init_knight_attacks() {
    for (int sq = 0; sq < 64; ++sq) {
        Bitboard b = square_bb(sq);
        knight_attacks[sq] =
            ((b << 17) & ~FILE_A) |
            ((b << 15) & ~FILE_H) |
            ((b << 10) & ~(FILE_A | FILE_B)) |
            ((b << 6) & ~(FILE_G | FILE_H)) |
            ((b >> 17) & ~FILE_H) |
            ((b >> 15) & ~FILE_A) |
            ((b >> 10) & ~(FILE_G | FILE_H)) |
            ((b >> 6) & ~(FILE_A | FILE_B));
    }
}

static void init_king_attacks() {
    for (int sq = 0; sq < 64; ++sq) {
        Bitboard b = square_bb(sq);
        king_attacks[sq] =
            shift_north(b) | shift_south(b) |
            shift_east(b) | shift_west(b) |
            shift_north_east(b) | shift_north_west(b) |
            shift_south_east(b) | shift_south_west(b);
    }
}

static void init_pawn_attacks() {
    for (int sq = 0; sq < 64; ++sq) {
        Bitboard b = square_bb(sq);
        pawn_attacks[WHITE][sq] = shift_north_east(b) | shift_north_west(b);
        pawn_attacks[BLACK][sq] = shift_south_east(b) | shift_south_west(b);
    }
}

// =============================================================================
// MOVE GENERATION
// =============================================================================

void generate_all_moves(const Board& board, MoveList& moves) {
    Color us = board.side_to_move;
    Color them = Color(1 - us);
    Bitboard our_pieces = board.colors[us];
    Bitboard their_pieces = board.colors[them];
    Bitboard occupied = board.occupied();
    Bitboard empty = board.empty();

    // Pawns
    Bitboard pawns = board.pieces_of(us, PAWN);
    if (us == WHITE) {
        // Single pushes
        Bitboard single = shift_north(pawns) & empty;
        Bitboard promo = single & RANK_8;
        single &= ~RANK_8;

        while (single) {
            int to = pop_lsb(single);
            moves.add(make_move(to - 8, to));
        }

        while (promo) {
            int to = pop_lsb(promo);
            moves.add(make_promotion(to - 8, to, QUEEN - KNIGHT));
            moves.add(make_promotion(to - 8, to, ROOK - KNIGHT));
            moves.add(make_promotion(to - 8, to, BISHOP - KNIGHT));
            moves.add(make_promotion(to - 8, to, KNIGHT - KNIGHT));
        }

        // Double pushes
        Bitboard double_push = shift_north(shift_north(pawns) & empty & RANK_3) & empty;
        while (double_push) {
            int to = pop_lsb(double_push);
            moves.add(make_move(to - 16, to));
        }

        // Captures
        Bitboard cap_left = shift_north_west(pawns) & their_pieces;
        Bitboard cap_right = shift_north_east(pawns) & their_pieces;

        Bitboard cap_left_promo = cap_left & RANK_8;
        Bitboard cap_right_promo = cap_right & RANK_8;
        cap_left &= ~RANK_8;
        cap_right &= ~RANK_8;

        while (cap_left) {
            int to = pop_lsb(cap_left);
            moves.add(make_move(to - 7, to));
        }
        while (cap_right) {
            int to = pop_lsb(cap_right);
            moves.add(make_move(to - 9, to));
        }
        while (cap_left_promo) {
            int to = pop_lsb(cap_left_promo);
            for (int p = 0; p < 4; ++p) moves.add(make_promotion(to - 7, to, p));
        }
        while (cap_right_promo) {
            int to = pop_lsb(cap_right_promo);
            for (int p = 0; p < 4; ++p) moves.add(make_promotion(to - 9, to, p));
        }

        // En passant
        if (board.ep_square != NO_SQUARE) {
            Bitboard ep_attackers = pawn_attacks[BLACK][board.ep_square] & pawns;
            while (ep_attackers) {
                int from = pop_lsb(ep_attackers);
                moves.add(make_en_passant(from, board.ep_square));
            }
        }
    } else {
        // Black pawns (mirror of white)
        Bitboard single = shift_south(pawns) & empty;
        Bitboard promo = single & RANK_1;
        single &= ~RANK_1;

        while (single) {
            int to = pop_lsb(single);
            moves.add(make_move(to + 8, to));
        }
        while (promo) {
            int to = pop_lsb(promo);
            for (int p = 0; p < 4; ++p) moves.add(make_promotion(to + 8, to, p));
        }

        Bitboard double_push = shift_south(shift_south(pawns) & empty & RANK_6) & empty;
        while (double_push) {
            int to = pop_lsb(double_push);
            moves.add(make_move(to + 16, to));
        }

        Bitboard cap_left = shift_south_west(pawns) & their_pieces;
        Bitboard cap_right = shift_south_east(pawns) & their_pieces;

        Bitboard cap_left_promo = cap_left & RANK_1;
        Bitboard cap_right_promo = cap_right & RANK_1;
        cap_left &= ~RANK_1;
        cap_right &= ~RANK_1;

        while (cap_left) {
            int to = pop_lsb(cap_left);
            moves.add(make_move(to + 9, to));
        }
        while (cap_right) {
            int to = pop_lsb(cap_right);
            moves.add(make_move(to + 7, to));
        }
        while (cap_left_promo) {
            int to = pop_lsb(cap_left_promo);
            for (int p = 0; p < 4; ++p) moves.add(make_promotion(to + 9, to, p));
        }
        while (cap_right_promo) {
            int to = pop_lsb(cap_right_promo);
            for (int p = 0; p < 4; ++p) moves.add(make_promotion(to + 7, to, p));
        }

        if (board.ep_square != NO_SQUARE) {
            Bitboard ep_attackers = pawn_attacks[WHITE][board.ep_square] & pawns;
            while (ep_attackers) {
                int from = pop_lsb(ep_attackers);
                moves.add(make_en_passant(from, board.ep_square));
            }
        }
    }

    // Knights
    Bitboard knights = board.pieces_of(us, KNIGHT);
    while (knights) {
        int from = pop_lsb(knights);
        Bitboard attacks = knight_attacks[from] & ~our_pieces;
        while (attacks) {
            int to = pop_lsb(attacks);
            moves.add(make_move(from, to));
        }
    }

    // Bishops
    Bitboard bishops = board.pieces_of(us, BISHOP);
    while (bishops) {
        int from = pop_lsb(bishops);
        Bitboard attacks = bishop_attacks(from, occupied) & ~our_pieces;
        while (attacks) {
            int to = pop_lsb(attacks);
            moves.add(make_move(from, to));
        }
    }

    // Rooks
    Bitboard rooks = board.pieces_of(us, ROOK);
    while (rooks) {
        int from = pop_lsb(rooks);
        Bitboard attacks = rook_attacks(from, occupied) & ~our_pieces;
        while (attacks) {
            int to = pop_lsb(attacks);
            moves.add(make_move(from, to));
        }
    }

    // Queens
    Bitboard queens = board.pieces_of(us, QUEEN);
    while (queens) {
        int from = pop_lsb(queens);
        Bitboard attacks = queen_attacks(from, occupied) & ~our_pieces;
        while (attacks) {
            int to = pop_lsb(attacks);
            moves.add(make_move(from, to));
        }
    }

    // King
    int king_sq = board.king_square(us);
    Bitboard king_moves = king_attacks[king_sq] & ~our_pieces;
    while (king_moves) {
        int to = pop_lsb(king_moves);
        moves.add(make_move(king_sq, to));
    }

    // Castling
    if (us == WHITE) {
        if ((board.castling_rights & Board::WHITE_OO) &&
            !(occupied & 0x60ULL) &&
            !board.is_attacked(E1, BLACK) &&
            !board.is_attacked(F1, BLACK) &&
            !board.is_attacked(G1, BLACK)) {
            moves.add(make_castling(E1, G1));
        }
        if ((board.castling_rights & Board::WHITE_OOO) &&
            !(occupied & 0x0EULL) &&
            !board.is_attacked(E1, BLACK) &&
            !board.is_attacked(D1, BLACK) &&
            !board.is_attacked(C1, BLACK)) {
            moves.add(make_castling(E1, C1));
        }
    } else {
        if ((board.castling_rights & Board::BLACK_OO) &&
            !(occupied & 0x6000000000000000ULL) &&
            !board.is_attacked(E8, WHITE) &&
            !board.is_attacked(F8, WHITE) &&
            !board.is_attacked(G8, WHITE)) {
            moves.add(make_castling(E8, G8));
        }
        if ((board.castling_rights & Board::BLACK_OOO) &&
            !(occupied & 0x0E00000000000000ULL) &&
            !board.is_attacked(E8, WHITE) &&
            !board.is_attacked(D8, WHITE) &&
            !board.is_attacked(C8, WHITE)) {
            moves.add(make_castling(E8, C8));
        }
    }
}

void generate_captures(const Board& board, MoveList& moves) {
    Color us = board.side_to_move;
    Color them = Color(1 - us);
    Bitboard their_pieces = board.colors[them];
    Bitboard occupied = board.occupied();

    // Similar to generate_all_moves but only captures
    Bitboard pawns = board.pieces_of(us, PAWN);
    if (us == WHITE) {
        Bitboard cap_left = shift_north_west(pawns) & their_pieces;
        Bitboard cap_right = shift_north_east(pawns) & their_pieces;

        while (cap_left) {
            int to = pop_lsb(cap_left);
            if (rank_of(to) == 7) {
                for (int p = 0; p < 4; ++p) moves.add(make_promotion(to - 7, to, p));
            } else {
                moves.add(make_move(to - 7, to));
            }
        }
        while (cap_right) {
            int to = pop_lsb(cap_right);
            if (rank_of(to) == 7) {
                for (int p = 0; p < 4; ++p) moves.add(make_promotion(to - 9, to, p));
            } else {
                moves.add(make_move(to - 9, to));
            }
        }
        if (board.ep_square != NO_SQUARE) {
            Bitboard ep_attackers = pawn_attacks[BLACK][board.ep_square] & pawns;
            while (ep_attackers) {
                int from = pop_lsb(ep_attackers);
                moves.add(make_en_passant(from, board.ep_square));
            }
        }
    } else {
        Bitboard cap_left = shift_south_west(pawns) & their_pieces;
        Bitboard cap_right = shift_south_east(pawns) & their_pieces;

        while (cap_left) {
            int to = pop_lsb(cap_left);
            if (rank_of(to) == 0) {
                for (int p = 0; p < 4; ++p) moves.add(make_promotion(to + 9, to, p));
            } else {
                moves.add(make_move(to + 9, to));
            }
        }
        while (cap_right) {
            int to = pop_lsb(cap_right);
            if (rank_of(to) == 0) {
                for (int p = 0; p < 4; ++p) moves.add(make_promotion(to + 7, to, p));
            } else {
                moves.add(make_move(to + 7, to));
            }
        }
        if (board.ep_square != NO_SQUARE) {
            Bitboard ep_attackers = pawn_attacks[WHITE][board.ep_square] & pawns;
            while (ep_attackers) {
                int from = pop_lsb(ep_attackers);
                moves.add(make_en_passant(from, board.ep_square));
            }
        }
    }

    // Piece captures
    Bitboard knights = board.pieces_of(us, KNIGHT);
    while (knights) {
        int from = pop_lsb(knights);
        Bitboard attacks = knight_attacks[from] & their_pieces;
        while (attacks) {
            moves.add(make_move(from, pop_lsb(attacks)));
        }
    }

    Bitboard bishops = board.pieces_of(us, BISHOP);
    while (bishops) {
        int from = pop_lsb(bishops);
        Bitboard attacks = bishop_attacks(from, occupied) & their_pieces;
        while (attacks) {
            moves.add(make_move(from, pop_lsb(attacks)));
        }
    }

    Bitboard rooks = board.pieces_of(us, ROOK);
    while (rooks) {
        int from = pop_lsb(rooks);
        Bitboard attacks = rook_attacks(from, occupied) & their_pieces;
        while (attacks) {
            moves.add(make_move(from, pop_lsb(attacks)));
        }
    }

    Bitboard queens = board.pieces_of(us, QUEEN);
    while (queens) {
        int from = pop_lsb(queens);
        Bitboard attacks = queen_attacks(from, occupied) & their_pieces;
        while (attacks) {
            moves.add(make_move(from, pop_lsb(attacks)));
        }
    }

    int king_sq = board.king_square(us);
    Bitboard king_caps = king_attacks[king_sq] & their_pieces;
    while (king_caps) {
        moves.add(make_move(king_sq, pop_lsb(king_caps)));
    }
}

void generate_legal_moves(const Board& board, MoveList& moves) {
    MoveList pseudo;
    generate_all_moves(board, pseudo);

    Board temp = board;
    for (int i = 0; i < pseudo.count; ++i) {
        Move m = pseudo[i];

        Piece captured = temp.piece_at(move_to(m));
        int prev_castling = temp.castling_rights;
        Square prev_ep = temp.ep_square;
        int prev_halfmove = temp.halfmove_clock;

        temp.make_move(m);

        // Check if own king is attacked
        Color us = Color(1 - temp.side_to_move);
        if (!temp.is_attacked(temp.king_square(us), temp.side_to_move)) {
            moves.add(m);
        }

        temp.unmake_move(m, captured, prev_castling, prev_ep, prev_halfmove);
    }
}

// Plan 03-01 D-03: signature updated to use persistent Engine-owned state.
// ply_killers: pointer to killers[ply][0..1] in SearchStack (Bug #2 fix).
// history: non-owning pointer to Engine::history_[2][64][64].
// counter_move_ptr: for Plan 03-02 counter-move scoring (received but not
//   yet consumed — TODO Plan 03-02 will add counter-move bonus here).
void score_moves(const Board& board, MoveList& moves, Move tt_move,
                 const Move* ply_killers,
                 const int (*history)[64][64],
                 const Move* counter_move_ptr,
                 int* scores) {
    Color stm = board.side_to_move;

    for (int i = 0; i < moves.count; ++i) {
        Move m = moves[i];
        int score = 0;

        if (m == tt_move) {
            score = 1000000;  // TT move first
        } else {
            Piece captured = board.piece_at(move_to(m));
            if (captured != NO_PIECE) {
                // MVV-LVA: prioritize high-value captures by low-value attackers
                Piece attacker = board.piece_at(move_from(m));
                score = 100000 + PIECE_VALUES[captured] * 10 - PIECE_VALUES[attacker];
            } else if (move_type(m) == PROMOTION) {
                score = 90000 + PIECE_VALUES[promo_piece(m)];
            } else if (move_type(m) == CASTLING) {
                score = 50000;  // Castling is usually good
            } else {
                // Quiet move — use killer heuristic + history score (D-03 Bug #2 fix).
                // Killer moves: quiet moves that caused a beta-cutoff at this ply.
                if (ply_killers != nullptr &&
                    (m == ply_killers[0] || m == ply_killers[1])) {
                    score = 80000;  // Below captures, above generic quiets
                } else {
                    // History heuristic: persistent across search() calls (D-03).
                    int from = move_from(m);
                    int to   = move_to(m);
                    int hist_score = (history != nullptr)
                        ? (*history)[stm][from][to]
                        : 0;

                    // TODO Plan 03-02: add counter-move bonus here when
                    // counter_move_ptr is wired in score_moves callsite.
                    // if (counter_move_ptr && m == *counter_move_ptr) hist_score += 10000;
                    (void)counter_move_ptr;  // suppress unused-parameter warning until 03-02

                    // Center control bonus for quiet moves (retained from prior impl)
                    int center_bonus = 0;
                    if ((to >= 27 && to <= 28) || (to >= 35 && to <= 36)) {
                        center_bonus = 20;  // d4, e4, d5, e5
                    } else if ((to >= 18 && to <= 21) || (to >= 26 && to <= 29) ||
                               (to >= 34 && to <= 37) || (to >= 42 && to <= 45)) {
                        center_bonus = 10;  // Extended center
                    }
                    score = hist_score + center_bonus;
                }
            }
        }

        scores[i] = score;
    }
}


// =============================================================================
// ATTACK DETECTION
// =============================================================================

bool Board::is_attacked(Square sq, Color by) const {
    Bitboard occupied = this->occupied();

    // Pawn attacks
    if (pawn_attacks[Color(1 - by)][sq] & pieces_of(by, PAWN)) return true;

    // Knight attacks
    if (knight_attacks[sq] & pieces_of(by, KNIGHT)) return true;

    // King attacks
    if (king_attacks[sq] & pieces_of(by, KING)) return true;

    // Sliding pieces
    if (bishop_attacks(sq, occupied) & (pieces_of(by, BISHOP) | pieces_of(by, QUEEN))) return true;
    if (rook_attacks(sq, occupied) & (pieces_of(by, ROOK) | pieces_of(by, QUEEN))) return true;

    return false;
}

bool Board::gives_check(Move m) const {
    Board temp = *this;
    Piece captured = temp.piece_at(move_to(m));
    int prev_castling = temp.castling_rights;
    Square prev_ep = temp.ep_square;
    int prev_halfmove = temp.halfmove_clock;

    temp.make_move(m);
    bool in_check = temp.is_in_check();
    temp.unmake_move(m, captured, prev_castling, prev_ep, prev_halfmove);

    return in_check;
}

// =============================================================================
// MAKE/UNMAKE MOVE
// =============================================================================
//
// NOTE (checker issue #3): Board::make_move and Board::unmake_move DO NOT
// touch any repetition stack. The Engine search wrapper (Plan 03) wraps
// these calls with rep_stack_.push() / pop() at the search layer. Board
// stays perft-clean.

void Board::make_move(Move m) {
    Square from = move_from(m);
    Square to = move_to(m);
    int type = move_type(m);
    Color us = side_to_move;
    Color them = Color(1 - us);
    Piece moved = piece_on[from];
    Piece captured = piece_on[to];

    // Update hash for castling
    hash ^= Zobrist::castling_keys[castling_rights];

    // Clear en passant
    if (ep_square != NO_SQUARE) {
        hash ^= Zobrist::ep_keys[ep_square];
        ep_square = NO_SQUARE;
    }

    // Handle special moves
    if (type == EN_PASSANT) {
        Square cap_sq = (us == WHITE) ? to - 8 : to + 8;
        remove_piece(cap_sq);
        move_piece(from, to);
    } else if (type == CASTLING) {
        move_piece(from, to);
        // Move rook
        if (to == G1) { move_piece(H1, F1); }
        else if (to == C1) { move_piece(A1, D1); }
        else if (to == G8) { move_piece(H8, F8); }
        else if (to == C8) { move_piece(A8, D8); }
    } else if (type == PROMOTION) {
        if (captured != NO_PIECE) remove_piece(to);
        remove_piece(from);
        put_piece(to, us, promo_piece(m));
    } else {
        if (captured != NO_PIECE) remove_piece(to);
        move_piece(from, to);
    }

    // Update castling rights
    if (moved == KING) {
        if (us == WHITE) {
            castling_rights &= ~(WHITE_OO | WHITE_OOO);
        } else {
            castling_rights &= ~(BLACK_OO | BLACK_OOO);
        }
    }
    if (from == A1 || to == A1) castling_rights &= ~WHITE_OOO;
    if (from == H1 || to == H1) castling_rights &= ~WHITE_OO;
    if (from == A8 || to == A8) castling_rights &= ~BLACK_OOO;
    if (from == H8 || to == H8) castling_rights &= ~BLACK_OO;

    // Set en passant square for double pawn push
    if (moved == PAWN && std::abs(to - from) == 16) {
        ep_square = (us == WHITE) ? from + 8 : from - 8;
        hash ^= Zobrist::ep_keys[ep_square];
    }

    // Update hash for new castling rights
    hash ^= Zobrist::castling_keys[castling_rights];

    // Flip side to move
    side_to_move = them;
    hash ^= Zobrist::side_key;

    // Update clocks
    if (moved == PAWN || captured != NO_PIECE) {
        halfmove_clock = 0;
    } else {
        halfmove_clock++;
    }
    if (us == BLACK) fullmove_number++;
}

void Board::unmake_move(Move m, Piece captured, int prev_castling, Square prev_ep, int prev_halfmove) {
    Square from = move_from(m);
    Square to = move_to(m);
    int type = move_type(m);
    Color them = side_to_move;
    Color us = Color(1 - them);

    // Restore state
    hash ^= Zobrist::castling_keys[castling_rights];
    castling_rights = prev_castling;
    hash ^= Zobrist::castling_keys[castling_rights];

    if (ep_square != NO_SQUARE) hash ^= Zobrist::ep_keys[ep_square];
    ep_square = prev_ep;
    if (ep_square != NO_SQUARE) hash ^= Zobrist::ep_keys[ep_square];

    halfmove_clock = prev_halfmove;

    // Unmake special moves
    if (type == EN_PASSANT) {
        move_piece(to, from);
        Square cap_sq = (us == WHITE) ? to - 8 : to + 8;
        put_piece(cap_sq, them, PAWN);
    } else if (type == CASTLING) {
        move_piece(to, from);
        if (to == G1) { move_piece(F1, H1); }
        else if (to == C1) { move_piece(D1, A1); }
        else if (to == G8) { move_piece(F8, H8); }
        else if (to == C8) { move_piece(D8, A8); }
    } else if (type == PROMOTION) {
        remove_piece(to);
        put_piece(from, us, PAWN);
        if (captured != NO_PIECE) put_piece(to, them, captured);
    } else {
        move_piece(to, from);
        if (captured != NO_PIECE) put_piece(to, them, captured);
    }

    side_to_move = us;
    hash ^= Zobrist::side_key;
    if (us == BLACK) fullmove_number--;
}

// Initialize all move generation tables
void init_move_tables() {
    init_knight_attacks();
    init_king_attacks();
    init_pawn_attacks();
}

} // namespace v7
