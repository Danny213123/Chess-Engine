import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import CustomBoard from './CustomBoard'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import './App.css'

function App() {
  const [game, setGame] = useState({
    fen: "start",
    active_color: "w",
    history: [],
    move_history_san: [],
    last_search_stats: null,
    is_check: false,
    is_checkmate: false,
    is_stalemate: false,
    possible_moves: []
  });

  const [orientation, setOrientation] = useState("black");  // Default to black's view since human plays black by default
  const [error, setError] = useState("");
  const [debugLog, setDebugLog] = useState([]);
  const logEndRef = useRef(null);

  const log = (msg) => {
    setDebugLog(prev => [...prev.slice(-99), msg]);
    // Console log for dev
    console.log(msg);
  };

  // Scroll to bottom of log
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [debugLog]);

  // Fetch initial state and set default engine config
  useEffect(() => {
    const initialize = async () => {
      await fetchState();
      // Set default engine configuration (human plays black vs v5c)
      try {
        await axios.post('/api/engine', { version: 'v5c', color: 'white' });
        await axios.post('/api/engine', { version: 'human', color: 'black' });
        log("white -> v5c");
        log("black -> human");
      } catch (e) {
        console.error("Failed to set default engines", e);
      }
    };
    initialize();
  }, []);

  const fetchState = async () => {
    try {
      const res = await axios.get('/api/state');
      setGame(res.data);
    } catch (err) {
      console.error("Failed to fetch state", err);
    }
  };

  // Current position evaluation (fetched from Stockfish)
  const [currentEval, setCurrentEval] = useState(0);

  // Fetch evaluation whenever FEN changes
  useEffect(() => {
    const fetchEval = async () => {
      try {
        const res = await axios.get('/api/eval');
        if (res.data && typeof res.data.eval === 'number') {
          setCurrentEval(res.data.eval);
        }
      } catch (err) {
        console.error("Failed to fetch eval", err);
      }
    };

    if (game.fen && game.fen !== "start") {
      fetchEval();
    }
  }, [game.fen]);

  const [hints, setHints] = useState([]);
  const [promotionPending, setPromotionPending] = useState(null);

  // onMove (Click-to-Move interface)
  const onMove = async (sourceSquare, targetSquare, type = "move") => {
    if (type === "select" || type === "deselect") {
      setHints([]);
      return;
    }

    // Check if this is a pawn promotion
    const sourceRank = sourceSquare[1];
    const targetRank = targetSquare[1];
    const isPromotion = (
      (sourceRank === '7' && targetRank === '8' && game.active_color === 'w') ||
      (sourceRank === '2' && targetRank === '1' && game.active_color === 'b')
    );

    const fenBoard = game.fen.split(' ')[0];
    const isPawnMove = checkIfPawnMove(sourceSquare, fenBoard, game.active_color);

    if (isPromotion && isPawnMove) {
      setPromotionPending({ source: sourceSquare, target: targetSquare, color: game.active_color });
      return;
    }

    await executeMove(sourceSquare, targetSquare, null);
  };

  // Helper to check if piece at square is a pawn
  const checkIfPawnMove = (square, fenBoard, activeColor) => {
    const file = square.charCodeAt(0) - 97;
    const rank = parseInt(square[1]);
    const row = 8 - rank;

    const rows = fenBoard.split('/');
    if (row < 0 || row >= 8) return false;

    let col = 0;
    for (const char of rows[row]) {
      if (col === file) {
        if (activeColor === 'w' && char === 'P') return true;
        if (activeColor === 'b' && char === 'p') return true;
        return false;
      }
      if (char >= '1' && char <= '8') {
        col += parseInt(char);
      } else {
        col++;
      }
    }
    return false;
  };

  const executeMove = async (sourceSquare, targetSquare, promotion) => {
    try {
      setError("");
      setHints([]);

      const res = await axios.post('/api/move', {
        start_sq: sourceSquare,
        end_sq: targetSquare,
        promotion: promotion || "Q"
      });

      setGame(res.data);

      if (!res.data.is_checkmate && !res.data.is_stalemate) {
        // Automatically interact if AI mode logic requires it? 
        // For now, let's keep the manual trigger or aiMove logic separate unless Battle Mode
        if (battleMode) {
          // In battle mode, next move is automatic
        } else {
          // If Human played, trigger AI? 
          // Typically yes if Human vs AI. 
          // But UI allows Engine Selection for both.
          // If the SIDE TO MOVE has an engine assigned that is NOT "Human" (implied), we could trigger.
          // But let's keep it simple: 
          // Manual Trigger Logic
          // Check if the side to move (which is now NOT the one who just moved) is AI
          const sideToMove = res.data.active_color === 'w' ? 'white' : 'black';
          const nextEngine = sideToMove === 'white' ? whiteEngine : blackEngine;

          log(`Move Complete. Active: ${res.data.active_color} (${sideToMove})`);
          log(`Next Engine: ${nextEngine}`);

          if (nextEngine !== 'human') {
            log("Triggering AI...");
            setTimeout(() => {
              aiMove();
            }, 500);
          } else {
            log("Waiting for Human...");
          }
        }
      }

      return true;
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || "Unknown Error";
      log(`Error: ${msg}`);
      setError(msg);
      return false;
    }
  };

  const handlePromotion = async (piece) => {
    if (!promotionPending) return;
    const { source, target } = promotionPending;
    setPromotionPending(null);
    await executeMove(source, target, piece);
  };

  const cancelPromotion = () => {
    setPromotionPending(null);
  };

  const [whiteEngine, setWhiteEngine] = useState("v5c");
  const [blackEngine, setBlackEngine] = useState("human");
  const [battleMode, setBattleMode] = useState(false);
  const [showSearchHistory, setShowSearchHistory] = useState(false);

  // Drag state for search history panel
  const [dragPosition, setDragPosition] = useState({ x: window.innerWidth - 380, y: 20 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging) return;
      setDragPosition({
        x: e.clientX - dragOffset.x,
        y: e.clientY - dragOffset.y
      });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, dragOffset]);

  const handleMouseDown = (e) => {
    setIsDragging(true);
    setDragOffset({
      x: e.clientX - dragPosition.x,
      y: e.clientY - dragPosition.y
    });
  };

  const switchEngine = async (ver, color) => {
    try {
      await axios.post('/api/engine', { version: ver, color: color });
      if (color === "white") {
        setWhiteEngine(ver);
        // Auto-flip board: if white is engine and black is human, show black's perspective
        if (ver !== "human" && blackEngine === "human") {
          setOrientation("black");
        } else if (ver === "human" && blackEngine !== "human") {
          setOrientation("white");
        }
      } else if (color === "black") {
        setBlackEngine(ver);
        // Auto-flip board: if black is human and white is engine, show black's perspective
        if (ver === "human" && whiteEngine !== "human") {
          setOrientation("black");
        } else if (ver !== "human" && whiteEngine === "human") {
          setOrientation("white");
        }
      }
      log(`${color} -> ${ver}`);
    } catch (e) {
      log("Error switching engine");
    }
  };

  useEffect(() => {
    let timer;
    if (battleMode && !game.is_checkmate && !game.is_stalemate) {
      // Check if current side to move is human - if so, don't auto-play
      const sideToMove = game.active_color === 'w' ? 'white' : 'black';
      const currentEngine = sideToMove === 'white' ? whiteEngine : blackEngine;

      if (currentEngine !== 'human') {
        timer = setTimeout(() => {
          aiMove();
        }, 500);
      }
    }
    return () => clearTimeout(timer);
  }, [battleMode, game.fen, game.is_checkmate, game.is_stalemate, game.active_color, whiteEngine, blackEngine]);

  const toggleBattle = async () => {
    if (battleMode) {
      // Stopping - force stop any ongoing searches
      try {
        await axios.post('/api/stop');
        log("Battle Stopped - Search Cancelled");
      } catch (e) {
        log("Battle Stopped");
      }
      setBattleMode(false);
    } else {
      // Starting
      setBattleMode(true);
      log("Battle Started");
    }
  }

  const resetGame = async () => {
    setBattleMode(false);
    await axios.post('/api/new-game');
    fetchState();
    setError("");
    setHints([]);
    setDebugLog([]);
    log("New Game Started");
  };

  const undoMove = async () => {
    try {
      const res = await axios.post('/api/undo');
      setGame(res.data);
      log("Move undone");
    } catch (err) {
      log("Cannot undo: " + (err.response?.data?.detail || err.message));
    }
  };

  const redoMove = async () => {
    try {
      const res = await axios.post('/api/redo');
      setGame(res.data);
      log("Move redone");
    } catch (err) {
      log("Cannot redo: " + (err.response?.data?.detail || err.message));
    }
  };

  const [fenInput, setFenInput] = useState("");

  const loadFen = async () => {
    if (!fenInput.trim()) {
      log("Please enter a FEN string");
      return;
    }
    try {
      setBattleMode(false);
      const res = await axios.post('/api/load-fen', { fen: fenInput.trim() });
      setGame(res.data);
      setError("");
      log("Position loaded from FEN");
    } catch (err) {
      log("Invalid FEN: " + (err.response?.data?.detail || err.message));
    }
  };

  const aiMove = async () => {
    try {
      const res = await axios.post('/api/ai-move');
      setGame(res.data);
    } catch (err) {
      // If error (e.g. game over), stop battle
      setBattleMode(false);
    }
  };

  // Prepare Move Pairs for Table
  const movePairs = [];
  if (game.move_history_san) {
    for (let i = 0; i < game.move_history_san.length; i += 2) {
      movePairs.push([game.move_history_san[i], game.move_history_san[i + 1]]);
    }
  }

  return (
    <div className="app-container">

      {/* Promotion Modal */}
      {promotionPending && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#2a2a2a', padding: '20px', textAlign: 'center', boxShadow: '0 8px 32px rgba(0,0,0,0.4)', border: '1px solid #444'
          }}>
            <h3 style={{ color: '#fff', border: 'none' }}>Promote to</h3>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginBottom: '15px' }}>
              {['Q', 'R', 'B', 'N'].map(piece => (
                <button
                  key={piece}
                  onClick={() => handlePromotion(piece)}
                  style={{ fontSize: '24px', width: '50px', height: '50px' }}
                >
                  {piece}
                </button>
              ))}
            </div>
            <button onClick={cancelPromotion}>Cancel</button>
          </div>
        </div>
      )}

      {/* Left Panel: Settings & Log */}
      <div className="info-panel">
        <div style={{ marginBottom: '20px' }}>
          <h2>Chess Arena</h2>
          <div style={{ color: '#666', fontSize: '13px' }}>v5 Bitboard Engine</div>
        </div>

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <h3>Engine Config</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '20px' }}>
            <select value={whiteEngine} onChange={(e) => switchEngine(e.target.value, "white")}>
              <option value="human">White: Human</option>
              <option value="stockfish">White: Stockfish</option>
              <option value="v6">White: V6 (C++)</option>
              <option value="v5d">White: V5d (5s)</option>
              <option value="v5c">White: V5c</option>
              <option value="v5b">White: V5b</option>
              <option value="v5">White: V5</option>
              <option value="v4c">White: V4c</option>
              <option value="v4b">White: V4b</option>
              <option value="v3">White: V3</option>
            </select>
            <select value={blackEngine} onChange={(e) => switchEngine(e.target.value, "black")}>
              <option value="human">Black: Human</option>
              <option value="stockfish">Black: Stockfish</option>
              <option value="v6">Black: V6 (C++)</option>
              <option value="v5d">Black: V5d (5s)</option>
              <option value="v5c">Black: V5c</option>
              <option value="v5b">Black: V5b</option>
              <option value="v5">Black: V5</option>
              <option value="v4c">Black: V4c</option>
              <option value="v4b">Black: V4b</option>
              <option value="v3">Black: V3</option>
            </select>
          </div>

          <h3>Controls</h3>
          <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
            <button className={`primary`} style={{ flex: 1 }} onClick={toggleBattle}>
              {battleMode ? "Stop Battle" : "Start Battle"}
            </button>
            <button onClick={resetGame}>Reset</button>
            <button onClick={() => setOrientation(orientation === 'white' ? 'black' : 'white')}>
              Flip Board
            </button>
          </div>
          <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
            <button onClick={undoMove} title="Undo (Ctrl+Z)">
              ← Undo
            </button>
            <button onClick={redoMove} title="Redo (Ctrl+Y)">
              Redo →
            </button>
          </div>

          <h3>Load Position (FEN)</h3>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
            <input
              type="text"
              value={fenInput}
              onChange={(e) => setFenInput(e.target.value)}
              placeholder="Paste FEN string..."
              style={{
                flex: 1,
                padding: '8px',
                borderRadius: '4px',
                border: '1px solid #444',
                background: '#2a2a2a',
                color: '#fff',
                fontSize: '12px'
              }}
              onKeyDown={(e) => { if (e.key === 'Enter') loadFen(); }}
            />
            <button onClick={loadFen}>Load</button>
          </div>

          <h3>Debug Log</h3>
          <pre className="log-output">
            {debugLog.map((l, i) => <div key={i}>{l}</div>)}
            <div ref={logEndRef} />
          </pre>
        </div>
      </div>

      {/* Center: Board */}
      <div className="main-board-area">
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          {/* Evaluation Bar (Lichess Style - Horizontal Above Board) */}
          {(() => {
            // Use live evaluation from /api/eval (currentEval is in centipawns)
            const latestEval = currentEval;

            // Convert centipawns to pawns
            const evalInPawns = latestEval / 100;
            const clampedEval = Math.max(-10, Math.min(10, evalInPawns));

            // Convert to percentage (0% = -10 pawns/Black winning, 100% = +10 pawns/White winning)
            const percentage = ((clampedEval + 10) / 20) * 100;

            // For display
            const absEval = Math.abs(evalInPawns).toFixed(1);
            const isWhiteWinning = evalInPawns > 0;
            const isBlackWinning = evalInPawns < 0;

            return (
              <div style={{
                width: '100%',
                maxWidth: '560px', // Match board width roughly or use standard
                height: '24px',
                background: '#404040', // Base color (Black side usually)
                marginBottom: '8px',
                borderRadius: '3px',
                position: 'relative',
                display: 'flex',
                overflow: 'hidden',
                boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
              }}>
                {/* White side (Left) */}
                <div style={{
                  width: `${percentage}%`,
                  height: '100%',
                  background: '#f0f0f0', // White side color
                  transition: 'width 0.5s ease-out'
                }} />

                {/* Score Text */}
                <div style={{
                  position: 'absolute',
                  top: 0, bottom: 0, left: 0, right: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '11px',
                  fontWeight: 'bold',
                  color: isWhiteWinning ? '#222' : (isBlackWinning ? '#fff' : '#888'),
                  textShadow: '0 0 2px rgba(0,0,0,0.1)'
                }}>
                  {evalInPawns > 0 ? `+${absEval}` : (evalInPawns < 0 ? `-${absEval}` : '0.0')}
                </div>
              </div>
            );
          })()}

          <div className="board-container">
            <CustomBoard
              fen={game.fen === 'start' ? 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1' : game.fen}
              onMove={onMove}
              orientation={orientation}
              log={log}
              hints={hints}
            />
          </div>
          {/* FEN Display */}
          <div style={{
            marginTop: '10px',
            padding: '8px 12px',
            background: '#1a1a1a',
            border: '1px solid #333',
            fontFamily: 'monospace',
            fontSize: '11px',
            color: '#888',
            maxWidth: '100%',
            wordBreak: 'break-all'
          }}>
            <span style={{ color: '#666' }}>FEN:</span> {game.fen}
          </div>
        </div>
      </div>

      {/* Right Panel: History & Stats */}
      <div className="log-panel">

        <h3>Last Search</h3>
        {game.last_search_stats ? (
          <div style={{ background: '#1a1a1a', padding: '10px', marginBottom: '20px', border: '1px solid #333' }}>
            <div className="debug-stat">
              <span className="stat-label">Depth</span>
              <span className="stat-value">{game.last_search_stats.depth}</span>
            </div>
            <div className="debug-stat">
              <span className="stat-label">Nodes</span>
              <span className="stat-value">{game.last_search_stats.nodes.toLocaleString()}</span>
            </div>
            <div className="debug-stat">
              <span className="stat-label">Time</span>
              <span className="stat-value">{game.last_search_stats.time.toFixed(3)}s</span>
            </div>
            <div className="debug-stat">
              <span className="stat-label">NPS</span>
              <span className="stat-value">{game.last_search_stats.nps.toLocaleString()}</span>
            </div>
            <div className="debug-stat">
              <span className="stat-label">Score</span>
              <span className="stat-value">{game.last_search_stats.score} cp</span>
            </div>
            <div style={{ marginTop: '5px', fontSize: '11px', color: '#888', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              PV: {game.last_search_stats.pv}
            </div>
          </div>
        ) : (
          <div style={{ padding: '10px', color: '#666', fontStyle: 'italic', marginBottom: '20px' }}>
            No search data needed for human move.
          </div>
        )}

        <h3>Move History</h3>
        <div style={{ flex: 1, overflowY: 'auto', border: '1px solid #333' }}>
          <table className="move-list-table">
            <thead>
              <tr>
                <th style={{ width: '40px' }}>#</th>
                <th>White</th>
                <th>Black</th>
              </tr>
            </thead>
            <tbody>
              {movePairs.map((pair, i) => (
                <tr key={i}>
                  <td style={{ color: '#666' }}>{i + 1}.</td>
                  <td style={{ color: '#fff' }}>{pair[0]}</td>
                  <td style={{ color: '#ccc' }}>{pair[1] || ''}</td>
                </tr>
              ))}
              {movePairs.length === 0 && (
                <tr><td colSpan="3" style={{ textAlign: 'center', padding: '20px', color: '#666' }}>No moves yet</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div style={{ marginTop: '10px' }}>
          <div style={{ fontSize: '12px', color: '#888' }}>
            State: {game.active_color === 'w' ? "White to move" : "Black to move"}
          </div>
          {game.is_check && <div style={{ color: '#ff9800', fontWeight: 'bold' }}>CHECK!</div>}
          {game.is_checkmate && <div style={{ color: '#f44336', fontWeight: 'bold' }}>CHECKMATE!</div>}
        </div>

        {/* Search History Toggle */}
        <button
          onClick={() => setShowSearchHistory(!showSearchHistory)}
          style={{ marginTop: '15px', width: '100%' }}
        >
          {showSearchHistory ? 'Hide Search History' : 'Show Search History'}
        </button>

        {/* Export Search History */}
        {game.search_history && game.search_history.length > 0 && (
          <button
            onClick={() => {
              window.open('/api/search-history/export', '_blank');
            }}
            style={{ marginTop: '10px', width: '100%', fontSize: '12px' }}
          >
            Export History (JSON)
          </button>
        )}

      </div>

      {/* Search History Panel */}
      {showSearchHistory && (
        <div
          className="search-history-panel"
          style={{
            position: 'fixed',
            left: dragPosition.x,
            top: dragPosition.y,
            width: '350px',
            minWidth: '300px',
            maxWidth: '800px',
            maxHeight: '90vh',
            background: '#1a1a1a',
            border: '1px solid #444',
            borderRadius: '8px',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 1000,
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            resize: 'both',
            overflow: 'hidden'
          }}
        >
          {/* Draggable Header */}
          <div
            onMouseDown={handleMouseDown}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '15px',
              background: '#252525',
              borderBottom: '1px solid #333',
              cursor: isDragging ? 'grabbing' : 'grab',
              userSelect: 'none'
            }}
          >
            <h3 style={{ margin: 0, border: 'none', fontSize: '16px' }}>Search History</h3>
            <button
              onClick={() => setShowSearchHistory(false)}
              style={{ padding: '4px 8px', fontSize: '12px', background: '#444', border: 'none', borderRadius: '4px', color: '#fff', cursor: 'pointer' }}
            >
              Close
            </button>
          </div>

          <div style={{ padding: '15px', overflowY: 'auto', flex: 1 }}>

            {/* Engine Performance Stats */}
            {game.search_history && game.search_history.length > 0 && (() => {
              const engineStats = {};
              game.search_history.forEach(search => {
                if (!engineStats[search.engine]) {
                  engineStats[search.engine] = { depths: [], nodes: [], times: [], nps: [], count: 0 };
                }
                engineStats[search.engine].depths.push(search.depth);
                engineStats[search.engine].nodes.push(search.nodes);
                engineStats[search.engine].times.push(search.time);
                engineStats[search.engine].nps.push(search.nps);
                engineStats[search.engine].count++;
              });

              const avg = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length;

              return (
                <div style={{ marginBottom: '15px', padding: '10px', background: '#252525', border: '1px solid #333', borderRadius: '4px' }}>
                  <h4 style={{ margin: '0 0 10px 0', fontSize: '13px', color: '#888' }}>Average Performance</h4>
                  {Object.entries(engineStats).map(([engine, stats]) => (
                    <div key={engine} style={{ marginBottom: '8px', fontSize: '11px', padding: '6px', background: '#1a1a1a', borderRadius: '3px' }}>
                      <div style={{ fontWeight: 'bold', color: '#4CAF50', marginBottom: '4px' }}>
                        {engine.toUpperCase()} ({stats.count} moves)
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px', color: '#ccc' }}>
                        <div>Depth: {avg(stats.depths).toFixed(1)}</div>
                        <div>Time: {avg(stats.times).toFixed(2)}s</div>
                        <div>Nodes: {Math.round(avg(stats.nodes)).toLocaleString()}</div>
                        <div>NPS: {Math.round(avg(stats.nps)).toLocaleString()}</div>
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}

            {/* Match Analysis Graphs */}
            {game.search_history && game.search_history.length > 0 && game.search_history.some(s => s.stockfish_eval !== undefined && s.stockfish_eval !== null) && (
              <div style={{ marginBottom: '20px' }}>
                <h4 style={{ margin: '0 0 15px 0', fontSize: '13px', color: '#888' }}>Match Analysis</h4>

                {/* Position Evaluation Graph */}
                <div style={{ marginBottom: '20px', padding: '15px', background: '#252525', border: '1px solid #333', borderRadius: '4px' }}>
                  <h5 style={{ margin: '0 0 5px 0', fontSize: '12px', color: '#4CAF50' }}>Position Evaluation (Stockfish)</h5>
                  <div style={{ fontSize: '10px', color: '#666', marginBottom: '10px' }}>Positive = White better | Negative = Black better</div>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={game.search_history.filter(s => s.stockfish_eval !== undefined && s.stockfish_eval !== null).map(s => ({
                      move: s.move_number,
                      eval: s.stockfish_eval / 100, // Convert centipawns to pawns for readability
                      move_san: s.move,
                      color: s.color
                    }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                      <XAxis dataKey="move" stroke="#888" label={{ value: 'Move #', position: 'insideBottom', offset: -5, fill: '#888' }} />
                      <YAxis stroke="#888" label={{ value: 'Evaluation', angle: -90, position: 'insideLeft', fill: '#888' }} domain={['auto', 'auto']} />
                      <Tooltip
                        contentStyle={{ background: '#1a1a1a', border: '1px solid #333', borderRadius: '4px' }}
                        labelStyle={{ color: '#4CAF50' }}
                        itemStyle={{ color: '#fff' }}
                        formatter={(value) => {
                          const evalNum = value;
                          const advantage = evalNum > 0 ? 'White' : evalNum < 0 ? 'Black' : 'Equal';
                          const absVal = Math.abs(evalNum).toFixed(2);
                          return [`${advantage} ${absVal !== '0.00' ? '+' + absVal : ''}`, 'Eval'];
                        }}
                        labelFormatter={(label) => {
                          const dataPoint = game.search_history.filter(s => s.stockfish_eval !== undefined && s.stockfish_eval !== null)[label - game.search_history.filter(s => s.stockfish_eval !== undefined && s.stockfish_eval !== null)[0]?.move_number] || game.search_history.find(s => s.move_number === label);
                          return dataPoint ? `Move ${label}: ${dataPoint.move}` : `Move ${label}`;
                        }}
                      />
                      {/* Reference line at 0 (equal position) */}
                      <Line type="monotone" dataKey={() => 0} stroke="#666" strokeWidth={1} strokeDasharray="5 5" dot={false} legendType="none" />
                      {/* Evaluation line */}
                      <Line type="monotone" dataKey="eval" stroke="#4CAF50" strokeWidth={2} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Engine Performance Graphs */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                  {/* Depth Graph */}
                  <div style={{ padding: '15px', background: '#252525', border: '1px solid #333', borderRadius: '4px' }}>
                    <h5 style={{ margin: '0 0 10px 0', fontSize: '12px', color: '#4CAF50' }}>Search Depth</h5>
                    <ResponsiveContainer width="100%" height={150}>
                      <LineChart data={game.search_history.map(s => ({
                        move: s.move_number,
                        depth: s.depth,
                        engine: s.engine
                      }))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                        <XAxis dataKey="move" stroke="#888" />
                        <YAxis stroke="#888" />
                        <Tooltip
                          contentStyle={{ background: '#1a1a1a', border: '1px solid #333' }}
                          labelStyle={{ color: '#4CAF50' }}
                        />
                        <Line type="monotone" dataKey="depth" stroke="#2196F3" strokeWidth={2} dot={{ r: 2 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Nodes Graph */}
                  <div style={{ padding: '15px', background: '#252525', border: '1px solid #333', borderRadius: '4px' }}>
                    <h5 style={{ margin: '0 0 10px 0', fontSize: '12px', color: '#4CAF50' }}>Nodes Searched</h5>
                    <ResponsiveContainer width="100%" height={150}>
                      <LineChart data={game.search_history.map(s => ({
                        move: s.move_number,
                        nodes: s.nodes,
                        engine: s.engine
                      }))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                        <XAxis dataKey="move" stroke="#888" />
                        <YAxis stroke="#888" />
                        <Tooltip
                          contentStyle={{ background: '#1a1a1a', border: '1px solid #333' }}
                          labelStyle={{ color: '#4CAF50' }}
                        />
                        <Line type="monotone" dataKey="nodes" stroke="#FF9800" strokeWidth={2} dot={{ r: 2 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  {/* NPS Graph */}
                  <div style={{ padding: '15px', background: '#252525', border: '1px solid #333', borderRadius: '4px' }}>
                    <h5 style={{ margin: '0 0 10px 0', fontSize: '12px', color: '#4CAF50' }}>Nodes Per Second</h5>
                    <ResponsiveContainer width="100%" height={150}>
                      <LineChart data={game.search_history.map(s => ({
                        move: s.move_number,
                        nps: s.nps,
                        engine: s.engine
                      }))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                        <XAxis dataKey="move" stroke="#888" />
                        <YAxis stroke="#888" />
                        <Tooltip
                          contentStyle={{ background: '#1a1a1a', border: '1px solid #333' }}
                          labelStyle={{ color: '#4CAF50' }}
                        />
                        <Line type="monotone" dataKey="nps" stroke="#9C27B0" strokeWidth={2} dot={{ r: 2 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Time Graph */}
                  <div style={{ padding: '15px', background: '#252525', border: '1px solid #333', borderRadius: '4px' }}>
                    <h5 style={{ margin: '0 0 10px 0', fontSize: '12px', color: '#4CAF50' }}>Search Time (s)</h5>
                    <ResponsiveContainer width="100%" height={150}>
                      <LineChart data={game.search_history.map(s => ({
                        move: s.move_number,
                        time: s.time,
                        engine: s.engine
                      }))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                        <XAxis dataKey="move" stroke="#888" />
                        <YAxis stroke="#888" />
                        <Tooltip
                          contentStyle={{ background: '#1a1a1a', border: '1px solid #333' }}
                          labelStyle={{ color: '#4CAF50' }}
                        />
                        <Line type="monotone" dataKey="time" stroke="#F44336" strokeWidth={2} dot={{ r: 2 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}

            {game.search_history && game.search_history.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {game.search_history.map((search, i) => (
                  <div key={i} style={{
                    background: '#252525',
                    padding: '10px',
                    border: '1px solid #333',
                    borderLeft: `3px solid ${search.color === 'white' ? '#fff' : '#666'}`
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                      <span style={{ color: '#4CAF50', fontWeight: 'bold' }}>#{search.move_number} {search.move}</span>
                      <span style={{ color: '#888', fontSize: '11px' }}>{search.engine.toUpperCase()}</span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '5px', fontSize: '11px' }}>
                      <div><span style={{ color: '#666' }}>Depth:</span> <span style={{ color: '#fff' }}>{search.depth}</span></div>
                      <div><span style={{ color: '#666' }}>Score:</span> <span style={{ color: search.score >= 0 ? '#4CAF50' : '#f44336' }}>{search.score} cp</span></div>
                      <div><span style={{ color: '#666' }}>Nodes:</span> <span style={{ color: '#fff' }}>{search.nodes.toLocaleString()}</span></div>
                      <div><span style={{ color: '#666' }}>NPS:</span> <span style={{ color: '#fff' }}>{search.nps.toLocaleString()}</span></div>
                      <div style={{ gridColumn: '1 / -1' }}><span style={{ color: '#666' }}>Time:</span> <span style={{ color: '#fff' }}>{search.time.toFixed(3)}s</span></div>
                    </div>
                    {search.pv && (
                      <div style={{ marginTop: '5px', fontSize: '10px', color: '#888', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        PV: {search.pv}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: 'center', color: '#666', padding: '20px' }}>
                No search history yet. AI moves will appear here.
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  )
}

export default App
