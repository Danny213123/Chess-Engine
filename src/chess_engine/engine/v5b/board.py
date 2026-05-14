"""
V4d Board State - Bitboard-based Position Representation
Following Chess Programming Wiki (CPW) specifications.

The board is represented using 12 bitboards (one per piece type/color),
plus additional state for castling rights, en passant, and side to move.
"""

import numpy as np
from numba import njit, uint64, int32, boolean
from numba.experimental import jitclass
from numba import types

from chess_engine.engine.v5b.bitboard import (
    EMPTY, set_bit, clear_bit, get_bit, bitscan_forward, popcount, iter_bits,
    KNIGHT_ATTACKS, KING_ATTACKS, WHITE_PAWN_ATTACKS, BLACK_PAWN_ATTACKS,
    RANK_1, RANK_2, RANK_7, RANK_8, FILE_A, FILE_H,
    A1, B1, C1, D1, E1, F1, G1, H1,
    A8, B8, C8, D8, E8, F8, G8, H8
)
from chess_engine.engine.v5b.magic import get_rook_attacks, get_bishop_attacks, get_queen_attacks


# =============================================================================
# PIECE INDICES
# =============================================================================

WP, WN, WB, WR, WQ, WK = 0, 1, 2, 3, 4, 5  # White pieces
BP, BN, BB, BR, BQ, BK = 6, 7, 8, 9, 10, 11  # Black pieces

# Castling rights bits
CASTLE_WK = 1  # White kingside
CASTLE_WQ = 2  # White queenside
CASTLE_BK = 4  # Black kingside
CASTLE_BQ = 8  # Black queenside


# =============================================================================
# BOARD STATE CLASS
# =============================================================================

class BoardState:
    """
    Bitboard-based chess position.
    
    Attributes:
        pieces: 12 bitboards (WP, WN, WB, WR, WQ, WK, BP, BN, BB, BR, BQ, BK)
        white_occ: All white pieces
        black_occ: All black pieces
        all_occ: All pieces
        white_to_move: True if white to move
        castle_rights: 4-bit integer (KQkq)
        ep_square: En passant target square (-1 if none)
        halfmove: Halfmove clock for 50-move rule
        fullmove: Fullmove number
        hash: Zobrist hash of position
    """
    
    def __init__(self):
        # 12 piece bitboards
        self.pieces = np.zeros(12, dtype=np.uint64)
        
        # Occupancy bitboards (derived)
        self.white_occ = np.uint64(0)
        self.black_occ = np.uint64(0)
        self.all_occ = np.uint64(0)
        
        # Game state
        self.white_to_move = True
        self.castle_rights = CASTLE_WK | CASTLE_WQ | CASTLE_BK | CASTLE_BQ  # All rights
        self.ep_square = -1
        self.halfmove = 0
        self.fullmove = 1
        
        # Zobrist hash
        self.hash = np.uint64(0)
        
        # Move history for undo
        self.history = []
        
        # Set up starting position
        self._setup_start_position()
    
    def _setup_start_position(self):
        """Set up the standard chess starting position."""
        # Clear all
        self.pieces.fill(0)
        
        # Helper to set bit using pure Python (avoids numba signed issues)
        def set_bit_py(sq):
            return np.uint64(1 << sq)
        
        # White pawns (rank 2)
        self.pieces[WP] = RANK_2
        
        # Black pawns (rank 7)
        self.pieces[BP] = RANK_7
        
        # White pieces (rank 1)
        self.pieces[WR] = set_bit_py(A1) | set_bit_py(H1)
        self.pieces[WN] = set_bit_py(B1) | set_bit_py(G1)
        self.pieces[WB] = set_bit_py(C1) | set_bit_py(F1)
        self.pieces[WQ] = set_bit_py(D1)
        self.pieces[WK] = set_bit_py(E1)
        
        # Black pieces (rank 8)
        self.pieces[BR] = set_bit_py(A8) | set_bit_py(H8)
        self.pieces[BN] = set_bit_py(B8) | set_bit_py(G8)
        self.pieces[BB] = set_bit_py(C8) | set_bit_py(F8)
        self.pieces[BQ] = set_bit_py(D8)
        self.pieces[BK] = set_bit_py(E8)
        
        # Update occupancy
        self._update_occupancy()
        
        # Reset state
        self.white_to_move = True
        self.castle_rights = CASTLE_WK | CASTLE_WQ | CASTLE_BK | CASTLE_BQ
        self.ep_square = -1
        self.halfmove = 0
        self.fullmove = 1
        self.history = []
    
    def _update_occupancy(self):
        """Update derived occupancy bitboards."""
        self.white_occ = np.uint64(0)
        self.black_occ = np.uint64(0)
        
        for i in range(6):
            self.white_occ |= self.pieces[i]
            self.black_occ |= self.pieces[i + 6]
        
        self.all_occ = self.white_occ | self.black_occ
    
    def copy(self):
        """Create a deep copy of the board state."""
        new_board = BoardState.__new__(BoardState)
        new_board.pieces = self.pieces.copy()
        new_board.white_occ = self.white_occ
        new_board.black_occ = self.black_occ
        new_board.all_occ = self.all_occ
        new_board.white_to_move = self.white_to_move
        new_board.castle_rights = self.castle_rights
        new_board.ep_square = self.ep_square
        new_board.halfmove = self.halfmove
        new_board.fullmove = self.fullmove
        new_board.hash = self.hash
        new_board.history = []  # Don't copy history for search
        return new_board
    
    # =========================================================================
    # PIECE QUERIES
    # =========================================================================
    
    def piece_at(self, sq):
        """Get the piece at a square. Returns (piece_type, is_white) or None."""
        mask = np.uint64(1) << np.uint64(sq)
        
        for i in range(12):
            if self.pieces[i] & mask:
                return (i % 6, i < 6)
        return None
    
    def is_square_attacked(self, sq, by_white):
        """Check if a square is attacked by the given side."""
        if by_white:
            # Attacked by white pawns?
            if BLACK_PAWN_ATTACKS[sq] & self.pieces[WP]:
                return True
            # Knights
            if KNIGHT_ATTACKS[sq] & self.pieces[WN]:
                return True
            # King
            if KING_ATTACKS[sq] & self.pieces[WK]:
                return True
            # Bishops/Queens (diagonals)
            diag_attacks = get_bishop_attacks(sq, self.all_occ)
            if diag_attacks & (self.pieces[WB] | self.pieces[WQ]):
                return True
            # Rooks/Queens (straights)
            straight_attacks = get_rook_attacks(sq, self.all_occ)
            if straight_attacks & (self.pieces[WR] | self.pieces[WQ]):
                return True
        else:
            # Attacked by black pawns?
            if WHITE_PAWN_ATTACKS[sq] & self.pieces[BP]:
                return True
            # Knights
            if KNIGHT_ATTACKS[sq] & self.pieces[BN]:
                return True
            # King
            if KING_ATTACKS[sq] & self.pieces[BK]:
                return True
            # Bishops/Queens
            diag_attacks = get_bishop_attacks(sq, self.all_occ)
            if diag_attacks & (self.pieces[BB] | self.pieces[BQ]):
                return True
            # Rooks/Queens
            straight_attacks = get_rook_attacks(sq, self.all_occ)
            if straight_attacks & (self.pieces[BR] | self.pieces[BQ]):
                return True
        
        return False
    
    def is_in_check(self):
        """Check if the side to move is in check."""
        if self.white_to_move:
            king_sq = bitscan_forward(self.pieces[WK])
            return self.is_square_attacked(king_sq, by_white=False)
        else:
            king_sq = bitscan_forward(self.pieces[BK])
            return self.is_square_attacked(king_sq, by_white=True)
    
    # =========================================================================
    # FEN CONVERSION
    # =========================================================================
    
    def from_fen(self, fen):
        """Load position from FEN string."""
        parts = fen.split()
        board_str = parts[0]
        
        # Clear board
        self.pieces.fill(0)
        
        # Piece mapping
        piece_map = {
            'P': WP, 'N': WN, 'B': WB, 'R': WR, 'Q': WQ, 'K': WK,
            'p': BP, 'n': BN, 'b': BB, 'r': BR, 'q': BQ, 'k': BK
        }
        
        sq = 56  # Start at a8
        for char in board_str:
            if char == '/':
                sq -= 16  # Move to next rank down
            elif char.isdigit():
                sq += int(char)
            else:
                # Use pure Python bit operation to avoid numba signed issues
                self.pieces[piece_map[char]] = np.uint64(int(self.pieces[piece_map[char]]) | (1 << sq))
                sq += 1
        
        # Side to move
        self.white_to_move = parts[1] == 'w' if len(parts) > 1 else True
        
        # Castling rights
        self.castle_rights = 0
        if len(parts) > 2:
            if 'K' in parts[2]: self.castle_rights |= CASTLE_WK
            if 'Q' in parts[2]: self.castle_rights |= CASTLE_WQ
            if 'k' in parts[2]: self.castle_rights |= CASTLE_BK
            if 'q' in parts[2]: self.castle_rights |= CASTLE_BQ
        
        # En passant
        if len(parts) > 3 and parts[3] != '-':
            file = ord(parts[3][0]) - ord('a')
            rank = int(parts[3][1]) - 1
            self.ep_square = rank * 8 + file
        else:
            self.ep_square = -1
        
        # Halfmove and fullmove
        self.halfmove = int(parts[4]) if len(parts) > 4 else 0
        self.fullmove = int(parts[5]) if len(parts) > 5 else 1
        
        self._update_occupancy()
        self.history = []
    
    def to_fen(self):
        """Convert position to FEN string."""
        piece_chars = ['P', 'N', 'B', 'R', 'Q', 'K', 'p', 'n', 'b', 'r', 'q', 'k']
        
        fen_parts = []
        
        # Board
        board_str = ""
        for rank in range(7, -1, -1):
            empty = 0
            for file in range(8):
                sq = rank * 8 + file
                piece = None
                for i in range(12):
                    if get_bit(self.pieces[i], sq):
                        piece = piece_chars[i]
                        break
                
                if piece:
                    if empty > 0:
                        board_str += str(empty)
                        empty = 0
                    board_str += piece
                else:
                    empty += 1
            
            if empty > 0:
                board_str += str(empty)
            if rank > 0:
                board_str += '/'
        
        fen_parts.append(board_str)
        
        # Side to move
        fen_parts.append('w' if self.white_to_move else 'b')
        
        # Castling
        castle_str = ""
        if self.castle_rights & CASTLE_WK: castle_str += 'K'
        if self.castle_rights & CASTLE_WQ: castle_str += 'Q'
        if self.castle_rights & CASTLE_BK: castle_str += 'k'
        if self.castle_rights & CASTLE_BQ: castle_str += 'q'
        fen_parts.append(castle_str if castle_str else '-')
        
        # En passant
        if self.ep_square >= 0:
            file = chr(ord('a') + (self.ep_square % 8))
            rank = str((self.ep_square // 8) + 1)
            fen_parts.append(file + rank)
        else:
            fen_parts.append('-')
        
        # Halfmove and fullmove
        fen_parts.append(str(self.halfmove))
        fen_parts.append(str(self.fullmove))
        
        return ' '.join(fen_parts)
    
    def __str__(self):
        """Pretty print the board."""
        piece_chars = [' P', ' N', ' B', ' R', ' Q', ' K', ' p', ' n', ' b', ' r', ' q', ' k']
        
        result = "\n  +---+---+---+---+---+---+---+---+\n"
        for rank in range(7, -1, -1):
            result += f"{rank + 1} |"
            for file in range(8):
                sq = rank * 8 + file
                piece = " ."
                for i in range(12):
                    if get_bit(self.pieces[i], sq):
                        piece = piece_chars[i]
                        break
                result += f"{piece} |"
            result += "\n  +---+---+---+---+---+---+---+---+\n"
        result += "    a   b   c   d   e   f   g   h\n"
        result += f"\nFEN: {self.to_fen()}\n"
        return result
