# Author: Danny Guan
# Description: This file is a playground for testing the chess engine.
#
# Engines : v1, old
# 

from chess_engine.engine.v1.chess_engine import *
from chess_engine.engine.v1.chess_algorithm import *
from chess_engine.visual import visualize


if __name__ == "__main__":
    ChessEngine = GameState()
    visualize("v1")