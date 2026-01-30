import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main.server.game_manager import GameManager

def test_simulation():
    gm = GameManager()
    print("Initial FEN:", gm.get_state()['fen'])
    
    # 1. e2->e4
    print("\nAttempting e2e4...")
    success, msg = gm.make_move_lan("e2", "e4", "Q")
    if success:
        print("Success! FEN:", gm.get_state()['fen'])
    else:
        print("e2e4 Failed:", msg)
        debug_moves(gm)
        return

    # 2. e7->e5
    print("\nAttempting e7e5...")
    success, msg = gm.make_move_lan("e7", "e5", "Q")
    if success:
        print("Success! FEN:", gm.get_state()['fen'])
    else:
        print("e7e5 Failed:", msg)
        debug_moves(gm)
        return

    # 3. g1->f3 (Knight)
    print("\nAttempting g1f3...")
    success, msg = gm.make_move_lan("g1", "f3", "Q")
    if success:
        print("Success! FEN:", gm.get_state()['fen'])
    else:
        print("g1f3 Failed:", msg)
        debug_moves(gm)
        return

def debug_moves(gm):
    print("Valid Moves available:")
    for m in gm.valid_moves:
        print(f" - {m}")

if __name__ == "__main__":
    test_simulation()
