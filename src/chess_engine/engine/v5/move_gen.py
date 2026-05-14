"""
V4d Move Generation - Fast Pseudo-Legal Move Generation
Following Chess Programming Wiki (CPW) specifications.

Generates pseudo-legal moves using bitboard operations.
Pseudo-legal means all moves that "look" legal except for leaving the king in check.
Legality is verified during search when making the move.
"""

import numpy as np
from numba import njit, uint64, int32, int16
from typing import List, Tuple

from chess_engine.engine.v5.bitboard import (
    EMPTY, set_bit_py as set_bit, clear_bit_py as clear_bit, get_bit_py as get_bit,
    bitscan_forward, popcount, iter_bits_py as iter_bits,
    north, south, east, west,
    KNIGHT_ATTACKS, KING_ATTACKS, WHITE_PAWN_ATTACKS, BLACK_PAWN_ATTACKS,
    RANK_1, RANK_2, RANK_3, RANK_4, RANK_5, RANK_6, RANK_7, RANK_8,
    FILE_A, FILE_H, NOT_FILE_A, NOT_FILE_H,
    A1, B1, H1, A8, B8, H8, C1, G1, C8, G8, D1, F1, D8, F8, E1, E8
)
from chess_engine.engine.v5.magic import get_rook_attacks, get_bishop_attacks, get_queen_attacks
from chess_engine.engine.v5.board import (
    BoardState, WP, WN, WB, WR, WQ, WK, BP, BN, BB, BR, BQ, BK,
    CASTLE_WK, CASTLE_WQ, CASTLE_BK, CASTLE_BQ
)


# =============================================================================
# MOVE ENCODING
# =============================================================================
# Moves are encoded as 16-bit integers for speed:
# bits 0-5:   from square (0-63)
# bits 6-11:  to square (0-63)
# bits 12-13: promotion piece (0=none, 1=knight, 2=bishop, 3=rook, 4=queen)
# bits 14-15: special flags (0=normal, 1=castling, 2=en passant, 3=promotion)

MOVE_NORMAL = 0
MOVE_CASTLE = 1
MOVE_EP = 2
MOVE_PROMO = 3

PROMO_KNIGHT = 1
PROMO_BISHOP = 2
PROMO_ROOK = 3
PROMO_QUEEN = 4


@njit(cache=True)
def encode_move(from_sq: int, to_sq: int, promo: int = 0, flags: int = 0) -> int:
    """Encode a move as a 16-bit integer."""
    return from_sq | (to_sq << 6) | (promo << 12) | (flags << 14)


@njit(cache=True)
def decode_move(move: int):
    """Decode a move. Returns (from_sq, to_sq, promo, flags)."""
    from_sq = move & 0x3F
    to_sq = (move >> 6) & 0x3F
    promo = (move >> 12) & 0x3
    flags = (move >> 14) & 0x3
    return from_sq, to_sq, promo, flags


def move_to_string(move: int) -> str:
    """Convert move to UCI string (e.g., 'e2e4', 'e7e8q')."""
    from_sq, to_sq, promo, flags = decode_move(move)
    
    from_file = chr(ord('a') + (from_sq % 8))
    from_rank = str((from_sq // 8) + 1)
    to_file = chr(ord('a') + (to_sq % 8))
    to_rank = str((to_sq // 8) + 1)
    
    move_str = from_file + from_rank + to_file + to_rank
    
    if flags == MOVE_PROMO:
        promo_chars = ['', 'n', 'b', 'r', 'q']
        move_str += promo_chars[promo]
    
    return move_str


def string_to_move(board: BoardState, uci: str) -> int:
    """Convert UCI string to move."""
    from_file = ord(uci[0]) - ord('a')
    from_rank = int(uci[1]) - 1
    to_file = ord(uci[2]) - ord('a')
    to_rank = int(uci[3]) - 1
    
    from_sq = from_rank * 8 + from_file
    to_sq = to_rank * 8 + to_file
    
    promo = 0
    flags = MOVE_NORMAL
    
    if len(uci) > 4:
        promo_map = {'n': PROMO_KNIGHT, 'b': PROMO_BISHOP, 'r': PROMO_ROOK, 'q': PROMO_QUEEN}
        promo = promo_map.get(uci[4], 0)
        flags = MOVE_PROMO
    
    # Detect castling
    piece = board.piece_at(from_sq)
    if piece and piece[0] == 5:  # King
        if abs(from_sq - to_sq) == 2:
            flags = MOVE_CASTLE
    
    # Detect en passant
    if piece and piece[0] == 0 and to_sq == board.ep_square:  # Pawn to EP square
        flags = MOVE_EP
    
    return encode_move(from_sq, to_sq, promo, flags)


# =============================================================================
# MOVE GENERATION
# =============================================================================

def generate_moves(board: BoardState) -> np.ndarray:
    """
    Generate all pseudo-legal moves for the side to move.
    Returns a numpy array of encoded moves.
    """
    moves = []
    
    if board.white_to_move:
        _generate_white_moves(board, moves)
    else:
        _generate_black_moves(board, moves)
    
    return np.array(moves, dtype=np.int32)


def _generate_white_moves(board: BoardState, moves: list):
    """Generate all pseudo-legal moves for white."""
    
    # Pawn moves
    _generate_white_pawn_moves(board, moves)
    
    # Knight moves
    knights = board.pieces[WN]
    while knights:
        sq = bitscan_forward(knights)
        attacks = KNIGHT_ATTACKS[sq] & ~board.white_occ
        for to_sq in iter_bits(attacks):
            moves.append(encode_move(sq, to_sq))
        knights &= knights - 1
    
    # Bishop moves
    bishops = board.pieces[WB]
    while bishops:
        sq = bitscan_forward(bishops)
        attacks = get_bishop_attacks(sq, board.all_occ) & ~board.white_occ
        for to_sq in iter_bits(attacks):
            moves.append(encode_move(sq, to_sq))
        bishops &= bishops - 1
    
    # Rook moves
    rooks = board.pieces[WR]
    while rooks:
        sq = bitscan_forward(rooks)
        attacks = get_rook_attacks(sq, board.all_occ) & ~board.white_occ
        for to_sq in iter_bits(attacks):
            moves.append(encode_move(sq, to_sq))
        rooks &= rooks - 1
    
    # Queen moves
    queens = board.pieces[WQ]
    while queens:
        sq = bitscan_forward(queens)
        attacks = get_queen_attacks(sq, board.all_occ) & ~board.white_occ
        for to_sq in iter_bits(attacks):
            moves.append(encode_move(sq, to_sq))
        queens &= queens - 1
    
    # King moves
    king_sq = bitscan_forward(board.pieces[WK])
    attacks = KING_ATTACKS[king_sq] & ~board.white_occ
    for to_sq in iter_bits(attacks):
        moves.append(encode_move(king_sq, to_sq))
    
    # Castling
    _generate_white_castling(board, moves)


def _generate_black_moves(board: BoardState, moves: list):
    """Generate all pseudo-legal moves for black."""
    
    # Pawn moves
    _generate_black_pawn_moves(board, moves)
    
    # Knight moves
    knights = board.pieces[BN]
    while knights:
        sq = bitscan_forward(knights)
        attacks = KNIGHT_ATTACKS[sq] & ~board.black_occ
        for to_sq in iter_bits(attacks):
            moves.append(encode_move(sq, to_sq))
        knights &= knights - 1
    
    # Bishop moves
    bishops = board.pieces[BB]
    while bishops:
        sq = bitscan_forward(bishops)
        attacks = get_bishop_attacks(sq, board.all_occ) & ~board.black_occ
        for to_sq in iter_bits(attacks):
            moves.append(encode_move(sq, to_sq))
        bishops &= bishops - 1
    
    # Rook moves
    rooks = board.pieces[BR]
    while rooks:
        sq = bitscan_forward(rooks)
        attacks = get_rook_attacks(sq, board.all_occ) & ~board.black_occ
        for to_sq in iter_bits(attacks):
            moves.append(encode_move(sq, to_sq))
        rooks &= rooks - 1
    
    # Queen moves
    queens = board.pieces[BQ]
    while queens:
        sq = bitscan_forward(queens)
        attacks = get_queen_attacks(sq, board.all_occ) & ~board.black_occ
        for to_sq in iter_bits(attacks):
            moves.append(encode_move(sq, to_sq))
        queens &= queens - 1
    
    # King moves
    king_sq = bitscan_forward(board.pieces[BK])
    attacks = KING_ATTACKS[king_sq] & ~board.black_occ
    for to_sq in iter_bits(attacks):
        moves.append(encode_move(king_sq, to_sq))
    
    # Castling
    _generate_black_castling(board, moves)


def _generate_white_pawn_moves(board: BoardState, moves: list):
    """Generate white pawn moves."""
    pawns = board.pieces[WP]
    empty = ~board.all_occ
    enemies = board.black_occ
    
    # Single push
    single = north(pawns) & empty
    for to_sq in iter_bits(single & ~RANK_8):  # Non-promotion
        moves.append(encode_move(to_sq - 8, to_sq))
    
    # Promotions (single push to rank 8)
    for to_sq in iter_bits(single & RANK_8):
        for promo in [PROMO_QUEEN, PROMO_ROOK, PROMO_BISHOP, PROMO_KNIGHT]:
            moves.append(encode_move(to_sq - 8, to_sq, promo, MOVE_PROMO))
    
    # Double push
    double = north(single & RANK_3) & empty
    for to_sq in iter_bits(double):
        moves.append(encode_move(to_sq - 16, to_sq))
    
    # Captures
    cap_left = ((pawns << np.uint64(7)) & NOT_FILE_H) & enemies
    cap_right = ((pawns << np.uint64(9)) & NOT_FILE_A) & enemies
    
    for to_sq in iter_bits(cap_left & ~RANK_8):
        moves.append(encode_move(to_sq - 7, to_sq))
    for to_sq in iter_bits(cap_left & RANK_8):
        for promo in [PROMO_QUEEN, PROMO_ROOK, PROMO_BISHOP, PROMO_KNIGHT]:
            moves.append(encode_move(to_sq - 7, to_sq, promo, MOVE_PROMO))
    
    for to_sq in iter_bits(cap_right & ~RANK_8):
        moves.append(encode_move(to_sq - 9, to_sq))
    for to_sq in iter_bits(cap_right & RANK_8):
        for promo in [PROMO_QUEEN, PROMO_ROOK, PROMO_BISHOP, PROMO_KNIGHT]:
            moves.append(encode_move(to_sq - 9, to_sq, promo, MOVE_PROMO))
    
    # En passant
    if board.ep_square >= 0:
        ep_bb = set_bit(EMPTY, board.ep_square)
        ep_left = ((pawns << np.uint64(7)) & NOT_FILE_H) & ep_bb
        ep_right = ((pawns << np.uint64(9)) & NOT_FILE_A) & ep_bb
        
        if ep_left:
            moves.append(encode_move(board.ep_square - 7, board.ep_square, 0, MOVE_EP))
        if ep_right:
            moves.append(encode_move(board.ep_square - 9, board.ep_square, 0, MOVE_EP))


def _generate_black_pawn_moves(board: BoardState, moves: list):
    """Generate black pawn moves."""
    pawns = board.pieces[BP]
    empty = ~board.all_occ
    enemies = board.white_occ
    
    # Single push
    single = south(pawns) & empty
    for to_sq in iter_bits(single & ~RANK_1):
        moves.append(encode_move(to_sq + 8, to_sq))
    
    # Promotions
    for to_sq in iter_bits(single & RANK_1):
        for promo in [PROMO_QUEEN, PROMO_ROOK, PROMO_BISHOP, PROMO_KNIGHT]:
            moves.append(encode_move(to_sq + 8, to_sq, promo, MOVE_PROMO))
    
    # Double push
    double = south(single & RANK_6) & empty
    for to_sq in iter_bits(double):
        moves.append(encode_move(to_sq + 16, to_sq))
    
    # Captures
    cap_left = ((pawns >> np.uint64(9)) & NOT_FILE_H) & enemies
    cap_right = ((pawns >> np.uint64(7)) & NOT_FILE_A) & enemies
    
    for to_sq in iter_bits(cap_left & ~RANK_1):
        moves.append(encode_move(to_sq + 9, to_sq))
    for to_sq in iter_bits(cap_left & RANK_1):
        for promo in [PROMO_QUEEN, PROMO_ROOK, PROMO_BISHOP, PROMO_KNIGHT]:
            moves.append(encode_move(to_sq + 9, to_sq, promo, MOVE_PROMO))
    
    for to_sq in iter_bits(cap_right & ~RANK_1):
        moves.append(encode_move(to_sq + 7, to_sq))
    for to_sq in iter_bits(cap_right & RANK_1):
        for promo in [PROMO_QUEEN, PROMO_ROOK, PROMO_BISHOP, PROMO_KNIGHT]:
            moves.append(encode_move(to_sq + 7, to_sq, promo, MOVE_PROMO))
    
    # En passant
    if board.ep_square >= 0:
        ep_bb = set_bit(EMPTY, board.ep_square)
        ep_left = ((pawns >> np.uint64(9)) & NOT_FILE_H) & ep_bb
        ep_right = ((pawns >> np.uint64(7)) & NOT_FILE_A) & ep_bb
        
        if ep_left:
            moves.append(encode_move(board.ep_square + 9, board.ep_square, 0, MOVE_EP))
        if ep_right:
            moves.append(encode_move(board.ep_square + 7, board.ep_square, 0, MOVE_EP))


def _generate_white_castling(board: BoardState, moves: list):
    """Generate white castling moves."""
    if board.is_in_check():
        return
    
    # Kingside (e1-g1)
    if board.castle_rights & CASTLE_WK:
        # Squares between king and rook must be empty
        if not (board.all_occ & (set_bit(set_bit(EMPTY, F1), G1))):
            # King doesn't pass through check
            if not board.is_square_attacked(F1, by_white=False):
                if not board.is_square_attacked(G1, by_white=False):
                    moves.append(encode_move(E1, G1, 0, MOVE_CASTLE))
    
    # Queenside (e1-c1)
    if board.castle_rights & CASTLE_WQ:
        if not (board.all_occ & (set_bit(set_bit(set_bit(EMPTY, D1), C1), B1))):
            if not board.is_square_attacked(D1, by_white=False):
                if not board.is_square_attacked(C1, by_white=False):
                    moves.append(encode_move(E1, C1, 0, MOVE_CASTLE))


def _generate_black_castling(board: BoardState, moves: list):
    """Generate black castling moves."""
    if board.is_in_check():
        return
    
    # Kingside (e8-g8)
    if board.castle_rights & CASTLE_BK:
        if not (board.all_occ & (set_bit(set_bit(EMPTY, F8), G8))):
            if not board.is_square_attacked(F8, by_white=True):
                if not board.is_square_attacked(G8, by_white=True):
                    moves.append(encode_move(E8, G8, 0, MOVE_CASTLE))
    
    # Queenside (e8-c8)
    if board.castle_rights & CASTLE_BQ:
        if not (board.all_occ & (set_bit(set_bit(set_bit(EMPTY, D8), C8), B8))):
            if not board.is_square_attacked(D8, by_white=True):
                if not board.is_square_attacked(C8, by_white=True):
                    moves.append(encode_move(E8, C8, 0, MOVE_CASTLE))


# =============================================================================
# MAKE / UNMAKE MOVE
# =============================================================================

def make_move(board: BoardState, move: int) -> bool:
    """
    Make a move on the board. Returns True if legal, False if leaves king in check.
    Modifies board state in place.
    """
    from_sq, to_sq, promo, flags = decode_move(move)
    
    # Save state for undo
    state = (
        board.pieces.copy(),
        board.white_occ, board.black_occ, board.all_occ,
        board.white_to_move, board.castle_rights, board.ep_square,
        board.halfmove, board.hash
    )
    board.history.append(state)
    
    # Get piece info
    piece_info = board.piece_at(from_sq)
    if not piece_info:
        board.history.pop()
        return False
    
    piece_type, is_white = piece_info
    piece_idx = piece_type if is_white else piece_type + 6
    
    # Get captured piece (if any)
    captured_info = board.piece_at(to_sq)
    captured_idx = -1
    if captured_info:
        cap_type, cap_white = captured_info
        captured_idx = cap_type if cap_white else cap_type + 6
    
    # Update halfmove clock
    if piece_type == 0 or captured_idx >= 0:  # Pawn move or capture
        board.halfmove = 0
    else:
        board.halfmove += 1
    
    # Handle special moves
    if flags == MOVE_CASTLE:
        _make_castle(board, from_sq, to_sq, is_white)
    elif flags == MOVE_EP:
        _make_ep_capture(board, from_sq, to_sq, is_white)
    elif flags == MOVE_PROMO:
        _make_promotion(board, from_sq, to_sq, promo, is_white, captured_idx)
    else:
        _make_normal_move(board, from_sq, to_sq, piece_idx, captured_idx)
    
    # Update en passant square
    old_ep = board.ep_square
    board.ep_square = -1
    if piece_type == 0 and abs(from_sq - to_sq) == 16:  # Pawn double push
        board.ep_square = (from_sq + to_sq) // 2
    
    # Update castling rights
    _update_castling_rights(board, from_sq, to_sq, piece_type, captured_idx)
    
    # Switch side to move
    board.white_to_move = not board.white_to_move
    if not board.white_to_move:
        board.fullmove += 1
    
    # Update occupancy
    board._update_occupancy()
    
    # Check if move is legal (doesn't leave own king in check)
    if is_white:
        king_sq = bitscan_forward(board.pieces[WK])
        if board.is_square_attacked(king_sq, by_white=False):
            unmake_move(board)
            return False
    else:
        king_sq = bitscan_forward(board.pieces[BK])
        if board.is_square_attacked(king_sq, by_white=True):
            unmake_move(board)
            return False
    
    return True


def unmake_move(board: BoardState):
    """Undo the last move."""
    if not board.history:
        return
    
    state = board.history.pop()
    (board.pieces, board.white_occ, board.black_occ, board.all_occ,
     board.white_to_move, board.castle_rights, board.ep_square,
     board.halfmove, board.hash) = state
    
    if board.white_to_move:
        board.fullmove -= 1


def _make_normal_move(board: BoardState, from_sq: int, to_sq: int, piece_idx: int, captured_idx: int):
    """Make a normal (non-special) move."""
    # Remove piece from source
    board.pieces[piece_idx] = clear_bit(board.pieces[piece_idx], from_sq)
    
    # Remove captured piece (if any)
    if captured_idx >= 0:
        board.pieces[captured_idx] = clear_bit(board.pieces[captured_idx], to_sq)
    
    # Place piece at destination
    board.pieces[piece_idx] = set_bit(board.pieces[piece_idx], to_sq)


def _make_castle(board: BoardState, from_sq: int, to_sq: int, is_white: bool):
    """Make a castling move."""
    king_idx = WK if is_white else BK
    rook_idx = WR if is_white else BR
    
    # Move king
    board.pieces[king_idx] = clear_bit(board.pieces[king_idx], from_sq)
    board.pieces[king_idx] = set_bit(board.pieces[king_idx], to_sq)
    
    # Move rook
    if to_sq == G1:  # White kingside
        board.pieces[rook_idx] = clear_bit(board.pieces[rook_idx], H1)
        board.pieces[rook_idx] = set_bit(board.pieces[rook_idx], F1)
    elif to_sq == C1:  # White queenside
        board.pieces[rook_idx] = clear_bit(board.pieces[rook_idx], A1)
        board.pieces[rook_idx] = set_bit(board.pieces[rook_idx], D1)
    elif to_sq == G8:  # Black kingside
        board.pieces[rook_idx] = clear_bit(board.pieces[rook_idx], H8)
        board.pieces[rook_idx] = set_bit(board.pieces[rook_idx], F8)
    elif to_sq == C8:  # Black queenside
        board.pieces[rook_idx] = clear_bit(board.pieces[rook_idx], A8)
        board.pieces[rook_idx] = set_bit(board.pieces[rook_idx], D8)


def _make_ep_capture(board: BoardState, from_sq: int, to_sq: int, is_white: bool):
    """Make an en passant capture."""
    pawn_idx = WP if is_white else BP
    enemy_pawn_idx = BP if is_white else WP
    
    # Move capturing pawn
    board.pieces[pawn_idx] = clear_bit(board.pieces[pawn_idx], from_sq)
    board.pieces[pawn_idx] = set_bit(board.pieces[pawn_idx], to_sq)
    
    # Remove captured pawn (one rank behind ep square)
    captured_sq = to_sq - 8 if is_white else to_sq + 8
    board.pieces[enemy_pawn_idx] = clear_bit(board.pieces[enemy_pawn_idx], captured_sq)


def _make_promotion(board: BoardState, from_sq: int, to_sq: int, promo: int, is_white: bool, captured_idx: int):
    """Make a pawn promotion move."""
    pawn_idx = WP if is_white else BP
    
    # Remove pawn
    board.pieces[pawn_idx] = clear_bit(board.pieces[pawn_idx], from_sq)
    
    # Remove captured piece (if any)
    if captured_idx >= 0:
        board.pieces[captured_idx] = clear_bit(board.pieces[captured_idx], to_sq)
    
    # Add promoted piece
    promo_map = {PROMO_KNIGHT: 1, PROMO_BISHOP: 2, PROMO_ROOK: 3, PROMO_QUEEN: 4}
    promo_piece_type = promo_map.get(promo, 4)  # Default to queen
    promo_idx = promo_piece_type if is_white else promo_piece_type + 6
    board.pieces[promo_idx] = set_bit(board.pieces[promo_idx], to_sq)


def _update_castling_rights(board: BoardState, from_sq: int, to_sq: int, piece_type: int, captured_idx: int):
    """Update castling rights after a move."""
    # King moved
    if piece_type == 5:  # King
        if board.white_to_move:
            board.castle_rights &= ~(CASTLE_WK | CASTLE_WQ)
        else:
            board.castle_rights &= ~(CASTLE_BK | CASTLE_BQ)
    
    # Rook moved from starting square
    if from_sq == A1: board.castle_rights &= ~CASTLE_WQ
    if from_sq == H1: board.castle_rights &= ~CASTLE_WK
    if from_sq == A8: board.castle_rights &= ~CASTLE_BQ
    if from_sq == H8: board.castle_rights &= ~CASTLE_BK
    
    # Rook captured on starting square
    if to_sq == A1: board.castle_rights &= ~CASTLE_WQ
    if to_sq == H1: board.castle_rights &= ~CASTLE_WK
    if to_sq == A8: board.castle_rights &= ~CASTLE_BQ
    if to_sq == H8: board.castle_rights &= ~CASTLE_BK


# =============================================================================
# LEGAL MOVE GENERATION
# =============================================================================

def generate_legal_moves(board: BoardState) -> np.ndarray:
    """
    Generate all legal moves for the side to move.
    More expensive than pseudo-legal generation but guarantees legality.
    """
    pseudo_legal = generate_moves(board)
    legal_moves = []
    
    for move in pseudo_legal:
        if make_move(board, move):
            unmake_move(board)
            legal_moves.append(move)
    
    return np.array(legal_moves, dtype=np.int32)
