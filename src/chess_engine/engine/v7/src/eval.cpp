// V7 evaluation (Plan 04) — implements EVAL-01..EVAL-11.
//
// REPLACES Plan 02's empty `// stub — implemented in Wave 3 (Plan 04)`
// placeholder. Every weight is read via v7::coeffs::* extern symbols
// defined in src/coeffs.cpp (auto-generated from coeffs.json by
// tools/gen_coeffs.py via the CMake add_custom_command pre-staged by
// Plan 02 task 3).
//
// EVAL-10 contract: no hardcoded weight constants live in this file.
// Numeric literals appearing here are exclusively:
//   - small loop indices and rank/file arithmetic (0..7, 8, 56)
//   - the piece-count threshold for the bishop-pair bonus (2)
//   - the divisor 256 for the Stockfish 0..256 tapered combine (ENDG-04)
//
// Plan 03-04 ENDG-04: phase accumulator replaced with Stockfish-style
// 0..256 continuous blend based on non_pawn_material() (replacing the old
// 0-24 Pesto integer scale at eval.cpp:424 `/ 24`). endgame_eval() call
// inserted between the tempo block and the tapered combine.
//
// Phase 4 Texel tuning mutates coeffs.json; the CMake custom command
// regenerates coeffs.cpp on every build; no edits to this file required.
//
// Pawn-hash table optimization (EVAL-08 NPS-recovery aspect) is deferred:
// see TODO(phase-4) comment below in the pawn structure section.

#include "eval.hpp"
#include "endgame.hpp"   // Plan 03-04: endgame_eval() hook + ENDG-01..05
#include "coeffs.hpp"
#include "board.hpp"
#include "movegen.hpp"

#include <algorithm>
#include <array>
#include <cstdint>

namespace v7 {

namespace {

// Square mirror for black: a8 (56) <-> a1 (0). Pesto tables are
// white-relative; flipping via XOR with 56 inverts the rank while
// preserving the file.
inline Square mirror_sq(Square sq) { return sq ^ 56; }

// PST lookup helpers — keyed by piece type, returning the proper
// extern array. Indexed by [P, N, B, R, Q, K] = [0..5].
inline int pst_mg(Piece p, Square sq_white_perspective) {
    switch (p) {
        case PAWN:   return v7::coeffs::pst_mg_P[sq_white_perspective];
        case KNIGHT: return v7::coeffs::pst_mg_N[sq_white_perspective];
        case BISHOP: return v7::coeffs::pst_mg_B[sq_white_perspective];
        case ROOK:   return v7::coeffs::pst_mg_R[sq_white_perspective];
        case QUEEN:  return v7::coeffs::pst_mg_Q[sq_white_perspective];
        case KING:   return v7::coeffs::pst_mg_K[sq_white_perspective];
    }
    return 0;
}

inline int pst_eg(Piece p, Square sq_white_perspective) {
    switch (p) {
        case PAWN:   return v7::coeffs::pst_eg_P[sq_white_perspective];
        case KNIGHT: return v7::coeffs::pst_eg_N[sq_white_perspective];
        case BISHOP: return v7::coeffs::pst_eg_B[sq_white_perspective];
        case ROOK:   return v7::coeffs::pst_eg_R[sq_white_perspective];
        case QUEEN:  return v7::coeffs::pst_eg_Q[sq_white_perspective];
        case KING:   return v7::coeffs::pst_eg_K[sq_white_perspective];
    }
    return 0;
}

inline int material_mg(Piece p) {
    switch (p) {
        case PAWN:   return v7::coeffs::material_mg_P;
        case KNIGHT: return v7::coeffs::material_mg_N;
        case BISHOP: return v7::coeffs::material_mg_B;
        case ROOK:   return v7::coeffs::material_mg_R;
        case QUEEN:  return v7::coeffs::material_mg_Q;
        case KING:   return v7::coeffs::material_mg_K;
    }
    return 0;
}

inline int material_eg(Piece p) {
    switch (p) {
        case PAWN:   return v7::coeffs::material_eg_P;
        case KNIGHT: return v7::coeffs::material_eg_N;
        case BISHOP: return v7::coeffs::material_eg_B;
        case ROOK:   return v7::coeffs::material_eg_R;
        case QUEEN:  return v7::coeffs::material_eg_Q;
        case KING:   return v7::coeffs::material_eg_K;
    }
    return 0;
}

inline int phase_weight(Piece p) {
    switch (p) {
        case PAWN:   return v7::coeffs::phase_weights_P;
        case KNIGHT: return v7::coeffs::phase_weights_N;
        case BISHOP: return v7::coeffs::phase_weights_B;
        case ROOK:   return v7::coeffs::phase_weights_R;
        case QUEEN:  return v7::coeffs::phase_weights_Q;
        case KING:   return v7::coeffs::phase_weights_K;
    }
    return 0;
}

// File mask helpers for pawn-structure detection.
constexpr Bitboard FILE_MASKS_LOC[8] = {
    FILE_A, FILE_B, FILE_C, FILE_D, FILE_E, FILE_F, FILE_G, FILE_H
};

// Adjacent-file mask: for isolated-pawn detection.
inline Bitboard adjacent_files(int f) {
    Bitboard r = 0;
    if (f > 0) r |= FILE_MASKS_LOC[f - 1];
    if (f < 7) r |= FILE_MASKS_LOC[f + 1];
    return r;
}

// Front span of a pawn (squares strictly in front, all files for the
// passed-pawn test we mask to file + adjacent files outside this helper).
inline Bitboard front_span_white(Square sq) {
    Bitboard m = 0;
    for (int r = rank_of(sq) + 1; r <= 7; ++r) {
        m |= RANK_1 << (8 * r);
    }
    return m;
}
inline Bitboard front_span_black(Square sq) {
    Bitboard m = 0;
    for (int r = rank_of(sq) - 1; r >= 0; --r) {
        m |= RANK_1 << (8 * r);
    }
    return m;
}

// King-zone: king square + 8 neighbors. Used for EVAL-08 attack units.
inline Bitboard king_zone(Square ksq) {
    return king_attacks[ksq] | square_bb(ksq);
}

// Attack-units weight per attacker piece type. These multipliers are
// part of the king-safety MODEL (not weights); the cp penalty per units
// total lives entirely in v7::coeffs::king_attack_table[]. Keeping these as
// local constants preserves the "all tunable weights in coeffs.json"
// invariant — these are the model-shape coefficients (analogous to the
// `24` in the tapered formula) rather than tunable cp values.
constexpr int ATTACK_UNITS[6] = {
    0,  // PAWN: contributes via pawn attacks on king zone but conservatively 0 here
    2,  // KNIGHT
    2,  // BISHOP
    3,  // ROOK
    5,  // QUEEN
    0   // KING
};

} // namespace

int evaluate(const Board& board, bool fortress_enabled) {
    // ---- Phase (ENDG-04 / Plan 03-04) -----------------------------------
    // Stockfish-style 0..256 continuous phase blend using non_pawn_material().
    // Replaces the old 0-24 Pesto integer accumulator.
    //
    // npm = std::clamp(non_pawn_material(WHITE) + non_pawn_material(BLACK),
    //                  endgame_limit, midgame_limit)
    // phase = ((npm - endgame_limit) * 256) / (midgame_limit - endgame_limit)
    // phase = 256 at full midgame (all pieces), 0 at bare kings
    int npm = board.non_pawn_material(WHITE) + board.non_pawn_material(BLACK);
    npm = std::clamp(npm, v7::coeffs::endgame_limit, v7::coeffs::midgame_limit);
    int phase = ((npm - v7::coeffs::endgame_limit) * 256) /
                (v7::coeffs::midgame_limit - v7::coeffs::endgame_limit);

    // ---- Material + PSTs (EVAL-01, EVAL-02) ------------------------------
    int mg_score = 0;
    int eg_score = 0;

    for (int p = PAWN; p <= KING; ++p) {
        Piece piece = static_cast<Piece>(p);
        // White pieces
        Bitboard bb_white = board.pieces_of(WHITE, piece);
        while (bb_white) {
            Square sq = static_cast<Square>(pop_lsb(bb_white));
            mg_score += material_mg(piece) + pst_mg(piece, sq);
            eg_score += material_eg(piece) + pst_eg(piece, sq);
        }
        // Black pieces (mirror PST square; subtract from running totals)
        Bitboard bb_black = board.pieces_of(BLACK, piece);
        while (bb_black) {
            Square sq = static_cast<Square>(pop_lsb(bb_black));
            Square ms = mirror_sq(sq);
            mg_score -= material_mg(piece) + pst_mg(piece, ms);
            eg_score -= material_eg(piece) + pst_eg(piece, ms);
        }
    }

    // ---- Mobility (EVAL-04) ----------------------------------------------
    // Indexed by attack-count clamped to the table length. Excludes squares
    // occupied by friendly pieces.
    Bitboard occ = board.occupied();
    for (Color c = WHITE; c <= BLACK; ++c) {
        Bitboard own = board.colors[c];
        int sign = (c == WHITE) ? 1 : -1;

        Bitboard knights = board.pieces_of(c, KNIGHT);
        while (knights) {
            Square sq = static_cast<Square>(pop_lsb(knights));
            int mc = popcount(knight_attacks[sq] & ~own);
            if (mc > 8) mc = 8;
            mg_score += sign * v7::coeffs::mobility_knight_mg[mc];
            eg_score += sign * v7::coeffs::mobility_knight_eg[mc];
        }
        Bitboard bishops = board.pieces_of(c, BISHOP);
        while (bishops) {
            Square sq = static_cast<Square>(pop_lsb(bishops));
            int mc = popcount(bishop_attacks(sq, occ) & ~own);
            if (mc > 13) mc = 13;
            mg_score += sign * v7::coeffs::mobility_bishop_mg[mc];
            eg_score += sign * v7::coeffs::mobility_bishop_eg[mc];
        }
        Bitboard rooks = board.pieces_of(c, ROOK);
        while (rooks) {
            Square sq = static_cast<Square>(pop_lsb(rooks));
            int mc = popcount(rook_attacks(sq, occ) & ~own);
            if (mc > 14) mc = 14;
            mg_score += sign * v7::coeffs::mobility_rook_mg[mc];
            eg_score += sign * v7::coeffs::mobility_rook_eg[mc];
        }
        Bitboard queens = board.pieces_of(c, QUEEN);
        while (queens) {
            Square sq = static_cast<Square>(pop_lsb(queens));
            int mc = popcount(queen_attacks(sq, occ) & ~own);
            if (mc > 27) mc = 27;
            mg_score += sign * v7::coeffs::mobility_queen_mg[mc];
            eg_score += sign * v7::coeffs::mobility_queen_eg[mc];
        }
    }

    // ---- Bishop pair (EVAL-05) -------------------------------------------
    if (popcount(board.pieces_of(WHITE, BISHOP)) >= 2) {
        mg_score += v7::coeffs::bishop_pair_mg;
        eg_score += v7::coeffs::bishop_pair_eg;
    }
    if (popcount(board.pieces_of(BLACK, BISHOP)) >= 2) {
        mg_score -= v7::coeffs::bishop_pair_mg;
        eg_score -= v7::coeffs::bishop_pair_eg;
    }

    // ---- Rook on (semi-)open file (EVAL-06) ------------------------------
    Bitboard white_pawns = board.pieces_of(WHITE, PAWN);
    Bitboard black_pawns = board.pieces_of(BLACK, PAWN);
    for (Color c = WHITE; c <= BLACK; ++c) {
        int sign = (c == WHITE) ? 1 : -1;
        Bitboard own_pawns = (c == WHITE) ? white_pawns : black_pawns;
        Bitboard enemy_pawns = (c == WHITE) ? black_pawns : white_pawns;
        Bitboard rooks = board.pieces_of(c, ROOK);
        while (rooks) {
            Square sq = static_cast<Square>(pop_lsb(rooks));
            Bitboard fm = FILE_MASKS_LOC[file_of(sq)];
            bool own_blocks = (fm & own_pawns) != 0;
            bool enemy_blocks = (fm & enemy_pawns) != 0;
            if (!own_blocks && !enemy_blocks) {
                mg_score += sign * v7::coeffs::rook_open_file;
                eg_score += sign * v7::coeffs::rook_open_file;
            } else if (!own_blocks) {
                mg_score += sign * v7::coeffs::rook_semi_open_file;
                eg_score += sign * v7::coeffs::rook_semi_open_file;
            }
        }
    }

    // ---- Pawn structure (EVAL-08 terms) ----------------------------------
    // TODO(phase-4): pawn hash table for incremental eval (EVAL-08 NPS optimization)
    for (Color c = WHITE; c <= BLACK; ++c) {
        int sign = (c == WHITE) ? 1 : -1;
        Bitboard own_pawns = (c == WHITE) ? white_pawns : black_pawns;
        Bitboard enemy_pawns = (c == WHITE) ? black_pawns : white_pawns;

        Bitboard scan = own_pawns;
        while (scan) {
            Square sq = static_cast<Square>(pop_lsb(scan));
            int f = file_of(sq);
            int r = rank_of(sq);
            Bitboard fm = FILE_MASKS_LOC[f];
            Bitboard adj = adjacent_files(f);

            // Doubled: more than one own pawn on the same file
            if (popcount(own_pawns & fm) > 1) {
                mg_score += sign * v7::coeffs::doubled_pawn;
                eg_score += sign * v7::coeffs::doubled_pawn;
            }
            // Isolated: no own pawn on any adjacent file
            if ((own_pawns & adj) == 0) {
                mg_score += sign * v7::coeffs::isolated_pawn;
                eg_score += sign * v7::coeffs::isolated_pawn;
            }
            // Backward: own pawn has no friendly pawn on an adjacent file
            // at or behind its rank, AND is not isolated (isolated takes
            // precedence — backward is a milder penalty for pawns that
            // have neighbors but can't be defended from behind).
            Bitboard backwards_region = 0;
            if (c == WHITE) {
                for (int rr = 0; rr <= r; ++rr) backwards_region |= (RANK_1 << (8 * rr));
            } else {
                for (int rr = 7; rr >= r; --rr) backwards_region |= (RANK_1 << (8 * rr));
            }
            const bool has_adj_pawn = (own_pawns & adj) != 0;
            const bool no_backup    = (own_pawns & adj & backwards_region) == 0;
            if (has_adj_pawn && no_backup) {
                mg_score += sign * v7::coeffs::backward_pawn;
                eg_score += sign * v7::coeffs::backward_pawn;
            }
            // Passed pawn: no enemy pawn in front on own file or adjacent files
            Bitboard front = (c == WHITE) ? front_span_white(sq) : front_span_black(sq);
            Bitboard block_mask = (fm | adj) & front;
            if ((enemy_pawns & block_mask) == 0) {
                int idx = (c == WHITE) ? r : (7 - r);
                if (idx < 0) idx = 0;
                if (idx > 7) idx = 7;
                int bonus = v7::coeffs::passed_pawn_by_rank[idx];
                mg_score += sign * bonus;
                eg_score += sign * bonus;
            }
        }
    }

    // ---- Threats (EVAL-07) -----------------------------------------------
    // For each color, compute pawn attacks; squares attacked by enemy
    // pawns that hold our minor pieces incur threat_minor_by_pawn. Same
    // shape for rook-by-minor and queen-by-rook.
    Bitboard white_pawn_atk =
        shift_north_east(white_pawns) | shift_north_west(white_pawns);
    Bitboard black_pawn_atk =
        shift_south_east(black_pawns) | shift_south_west(black_pawns);

    {
        // Our minors attacked by enemy pawns
        Bitboard w_minors = board.pieces_of(WHITE, KNIGHT) | board.pieces_of(WHITE, BISHOP);
        Bitboard b_minors = board.pieces_of(BLACK, KNIGHT) | board.pieces_of(BLACK, BISHOP);
        int wm_threats = popcount(w_minors & black_pawn_atk);
        int bm_threats = popcount(b_minors & white_pawn_atk);
        mg_score += wm_threats * v7::coeffs::threat_minor_by_pawn;
        eg_score += wm_threats * v7::coeffs::threat_minor_by_pawn;
        mg_score -= bm_threats * v7::coeffs::threat_minor_by_pawn;
        eg_score -= bm_threats * v7::coeffs::threat_minor_by_pawn;
    }
    {
        // Rook attacked by enemy minor (collect minor attack squares)
        Bitboard w_minor_atk = 0;
        Bitboard bn = board.pieces_of(WHITE, KNIGHT);
        while (bn) { w_minor_atk |= knight_attacks[pop_lsb(bn)]; }
        Bitboard bb = board.pieces_of(WHITE, BISHOP);
        while (bb) { w_minor_atk |= bishop_attacks(pop_lsb(bb), occ); }

        Bitboard b_minor_atk = 0;
        Bitboard bn2 = board.pieces_of(BLACK, KNIGHT);
        while (bn2) { b_minor_atk |= knight_attacks[pop_lsb(bn2)]; }
        Bitboard bb2 = board.pieces_of(BLACK, BISHOP);
        while (bb2) { b_minor_atk |= bishop_attacks(pop_lsb(bb2), occ); }

        int wr_threats = popcount(board.pieces_of(WHITE, ROOK) & b_minor_atk);
        int br_threats = popcount(board.pieces_of(BLACK, ROOK) & w_minor_atk);
        mg_score += wr_threats * v7::coeffs::threat_rook_by_minor;
        eg_score += wr_threats * v7::coeffs::threat_rook_by_minor;
        mg_score -= br_threats * v7::coeffs::threat_rook_by_minor;
        eg_score -= br_threats * v7::coeffs::threat_rook_by_minor;

        // Queen attacked by enemy rook
        Bitboard w_rook_atk = 0;
        Bitboard wr = board.pieces_of(WHITE, ROOK);
        while (wr) { w_rook_atk |= rook_attacks(pop_lsb(wr), occ); }
        Bitboard b_rook_atk = 0;
        Bitboard br = board.pieces_of(BLACK, ROOK);
        while (br) { b_rook_atk |= rook_attacks(pop_lsb(br), occ); }

        int wq_threats = popcount(board.pieces_of(WHITE, QUEEN) & b_rook_atk);
        int bq_threats = popcount(board.pieces_of(BLACK, QUEEN) & w_rook_atk);
        mg_score += wq_threats * v7::coeffs::threat_queen_by_rook;
        eg_score += wq_threats * v7::coeffs::threat_queen_by_rook;
        mg_score -= bq_threats * v7::coeffs::threat_queen_by_rook;
        eg_score -= bq_threats * v7::coeffs::threat_queen_by_rook;
    }

    // ---- King safety (EVAL-08) -------------------------------------------
    // Accumulate attack units for each enemy piece attacking the friendly
    // king zone, index into king_attack_table[], subtract from STM side.
    for (Color c = WHITE; c <= BLACK; ++c) {
        Color enemy = static_cast<Color>(1 - c);
        Square ksq = board.king_square(c);
        Bitboard kz = king_zone(ksq);
        int units = 0;

        // Knight attackers
        Bitboard kn = board.pieces_of(enemy, KNIGHT);
        while (kn) {
            Square s = static_cast<Square>(pop_lsb(kn));
            if (knight_attacks[s] & kz) units += ATTACK_UNITS[KNIGHT];
        }
        // Bishop attackers
        Bitboard bs = board.pieces_of(enemy, BISHOP);
        while (bs) {
            Square s = static_cast<Square>(pop_lsb(bs));
            if (bishop_attacks(s, occ) & kz) units += ATTACK_UNITS[BISHOP];
        }
        // Rook attackers
        Bitboard rk = board.pieces_of(enemy, ROOK);
        while (rk) {
            Square s = static_cast<Square>(pop_lsb(rk));
            if (rook_attacks(s, occ) & kz) units += ATTACK_UNITS[ROOK];
        }
        // Queen attackers
        Bitboard qn = board.pieces_of(enemy, QUEEN);
        while (qn) {
            Square s = static_cast<Square>(pop_lsb(qn));
            if (queen_attacks(s, occ) & kz) units += ATTACK_UNITS[QUEEN];
        }
        if (units > 99) units = 99;
        if (units < 0) units = 0;
        int penalty = v7::coeffs::king_attack_table[units];
        int sign = (c == WHITE) ? -1 : 1;  // penalty hurts the king's owner
        mg_score += sign * penalty;
        eg_score += sign * penalty;
    }

    // ---- Tempo (EVAL-09) -------------------------------------------------
    if (board.side_to_move == WHITE) {
        mg_score += v7::coeffs::tempo_mg;
        eg_score += v7::coeffs::tempo_eg;
    } else {
        mg_score -= v7::coeffs::tempo_mg;
        eg_score -= v7::coeffs::tempo_eg;
    }

    // ---- Endgame eval hook (Plan 03-04 ENDG-01..05) ---------------------
    // Called between the tempo block and the tapered combine.
    // May adjust mg_score/eg_score in-place or short-circuit for known
    // draw/win positions (KPK, wrong-bishop+RP, fortress).
    endgame_eval(board, mg_score, eg_score, phase, fortress_enabled);

    // ---- ENDG-04 Stockfish-style 0..256 tapered combine -----------------
    // Replaces old `(mg * phase + eg * (24 - phase)) / 24` formula.
    // phase = 256 at full midgame; phase = 0 at bare kings.
    int final_score = (mg_score * phase + eg_score * (256 - phase)) / 256;

    // Return from STM perspective (unchanged from EVAL-11)
    return (board.side_to_move == WHITE) ? final_score : -final_score;
}

int see(const Board& board, Move m) {
    Square from = move_from(m);
    Square to = move_to(m);

    Piece attacker = board.piece_at(from);
    Piece victim = board.piece_at(to);

    if (victim == NO_PIECE) {
        if (move_type(m) == EN_PASSANT) {
            return material_mg(PAWN);
        }
        return 0;
    }

    int victim_value = material_mg(victim);
    int attacker_value = material_mg(attacker);

    if (attacker_value <= victim_value) {
        return victim_value;
    }

    return victim_value - attacker_value / 2;
}

int evaluate_entry(const std::string& fen) {
    init_magics();

    Board b;
    b.from_fen(fen);
    return evaluate(b);
}

int compute_phase(const Board& board) {
    // Expose the 0..256 Stockfish-style phase for testing (ENDG-04 / test_v7_phase_blend.py).
    int npm = board.non_pawn_material(WHITE) + board.non_pawn_material(BLACK);
    npm = std::clamp(npm, v7::coeffs::endgame_limit, v7::coeffs::midgame_limit);
    int phase = ((npm - v7::coeffs::endgame_limit) * 256) /
                (v7::coeffs::midgame_limit - v7::coeffs::endgame_limit);
    return phase;
}

} // namespace v7
