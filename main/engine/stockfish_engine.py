from stockfish import Stockfish, StockfishException

class StockFishEngine:
    
    def __init__(self, path: str, depth: int, threads: int, minimum_thinking_time: int, skill_level: int, ponder: bool):
        self.stockfish = Stockfish(path, depth, parameters={"Threads": threads, "Minimum Thinking Time": minimum_thinking_time, "Skill Level": skill_level, "Ponder": ponder})

    def set_fen_position(self, fen: str):
        self.stockfish.set_fen_position(fen)

    def get_best_move(self):
        return self.stockfish.get_best_move()

    def get_evaluation(self):
        return self.stockfish.get_evaluation()