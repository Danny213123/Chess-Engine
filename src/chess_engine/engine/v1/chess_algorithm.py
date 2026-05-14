# Authors:  Danny Guan
# Description: This file contains the algorithm that determines the best move
#              for the AI to make. The algorithm is an implementation of the
#              Negascout algorithm, which combines alpha-beta pruning and
#              transpositional tables to optimize the search for the best move
#              in a game of chess. It utilizes advanced techniques such as
#              heuristic evaluation, move ordering, and iterative deepening to
#              efficiently explore the game tree and determine the optimal move.
#              The algorithm employs alpha-beta pruning to eliminate irrelevant
#              branches of the tree, reducing the number of positions that need
#              to be evaluated. Additionally, it utilizes transpositional tables
#              to store previously evaluated positions, allowing for efficient
#              retrieval and reuse of previously computed scores. This algorithm
#              is a sophisticated and highly effective approach to chess game
#              analysis and decision-making.

import random
import time
import pickle
from pathlib import Path
from . import chess_hash

from .chess_heuristic_calculation import score_board
from .chess_transposition_table import TranspositionTableEntry



transpositional_table = {}

DEPTH = 6

def _transposition_table_path():
    cache_dir = Path.home() / ".cache" / "chess-engine"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "transposition_table_v1.pickle"

next_move = None
initial_depth = 1  # Track the initial depth for move selection

def find_best_move(game_state, valid_moves, engine):
    '''
    Calls the appropriate function to find the best move.

    :param game_state: current game state
    :param valid_moves: list of valid moves
    :param engine: engine to use
    :return: best move
    '''

    global next_move, counter, initial_depth
    counter = 0

    next_move = None
    random.shuffle(valid_moves)

    start = time.time()
    total_time = 0

    # negascout with move ordering and iterative deepening
    if engine == "v1":

        # iterative deepening
        for depth in range(1, DEPTH+1):
            initial_depth = depth  # Track the depth for this iteration

            # negascout
            find_negascout(game_state, valid_moves, depth, float("-inf"), float("inf"), 1 if game_state.white else -1)

            # time
            print(f"Depth {depth} completed in {time.time() - start}s")

            total_time += time.time() - start

    else:
        # 'old' engine - single depth negascout
        initial_depth = 1
        find_negascout(game_state, valid_moves, 1, float("-inf"), float("inf"), 1 if game_state.white else -1)

    # if no move is found, pick a random valid move (fallback for both engines)
    if next_move is None and valid_moves:
        next_move = random.choice(valid_moves)

    total_time = time.time() - start

    print(f"Time taken: {total_time}s")
    print(f"Positions evaluated: {counter}")
    print(f"Evaluation score: {score_board(game_state)}")
    print(f"Transpositional table size: {len(transpositional_table)}")
    print(f"Next move: {next_move}")
    print(f"Fen: {game_state.get_fen()}")

    return next_move

def order_moves(valid_moves, game_state) -> list:
    '''
    The algorithm uses the heuristic evaluation function to order the moves
    in the list of valid moves. The heuristic evaluation function assigns a score
    to each move based on the value of the piece captured.

    :param valid_moves: list of valid moves
    :param game_state: current game state
    :return: list of ordered moves
    '''

    ordered_moves = []

    # iterate through valid moves
    for move in valid_moves:

        # if piece is captured, insert move at beginning of list
        if move.pieceCaptured != "--":

            ordered_moves.insert(0, move)

        else:

            ordered_moves.append(move)

    return ordered_moves



def find_negascout(game_state, valid_moves, depth, alpha, beta, turn_multiplier):
    '''
    The algorithm in question is an implementation of the Negascout algorithm, 
    which combines alpha-beta pruning and transpositional tables to optimize the 
    search for the best move in a game of chess. It utilizes advanced techniques 
    such as heuristic evaluation, move ordering, and iterative deepening to 
    efficiently explore the game tree and determine the optimal move. 
    The algorithm employs alpha-beta pruning to eliminate irrelevant branches of 
    the tree, reducing the number of positions that need to be evaluated. Additionally, 
    it utilizes transpositional tables to store previously evaluated positions, allowing 
    for efficient retrieval and reuse of previously computed scores. This algorithm is 
    a sophisticated and highly effective approach to chess game analysis and decision-making.

    :param game_state: current game state
    :param valid_moves: list of valid moves
    :param depth: depth of the search tree
    :param alpha: alpha value
    :param beta: beta value
    :param turn_multiplier: 1 if white, -1 if black
    
    '''

    global next_move, counter, initial_depth
    counter += 1

    # base case
    if depth == 0:
        return turn_multiplier * score_board(game_state)

    # move ordering
    valid_moves = order_moves(valid_moves, game_state)

    # get hash key
    hash_k = chess_hash.zobrist_key(game_state)

    # check if transpositional table is empty
    if len(transpositional_table) == 0:
        tt_entry = None
    else:
        tt_entry = transpositional_table.get(hash_k)

    # check if transpositional table entry is valid
    if tt_entry is not None and tt_entry.depth >= depth:

        # check transpositional table entry flag
        if tt_entry.flag == "exact":

            return tt_entry.score
        
        # if flag is alphga, check if score is less than alpha
        elif tt_entry.flag == "alpha" and tt_entry.score <= alpha:

            return alpha
        
        # if flag is beta, check if score is greater than beta
        elif tt_entry.flag == "beta" and tt_entry.score >= beta:

            return beta

    # initial score
    best_score = float("-inf")

    # iterate through valid moves
    for move in valid_moves:

        # make move
        game_state.make_move(move)

        # get next moves
        next_moves = game_state.get_valid_moves()

        # recursive call
        if best_score == float("-inf"):

            score = -find_negascout(game_state, next_moves, depth - 1, -beta, -alpha, -turn_multiplier)

        else:

            score = -find_negascout(game_state, next_moves, depth - 1, -alpha - 1, -alpha, -turn_multiplier)

            # check if score is between alpha and beta
            if alpha < score < beta:

                # recursive call
                score = -find_negascout(game_state, next_moves, depth - 1, -beta, -score, -turn_multiplier)

        # if score is greater than best score, update best score
        if score > best_score:

            best_score = score

            # check if at root depth (the initial depth we started searching from)
            if depth == initial_depth:

                # update next move
                next_move = move

        # undo move
        game_state.undo_move()

        # update alpha
        alpha = max(alpha, best_score)

        # check if alpha is greater than or equal to beta
        if alpha >= beta:
            break

    # check if best score is less than or equal to alpha
    if best_score <= alpha:

        flag = "beta"

    # check if best score is greater than or equal to beta
    elif best_score >= beta:

        flag = "alpha"

    # otherwise, flag is exact
    else:
        flag = "exact"

    # create transpositional table entry
    tt_entry = TranspositionTableEntry(depth, best_score, flag)

    # add entry to transpositional table
    hash_k = chess_hash.zobrist_key(game_state)

    transpositional_table[hash_k] = tt_entry

    return best_score

def export_transposition_table():
    '''
    This function exports the transpositional table to a pickle file.
    '''

    with _transposition_table_path().open("wb") as f:
        pickle.dump(transpositional_table, f)

def import_transposition_table():
    '''
    This function imports the transpositional table from a pickle file.
    '''

    try:
        with _transposition_table_path().open("rb") as f:
            transpositional_table = pickle.load(f)
    except (FileNotFoundError, EOFError, pickle.UnpicklingError):
        pass # Start with empty table
