"""
Pre-calculated attack tables for v2 engine (Leaper pieces).
"""
from .bitboard_helpers import *

# Attack tables
# [color][square] -> bitboard
pawn_attacks = [[0] * 64 for _ in range(2)]

# [square] -> bitboard
knight_attacks = [0] * 64
king_attacks = [0] * 64

def mask_pawn_attacks(side: int, square: int) -> int:
    """
    Generate pawn attacks for a single square.
    side: 0 = White, 1 = Black
    """
    attacks = 0
    bitboard = 0
    bitboard = set_bit(bitboard, square)

    # White pawns (move "up" board, index decreases if A1=0 at bottom... wait)
    # Standard mapping: A1=0 (bottom left), H1=7, A8=56, H8=63
    # White moves +8 (North). Attacks +7 (NW), +9 (NE)
    # Black moves -8 (South). Attacks -7 (SE), -9 (SW)
    
    if side == 0: # White
        # Attack North West (index + 7), verify not on H file (file 7) to avoid wrapping? 
        # Actually if on A file (0), -1 is invalid?
        # Let's check files.
        # file = square % 8
        # NE = square + 9. If file != 7 (H-file)
        # NW = square + 7. If file != 0 (A-file)
        
        if (bitboard >> 7) & 1: pass # Logic error in thought, let's use math
        
        # Capture Right (North East)
        if ((bitboard << 9) & 0xFEFEFEFEFEFEFEFE) : # overflow check implicitly handled? 
             pass 

    # Reworking logic to be explicit with coordinates
    rank = square // 8
    file = square % 8
    
    if side == 0: # White
        if rank < 7:
            if file > 0: attacks |= (1 << (square + 7)) # Capture Left (NW)
            if file < 7: attacks |= (1 << (square + 9)) # Capture Right (NE)
    else: # Black
        if rank > 0:
            if file > 0: attacks |= (1 << (square - 9)) # Capture Left (SW) - from black perspective?
            # White perspective:
            # Black pawn on d5 (35). Attacks c4 (26) and e4 (28).
            # 35 - 9 = 26. 35 - 7 = 28.
            if file > 0: attacks |= (1 << (square - 9)) # Capture Right (from white persp) - SW
            if file < 7: attacks |= (1 << (square - 7)) # Capture Left (from white persp) - SE
            
    return attacks

def mask_knight_attacks(square: int) -> int:
    attacks = 0
    bitboard = 0
    bitboard = set_bit(bitboard, square)
    
    rank = square // 8
    file = square % 8
    
    # NNE (+17), NNW (+15), ENE (+10), WNW (+6) etc..
    # Using explicit coordinates to prevent wrapping errors
    moves = [
        (rank + 2, file + 1), (rank + 2, file - 1),
        (rank - 2, file + 1), (rank - 2, file - 1),
        (rank + 1, file + 2), (rank + 1, file - 2),
        (rank - 1, file + 2), (rank - 1, file - 2)
    ]
    
    for r, f in moves:
        if 0 <= r <= 7 and 0 <= f <= 7:
            attacks |= (1 << (r * 8 + f))
            
    return attacks

def mask_king_attacks(square: int) -> int:
    attacks = 0
    rank = square // 8
    file = square % 8
    
    moves = [
        (rank + 1, file), (rank - 1, file),
        (rank, file + 1), (rank, file - 1),
        (rank + 1, file + 1), (rank + 1, file - 1),
        (rank - 1, file + 1), (rank - 1, file - 1)
    ]
    
    for r, f in moves:
        if 0 <= r <= 7 and 0 <= f <= 7:
            attacks |= (1 << (r * 8 + f))
            
    return attacks

def init_leaper_attacks():
    """Initialize arrays for pawn, knight, and king attacks."""
    for square in range(64):
        pawn_attacks[0][square] = mask_pawn_attacks(0, square)
        pawn_attacks[1][square] = mask_pawn_attacks(1, square)
        
        knight_attacks[square] = mask_knight_attacks(square)
        king_attacks[square] = mask_king_attacks(square)

# Initializing Sliding Attacks (On-the-fly for now, or precomputed magic candidates)
# For simplicity in this iteration, we will use a "Hyperbola Quintessence" or classical ray approach
# But simply iterating is safest to verify logic first.

def get_rook_attacks(square: int, occupancy: int) -> int:
    """
    Generate rook attacks on the fly.
    """
    attacks = 0
    rank = square // 8
    file = square % 8
    
    # North
    for r in range(rank + 1, 8):
        sq = r * 8 + file
        attacks |= (1 << sq)
        if (occupancy >> sq) & 1: break
        
    # South
    for r in range(rank - 1, -1, -1):
        sq = r * 8 + file
        attacks |= (1 << sq)
        if (occupancy >> sq) & 1: break
        
    # East
    for f in range(file + 1, 8):
        sq = rank * 8 + f
        attacks |= (1 << sq)
        if (occupancy >> sq) & 1: break
        
    # West
    for f in range(file - 1, -1, -1):
        sq = rank * 8 + f
        attacks |= (1 << sq)
        if (occupancy >> sq) & 1: break
        
    return attacks

def get_bishop_attacks(square: int, occupancy: int) -> int:
    """
    Generate bishop attacks on the fly.
    """
    attacks = 0
    rank = square // 8
    file = square % 8
    
    # NE
    for r, f in zip(range(rank + 1, 8), range(file + 1, 8)):
        sq = r * 8 + f
        attacks |= (1 << sq)
        if (occupancy >> sq) & 1: break

    # NW
    for r, f in zip(range(rank + 1, 8), range(file - 1, -1, -1)):
        sq = r * 8 + f
        attacks |= (1 << sq)
        if (occupancy >> sq) & 1: break

    # SE
    for r, f in zip(range(rank - 1, -1, -1), range(file + 1, 8)):
        sq = r * 8 + f
        attacks |= (1 << sq)
        if (occupancy >> sq) & 1: break

    # SW
    for r, f in zip(range(rank - 1, -1, -1), range(file - 1, -1, -1)):
        sq = r * 8 + f
        attacks |= (1 << sq)
        if (occupancy >> sq) & 1: break
        
    return attacks

def get_queen_attacks(square: int, occupancy: int) -> int:
    return get_rook_attacks(square, occupancy) | get_bishop_attacks(square, occupancy)

# Initialize on import
init_leaper_attacks()
