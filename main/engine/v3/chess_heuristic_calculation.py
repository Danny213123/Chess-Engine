# Chess Evaluation Function - Comprehensive CPW-Based Evaluation
# Reference: https://www.chessprogramming.org/Evaluation
# Features: Material, PSTs, Pawn Structure, Mobility, Bishop Pair, Rook Placement, King Safety

from .chess_constants import (
    score_dict, piece_position,
    king_table_mg, king_table_eg,
    king_table_mg_black, king_table_eg_black
)

# =============================================================================
# EVALUATION BONUSES (in centipawns)
# =============================================================================
BISHOP_PAIR_BONUS = 50
ROOK_OPEN_FILE_BONUS = 25
ROOK_SEMI_OPEN_BONUS = 15
ROOK_SEVENTH_RANK_BONUS = 20
KNIGHT_OUTPOST_BONUS = 30
DOUBLED_PAWN_PENALTY = -15
ISOLATED_PAWN_PENALTY = -20
PASSED_PAWN_BONUS = [0, 10, 20, 40, 60, 100, 150, 0]  # By rank (0=unused, 1-7 for actual ranks)
MOBILITY_WEIGHT = 4  # centipawns per legal move

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def get_game_phase(game_state):
    """
    Determine game phase based on material.
    Returns a value from 0 (endgame) to 256 (opening/middlegame).
    """
    phase = 0
    for row in game_state.board:
        for square in row:
            if square == "--":
                continue
            piece_type = square[1]
            if piece_type == "Q":
                phase += 4
            elif piece_type == "R":
                phase += 2
            elif piece_type in ("B", "N"):
                phase += 1
    
    phase = min(phase, 24)
    return (phase * 256 + 12) // 24


def count_pieces(game_state):
    """Count pieces by type and color."""
    counts = {
        "wP": 0, "wN": 0, "wB": 0, "wR": 0, "wQ": 0, "wK": 0,
        "bP": 0, "bN": 0, "bB": 0, "bR": 0, "bQ": 0, "bK": 0,
    }
    positions = {k: [] for k in counts}
    
    for row in range(8):
        for col in range(8):
            piece = game_state.board[row][col]
            if piece != "--":
                counts[piece] = counts.get(piece, 0) + 1
                positions[piece].append((row, col))
    
    return counts, positions


def get_pawn_files(game_state):
    """Get files with pawns for each color."""
    white_pawn_files = set()
    black_pawn_files = set()
    white_pawn_ranks = {}  # file -> list of ranks
    black_pawn_ranks = {}
    
    for row in range(8):
        for col in range(8):
            piece = game_state.board[row][col]
            if piece == "wP":
                white_pawn_files.add(col)
                if col not in white_pawn_ranks:
                    white_pawn_ranks[col] = []
                white_pawn_ranks[col].append(row)
            elif piece == "bP":
                black_pawn_files.add(col)
                if col not in black_pawn_ranks:
                    black_pawn_ranks[col] = []
                black_pawn_ranks[col].append(row)
    
    return white_pawn_files, black_pawn_files, white_pawn_ranks, black_pawn_ranks


# =============================================================================
# EVALUATION FEATURES
# =============================================================================
def evaluate_bishop_pair(counts):
    """Bonus for having both bishops."""
    score = 0
    if counts["wB"] >= 2:
        score += BISHOP_PAIR_BONUS
    if counts["bB"] >= 2:
        score -= BISHOP_PAIR_BONUS
    return score


def evaluate_rooks(game_state, white_pawn_files, black_pawn_files):
    """Evaluate rook placement: open files, 7th rank."""
    score = 0
    
    for row in range(8):
        for col in range(8):
            piece = game_state.board[row][col]
            
            if piece == "wR":
                # Open file: no pawns of either color
                if col not in white_pawn_files and col not in black_pawn_files:
                    score += ROOK_OPEN_FILE_BONUS
                # Semi-open: no friendly pawns
                elif col not in white_pawn_files:
                    score += ROOK_SEMI_OPEN_BONUS
                # 7th rank bonus
                if row == 1:  # 7th rank for white
                    score += ROOK_SEVENTH_RANK_BONUS
                    
            elif piece == "bR":
                if col not in white_pawn_files and col not in black_pawn_files:
                    score -= ROOK_OPEN_FILE_BONUS
                elif col not in black_pawn_files:
                    score -= ROOK_SEMI_OPEN_BONUS
                if row == 6:  # 7th rank for black (2nd rank from white's view)
                    score -= ROOK_SEVENTH_RANK_BONUS
    
    return score


def evaluate_pawn_structure(white_pawn_ranks, black_pawn_ranks, white_pawn_files, black_pawn_files):
    """Evaluate pawn structure: doubled, isolated, passed pawns."""
    score = 0
    
    # Doubled pawns
    for file_col, ranks in white_pawn_ranks.items():
        if len(ranks) > 1:
            score += DOUBLED_PAWN_PENALTY * (len(ranks) - 1)
    
    for file_col, ranks in black_pawn_ranks.items():
        if len(ranks) > 1:
            score -= DOUBLED_PAWN_PENALTY * (len(ranks) - 1)
    
    # Isolated pawns (no friendly pawns on adjacent files)
    for col in white_pawn_files:
        adjacent = set()
        if col > 0:
            adjacent.add(col - 1)
        if col < 7:
            adjacent.add(col + 1)
        if not adjacent.intersection(white_pawn_files):
            score += ISOLATED_PAWN_PENALTY
    
    for col in black_pawn_files:
        adjacent = set()
        if col > 0:
            adjacent.add(col - 1)
        if col < 7:
            adjacent.add(col + 1)
        if not adjacent.intersection(black_pawn_files):
            score -= ISOLATED_PAWN_PENALTY
    
    # Passed pawns (no enemy pawns in front or adjacent)
    for col, ranks in white_pawn_ranks.items():
        for row in ranks:
            is_passed = True
            # Check files col-1, col, col+1 for any black pawns ahead
            for check_col in range(max(0, col - 1), min(8, col + 2)):
                for check_row in range(0, row):  # Rows in front
                    if check_col in black_pawn_ranks and check_row in black_pawn_ranks.get(check_col, []):
                        is_passed = False
                        break
                    # Direct check on board
                    if black_pawn_ranks.get(check_col):
                        for bpr in black_pawn_ranks[check_col]:
                            if bpr < row:
                                is_passed = False
                                break
            if is_passed:
                # Rank bonus: closer to promotion = higher bonus
                # row 6 = rank 2 (just moved), row 1 = rank 7 (about to promote)
                rank_from_promo = row  # 0 = about to promote, 6 = just started
                pawn_rank = 7 - row  # Convert to 1-7 scale
                if pawn_rank < len(PASSED_PAWN_BONUS):
                    score += PASSED_PAWN_BONUS[pawn_rank]
    
    for col, ranks in black_pawn_ranks.items():
        for row in ranks:
            is_passed = True
            for check_col in range(max(0, col - 1), min(8, col + 2)):
                if white_pawn_ranks.get(check_col):
                    for wpr in white_pawn_ranks[check_col]:
                        if wpr > row:
                            is_passed = False
                            break
            if is_passed:
                pawn_rank = row  # For black, row 6 = rank 2
                if pawn_rank < len(PASSED_PAWN_BONUS):
                    score -= PASSED_PAWN_BONUS[pawn_rank]
    
    return score


def evaluate_mobility(game_state):
    """
    Approximate mobility based on piece placement.
    Full legal move generation is expensive, so use heuristics.
    """
    score = 0
    
    # Knight mobility: penalty for edge knights
    for row in range(8):
        for col in range(8):
            piece = game_state.board[row][col]
            if piece == "wN":
                # Edge penalty
                if row == 0 or row == 7 or col == 0 or col == 7:
                    score -= 10
                # Corner is worst
                if (row in [0, 7]) and (col in [0, 7]):
                    score -= 15
            elif piece == "bN":
                if row == 0 or row == 7 or col == 0 or col == 7:
                    score += 10
                if (row in [0, 7]) and (col in [0, 7]):
                    score += 15
    
    return score


def evaluate_king_safety(game_state, phase):
    """
    King safety in middlegame: bonus for castled king with pawn shield.
    """
    if phase < 128:  # Endgame - king safety less important
        return 0
    
    score = 0
    
    # Find kings
    wk_pos = game_state.white_king
    bk_pos = game_state.black_king
    
    # White king safety
    wk_row, wk_col = wk_pos
    if wk_row == 7:  # King on back rank
        # Check pawn shield
        pawns_in_front = 0
        for col in range(max(0, wk_col - 1), min(8, wk_col + 2)):
            if wk_row > 0 and game_state.board[wk_row - 1][col] == "wP":
                pawns_in_front += 1
        score += pawns_in_front * 15
        
        # Castled king bonus
        if wk_col in [6, 7]:  # Kingside castle
            score += 20
        elif wk_col in [0, 1, 2]:  # Queenside castle
            score += 15
    
    # Black king safety
    bk_row, bk_col = bk_pos
    if bk_row == 0:
        pawns_in_front = 0
        for col in range(max(0, bk_col - 1), min(8, bk_col + 2)):
            if bk_row < 7 and game_state.board[bk_row + 1][col] == "bP":
                pawns_in_front += 1
        score -= pawns_in_front * 15
        
        if bk_col in [6, 7]:
            score -= 20
        elif bk_col in [0, 1, 2]:
            score -= 15
    
    return score


# =============================================================================
# MAIN EVALUATION FUNCTION
# =============================================================================
def score_board(game_state):
    """
    Comprehensive board evaluation using:
    - Material count (centipawns)
    - Piece-square tables
    - Pawn structure (doubled, isolated, passed)
    - Bishop pair bonus
    - Rook on open/semi-open files
    - King safety (pawn shield)
    - Tapered evaluation
    
    Returns score from White's perspective (positive = White better).
    """
    # Check for checkmate/stalemate
    if game_state.check_mate:
        if game_state.white:
            return -99999
        else:
            return 99999
    
    if game_state.stale_mate:
        return 0

    # Get game phase
    phase = get_game_phase(game_state)
    
    # Count pieces and get positions
    counts, positions = count_pieces(game_state)
    
    # Get pawn files
    white_pawn_files, black_pawn_files, white_pawn_ranks, black_pawn_ranks = get_pawn_files(game_state)
    
    mg_score = 0
    eg_score = 0

    # Material and PST evaluation
    for row in range(8):
        for col in range(8):
            square = game_state.board[row][col]
            if square == "--":
                continue

            color = square[0]
            piece_type = square[1]
            multiplier = 1 if color == "w" else -1

            # Material value
            material = score_dict.get(piece_type, 0)
            mg_score += multiplier * material
            eg_score += multiplier * material

            # PST bonus
            if piece_type == "K":
                if color == "w":
                    mg_pst = king_table_mg[row][col]
                    eg_pst = king_table_eg[row][col]
                else:
                    mg_pst = king_table_mg_black[row][col]
                    eg_pst = king_table_eg_black[row][col]
                mg_score += multiplier * mg_pst
                eg_score += multiplier * eg_pst
            elif piece_type == "P":
                pst_key = f"{color}P"
                if pst_key in piece_position:
                    pst_value = piece_position[pst_key][row][col]
                    mg_score += multiplier * pst_value
                    eg_score += multiplier * pst_value
            else:
                if piece_type in piece_position:
                    lookup_row = row if color == "w" else (7 - row)
                    pst_value = piece_position[piece_type][lookup_row][col]
                    mg_score += multiplier * pst_value
                    eg_score += multiplier * pst_value

    # Tapered base score
    base_score = ((mg_score * phase) + (eg_score * (256 - phase))) // 256
    
    # Add positional bonuses
    positional_score = 0
    positional_score += evaluate_bishop_pair(counts)
    positional_score += evaluate_rooks(game_state, white_pawn_files, black_pawn_files)
    positional_score += evaluate_pawn_structure(white_pawn_ranks, black_pawn_ranks, white_pawn_files, black_pawn_files)
    positional_score += evaluate_mobility(game_state)
    positional_score += evaluate_king_safety(game_state, phase)

    return base_score + positional_score