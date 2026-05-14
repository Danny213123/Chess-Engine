from importlib.resources import files

WIDTH = HEIGHT = 512
DIMENSION = 8
SQUARESIZE = HEIGHT // DIMENSION
IMAGE_LOCATION = files("chess_engine.images")
