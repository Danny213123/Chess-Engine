from pydantic import BaseModel
from typing import Optional, List, Tuple

class MoveRequest(BaseModel):
    start_sq: str # e.g. "e2"
    end_sq: str   # e.g. "e4"
    promotion: Optional[str] = None # "Q", "R", "B", "N"

class GameStateResponse(BaseModel):
    fen: str
    active_color: str
    is_check: bool
    is_checkmate: bool
    is_stalemate: bool
    possible_moves: List[str] # List of LAN moves e.g. ["e2e4", "g1f3"]
    history: List[str] # SAN or LAN history
