import pytest

from chess_engine.engine.v6 import chess_algorithm as v6


@pytest.fixture(scope="module")
def v6_native_engine():
    try:
        return v6.ensure_available(auto_build=True)
    except Exception as error:
        pytest.skip(f"V6 native engine unavailable: {error}")


def test_v6_tempo_is_positive_for_side_to_move(v6_native_engine):
    white_to_move = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
    black_to_move = "4k3/8/8/8/8/8/8/4K3 b - - 0 1"

    white_score = v6_native_engine.evaluate(white_to_move)
    black_score = v6_native_engine.evaluate(black_to_move)

    assert white_score > 0
    assert black_score > 0


def test_v6_penalizes_early_queen_development(v6_native_engine):
    queen_home = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    queen_out = "rnbqkbnr/pppppppp/8/7Q/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1"

    assert v6_native_engine.evaluate(queen_home) > v6_native_engine.evaluate(queen_out)


def test_v6_rewards_development_against_rook_shuffling(v6_native_engine):
    rook_shuffle_position = (
        "1nbqkbn1/rppppppr/p6p/8/3P4/1PN1PN2/PBP1QPPP/R3KB1R b KQ - 0 7"
    )

    assert v6_native_engine.evaluate(rook_shuffle_position) < -60
