import { useState, useEffect } from 'react'
import axios from 'axios'
import CustomBoard from './CustomBoard'
import './App.css'

function App() {
  const [game, setGame] = useState({
    fen: "start",
    active_color: "w",
    history: [],
    is_check: false,
    is_checkmate: false,
    possible_moves: []
  });

  const [orientation, setOrientation] = useState("white");
  const [error, setError] = useState("");
  const [debugLog, setDebugLog] = useState([]);

  const log = (msg) => {
    setDebugLog(prev => [...prev.slice(-4), msg]); // Keep last 5
    console.log(msg);
  };

  // Log FEN on change
  useEffect(() => {
    log(`Current FEN: ${game.fen}`);
  }, [game.fen]);

  // Fetch initial state
  useEffect(() => {
    fetchState();
  }, []);

  const fetchState = async () => {
    try {
      const res = await axios.get('/api/state');
      setGame(res.data);
    } catch (err) {
      console.error("Failed to fetch state", err);
    }
  };

  const [hint, setHint] = useState("");
  const [hints, setHints] = useState([]);

  // onMove (Click-to-Move interface)
  const onMove = async (sourceSquare, targetSquare, type = "move") => {
    if (type === "select") {
      // Fetch Hint
      setHint("Thinking...");
      setHints([]);
      try {
        const res = await axios.post('/api/hint', { start_sq: sourceSquare });
        if (res.data.moves && res.data.moves.length > 0) {
          setHint("Best moves shown on board");
          // Map moves to arrows
          const newHints = res.data.moves.map((m, i) => ({
            start: m.move.substring(0, 2),
            end: m.move.substring(2, 4),
            opacity: Math.max(0.3, 1.0 - (i * 0.2)) // 1.0, 0.8, 0.6...
          }));
          setHints(newHints);
        } else {
          setHint("No move found");
        }
      } catch (e) {
        setHint("Hint error");
      }
      return;
    }
    if (type === "deselect") {
      setHint("");
      setHints([]);
      return;
    }

    // Move Logic
    try {
      setError("");
      setHint("");
      setHints([]); // Clear hints
      log(`Move: ${sourceSquare} -> ${targetSquare}`);

      const res = await axios.post('/api/move', {
        start_sq: sourceSquare,
        end_sq: targetSquare,
        promotion: "Q"
      });

      log(`Result: Success! New FEN: ${res.data.fen.substring(0, 15)}...`);
      setGame(res.data);

      // Trigger AI Move automatically if game not over
      if (!res.data.is_checkmate && !res.data.is_stalemate) {
        log("Triggering AI Move...");
        setTimeout(() => {
          aiMove();
        }, 500);
      }

      return true;
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || "Unknown Error";
      log(`Error: ${msg}`);
      setError(msg);
      return false;
    }
  };

  const resetGame = async () => {
    await axios.post('/api/new-game');
    fetchState();
    setError("");
    setHint("");
    setHints([]);
  };

  const aiMove = async () => {
    try {
      const res = await axios.post('/api/ai-move');
      setGame(res.data);
      setHints([]); // Clear hints if AI moves
    } catch (err) {
      alert("AI failed to move: " + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="app-container" style={{ display: 'flex', flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'center', gap: '20px' }}>

      {/* Left Column: Info & Controls */}
      <div className="info-panel" style={{ width: '250px', textAlign: 'left' }}>
        <h1>Chess Engine V2</h1>
        {error && <div className="error-banner" style={{ background: '#ff4444', padding: '10px', marginBottom: '10px', borderRadius: '4px' }}>{error}</div>}

        <div className="stats">
          <p>Turn: {game.active_color === 'w' ? "White" : "Black"}</p>
          <p>Check: {game.is_check ? "YES" : "No"}</p>
          <p>Mate: {game.is_checkmate ? "YES" : "No"}</p>
        </div>

        <div className="controls" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <button onClick={resetGame}>New Game</button>
          <button onClick={aiMove} disabled={game.is_checkmate}>AI Move</button>
          <button onClick={() => log("Test Log Clicked")}>Test Log</button>
        </div>

        <div className="hint-box" style={{ marginTop: '20px', padding: '10px', background: '#444', borderRadius: '4px', minHeight: '40px' }}>
          <strong>AI Hint:</strong><br />
          {hint || "Select a piece..."}
        </div>

        <div style={{ marginTop: '10px', fontSize: '10px', color: '#888' }}>
          RAW FEN: {game.fen}
        </div>
      </div>

      {/* Center Column: Board */}
      <div className="board-container">
        <CustomBoard
          fen={game.fen === 'start' ? 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1' : game.fen}
          onMove={onMove}
          orientation={orientation}
          log={log}
          hints={hints}
        />
      </div>

      {/* Right Column: Debug Log */}
      <div className="debug-panel" style={{ width: '300px', background: '#222', padding: '10px', height: '600px', overflowY: 'auto', borderRadius: '8px', border: '1px solid #444', textAlign: 'left', fontFamily: 'monospace', fontSize: '12px' }}>
        <h4 style={{ marginTop: 0, borderBottom: '1px solid #555', paddingBottom: '5px' }}>Debug Logic</h4>
        {debugLog.map((l, i) => (
          <div key={i} style={{ borderBottom: '1px solid #333', padding: '2px 0' }}>{l}</div>
        ))}
        <div id="log-end"></div>
      </div>
    </div>
  )
}

export default App
