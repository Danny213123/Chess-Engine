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
    gm.set_engine_version(req.version, req.color)
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

@app.get("/api/eval")
async def get_position_eval():
    """Get quick Stockfish evaluation of current position."""
    try:
        from main.engine.stockfish.chess_algorithm import get_engine
        sf = get_engine()
        fen = gm.gs.get_fen()
        _, sf_stats = sf.get_best_move(fen, time_ms=100)
        raw_eval = sf_stats.get("score", 0)
        
        # Normalize to White's perspective
        parts = fen.split()
        side_to_move = parts[1] if len(parts) > 1 else 'w'
        
        if side_to_move == 'w':
            normalized_eval = raw_eval
        else:
            normalized_eval = -raw_eval
        
        return {"eval": normalized_eval, "fen": fen}
    except Exception as e:
        return {"eval": 0, "error": str(e)}

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

    # Position evaluation summary
    stockfish_evals = [s['stockfish_eval'] for s in gm.search_history if s.get('stockfish_eval') is not None]
    eval_summary = None
    if stockfish_evals:
        eval_summary = {
            'min_eval': min(stockfish_evals),
            'max_eval': max(stockfish_evals),
            'avg_eval': sum(stockfish_evals) / len(stockfish_evals),
            'total_positions_evaluated': len(stockfish_evals)
        }

    # Prepare graph data
    graphs = {
        'position_evaluation': [
            {
                'move': s['move_number'],
                'eval': s['stockfish_eval'],
                'color': s['color'],
                'move_san': s['move']
            }
            for s in gm.search_history if s.get('stockfish_eval') is not None
        ],
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
        'position_evaluation_summary': eval_summary,
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

# Serve static files (Frontend)
# relative path to client/dist
client_dist = os.path.join(os.path.dirname(__file__), '..', 'client', 'dist')
if os.path.exists(client_dist):
    app.mount("/", StaticFiles(directory=client_dist, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
