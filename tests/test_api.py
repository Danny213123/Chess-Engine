from fastapi.testclient import TestClient

from chess_engine.server.app import app
from chess_engine.server.app import gm
from chess_engine.server import game_manager as game_manager_module


client = TestClient(app)


def test_api_move_flow():
    res = client.post("/api/new-game")
    assert res.status_code == 200

    res = client.post(
        "/api/move",
        json={"start_sq": "e2", "end_sq": "e4", "promotion": "Q"},
    )
    assert res.status_code == 200
    assert "fen" in res.json()

    res = client.post("/api/move", json={"start_sq": "e7", "end_sq": "e5"})
    assert res.status_code == 200
    assert "fen" in res.json()

    res = client.post("/api/move", json={"start_sq": "g1", "end_sq": "f3"})
    assert res.status_code == 200
    assert "fen" in res.json()


def test_rejects_removed_engine():
    res = client.post("/api/engine", json={"version": "external", "color": "white"})
    assert res.status_code == 400


def test_eval_endpoint_removed():
    res = client.get("/api/eval")
    assert res.status_code == 404


def test_v6_engine_selection_auto_builds(monkeypatch):
    calls = []

    def fake_ensure_available(auto_build=False):
        calls.append(auto_build)
        return object()

    monkeypatch.setattr(game_manager_module.algo_v6, "ensure_available", fake_ensure_available)

    res = client.post("/api/engine", json={"version": "v6", "color": "black"})

    assert res.status_code == 200
    assert calls == [True]
    assert res.json()["black_engine"] == "v6"


def test_v6_engine_selection_failure_preserves_previous_engine(monkeypatch):
    client.post("/api/engine", json={"version": "v5c", "color": "black"})
    previous_engine = gm.black_engine

    def fake_ensure_available(auto_build=False):
        raise game_manager_module.algo_v6.V6UnavailableError("CMake is missing")

    monkeypatch.setattr(game_manager_module.algo_v6, "ensure_available", fake_ensure_available)

    res = client.post("/api/engine", json={"version": "v6", "color": "black"})

    assert res.status_code == 400
    assert "CMake is missing" in res.json()["detail"]
    assert gm.black_engine == previous_engine
