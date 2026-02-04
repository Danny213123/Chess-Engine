"""
V5 Evaluation - Optimized Static Position Evaluation with Numba JIT
"""

import numpy as np
from numba import njit, uint64, int32, boolean

from main.engine.v5.bitboard import (
    popcount, bitscan_forward, iter_bits,
    KNIGHT_ATTACKS, KING_ATTACKS,
    RANK_2, RANK_3, RANK_6, RANK_7
)
from main.engine.v5.magic import (
    ROOK_ATTACK_TABLES, BISHOP_ATTACK_TABLES,
    ROOK_MASKS, BISHOP_MASKS,
    ROOK_MAGICS, BISHOP_MAGICS,
    ROOK_RELEVANT_BITS, BISHOP_RELEVANT_BITS
)
from main.engine.v5.board import BoardState, WP, WN, WB, WR, WQ, WK, BP, BN, BB, BR, BQ, BK

# =============================================================================
# CONSTANTS & TABLES (Optimized for Numba)
# =============================================================================

# Material
PIECE_VALUES_MG = np.array([100, 320, 330, 500, 900, 20000], dtype=np.int32)
PIECE_VALUES_EG = np.array([120, 300, 320, 550, 1000, 20000], dtype=np.int32)

PHASE_TOTAL = 4 * PIECE_VALUES_MG[1] + 4 * PIECE_VALUES_MG[2] + 4 * PIECE_VALUES_MG[3] + 2 * PIECE_VALUES_MG[4]

# PSTs (Flattened for Numba)
PAWN_PST_MG = np.array([
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0
], dtype=np.int32)

PAWN_PST_EG = np.array([
     0,  0,  0,  0,  0,  0,  0,  0,
    80, 80, 80, 80, 80, 80, 80, 80,
    50, 50, 50, 50, 50, 50, 50, 50,
    30, 30, 30, 30, 30, 30, 30, 30,
    20, 20, 20, 20, 20, 20, 20, 20,
    10, 10, 10, 10, 10, 10, 10, 10,
     5,  5,  5,  5,  5,  5,  5,  5,
     0,  0,  0,  0,  0,  0,  0,  0
], dtype=np.int32)

KNIGHT_PST_MG = np.array([
   -50,-40,-30,-30,-30,-30,-40,-50,
   -40,-20,  0,  0,  0,  0,-20,-40,
   -30,  0, 10, 15, 15, 10,  0,-30,
   -30,  5, 15, 20, 20, 15,  5,-30,
   -30,  0, 15, 20, 20, 15,  0,-30,
   -30,  5, 10, 15, 15, 10,  5,-30,
   -40,-20,  0,  5,  5,  0,-20,-40,
   -50,-40,-30,-30,-30,-30,-40,-50
], dtype=np.int32)

BISHOP_PST_MG = np.array([
   -20,-10,-10,-10,-10,-10,-10,-20,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -10,  0,  5, 10, 10,  5,  0,-10,
   -10,  5,  5, 10, 10,  5,  5,-10,
   -10,  0, 10, 10, 10, 10,  0,-10,
   -10, 10, 10, 10, 10, 10, 10,-10,
   -10,  5,  0,  0,  0,  0,  5,-10,
   -20,-10,-10,-10,-10,-10,-10,-20
], dtype=np.int32)

ROOK_PST_MG = np.array([
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0
], dtype=np.int32)

QUEEN_PST_MG = np.array([
   -20,-10,-10, -5, -5,-10,-10,-20,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -10,  0,  5,  5,  5,  5,  0,-10,
    -5,  0,  5,  5,  5,  5,  0, -5,
     0,  0,  5,  5,  5,  5,  0, -5,
   -10,  5,  5,  5,  5,  5,  0,-10,
   -10,  0,  5,  0,  0,  0,  0,-10,
   -20,-10,-10, -5, -5,-10,-10,-20
], dtype=np.int32)

KING_PST_MG = np.array([
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -20,-30,-30,-40,-40,-30,-30,-20,
   -10,-20,-20,-20,-20,-20,-20,-10,
    20, 20,  0,  0,  0,  0, 20, 20,
    20, 30, 10,  0,  0, 10, 30, 20
], dtype=np.int32)

KING_PST_EG = np.array([
   -50,-40,-30,-20,-20,-30,-40,-50,
   -30,-20,-10,  0,  0,-10,-20,-30,
   -30,-10, 20, 30, 30, 20,-10,-30,
   -30,-10, 30, 40, 40, 30,-10,-30,
   -30,-10, 30, 40, 40, 30,-10,-30,
   -30,-10, 20, 30, 30, 20,-10,-30,
   -30,-30,  0,  0,  0,  0,-30,-30,
   -50,-30,-30,-30,-30,-30,-30,-50
], dtype=np.int32)

# Stack PSTs for simple indexing: PST_MG_ARR[piece_type, sq]
PST_MG_ARR = np.vstack((PAWN_PST_MG, KNIGHT_PST_MG, BISHOP_PST_MG, ROOK_PST_MG, QUEEN_PST_MG, KING_PST_MG)).astype(np.int32)
PST_EG_ARR = np.vstack((PAWN_PST_EG, KNIGHT_PST_MG, BISHOP_PST_MG, np.zeros(64, dtype=np.int32), QUEEN_PST_MG, KING_PST_EG)).astype(np.int32)

# Magic Lookups - Flattened
ROOK_LUT = np.concatenate(ROOK_ATTACK_TABLES).astype(np.uint64)
BISHOP_LUT = np.concatenate(BISHOP_ATTACK_TABLES).astype(np.uint64)

ROOK_OFFSETS = np.zeros(64, dtype=np.int32)
curr = 0
for i in range(64):
    ROOK_OFFSETS[i] = curr
    curr += len(ROOK_ATTACK_TABLES[i])

BISHOP_OFFSETS = np.zeros(64, dtype=np.int32)
curr = 0
for i in range(64):
    BISHOP_OFFSETS[i] = curr
    curr += len(BISHOP_ATTACK_TABLES[i])

# Bonuses
INFINITY = 30000
MATE_SCORE = 29000
DRAW_SCORE = 0
TEMPO_BONUS = 10
BISHOP_PAIR_BONUS_MG = 30
BISHOP_PAIR_BONUS_EG = 50
MOBILITY_KNIGHT = 4
MOBILITY_BISHOP = 5
MOBILITY_ROOK = 2
DOUBLED_PAWN_PENALTY = -10
ISOLATED_PAWN_PENALTY = -20
PASSED_PAWN_BONUS = np.array([0, 10, 20, 40, 60, 100, 150, 0], dtype=np.int32)

# Rook bonuses
ROOK_OPEN_FILE_BONUS = 40
ROOK_SEMI_OPEN_FILE_BONUS = 20
ROOK_ON_SEVENTH_MG = 30
ROOK_ON_SEVENTH_EG = 50

# Knight bonuses
KNIGHT_OUTPOST_BONUS_MG = 25
KNIGHT_OUTPOST_BONUS_EG = 15

# Bishop penalties
BAD_BISHOP_PENALTY_MG = 3
BAD_BISHOP_PENALTY_EG = 5

# King Safety
KING_SAFETY_PAWN_SHIELD_MISSING = -10
KING_SAFETY_SEMI_OPEN_FILE = -25
KING_SAFETY_OPEN_FILE = -45

FILE_MASKS = np.array([0x0101010101010101 << i for i in range(8)], dtype=np.uint64)
ADJACENT_FILES = np.array([
    FILE_MASKS[max(0, i-1)] | FILE_MASKS[min(7, i+1)] if i > 0 and i < 7 else (FILE_MASKS[1] if i == 0 else FILE_MASKS[6])
    for i in range(8)
], dtype=np.uint64)

# Rank masks
RANK_MASKS = np.array([uint64(0xFF) << (i * 8) for i in range(8)], dtype=np.uint64)

# Light and dark squares
LIGHT_SQUARES = uint64(0x55AA55AA55AA55AA)
DARK_SQUARES = uint64(0xAA55AA55AA55AA55)


# =============================================================================
# JIT HELPERS (Inlined for Strict Typing)
# =============================================================================

@njit(cache=True)
def _popcount(bb: uint64) -> int32:
    count = int32(0)
    while bb:
        bb &= bb - uint64(1)
        count += int32(1)
    return count

@njit(cache=True)
def _bitscan_forward(bb: uint64) -> int32:
    if bb == uint64(0):
        return int32(-1)
    count = int32(0)
    while (bb & uint64(1)) == uint64(0):
        bb >>= uint64(1)
        count += int32(1)
    return count

@njit(cache=True)
def _iter_bits(bb: uint64):
    squares = np.empty(64, dtype=np.int32)
    count = int32(0)
    while bb:
        sq = _bitscan_forward(bb)
        squares[count] = sq
        count += int32(1)
        bb &= bb - uint64(1)
    return squares[:count]

@njit(cache=True)
def get_file(sq: int32) -> int32:
    return sq & int32(7)

@njit(cache=True)
def get_rank(sq: int32) -> int32:
    return sq >> int32(3)

@njit(cache=True)
def get_rook_attacks_fast(sq, occ, masks, magics, bits, lut, offsets):
    mask = masks[sq]
    blockers = occ & mask
    shift = int32(64) - bits[sq]
    index = int32((blockers * magics[sq]) >> shift)
    return lut[offsets[sq] + index]

@njit(cache=True)
def get_bishop_attacks_fast(sq, occ, masks, magics, bits, lut, offsets):
    mask = masks[sq]
    blockers = occ & mask
    shift = int32(64) - bits[sq]
    index = int32((blockers * magics[sq]) >> shift)
    return lut[offsets[sq] + index]

# =============================================================================
# FAST EVALUATION (JIT)
# =============================================================================

@njit(int32(uint64[:], uint64, uint64, uint64, boolean))
def evaluate_fast(pieces, white_occ, black_occ, all_occ, white_to_move):
    score_mg = 0
    score_eg = 0
    phase = 0
    
    white_pawns = uint64(pieces[WP])
    black_pawns = uint64(pieces[BP])

    # --- MATERIAL + PST ---
    for pt in range(6):
        # White
        w_bb = uint64(pieces[pt])
        # iter_bits returns array of squares, nopython loop works
        for sq in _iter_bits(w_bb):
            score_mg += PIECE_VALUES_MG[pt] + PST_MG_ARR[pt, sq]
            score_eg += PIECE_VALUES_EG[pt] + PST_EG_ARR[pt, sq]
            if pt >= 1 and pt <= 4:
                phase += PIECE_VALUES_MG[pt]

        # Black
        b_bb = uint64(pieces[pt + 6])
        for sq in _iter_bits(b_bb):
            mirrored = sq ^ 56
            score_mg -= PIECE_VALUES_MG[pt] + PST_MG_ARR[pt, mirrored]
            score_eg -= PIECE_VALUES_EG[pt] + PST_EG_ARR[pt, mirrored]
            if pt >= 1 and pt <= 4:
                phase += PIECE_VALUES_MG[pt]

    # --- BISHOP PAIR ---
    if _popcount(uint64(pieces[WB])) >= 2:
        score_mg += BISHOP_PAIR_BONUS_MG
        score_eg += BISHOP_PAIR_BONUS_EG
    if _popcount(uint64(pieces[BB])) >= 2:
        score_mg -= BISHOP_PAIR_BONUS_MG
        score_eg -= BISHOP_PAIR_BONUS_EG

    # --- MOBILITY ---
    # Knight
    for sq in _iter_bits(uint64(pieces[WN])):
        atk = KNIGHT_ATTACKS[sq] & ~white_occ
        score_mg += _popcount(atk) * MOBILITY_KNIGHT
    for sq in _iter_bits(uint64(pieces[BN])):
        atk = KNIGHT_ATTACKS[sq] & ~black_occ
        score_mg -= _popcount(atk) * MOBILITY_KNIGHT

    # Bishop
    for sq in _iter_bits(uint64(pieces[WB])):
        atk = get_bishop_attacks_fast(sq, all_occ, BISHOP_MASKS, BISHOP_MAGICS, BISHOP_RELEVANT_BITS, BISHOP_LUT, BISHOP_OFFSETS) & ~white_occ
        score_mg += _popcount(atk) * MOBILITY_BISHOP
    for sq in _iter_bits(uint64(pieces[BB])):
        atk = get_bishop_attacks_fast(sq, all_occ, BISHOP_MASKS, BISHOP_MAGICS, BISHOP_RELEVANT_BITS, BISHOP_LUT, BISHOP_OFFSETS) & ~black_occ
        score_mg -= _popcount(atk) * MOBILITY_BISHOP

    # Rook
    for sq in _iter_bits(uint64(pieces[WR])):
        atk = get_rook_attacks_fast(sq, all_occ, ROOK_MASKS, ROOK_MAGICS, ROOK_RELEVANT_BITS, ROOK_LUT, ROOK_OFFSETS) & ~white_occ
        score_mg += _popcount(atk) * MOBILITY_ROOK
    for sq in _iter_bits(uint64(pieces[BR])):
        atk = get_rook_attacks_fast(sq, all_occ, ROOK_MASKS, ROOK_MAGICS, ROOK_RELEVANT_BITS, ROOK_LUT, ROOK_OFFSETS) & ~black_occ
        score_mg -= _popcount(atk) * MOBILITY_ROOK

    # --- ROOK BONUSES ---
    # White rooks
    for sq in _iter_bits(uint64(pieces[WR])):
        file = get_file(sq)
        rank = get_rank(sq)
        f_mask = FILE_MASKS[file]

        # Open file (no pawns)
        if not (white_pawns & f_mask) and not (black_pawns & f_mask):
            score_mg += ROOK_OPEN_FILE_BONUS
            score_eg += ROOK_OPEN_FILE_BONUS // 2
        # Semi-open file (no friendly pawns)
        elif not (white_pawns & f_mask):
            score_mg += ROOK_SEMI_OPEN_FILE_BONUS
            score_eg += ROOK_SEMI_OPEN_FILE_BONUS // 2

        # Rook on 7th rank
        if rank == int32(6):  # Rank 7 for white (0-indexed from rank 1)
            score_mg += ROOK_ON_SEVENTH_MG
            score_eg += ROOK_ON_SEVENTH_EG

    # Black rooks
    for sq in _iter_bits(uint64(pieces[BR])):
        file = get_file(sq)
        rank = get_rank(sq)
        f_mask = FILE_MASKS[file]

        # Open file
        if not (white_pawns & f_mask) and not (black_pawns & f_mask):
            score_mg -= ROOK_OPEN_FILE_BONUS
            score_eg -= ROOK_OPEN_FILE_BONUS // 2
        # Semi-open file
        elif not (black_pawns & f_mask):
            score_mg -= ROOK_SEMI_OPEN_FILE_BONUS
            score_eg -= ROOK_SEMI_OPEN_FILE_BONUS // 2

        # Rook on 2nd rank
        if rank == int32(1):  # Rank 2 for black (0-indexed from rank 1)
            score_mg -= ROOK_ON_SEVENTH_MG
            score_eg -= ROOK_ON_SEVENTH_EG

    # --- KNIGHT OUTPOSTS ---
    # White knights
    for sq in _iter_bits(uint64(pieces[WN])):
        rank = get_rank(sq)
        file = get_file(sq)

        # In enemy territory (ranks 5-7 for white)
        if rank >= int32(4):
            # Check if protected by friendly pawn
            pawn_protected = False
            # Check diagonally backward squares for white pawns
            if file > int32(0) and rank > int32(0):
                if uint64(pieces[WP]) & (uint64(1) << ((rank - int32(1)) * int32(8) + file - int32(1))):
                    pawn_protected = True
            if file < int32(7) and rank > int32(0):
                if uint64(pieces[WP]) & (uint64(1) << ((rank - int32(1)) * int32(8) + file + int32(1))):
                    pawn_protected = True

            if pawn_protected:
                # Check if cannot be attacked by enemy pawns
                ahead_mask = FILE_MASKS[file]
                for r in range(rank + int32(1), int32(8)):
                    ahead_mask |= uint64(1) << (r * int32(8) + file)

                adj_files = ADJACENT_FILES[file]
                enemy_pawn_threat = black_pawns & (ahead_mask | (adj_files & ahead_mask))

                if not enemy_pawn_threat:
                    score_mg += KNIGHT_OUTPOST_BONUS_MG
                    score_eg += KNIGHT_OUTPOST_BONUS_EG

    # Black knights
    for sq in _iter_bits(uint64(pieces[BN])):
        rank = get_rank(sq)
        file = get_file(sq)

        # In enemy territory (ranks 2-4 for black, which is ranks 1-3 in 0-indexed)
        if rank <= int32(3):
            # Check if protected by friendly pawn
            pawn_protected = False
            if file > int32(0) and rank < int32(7):
                if uint64(pieces[BP]) & (uint64(1) << ((rank + int32(1)) * int32(8) + file - int32(1))):
                    pawn_protected = True
            if file < int32(7) and rank < int32(7):
                if uint64(pieces[BP]) & (uint64(1) << ((rank + int32(1)) * int32(8) + file + int32(1))):
                    pawn_protected = True

            if pawn_protected:
                # Check if cannot be attacked by enemy pawns
                ahead_mask = uint64(0)
                for r in range(int32(0), rank):
                    ahead_mask |= FILE_MASKS[file] & RANK_MASKS[r]

                adj_files = ADJACENT_FILES[file]
                enemy_pawn_threat = white_pawns & (ahead_mask | (adj_files & ahead_mask))

                if not enemy_pawn_threat:
                    score_mg -= KNIGHT_OUTPOST_BONUS_MG
                    score_eg -= KNIGHT_OUTPOST_BONUS_EG

    # --- BAD BISHOPS ---
    # White bishops - penalize if many pawns on same color
    for sq in _iter_bits(uint64(pieces[WB])):
        # Check if bishop is on light or dark square
        if (sq & int32(1)) ^ ((sq >> int32(3)) & int32(1)):  # Dark square
            blocked_pawns = _popcount(white_pawns & DARK_SQUARES)
        else:  # Light square
            blocked_pawns = _popcount(white_pawns & LIGHT_SQUARES)

        score_mg -= blocked_pawns * BAD_BISHOP_PENALTY_MG
        score_eg -= blocked_pawns * BAD_BISHOP_PENALTY_EG

    # Black bishops
    for sq in _iter_bits(uint64(pieces[BB])):
        if (sq & int32(1)) ^ ((sq >> int32(3)) & int32(1)):  # Dark square
            blocked_pawns = _popcount(black_pawns & DARK_SQUARES)
        else:  # Light square
            blocked_pawns = _popcount(black_pawns & LIGHT_SQUARES)

        score_mg += blocked_pawns * BAD_BISHOP_PENALTY_MG
        score_eg += blocked_pawns * BAD_BISHOP_PENALTY_EG

    # --- PAWN STRUCTURE ---
    # White
    for sq in _iter_bits(white_pawns):
        file = get_file(sq)
        rank = get_rank(sq)
        f_mask = FILE_MASKS[file]
        
        # Doubled
        if _popcount(white_pawns & f_mask) > 1:
            score_mg += DOUBLED_PAWN_PENALTY
            score_eg += DOUBLED_PAWN_PENALTY
        
        # Isolated
        adj = ADJACENT_FILES[file]
        if not (white_pawns & adj):
            score_mg += ISOLATED_PAWN_PENALTY
            score_eg += ISOLATED_PAWN_PENALTY
            
        # Passed
        ahead_mask = (f_mask | adj) & (uint64(0xFF) << ((rank + 1) * 8))
        # Mask out bits below rank+1 via shift... Wait, logic check:
        # Simplest passed pawn check: No black pawns ahead in file or adj files
        # Efficient mask usage:
        # We need a mask of all squares "ahead" of this pawn on file and adjacent files.
        # Numba doesn't have `~` on scalars in same way cleanly without types.
        # Let's simple loop check.
        passed = True
        # Check squares ahead for black pawns
        # Mask for squares ahead on file + adj
        check_mask = (f_mask | adj)
        # We need to mask out ranks <= current rank
        # 0xFFFFFF... << ((rank+1)*8)
        rank_mask = uint64(0xFFFFFFFFFFFFFFFF) << uint64((rank + 1) * 8)
        if (black_pawns & check_mask & rank_mask):
            passed = False
            
        if passed:
            score_mg += PASSED_PAWN_BONUS[rank]
            score_eg += PASSED_PAWN_BONUS[rank] * 2

    # Black
    for sq in _iter_bits(black_pawns):
        file = get_file(sq)
        rank = get_rank(sq)
        f_mask = FILE_MASKS[file]
        
        if _popcount(black_pawns & f_mask) > 1:
            score_mg -= DOUBLED_PAWN_PENALTY
            score_eg -= DOUBLED_PAWN_PENALTY
            
        adj = ADJACENT_FILES[file]
        if not (black_pawns & adj):
            score_mg -= ISOLATED_PAWN_PENALTY
            score_eg -= ISOLATED_PAWN_PENALTY
            
        # Passed (looking "down" board, ranks < current)
        passed = True
        check_mask = (f_mask | adj)
        # Shift >> ? No, clear high bits.
        # Mask for lower ranks: ~(0xFF... << (rank * 8))
        rank_mask = ~(uint64(0xFFFFFFFFFFFFFFFF) << uint64(rank * 8))
        if (white_pawns & check_mask & rank_mask):
            passed = False
            
        if passed:
            score_mg -= PASSED_PAWN_BONUS[7 - rank]
            score_eg -= PASSED_PAWN_BONUS[7 - rank] * 2

    # --- KING SAFETY ---
    # White
    w_king_sq = _bitscan_forward(uint64(pieces[WK]))
    if w_king_sq < 16:
        k_file = get_file(w_king_sq)
        start_f = max(0, k_file - 1)
        end_f = min(7, k_file + 1)
        
        for f in range(start_f, end_f + 1):
            f_mask = FILE_MASKS[f]
            if not (white_pawns & f_mask):
                if (black_pawns & f_mask):
                    score_mg += KING_SAFETY_SEMI_OPEN_FILE
                else:
                    score_mg += KING_SAFETY_OPEN_FILE
            elif not (white_pawns & f_mask & (RANK_2 | RANK_3)):
                 score_mg += KING_SAFETY_PAWN_SHIELD_MISSING

    # Black
    b_king_sq = _bitscan_forward(uint64(pieces[BK]))
    if b_king_sq >= 48:
        k_file = get_file(b_king_sq)
        start_f = max(0, k_file - 1)
        end_f = min(7, k_file + 1)
        
        for f in range(start_f, end_f + 1):
            f_mask = FILE_MASKS[f]
            if not (black_pawns & f_mask):
                if (white_pawns & f_mask):
                    score_mg -= KING_SAFETY_SEMI_OPEN_FILE
                else:
                    score_mg -= KING_SAFETY_OPEN_FILE
            elif not (black_pawns & f_mask & (RANK_6 | RANK_7)):
                 score_mg -= KING_SAFETY_PAWN_SHIELD_MISSING

    # --- TAPERED EVAL ---
    if phase > PHASE_TOTAL: phase = PHASE_TOTAL
    mg_weight = phase
    eg_weight = PHASE_TOTAL - phase
    
    score = (score_mg * mg_weight + score_eg * eg_weight) // PHASE_TOTAL
    score += TEMPO_BONUS
    
    if not white_to_move:
        score = -score
        
    return score

def evaluate(board: BoardState) -> int:
    """Wrapper calling the JIT function."""
    return int(evaluate_fast(
        board.pieces.astype(np.uint64), 
        np.uint64(board.white_occ), 
        np.uint64(board.black_occ), 
        np.uint64(board.all_occ), 
        board.white_to_move
    ))

def is_mate_score(score: int) -> bool:
    return abs(score) > MATE_SCORE - 100

def mate_in(score: int) -> int:
    if score > 0:
        return (MATE_SCORE - score + 1) // 2
    else:
        return -(MATE_SCORE + score + 1) // 2
