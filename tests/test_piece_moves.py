"""
Tests for individual piece movement rules.
These tests verify that each piece type moves according to chess rules.
"""
import pytest
from conftest import move_exists, count_moves_from_square, make_move_from_notation
from chess_engine.engine.v2.chess_engine import GameState


class TestPawnMoves:
    """Tests for pawn movement."""
    
    def test_pawn_single_push(self, initial_game):
        """Pawn can move one square forward."""
        gs = initial_game
        # e2-e3 should be valid
        assert move_exists(gs, (6, 4), (5, 4))
    
    def test_pawn_double_push_from_start(self, initial_game):
        """Pawn can move two squares forward from starting position."""
        gs = initial_game
        # e2-e4 should be valid
        assert move_exists(gs, (6, 4), (4, 4))
    
    def test_pawn_no_double_push_after_moved(self, initial_game):
        """Pawn cannot move two squares after it has already moved."""
        gs = initial_game
        # Move e2-e3
        make_move_from_notation(gs, (6, 4), (5, 4))
        # Black moves
        make_move_from_notation(gs, (1, 0), (2, 0))
        # Now e3-e5 should NOT be valid (double push after already moved)
        assert not move_exists(gs, (5, 4), (3, 4))

    def test_pawn_blocked_cannot_move(self, initial_game):
        """Pawn cannot move forward if blocked."""
        gs = initial_game
        # Block e2 pawn with a piece
        gs.board[5][4] = "wN"  # Knight at e3
        # e2 pawn should have no forward moves
        assert not move_exists(gs, (6, 4), (5, 4))
        assert not move_exists(gs, (6, 4), (4, 4))

    def test_black_pawn_moves_down(self, initial_game):
        """Black pawn moves down the board (increasing row)."""
        gs = initial_game
        # Make white move first
        make_move_from_notation(gs, (6, 4), (4, 4))
        # Now black's turn - e7-e6 should be valid
        assert move_exists(gs, (1, 4), (2, 4))
        # e7-e5 double push should be valid
        assert move_exists(gs, (1, 4), (3, 4))


class TestRookMoves:
    """Tests for rook movement."""
    
    def test_rook_moves_on_initial_board(self, initial_game):
        """Rook on initial board has no moves (blocked by pieces)."""
        gs = initial_game
        # a1 rook has no moves initially
        moves = count_moves_from_square(gs, 7, 0)
        assert moves == 0


class TestKnightMoves:
    """Tests for knight movement."""
    
    def test_knight_initial_moves(self, initial_game):
        """Knight on initial board has exactly 2 moves each."""
        gs = initial_game
        # b1 knight can move to a3 or c3
        assert move_exists(gs, (7, 1), (5, 0))  # Na3
        assert move_exists(gs, (7, 1), (5, 2))  # Nc3
        moves = count_moves_from_square(gs, 7, 1)
        assert moves == 2
    
    def test_knight_jumps_over_pieces(self, initial_game):
        """Knight can jump over other pieces."""
        gs = initial_game
        # b1 knight can move even though surrounded by pawns
        assert move_exists(gs, (7, 1), (5, 0))  # Nc3
        assert move_exists(gs, (7, 1), (5, 2))  # Na3


class TestBishopMoves:
    """Tests for bishop movement."""
    
    def test_bishop_blocked_on_initial(self, initial_game):
        """Bishop on initial board has no moves (blocked by pawns)."""
        gs = initial_game
        # c1 bishop blocked
        moves = count_moves_from_square(gs, 7, 2)
        assert moves == 0


class TestQueenMoves:
    """Tests for queen movement."""
    
    def test_queen_blocked_on_initial(self, initial_game):
        """Queen on initial board has no moves (blocked)."""
        gs = initial_game
        moves = count_moves_from_square(gs, 7, 3)
        assert moves == 0


class TestKingMoves:
    """Tests for king movement."""
    
    def test_king_blocked_on_initial(self, initial_game):
        """King on initial board has no moves (blocked)."""
        gs = initial_game
        moves = count_moves_from_square(gs, 7, 4)
        assert moves == 0
    
    def test_king_moves_after_development(self, initial_game):
        """King can move after pieces develop."""
        gs = initial_game
        # Clear the way for king side castle or f1 move
        gs.board[7][5] = "--"  # Remove f1 bishop
        gs.board[7][6] = "--"  # Remove g1 knight
        # Now king can castle or move to f1
        moves = count_moves_from_square(gs, 7, 4)
        assert moves > 0


class TestMoveCount:
    """Tests for move count in various positions."""
    
    def test_initial_position_move_count(self, initial_game):
        """Initial position has exactly 20 legal moves."""
        gs = initial_game
        valid_moves = gs.get_valid_moves()
        # 16 pawn moves + 4 knight moves = 20
        assert len(valid_moves) == 20
    
    def test_after_e4_black_has_20_moves(self, initial_game):
        """After 1.e4, black has 20 legal moves."""
        gs = initial_game
        make_move_from_notation(gs, (6, 4), (4, 4))  # e4
        valid_moves = gs.get_valid_moves()
        assert len(valid_moves) == 20
