# V3 CPU Kernels - Numba Optimized Evaluation (No GIL)
# Enables true multi-threading on CPU

import numpy as np
import numba
from numba import int32, float32, void

# =============================================================================
# CONSTANTS (Numpy arrays for Numba)
# =============================================================================

# Piece encodings
EMPTY = 0
WP, WN, WB, WR, WQ, WK = 1, 2, 3, 4, 5, 6
BP, BN, BB, BR, BQ, BK = 7, 8, 9, 10, 11, 12

# Piece Values
PIECE_VALUES = np.array([
    0,      # Empty
    100,    # WP
    320,    # WN
    330,    # WB
    500,    # WR
    900,    # WQ
    20000,  # WK
    -100,   # BP
    -320,   # BN
    -330,   # BB
    -500,   # BR
    -900,   # BQ
    -20000  # BK
], dtype=np.int32)

# Bonuses
BISHOP_PAIR_BONUS = 50
ROOK_OPEN_FILE = 25
ROOK_SEMI_OPEN = 15
ROOK_7TH_RANK = 20
DOUBLED_PENALTY = 15
ISOLATED_PENALTY = 20
PASSED_BONUS = np.array([0, 10, 20, 40, 60, 100, 150, 0], dtype=np.int32)

# Flattened PSTs [piece_type][64]
# piece_type 0 maps to empty (zeros)
# 1-6 white, 7-12 black
PST = np.zeros((13, 64), dtype=np.int32)

def _init_tables():
    from .chess_constants import (
        pawn_table, knight_table, bishop_table, rook_table, queen_table,
        king_table_mg, king_table_mg_black
    )
    
    # Helper to flatten 8x8 list to 64-element array
    def flatten(table):
        return np.array(table, dtype=np.int32).flatten()
    
    # Helper to flip for black (mirror vertically)
    def flip(table):
        arr = np.array(table, dtype=np.int32)
        return np.flipud(arr).flatten()

    # White pieces
    PST[WP] = flatten(pawn_table)
    PST[WN] = flatten(knight_table)
    PST[WB] = flatten(bishop_table)
    PST[WR] = flatten(rook_table)
    PST[WQ] = flatten(queen_table)
    PST[WK] = flatten(king_table_mg)
    
    # Black pieces (Negate for correct sign)
    PST[BP] = -1 * flip(pawn_table)
    PST[BN] = -1 * flip(knight_table)
    PST[BB] = -1 * flip(bishop_table)
    PST[BR] = -1 * flip(rook_table)
    PST[BQ] = -1 * flip(queen_table)
    PST[BK] = -1 * flatten(king_table_mg_black) # Already flipped in constants

_init_tables()


# =============================================================================
# NUMBA KERNELS (nogil=True releases GIL)
# =============================================================================

@numba.jit(nopython=True, nogil=True)
def evaluate_board_cpu(board):
    """
    Evaluate board score from White's perspective.
    Args:
        board: 64-element int8 array with piece encodings
    """
    score = 0
    phase = 0
    
    # Piece counts
    wb_count = 0
    bb_count = 0
    
    # Pawn structures (bitmasks would be faster but arrays are easier for now)
    w_pawns_files = np.zeros(8, dtype=np.int32)
    b_pawns_files = np.zeros(8, dtype=np.int32)
    w_pawns_ranks = np.zeros((8, 8), dtype=np.int32) # file -> list of ranks (mask)
    b_pawns_ranks = np.zeros((8, 8), dtype=np.int32)
    
    # Single pass loop
    for idx in range(64):
        piece = board[idx]
        if piece == EMPTY:
            continue
            
        row = idx // 8
        col = idx % 8
        
        # 1. Material & PST
        score += PIECE_VALUES[piece]
        score += PST[piece, idx]
        
        # Phase Calculation
        if piece == WQ or piece == BQ: phase += 4
        elif piece == WR or piece == BR: phase += 2
        elif piece == WB or piece == BN or piece == WB or piece == BB: phase += 1
        
        # Piece Specifics
        if piece == WB: wb_count += 1
        if piece == BB: bb_count += 1
        
        if piece == WP:
            w_pawns_files[col] += 1
            w_pawns_ranks[col, row] = 1
        elif piece == BP:
            b_pawns_files[col] += 1
            b_pawns_ranks[col, row] = 1

    # 2. Bishop Pair
    if wb_count >= 2: score += BISHOP_PAIR_BONUS
    if bb_count >= 2: score -= BISHOP_PAIR_BONUS
    
    # 3. Pawn Structure & Rooks
    # (Simplified logic for Numba speed - implementing full logic is complex without bitboards)
    
    # Doubled Pawns
    for col in range(8):
        if w_pawns_files[col] > 1: score -= DOUBLED_PENALTY * (w_pawns_files[col] - 1)
        if b_pawns_files[col] > 1: score += DOUBLED_PENALTY * (b_pawns_files[col] - 1)
        
        # Isolated Pawns
        is_isolated_w = True
        is_isolated_b = True
        
        if col > 0:
            if w_pawns_files[col-1] > 0: is_isolated_w = False
            if b_pawns_files[col-1] > 0: is_isolated_b = False
        if col < 7:
            if w_pawns_files[col+1] > 0: is_isolated_w = False
            if b_pawns_files[col+1] > 0: is_isolated_b = False
            
        if w_pawns_files[col] > 0 and is_isolated_w: score -= ISOLATED_PENALTY
        if b_pawns_files[col] > 0 and is_isolated_b: score += ISOLATED_PENALTY
        
    return score


# =============================================================================
# WRAPPER HELPER
# =============================================================================
def board_to_cpu_format(game_state):
    """Convert GameState board to flat int32 array for Numba."""
    # This conversion overhead is unavoidable but optimized
    arr = np.zeros(64, dtype=np.int32)
    # Fast iteration
    for r in range(8):
        row_data = game_state.board[r]
        for c in range(8):
            piece = row_data[c]
            if piece != "--":
                # Manual map lookup is faster than function call
                sq = r * 8 + c
                # Map piece string to int
                # "wP" -> 1, "bP" -> 7
                if piece[0] == "w":
                    offset = 0
                else:
                    offset = 6
                
                pt = piece[1]
                if pt == "P": val = 1
                elif pt == "N": val = 2
                elif pt == "B": val = 3
                elif pt == "R": val = 4
                elif pt == "Q": val = 5
                elif pt == "K": val = 6
                else: val = 0
                
                arr[sq] = val + offset
    return arr

def score_board_fast(game_state):
    """
    Fast evaluation wrapper using Numba.
    Releases GIL for multi-threading.
    """
    board_arr = board_to_cpu_format(game_state)
    return evaluate_board_cpu(board_arr)

