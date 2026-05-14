import pytest

from chess_engine.engine.v3.chess_engine import GameState
from chess_engine.engine.v6 import chess_algorithm as v6


def test_unavailable_v6_does_not_return_first_legal(monkeypatch):
    game_state = GameState()
    valid_moves = game_state.get_valid_moves()

    def missing_engine():
        raise ImportError("missing test module")

    monkeypatch.setattr(v6, "V6_AVAILABLE", False)
    monkeypatch.setattr(v6, "v6_engine", None)
    monkeypatch.setattr(v6, "_load_v6_engine", missing_engine)

    with pytest.raises(v6.V6UnavailableError):
        v6.find_best_move(game_state, valid_moves, "v6")


def test_illegal_v6_result_does_not_return_first_legal(monkeypatch):
    game_state = GameState()
    valid_moves = game_state.get_valid_moves()

    class FakeV6Engine:
        @staticmethod
        def find_best_move(fen, time_limit_ms, num_threads):
            return "a1a1", 0, 1, 1, 1

    monkeypatch.setattr(v6, "V6_AVAILABLE", True)
    monkeypatch.setattr(v6, "v6_engine", FakeV6Engine)
    monkeypatch.setattr(v6.OPENING_BOOK, "get_move", lambda fen_prefix: None)

    with pytest.raises(RuntimeError, match="not legal"):
        v6.find_best_move(game_state, valid_moves, "v6")
