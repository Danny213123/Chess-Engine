from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .models import MoveRequest, GameStateResponse
from .game_manager import GameManager

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

class FenRequest(BaseModel):
    fen: str

@app.post("/api/load-fen")
async def load_fen(req: FenRequest):
    """Load a position from a FEN string."""
    success, msg = gm.load_fen(req.fen)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
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

class EngineRequest(BaseModel):
    version: str
    color: str = None  # "white", "black", or None for both

@app.post("/api/engine")
async def set_engine(req: EngineRequest):
    success, msg = gm.set_engine_version(req.version, req.color)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {
        "status": "ok",
        "white_engine": gm.white_engine,
        "black_engine": gm.black_engine
    }

@app.post("/api/stop")
async def stop_search():
    """Stop any ongoing engine search immediately."""
    gm.stop_search()
    return {"status": "stopped"}

@app.post("/api/undo")
async def undo_move():
    """Undo the last move."""
    success, msg = gm.undo_move()
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return gm.get_state()

@app.post("/api/redo")
async def redo_move():
    """Redo a previously undone move."""
    success, msg = gm.redo_move()
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return gm.get_state()

@app.get("/api/search-history/export")
async def export_search_history():
    """Export comprehensive match statistics as JSON for analysis."""
    import json
    from fastapi.responses import Response
    from datetime import datetime

    # Calculate summary statistics
    engine_stats = {}
    for search in gm.search_history:
        engine = search['engine']
        if engine not in engine_stats:
            engine_stats[engine] = {
                'total_moves': 0,
                'avg_depth': 0,
                'avg_nodes': 0,
                'avg_time': 0,
                'avg_nps': 0,
                'depths': [],
                'nodes': [],
                'times': [],
                'nps_list': []
            }

        stats = engine_stats[engine]
        stats['total_moves'] += 1
        stats['depths'].append(search['depth'])
        stats['nodes'].append(search['nodes'])
        stats['times'].append(search['time'])
        stats['nps_list'].append(search['nps'])

    # Calculate averages
    for engine, stats in engine_stats.items():
        if stats['total_moves'] > 0:
            stats['avg_depth'] = sum(stats['depths']) / len(stats['depths'])
            stats['avg_nodes'] = sum(stats['nodes']) / len(stats['nodes'])
            stats['avg_time'] = sum(stats['times']) / len(stats['times'])
            stats['avg_nps'] = sum(stats['nps_list']) / len(stats['nps_list'])
            # Remove raw lists to reduce file size
            del stats['depths']
            del stats['nodes']
            del stats['times']
            del stats['nps_list']

    # Prepare graph data
    graphs = {
        'search_depth': [
            {
                'move': s['move_number'],
                'depth': s['depth'],
                'engine': s['engine'],
                'move_san': s['move']
            }
            for s in gm.search_history
        ],
        'nodes_searched': [
            {
                'move': s['move_number'],
                'nodes': s['nodes'],
                'engine': s['engine'],
                'move_san': s['move']
            }
            for s in gm.search_history
        ],
        'nodes_per_second': [
            {
                'move': s['move_number'],
                'nps': s['nps'],
                'engine': s['engine'],
                'move_san': s['move']
            }
            for s in gm.search_history
        ],
        'search_time': [
            {
                'move': s['move_number'],
                'time': s['time'],
                'engine': s['engine'],
                'move_san': s['move']
            }
            for s in gm.search_history
        ]
    }

    # Comprehensive export
    export_data = {
        'metadata': {
            'export_date': datetime.now().isoformat(),
            'total_moves': len(gm.search_history),
            'white_engine': gm.white_engine,
            'black_engine': gm.black_engine,
            'current_fen': gm.gs.get_fen()
        },
        'engine_statistics': engine_stats,
        'graphs': graphs,
        'search_history': gm.search_history
    }

    history_json = json.dumps(export_data, indent=2)

    return Response(
        content=history_json,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=match_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        }
    )

# Serve static files (frontend production build) when present.
client_dist = Path(__file__).resolve().parents[3] / "client" / "dist"
if client_dist.exists():
    app.mount("/", StaticFiles(directory=client_dist, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
