from pydantic import BaseModel
from typing import Optional, List, Tuple

class MoveRequest(BaseModel):
    start_sq: str # e.g. "e2"
    end_sq: str   # e.g. "e4"
    promotion: Optional[str] = None # "Q", "R", "B", "N"

class SearchStats(BaseModel):
    depth: int
    nodes: int
    time: float
    score: int
    nps: int
    pv: Optional[str] = None

class GameStateResponse(BaseModel):
    fen: str
    active_color: str
    is_check: bool
    is_checkmate: bool
    is_stalemate: bool
    possible_moves: List[str] # List of LAN moves e.g. ["e2e4", "g1f3"]
    history: List[str] # LAN history
    move_history_san: List[str] = [] # SAN history for UI
    last_search_stats: Optional[SearchStats] = None
