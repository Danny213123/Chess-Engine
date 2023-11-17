import random
import ZobristKeys
import time
import pickle
import StockFishEngine

#stockfish = Stockfish(path="/stockfish/stockfish-windows-x86-64-avx2")

transpositional_table = {}

score_dict = {"Q": 16, "B": 7, "R": 8, "N": 5, "P": 1, "K": 0}

knight_score = [
    [1, 1, 1, 1, 1, 1, 1, 1],
    [1, 2, 2, 2, 2, 2, 2, 1],
    [1, 2, 3, 3, 3, 3, 2, 1],
    [1, 2, 3, 4, 4, 3, 2, 1],
    [1, 2, 3, 4, 4, 3, 2, 1],
    [1, 2, 3, 3, 3, 3, 2, 1],
    [1, 2, 2, 2, 2, 2, 2, 1],
    [1, 1, 1, 1, 1, 1, 1, 1]
]

bishop_score = [
    [4, 3, 2, 1, 1, 2, 3, 4],
    [3, 4, 3, 2, 2, 3, 4, 3],
    [2, 3, 4, 3, 3, 4, 3, 2],
    [1, 2, 3, 4, 4, 3, 2, 1],
    [1, 2, 3, 4, 4, 3, 2, 1],
    [2, 3, 4, 3, 3, 4, 3, 2],
    [3, 4, 3, 2, 2, 3, 4, 3],
    [4, 3, 2, 1, 1, 2, 3, 4]
]

rook_score = [
    [4, 3, 4, 4, 4, 4, 3, 4],
    [4, 4, 4, 4, 4, 4, 4, 4],
    [1, 1, 2, 3, 3, 2, 1, 1],
    [1, 2, 3, 4, 4, 3, 2, 1],
    [1, 2, 3, 4, 4, 3, 2, 1],
    [1, 1, 2, 2, 2, 2, 1, 1],
    [4, 4, 4, 4, 4, 4, 4, 4],
    [4, 3, 4, 4, 4, 4, 3, 4]
]

queen_score = [
    [1, 1, 1, 3, 1, 1, 1, 1],
    [4, 4, 4, 4, 4, 4, 4, 4],
    [1, 4, 3, 3, 3, 4, 1, 1],
    [1, 2, 3, 3, 3, 3, 2, 1],
    [1, 2, 3, 3, 3, 3, 2, 1],
    [1, 4, 3, 3, 3, 4, 2, 1],
    [1, 1, 2, 3, 3, 1, 1, 1],
    [1, 1, 1, 3, 1, 1, 1, 1]
]

white_pawn_score = [
    [8, 8, 8, 8, 8, 8, 8, 8],
    [8, 8, 8, 8, 8, 8, 8, 8],
    [5, 6, 7, 7, 7, 7, 6, 5],
    [2, 3, 3, 5, 5, 3, 3, 2],
    [1, 2, 3, 4, 4, 3, 2, 1],
    [1, 1, 2, 3, 3, 2, 1, 1],
    [1, 1, 1, 0, 0, 1, 1, 1],
    [0, 0, 0, 0, 0, 0, 0, 0]
]

black_pawn_score = [
    [0, 0, 0, 0, 0, 0, 0, 0],
    [1, 1, 1, 0, 0, 1, 1, 1],
    [1, 1, 2, 3, 3, 2, 1, 1],
    [1, 2, 3, 4, 4, 3, 2, 1],
    [2, 3, 3, 5, 5, 3, 3, 2],
    [5, 6, 7, 7, 7, 7, 6, 5],
    [8, 8, 8, 8, 8, 8, 8, 8],
    [8, 8, 8, 8, 8, 8, 8, 8]
]


# openings
# https://www.chess.com/openings/Scandinavian-Defense-2.Nf3-d5-3.exd5-Qxd5
# https://www.chess.com/openings/Scandinavian-Defense-2.Nf3-d5-3.exd5-Qxd5-4.Nc3
# https://www.chess.com/openings/Scandinavian-Defense-2.Nf3-d5-3.exd5-Qxd5-4.Nc3-Qa5

# midgame
# https://www.chess.com/openings/Scandinavian-Defense-2.Nf3-d5-3.exd5-Qxd5-4.Nc3-Qa5-5.d4
# https://www.chess.com/openings/Scandinavian-Defense-2.Nf3-d5-3.exd5-Qxd5-4.Nc3-Qa5-5.d4-Bg4
# https://www.chess.com/openings/Scandinavian-Defense-2.Nf3-d5-3.exd5-Qxd5-4.Nc3-Qa5-5.d4-Bg4-6.Be2

# endgame
# https://www.chess.com/openings/Scandinavian-Defense-2.Nf3-d5-3.exd5-Qxd5-4.Nc3-Qa5-5.d4-Bg4-6.Be2-Nf6
# https://www.chess.com/openings/Scandinavian-Defense-2.Nf3-d5-3.exd5-Qxd5-4.Nc3-Qa5-5.d4-Bg4-6.Be2-Nf6-7.O-O
# https://www.chess.com/openings/Scandinavian-Defense-2.Nf3-d5-3.exd5-Qxd5-4.Nc3-Qa5-5.d4-Bg4-6.Be2-Nf6-7.O-O-O

piece_position = {"N": knight_score, "Q": queen_score, "B": bishop_score, "R": rook_score, "wP": white_pawn_score,
                  "bP": black_pawn_score}

DEPTH = 6

next_move = None

stockfish = StockFishEngine.StockFishEngine()

def find_best_move(gs, valid_moves, engine):
    global next_move, counter
    counter = 0

    next_move = None
    random.shuffle(valid_moves)

    start = time.time()
    total_time = 0

    if engine == "experimental":
        for depth in range(1, DEPTH+1):
            find_negascout(gs, valid_moves, depth, float("-inf"), float("inf"), 1 if gs.white else -1)
            print(f"Depth {depth} completed in {time.time() - start}s")
            total_time += time.time() - start
            if next_move is not None:
                break
        if next_move is None:
            find_negascout(gs, valid_moves, 1, float("-inf"), float("inf"), 1 if gs.white else -1)
    elif engine == "stockfish":
        stockfish_scout(gs, valid_moves)
        total_time += time.time() - start
    else:
        find_negascout(gs, valid_moves, 1, float("-inf"), float("inf"), 1 if gs.white else -1)

    print(f"Time taken: {total_time}s")
    print(f"Positions evaluated: {counter}")
    print(f"Evaluation score: {positional_score(gs)}")
    print(f"Transpositional table size: {len(transpositional_table)}")
    print(f"Next move: {next_move}")
    print(f"Fen: {gs.get_fen()}")

    return next_move

def order_moves(valid_moves, gs):
    ordered_moves = []
    for move in valid_moves:
        if move.pieceCaptured != "--":
            ordered_moves.insert(0, move)
        else:
            ordered_moves.append(move)
    return ordered_moves

class TranspositionTableEntry():
    def __init__(self, depth, score, flag):
        self.depth = depth
        self.score = score
        self.flag = flag

def stockfish_scout(gs, valid_moves):
    global next_move, counter

    best_score = float("-inf")
    for move in valid_moves:
        gs.make_move(move)
        next_moves = gs.get_valid_moves()
        score = -positional_score(gs)
        counter += 1
        if score > best_score:
            best_score = score
            next_move = move
        gs.undo_move()

def find_negascout(gs, valid_moves, depth, alpha, beta, turn_multiplier):
    global next_move, counter
    counter += 1

    if depth == 0:
        return turn_multiplier * score_board(gs)

    # move ordering
    valid_moves = order_moves(valid_moves, gs)
    # valid_moves = gs.get_valid_moves()

    hash_k = ZobristKeys.zobrist_key(gs)

    # transposition table lookup
    # print(transpositional_table)

    # check if transpositional table is empty
    if len(transpositional_table) == 0:
        tt_entry = None
    else:
        tt_entry = transpositional_table.get(hash_k)

    if tt_entry is not None and tt_entry.depth >= depth:
        if tt_entry.flag == "exact":
            return tt_entry.score
        elif tt_entry.flag == "alpha" and tt_entry.score <= alpha:
            return alpha
        elif tt_entry.flag == "beta" and tt_entry.score >= beta:
            return beta

    best_score = float("-inf")
    for move in valid_moves:
        gs.make_move(move)
        next_moves = gs.get_valid_moves()
        if best_score == float("-inf"):
            score = -find_negascout(gs, next_moves, depth - 1, -beta, -alpha, -turn_multiplier)
        else:
            score = -find_negascout(gs, next_moves, depth - 1, -alpha - 1, -alpha, -turn_multiplier)
            if alpha < score < beta:
                score = -find_negascout(gs, next_moves, depth - 1, -beta, -score, -turn_multiplier)
        if score > best_score:
            best_score = score
            if depth == DEPTH:
                next_move = move
        gs.undo_move()
        alpha = max(alpha, best_score)
        if alpha >= beta:
            break

    if best_score <= alpha:
        flag = "beta"
    elif best_score >= beta:
        flag = "alpha"
    else:
        flag = "exact"

    tt_entry = TranspositionTableEntry(depth, best_score, flag)
    hash_k = ZobristKeys.zobrist_key(gs)
    transpositional_table[hash_k] = tt_entry

    return best_score

'''
def score_board(gs):
    if gs.check_mate:
        if gs.white:
            return -1000
        else:
            return 1000

    score = 0

    # Piece scores
    for row in range(len(gs.board)):
        for col in range(len(gs.board[row])):
            square = gs.board[row][col]
            if square != "--":
                piece_type = square[1]
                piece_colour = square[0]
                if piece_type == "P":
                    piece_position_score = piece_position [piece_colour + piece_type][row][col]
                else:
                    piece_position_score = piece_position[piece_type][row][col]

                # Mobility score
                moves = gs.get_valid_moves_at_square(row, col)
                mobility_score = len(moves)

                # Center control score
                center_control_score = 0
                if (row, col) in [(3, 3), (3, 4), (4, 3), (4, 4)]:
                    center_control_score = 1

                # Open file/diagonal score
                open_file_score = 0
                open_diagonal_score = 0
                if piece_type in ["R", "Q"]:
                    if gs.is_file_open(col):
                        open_file_score = 1
                    if gs.is_diagonal_open(row, col):
                        open_diagonal_score = 1
                elif piece_type == "B":
                    if gs.is_diagonal_open(row, col):
                        open_diagonal_score = 1

                # King attack score
                king_attack_score = 0
                if piece_type != "K":
                    king_pos = gs.get_king_pos(piece_colour)
                    if king_pos is not None:
                        king_row, king_col = king_pos
                        if (row, col) in gs.get_valid_moves_at_square(king_row, king_col):
                            king_attack_score = 1

                # Add up scores
                piece_score = (
                    score_dict[piece_type]
                    + piece_position_score
                    + mobility_score
                    + center_control_score
                    + open_file_score
                    + open_diagonal_score
                    + king_attack_score
                )
                if piece_colour == "w":
                    score += piece_score
                else:
                    score -= piece_score

    # Pawn scores
    for row in range(len(gs.board)):
        for col in range(len(gs.board[row])):
            square = gs.board[row][col]
            if square != "--" and square[1] == "P":
                pawn_colour = square[0]
                pawn_position_score = piece_position[square][row][col]

                # Pawn promotion score
                promotion_score = 0
                if (pawn_colour == "w" and row == 0) or (pawn_colour == "b" and row == 7):
                    promotion_score = 1

                # Add up scores
                pawn_score = score_dict["P"] + pawn_position_score + promotion_score
                if pawn_colour == "w":
                    score += pawn_score
                else:
                    score -= pawn_score

    # King safety score
    white_king_pos = gs.get_king_pos("w")
    black_king_pos = gs.get_king_pos("b")
    if white_king_pos is not None:
        white_safety_score = gs.get_num_attacking_pieces(white_king_pos, "b")
        score += white_safety_score
    if black_king_pos is not None:
        black_safety_score = gs.get_num_attacking_pieces(black_king_pos, "w")
        score -= black_safety_score

    # Remaining piece scores
    white_piece_score = len(gs.get_all_pieces("w"))
    black_piece_score = len(gs.get_all_pieces("b"))
    score += white_piece_score - black_piece_score

    # Remaining pawn scores
    white_pawn_score = len(gs.get_all_pawns("w"))
    black_pawn_score = len(gs.get_all_pawns("b"))
    score += white_pawn_score - black_pawn_score

    # Developed piece scores
    white_developed_score = gs.get_num_developed_pieces("w")
    black_developed_score = gs.get_num_developed_pieces("b")
    score += white_developed_score - black_developed_score

    # Piece on opponent's side score
    white_opponent_side_score = gs.get_num_pieces_on_opponent_side("w")
    black_opponent_side_score = gs.get_num_pieces_on_opponent_side("b")
    score += white_opponent_side_score - black_opponent_side_score

    # King defense score
    white_king_defense_score = gs.get_num_defending_pieces(white_king_pos, "w")
    black_king_defense_score = gs.get_num_defending_pieces(black_king_pos, "b")
    score += white_king_defense_score - black_king_defense_score

    # King attack score
    white_king_attack_score = gs.get_num_attacking_pieces(white_king_pos, "w")
    black_king_attack_score = gs.get_num_attacking_pieces(black_king_pos, "b")
    score += white_king_attack_score - black_king_attack_score

    return score
'''

def positional_score(gs):
    stockfish.set_fen_position(gs.get_fen())
    return stockfish.get_evaluation()['value']

def score_board(gs):
    if gs.check_mate:
        if gs.white:
            return -1000
        else:
            return 1000

    score = 0

    for row in range(len(gs.board)):
        for col in range(len(gs.board[row])):
            square = gs.board[row][col]
            if square != "--":

                piece_position_score = 0
                if square[1] != "K":
                    if square[1] == "P":
                        piece_position_score = piece_position[square][row][col]
                    else:
                        piece_position_score = piece_position[square[1]][row][col]

                if square[0] == "w":
                    score += score_dict[square[1]] + piece_position_score
                elif square[0] == "b":
                    score -= score_dict[square[1]] + piece_position_score

    return score

def export_transposition_table():
    with open("main/transpositional_table.pickle", "wb") as f:
        pickle.dump(transpositional_table, f)

def import_transposition_table():
    with open("main/transpositional_table.pickle", "rb") as f:
        transpositional_table = pickle.load(f)
