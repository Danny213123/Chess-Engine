class Move:

    def __init__(self, start_sq, end_sq, board, enpassant_move=False, isCastleMove=False):
        self.start_row = start_sq[0]
        self.start_col = start_sq[1]
        self.end_row = end_sq[0]
        self.end_col = end_sq[1]
        self.pieceCaptured = board[self.end_row][self.end_col]

        self.pawn_promotion = False

        self.moveID = self.start_row * 1000 + self.start_col * 100 + self.end_row * 10 + self.end_col

        self.pieceMoved = board[self.start_row][self.start_col]
        self.pieceEnd = board[self.end_row][self.end_col]

        if (self.pieceMoved == "wP" and self.end_row == 0) or (self.pieceMoved == "bP" and self.end_row == 7):
            self.pawn_promotion = True

        self.enpassant_move = enpassant_move

        if self.enpassant_move:
            self.pieceEnd = "bP" if self.pieceMoved[0] == "w" else "wP"

        self.isCastleMove = isCastleMove

    def __eq__(self, other):
        if isinstance(other, Move):
            return self.moveID == other.moveID
        return False

    def __hash__(self):
        return self.moveID

    def print(self):
        print(self.pieceMoved, self.pieceEnd, (self.start_row, self.start_col), (self.end_row, self.end_col),
              self.moveID)

    def __str__(self):
        # Convert coordinates to algebraic notation
        # (7, 0) -> a1
        # (0, 7) -> h8
        
        ranks_to_rows = {"1": 7, "2": 6, "3": 5, "4": 4, "5": 3, "6": 2, "7": 1, "8": 0}
        rows_to_ranks = {v: k for k, v in ranks_to_rows.items()}
        cols_to_files = {0: "a", 1: "b", 2: "c", 3: "d", 4: "e", 5: "f", 6: "g", 7: "h"}
        
        start = cols_to_files[self.start_col] + rows_to_ranks[self.start_row]
        end = cols_to_files[self.end_col] + rows_to_ranks[self.end_row]
        
        return start + end
