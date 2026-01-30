"""
PGN (Portable Game Notation) parser for importing chess games.
"""
import re
from .chess_engine import GameState, Move


class PGNParser:
    """Parser for PGN format chess games."""
    
    # Mapping from file letters to column numbers
    FILE_TO_COL = {'a': 0, 'b': 1, 'c': 2, 'd': 3, 'e': 4, 'f': 5, 'g': 6, 'h': 7}
    COL_TO_FILE = {v: k for k, v in FILE_TO_COL.items()}
    
    # Mapping from rank numbers to row numbers (rank 1 = row 7, rank 8 = row 0)
    RANK_TO_ROW = {'1': 7, '2': 6, '3': 5, '4': 4, '5': 3, '6': 2, '7': 1, '8': 0}
    ROW_TO_RANK = {v: k for k, v in RANK_TO_ROW.items()}
    
    def __init__(self):
        self.headers = {}
        self.moves = []
        self.result = None
    
    def parse(self, pgn_text):
        """
        Parse a PGN string and extract headers and moves.
        
        :param pgn_text: PGN formatted string
        :return: self for chaining
        """
        self.headers = {}
        self.moves = []
        
        lines = pgn_text.strip().split('\n')
        
        # Parse headers
        movetext_start = 0
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('['):
                match = re.match(r'\[(\w+)\s+"(.*)"\]', line)
                if match:
                    self.headers[match.group(1)] = match.group(2)
            elif line and not line.startswith('['):
                movetext_start = i
                break
        
        # Parse moves (everything after headers)
        movetext = ' '.join(lines[movetext_start:])
        self._parse_movetext(movetext)
        
        return self
    
    def _parse_movetext(self, movetext):
        """Parse the movetext portion of PGN."""
        # Remove comments in braces
        movetext = re.sub(r'\{[^}]*\}', '', movetext)
        # Remove move numbers
        movetext = re.sub(r'\d+\.+', '', movetext)
        # Remove result at end
        movetext = re.sub(r'(1-0|0-1|1/2-1/2|\*)$', '', movetext)
        
        # Split into tokens
        tokens = movetext.split()
        
        self.moves = []
        for token in tokens:
            token = token.strip()
            if token and not token.startswith('$'):  # Skip NAG annotations
                self.moves.append(token)
    
    def find_move(self, gs, san_move):
        """
        Find the move in valid moves that matches the SAN notation.
        
        :param gs: Current GameState
        :param san_move: Move in Standard Algebraic Notation (e.g., "e4", "Nf3", "O-O")
        :return: Move object or None
        """
        valid_moves = gs.get_valid_moves()
        
        # Handle castling
        if san_move in ('O-O', '0-0'):
            # Kingside castling
            king_col = 4
            target_col = 6
            row = 7 if gs.white else 0
            for move in valid_moves:
                if move.isCastleMove and move.end_col == target_col:
                    return move
            return None
        
        if san_move in ('O-O-O', '0-0-0'):
            # Queenside castling
            king_col = 4
            target_col = 2
            row = 7 if gs.white else 0
            for move in valid_moves:
                if move.isCastleMove and move.end_col == target_col:
                    return move
            return None
        
        # Remove check/checkmate indicators
        san_move = san_move.rstrip('+#')
        
        # Handle promotion
        promotion_piece = None
        if '=' in san_move:
            san_move, promotion_piece = san_move.split('=')
        
        # Parse the move
        piece_type = 'P'  # Default to pawn
        from_file = None
        from_rank = None
        is_capture = 'x' in san_move
        san_move = san_move.replace('x', '')
        
        # Determine piece type and destination
        if san_move[0].isupper():
            piece_type = san_move[0]
            san_move = san_move[1:]
        
        # Extract destination (last 2 characters)
        if len(san_move) >= 2:
            dest_file = san_move[-2]
            dest_rank = san_move[-1]
            if dest_file in self.FILE_TO_COL and dest_rank in self.RANK_TO_ROW:
                dest_col = self.FILE_TO_COL[dest_file]
                dest_row = self.RANK_TO_ROW[dest_rank]
            else:
                return None
            
            # Check for disambiguation (remaining characters)
            disambiguation = san_move[:-2]
            if len(disambiguation) >= 1:
                if disambiguation[0] in self.FILE_TO_COL:
                    from_file = self.FILE_TO_COL[disambiguation[0]]
                elif disambiguation[0] in self.RANK_TO_ROW:
                    from_rank = self.RANK_TO_ROW[disambiguation[0]]
            if len(disambiguation) == 2:
                from_file = self.FILE_TO_COL[disambiguation[0]]
                from_rank = self.RANK_TO_ROW[disambiguation[1]]
        else:
            return None
        
        # Find matching move
        color = 'w' if gs.white else 'b'
        piece_code = color + piece_type
        
        for move in valid_moves:
            if move.pieceMoved == piece_code:
                if move.end_row == dest_row and move.end_col == dest_col:
                    # Check disambiguation
                    if from_file is not None and move.start_col != from_file:
                        continue
                    if from_rank is not None and move.start_row != from_rank:
                        continue
                    return move
        
        return None
    
    def play_game(self, gs=None):
        """
        Play through all moves in the parsed game.
        
        :param gs: Optional GameState to use (creates new one if None)
        :return: tuple (GameState after all moves, list of move objects)
        """
        if gs is None:
            gs = GameState()
        
        played_moves = []
        for i, san_move in enumerate(self.moves):
            move = self.find_move(gs, san_move)
            if move is None:
                raise ValueError(f"Could not find move '{san_move}' at position {i+1}")
            gs.make_move(move)
            played_moves.append(move)
        
        return gs, played_moves


def parse_pgn(pgn_text):
    """
    Convenience function to parse PGN text.
    
    :param pgn_text: PGN formatted string
    :return: PGNParser instance
    """
    return PGNParser().parse(pgn_text)


def play_pgn_game(pgn_text):
    """
    Parse and play through a PGN game.
    
    :param pgn_text: PGN formatted string
    :return: tuple (final GameState, list of moves, PGNParser with headers)
    """
    parser = parse_pgn(pgn_text)
    gs, moves = parser.play_game()
    return gs, moves, parser
