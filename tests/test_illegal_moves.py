"""
Tests ensuring illegal moves are not allowed.
"""
import pytest
from conftest import move_exists, make_move_from_notation
from chess_engine.engine.v2.chess_engine import GameState


class TestPawnIllegalMoves:
    """Tests for illegal pawn moves."""
    
    def test_pawn_cannot_move_backward(self, initial_game):
        """Pawns cannot move backward."""
        gs = initial_game
        # Move pawn forward first
        make_move_from_notation(gs, (6, 4), (4, 4))  # e4
        make_move_from_notation(gs, (1, 4), (3, 4))  # e5
        
        # White pawn at e4 cannot move back to e3
        assert not move_exists(gs, (4, 4), (5, 4))
    
    def test_pawn_cannot_capture_forward(self, initial_game):
        """Pawns can only capture diagonally, not forward."""
        gs = initial_game
        # Place enemy piece directly in front
        gs.board[5][4] = "bP"
        
        # e2 pawn cannot "capture" e3 (blocked, not a capture)
        assert not move_exists(gs, (6, 4), (5, 4))


class TestWrongColorMoves:
    """Tests ensuring players can only move their own pieces."""
    
    def test_white_cannot_move_black_pieces(self, initial_game):
        """White cannot move black pieces on white's turn."""
        gs = initial_game
        assert gs.white is True
        
        # No black pawn moves should be in valid moves
        valid_moves = gs.get_valid_moves()
        for move in valid_moves:
            assert move.pieceMoved[0] == "w", f"Found black piece move: {move.pieceMoved}"
    
    def test_black_cannot_move_white_pieces(self, initial_game):
        """Black cannot move white pieces on black's turn."""
        gs = initial_game
        make_move_from_notation(gs, (6, 4), (4, 4))  # White moves
        assert gs.white is False
        
        valid_moves = gs.get_valid_moves()
        for move in valid_moves:
            assert move.pieceMoved[0] == "b", f"Found white piece move: {move.pieceMoved}"


class TestCapturingOwnPieces:
    """Tests ensuring pieces cannot capture own pieces."""
    
    def test_cannot_capture_own_piece(self, initial_game):
        """No piece can capture a friendly piece."""
        gs = initial_game
        valid_moves = gs.get_valid_moves()
        
        for move in valid_moves:
            end_piece = gs.board[move.end_row][move.end_col]
            if end_piece != "--":
                # If landing on a piece, it must be enemy
                own_color = move.pieceMoved[0]
                assert end_piece[0] != own_color, \
                    f"Move captures own piece: {move.pieceMoved} to {end_piece}"


class TestMoveValidation:
    """General move validation tests."""
    
    def test_move_stays_on_board(self, initial_game):
        """All moves must stay within the 8x8 board."""
        gs = initial_game
        valid_moves = gs.get_valid_moves()
        
        for move in valid_moves:
            assert 0 <= move.end_row < 8, f"Move goes off board: row {move.end_row}"
            assert 0 <= move.end_col < 8, f"Move goes off board: col {move.end_col}"
    
    def test_piece_actually_moves(self, initial_game):
        """A move must actually change the piece's position."""
        gs = initial_game
        valid_moves = gs.get_valid_moves()
        
        for move in valid_moves:
            assert (move.start_row, move.start_col) != (move.end_row, move.end_col), \
                "Move starts and ends on same square"
    
    def test_no_moves_off_board(self, initial_game):
        """All moves should have valid board coordinates."""
        gs = initial_game
        valid_moves = gs.get_valid_moves()
        
        for move in valid_moves:
            assert 0 <= move.start_row < 8
            assert 0 <= move.start_col < 8
            assert 0 <= move.end_row < 8
            assert 0 <= move.end_col < 8
