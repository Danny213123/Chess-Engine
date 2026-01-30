from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .models import MoveRequest, GameStateResponse
from .game_manager import GameManager
import os

app = FastAPI()

# Allow CORS for dev (React Vite runs on 5173 by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gm = GameManager()

@app.get("/api/state", response_model=GameStateResponse)
async def get_state():
    return gm.get_state()

@app.post("/api/new-game")
async def new_game():
    gm.reset()
    return gm.get_state()

@app.post("/api/move")
async def make_move(move: MoveRequest):
    success, msg = gm.make_move_lan(move.start_sq, move.end_sq, move.promotion)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return gm.get_state()

@app.post("/api/ai-move")
async def ai_move():
    move = gm.ai_move()
    if not move:
        raise HTTPException(status_code=400, detail="AI Checkmate/Stalemate or failure")
    return gm.get_state()

class HintRequest(BaseModel):
    start_sq: str = None

@app.post("/api/hint")
async def get_hint(req: HintRequest):
    moves = gm.get_best_move(req.start_sq)
    return {"moves": moves}

# Serve static files (Frontend)
# relative path to client/dist
client_dist = os.path.join(os.path.dirname(__file__), '..', 'client', 'dist')
if os.path.exists(client_dist):
    app.mount("/", StaticFiles(directory=client_dist, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
