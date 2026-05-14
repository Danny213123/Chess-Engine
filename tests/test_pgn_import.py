"""
Tests for PGN parsing and real game imports.
"""
import pytest


from chess_engine.engine.v2.chess_engine import GameState
from chess_engine.engine.v2.pgn_parser import PGNParser, parse_pgn, play_pgn_game


# Real game: Magnus Carlsen vs Yaroslav Shevchenko, January 2026
CARLSEN_GAME = """
[Event "January 06 2026"]
[Site ""]
[Date "2026.01.06"]
[Round "?"]
[White "Magnus Carlsen"]
[Black "Yaroslav Shevchenko"]
[Result "1-0"]

1. e3 d5 2. Ke2 Nf6 3. f3 e5 4. Kf2 Nc6 5. Bb5 h5 6. b3 h4 7. Ne2 h3 8. g3 e4 9.
f4 Bg4 10. Bb2 a6 11. Bxc6+ bxc6 12. c4 Bc5 13. Bxf6 Qxf6 14. Nbc3 Bf3 15. cxd5
cxd5 16. b4 Ba7 17. Nxd5 Qd6 18. Ndc3 O-O-O 19. d4 exd3 20. Kxf3 Qc6+ 21. e4
dxe2 22. Qc2 f5 23. Rac1 Rhe8 24. Qxe2 Qg6 25. exf5 Qb6 26. Ne4 Kb8 27. Rhe1 Rd4
28. Qc2 Red8 29. Nc5 Ka8 30. Kg4 g6 31. Ne6 gxf5+ 32. Qxf5 Rg8+ 33. Kxh3 Rd7 34.
Nxc7+ 1-0
"""

# Simple Italian Game opening
ITALIAN_GAME = """
[Event "Test"]
[White "Player1"]
[Black "Player2"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 *
"""

# Fool's Mate
FOOLS_MATE = """
[Event "Fool's Mate"]
[Result "0-1"]

1. f3 e5 2. g4 Qh4# 0-1
"""


class TestPGNParser:
    """Tests for PGN parsing."""
    
    def test_parse_headers(self):
        """Parser extracts headers correctly."""
        parser = parse_pgn(CARLSEN_GAME)
        
        assert parser.headers['Event'] == "January 06 2026"
        assert parser.headers['White'] == "Magnus Carlsen"
        assert parser.headers['Black'] == "Yaroslav Shevchenko"
        assert parser.headers['Result'] == "1-0"
    
    def test_parse_moves(self):
        """Parser extracts moves correctly."""
        parser = parse_pgn(ITALIAN_GAME)
        
        assert 'e4' in parser.moves
        assert 'e5' in parser.moves
        assert 'Nf3' in parser.moves
        assert 'Nc6' in parser.moves
        assert 'Bc4' in parser.moves


class TestPGNMoveMatching:
    """Tests for matching SAN moves to engine moves."""
    
    def test_pawn_moves(self):
        """Parser finds pawn moves correctly."""
        parser = PGNParser()
        gs = GameState()
        
        move = parser.find_move(gs, 'e4')
        assert move is not None
        assert move.pieceMoved == 'wP'
        assert move.end_col == 4  # e-file
    
    def test_knight_moves(self):
        """Parser finds knight moves correctly."""
        parser = PGNParser()
        gs = GameState()
        
        move = parser.find_move(gs, 'Nf3')
        assert move is not None
        assert move.pieceMoved == 'wN'
        assert move.end_col == 5  # f-file


class TestPGNGamePlaythrough:
    """Tests for playing through complete games."""
    
    def test_italian_game_playthrough(self):
        """Play through Italian Game opening."""
        gs, moves, parser = play_pgn_game(ITALIAN_GAME)
        
        assert len(moves) == 5  # e4, e5, Nf3, Nc6, Bc4
        assert gs.board[4][2] == 'wB'  # Bishop on c4
    
    def test_fools_mate_playthrough(self):
        """Play through Fool's Mate and verify checkmate."""
        gs, moves, parser = play_pgn_game(FOOLS_MATE)
        
        assert len(moves) == 4
        gs.get_valid_moves()
        assert gs.check_mate
    
    def test_carlsen_game_first_10_moves(self):
        """Play through first 10 moves of Carlsen game."""
        parser = parse_pgn(CARLSEN_GAME)
        gs = GameState()
        
        # Play first 20 half-moves (10 full moves)
        for i, san in enumerate(parser.moves[:20]):
            move = parser.find_move(gs, san)
            assert move is not None, f"Move {i+1}: Could not find '{san}'"
            gs.make_move(move)
        
        # Verify game state is valid
        assert len(gs.move_log) == 20
    
    def test_carlsen_game_full_playthrough(self):
        """
        Play through the complete Magnus Carlsen game move-by-move.
        Verify all moves are valid and the result matches the PGN header.
        """
        parser = parse_pgn(CARLSEN_GAME)
        gs = GameState()
        
        # Play through ALL moves in the game
        for move_num, san in enumerate(parser.moves, 1):
            move = parser.find_move(gs, san)
            assert move is not None, f"Move {move_num}: Could not find '{san}'"
            
            # Verify the move is in the valid moves list
            valid_moves = gs.get_valid_moves()
            assert move in valid_moves, f"Move {move_num}: '{san}' not in valid moves"
            
            gs.make_move(move)
        
        # Verify all moves were played
        assert len(gs.move_log) == len(parser.moves), \
            f"Expected {len(parser.moves)} moves, got {len(gs.move_log)}"
        
        # Verify game result matches PGN header
        expected_result = parser.headers.get('Result', '*')
        
        # Check final game state
        gs.get_valid_moves()  # Update check/checkmate flags
        
        if expected_result == '1-0':
            # White wins - black should be in checkmate or resigned
            # Since this game ends with Nxc7+ (check), white is winning
            assert gs.in_check or gs.check_mate, \
                "Expected black to be in check or checkmate for white win"
        elif expected_result == '0-1':
            # Black wins - white should be in checkmate
            assert gs.check_mate and gs.white, \
                "Expected white to be in checkmate for black win"
        elif expected_result == '1/2-1/2':
            # Draw - could be stalemate or agreed draw
            pass  # No specific check for draws
        
        print(f"Game completed: {len(gs.move_log)} moves played")
        print(f"Result: {expected_result}")
        print(f"In check: {gs.in_check}, Checkmate: {gs.check_mate}")


class TestFEN:
    """Tests for FEN string generation."""
    
    def test_initial_position_fen(self):
        """Initial position generates correct FEN."""
        gs = GameState()
        fen = gs.get_fen()
        
        assert fen.startswith('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR')
        assert ' w ' in fen  # White to move
    
    def test_fen_changes_after_move(self):
        """FEN changes after a move is made."""
        gs = GameState()
        initial_fen = gs.get_fen()
        
        moves = gs.get_valid_moves()
        gs.make_move(moves[0])
        after_fen = gs.get_fen()
        
        assert initial_fen != after_fen
        assert ' b ' in after_fen  # Black to move
