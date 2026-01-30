# Chess Constants - CPW Simplified Evaluation Function
# Values in centipawns (1 pawn = 100)
# Reference: https://www.chessprogramming.org/Simplified_Evaluation_Function

piece_to_glyph = {
    "wP": "♙", "bP": "♟︎",
    "wR": "♖", "bR": "♜",
    "wN": "♘", "bN": "♞",
    "wB": "♗", "bB": "♝",
    "wQ": "♕", "bQ": "♛",
    "wK": "♔", "bK": "♚",
}

# Piece values in centipawns (CPW standard)
score_dict = {
    "P": 100,
    "N": 320,
    "B": 330,
    "R": 500,
    "Q": 900,
    "K": 20000  # High value to prevent king trades
}

# ============================================================================
# PIECE-SQUARE TABLES (from White's perspective, row 0 = rank 8)
# For Black, we flip the table vertically.
# ============================================================================

# Pawn PST: Encourage central advance, discourage d2/e2 pawns
pawn_table = [
    [  0,   0,   0,   0,   0,   0,   0,   0],  # Rank 8 (promotion)
    [ 50,  50,  50,  50,  50,  50,  50,  50],  # Rank 7
    [ 10,  10,  20,  30,  30,  20,  10,  10],  # Rank 6
    [  5,   5,  10,  25,  25,  10,   5,   5],  # Rank 5
    [  0,   0,   0,  20,  20,   0,   0,   0],  # Rank 4
    [  5,  -5, -10,   0,   0, -10,  -5,   5],  # Rank 3
    [  5,  10,  10, -20, -20,  10,  10,   5],  # Rank 2
    [  0,   0,   0,   0,   0,   0,   0,   0],  # Rank 1
]

# Knight PST: Strong center, terrible on edges
knight_table = [
    [-50, -40, -30, -30, -30, -30, -40, -50],
    [-40, -20,   0,   0,   0,   0, -20, -40],
    [-30,   0,  10,  15,  15,  10,   0, -30],
    [-30,   5,  15,  20,  20,  15,   5, -30],
    [-30,   0,  15,  20,  20,  15,   0, -30],
    [-30,   5,  10,  15,  15,  10,   5, -30],
    [-40, -20,   0,   5,   5,   0, -20, -40],
    [-50, -40, -30, -30, -30, -30, -40, -50],
]

# Bishop PST: Avoid edges, prefer diagonals
bishop_table = [
    [-20, -10, -10, -10, -10, -10, -10, -20],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-10,   0,   5,  10,  10,   5,   0, -10],
    [-10,   5,   5,  10,  10,   5,   5, -10],
    [-10,   0,  10,  10,  10,  10,   0, -10],
    [-10,  10,  10,  10,  10,  10,  10, -10],
    [-10,   5,   0,   0,   0,   0,   5, -10],
    [-20, -10, -10, -10, -10, -10, -10, -20],
]

# Rook PST: 7th rank bonus, centralize
rook_table = [
    [  0,   0,   0,   0,   0,   0,   0,   0],
    [  5,  10,  10,  10,  10,  10,  10,   5],  # 7th rank bonus
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [  0,   0,   0,   5,   5,   0,   0,   0],  # Central files
]

# Queen PST: Avoid early development, centralize
queen_table = [
    [-20, -10, -10,  -5,  -5, -10, -10, -20],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-10,   0,   5,   5,   5,   5,   0, -10],
    [ -5,   0,   5,   5,   5,   5,   0,  -5],
    [  0,   0,   5,   5,   5,   5,   0,  -5],
    [-10,   5,   5,   5,   5,   5,   0, -10],
    [-10,   0,   5,   0,   0,   0,   0, -10],
    [-20, -10, -10,  -5,  -5, -10, -10, -20],
]

# King Middlegame PST: Stay behind pawn shelter
king_middlegame_table = [
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-20, -30, -30, -40, -40, -30, -30, -20],
    [-10, -20, -20, -20, -20, -20, -20, -10],
    [ 20,  20,   0,   0,   0,   0,  20,  20],  # Castled king bonus
    [ 20,  30,  10,   0,   0,  10,  30,  20],  # Castle squares
]

# King Endgame PST: Centralize!
king_endgame_table = [
    [-50, -40, -30, -20, -20, -30, -40, -50],
    [-30, -20, -10,   0,   0, -10, -20, -30],
    [-30, -10,  20,  30,  30,  20, -10, -30],
    [-30, -10,  30,  40,  40,  30, -10, -30],
    [-30, -10,  30,  40,  40,  30, -10, -30],
    [-30, -10,  20,  30,  30,  20, -10, -30],
    [-30, -30,   0,   0,   0,   0, -30, -30],
    [-50, -30, -30, -30, -30, -30, -30, -50],
]

# Mapping for piece-square tables (used by evaluation)
# Note: We use separate white/black pawn tables for simplicity
piece_position = {
    "N": knight_table,
    "B": bishop_table,
    "R": rook_table,
    "Q": queen_table,
    # Pawns need color-specific flipping
    "wP": pawn_table,
    "bP": [[pawn_table[7-r][c] for c in range(8)] for r in range(8)],  # Flipped for black
}

# King tables (middlegame by default, endgame handled in evaluation)
king_table_mg = king_middlegame_table
king_table_eg = king_endgame_table

# Flipped versions for black
king_table_mg_black = [[king_middlegame_table[7-r][c] for c in range(8)] for r in range(8)]
king_table_eg_black = [[king_endgame_table[7-r][c] for c in range(8)] for r in range(8)]

# ============================================================================
# LEGACY COMPATIBILITY (old variable names) - kept for backwards compatibility
# ============================================================================
knight_score = knight_table
bishop_score = bishop_table
rook_score = rook_table
queen_score = queen_table
white_pawn_score = pawn_table
black_pawn_score = [[pawn_table[7-r][c] for c in range(8)] for r in range(8)]
