import copy

from engine.chess_move import Move
from engine.chess_castling import castle_rights

class GameState:
    def __init__(self):

        self.board = [
            ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
            ["bP", "bP", "bP", "bP", "bP", "bP", "bP", "bP"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["wP", "wP", "wP", "wP", "wP", "wP", "wP", "wP"],
            ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"]
        ]

        self.move_function = {
            'P': self.get_pawn_moves, 'R': self.get_rook_moves, "N": self.get_knight_moves,
            'B': self.get_bishop_moves, 'Q': self.get_queen_moves, "K": self.get_king_moves
        }

        self.white_king = (7, 4)
        self.black_king = (0, 4)

        self.check_mate = False
        self.stale_mate = False
        self.in_check = False

        self.enpassant_possible = ()

        self.pins = []
        self.checks = []

        self.white = True
        self.move_log = []

        self.current_castling_rights = castle_rights(True, True, True, True)
        self.castling_rights_log = [castle_rights(self.current_castling_rights.wks, self.current_castling_rights.wqs,
                                                  self.current_castling_rights.bks, self.current_castling_rights.bqs)]

    # turn board into fen
    def get_fen(self):

        fen_char = {
            "wR": "R", "wN": "N", "wB": "B", "wQ": "Q", "wK": "K", "wP": "P",
            "bR": "r", "bN": "n", "bB": "b", "bQ": "q", "bK": "k", "bP": "p",
        }

        space = 0
        fen = ""
        for row in self.board:
            for col in row:
                if col == "--":
                    space += 1
                else:
                    if space != 0:
                        fen += str(space)
                        space = 0
                    fen += fen_char[col]
            if space != 0:
                fen += str(space)
                space = 0
            fen += "/"
        
        # remove last "/"
        fen = fen[:-1]

        if self.white:
            fen += " w "
        else:
            fen += " b "
        
        if self.current_castling_rights.wks:
            fen += "K"
        if self.current_castling_rights.wqs:
            fen += "Q"
        if self.current_castling_rights.bks:
            fen += "k"
        if self.current_castling_rights.bqs:
            fen += "q"
        return fen

    def make_move(self, move) -> None:
        '''
        Make a move and update board
        :param move: Move
        :return: bool
        '''

        # change current piece position to "--"
        self.board[move.start_row][move.start_col] = "--"

        # change end piece position to piece moved
        self.board[move.end_row][move.end_col] = move.pieceMoved

        # add move to move log
        self.move_log.append(move)

        # change turn
        self.white = not self.white

        # update king position
        if move.pieceMoved == "wK":
            self.white_king = (move.end_row, move.end_col)
        elif move.pieceMoved == "bK":
            self.black_king = (move.end_row, move.end_col)

        # pawn promotion
        if move.pawn_promotion:
            self.board[move.end_row][move.end_col] = move.pieceMoved[0] + "Q"

        # enpassant
        if move.enpassant_move:
            self.board[move.start_row][move.end_col] = "--"

        # update enpassant_possible
        if move.pieceMoved[1] == "P" and abs(move.start_row - move.end_row) == 2:
            self.enpassant_possible = ((move.start_row + move.end_row) // 2, move.end_col)
        else:
            self.enpassant_possible = ()

        # castle move
        if move.isCastleMove:
            if move.end_col - move.start_col == 2:
                self.board[move.end_row][move.end_col - 1] = self.board[move.end_row][move.end_col + 1]
                self.board[move.end_row][move.end_col + 1] = "--"
            else:  # Queen side
                self.board[move.end_row][move.end_col + 1] = self.board[move.end_row][move.end_col - 2]
                self.board[move.end_row][move.end_col - 2] = "--"

        # update castling rights
        self.update_castle_rights(move)
        self.castling_rights_log.append(
            castle_rights(self.current_castling_rights.wks, self.current_castling_rights.wqs,
                          self.current_castling_rights.bks, self.current_castling_rights.bqs))

    def undo_move(self) -> None:
        '''
        Undo last move
        :return: None
        '''

        # check if there is a move to undo
        if len(self.move_log) < 1:
            pass
        else:

            # remove last move from move log
            move = self.move_log.pop()
            self.board[move.start_row][move.start_col] = move.pieceMoved
            self.board[move.end_row][move.end_col] = move.pieceEnd

            # change turn
            self.white = not self.white

            # update king position
            if move.pieceMoved == "wK":
                self.white_king = (move.start_row, move.start_col)
            elif move.pieceMoved == "bK":
                self.black_king = (move.start_row, move.start_col)

            # undo enpassant
            if move.enpassant_move:
                self.board[move.end_row][move.end_col] = "--"
                self.board[move.start_row][move.end_col] = move.pieceEnd
                self.enpassant_possible = (move.end_row, move.end_col)

            # undo pawn promotion
            if move.pieceMoved[1] == "P" and abs(move.start_row - move.end_row) == 2:
                self.enpassant_possible = ()

            # undo castle move from log
            self.castling_rights_log.pop()
            self.current_castling_rights = copy.deepcopy(self.castling_rights_log[-1])

            # undo castle move
            if move.isCastleMove:
                if move.end_col - move.start_col == 2:
                    self.board[move.end_row][move.end_col + 1] = self.board[move.end_row][move.end_col - 1]
                    self.board[move.end_row][move.end_col - 1] = "--"
                else:  # Queen side
                    self.board[move.end_row][move.end_col - 2] = self.board[move.end_row][move.end_col + 1]
                    self.board[move.end_row][move.end_col + 1] = "--"

    def update_castle_rights(self, move) -> None:
        '''
        Update castling rights after a move
        :param move: Move
        :return: None
        '''

        # if white rook moves from the first rank
        if move.pieceEnd == 'wR':
            if move.end_row == 7:

                # if white rook moves from the first column
                if move.end_col == 0:
                    self.current_castling_rights.wqs = False

                # if white rook moves from the last column
                elif move.end_col == 7:
                    self.current_castling_rights.wks = False

        # if black rook moves from the last rank
        elif move.pieceEnd == 'bR':
            if move.end_row == 0:

                # if black rook moves from the first column
                if move.end_col == 0:
                    self.current_castling_rights.bqs = False

                # if black rook moves from the last column
                elif move.end_col == 7:
                    self.current_castling_rights.bks = False

        # if white king moves
        if move.pieceMoved == "wK":
            self.current_castling_rights.wks = False
            self.current_castling_rights.wqs = False

        # if black king moves
        elif move.pieceMoved == "bK":
            self.current_castling_rights.bks = False
            self.current_castling_rights.bqs = False

        # if white rook moves
        elif move.pieceMoved == "wR":
            if move.start_row == 7:

                # if white rook moves from the first column
                if move.start_col == 0:
                    self.current_castling_rights.wqs = False

                # if white rook moves from the last column
                elif move.start_col == 7:
                    self.current_castling_rights.wks = False

        # if black rook moves
        elif move.pieceMoved == "bR":
            if move.start_row == 0:

                # if black rook moves from the first column
                if move.start_col == 0:
                    self.current_castling_rights.bqs = False

                # if black rook moves from the last column
                elif move.start_col == 7:
                    self.current_castling_rights.bks = False

    def get_valid_moves(self) -> list:
        '''
        Get all valid moves
        :return: list
        '''

        # get all possible empassant moves
        temp_empassant_possible = self.enpassant_possible

        # get all possible castling moves
        temp_castle = castle_rights(self.current_castling_rights.wks, self.current_castling_rights.wqs,
                                    self.current_castling_rights.bks, self.current_castling_rights.bqs)

        moves = []

        # check for pins and checks
        self.in_check, self.pins, self.checks = self.check_for_pins_and_checks()

        # get king position
        if self.white:
            king_row, king_col = self.white_king[0], self.white_king[1]
        else:
            king_row, king_col = self.black_king[0], self.black_king[1]

        # if in check
        if self.in_check:

            # if only one piece is checking
            if len(self.checks) == 1:

                # get possible moves
                moves = self.get_possible_moves()
                check = self.checks[0]

                # get piece checking
                check_row = check[0]
                check_col = check[1]

                # get piece checking position
                piece_checking = self.board[check_row][check_col]
                valid_squares = []

                # if knight is checking
                if piece_checking[1] == "N":
                    valid_squares = [(check_row, check_col)]
                else:

                    # get direction of piece checking
                    for x in range(1, 8):
                        valid_square = (king_row + check[2] * x, king_col + check[3] * x)
                        valid_squares.append(valid_square)
                        if valid_square[0] == check_row and valid_square[1] == check_col:
                            break

                # get rid of moves that don't block check or move king
                for x in range(len(moves) - 1, -1, -1):
                    if moves[x].pieceMoved[1] != "K":
                        if not (moves[x].end_row, moves[x].end_col) in valid_squares:
                            moves.remove(moves[x])

            # if more than one piece is checking
            else:
                self.get_king_moves(king_row, king_col, moves)

        # if not in check
        else:
            moves = self.get_possible_moves()

        # get all castle moves
        if self.white:
            self.get_castle_moves(self.white_king[0], self.white_king[1], moves)
        else:
            self.get_castle_moves(self.black_king[0], self.black_king[1], moves)

        self.current_castling_rights = temp_castle
        self.enpassant_possible = temp_empassant_possible
        return moves

    def check_for_pins_and_checks(self) -> tuple:
        '''
        Check for pins and checks
        :return: bool, list, list
        '''
        pins, checks = [], []
        in_check = False

        # get king position
        if self.white:
            enemy, ally, start_row, start_col = "b", "w", self.white_king[0], self.white_king[1]
        else:
            enemy, ally, start_row, start_col = "w", "b", self.black_king[0], self.black_king[1]

        # check for pins and checks
        directions = ((-1, 0), (0, -1), (1, 0), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1))

        # check each direction index
        for index in range(len(directions)):

            # reset pins and set direction
            direction = directions[index]
            possible_pin = ()

            # for each col
            for col in range(1, 8):

                # get end position
                end_row = start_row + direction[0] * col
                end_col = start_col + direction[1] * col

                # if end position is on the board
                if 0 <= end_row < 8 and 0 <= end_col < 8:
                    end_piece = self.board[end_row][end_col]

                    # if end piece is an ally
                    if end_piece[0] == ally:
                        if possible_pin == ():
                            possible_pin = (end_row, end_col, direction[0], direction[1])
                        else:
                            break

                    # if end piece is an enemy
                    elif end_piece[0] == enemy:

                        # get type of end piece
                        type = end_piece[1]

                        # if end piece is a rook or queen
                        if (0 <= index <= 3 and type == "R") or (4 <= index <= 7 and type == "B") or \
                                (col == 1 and type == "P" and ((enemy == "w" and 6 <= index <= 7) or (enemy == "b" and 4 <= index <= 5))) or \
                                (type == "Q") or (col == 1 and type == "K"):
                            
                            # if there is no possible pin
                            if possible_pin == ():
                                in_check = True
                                checks.append((end_row, end_col, direction[0], direction[1]))
                                break

                            # if there is a possible pin
                            else:
                                pins.append(possible_pin)
                                break
                        else:
                            break
                else:
                    break

        # check for knight checks
        knight_moves = ((-2, -1), (-2, 1), (2, -1), (2, 1), (-1, 2), (1, 2), (-1, -2), (1, -2))

        # for each knight move
        for move in knight_moves:

            # get end position
            end_row = start_row + move[0]
            end_col = start_col + move[1]

            # if end position is on the board
            if 0 <= end_row < 8 and 0 <= end_col < 8:
                end_piece = self.board[end_row][end_col]

                # if end piece is an enemy knight
                if end_piece[0] == enemy and end_piece[1] == "N":
                    in_check = True
                    checks.append((end_row, end_col, move[0], move[1]))

        return in_check, pins, checks

    def is_check(self) -> bool:
        '''
        Check if king is in check
        :return: bool
        '''

        # get square under attack of king
        if self.white:
            return self.square_under_attack(self.white_king[0], self.white_king[1])
        else:
            return self.square_under_attack(self.black_king[0], self.black_king[1])

    def get_king_pos(self, piece_colour) -> tuple:
        '''
        Get king position
        :param piece_colour: str
        :return: tuple
        '''

        if piece_colour == "w":
            return self.white_king
        else:
            return self.black_king
    
    def get_num_attacking_pieces(self, position, enemy):
        '''
        Get number of pieces attacking a square
        :param position: tuple
        :param enemy: str
        :return: int
        '''
        start_row, start_col = position
        num_atk = 0

        # for each row
        for row in range(8):

            # for each col
            for col in range(8):

                # if piece is an enemy
                if self.board[row][col][0] == enemy:

                    # get valid moves at square
                    moves = self.get_valid_moves_at_square(row, col)

                    # for each move
                    for move in moves:

                        # if move is a capture
                        if move.end_row == start_row and move.end_col == start_col:

                            # increment num
                            num_atk += 1

        return num_atk

    def square_under_attack(self, start_row, start_col) -> bool:
        '''
        Check if square is under attack
        :param start_row: int
        :param start_col: int
        :return: bool
        '''

        # change turn
        self.white = not self.white

        # get possible moves
        enemy_moves = self.get_possible_moves()

        # change turn
        self.white = not self.white

        # check if square is under attack
        for move in enemy_moves:

            # if move is a capture
            if move.end_row == start_row and move.end_col == start_col:

                return True
            
        return False
    
    def get_valid_moves_at_square(self, start_row, start_col) -> list:
        '''
        Get valid moves at square
        :param start_row: int
        :param start_col: int
        :return: list
        '''

        # get piece
        piece = self.board[start_row][start_col][1]
        moves = []

        # get moves
        self.move_function[piece](start_row, start_col, moves)

        return moves
    
    def is_file_open(self, start_col) -> bool:
        '''
        Check if file is open
        :param start_col: int
        :return: bool
        '''

        # for each row
        for row in range(8):

            # if piece is not empty
            if self.board[row][start_col] != "--":

                return False
            
        return True
    
    def is_diagonal_open(self, start_row, start_col) -> bool:
        '''
        Check if diagonal is open
        :param start_row: int
        :param start_col: int
        :return: bool
        '''

        # for each row
        for row in range(8):

            # if start row and start col are within board
            if start_row + row < 8 and start_col + row < 8:

                # if piece is not empty
                if self.board[start_row + row][start_col + row] != "--":

                    return False
                
            # if start row and start col are within board
            if start_row - row >= 0 and start_col + row < 8:

                # if piece is not empty
                if self.board[start_row - row][start_col + row] != "--":

                    return False
                
            # if start row and start col are within board
            if start_row + row < 8 and start_col - row >= 0:

                # if piece is not empty
                if self.board[start_row + row][start_col - row] != "--":

                    return False
                
            # if start row and start col are within board
            if start_row - row >= 0 and start_col - row >= 0:

                # if piece is not empty
                if self.board[start_row - row][start_col - row] != "--":

                    return False
                
        return True

    def get_possible_moves(self) -> list:
        '''
        Get all possible moves
        :return: list
        '''

        moves = []

        # for each row
        for row in range(len(self.board)):

            # for each col
            for col in range(len(self.board[row])):

                # turn is the colour of the piece selected
                turn = self.board[row][col][0]

                # if piece is not empty
                if (turn == "w" and self.white) or (turn == "b" and not self.white):

                    # get piece
                    piece = self.board[row][col][1]

                    # get moves
                    self.move_function[piece](row, col, moves)

        return moves

    def get_pawn_moves(self, start_row, start_col, moves: list) -> None:
        '''
        Get pawn moves
        :param row: int
        :param col: int
        :param moves: list
        :return: None
        '''

        piece_pinned = False
        pin_direction = ()

        # check if piece is pinned
        for pin_index in range (len(self.pins) - 1, -1, -1):

            # if piece is pinned
            if self.pins[pin_index][0] == start_row and self.pins[pin_index][1] == start_col:

                # piece is pinned
                piece_pinned = True
                pin_direction = (self.pins[pin_index][2], self.pins[pin_index][3])
                self.pins.remove(self.pins[pin_index])

                break

        # if white
        if self.white:

            move_amount = -1
            start_row = 6
            enemy = "b"
            king_row, king_col = self.white_king

        # if black
        else:
            move_amount = 1
            start_row = 1
            enemy = "w"
            king_row, king_col = self.black_king

        # if white
        if self.white:

            # if square in front is empty
            if self.board[start_row - 1][start_col] == "--":

                # if not pinned or pin direction is (1, 0)
                if not piece_pinned or pin_direction == (-1, 0):

                    # add move
                    moves.append(Move((start_row, start_col), (start_row - 1, start_col), self.board))

                    # if 2 squares in front is empty and starting row is 6
                    if start_row == 6 and self.board[start_row - 2][start_col] == "--":

                        # add move
                        moves.append(Move((start_row, start_col), (start_row - 2, start_col), self.board))

            # if starting col is not 0 and square in front left is an enemy
            if start_col - 1 >= 0:

                # check if end piece is enemy
                if self.board[start_row - 1][start_col - 1][0] == "b":

                    # if not pinned or pin direction is (1, -1)
                    if not piece_pinned or pin_direction == (-1, -1):

                        # add move
                        moves.append(Move((start_row, start_col), (start_row - 1, start_col - 1), self.board))

                # if enpassant is possible
                if (start_row - 1, start_col - 1) == self.enpassant_possible:

                    # if not pinned or pin direction is (1, -1)
                    if not piece_pinned or pin_direction == (-1, -1):

                        if not piece_pinned or pin_direction == (1, -1):


                            attacking_piece = block_piece = False

                            # if king row is starting row
                            if king_row == start_row:

                                # if king col is less than starting col
                                if king_col < start_col:

                                    # get inside range
                                    insideRange = range(king_col + 1, start_col - 1)

                                    # get outside range
                                    outsideRange = range(start_col + 1, 8)

                                # if king col is greater than starting col
                                else:
                                    
                                    # get inside range
                                    insideRange = range(king_col - 1, start_col, -1)

                                    # get outside range
                                    outsideRange = range(start_col - 2, -1, -1)

                                # for each col in inside range
                                for inside_col in insideRange:

                                    # if square is not empty
                                    if self.board[start_row][inside_col] != "--":

                                        block_piece = True

                                # for each col in outside range
                                for outside_col in outsideRange:

                                    # get square
                                    square = self.board[start_row][outside_col]

                                    # if square is an enemy rook or queen
                                    if square[0] == enemy and (square[1] == "R" or square[1] == "Q"):


                                        attacking_piece = True

                                    # if square is not empty
                                    elif square != "--":

                                        block_piece = True

                            # if not attacking piece or block piece
                            if not attacking_piece or block_piece:

                                # add move
                                moves.append(Move((start_row, start_col), (start_row - 1, start_col - 1), self.board, enpassant_move=True))

            # if starting col is not 7 and square in front right is an enemy
            if start_col + 1 <= 7:

                if self.board[start_row - 1][start_col + 1][0] == "b":

                    # if not pinned or pin direction is (1, 1)
                    if not piece_pinned or pin_direction == (-1, 1):

                        # add move
                        moves.append(Move((start_row, start_col), (start_row - 1, start_col + 1), self.board))

                # if enpassant is possible
                if (start_row - 1, start_col + 1) == self.enpassant_possible:

                    # if not pinned or pin direction is (1, 1)
                    if not piece_pinned or pin_direction == (-1, 1):

                        if not piece_pinned or pin_direction == (1, -1):

                            attacking_piece = block_piece = False

                            # if king row is starting row
                            if king_row == start_row:

                                # if king col is less than starting col
                                if king_col < start_col:

                                    # get inside range
                                    insideRange = range(king_col + 1, start_col)

                                    # get outside range
                                    outsideRange = range(start_col + 2, 8)

                                # if king col is greater than starting col
                                else:

                                    # get inside range
                                    insideRange = range(king_col - 1, start_col + 1, -1)

                                    # get outside range
                                    outsideRange = range(start_col - 1, -1, -1)

                                # for each col in inside range
                                for inside_col in insideRange:

                                    # if square is not empty
                                    if self.board[start_row][inside_col] != "--":

                                        block_piece = True

                                # for each col in outside range
                                for outside_col in outsideRange:

                                    square = self.board[start_row][outside_col]

                                    # if square is an enemy rook or queen
                                    if square[0] == enemy and (square[1] == "R" or square[1] == "Q"):

                                        attacking_piece = True

                                    elif square != "--":

                                        block_piece = True

                            # if not attacking piece or block piece
                            if not attacking_piece or block_piece:

                                # add move
                                moves.append(Move((start_row, start_col), (start_row - 1, start_col + 1), self.board, enpassant_move=True))

        else:

            # if square in front is empty
            if self.board[start_row + 1][start_col] == "--":

                # if not pinned or pin direction is (1, 0)
                if not piece_pinned or pin_direction == (1, 0):

                    # add move
                    moves.append(Move((start_row, start_col), (start_row + 1, start_col), self.board))

                    # if 2 squares in front is empty and starting row is 1
                    if start_row == 1 and self.board[start_row + 2][start_col] == "--":

                        # add move
                        moves.append(Move((start_row, start_col), (start_row + 2*move_amount, start_col), self.board))

            # if starting col is not 0 and square in front left is an enemy
            if start_col - 1 >= 0:

                if self.board[start_row + 1][start_col - 1][0] == "w":

                    # if not pinned or pin direction is (1, -1)
                    if not piece_pinned or pin_direction == (1, -1):

                        # add move
                        moves.append(Move((start_row, start_col), (start_row + move_amount, start_col - 1), self.board))

                # if enpassant is possible
                if (start_row + 1, start_col - 1) == self.enpassant_possible:

                    # if not pinned or pin direction is (1, -1)
                    if not piece_pinned or pin_direction == (1, -1):

                        attacking_piece = block_piece = False

                        # if king row is starting row
                        if king_row == start_row:

                            # if king col is less than starting col
                            if king_col < start_col:

                                # get inside range
                                insideRange = range(king_col + 1, start_col - 1)

                                # get outside range
                                outsideRange = range(start_col + 1, 8)

                            else:

                                # get inside range
                                insideRange = range(king_col - 1, start_col, -1)

                                # get outside range
                                outsideRange = range(start_col - 2, -1, -1)

                            # for each col in inside range
                            for inside_col in insideRange:

                                # if square is not empty
                                if self.board[start_row][inside_col] != "--":

                                    block_piece = True

                            # for each col in outside range
                            for outside_col in outsideRange:

                                square = self.board[start_row][outside_col]

                                # if square is an enemy rook or queen
                                if square[0] == enemy and (square[1] == "R" or square[1] == "Q"):

                                    attacking_piece = True

                                # if square is not empty
                                elif square != "--":

                                    block_piece = True

                        # if not attacking piece or block piece
                        if not attacking_piece or block_piece:

                            # add move
                            moves.append(Move((start_row, start_col), (start_row + move_amount, start_col - 1), self.board, enpassant_move=True))

            # if starting col is not 7 and square in front right is an enemy
            if start_col + 1 <= 7:

                if self.board[start_row + 1][start_col + 1][0] == "w":

                    # if not pinned or pin direction is (1, 1)
                    if not piece_pinned or pin_direction == (1, 1):

                        # add move
                        moves.append(Move((start_row, start_col), (start_row + move_amount, start_col + 1), self.board))

                # if enpassant is possible
                if (start_row + 1, start_col + 1) == self.enpassant_possible:

                    # if not pinned or pin direction is (1, 1)
                    if not piece_pinned or pin_direction == (1, 1):
                        
                        # if not pinned or pin direction is (1, -1)
                        if not piece_pinned or pin_direction == (1, -1):

                            attacking_piece = block_piece = False

                            # if king row is starting row
                            if king_row == start_row:

                                # if king col is less than starting col
                                if king_col < start_col:

                                    # get inside range
                                    insideRange = range(king_col + 1, start_col)

                                    # get outside range
                                    outsideRange = range(start_col + 2, 8)
                                    
                                else:

                                    # get inside range
                                    insideRange = range(king_col - 1, start_col + 1, -1)

                                    # get outside range
                                    outsideRange = range(start_col - 1, -1, -1)

                                # for each col in inside range
                                for inside_col in insideRange:

                                    # if square is not empty
                                    if self.board[start_row][inside_col] != "--":

                                        # block piece
                                        block_piece = True

                                # for each col in outside range
                                for outside_col in outsideRange:

                                    square = self.board[start_row][outside_col]

                                    # if square is an enemy rook or queen
                                    if square[0] == enemy and (square[1] == "R" or square[1] == "Q"):

                                        attacking_piece = True

                                    # if square is not empty
                                    elif square != "--":

                                        block_piece = True

                            # if not attacking piece or block piece
                            if not attacking_piece or block_piece:

                                # add move
                                moves.append(Move((start_row, start_col), (start_row + move_amount, start_col + 1), self.board, enpassant_move=True))

    def get_rook_moves(self, start_row, start_col, moves):
        '''
        Get rook moves
        :param row: int
        :param col: int
        :param moves: list
        :return: None
        '''
        piece_pinned = False
        pin_direction = ()

        # check if piece is pinned
        for pin_index in range(len(self.pins) - 1, -1, -1):

            if self.pins[pin_index][0] == start_row and self.pins[pin_index][1] == start_col:

                piece_pinned = True
                pin_direction = (self.pins[pin_index][2], self.pins[pin_index][3])
                self.pins.remove(self.pins[pin_index])

                break

        directions = ((-1, 0), (0, -1), (1, 0), (0, 1))
        enemy = "b" if self.white else "w"

        # for each direction
        for direction in directions:

            # for each scalar
            for scalar in range(1, 8):

                # get end position
                end_row = start_row + direction[0] * scalar
                end_col = start_col + direction[1] * scalar

                # if end position is on the board
                if 0 <= end_row < 8 and 0 <= end_col < 8:

                    # if not pinned or pin direction is direction or pin direction is (-direction[0], -direction[1])
                    if not piece_pinned or pin_direction == direction or pin_direction == (-direction[0], -direction[1]):

                        # get end piece
                        end_piece = self.board[end_row][end_col]

                        # if end piece is empty
                        if end_piece == "--":

                            # add move
                            moves.append(Move((start_row, start_col), (end_row, end_col), self.board))

                        elif end_piece[0] == enemy:

                            # add move
                            moves.append(Move((start_row, start_col), (end_row, end_col), self.board))
                            break

                        else:

                            break

                else:

                    break

    def get_knight_moves(self, start_row, start_col, moves: list) -> None:
        '''
        Get knight moves
        :param start_row: int
        :param start_col: int
        :param moves: list
        :return: None
        '''

        piece_pinned = False

        # check if piece is pinned
        for pin_index in range(len(self.pins) - 1, -1, -1):
            
            if self.pins[pin_index][0] == start_row and self.pins[pin_index][1] == start_col:

                piece_pinned = True
                self.pins.remove(self.pins[pin_index])

                break

        directions = ((-2, -1), (-2, 1), (2, -1), (2, 1), (-1, 2), (1, 2), (-1, -2), (1, -2))
        ally = "w" if self.white else "b"

        # for each direction
        for direction in directions:

            # get end position
            end_row = start_row + direction[0]
            end_col = start_col + direction[1]

            # if end position is on the board
            if 0 <= end_row < 8 and 0 <= end_col < 8:

                # if not pinned
                if not piece_pinned:

                    # get end piece
                    end_piece = self.board[end_row][end_col]

                    # if end piece is empty or an enemy
                    if end_piece[0] != ally:

                        # add move
                        moves.append(Move((start_row, start_col), (end_row, end_col), self.board))

    def get_bishop_moves(self, start_row, start_col, moves: list) -> None:
        '''
        Get bishop moves
        :param row: int
        :param col: int
        :param moves: list
        :return: None
        '''

        piece_pinned = False
        pin_direction = ()

        # check if piece is pinned
        for pin_index in range(len(self.pins) - 1, -1, -1):

            if self.pins[pin_index][0] == start_row and self.pins[pin_index][1] == start_col:

                piece_pinned = True
                pin_direction = (self.pins[pin_index][2], self.pins[pin_index][3])
                self.pins.remove(self.pins[pin_index])

                break

        directions = ((-1, -1), (1, 1), (-1, 1), (1, -1))
        enemy = "b" if self.white else "w"

        # for each direction
        for direction in directions:

            # for each scalar
            for scalar in range(1, 8):

                # get end position
                end_row = start_row + direction[0] * scalar
                end_col = start_col + direction[1] * scalar

                # if end position is on the board
                if 0 <= end_row < 8 and 0 <= end_col < 8:

                    # if not pinned or pin direction is direction or pin direction is (-direction[0], -direction[1])
                    if not piece_pinned or pin_direction == direction or pin_direction == (-direction[0], -direction[1]):

                        end_piece = self.board[end_row][end_col]

                        # if end piece is empty
                        if end_piece == "--":

                            # add move
                            moves.append(Move((start_row, start_col), (end_row, end_col), self.board))

                        # if end piece is an enemy
                        elif end_piece[0] == enemy:

                            # add move
                            moves.append(Move((start_row, start_col), (end_row, end_col), self.board))
                            break

                        else:

                            break

                else:

                    break

    def get_queen_moves(self, start_row, start_col, moves: list) -> None:
        '''
        Get queen moves
        :param start_row: int
        :param start_col: int
        :param moves: list
        :return: None
        '''

        self.get_rook_moves(start_row, start_col, moves)
        self.get_bishop_moves(start_row, start_col, moves)

    def get_king_moves(self, start_row, start_col, moves: list) -> None:
        '''
        Get king moves
        :param start_row: int
        :param start_col: int
        :param moves: list
        :return: None
        '''

        # get king moves in all directions
        row_moves = (-1, -1, -1, 0, 0, 1, 1, 1)
        col_moves = (-1, 0, 1, -1, 1, -1, 0, 1)

        ally = "w" if self.white else "b"

        # for each direction
        for index in range(8):

            # get end position
            end_row = start_row + row_moves[index]
            end_col = start_col + col_moves[index]

            # if end position is on the board
            if 0 <= end_row < 8 and 0 <= end_col < 8:

                # get end piece
                end_piece = self.board[end_row][end_col]

                # if end piece is empty or an enemy
                if end_piece[0] != ally:

                    # if ally is white
                    if ally == "w":

                        # set white king position to end position
                        self.white_king = (end_row, end_col)

                    # if ally is black
                    else:

                        # set black king position to end position
                        self.black_king = (end_row, end_col)

                    # check for pins and checks
                    inCheck, pins, checks = self.check_for_pins_and_checks()

                    # if not in check
                    if not inCheck:

                        # add move
                        moves.append(Move((start_row, start_col), (end_row, end_col), self.board))

                    # if ally is white
                    if ally == "w":

                        # set white king position to start position
                        self.white_king = (start_row, start_col)

                    # if ally is black
                    else:

                        # set black king position to start position
                        self.black_king = (start_row, start_col)

    def get_castle_moves(self, start_row, start_col, moves: list) -> None:
        '''
        Get castle moves
        :param start_row: int
        :param start_col: int
        :param moves: list
        :return: None
        '''

        # if king is in check
        if self.square_under_attack(start_row, start_col):
            return
        
        # if king side castle is possible
        if (self.white and self.current_castling_rights.wks) or (not self.white and self.current_castling_rights.bks):

            self.get_king_side_castle_moves(start_row, start_col, moves)

        # if queen side castle is possible
        if (self.white and self.current_castling_rights.wqs) or (not self.white and self.current_castling_rights.bqs):

            self.get_queen_side_castle_moves(start_row, start_col, moves)

    def get_king_side_castle_moves(self, start_row, start_col, moves: list) -> None:
        '''
        Get king side castle moves
        :param start_row: int
        :param start_col: int
        :param moves: list
        :return: None
        '''

        # if square in front of king is empty and square 2 in front of king is empty
        if self.board[start_row][start_col + 1] == "--" and self.board[start_row][start_col + 2] == "--":

            # if square is not under attack
            if not self.square_under_attack(start_row, start_col + 1) and not self.square_under_attack(start_row, start_col + 2):

                # add move
                moves.append(Move((start_row, start_col), (start_row, start_col + 2), self.board, isCastleMove=True))

    def get_queen_side_castle_moves(self, start_row, start_col, moves: list) -> None:
        '''
        Get queen side castle moves
        :param start_row: int
        :param start_col: int
        :param moves: list
        :return: None
        '''
        
        # if square in front of king is empty and square 2 in front of king is empty and square 3 in front of king is empty
        if self.board[start_row][start_col - 1] == "--" and self.board[start_row][start_col - 2] == "--" and self.board[start_row][start_col - 3] == "--":
            
            # if square is not under attack
            if not self.square_under_attack(start_row, start_col - 1) and not self.square_under_attack(start_row, start_col - 2):
                
                # add move
                moves.append(Move((start_row, start_col), (start_row, start_col - 2), self.board, isCastleMove=True))