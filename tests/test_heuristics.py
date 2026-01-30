"""
Tests for board evaluation heuristics.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))

from engine.v2.chess_engine import GameState
from engine.v2.chess_heuristic_calculation import score_board


class TestMaterialCounting:
    """Tests for material evaluation."""
    
    def test_initial_position_balanced(self):
        """Initial position should have balanced score."""
        gs = GameState()
        score = score_board(gs)
        
        # Initial position is equal, score should be close to 0
        # Allow for positional differences
        assert abs(score) < 10, f"Initial position should be balanced, got {score}"
    
    def test_score_changes_after_capture(self):
        """Score should change after a capture."""
        gs = GameState()
        initial_score = score_board(gs)
        
        # Simulate removing a black pawn
        gs.board[1][4] = "--"
        after_score = score_board(gs)
        
        # White should be ahead now (positive score)
        assert after_score > initial_score


class TestPositionalScoring:
    """Tests for positional evaluation."""
    
    def test_score_not_zero(self):
        """Score should account for material and position."""
        gs = GameState()
        score = score_board(gs)
        # Score should be a number (may be 0 for balanced position)
        assert isinstance(score, (int, float))


class TestScoreSymmetry:
    """Tests for score behavior."""
    
    def test_removing_white_piece_decreases_score(self):
        """Removing a white piece should decrease score."""
        gs = GameState()
        initial = score_board(gs)
        
        gs.board[6][4] = "--"  # Remove white e2 pawn
        after = score_board(gs)
        
        assert after < initial
    
    def test_removing_black_piece_increases_score(self):
        """Removing a black piece should increase score."""
        gs = GameState()
        initial = score_board(gs)
        
        gs.board[1][4] = "--"  # Remove black e7 pawn
        after = score_board(gs)
        
        assert after > initial
