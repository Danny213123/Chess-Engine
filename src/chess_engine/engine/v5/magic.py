"""
V4d Magic Bitboards - O(1) Sliding Piece Attack Generation
Following Chess Programming Wiki (CPW) specifications.

Magic bitboards use a perfect hash function to map blocker configurations
to precomputed attack bitboards. This gives O(1) attack lookups.

The "magic" is a carefully chosen number that, when multiplied with the
blocker bitboard, produces a unique index for each possible configuration.
"""

import numpy as np
from numba import njit, uint64, int32
from chess_engine.engine.v5.bitboard import (
    FILE_A, FILE_H, RANK_1, RANK_8,
    set_bit, get_bit, bitscan_forward, popcount
)

# =============================================================================
# MAGIC NUMBERS (Pre-computed, these are known good values)
# =============================================================================

# Rook magic numbers (one per square)
ROOK_MAGICS = np.array([
    0x8a80104000800020, 0x140002000100040, 0x2801880a0017001, 0x100081001000420,
    0x200020010080420, 0x3001c0002010008, 0x8480008002000100, 0x2080088004402900,
    0x800098204000, 0x2024401000200040, 0x100802000801000, 0x120800800801000,
    0x208808088000400, 0x2802200800400, 0x2200800100020080, 0x801000060821100,
    0x80044006422000, 0x100808020004000, 0x12108a0010204200, 0x140848010000802,
    0x481828014002800, 0x8094004002004100, 0x4010040010010802, 0x20008806104,
    0x100400080208000, 0x2040002120081000, 0x21200680100081, 0x20100080080080,
    0x2000a00200410, 0x20080800400, 0x80088400100102, 0x80004600042881,
    0x4040008040800020, 0x440003000200801, 0x4200011004500, 0x188020010100100,
    0x14800401802800, 0x2080040080800200, 0x124080204001001, 0x200046502000484,
    0x480400080088020, 0x1000422010034000, 0x30200100110040, 0x100021010009,
    0x2002080100110004, 0x202008004008002, 0x20020004010100, 0x2048440040820001,
    0x101002200408200, 0x40802000401080, 0x4008142004410100, 0x2060820c0120200,
    0x1001004080100, 0x20c020080040080, 0x2935610830022400, 0x44440041009200,
    0x280001040802101, 0x2100190040002085, 0x80c0084100102001, 0x4024081001000421,
    0x20030a0244872, 0x12001008414402, 0x2006104900a0804, 0x1004081002402
], dtype=np.uint64)

# Bishop magic numbers (one per square)
BISHOP_MAGICS = np.array([
    0x40040844404084, 0x2004208a004208, 0x10190041080202, 0x108060845042010,
    0x581104180800210, 0x2112080446200010, 0x1080820820060210, 0x3c0808410220200,
    0x4050404440404, 0x21001420088, 0x24d0080801082102, 0x1020a0a020400,
    0x40308200402, 0x4011002100800, 0x401484104104005, 0x801010402020200,
    0x400210c3880100, 0x404022024108200, 0x810018200204102, 0x4002801a02003,
    0x85040820080400, 0x810102c808880400, 0xe900410884800, 0x8002020480840102,
    0x220200865090201, 0x2010100a02021202, 0x152048408022401, 0x20080002081110,
    0x4001001021004000, 0x800040400a011002, 0xe4004081011002, 0x1c004001012080,
    0x8004200962a00220, 0x8422100208500202, 0x2000402200300c08, 0x8646020080080080,
    0x80020a0200100808, 0x2010004880111000, 0x623000a080011400, 0x42008c0340209202,
    0x209188240001000, 0x400408a884001800, 0x110400a6080400, 0x1840060a44020800,
    0x90080104000041, 0x201011000808101, 0x1a2208080504f080, 0x8012020600211212,
    0x500861011240000, 0x180806108200800, 0x4000020e01040044, 0x300000261044000a,
    0x802241102020002, 0x20906061210001, 0x5a84841004010310, 0x4010801011c04,
    0xa010109502200, 0x4a02012000, 0x500201010098b028, 0x8040002811040900,
    0x28000010020204, 0x6000020202d0240, 0x8918844842082200, 0x4010011029020020
], dtype=np.uint64)

# Relevant bit counts for each square (excludes edge squares)
ROOK_RELEVANT_BITS = np.array([
    12, 11, 11, 11, 11, 11, 11, 12,
    11, 10, 10, 10, 10, 10, 10, 11,
    11, 10, 10, 10, 10, 10, 10, 11,
    11, 10, 10, 10, 10, 10, 10, 11,
    11, 10, 10, 10, 10, 10, 10, 11,
    11, 10, 10, 10, 10, 10, 10, 11,
    11, 10, 10, 10, 10, 10, 10, 11,
    12, 11, 11, 11, 11, 11, 11, 12
], dtype=np.int32)

BISHOP_RELEVANT_BITS = np.array([
    6, 5, 5, 5, 5, 5, 5, 6,
    5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 7, 7, 7, 7, 5, 5,
    5, 5, 7, 9, 9, 7, 5, 5,
    5, 5, 7, 9, 9, 7, 5, 5,
    5, 5, 7, 7, 7, 7, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5,
    6, 5, 5, 5, 5, 5, 5, 6
], dtype=np.int32)


# =============================================================================
# MASK GENERATION
# =============================================================================

def _generate_rook_mask(sq):
    """Generate rook attack mask (excluding edge squares on the attack ray)."""
    mask = np.uint64(0)
    rank = sq // 8
    file = sq % 8
    
    # North
    for r in range(rank + 1, 7):  # Exclude rank 8
        mask = set_bit(mask, r * 8 + file)
    # South    
    for r in range(rank - 1, 0, -1):  # Exclude rank 1
        mask = set_bit(mask, r * 8 + file)
    # East
    for f in range(file + 1, 7):  # Exclude file H
        mask = set_bit(mask, rank * 8 + f)
    # West
    for f in range(file - 1, 0, -1):  # Exclude file A
        mask = set_bit(mask, rank * 8 + f)
    
    return mask


def _generate_bishop_mask(sq):
    """Generate bishop attack mask (excluding edge squares on the attack ray)."""
    mask = np.uint64(0)
    rank = sq // 8
    file = sq % 8
    
    # North-East
    r, f = rank + 1, file + 1
    while r < 7 and f < 7:
        mask = set_bit(mask, r * 8 + f)
        r += 1
        f += 1
    
    # North-West
    r, f = rank + 1, file - 1
    while r < 7 and f > 0:
        mask = set_bit(mask, r * 8 + f)
        r += 1
        f -= 1
    
    # South-East
    r, f = rank - 1, file + 1
    while r > 0 and f < 7:
        mask = set_bit(mask, r * 8 + f)
        r -= 1
        f += 1
    
    # South-West
    r, f = rank - 1, file - 1
    while r > 0 and f > 0:
        mask = set_bit(mask, r * 8 + f)
        r -= 1
        f -= 1
    
    return mask


# =============================================================================
# ATTACK GENERATION (with blockers) - Pure Python for table initialization
# =============================================================================

def _rook_attacks_on_the_fly(sq, blockers):
    """Generate rook attacks given blocker configuration (slow, for table init)."""
    # Use pure Python int to avoid numpy/numba signed issues
    attacks = 0
    blockers_int = int(blockers)
    rank = sq // 8
    file = sq % 8
    
    # North
    for r in range(rank + 1, 8):
        s = r * 8 + file
        attacks |= (1 << s)
        if blockers_int & (1 << s):
            break
    # South    
    for r in range(rank - 1, -1, -1):
        s = r * 8 + file
        attacks |= (1 << s)
        if blockers_int & (1 << s):
            break
    # East
    for f in range(file + 1, 8):
        s = rank * 8 + f
        attacks |= (1 << s)
        if blockers_int & (1 << s):
            break
    # West
    for f in range(file - 1, -1, -1):
        s = rank * 8 + f
        attacks |= (1 << s)
        if blockers_int & (1 << s):
            break
    
    return np.uint64(attacks)


def _bishop_attacks_on_the_fly(sq, blockers):
    """Generate bishop attacks given blocker configuration (slow, for table init)."""
    attacks = 0
    blockers_int = int(blockers)
    rank = sq // 8
    file = sq % 8
    
    # North-East
    r, f = rank + 1, file + 1
    while r < 8 and f < 8:
        s = r * 8 + f
        attacks |= (1 << s)
        if blockers_int & (1 << s):
            break
        r += 1
        f += 1
    
    # North-West
    r, f = rank + 1, file - 1
    while r < 8 and f >= 0:
        s = r * 8 + f
        attacks |= (1 << s)
        if blockers_int & (1 << s):
            break
        r += 1
        f -= 1
    
    # South-East
    r, f = rank - 1, file + 1
    while r >= 0 and f < 8:
        s = r * 8 + f
        attacks |= (1 << s)
        if blockers_int & (1 << s):
            break
        r -= 1
        f += 1
    
    # South-West
    r, f = rank - 1, file - 1
    while r >= 0 and f >= 0:
        s = r * 8 + f
        attacks |= (1 << s)
        if blockers_int & (1 << s):
            break
        r -= 1
        f -= 1
    
    return np.uint64(attacks)


# =============================================================================
# BLOCKER ENUMERATION
# =============================================================================

def _enumerate_blockers(mask):
    """Generate all possible blocker configurations for a given mask."""
    # Carry-Rippler trick - use Python int for arithmetic to avoid overflow
    mask_int = int(mask)
    blockers = []
    n = 0
    while True:
        blockers.append(np.uint64(n))
        n = (n - mask_int) & mask_int
        if n == 0:
            break
    return blockers


# =============================================================================
# MAGIC TABLE INITIALIZATION
# =============================================================================

def _init_magic_tables():
    """Initialize all magic bitboard lookup tables."""
    print("[V4d] Initializing Magic Bitboards...")
    
    # 64-bit mask
    MASK_64 = (1 << 64) - 1
    
    # Rook tables
    rook_masks = np.zeros(64, dtype=np.uint64)
    rook_attacks = []  # List of arrays (variable size per square)
    
    for sq in range(64):
        rook_masks[sq] = _generate_rook_mask(sq)
        mask = rook_masks[sq]
        relevant_bits = int(ROOK_RELEVANT_BITS[sq])
        table_size = 1 << relevant_bits
        
        attacks = np.zeros(table_size, dtype=np.uint64)
        blockers_list = _enumerate_blockers(mask)
        magic = int(ROOK_MAGICS[sq])
        
        for blockers in blockers_list:
            # Magic index calculation - mask to 64 bits before shifting
            blockers_int = int(blockers)
            product = (blockers_int * magic) & MASK_64
            index = product >> (64 - relevant_bits)
            attacks[index] = _rook_attacks_on_the_fly(sq, blockers)
        
        rook_attacks.append(attacks)
    
    # Bishop tables
    bishop_masks = np.zeros(64, dtype=np.uint64)
    bishop_attacks = []
    
    for sq in range(64):
        bishop_masks[sq] = _generate_bishop_mask(sq)
        mask = bishop_masks[sq]
        relevant_bits = int(BISHOP_RELEVANT_BITS[sq])
        table_size = 1 << relevant_bits
        
        attacks = np.zeros(table_size, dtype=np.uint64)
        blockers_list = _enumerate_blockers(mask)
        magic = int(BISHOP_MAGICS[sq])
        
        for blockers in blockers_list:
            blockers_int = int(blockers)
            product = (blockers_int * magic) & MASK_64
            index = product >> (64 - relevant_bits)
            attacks[index] = _bishop_attacks_on_the_fly(sq, blockers)
        
        bishop_attacks.append(attacks)
    
    print("[V4d] Magic Bitboards initialized!")
    return rook_masks, rook_attacks, bishop_masks, bishop_attacks


# Initialize tables at module load
ROOK_MASKS, ROOK_ATTACK_TABLES, BISHOP_MASKS, BISHOP_ATTACK_TABLES = _init_magic_tables()


# =============================================================================
# ATTACK LOOKUP FUNCTIONS (O(1))
# =============================================================================

# 64-bit mask constant
_MASK_64 = (1 << 64) - 1


def get_rook_attacks(sq: int, occupancy: np.uint64) -> np.uint64:
    """Get rook attacks for a square given the board occupancy. O(1)."""
    blockers = int(occupancy & ROOK_MASKS[sq])
    magic = int(ROOK_MAGICS[sq])
    relevant_bits = int(ROOK_RELEVANT_BITS[sq])
    product = (blockers * magic) & _MASK_64
    index = product >> (64 - relevant_bits)
    return ROOK_ATTACK_TABLES[sq][index]


def get_bishop_attacks(sq: int, occupancy: np.uint64) -> np.uint64:
    """Get bishop attacks for a square given the board occupancy. O(1)."""
    blockers = int(occupancy & BISHOP_MASKS[sq])
    magic = int(BISHOP_MAGICS[sq])
    relevant_bits = int(BISHOP_RELEVANT_BITS[sq])
    product = (blockers * magic) & _MASK_64
    index = product >> (64 - relevant_bits)
    return BISHOP_ATTACK_TABLES[sq][index]


def get_queen_attacks(sq: int, occupancy: np.uint64) -> np.uint64:
    """Get queen attacks (rook + bishop). O(1)."""
    return get_rook_attacks(sq, occupancy) | get_bishop_attacks(sq, occupancy)


# =============================================================================
# NUMBA JIT VERSIONS (for use in hot loops)
# =============================================================================

# We need to flatten the attack tables for Numba
# This is done separately to avoid Numba compilation issues with Python lists

@njit(cache=True)
def _rook_attacks_jit(sq, occupancy, masks, magics, bits, table_flat, table_offsets):
    """JIT-compiled rook attack lookup."""
    blockers = occupancy & masks[sq]
    shift = 64 - bits[sq]
    index = int((blockers * magics[sq]) >> shift)
    return table_flat[table_offsets[sq] + index]


@njit(cache=True)
def _bishop_attacks_jit(sq, occupancy, masks, magics, bits, table_flat, table_offsets):
    """JIT-compiled bishop attack lookup."""
    blockers = occupancy & masks[sq]
    shift = 64 - bits[sq]
    index = int((blockers * magics[sq]) >> shift)
    return table_flat[table_offsets[sq] + index]
