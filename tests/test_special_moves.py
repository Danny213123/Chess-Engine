"""
Tests for special chess moves: castling, en passant, and pawn promotion.
"""
import pytest
from conftest import move_exists, make_move_from_notation, find_move
from engine.v2.chess_engine import GameState, Move


class TestCastling:
    """Tests for castling mechanics."""
    
    def test_white_kingside_castling_available(self, castling_available_position):
        """White can castle kingside when path is clear."""
        gs = castling_available_position
        # King at e1 (7, 4) should be able to castle to g1 (7, 6)
        assert move_exists(gs, (7, 4), (7, 6))
    
    def test_white_queenside_castling_available(self, castling_available_position):
        """White can castle queenside when path is clear."""
        gs = castling_available_position
        # King at e1 (7, 4) should be able to castle to c1 (7, 2)
        assert move_exists(gs, (7, 4), (7, 2))
    
    def test_rook_moves_during_castle(self, castling_available_position):
        """Rook moves correctly during castling."""
        gs = castling_available_position
        # Do kingside castle
        move = find_move(gs, (7, 4), (7, 6))
        assert move is not None
        assert move.isCastleMove
        gs.make_move(move)
        # Rook should be at f1 (7, 5)
        assert gs.board[7][5] == "wR"
        # King at g1
        assert gs.board[7][6] == "wK"


class TestEnPassant:
    """Tests for en passant capture."""
    
    def test_en_passant_capture_available(self):
        """En passant capture is available after enemy pawn double push."""
        gs = GameState()
        # 1. e4 a6 2. e5 d5 - now e5xd6 en passant SHOULD be available
        make_move_from_notation(gs, (6, 4), (4, 4))  # e4
        make_move_from_notation(gs, (1, 0), (2, 0))  # a6
        make_move_from_notation(gs, (4, 4), (3, 4))  # e5
        make_move_from_notation(gs, (1, 3), (3, 3))  # d5
        # Now e5xd6 en passant SHOULD be available
        assert move_exists(gs, (3, 4), (2, 3))


class TestPawnPromotion:
    """Tests for pawn promotion detection."""
    
    def test_promotion_flag_detected_in_move(self):
        """Pawn promotion flag is detected in Move object for pawns reaching last rank."""
        gs = GameState()
        # Create a move from a7 to a8 (simulating promotion scenario)
        # The engine's Move class should recognize this as promotion
        board_with_pawn = [row[:] for row in gs.board]
        board_with_pawn[1][0] = "wP"  # White pawn at a7
        board_with_pawn[0][0] = "--"  # a8 is empty
        
        move = Move((1, 0), (0, 0), board_with_pawn)
        # The Move class should detect this is a promotion
        assert move.pawn_promotion == True
    
    def test_no_promotion_in_middle_of_board(self):
        """No promotion flag for normal pawn moves."""
        gs = GameState()
        # Regular e4 move
        move = Move((6, 4), (4, 4), gs.board)
        assert move.pawn_promotion == False
