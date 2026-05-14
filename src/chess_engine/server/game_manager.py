from chess_engine.engine.v3.chess_engine import GameState
from chess_engine.engine.v2 import chess_algorithm as algo_v2
from chess_engine.engine.v3 import chess_algorithm as algo_v3
from chess_engine.engine.v4 import chess_algorithm as algo_v4
from chess_engine.engine.v4b import chess_algorithm as algo_v4b
from chess_engine.engine.v4c import chess_algorithm as algo_v4c
from chess_engine.engine.v5 import chess_algorithm as algo_v5
from chess_engine.engine.v5b import chess_algorithm as algo_v5b
from chess_engine.engine.v5c import chess_algorithm as algo_v5c
from chess_engine.engine.v5d import chess_algorithm as algo_v5d
from chess_engine.engine.v6 import chess_algorithm as algo_v6

AVAILABLE_ENGINES = {
    "human",
    "v2",
    "v3",
    "v4",
    "v4b",
    "v4c",
    "v5",
    "v5b",
    "v5c",
    "v5d",
    "v6",
}


class GameManager:
    def __init__(self):
        self.gs = GameState()
        self.valid_moves = self.gs.get_valid_moves()
        self.white_engine = "v3"  # Default
        self.black_engine = "v3"  # Default
        self.last_search_stats = None
        self.san_history = []
        self.current_search_info = None  # Reference to active search
        self.search_history = []  # History of all AI searches for analysis
        self.redo_stack = []  # Stack of moves for redo functionality
        self.redo_san_stack = []  # Corresponding SAN history for redo
        
    def set_engine_version(self, version: str, color: str = None):
        """Set engine version. If color is None, sets both. Otherwise sets for specific color."""
        ver = version.lower()
        if ver not in AVAILABLE_ENGINES:
            return False, f"Unsupported engine version: {version}"

        if ver == "v6":
            try:
                algo_v6.ensure_available(auto_build=True)
            except algo_v6.V6UnavailableError as error:
                return False, f"V6 is unavailable: {error}"
            
        if color is None:
            self.white_engine = ver
            self.black_engine = ver
            print(f"DEBUG: Both engines switched to {ver}")
        elif color.lower() == "white":
            self.white_engine = ver
            print(f"DEBUG: White engine switched to {ver}")
        elif color.lower() == "black":
            self.black_engine = ver
            print(f"DEBUG: Black engine switched to {ver}")
        else:
            return False, f"Unsupported engine color: {color}"

        return True, "Engine updated"
        
    def stop_search(self):
        """Stop any ongoing search immediately."""
        if self.current_search_info:
            self.current_search_info.stopped = True
            print("[GameManager] Search stop requested")
        return True

    def reset(self):
        self.stop_search()  # Stop any ongoing search
        self.gs = GameState()
        self.valid_moves = self.gs.get_valid_moves()
        self.last_search_stats = None
        self.san_history = []
        self.current_search_info = None
        self.search_history = []  # Clear search history on new game
        self.redo_stack = []  # Clear redo on reset
        self.redo_san_stack = []
    
    def load_fen(self, fen: str):
        """
        Load a game state from a FEN string.
        Returns (success, message) tuple.
        """
        self.stop_search()
        
        if not self.gs.set_fen(fen):
            return False, "Invalid FEN string"
        
        # Reset all tracking after loading FEN
        self.valid_moves = self.gs.get_valid_moves()
        self.last_search_stats = None
        self.san_history = []
        self.current_search_info = None
        self.search_history = []
        self.redo_stack = []
        self.redo_san_stack = []
        
        return True, "Position loaded"
        
    def get_state(self):
        return {
            "fen": self.gs.get_fen(),
            "active_color": "w" if self.gs.white else "b",
            "is_check": self.gs.in_check,
            "is_checkmate": self.gs.check_mate,
            "is_stalemate": self.gs.stale_mate,
            "possible_moves": [str(m) for m in self.valid_moves],
            "history": [str(m) for m in self.gs.move_log],
            "move_history_san": self.san_history,
            "last_search_stats": self.last_search_stats,
            "search_history": self.search_history
        }

    def _get_san(self, move):
        """Generate Standard Algebraic Notation for a move."""
        if hasattr(move, 'isCastleMove') and move.isCastleMove:
            return "O-O-O" if move.end_col < move.start_col else "O-O"
        
        start_sq = self._get_sq_name(move.start_row, move.start_col)
        end_sq = self._get_sq_name(move.end_row, move.end_col)
        piece = move.pieceMoved[1] # 'P', 'N', 'B', 'R', 'Q', 'K'
        
        if piece == 'P':
            if move.pieceCaptured != '--':
                return f"{start_sq[0]}x{end_sq}"
            else:
                return end_sq
        
        # Piece move
        san = piece
        
        # Disambiguation (simplified: just add file if needed, or always for safety?)
        # Full disambiguation is expensive, let's skip strict disambiguation for now 
        # unless we want to filter valid_moves.
        # Let's do basic captures:
        if move.pieceCaptured != '--':
            san += "x"
        
        san += end_sq
        
        # Promotion
        if hasattr(move, 'pawn_promotion') and move.pawn_promotion:
            promo = getattr(move, 'promotion_piece', 'Q')
            san += "=" + promo
            
        return san

    def _get_sq_name(self, r, c):
        files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        return f"{files[c]}{8-r}"

    def make_move_lan(self, start_sq: str, end_sq: str, promotion: str = None):
        """
        Make a move using Long Algebraic Notation (e.g. 'e2', 'e4').
        Promotion can be 'Q', 'R', 'B', or 'N'.
        """
        try:
            print(f"DEBUG: Attempting move: {start_sq} -> {end_sq} (promo={promotion})")
            
            start_row, start_col = self._parse_sq(start_sq)
            end_row, end_col = self._parse_sq(end_sq)
            
            # Find matching moves in valid_moves
            matching_moves = []
            for move in self.valid_moves:
                if (move.start_row == start_row and move.start_col == start_col and 
                    move.end_row == end_row and move.end_col == end_col):
                    matching_moves.append(move)
            
            chosen_move = None
            
            if len(matching_moves) == 1:
                chosen_move = matching_moves[0]
            elif len(matching_moves) > 1:
                # Multiple matches = promotion moves with different pieces
                # Match by promotion piece
                promo_piece = (promotion or 'Q').upper()
                for move in matching_moves:
                    # Check if this move's promotion piece matches
                    if hasattr(move, 'promotion_piece') and move.promotion_piece == promo_piece:
                        chosen_move = move
                        break
                    # Fallback: check move string ends with promotion piece
                    elif str(move).upper().endswith(promo_piece):
                        chosen_move = move
                        break
                # If still no match, default to first (usually Queen)
                if not chosen_move:
                    chosen_move = matching_moves[0]
            
            if chosen_move:
                # Set promotion piece if needed
                if hasattr(chosen_move, 'pawn_promotion') and chosen_move.pawn_promotion:
                    promo_piece = (promotion or 'Q').upper()
                    chosen_move.promotion_piece = promo_piece
                
                # Generate SAN before making move (need context?)
                # Actually, check/mate status is after move.
                # So we make move, then check status to append "+"/"#"
                
                san = self._get_san(chosen_move)
                self.gs.make_move(chosen_move)
                
                # Check for check/mate to append suffix
                if self.gs.check_mate:
                    san += "#"
                elif self.gs.in_check:
                    san += "+"
                
                self.san_history.append(san)
                self.last_search_stats = None # Clear stats for human move
                self.redo_stack = []  # Clear redo stack on new move
                self.redo_san_stack = []
                
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

    def undo_move(self):
        """
        Undo the last move. Saves it to redo stack for potential redo.
        Returns True if successful, False if no moves to undo.
        """
        if len(self.gs.move_log) < 1:
            return False, "No moves to undo"
        
        # Save the move to redo stack before undoing
        move_to_undo = self.gs.move_log[-1]
        self.redo_stack.append(move_to_undo)
        
        # Save corresponding SAN
        if self.san_history:
            san = self.san_history.pop()
            self.redo_san_stack.append(san)
        
        # Undo the move using GameState's undo
        self.gs.undo_move()
        self.valid_moves = self.gs.get_valid_moves()
        self.last_search_stats = None
        
        print(f"DEBUG: Undo successful. Now {'White' if self.gs.white else 'Black'}'s turn")
        return True, "Move undone"
    
    def redo_move(self):
        """
        Redo the last undone move.
        Returns True if successful, False if no moves to redo.
        """
        if not self.redo_stack:
            return False, "No moves to redo"
        
        # Pop from redo stack
        move_to_redo = self.redo_stack.pop()
        
        # Make the move again
        self.gs.make_move(move_to_redo)
        self.valid_moves = self.gs.get_valid_moves()
        
        # Restore SAN
        if self.redo_san_stack:
            san = self.redo_san_stack.pop()
            self.san_history.append(san)
        
        self.last_search_stats = None
        print(f"DEBUG: Redo successful. Now {'White' if self.gs.white else 'Black'}'s turn")
        return True, "Move redone"


    def ai_move(self):
        if self.gs.check_mate or self.gs.stale_mate:
            return None

        # Select engine based on whose turn it is
        current_engine = self.white_engine if self.gs.white else self.black_engine
        
        # If it's a human's turn, don't make an AI move - just return current state
        if current_engine == "human":
            print(f"[GameManager] Human's turn ({'White' if self.gs.white else 'Black'}), skipping AI move")
            return self.get_state()

        move = None
        stats = None

        if current_engine == "v5":
             # Create SearchInfo for v5 engine so we can stop it
             from chess_engine.engine.v5.search import SearchInfo
             self.current_search_info = SearchInfo()

             # V5 returns (move, stats)
             result = algo_v5.find_best_move(self.gs, self.valid_moves, current_engine, search_info=self.current_search_info)
             if isinstance(result, tuple):
                 move, stats = result
             else:
                 move = result

             self.current_search_info = None  # Clear reference after search
        elif current_engine == "v5b":
             # Create SearchInfo for v5b engine so we can stop it
             from chess_engine.engine.v5b.search import SearchInfo
             self.current_search_info = SearchInfo()

             # V5b returns (move, stats) with deeper search
             result = algo_v5b.find_best_move(self.gs, self.valid_moves, current_engine, search_info=self.current_search_info)
             if isinstance(result, tuple):
                 move, stats = result
             else:
                 move = result

             self.current_search_info = None  # Clear reference after search
        elif current_engine == "v5c":
             # Create SearchInfo for v5c engine so we can stop it
             from chess_engine.engine.v5c.search import SearchInfo
             self.current_search_info = SearchInfo()

             # V5c returns (move, stats) with ultra-fast search for maximum depth
             result = algo_v5c.find_best_move(self.gs, self.valid_moves, current_engine, search_info=self.current_search_info)
             if isinstance(result, tuple):
                 move, stats = result
             else:
                 move = result

             self.current_search_info = None  # Clear reference after search
        elif current_engine == "v5d":
             # Create SearchInfo for v5d engine so we can stop it
             from chess_engine.engine.v5d.search import SearchInfo
             self.current_search_info = SearchInfo()

             # V5d returns (move, stats) with improved search (5s, check extensions)
             result = algo_v5d.find_best_move(self.gs, self.valid_moves, current_engine, search_info=self.current_search_info)
             if isinstance(result, tuple):
                 move, stats = result
             else:
                 move = result

             self.current_search_info = None  # Clear reference after search
        elif current_engine == "v6":
             # V6 C++ engine with OpenMP parallel search
             try:
                 result = algo_v6.find_best_move(self.gs, self.valid_moves, current_engine)
                 if isinstance(result, tuple):
                     move, stats = result
                 else:
                     move = result
             except Exception as error:
                 self.last_search_stats = None
                 print(f"[GameManager] V6 move failed: {error}")
                 return None
        elif current_engine == "v2":
            move = algo_v2.find_best_move(self.gs, self.valid_moves, "v2")
        elif current_engine == "v4":
            move = algo_v4.find_best_move(self.gs, self.valid_moves, current_engine)
        elif current_engine == "v4b":
            move = algo_v4b.find_best_move(self.gs, self.valid_moves, current_engine)
        elif current_engine == "v4c":
            move = algo_v4c.find_best_move(self.gs, self.valid_moves, current_engine)
        else:
            move = algo_v3.find_best_move(self.gs, self.valid_moves, current_engine)

        if move:
            san = self._get_san(move)
            self.gs.make_move(move)
            
            if self.gs.check_mate:
                san += "#"
            elif self.gs.in_check:
                san += "+"
                
            self.san_history.append(san)
            
            if stats:
                # Convert numpy types to native Python for JSON serialization
                score = int(stats.get("score", 0))
                depth = int(stats.get("depth", 0))

                # Validate score - don't record if it looks invalid (stopped search)
                # Valid scores are between -30000 and 30000 (INFINITY = 30000)
                # But we want to exclude exact INFINITY values which indicate bad search
                is_valid_score = abs(score) < 29000  # Below MATE_SCORE threshold

                if is_valid_score and depth > 0:
                    self.last_search_stats = {
                        "depth": depth,
                        "nodes": int(stats.get("nodes", 0)),
                        "time": float(stats.get("time", 0)),
                        "score": score,
                        "nps": int(stats.get("nps", 0)),
                        "pv": str(stats.get("pv", ""))
                    }
                    # Add to search history with move info
                    search_entry = {
                        "move_number": len(self.san_history),
                        "move": san,
                        "engine": current_engine,
                        "color": "white" if not self.gs.white else "black",  # After move, color flipped
                        **self.last_search_stats
                    }

                    self.search_history.append(search_entry)
                else:
                    # Invalid/stopped search - don't record stats
                    self.last_search_stats = None
                    print(f"[GameManager] Skipped recording invalid search stats (score={score}, depth={depth})")
            else:
                self.last_search_stats = None
                
            self.valid_moves = self.gs.get_valid_moves()
            return str(move)
        return None

    def get_best_move(self, start_sq=None):
        current_engine = self.white_engine if self.gs.white else self.black_engine
        if current_engine == "v2":
             print("[HINT] Hints disabled for v2 engine (performance)")
             return []
        
        # V3 implementation
        # return algo_v3.find_top_moves(...) 
        # But wait, find_top_moves returns move objects. 
        # Check signature: find_top_moves(gs, valid, engine, top_n) -> list of dicts {move: str, score: int}
        try:
             # Just return top 3 moves for the current position
             # We want "hints for a piece" logic? 
             # No, standard engine analysis usually gives best line.
             # But the UI asks for hints for `start_sq`.
             # If start_sq is provided, filter moves starting from there.
             
             # Actually, simpler: Let V3 engine run standard search.
             # Then filter results.
             top_moves = algo_v3.find_top_moves(self.gs, self.valid_moves, current_engine, top_n=3)
             
             # Format for UI: {move: "e2e4", score: 100}
             # UI expects list of objects with "move" property
             
             if not start_sq:
                 return top_moves
                 
             # Filter by start_sq
             filtered = [m for m in top_moves if str(m['move']).startswith(start_sq)]
             return filtered
        except Exception:
             return []

    def _parse_sq(self, sq: str):
        # "a1" -> (7, 0)
        # "e2" -> (6, 4)
        col_map = {c: i for i, c in enumerate("abcdefgh")}
        file = col_map[sq[0]]
        rank = int(sq[1])
        row = 8 - rank
        return row, file
