"""
Tests for game states: check, checkmate, stalemate.
"""
import pytest
from conftest import move_exists, make_move_from_notation
from chess_engine.engine.v2.chess_engine import GameState


class TestCheckDetection:
    """Tests for detecting when king is in check."""
    
    def test_initial_position_not_in_check(self, initial_game):
        """Initial position is not in check."""
        gs = initial_game
        gs.get_valid_moves()  # Updates in_check
        assert not gs.in_check


class TestCheckmate:
    """Tests for checkmate detection."""
    
    def test_fools_mate(self, initial_game):
        """Fool's Mate in 2 moves."""
        gs = initial_game
        # 1. f3 e5 2. g4 Qh4#
        make_move_from_notation(gs, (6, 5), (5, 5))  # f3
        make_move_from_notation(gs, (1, 4), (3, 4))  # e5
        make_move_from_notation(gs, (6, 6), (4, 6))  # g4
        make_move_from_notation(gs, (0, 3), (4, 7))  # Qh4#
        
        gs.get_valid_moves()
        assert gs.check_mate
        assert gs.in_check
    
    def test_scholars_mate(self, initial_game):
        """Scholar's Mate."""
        gs = initial_game
        # 1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6?? 4. Qxf7#
        make_move_from_notation(gs, (6, 4), (4, 4))  # e4
        make_move_from_notation(gs, (1, 4), (3, 4))  # e5
        make_move_from_notation(gs, (7, 5), (4, 2))  # Bc4
        make_move_from_notation(gs, (0, 1), (2, 2))  # Nc6
        make_move_from_notation(gs, (7, 3), (3, 7))  # Qh5
        make_move_from_notation(gs, (0, 6), (2, 5))  # Nf6
        make_move_from_notation(gs, (3, 7), (1, 5))  # Qxf7#
        
        gs.get_valid_moves()
        assert gs.check_mate


class TestStalemate:
    """Tests for stalemate detection."""
    
    def test_stalemate_position(self):
        """Stalemate when king has no legal moves and not in check."""
        gs = GameState()
        # Clear board
        for row in range(8):
            for col in range(8):
                gs.board[row][col] = "--"
        
        # Classic stalemate: white king in corner, black queen controls escape
        gs.board[0][0] = "wK"  # White king at a8
        gs.white_king = (0, 0)
        gs.board[2][1] = "bQ"  # Queen at b6 controls escape
        gs.board[7][7] = "bK"  # Black king at h1
        gs.black_king = (7, 7)
        
        # Reset castling rights (no castling in this position)
        gs.current_castling_rights.wks = False
        gs.current_castling_rights.wqs = False
        gs.current_castling_rights.bks = False
        gs.current_castling_rights.bqs = False
        
        valid_moves = gs.get_valid_moves()
        # Should be stalemate (no moves, not in check)
        assert len(valid_moves) == 0
        assert gs.stale_mate


class TestKingCannotMoveIntoCheck:
    """Tests ensuring king cannot move into attacked squares."""
    
    def test_king_moves_after_opening(self, initial_game):
        """King can move after opening development."""
        gs = initial_game
        # Play some moves to open position
        make_move_from_notation(gs, (6, 4), (4, 4))  # e4
        make_move_from_notation(gs, (1, 4), (3, 4))  # e5
        # Now king at e1 can potentially move to e2
        assert move_exists(gs, (7, 4), (6, 4))  # Ke2


class TestUndoMove:
    """Tests for undo move functionality."""
    
    def test_undo_restores_position(self, initial_game):
        """Undo move restores the previous position."""
        gs = initial_game
        original_board = [row[:] for row in gs.board]
        
        make_move_from_notation(gs, (6, 4), (4, 4))  # e4
        gs.undo_move()
        
        assert gs.board == original_board
        assert gs.white is True  # Back to white's turn
    
    def test_undo_multiple_moves(self, initial_game):
        """Can undo multiple moves."""
        gs = initial_game
        
        make_move_from_notation(gs, (6, 4), (4, 4))  # e4
        make_move_from_notation(gs, (1, 4), (3, 4))  # e5
        make_move_from_notation(gs, (7, 6), (5, 5))  # Nf3
        
        assert len(gs.move_log) == 3
        
        gs.undo_move()
        gs.undo_move()
        gs.undo_move()
        
        assert len(gs.move_log) == 0
        assert gs.white is True
