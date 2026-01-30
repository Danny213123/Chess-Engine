import sys
import os

# Add main to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from main.engine.v2.chess_engine import GameState
from main.engine.v2 import chess_algorithm
from main.engine.v2.chess_move import Move

class GameManager:
    def __init__(self):
        self.gs = GameState()
        self.valid_moves = self.gs.get_valid_moves()
        
    def reset(self):
        self.gs = GameState()
        self.valid_moves = self.gs.get_valid_moves()
        
    def get_state(self):
        return {
            "fen": self.gs.get_fen(),
            "active_color": "w" if self.gs.white else "b",
            "is_check": self.gs.in_check,
            "is_checkmate": self.gs.check_mate,
            "is_stalemate": self.gs.stale_mate,
            "possible_moves": [str(m) for m in self.valid_moves], # Move.__str__ needs verification
            "history": [str(m) for m in self.gs.move_log]
        }

    def make_move_lan(self, start_sq: str, end_sq: str, promotion: str = None):
        """
        Make a move using Long Algebraic Notation (e.g. 'e2', 'e4').
        """
    def make_move_lan(self, start_sq: str, end_sq: str, promotion: str = None):
        """
        Make a move using Long Algebraic Notation (e.g. 'e2', 'e4').
        """
        try:
            print(f"DEBUG: Attempting move: {start_sq} -> {end_sq} (promo={promotion})")
            
            start_row, start_col = self._parse_sq(start_sq)
            end_row, end_col = self._parse_sq(end_sq)
            
            print(f"DEBUG: Parsed coords: ({start_row}, {start_col}) -> ({end_row}, {end_col})")
            print(f"DEBUG: Current Valid Moves Count: {len(self.valid_moves)}")
            
            # Find the matching move in valid_moves
            chosen_move = None
            for move in self.valid_moves:
                 if (move.start_row == start_row and move.start_col == start_col and 
                    move.end_row == end_row and move.end_col == end_col):
                    chosen_move = move
                    break
            
            if chosen_move:
                self.gs.make_move(chosen_move)
                self.valid_moves = self.gs.get_valid_moves()
                print(f"DEBUG: Move SUCCESS. New Turn: {'White' if self.gs.white else 'Black'}")
                return True, "Move made"
            else:
                print(f"DEBUG: Move FAILED. No match found in {len(self.valid_moves)} moves.")
                # Print first few valid moves to help debug
                for m in self.valid_moves[:5]:
                    print(f" - Candidate: {m}")
                return False, "Illegal move"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"Server Error: {str(e)}"

    def ai_move(self):
        if self.gs.check_mate or self.gs.stale_mate:
            return None
            
        move = chess_algorithm.find_best_move(self.gs, self.valid_moves, "v2")
        if move:
            self.gs.make_move(move)
            self.valid_moves = self.gs.get_valid_moves()
            return str(move)
        return None

    def get_best_move(self, start_sq=None):
        # Hints disabled for v2 - too slow (will be re-enabled in v3 with better performance)
        print("[HINT] Hints disabled for v2 engine (performance)")
        return []

    def _parse_sq(self, sq: str):
        # "a1" -> (7, 0)
        # "e2" -> (6, 4)
        col_map = {c: i for i, c in enumerate("abcdefgh")}
        file = col_map[sq[0]]
        rank = int(sq[1])
        row = 8 - rank
        return row, file
