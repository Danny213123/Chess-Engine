import unittest
from unittest.mock import patch


from chess_engine.engine.v2.chess_engine import GameState
import chess_engine.engine.v2.chess_algorithm as chess_algorithm

class TestChessEngine(unittest.TestCase):
    def setUp(self):
        self.game_state = GameState()

    def test_initial_state(self):
        self.assertTrue(self.game_state.white)
        self.assertEqual(len(self.game_state.move_log), 0)

    def test_valid_moves(self):
        valid_moves = self.game_state.get_valid_moves()
        # Initial position has 20 valid moves (16 pawn moves + 4 knight moves)
        self.assertEqual(len(valid_moves), 20)

    def test_v1_engine(self):
        valid_moves = self.game_state.get_valid_moves()
        
        # Patch DEPTH to 1 to make test fast
        with patch('engine.v2.chess_algorithm.DEPTH', 1):
             best_move = chess_algorithm.find_best_move(self.game_state, valid_moves, "v1")
        
        self.assertIsNotNone(best_move)
        
    def test_make_move(self):
        valid_moves = self.game_state.get_valid_moves()
        move = valid_moves[0]
        self.game_state.make_move(move)
        self.assertFalse(self.game_state.white)
        self.assertEqual(len(self.game_state.move_log), 1)

if __name__ == '__main__':
    unittest.main()
