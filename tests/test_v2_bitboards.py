import sys
import os
import unittest

# Add 'main' to sys.path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'main')))

from engine.v2.chess_engine import GameState
from engine.v2.bitboard_helpers import get_bit, count_bits

class TestV2Bitboards(unittest.TestCase):
    def setUp(self):
        self.gs = GameState()

    def test_initial_bitboard_population(self):
        """Verify that bitboards are populated correctly from the board array."""
        
        # White Pawns on Rank 2 (A2-H2)
        # Squares 8-15
        wP = self.gs.bitboards["wP"]
        self.assertEqual(count_bits(wP), 8)
        for sq in range(8, 16):
            self.assertEqual(get_bit(wP, sq), 1, f"White pawn missing at square {sq}")

        # Black King on E8 (Square 60)
        # E1 is 4. E8 is 4 + 7*8 = 60.
        bK = self.gs.bitboards["bK"]
        self.assertEqual(count_bits(bK), 1)
        self.assertEqual(get_bit(bK, 60), 1, "Black King missing at E8 (60)")
        
        # White King on E1 (Square 4)
        wK = self.gs.bitboards["wK"]
        self.assertEqual(count_bits(wK), 1)
        self.assertEqual(get_bit(wK, 4), 1, "White King missing at E1 (4)")

    def test_occupancy_initialization(self):
        """Verify absolute occupancies."""
        # White pieces: 8 pawns + 2 R + 2 N + 2 B + 1 Q + 1 K = 16
        self.assertEqual(count_bits(self.gs.occupancies["w"]), 16)
        self.assertEqual(count_bits(self.gs.occupancies["b"]), 16)
        self.assertEqual(count_bits(self.gs.occupancies["both"]), 32)
        
    def test_make_move_updates_bitboards(self):
        """Verify that make_move updates bitboards correctly."""
        # E2 (12) -> E4 (28) (White Pawn)
        # Find the move
        moves = self.gs.get_valid_moves()
        e2e4 = None
        for move in moves:
            if move.pieceMoved == "wP" and move.start_row == 6 and move.start_col == 4 and move.end_row == 4 and move.end_col == 4:
                e2e4 = move
                break
        
        self.assertIsNotNone(e2e4, "Could not find E2-E4 move")
        
        self.gs.make_move(e2e4)
        
        # Check bitboards
        wP = self.gs.bitboards["wP"]
        self.assertEqual(get_bit(wP, 12), 0, "Pawn still at E2 (12)")
        self.assertEqual(get_bit(wP, 28), 1, "Pawn not at E4 (28)")
        
        # Check occupancies
        self.assertEqual(get_bit(self.gs.occupancies["w"], 12), 0)
        self.assertEqual(get_bit(self.gs.occupancies["w"], 28), 1)
        
        # Undo
        self.gs.undo_move()
        wP = self.gs.bitboards["wP"]
        self.assertEqual(get_bit(wP, 12), 1, "Pawn not restored to E2")
        self.assertEqual(get_bit(wP, 28), 0, "Pawn still at E4")

if __name__ == '__main__':
    unittest.main()
