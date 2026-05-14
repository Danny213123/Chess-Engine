
import os
import time
import importlib
import traceback
import contextlib


from chess_engine.engine.v1 import chess_algorithm as v1_algo
from chess_engine.engine.v1.chess_engine import GameState as GameStateV1
from chess_engine.engine.v2 import chess_algorithm as v2_algo
from chess_engine.engine.v2.chess_engine import GameState as GameStateV2
from chess_engine.engine.v1.pgn_parser import parse_pgn

# Test Positions (name, fen/setup)
POSITIONS = [
    ("Starting Position", None), # None means use default constructor
    ("Kiwipete (Middle Game)", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"),
    ("Endgame (Rook/Pawn)", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1")
]

ENGINES = [
    ("v1", v1_algo, GameStateV1),
    ("v2", v2_algo, GameStateV2)
]

DEPTH = 3 # Keep depth low for quick verification, scale up for real tests

def setup_gamestate(gamestate_cls, fen):
    gs = gamestate_cls()
    if fen:
        set_fen_on_gamestate(gs, fen)
    return gs

def set_fen_on_gamestate(gs, fen):
    """
    Basic FEN setter for the purpose of benchmarking.
    Handles board, turn, and basic castling rights to prevent crashes.
    """
    parts = fen.split(" ")
    board_part = parts[0]
    turn_part = parts[1]
    castling_part = parts[2] if len(parts) > 2 else "-"
    
    rows = board_part.split("/")
    new_board = []
    
    white_king_loc = (7, 4)
    black_king_loc = (0, 4)
    
    for r, row_str in enumerate(rows):
        row_arr = []
        c = 0
        for char in row_str:
            if char.isdigit():
                count = int(char)
                for _ in range(count):
                    row_arr.append("--")
                c += count
            else:
                color = "w" if char.isupper() else "b"
                piece = color + char.upper()
                row_arr.append(piece)
                
                # Track Kings
                if piece == "wK":
                    white_king_loc = (r, c)
                elif piece == "bK":
                    black_king_loc = (r, c)
                
                c += 1
        new_board.append(row_arr)
        
    gs.board = new_board
    gs.white = (turn_part == 'w')
    
    # Update King locations
    gs.white_king_location = white_king_loc # Note: Verify property name. v1 uses white_king_location?
    gs.black_king_location = black_king_loc
    
    # Check property names in GS (v1 uses white_king_location? Let's assume standard)
    # Actually, legacy code (v1) usually has self.white_king_location.
    # But wait, looking at v2/chess_engine.py snippet I viewed earlier (Step 756):
    # self.white_king = (7, 4) NOT white_king_location?
    # No, snippet 756 says: "self.white_king = (7, 4)".
    # AND "self.black_king = (0, 4)".
    # Let's verify names.
    
    if hasattr(gs, 'white_king_location'):
        gs.white_king_location = white_king_loc
        gs.black_king_location = black_king_loc
    elif hasattr(gs, 'white_king'):
        gs.white_king = white_king_loc
        gs.black_king = black_king_loc
        
    # Update Castling Rights
    # Reset to False
    gs.current_castling_rights.wks = False
    gs.current_castling_rights.wqs = False
    gs.current_castling_rights.bks = False
    gs.current_castling_rights.bqs = False
    
    if castling_part != "-":
        if "K" in castling_part: gs.current_castling_rights.wks = True
        if "Q" in castling_part: gs.current_castling_rights.wqs = True
        if "k" in castling_part: gs.current_castling_rights.bks = True
        if "q" in castling_part: gs.current_castling_rights.bqs = True
    
    # Update log to verify consistency
    if hasattr(gs, 'castling_rights_log'):
        # Recreate the log with the current rights as the initial state
        # Need to import castle_rights or reuse the object type. 
        # Since we modified the object in place, let's just deepcopy it or create a new one if we knew the class
        # But we don't have the class imported easily.
        # However, gs.castling_rights_log is a list.
        # We can just clear it and append a copy of current.
        import copy
        gs.castling_rights_log = [copy.deepcopy(gs.current_castling_rights)]
    
    # Re-init bitboards for V2
    if hasattr(gs, '_init_bitboards_from_board'):
        gs._init_bitboards_from_board()
        
    return gs

def run_benchmark():
    print(f"Running Benchmarks (Depth {DEPTH})...")
    print(f"{'Engine':<10} | {'Position':<25} | {'Time (s)':<10} | {'Nodes':<10} | {'NPS':<10}")
    print("-" * 80)
    
    results = {}

    for pos_name, fen in POSITIONS:
        for eng_name, eng_mod, eng_cls in ENGINES:
            
            # Setup
            gs = eng_cls()
            if fen:
                set_fen_on_gamestate(gs, fen)
                
            # Clear TT
            eng_mod.transpositional_table = {}
            
            # Run
            start_time = time.time()
            
            # Monkeypatch DEPTH
            original_depth = eng_mod.DEPTH
            eng_mod.DEPTH = DEPTH
            
            try:
                # Get valid moves first (required by API)
                valid_moves = gs.get_valid_moves()
                
                # Search (suppress engine prints)
                with contextlib.redirect_stdout(open(os.devnull, 'w')):
                    eng_mod.find_best_move(gs, valid_moves, eng_name) # Passing eng_name "v1" or "v2" logic
                
                duration = time.time() - start_time
                nodes = eng_mod.counter
                nps = int(nodes / duration) if duration > 0 else 0
                
                print(f"{eng_name:<10} | {pos_name:<25} | {duration:.4f}     | {nodes:<10} | {nps:<10}")
                
            except Exception as e:
                print(f"{eng_name:<10} | {pos_name:<25} | FAILED ({e})")
                traceback.print_exc()
            finally:
                eng_mod.DEPTH = original_depth

if __name__ == "__main__":
    run_benchmark()
