import engine.stockfish_engine as stockfish_engine
from engine.chess_constants import *

stockfish = stockfish_engine.StockFishEngine(PATH, DEPTH, THREADS, MINIMUM_THINKING_TIME, SKILL_LEVEL, PONDER)

def positional_score(game_state):
    '''
    Use stockfish engine to evaluate the board position.
    :param game_state: current game state
    '''

    stockfish.set_fen_position(game_state.get_fen())
    return stockfish.get_evaluation()['value']

def score_board(game_state):
    '''
    Use own heuristic evaluation function to evaluate the board position.
    :param game_state: current game state
    '''

    # check if game state is in checkmate
    if game_state.check_mate:
        if game_state.white:
            return float("-inf")
        else:
            return float("inf")

    score = 0

    # iterate through board
    for row in range(len(game_state.board)):

        for col in range(len(game_state.board[row])):

            # get piece on square
            square = game_state.board[row][col]

            # if square is not empty
            if square != "--":

                # get piece position score
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