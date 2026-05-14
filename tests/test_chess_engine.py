"""
Tests for the chess engine core functionality.
"""


from chess_engine.engine.v2.chess_engine import GameState, Move


class TestGameState:
    """Tests for GameState class."""
    
    def test_initial_board_setup(self):
        """Test that the initial board is set up correctly."""
        gs = GameState()
        
        # Check white pieces in correct positions
        assert gs.board[7][0] == "wR"
        assert gs.board[7][1] == "wN"
        assert gs.board[7][2] == "wB"
        assert gs.board[7][3] == "wQ"
        assert gs.board[7][4] == "wK"
        assert gs.board[7][5] == "wB"
        assert gs.board[7][6] == "wN"
        assert gs.board[7][7] == "wR"
        
        # Check white pawns
        for col in range(8):
            assert gs.board[6][col] == "wP"
        
        # Check black pieces in correct positions
        assert gs.board[0][0] == "bR"
        assert gs.board[0][1] == "bN"
        assert gs.board[0][2] == "bB"
        assert gs.board[0][3] == "bQ"
        assert gs.board[0][4] == "bK"
        assert gs.board[0][5] == "bB"
        assert gs.board[0][6] == "bN"
        assert gs.board[0][7] == "bR"
        
        # Check black pawns
        for col in range(8):
            assert gs.board[1][col] == "bP"
        
        # Check empty squares
        for row in range(2, 6):
            for col in range(8):
                assert gs.board[row][col] == "--"

    def test_initial_white_to_move(self):
        """Test that white moves first."""
        gs = GameState()
        assert gs.white is True

    def test_get_valid_moves_initial_position(self):
        """Test that valid moves are generated for initial position."""
        gs = GameState()
        valid_moves = gs.get_valid_moves()
        
        # In the starting position, white has 20 possible moves
        # 16 pawn moves (2 per pawn) + 4 knight moves (2 per knight)
        assert len(valid_moves) == 20

    def test_make_move(self):
        """Test making a move updates the board correctly."""
        gs = GameState()
        valid_moves = gs.get_valid_moves()
        
        # Find e2-e4 move
        e2_e4 = None
        for move in valid_moves:
            if move.start_row == 6 and move.start_col == 4 and move.end_row == 4 and move.end_col == 4:
                e2_e4 = move
                break
        
        assert e2_e4 is not None
        gs.make_move(e2_e4)
        
        # Check the move was made
        assert gs.board[6][4] == "--"
        assert gs.board[4][4] == "wP"
        assert gs.white is False

    def test_undo_move(self):
        """Test undoing a move restores the board."""
        gs = GameState()
        valid_moves = gs.get_valid_moves()
        
        # Make e2-e4 move
        e2_e4 = None
        for move in valid_moves:
            if move.start_row == 6 and move.start_col == 4 and move.end_row == 4 and move.end_col == 4:
                e2_e4 = move
                break
        
        gs.make_move(e2_e4)
        gs.undo_move()
        
        # Check the move was undone
        assert gs.board[6][4] == "wP"
        assert gs.board[4][4] == "--"
        assert gs.white is True

    def test_get_fen_initial_position(self):
        """Test FEN generation for initial position."""
        gs = GameState()
        fen = gs.get_fen()
        
        # Initial position FEN (position part only)
        assert fen.startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR")


class TestMove:
    """Tests for Move class."""
    
    def test_move_notation(self):
        """Test move notation generation."""
        gs = GameState()
        move = Move((6, 4), (4, 4), gs.board)
        
        # Check start and end positions are recorded
        assert move.start_row == 6
        assert move.start_col == 4
        assert move.end_row == 4
        assert move.end_col == 4
        assert move.pieceMoved == "wP"
        assert move.pieceCaptured == "--"

    def test_move_equality(self):
        """Test that two identical moves are equal."""
        gs = GameState()
        move1 = Move((6, 4), (4, 4), gs.board)
        move2 = Move((6, 4), (4, 4), gs.board)
        
        assert move1 == move2

    def test_move_inequality(self):
        """Test that different moves are not equal."""
        gs = GameState()
        move1 = Move((6, 4), (4, 4), gs.board)
        move2 = Move((6, 3), (4, 3), gs.board)
        
        assert move1 != move2
