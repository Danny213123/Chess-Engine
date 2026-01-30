"""
Bitboard constants and helper functions for v2 engine.
"""

# Board squares
A1, B1, C1, D1, E1, F1, G1, H1 = range(8)
A2, B2, C2, D2, E2, F2, G2, H2 = range(8, 16)
A3, B3, C3, D3, E3, F3, G3, H3 = range(16, 24)
A4, B4, C4, D4, E4, F4, G4, H4 = range(24, 32)
A5, B5, C5, D5, E5, F5, G5, H5 = range(32, 40)
A6, B6, C6, D6, E6, F6, G6, H6 = range(40, 48)
A7, B7, C7, D7, E7, F7, G7, H7 = range(48, 56)
A8, B8, C8, D8, E8, F8, G8, H8 = range(56, 64)

# Square coordinate mapping
SQUARE_NAMES = [
    "a1", "b1", "c1", "d1", "e1", "f1", "g1", "h1",
    "a2", "b2", "c2", "d2", "e2", "f2", "g2", "h2",
    "a3", "b3", "c3", "d3", "e3", "f3", "g3", "h3",
    "a4", "b4", "c4", "d4", "e4", "f4", "g4", "h4",
    "a5", "b5", "c5", "d5", "e5", "f5", "g5", "h5",
    "a6", "b6", "c6", "d6", "e6", "f6", "g6", "h6",
    "a7", "b7", "c7", "d7", "e7", "f7", "g7", "h7",
    "a8", "b8", "c8", "d8", "e8", "f8", "g8", "h8",
]

# Bit manipulation functions

def set_bit(bitboard: int, square: int) -> int:
    """Set the bit at the given square index."""
    return bitboard | (1 << square)

def pop_bit(bitboard: int, square: int) -> int:
    """Clear the bit at the given square index."""
    return bitboard & ~(1 << square)

def get_bit(bitboard: int, square: int) -> int:
    """Check if the bit at the given square index is set."""
    return (bitboard >> square) & 1

def count_bits(bitboard: int) -> int:
    """Count the number of set bits (population count)."""
    return bin(bitboard).count('1')

def get_lsb_index(bitboard: int) -> int:
    """Get the index of the Least Significant Bit (LSB). Returns -1 if empty."""
    if bitboard == 0:
        return -1
    return (bitboard & -bitboard).bit_length() - 1

def print_bitboard(bitboard: int) -> None:
    """Print the bitboard in an 8x8 grid."""
    print()
    for rank in range(7, -1, -1):
        line = f"{rank + 1}  "
        for file in range(8):
            square = rank * 8 + file
            bit = 1 if (bitboard & (1 << square)) else 0
            line += f"{bit} "
        print(line)
    print("\n    a b c d e f g h")
    print(f"\n    Decimal: {bitboard}  Hex: {hex(bitboard)}\n")
