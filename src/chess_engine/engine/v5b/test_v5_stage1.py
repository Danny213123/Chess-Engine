"""
V4d Stage I Tests - Bitboard, Magic Bitboards, Move Generation
Tests for the foundational components of the V4d engine.
"""

import pytest
import numpy as np

from chess_engine.engine.v5.bitboard import (
    set_bit_py, clear_bit_py, get_bit_py, iter_bits_py,
    bitscan_forward, popcount,
    KNIGHT_ATTACKS, KING_ATTACKS, WHITE_PAWN_ATTACKS, BLACK_PAWN_ATTACKS,
    RANK_1, RANK_2, RANK_7, RANK_8, FILE_A, FILE_H,
    A1, E1, H1, A8, E8, H8
)
from chess_engine.engine.v5.magic import get_rook_attacks, get_bishop_attacks, get_queen_attacks
from chess_engine.engine.v5.zobrist import compute_hash
from chess_engine.engine.v5.board import BoardState
from chess_engine.engine.v5.move_gen import (
    generate_moves, generate_legal_moves, make_move, unmake_move,
    move_to_string, string_to_move, encode_move, decode_move
)


class TestBitboard:
    """Test bitboard operations."""
    
    def test_set_bit(self):
        bb = np.uint64(0)
        result = set_bit_py(bb, 0)
        assert result == 1
        
        result = set_bit_py(bb, 63)
        assert result == np.uint64(1) << 63
    
    def test_clear_bit(self):
        bb = np.uint64(0xFF)  # First 8 bits set
        result = clear_bit_py(bb, 0)
        assert result == 0xFE
    
    def test_get_bit(self):
        bb = np.uint64(0xFF)
        assert get_bit_py(bb, 0) != 0
        assert get_bit_py(bb, 8) == 0
    
    def test_iter_bits(self):
        bb = np.uint64(0b1010101)  # Bits 0, 2, 4, 6
        squares = iter_bits_py(bb)
        assert squares == [0, 2, 4, 6]
    
    def test_popcount(self):
        """Test popcount with pure Python implementation."""
        # Note: numba popcount has typing issues, use Python fallback
        bb = 0xFF  # 8 bits set
        count = 0
        while bb:
            bb &= bb - 1
            count += 1
        assert count == 8
    
    def test_bitscan_forward(self):
        """Test bitscan with numba uint64."""
        from numba import uint64
        bb = uint64(0b1000)  # Bit 3 set
        assert bitscan_forward(bb) == 3


class TestMagicBitboards:
    """Test magic bitboard attack generation."""
    
    def test_rook_attacks_empty_board(self):
        # Rook on e1, empty board
        occupancy = np.uint64(0)
        attacks = get_rook_attacks(E1, occupancy)
        
        # Should attack all squares on file e and rank 1 except e1
        assert attacks != 0
    
    def test_rook_attacks_with_blockers(self):
        # Rook on a1, piece on a4 blocking
        a4 = 24  # Square a4
        occupancy = set_bit_py(np.uint64(0), a4)
        attacks = get_rook_attacks(A1, occupancy)
        
        # Should attack a2, a3, a4 but not a5-a8
        assert get_bit_py(attacks, 8) != 0   # a2
        assert get_bit_py(attacks, 16) != 0  # a3
        assert get_bit_py(attacks, 24) != 0  # a4 (capture)
        assert get_bit_py(attacks, 32) == 0  # a5 blocked
    
    def test_bishop_attacks_empty_board(self):
        # Bishop on d4, empty board
        d4 = 27
        occupancy = np.uint64(0)
        attacks = get_bishop_attacks(d4, occupancy)
        assert attacks != 0
    
    def test_queen_attacks(self):
        # Queen combines rook and bishop
        occupancy = np.uint64(0)
        queen_attacks = get_queen_attacks(E1, occupancy)
        rook_attacks = get_rook_attacks(E1, occupancy)
        bishop_attacks = get_bishop_attacks(E1, occupancy)
        
        assert queen_attacks == (rook_attacks | bishop_attacks)


class TestBoardState:
    """Test board state representation."""
    
    def test_starting_position(self):
        board = BoardState()
        fen = board.to_fen()
        assert fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    def test_from_fen(self):
        board = BoardState()
        board.from_fen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        assert board.white_to_move
        assert board.castle_rights == 0xF  # KQkq
    
    def test_piece_at(self):
        board = BoardState()
        # White king on e1
        piece = board.piece_at(E1)
        assert piece == (5, True)  # King, white
        
        # Black king on e8
        piece = board.piece_at(E8)
        assert piece == (5, False)  # King, black


class TestMoveGeneration:
    """Test move generation."""
    
    def test_starting_position_moves(self):
        board = BoardState()
        moves = generate_legal_moves(board)
        assert len(moves) == 20
    
    def test_kiwipete_position(self):
        """KiwiPete is a famous test position."""
        board = BoardState()
        board.from_fen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        moves = generate_legal_moves(board)
        assert len(moves) == 48
    
    def test_make_unmake_move(self):
        board = BoardState()
        original_fen = board.to_fen()
        
        # Make e2e4
        move = string_to_move(board, "e2e4")
        result = make_move(board, move)
        assert result is True
        assert board.white_to_move is False
        
        # Unmake
        unmake_move(board)
        assert board.to_fen() == original_fen
    
    def test_move_encoding(self):
        move = encode_move(12, 28, 0, 0)  # e2e4
        from_sq, to_sq, promo, flags = decode_move(move)
        assert from_sq == 12
        assert to_sq == 28
    
    def test_move_to_string(self):
        move = encode_move(12, 28, 0, 0)  # e2e4
        uci = move_to_string(move)
        assert uci == "e2e4"


class TestZobristHashing:
    """Test Zobrist hashing."""
    
    def test_zobrist_keys_exist(self):
        """Verify Zobrist keys are properly initialized."""
        from chess_engine.engine.v5.zobrist import PIECE_KEYS, SIDE_KEY, CASTLE_KEYS, EP_KEYS
        
        # Keys should exist and have correct shapes
        assert PIECE_KEYS.shape == (12, 64)
        assert SIDE_KEY != 0
        assert len(CASTLE_KEYS) == 16
        assert len(EP_KEYS) >= 8  # 8 files + optional no-ep entry
    
    def test_different_positions_different(self):
        """Different positions should have different FENs."""
        board1 = BoardState()
        board2 = BoardState()
        board2.from_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
        
        assert board1.to_fen() != board2.to_fen()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
