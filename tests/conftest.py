"""
Shared pytest fixtures for chess engine tests.
"""


import pytest
from chess_engine.engine.v2.chess_engine import GameState, Move


@pytest.fixture
def initial_game():
    """Create a fresh game state with initial position."""
    return GameState()


@pytest.fixture
def empty_board_game():
    """Create a game state with an empty board (only kings)."""
    gs = GameState()
    # Clear the board
    for row in range(8):
        for col in range(8):
            gs.board[row][col] = "--"
    # Place kings at e1 and e8
    gs.board[0][4] = "bK"
    gs.board[7][4] = "wK"
    gs.white_king = (7, 4)
    gs.black_king = (0, 4)
    return gs


def make_move_from_notation(gs, start, end):
    """
    Helper to make a move from algebraic-style notation.
    start/end are tuples like (row, col) where row 0 = rank 8, col 0 = file a.
    """
    valid_moves = gs.get_valid_moves()
    for move in valid_moves:
        if (move.start_row, move.start_col) == start and (move.end_row, move.end_col) == end:
            gs.make_move(move)
            return move
    return None


def find_move(gs, start, end):
    """Find a move in valid moves list without making it."""
    valid_moves = gs.get_valid_moves()
    for move in valid_moves:
        if (move.start_row, move.start_col) == start and (move.end_row, move.end_col) == end:
            return move
    return None


def move_exists(gs, start, end):
    """Check if a move exists in valid moves."""
    return find_move(gs, start, end) is not None


def count_moves_from_square(gs, row, col):
    """Count how many valid moves originate from a square."""
    valid_moves = gs.get_valid_moves()
    return sum(1 for m in valid_moves if m.start_row == row and m.start_col == col)


# Common board setups as fixtures
@pytest.fixture
def scholars_mate_position():
    """Position right before Scholar's Mate."""
    gs = GameState()
    # 1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6??
    moves = [
        ((6, 4), (4, 4)),  # e4
        ((1, 4), (3, 4)),  # e5
        ((7, 5), (4, 2)),  # Bc4
        ((0, 1), (2, 2)),  # Nc6
        ((7, 3), (3, 7)),  # Qh5
        ((0, 6), (2, 5)),  # Nf6??
    ]
    for start, end in moves:
        make_move_from_notation(gs, start, end)
    return gs


@pytest.fixture  
def castling_available_position():
    """Position where castling is available for white."""
    gs = GameState()
    # Clear pieces between king and rooks
    gs.board[7][5] = "--"  # Remove bishop
    gs.board[7][6] = "--"  # Remove knight
    gs.board[7][1] = "--"  # Remove knight
    gs.board[7][2] = "--"  # Remove bishop
    gs.board[7][3] = "--"  # Remove queen
    return gs


@pytest.fixture
def en_passant_position():
    """Position where en passant is possible for white."""
    gs = GameState()
    # Set up white pawn on 5th rank, black pawn just moved 2 squares
    gs.board[6][4] = "--"  # Remove white e pawn from start
    gs.board[3][4] = "wP"  # Place white pawn on e5
    gs.board[1][3] = "--"  # Remove black d pawn from start  
    gs.board[3][3] = "bP"  # Place black pawn on d5 (just moved)
    gs.enpassant_possible = (2, 3)  # d6 is en passant target
    return gs


@pytest.fixture
def checkmate_position():
    """Simple back rank checkmate position."""
    gs = GameState()
    # Clear board
    for row in range(8):
        for col in range(8):
            gs.board[row][col] = "--"
    # Set up back rank mate
    gs.board[7][7] = "wK"  # White king in corner
    gs.board[7][6] = "wP"  # Pawns blocking escape
    gs.board[6][6] = "wP"
    gs.board[6][7] = "wP"
    gs.board[7][0] = "bR"  # Black rook delivering mate
    gs.board[0][4] = "bK"  # Black king
    gs.white_king = (7, 7)
    gs.black_king = (0, 4)
    return gs


@pytest.fixture
def stalemate_position():
    """Position where it's stalemate for white."""
    gs = GameState()
    # Clear board
    for row in range(8):
        for col in range(8):
            gs.board[row][col] = "--"
    # Classic stalemate: king in corner, queen trapping
    gs.board[0][0] = "wK"  # White king trapped
    gs.board[1][2] = "bQ"  # Queen controls escape squares
    gs.board[7][7] = "bK"  # Black king
    gs.white_king = (0, 0)
    gs.black_king = (7, 7)
    return gs
