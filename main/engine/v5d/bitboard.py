"""
V4d Bitboard - Core Bitboard Operations and Constants
Following Chess Programming Wiki (CPW) specifications.

A bitboard is a 64-bit integer where each bit represents a square.
Square mapping: a1=0, b1=1, ..., h1=7, a2=8, ..., h8=63 (Little-Endian Rank-File Mapping)
"""

import numpy as np
from numba import njit, uint64, int32, int8
from numba.typed import List as NumbaList

# =============================================================================
# CONSTANTS
# =============================================================================

# Square indices (Little-Endian Rank-File Mapping)
A1, B1, C1, D1, E1, F1, G1, H1 = 0, 1, 2, 3, 4, 5, 6, 7
A2, B2, C2, D2, E2, F2, G2, H2 = 8, 9, 10, 11, 12, 13, 14, 15
A3, B3, C3, D3, E3, F3, G3, H3 = 16, 17, 18, 19, 20, 21, 22, 23
A4, B4, C4, D4, E4, F4, G4, H4 = 24, 25, 26, 27, 28, 29, 30, 31
A5, B5, C5, D5, E5, F5, G5, H5 = 32, 33, 34, 35, 36, 37, 38, 39
A6, B6, C6, D6, E6, F6, G6, H6 = 40, 41, 42, 43, 44, 45, 46, 47
A7, B7, C7, D7, E7, F7, G7, H7 = 48, 49, 50, 51, 52, 53, 54, 55
A8, B8, C8, D8, E8, F8, G8, H8 = 56, 57, 58, 59, 60, 61, 62, 63

# File masks (columns)
FILE_A = np.uint64(0x0101010101010101)
FILE_B = np.uint64(0x0202020202020202)
FILE_C = np.uint64(0x0404040404040404)
FILE_D = np.uint64(0x0808080808080808)
FILE_E = np.uint64(0x1010101010101010)
FILE_F = np.uint64(0x2020202020202020)
FILE_G = np.uint64(0x4040404040404040)
FILE_H = np.uint64(0x8080808080808080)

# Rank masks (rows)
RANK_1 = np.uint64(0x00000000000000FF)
RANK_2 = np.uint64(0x000000000000FF00)
RANK_3 = np.uint64(0x0000000000FF0000)
RANK_4 = np.uint64(0x00000000FF000000)
RANK_5 = np.uint64(0x000000FF00000000)
RANK_6 = np.uint64(0x0000FF0000000000)
RANK_7 = np.uint64(0x00FF000000000000)
RANK_8 = np.uint64(0xFF00000000000000)

# Not-file masks (for preventing wrap-around)
NOT_FILE_A = ~FILE_A
NOT_FILE_H = ~FILE_H
NOT_FILE_AB = ~(FILE_A | FILE_B)
NOT_FILE_GH = ~(FILE_G | FILE_H)

# All squares
ALL_SQUARES = np.uint64(0xFFFFFFFFFFFFFFFF)
EMPTY = np.uint64(0)

# Piece types (for indexing)
PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = 0, 1, 2, 3, 4, 5
WHITE, BLACK = 0, 1

# =============================================================================
# BITBOARD OPERATIONS (Numba JIT compiled)
# =============================================================================

@njit(cache=True)
def popcount(bb: uint64) -> int32:
    """Count the number of set bits (population count)."""
    count = 0
    while bb:
        bb &= bb - 1
        count += 1
    return count


@njit(cache=True)
def bitscan_forward(bb: uint64) -> int32:
    """Find the index of the least significant set bit (LSB)."""
    if bb == 0:
        return -1
    count = 0
    while (bb & 1) == 0:
        bb >>= 1
        count += 1
    return count


@njit(cache=True)
def bitscan_reverse(bb: uint64) -> int32:
    """Find the index of the most significant set bit (MSB)."""
    if bb == 0:
        return -1
    count = 63
    while (bb >> 63) == 0:
        bb <<= 1
        count -= 1
    return count


@njit(cache=True)
def set_bit(bb: uint64, sq: int32) -> uint64:
    """Set a bit at the given square."""
    return bb | (uint64(1) << uint64(sq))


@njit(cache=True)
def clear_bit(bb: uint64, sq: int32) -> uint64:
    """Clear a bit at the given square."""
    return bb & ~(uint64(1) << uint64(sq))


@njit(cache=True)
def get_bit(bb: uint64, sq: int32) -> uint64:
    """Get the bit at the given square (returns 0 or non-zero)."""
    return bb & (uint64(1) << uint64(sq))


@njit(cache=True)
def toggle_bit(bb: uint64, sq: int32) -> uint64:
    """Toggle a bit at the given square."""
    return bb ^ (uint64(1) << uint64(sq))


@njit(cache=True)
def pop_lsb(bb: uint64):
    """Pop the least significant bit and return (new_bb, sq)."""
    sq = bitscan_forward(bb)
    return bb & (bb - 1), sq


# Pure Python versions for use with numpy arrays (avoids overflow issues)
def set_bit_py(bb, sq):
    """Set a bit at the given square - pure Python version."""
    return np.uint64(int(bb) | (1 << sq))


def clear_bit_py(bb, sq):
    """Clear a bit at the given square - pure Python version."""
    return np.uint64(int(bb) & ~(1 << sq))


def get_bit_py(bb, sq):
    """Get the bit at the given square - pure Python version."""
    return int(bb) & (1 << sq)


# =============================================================================
# DIRECTIONAL SHIFTS
# =============================================================================

@njit(cache=True)
def north(bb: uint64) -> uint64:
    return bb << uint64(8)


@njit(cache=True)
def south(bb: uint64) -> uint64:
    return bb >> uint64(8)


@njit(cache=True)
def east(bb: uint64) -> uint64:
    return (bb << uint64(1)) & NOT_FILE_A


@njit(cache=True)
def west(bb: uint64) -> uint64:
    return (bb >> uint64(1)) & NOT_FILE_H


@njit(cache=True)
def north_east(bb: uint64) -> uint64:
    return (bb << uint64(9)) & NOT_FILE_A


@njit(cache=True)
def north_west(bb: uint64) -> uint64:
    return (bb << uint64(7)) & NOT_FILE_H


@njit(cache=True)
def south_east(bb: uint64) -> uint64:
    return (bb >> uint64(7)) & NOT_FILE_A


@njit(cache=True)
def south_west(bb: uint64) -> uint64:
    return (bb >> uint64(9)) & NOT_FILE_H


# =============================================================================
# KNIGHT ATTACKS (Precomputed)
# =============================================================================

def _init_knight_attacks():
    """Generate knight attack table for all 64 squares."""
    attacks = np.zeros(64, dtype=np.uint64)
    for sq in range(64):
        bb = np.uint64(1) << np.uint64(sq)
        attack = np.uint64(0)
        
        # All 8 knight move directions
        attack |= (bb << np.uint64(17)) & ~FILE_A  # NNE
        attack |= (bb << np.uint64(15)) & ~FILE_H  # NNW
        attack |= (bb << np.uint64(10)) & ~(FILE_A | FILE_B)  # NEE
        attack |= (bb << np.uint64(6)) & ~(FILE_G | FILE_H)   # NWW
        attack |= (bb >> np.uint64(17)) & ~FILE_H  # SSW
        attack |= (bb >> np.uint64(15)) & ~FILE_A  # SSE
        attack |= (bb >> np.uint64(10)) & ~(FILE_G | FILE_H)  # SWW
        attack |= (bb >> np.uint64(6)) & ~(FILE_A | FILE_B)   # SEE
        
        attacks[sq] = attack
    return attacks

KNIGHT_ATTACKS = _init_knight_attacks()


# =============================================================================
# KING ATTACKS (Precomputed)
# =============================================================================

def _init_king_attacks():
    """Generate king attack table for all 64 squares."""
    attacks = np.zeros(64, dtype=np.uint64)
    for sq in range(64):
        bb = np.uint64(1) << np.uint64(sq)
        attack = np.uint64(0)
        
        # All 8 directions
        attack |= north(bb)
        attack |= south(bb)
        attack |= east(bb)
        attack |= west(bb)
        attack |= north_east(bb)
        attack |= north_west(bb)
        attack |= south_east(bb)
        attack |= south_west(bb)
        
        attacks[sq] = attack
    return attacks

KING_ATTACKS = _init_king_attacks()


# =============================================================================
# PAWN ATTACKS (Precomputed)
# =============================================================================

def _init_pawn_attacks():
    """Generate pawn attack tables for white and black."""
    white_attacks = np.zeros(64, dtype=np.uint64)
    black_attacks = np.zeros(64, dtype=np.uint64)
    
    for sq in range(64):
        bb = np.uint64(1) << np.uint64(sq)
        
        # White pawns attack diagonally upward
        white_attacks[sq] = north_east(bb) | north_west(bb)
        
        # Black pawns attack diagonally downward
        black_attacks[sq] = south_east(bb) | south_west(bb)
    
    return white_attacks, black_attacks

WHITE_PAWN_ATTACKS, BLACK_PAWN_ATTACKS = _init_pawn_attacks()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

@njit(cache=True)
def square_to_coords(sq: int32):
    """Convert square index to (file, rank)."""
    return sq & 7, sq >> 3


@njit(cache=True)
def coords_to_square(file: int32, rank: int32) -> int32:
    """Convert (file, rank) to square index."""
    return rank * 8 + file


def bb_to_string(bb: np.uint64) -> str:
    """Convert bitboard to visual string representation."""
    result = ""
    for rank in range(7, -1, -1):
        for file in range(8):
            sq = rank * 8 + file
            if get_bit(bb, sq):
                result += "1 "
            else:
                result += ". "
        result += f"  {rank + 1}\n"
    result += "a b c d e f g h\n"
    return result


# =============================================================================
# ITERATOR FOR BITBOARD SQUARES
# =============================================================================

@njit(cache=True)
def iter_bits(bb: uint64):
    """Iterate over all set bits, yielding square indices. Returns array of squares."""
    squares = np.empty(64, dtype=np.int32)
    count = 0
    while bb:
        sq = bitscan_forward(bb)
        squares[count] = sq
        count += 1
        bb &= bb - 1
    return squares[:count]


def iter_bits_py(bb):
    """Pure Python version of iter_bits - works with any type."""
    bb_int = int(bb) & ((1 << 64) - 1)  # Ensure 64-bit unsigned
    squares = []
    while bb_int:
        sq = (bb_int & -bb_int).bit_length() - 1
        squares.append(sq)
        bb_int &= bb_int - 1
    return squares
