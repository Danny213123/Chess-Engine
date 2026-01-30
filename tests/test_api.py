import requests
import json
import pytest

BASE_URL = "http://localhost:8000/api"

def is_server_running():
    """Check if the server is running."""
    try:
        requests.get(f"{BASE_URL}/../", timeout=1)
        return True
    except requests.exceptions.ConnectionError:
        return False

@pytest.mark.skipif(not is_server_running(), reason="Server not running (start with python run_ui.py)")
def test_api():
    # 1. New Game
    print("Resetting game...")
    res = requests.post(f"{BASE_URL}/new-game")
    if res.status_code != 200:
        print("Failed to reset game:", res.text)
        return

    # 2. Try move e2e4
    payload = {
        "start_sq": "e2",
        "end_sq": "e4",
        "promotion": "Q"
    }
    print(f"Sending move: {payload}")
    res = requests.post(f"{BASE_URL}/move", json=payload)
    
    if res.status_code == 200:
        print("Move e2e4 SUCCESS!")
        print("New State:", res.json()['fen'])
    else:
        print("Move e2e4 FAILED!")
        print("Status:", res.status_code)
        print("Response:", res.text)
        return

    # 3. Try move e7e5 (Black)
    payload = {"start_sq": "e7", "end_sq": "e5"}
    print(f"Sending move: {payload}")
    res = requests.post(f"{BASE_URL}/move", json=payload)
    if res.status_code == 200:
        print("Move e7e5 SUCCESS!")
        print("New State:", res.json()['fen'])
    else:
        print("Move e7e5 FAILED!")
        print("Status:", res.status_code)
        print("Response:", res.text)
        return

    # 4. Try move g1f3 (White Knight)
    payload = {"start_sq": "g1", "end_sq": "f3"}
    print(f"Sending move: {payload}")
    res = requests.post(f"{BASE_URL}/move", json=payload)
    if res.status_code == 200:
        print("Move g1f3 SUCCESS!")
        print("New State:", res.json()['fen'])
    else:
        print("Move g1f3 FAILED!")
        print("Status:", res.status_code)
        print("Response:", res.text)


if __name__ == "__main__":
    try:
        test_api()
    except Exception as e:
        print(f"Could not connect to server: {e}")
        print("Make sure run_ui.py is running!")
