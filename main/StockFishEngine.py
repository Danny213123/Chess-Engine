from stockfish import Stockfish, StockfishException

# why wont this run
stockfish = Stockfish('main\stockfish\stockfish-windows-x86-64-avx2.exe', depth=15, parameters={"Threads": 4, "Minimum Thinking Time": 30, "Skill Level": 20, "Ponder": "true"})

class StockFishEngine:
    
    def __init__(self):
        pass
    
    def set_fen_position(self, fen):
        stockfish.set_fen_position(fen)

    def get_best_move(self):
        return stockfish.get_best_move()

    def get_evaluation(self):
        return stockfish.get_evaluation()