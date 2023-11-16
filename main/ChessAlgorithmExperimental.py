import random
import Zobrist_keys
import time

score_dict = {"Q": 11, "B": 7, "R": 8, "N": 5, "P": 1, "K": 0}

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

DEPTH = 9

transpositional_table = {}

def find_best_move(gs, valid_moves):
    global next_move, counter
    counter = 0

    next_move = None
    random.shuffle(valid_moves)

    start = time.time()

    for depth in range(1, DEPTH+1):
        find_nega_max_alpha_beta(gs, valid_moves, depth, float("-inf"), float("inf"), 1 if gs.white else -1)
        print(f"Depth {depth} completed in {time.time() - start}s")
        if next_move is not None:
            break

    if next_move is None:
        find_nega_max_alpha_beta(gs, valid_moves, 1, float("-inf"), float("inf"), 1 if gs.white else -1)

    print(f"Time taken: {time.time() - start}s")
    print(f"Positions evaluated: {counter}")
    print(f"Move score: {next_move.score}")
    print(f"Transpositional table size: {len(transpositional_table)}")
    print(f"Move: {next_move.get_chess_notation()}")
    return next_move

def order_moves(valid_moves, gs):
    ordered_moves = []
    for move in valid_moves:
        if move.pieceCaptured != "--":
            ordered_moves.insert(0, move)
        else:
            ordered_moves.append(move)
    return ordered_moves

def score_board(gs):
    if gs.checkmate:
        if gs.white_to_move:
            return -100000
        else:
            return 100000
    elif gs.stalemate:
        return 0

    score = 0
    for row in range(len(gs.board)):
        for col in range(len(gs.board[row])):
            piece = gs.board[row][col]
            if piece != "--":
                piece_position_score = 0
                if piece[1] != "K":
                    if piece[1] == "P":
                        piece_position_score = pawn_score[piece[0]][row][col]
                    else:
                        piece_position_score = piece_position[piece[1]][row][col]
                if piece[0] == "w":
                    score += score_dict[piece[1]] + piece_position_score * .1
                elif piece[0] == "b":
                    score -= score_dict[piece[1]] + piece_position_score * .1

    return score

class TranspositionTableEntry():
    def __init__(self, depth, score, flag):
        self.depth = depth
        self.score = score
        self.flag = flag

def find_nega_max_alpha_beta(gs, valid_moves, depth, alpha, beta, turn_multiplier):
    global next_move, counter
    counter += 1

    if depth == 0:
        return turn_multiplier * score_board(gs)

    if len(valid_moves) == 0:
        if gs.in_check():
            return -100000 if turn_multiplier == 1 else 100000
        else:
            return 0

    # move ordering
    valid_moves = order_moves(valid_moves, gs)

    hash_k = Zobrist_keys.zobrist_key(gs)

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

    max_score = float("-inf")
    for move in valid_moves:
        gs.make_move(move)
        next_moves = gs.get_valid_moves()
        score = -find_nega_max_alpha_beta(gs, next_moves, depth - 1, -beta, -alpha, -turn_multiplier)
        if score > max_score:
            max_score = score
            if depth == DEPTH:
                next_move = move
        gs.undo_move()
        alpha = max(alpha, max_score)
        if alpha >= beta:
            break

    if max_score <= alpha:
        flag = "beta"
    elif max_score >= beta:
        flag = "alpha"
    else:
        flag = "exact"

    tt_entry = TranspositionTableEntry(depth, max_score, flag)
    hash_k = Zobrist_keys.zobrist_key(gs)
    transpositional_table[hash_k] = tt_entry

    return max_score

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

class TranspositionTableEntry():
    def __init__(self, depth, score, flag):
        self.depth = depth
        self.score = score
        self.flag = flag

transpositional_table = {}
next_move = None

def export_transposition_table():
    with open("main/transpositional_table.txt", "w") as f:
        for key in transpositional_table:
            entry = transpositional_table[key]
            f.write(str(key) + "," + str(entry.depth) + "," + str(entry.score) + "," + str(entry.flag) + "\n")

def import_transposition_table():
    flag_dict = {"exact": 0, "alpha": 1, "beta": 2}
    with open("main/transpositional_table.txt", "r") as f:
        for line in f.read().split("\n"):
            if line != "":
                key, depth, score, flag = line.split(",")
                transpositional_table[int(key)] = TranspositionTableEntry(int(depth), int(score), flag_dict[flag])
