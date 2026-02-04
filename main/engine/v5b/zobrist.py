"""
V4d Zobrist Hashing - Incremental Position Hashing
Following Chess Programming Wiki (CPW) specifications.

Zobrist hashing uses XOR of random 64-bit numbers to create a nearly-unique
hash for each position. The key property is that the hash can be incrementally
updated when making/unmaking moves (just XOR the changes).
"""

import numpy as np
from numba import njit, uint64

# =============================================================================
# ZOBRIST KEY TABLES
# =============================================================================

# Use a fixed seed for reproducibility
np.random.seed(42)

# Random keys for each piece on each square (12 piece types x 64 squares)
# Index: [piece_type * 2 + color][square]
# Piece order: Pawn, Knight, Bishop, Rook, Queen, King
PIECE_KEYS = np.random.randint(0, 2**63, size=(12, 64), dtype=np.uint64)

# Side to move key
SIDE_KEY = np.random.randint(0, 2**63, dtype=np.uint64)

# Castling rights keys (4 bits: KQkq)
CASTLE_KEYS = np.random.randint(0, 2**63, size=16, dtype=np.uint64)

# En passant file keys (8 files, 0 = no en passant)
EP_KEYS = np.random.randint(0, 2**63, size=9, dtype=np.uint64)  # Index 0 = none, 1-8 = files a-h


# =============================================================================
# PIECE TYPE INDEXING
# =============================================================================

# Piece to index mapping
# White pieces: 0-5, Black pieces: 6-11
PAWN_W, KNIGHT_W, BISHOP_W, ROOK_W, QUEEN_W, KING_W = 0, 1, 2, 3, 4, 5
PAWN_B, KNIGHT_B, BISHOP_B, ROOK_B, QUEEN_B, KING_B = 6, 7, 8, 9, 10, 11


@njit(cache=True)
def piece_index(piece_type: int, is_white: bool) -> int:
    """Get the Zobrist index for a piece type and color."""
    return piece_type if is_white else piece_type + 6


# =============================================================================
# HASH COMPUTATION
# =============================================================================

@njit(cache=True)
def hash_piece(key: uint64, piece_idx: int, square: int) -> uint64:
    """Toggle a piece on/off in the hash (XOR is its own inverse)."""
    return key ^ PIECE_KEYS[piece_idx, square]


@njit(cache=True)
def hash_castle(key: uint64, castle_rights: int) -> uint64:
    """Update hash for castling rights."""
    return key ^ CASTLE_KEYS[castle_rights]


@njit(cache=True)
def hash_ep(key: uint64, ep_file: int) -> uint64:
    """Update hash for en passant file (0 = none, 1-8 = files a-h)."""
    return key ^ EP_KEYS[ep_file]


@njit(cache=True)
def hash_side(key: uint64) -> uint64:
    """Toggle side to move in the hash."""
    return key ^ SIDE_KEY


# =============================================================================
# FULL POSITION HASHING
# =============================================================================

def compute_hash(piece_bbs, white_pieces, black_pieces, white_to_move, castle_rights, ep_file):
    """
    Compute the full Zobrist hash for a position.
    
    Args:
        piece_bbs: 12 bitboards (one per piece type: wP, wN, wB, wR, wQ, wK, bP, bN, bB, bR, bQ, bK)
        white_to_move: True if white to move
        castle_rights: 4-bit integer (KQkq)
        ep_file: 0 if none, 1-8 for files a-h
    
    Returns:
        64-bit Zobrist hash
    """
    key = np.uint64(0)
    
    # Hash all pieces
    for piece_idx in range(12):
        bb = piece_bbs[piece_idx]
        while bb:
            sq = int(np.log2(bb & -bb))  # Find LSB
            key ^= PIECE_KEYS[piece_idx, sq]
            bb &= bb - 1  # Clear LSB
    
    # Hash side to move
    if white_to_move:
        key ^= SIDE_KEY
    
    # Hash castling rights
    key ^= CASTLE_KEYS[castle_rights]
    
    # Hash en passant
    key ^= EP_KEYS[ep_file]
    
    return key


# =============================================================================
# INCREMENTAL HASH UPDATES
# =============================================================================

@njit(cache=True)
def update_hash_move(
    key: uint64,
    from_sq: int,
    to_sq: int,
    piece_idx: int,
    captured_idx: int,  # -1 if no capture
    old_castle: int,
    new_castle: int,
    old_ep: int,
    new_ep: int
) -> uint64:
    """
    Incrementally update hash for a move.
    Much faster than recomputing the full hash.
    """
    # Remove piece from source square
    key ^= PIECE_KEYS[piece_idx, from_sq]
    
    # Add piece to destination square
    key ^= PIECE_KEYS[piece_idx, to_sq]
    
    # Handle capture
    if captured_idx >= 0:
        key ^= PIECE_KEYS[captured_idx, to_sq]
    
    # Update castling rights if changed
    if old_castle != new_castle:
        key ^= CASTLE_KEYS[old_castle]
        key ^= CASTLE_KEYS[new_castle]
    
    # Update en passant if changed
    if old_ep != new_ep:
        key ^= EP_KEYS[old_ep]
        key ^= EP_KEYS[new_ep]
    
    # Toggle side to move
    key ^= SIDE_KEY
    
    return key


@njit(cache=True)
def update_hash_castle(
    key: uint64,
    king_from: int,
    king_to: int,
    rook_from: int,
    rook_to: int,
    king_idx: int,
    rook_idx: int,
    old_castle: int,
    new_castle: int
) -> uint64:
    """Update hash for castling move."""
    # Move king
    key ^= PIECE_KEYS[king_idx, king_from]
    key ^= PIECE_KEYS[king_idx, king_to]
    
    # Move rook
    key ^= PIECE_KEYS[rook_idx, rook_from]
    key ^= PIECE_KEYS[rook_idx, rook_to]
    
    # Update castling rights
    key ^= CASTLE_KEYS[old_castle]
    key ^= CASTLE_KEYS[new_castle]
    
    # Toggle side
    key ^= SIDE_KEY
    
    return key


@njit(cache=True)
def update_hash_ep_capture(
    key: uint64,
    from_sq: int,
    to_sq: int,
    captured_sq: int,
    pawn_idx: int,
    captured_pawn_idx: int,
    old_ep: int
) -> uint64:
    """Update hash for en passant capture."""
    # Move capturing pawn
    key ^= PIECE_KEYS[pawn_idx, from_sq]
    key ^= PIECE_KEYS[pawn_idx, to_sq]
    
    # Remove captured pawn (different square than to_sq)
    key ^= PIECE_KEYS[captured_pawn_idx, captured_sq]
    
    # Clear en passant
    key ^= EP_KEYS[old_ep]
    key ^= EP_KEYS[0]
    
    # Toggle side
    key ^= SIDE_KEY
    
    return key


@njit(cache=True)
def update_hash_promotion(
    key: uint64,
    from_sq: int,
    to_sq: int,
    pawn_idx: int,
    promoted_idx: int,
    captured_idx: int,  # -1 if no capture
    old_castle: int,
    new_castle: int
) -> uint64:
    """Update hash for pawn promotion."""
    # Remove pawn
    key ^= PIECE_KEYS[pawn_idx, from_sq]
    
    # Add promoted piece
    key ^= PIECE_KEYS[promoted_idx, to_sq]
    
    # Handle capture
    if captured_idx >= 0:
        key ^= PIECE_KEYS[captured_idx, to_sq]
    
    # Update castling if needed
    if old_castle != new_castle:
        key ^= CASTLE_KEYS[old_castle]
        key ^= CASTLE_KEYS[new_castle]
    
    # Toggle side
    key ^= SIDE_KEY
    
    return key
