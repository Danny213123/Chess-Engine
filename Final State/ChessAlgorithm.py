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

piece_position = {"N": knight_score, "Q": queen_score, "B": bishop_score, "R": rook_score, "wP": white_pawn_score,
                  "bP": black_pawn_score}

DEPTH = 6

transpositional_table = {}


def find_best_move(gs, valid_moves):
    global next_move, counter
    counter = 0

    next_move = None
    random.shuffle(valid_moves)

    start = time.time()

    find_nega_max_alpha_beta(gs, valid_moves, DEPTH, -1000, 1000, 1 if gs.white else -1)
    print(len(transpositional_table))
    print(counter)
    print(str(time.time() - start) + "s")
    return next_move


def minimax(gs, valid_moves, depth, isminimax):
    global next_move

    if depth == 0:
        return find_score(gs.board)

    if isminimax:
        maxScore = -1000
        for move in valid_moves:
            gs.make_move(move)
            next_moves = gs.get_valid_moves()
            score = minimax(gs, next_moves, depth - 1, False)
            if score > maxScore:
                maxScore = score
                if depth == DEPTH:
                    next_move = move
            gs.undo_move()
        return maxScore

    else:
        minScore = 1000
        for move in valid_moves:
            gs.make_move(move)
            next_moves = gs.get_valid_moves()
            score = minimax(gs, next_moves, depth - 1, True)
            if score < minScore:
                minScore = score
                if depth == DEPTH:
                    next_move = move
            gs.undo_move()
        return minScore


def find_nega_max(gs, valid_moves, depth, turn):
    global counter
    global next_move

    counter += 1

    if depth == 0:
        return turn * score_board(gs)

    max_score = -1000
    for move in valid_moves:
        gs.make_move(move)

        next_moves = gs.get_valid_moves()
        score = -find_nega_max(gs, next_moves, depth - 1, -turn)
        if score > max_score:
            max_score = score
            if depth == DEPTH:
                next_move = move

        gs.undo_move()
    return max_score


def find_nega_max_alpha_beta(gs, valid_moves, depth, alpha, beta, turn):
    global next_move, counter
    counter += 1

    alpha_orig = alpha

    if depth == 0:
        return turn * score_board(gs)

    hash_k = (Zobrist_keys.zobrist_key(gs))

    hash_entry = transpositional_table.get(hash_k)
    if hash_entry:
        hash_depth, hash_flag, hash_score = hash_entry
        if hash_depth >= depth:
            if hash_flag == "EXACT":
                return hash_score
            elif hash_flag == "LOWERBOUND":
                alpha = max(alpha, hash_score)
            elif hash_flag == "UPPERBOUND":
                beta = min(beta, hash_score)

            if alpha >= beta:
                return hash_score

    max_score = -1000
    for move in valid_moves:
        gs.make_move(move)

        next_moves = gs.get_valid_moves()
        score = -find_nega_max_alpha_beta(gs, next_moves, depth - 1, -beta, -alpha, -turn)

        if score > max_score:
            max_score = score
            if depth == DEPTH:
                next_move = move

        gs.undo_move()
        alpha = max(max_score, alpha)
        if alpha >= beta:
            break

    hash_score = max_score
    if max_score <= alpha_orig:
        hash_flag = "UPPERBOUND"
    elif max_score >= beta:
        hash_flag = "LOWERBOUND"
    else:
        hash_flag = "EXACT"
    hash_depth = depth

    hash_k = Zobrist_keys.zobrist_key(gs)
    transpositional_table[hash_k] = (hash_depth, hash_flag, hash_score)

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


def find_score(board):
    score = 0
    for row in board:
        for square in row:
            if square[0] == "w":
                score += score_dict[square[1]]
            elif square[1] == "b":
                score -= score_dict[square[1]]
    return score