# V3 Thread-Safe Transposition Table
# Supports both GPU (CUDA) and CPU with proper locking

import threading
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class TTEntry:
    """Transposition table entry."""
    depth: int
    score: int
    flag: str  # "exact", "lower", "upper"
    best_move: Any = None  # Optional best move from this position


class ThreadSafeTranspositionTable:
    """Thread-safe transposition table with size limit."""
    
    def __init__(self, max_entries: int = 10_000_000):
        self._table: Dict[int, TTEntry] = {}
        self._lock = threading.RLock()
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0
    
    def get(self, key: int) -> Optional[TTEntry]:
        """Thread-safe lookup."""
        with self._lock:
            entry = self._table.get(key)
            if entry is not None:
                self._hits += 1
            else:
                self._misses += 1
            return entry
    
    def put(self, key: int, entry: TTEntry):
        """Thread-safe insert with replacement policy."""
        with self._lock:
            # Size limit check
            if len(self._table) >= self._max_entries:
                # Simple eviction: clear half the table
                # More sophisticated: age-based or depth-based
                keys = list(self._table.keys())[:len(self._table) // 2]
                for k in keys:
                    del self._table[k]
            
            # Replace if deeper or same depth
            existing = self._table.get(key)
            if existing is None or entry.depth >= existing.depth:
                self._table[key] = entry
    
    def clear(self):
        """Clear the table."""
        with self._lock:
            self._table.clear()
            self._hits = 0
            self._misses = 0
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._table)
    
    @property
    def hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
    
    def stats(self) -> dict:
        """Get table statistics."""
        with self._lock:
            return {
                "entries": len(self._table),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{self.hit_rate:.1%}"
            }


# Global thread-safe TT instance
_global_tt: Optional[ThreadSafeTranspositionTable] = None

def get_transposition_table() -> ThreadSafeTranspositionTable:
    """Get the global thread-safe transposition table."""
    global _global_tt
    if _global_tt is None:
        _global_tt = ThreadSafeTranspositionTable()
    return _global_tt


def clear_transposition_table():
    """Clear the global transposition table."""
    global _global_tt
    if _global_tt is not None:
        _global_tt.clear()