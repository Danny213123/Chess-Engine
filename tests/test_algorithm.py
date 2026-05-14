"""
Tests for the AI algorithm components.
"""
import pytest


from chess_engine.engine.v2.chess_engine import GameState
from chess_engine.engine.v2.chess_algorithm import find_best_move, order_moves
import chess_engine.engine.v2.chess_hash as chess_hash


@pytest.fixture(autouse=True)
def setup_zobrist():
    """Load zobrist keys before each test."""
    try:
        chess_hash.load_zobrist()
    except:
        chess_hash.init_zobrist()


class TestMoveOrdering:
    """Tests for move ordering heuristic."""
    
    def test_order_moves_returns_list(self):
        """order_moves should return a list."""
        gs = GameState()
        valid_moves = gs.get_valid_moves()
        ordered = order_moves(valid_moves, gs)
        assert isinstance(ordered, list)
        assert len(ordered) == len(valid_moves)


class TestFindBestMove:
    """Tests for best move finding."""
    
    def test_find_best_move_returns_valid_move(self):
        """find_best_move should return a move from valid moves."""
        gs = GameState()
        valid_moves = gs.get_valid_moves()
        
        best_move = find_best_move(gs, valid_moves, "old")  # Use 'old' for faster test
        
        assert best_move is not None
        assert best_move in valid_moves
    
    def test_find_best_move_doesnt_crash_with_v1(self):
        """find_best_move with v1 engine runs without error."""
        gs = GameState()
        valid_moves = gs.get_valid_moves()
        
        # Just verify it doesn't crash - full depth takes too long
        best_move = find_best_move(gs, valid_moves, "old")
        assert best_move is not None


class TestTranspositionTable:
    """Tests for transposition table."""
    
    def test_same_position_same_hash(self):
        """Same position should produce same hash."""
        gs1 = GameState()
        gs2 = GameState()
        
        hash1 = chess_hash.zobrist_key(gs1)
        hash2 = chess_hash.zobrist_key(gs2)
        
        assert hash1 == hash2
    
    def test_different_position_different_hash(self):
        """Different positions should produce different hashes."""
        gs = GameState()
        hash_before = chess_hash.zobrist_key(gs)
        
        valid_moves = gs.get_valid_moves()
        gs.make_move(valid_moves[0])
        hash_after = chess_hash.zobrist_key(gs)
        
        assert hash_before != hash_after
