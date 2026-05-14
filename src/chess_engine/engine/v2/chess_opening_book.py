# Opening Book - Coordinate Notation
# All moves use coordinate format: "e2e4" (not SAN like "e4" or "Nf3")
# Reference: https://www.chessprogramming.org/Opening_Book

import random

class OpeningBook:
    def __init__(self):
        # Dictionary: FEN board position -> list of good moves (coordinate notation)
        self.book = {
            # ================================================================
            # STARTING POSITION
            # ================================================================
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR": [
                "e2e4", "d2d4", "g1f3", "c2c4"  # Main openings
            ],

            # ================================================================
            # 1.e4 RESPONSES (Black to move)
            # ================================================================
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR": [
                "e7e5",  # Open Game
                "c7c5",  # Sicilian
                "e7e6",  # French
                "c7c6",  # Caro-Kann
                "d7d5",  # Scandinavian
                "g8f6",  # Alekhine
            ],

            # ================================================================
            # ITALIAN GAME / RUY LOPEZ LINES
            # ================================================================
            # 1.e4 e5
            "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR": [
                "g1f3",  # Main line
            ],
            # 1.e4 e5 2.Nf3
            "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R": [
                "b8c6",  # Main defense
            ],
            # 1.e4 e5 2.Nf3 Nc6
            "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R": [
                "f1b5",  # Ruy Lopez
                "f1c4",  # Italian Game
                "d2d4",  # Scotch Game
            ],
            # Ruy Lopez: 1.e4 e5 2.Nf3 Nc6 3.Bb5
            "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R": [
                "a7a6",  # Morphy Defense
                "g8f6",  # Berlin Defense
                "f7f5",  # Schliemann
            ],
            # Ruy Lopez Morphy: 3...a6
            "r1bqkbnr/1ppp1ppp/p1n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R": [
                "b5a4",  # Main line
            ],
            # Italian Game: 1.e4 e5 2.Nf3 Nc6 3.Bc4
            "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R": [
                "f8c5",  # Giuoco Piano
                "g8f6",  # Two Knights
            ],

            # ================================================================
            # SICILIAN DEFENSE
            # ================================================================
            # 1.e4 c5
            "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR": [
                "g1f3",  # Open Sicilian
                "b1c3",  # Closed Sicilian
                "c2c3",  # Alapin
            ],
            # 1.e4 c5 2.Nf3
            "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R": [
                "d7d6",  # Najdorf/Dragon setup
                "b8c6",  # Classical
                "e7e6",  # Scheveningen/Paulsen
            ],
            # 1.e4 c5 2.Nf3 d6
            "rnbqkbnr/pp2pppp/3p4/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R": [
                "d2d4",  # Open Sicilian main line
            ],
            # 1.e4 c5 2.Nf3 d6 3.d4
            "rnbqkbnr/pp2pppp/3p4/2p5/3PP3/5N2/PPP2PPP/RNBQKB1R": [
                "c5d4",  # Capture
            ],
            # 1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4
            "rnbqkbnr/pp2pppp/3p4/8/3NP3/8/PPP2PPP/RNBQKB1R": [
                "g8f6",  # Najdorf / Dragon / Classical
            ],
            # Sicilian Najdorf: 4...Nf6 5.Nc3
            "rnbqkb1r/pp2pppp/3p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R": [
                "a7a6",  # Najdorf
                "g7g6",  # Dragon
                "e7e6",  # Scheveningen
            ],

            # ================================================================
            # FRENCH DEFENSE
            # ================================================================
            # 1.e4 e6
            "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR": [
                "d2d4",  # Main line
            ],
            # 1.e4 e6 2.d4
            "rnbqkbnr/pppp1ppp/4p3/8/3PP3/8/PPP2PPP/RNBQKBNR": [
                "d7d5",  # Main defense
            ],
            # 1.e4 e6 2.d4 d5
            "rnbqkbnr/ppp2ppp/4p3/3p4/3PP3/8/PPP2PPP/RNBQKBNR": [
                "b1c3",  # Classical
                "e4e5",  # Advance
                "b1d2",  # Tarrasch
            ],

            # ================================================================
            # CARO-KANN DEFENSE
            # ================================================================
            # 1.e4 c6
            "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR": [
                "d2d4",  # Main line
            ],
            # 1.e4 c6 2.d4
            "rnbqkbnr/pp1ppppp/2p5/8/3PP3/8/PPP2PPP/RNBQKBNR": [
                "d7d5",  # Main defense
            ],
            # 1.e4 c6 2.d4 d5
            "rnbqkbnr/pp2pppp/2p5/3p4/3PP3/8/PPP2PPP/RNBQKBNR": [
                "b1c3",  # Classical
                "e4e5",  # Advance
            ],

            # ================================================================
            # 1.d4 RESPONSES (Black to move)
            # ================================================================
            "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR": [
                "d7d5",  # Queen's Gambit territory
                "g8f6",  # Indian Defenses
            ],

            # ================================================================
            # QUEEN'S GAMBIT
            # ================================================================
            # 1.d4 d5
            "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR": [
                "c2c4",  # Queen's Gambit
            ],
            # 1.d4 d5 2.c4
            "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR": [
                "e7e6",  # QGD
                "c7c6",  # Slav
                "d5c4",  # QGA
            ],
            # QGD: 1.d4 d5 2.c4 e6
            "rnbqkbnr/ppp2ppp/4p3/3p4/2PP4/8/PP2PPPP/RNBQKBNR": [
                "b1c3",  # Main line
            ],
            # Slav: 1.d4 d5 2.c4 c6
            "rnbqkbnr/pp2pppp/2p5/3p4/2PP4/8/PP2PPPP/RNBQKBNR": [
                "g1f3",  # Main line
                "b1c3",  # Classical
            ],

            # ================================================================
            # INDIAN DEFENSES
            # ================================================================
            # 1.d4 Nf6
            "rnbqkb1r/pppppppp/5n2/8/3P4/8/PPP1PPPP/RNBQKBNR": [
                "c2c4",  # Main continuation
            ],
            # 1.d4 Nf6 2.c4
            "rnbqkb1r/pppppppp/5n2/8/2PP4/8/PP2PPPP/RNBQKBNR": [
                "e7e6",  # Nimzo/Queen's Indian
                "g7g6",  # King's Indian
                "c7c5",  # Benoni
            ],
            # King's Indian: 1.d4 Nf6 2.c4 g6
            "rnbqkb1r/pppppp1p/5np1/8/2PP4/8/PP2PPPP/RNBQKBNR": [
                "b1c3",  # Main line
            ],
            # King's Indian: 2...g6 3.Nc3
            "rnbqkb1r/pppppp1p/5np1/8/2PP4/2N5/PP2PPPP/R1BQKBNR": [
                "f8g7",  # Fianchetto
            ],
            # Nimzo-Indian: 1.d4 Nf6 2.c4 e6 3.Nc3
            "rnbqkb1r/pppp1ppp/4pn2/8/2PP4/2N5/PP2PPPP/R1BQKBNR": [
                "f8b4",  # Nimzo-Indian
            ],

            # ================================================================
            # LONDON SYSTEM (Popular at club level)
            # ================================================================
            # 1.d4 d5 2.Bf4 (or 1.d4 Nf6 2.Bf4)
            "rnbqkbnr/ppp1pppp/8/3p4/3P1B2/8/PPP1PPPP/RN1QKBNR": [
                "g8f6",
                "e7e6",
                "c7c5",
            ],

            # ================================================================
            # ENGLISH OPENING
            # ================================================================
            # 1.c4
            "rnbqkbnr/pppppppp/8/8/2P5/8/PP1PPPPP/RNBQKBNR": [
                "e7e5",  # Reversed Sicilian
                "c7c5",  # Symmetrical
                "g8f6",  # Indian
            ],

            # ================================================================
            # RETI OPENING
            # ================================================================
            # 1.Nf3
            "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R": [
                "d7d5",
                "g8f6",
                "c7c5",
            ],
        }

    def get_move(self, fen):
        """
        Look up position in opening book.
        Returns list of good moves, or None if not in book.
        """
        # Extract just the board position (ignore castling rights, etc.)
        fen_board = fen.split(" ")[0] if " " in fen else fen

        if fen_board in self.book:
            return self.book[fen_board]
        
        return None
    
    def get_random_book_move(self, fen):
        """
        Get a random move from the book for this position.
        Returns None if position not in book.
        """
        moves = self.get_move(fen)
        if moves:
            return random.choice(moves)
        return None
