"""
Tests that play through famous chess games move-by-move to verify correctness.
"""
import pytest
from conftest import make_move_from_notation, move_exists
from engine.v2.chess_engine import GameState


class TestFoolsMate:
    """Fool's Mate - the shortest possible checkmate."""
    
    def test_fools_mate_complete_game(self, initial_game):
        """Play through Fool's Mate and verify checkmate."""
        gs = initial_game
        
        # 1. f3 e5
        assert move_exists(gs, (6, 5), (5, 5))  # f3 is legal
        make_move_from_notation(gs, (6, 5), (5, 5))
        assert move_exists(gs, (1, 4), (3, 4))  # e5 is legal
        make_move_from_notation(gs, (1, 4), (3, 4))
        
        # 2. g4 Qh4#
        assert move_exists(gs, (6, 6), (4, 6))  # g4 is legal
        make_move_from_notation(gs, (6, 6), (4, 6))
        assert move_exists(gs, (0, 3), (4, 7))  # Qh4 is legal
        make_move_from_notation(gs, (0, 3), (4, 7))
        
        # Verify checkmate
        gs.get_valid_moves()
        assert gs.check_mate
        assert gs.in_check


class TestScholarsMate:
    """Scholar's Mate - a common 4-move checkmate."""
    
    def test_scholars_mate_complete_game(self, initial_game):
        """Play through Scholar's Mate and verify checkmate."""
        gs = initial_game
        
        # 1. e4 e5
        make_move_from_notation(gs, (6, 4), (4, 4))  # e4
        make_move_from_notation(gs, (1, 4), (3, 4))  # e5
        
        # 2. Bc4 Nc6
        make_move_from_notation(gs, (7, 5), (4, 2))  # Bc4
        make_move_from_notation(gs, (0, 1), (2, 2))  # Nc6
        
        # 3. Qh5 Nf6??
        make_move_from_notation(gs, (7, 3), (3, 7))  # Qh5
        make_move_from_notation(gs, (0, 6), (2, 5))  # Nf6
        
        # 4. Qxf7#
        assert move_exists(gs, (3, 7), (1, 5))  # Qxf7 is legal
        make_move_from_notation(gs, (3, 7), (1, 5))  # Qxf7#
        
        # Verify checkmate
        gs.get_valid_moves()
        assert gs.check_mate


class TestItalianGame:
    """Italian Game opening - verify legal moves."""
    
    def test_italian_game_opening(self, initial_game):
        """Play through Italian Game opening."""
        gs = initial_game
        
        # 1. e4 e5
        make_move_from_notation(gs, (6, 4), (4, 4))
        make_move_from_notation(gs, (1, 4), (3, 4))
        
        # 2. Nf3 Nc6
        make_move_from_notation(gs, (7, 6), (5, 5))
        make_move_from_notation(gs, (0, 1), (2, 2))
        
        # 3. Bc4 (Italian Game)
        assert move_exists(gs, (7, 5), (4, 2))  # Bc4 is legal
        make_move_from_notation(gs, (7, 5), (4, 2))
        
        # Verify position
        assert gs.board[4][2] == "wB"  # Bishop on c4
        assert gs.board[5][5] == "wN"  # Knight on f3
        assert gs.board[2][2] == "bN"  # Knight on c6


class TestLegalMoveVerification:
    """Verify that all moves in games are legal at each step."""
    
    def test_move_count_changes_correctly(self, initial_game):
        """Move log grows with each move."""
        gs = initial_game
        assert len(gs.move_log) == 0
        
        make_move_from_notation(gs, (6, 4), (4, 4))  # e4
        assert len(gs.move_log) == 1
        
        make_move_from_notation(gs, (1, 4), (3, 4))  # e5
        assert len(gs.move_log) == 2
    
    def test_turn_alternates(self, initial_game):
        """Turn alternates between white and black."""
        gs = initial_game
        assert gs.white is True
        
        make_move_from_notation(gs, (6, 4), (4, 4))  # White moves
        assert gs.white is False
        
        make_move_from_notation(gs, (1, 4), (3, 4))  # Black moves
        assert gs.white is True
    
    def test_fen_updates_correctly(self, initial_game):
        """FEN string updates after moves."""
        gs = initial_game
        initial_fen = gs.get_fen()
        
        make_move_from_notation(gs, (6, 4), (4, 4))  # e4
        after_e4_fen = gs.get_fen()
        
        assert initial_fen != after_e4_fen
        # FEN should show black to move
        assert " b " in after_e4_fen
