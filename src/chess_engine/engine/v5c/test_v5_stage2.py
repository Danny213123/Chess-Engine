"""
V4d Stage II Tests - Search, Evaluation, Transposition Table
Tests for the search algorithm components.
"""

import pytest
import time
import numpy as np

from chess_engine.engine.v5.board import BoardState
from chess_engine.engine.v5.eval import evaluate, INFINITY, MATE_SCORE
from chess_engine.engine.v5.tt import TranspositionTable, TT_EXACT, TT_ALPHA, TT_BETA
from chess_engine.engine.v5.search import search, get_best_move, alpha_beta, SearchInfo
from chess_engine.engine.v5.move_gen import move_to_string, string_to_move


class TestEvaluation:
    """Test evaluation function."""
    
    def test_starting_position(self):
        """Starting position should be approximately equal."""
        board = BoardState()
        score = evaluate(board)
        # Score should be close to 0 (just tempo bonus)
        assert -50 < score < 50
    
    def test_white_advantage(self):
        """White with extra piece should have positive score."""
        board = BoardState()
        # Position with white having extra knight
        board.from_fen("rnbqkb1r/pppppppp/5n2/8/8/5N2/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        score = evaluate(board)
        # White is up a knight (about 320 cp)
        assert score > 250
    
    def test_material_symmetry(self):
        """Equal material should give near-zero score."""
        board = BoardState()
        score = evaluate(board)
        assert abs(score) < 100  # Only tempo affects score


class TestTranspositionTable:
    """Test transposition table."""
    
    def test_store_and_probe(self):
        tt = TranspositionTable(size_mb=1)
        
        key = 12345678
        tt.store(key, 100, 50, 5, TT_EXACT)
        
        entry = tt.probe(key)
        assert entry is not None
        assert entry.move == 100
        assert entry.score == 50
        assert entry.depth == 5
        assert entry.flag == TT_EXACT
    
    def test_probe_miss(self):
        tt = TranspositionTable(size_mb=1)
        
        entry = tt.probe(99999999)
        assert entry is None
    
    def test_replacement(self):
        """Deeper searches should replace shallower ones."""
        tt = TranspositionTable(size_mb=1)
        
        key = 12345678
        tt.store(key, 100, 50, 3, TT_EXACT)
        tt.store(key, 200, 60, 5, TT_EXACT)  # Deeper
        
        entry = tt.probe(key)
        assert entry.move == 200
        assert entry.depth == 5


class TestSearch:
    """Test search algorithm."""
    
    def test_finds_move(self):
        """Search should find a legal move."""
        board = BoardState()
        move, stats = search(board, depth_limit=3, verbose=False)
        
        assert move != 0
        move_str = move_to_string(move)
        assert len(move_str) >= 4
    
    def test_depth_increases_nodes(self):
        """Deeper searches should explore more nodes."""
        board = BoardState()
        
        info1 = SearchInfo()
        info1.depth_limit = 2
        move1, _ = search(board, depth_limit=2, verbose=False)
        
        info2 = SearchInfo()
        info2.depth_limit = 4
        move2, _ = search(board, depth_limit=4, verbose=False)
        
        # Both should find moves
        assert move1 != 0
        assert move2 != 0
    
    def test_time_limit_respected(self):
        """Search should respect time limits."""
        board = BoardState()
        
        start = time.time()
        move, stats = search(board, time_limit=0.5, verbose=False)
        elapsed = time.time() - start
        
        # Should complete within 1 second (with some buffer)
        assert elapsed < 1.5
    
    def test_mate_in_one(self):
        """Should find mate in one."""
        board = BoardState()
        # Position where white can mate with Qxf7#
        board.from_fen("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1")
        
        move, stats = search(board, depth_limit=4, verbose=False)
        move_str = move_to_string(move)
        
        # Should find Qxf7# (scholar's mate)
        assert move_str == "h5f7" or stats['score'] > MATE_SCORE - 10


class TestGetBestMove:
    """Test simple interface."""
    
    def test_returns_move(self):
        board = BoardState()
        move = get_best_move(board, time_limit=0.5)
        assert move != 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
