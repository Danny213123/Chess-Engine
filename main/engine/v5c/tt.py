"""
V4d Transposition Table - Lockless Hash Table for Move Caching
Following Chess Programming Wiki (CPW) specifications.

The transposition table stores previously searched positions to avoid
redundant work. Uses Zobrist keys for position identification.
"""

import numpy as np
from numba import njit, uint64, int32, int16
from typing import NamedTuple, Optional

# =============================================================================
# TT ENTRY FLAGS
# =============================================================================

TT_EXACT = 0    # Exact score
TT_ALPHA = 1    # Upper bound (failed low)
TT_BETA = 2     # Lower bound (failed high)

# =============================================================================
# TT ENTRY STRUCTURE
# =============================================================================

# Structure: 16 bytes per entry
# - hash: 8 bytes (uint64) - Zobrist key
# - move: 4 bytes (int32) - Best move
# - score: 2 bytes (int16) - Evaluation score
# - depth: 1 byte (int8) - Search depth
# - flag: 1 byte (int8) - Entry type (exact/alpha/beta)


class TTEntry:
    """Transposition table entry."""
    __slots__ = ['hash', 'move', 'score', 'depth', 'flag', 'age']
    
    def __init__(self, hash_key=0, move=0, score=0, depth=0, flag=TT_EXACT, age=0):
        self.hash = hash_key
        self.move = move
        self.score = score
        self.depth = depth
        self.flag = flag
        self.age = age


# =============================================================================
# TRANSPOSITION TABLE
# =============================================================================

class TranspositionTable:
    """
    Lockless transposition table using numpy arrays.
    
    Uses a simple replacement scheme: always replace if:
    - New entry is from deeper search
    - Existing entry is from an older search
    """
    
    def __init__(self, size_mb: int = 64):
        """Initialize TT with given size in megabytes."""
        # Each entry is roughly 24 bytes (with Python overhead, we estimate 32)
        # For arrays, we use separate arrays which is more cache-efficient
        self.entry_size = 32
        self.num_entries = (size_mb * 1024 * 1024) // self.entry_size
        
        # Use power of 2 for fast modulo via bitwise AND
        self.num_entries = 1 << (self.num_entries.bit_length() - 1)
        self.mask = self.num_entries - 1
        
        # Separate arrays for better cache performance
        self.keys = np.zeros(self.num_entries, dtype=np.uint64)
        self.moves = np.zeros(self.num_entries, dtype=np.int32)
        self.scores = np.zeros(self.num_entries, dtype=np.int16)
        self.depths = np.zeros(self.num_entries, dtype=np.int8)
        self.flags = np.zeros(self.num_entries, dtype=np.int8)
        self.ages = np.zeros(self.num_entries, dtype=np.uint8)  # 0-255 range
        
        self.current_age = 0
        self.hits = 0
        self.stores = 0
        
        print(f"[V4d] TT initialized: {self.num_entries} entries ({size_mb}MB)")
    
    def clear(self):
        """Clear all entries."""
        self.keys.fill(0)
        self.moves.fill(0)
        self.scores.fill(0)
        self.depths.fill(0)
        self.flags.fill(0)
        self.ages.fill(0)
        self.hits = 0
        self.stores = 0
    
    def new_search(self):
        """Called at the start of each new search."""
        self.current_age = (self.current_age + 1) % 256
    
    def probe(self, key: int) -> Optional[TTEntry]:
        """
        Look up a position in the TT.
        Returns TTEntry if found, None otherwise.
        """
        index = key & self.mask
        
        if self.keys[index] == key:
            self.hits += 1
            return TTEntry(
                hash_key=self.keys[index],
                move=int(self.moves[index]),
                score=int(self.scores[index]),
                depth=int(self.depths[index]),
                flag=int(self.flags[index]),
                age=int(self.ages[index])
            )
        
        return None
    
    def store(self, key: int, move: int, score: int, depth: int, flag: int):
        """
        Store a position in the TT.
        Uses replacement scheme: replace if deeper or older entry.
        """
        index = key & self.mask
        
        # Replacement logic: always replace if
        # 1. Empty entry
        # 2. Same position (update)
        # 3. New search has deeper depth
        # 4. Old entry is from previous search
        should_replace = (
            self.keys[index] == 0 or
            self.keys[index] == key or
            depth >= self.depths[index] or
            self.ages[index] != self.current_age
        )
        
        if should_replace:
            self.keys[index] = key
            self.moves[index] = move
            self.scores[index] = max(-32000, min(32000, score))  # Clamp
            self.depths[index] = depth
            self.flags[index] = flag
            self.ages[index] = np.uint8(self.current_age & 0xFF)
            self.stores += 1
    
    def hashfull(self) -> int:
        """Return permille of TT entries used (for UCI info)."""
        # Sample 1000 entries
        sample_size = min(1000, self.num_entries)
        used = np.count_nonzero(self.keys[:sample_size])
        return (used * 1000) // sample_size


# Global TT instance
TT = TranspositionTable(size_mb=64)
