# Author: Danny Guan
# Description: This file is a playground for testing the chess engine.
#
# Engines : v1, old
# 

from engine.v1.chess_engine import *
from engine.v1.chess_algorithm import *
from visual import *


if __name__ == "__main__":
    ChessEngine = GameState()
    visualize("v1")