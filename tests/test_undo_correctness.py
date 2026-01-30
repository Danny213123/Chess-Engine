import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main.engine.v2.chess_engine import GameState

def test_undo():
    gs = GameState()
    start_fen = gs.get_fen()
    print("Start FEN:", start_fen)
    
    # 1. e2e4
    moves = gs.get_valid_moves()
    e2e4 = next(m for m in moves if str(m) == "e2e4")
    
    print("Making e2e4...")
    gs.make_move(e2e4)
    mid_fen = gs.get_fen()
    print("Mid FEN:", mid_fen)
    
    # Verify bitboards updated
    if gs.bitboards['wP'] & (1 << 28): # E4 is square 28? (Row 4, Col 4).
        # Sq mapping: (7-r)*8 + c.
        # e4 is Row 4, Col 4. (7-4)*8 + 4 = 24 + 4 = 28.
        print("Bitboard set at e4 (28) Correct.")
    else:
        print("Bitboard e4 NOT SET!")

    # 2. Undo
    print("Undoing...")
    gs.undo_move()
    end_fen = gs.get_fen()
    print("End FEN:", end_fen)
    
    if start_fen == end_fen:
        print("SUCCESS: FEN restored.")
    else:
        print("FAIL: FEN mismatch!")
        print("Expected:", start_fen)
        print("Got:     ", end_fen)
        
    # Check bitboards restored
    if gs.bitboards['wP'] & (1 << 28):
        print("FAIL: Bitboard e4 still set!")
    else:
        print("SUCCESS: Bitboard e4 cleared.")

if __name__ == "__main__":
    test_undo()
