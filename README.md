# Chess Engine

This project is a simple chess engine implemented in Python, providing a basic framework for playing chess, move generation, and position hashing using Zobrist hashing.

## Features

- **Chessboard Representation:** The chessboard is represented as a 2D array, and the game state is maintained using a `GameState` class.

- **Move Generation:** The engine can generate legal moves for each piece on the board, considering special moves like castling and en passant.

- **Zobrist Hashing:** Zobrist hashing is implemented for efficient position hashing. It uses a random bitstring for each piece at each square on the board.

- **Undo Move:** The engine supports undoing moves, allowing for exploration of different lines of play.

- **Game Visualization** Using pygame, the board is visualized including move highlighting

## Usage

To use the chess engine, you can instantiate a `GameState` object and make moves using the `make_move` method. You can also generate valid moves for a given position using the `get_valid_moves` method.

Example:

```python
from engine.chess_engine import *
from engine.chess_algorithm import *
from visual import *


ChessEngine = GameState()
print(ChessEngine.board)
visualize("stockfish")
```

## Move Generation

Alpha-Beta Pruning is an optimization technique used in decision trees and game trees to reduce the number of nodes evaluated in the search tree. It is commonly applied in two-player games, such as chess, to enhance the efficiency of the minimax algorithm.

### Background

In game-playing scenarios, the minimax algorithm is often used to determine the best move for a player by exploring all possible moves up to a certain depth in the game tree. However, the number of possible game states can be prohibitively large, making an exhaustive search impractical.

### Minimax Algorithm

The minimax algorithm works on the principle of evaluating the game states from the perspective of both players, maximizing the score for the current player and minimizing it for the opponent. This is done recursively, exploring the tree until a terminal state or a specified depth is reached.

### Alpha-Beta Pruning

Alpha-Beta Pruning enhances the minimax algorithm by introducing two parameters, alpha and beta, to keep track of the best choices found for the maximizing and minimizing players, respectively.

- **Alpha**: The best value that the maximizing player can currently guarantee at the current level or above.
- **Beta**: The best value that the minimizing player can currently guarantee at the current level or above.

The pruning occurs when a player discovers a move that is guaranteed to be worse than a previously examined move. If the current move is worse than the best move found so far, it can be safely ignored, and the search can be pruned. This reduces the number of nodes evaluated, significantly improving the efficiency of the search.

### Code Snip

```python
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

        # check if depth is 0
        if depth == DEPTH:

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
```

## TODO

1. Transposition Table Caching
2. Threats Calculator
3. Bitboard
