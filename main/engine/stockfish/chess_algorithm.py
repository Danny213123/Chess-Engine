"""
Stockfish Engine Wrapper
Provides the same interface as other engines but communicates with Stockfish via UCI.
"""
import subprocess
import time
import os
import shutil

# Try to find Stockfish executable
STOCKFISH_PATH = None

def find_stockfish():
    """Try to locate Stockfish executable."""
    global STOCKFISH_PATH
    
    # Common locations
    paths_to_try = [
        # User provided location
        os.path.join(os.path.dirname(__file__), '..', '..', 'stockfish', 'stockfish-windows-x86-64-avx2.exe'),
        "stockfish",  # In PATH
        "stockfish.exe",
        r"C:\stockfish\stockfish.exe",
        r"C:\Program Files\stockfish\stockfish.exe",
        r"C:\Program Files (x86)\stockfish\stockfish.exe",
        os.path.expanduser("~/stockfish/stockfish"),
        "/usr/local/bin/stockfish",
        "/usr/bin/stockfish",
    ]
    
    # Check if in PATH first
    sf_in_path = shutil.which("stockfish")
    if sf_in_path:
        STOCKFISH_PATH = sf_in_path
        print(f"[Stockfish] Found in PATH: {sf_in_path}")
        return True
    
    # Try explicit paths
    for path in paths_to_try:
        if os.path.isfile(path):
            STOCKFISH_PATH = path
            print(f"[Stockfish] Found at: {path}")
            return True
    
    print("[Stockfish] WARNING: Could not find Stockfish executable!")
    print("[Stockfish] Please install Stockfish and ensure it's in your PATH")
    return False

# Try to find on module load
find_stockfish()

class StockfishEngine:
    """Wrapper for Stockfish UCI engine."""
    
    def __init__(self, path=None, depth=12, time_limit=2.0):
        self.path = path or STOCKFISH_PATH
        self.depth = depth
        self.time_limit = time_limit
        self.process = None
        self.stats = {}
        
    def start(self):
        """Start Stockfish process."""
        if not self.path:
            raise RuntimeError("Stockfish path not set. Please install Stockfish.")
        
        self.process = subprocess.Popen(
            [self.path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Initialize UCI
        self._send("uci")
        self._wait_for("uciok")
        self._send("isready")
        self._wait_for("readyok")
        print("[Stockfish] Engine initialized")
        
    def stop(self):
        """Stop Stockfish process."""
        if self.process:
            self._send("quit")
            self.process.terminate()
            self.process = None
            
    def _send(self, command):
        """Send command to Stockfish."""
        if self.process:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
            
    def _read_line(self, timeout=10.0):
        """Read a line from Stockfish output."""
        if not self.process:
            return None
        try:
            return self.process.stdout.readline().strip()
        except:
            return None
            
    def _wait_for(self, expected, timeout=10.0):
        """Wait for specific response."""
        start = time.time()
        while time.time() - start < timeout:
            line = self._read_line()
            if line and expected in line:
                return line
        return None
        
    def get_best_move(self, fen, time_ms=2000):
        """Get best move for position."""
        if not self.process:
            self.start()
            
        # Set position
        self._send(f"position fen {fen}")
        
        # Start search
        self._send(f"go movetime {time_ms}")
        
        # Parse output
        best_move = None
        self.stats = {
            "depth": 0,
            "nodes": 0,
            "time": 0,
            "score": 0,
            "nps": 0,
            "pv": ""
        }
        
        while True:
            line = self._read_line()
            if not line:
                continue
                
            if line.startswith("info"):
                # Parse info line
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "depth" and i + 1 < len(parts):
                        self.stats["depth"] = int(parts[i + 1])
                    elif part == "nodes" and i + 1 < len(parts):
                        self.stats["nodes"] = int(parts[i + 1])
                    elif part == "time" and i + 1 < len(parts):
                        self.stats["time"] = int(parts[i + 1]) / 1000.0
                    elif part == "nps" and i + 1 < len(parts):
                        self.stats["nps"] = int(parts[i + 1])
                    elif part == "cp" and i + 1 < len(parts):
                        self.stats["score"] = int(parts[i + 1])
                    elif part == "mate" and i + 1 < len(parts):
                        mate_in = int(parts[i + 1])
                        self.stats["score"] = 10000 * (1 if mate_in > 0 else -1)
                    elif part == "pv" and i + 1 < len(parts):
                        self.stats["pv"] = " ".join(parts[i + 1:])
                        
            elif line.startswith("bestmove"):
                parts = line.split()
                if len(parts) >= 2:
                    best_move = parts[1]
                break
                
        return best_move, self.stats

# Global engine instance
_engine = None

def get_engine():
    """Get or create Stockfish engine instance."""
    global _engine
    if _engine is None:
        _engine = StockfishEngine()
    return _engine

def find_best_move(game_state, valid_moves, engine_name):
    """
    Find best move using Stockfish.
    Returns (move, stats) tuple to match V5 interface.
    """
    if not STOCKFISH_PATH:
        print("[Stockfish] ERROR: Stockfish not found, falling back to first legal move")
        return (valid_moves[0], {"depth": 0, "nodes": 0, "time": 0, "score": 0, "nps": 0, "pv": ""}) if valid_moves else (None, {})
    
    # Get FEN from game state
    fen = game_state.get_fen() if hasattr(game_state, 'get_fen') else str(game_state)
    
    print(f"[Stockfish] Analyzing position...")
    
    sf = get_engine()
    try:
        best_move_str, stats = sf.get_best_move(fen, time_ms=2000)
    except Exception as e:
        print(f"[Stockfish] Error: {e}")
        return (valid_moves[0], {"depth": 0, "nodes": 0, "time": 0, "score": 0, "nps": 0, "pv": ""}) if valid_moves else (None, {})
    
    print(f"[Stockfish] Best: {best_move_str} (depth {stats['depth']}, {stats['nodes']} nodes)")
    
    # Match Stockfish move to valid moves
    for vm in valid_moves:
        vm_str = str(vm).lower()
        if vm_str == best_move_str or vm_str.startswith(best_move_str):
            return vm, stats
    
    # Try coordinate matching
    if best_move_str and len(best_move_str) >= 4:
        from_sq = best_move_str[:2]
        to_sq = best_move_str[2:4]
        
        from_col = ord(from_sq[0]) - ord('a')
        from_row = 8 - int(from_sq[1])
        to_col = ord(to_sq[0]) - ord('a')
        to_row = 8 - int(to_sq[1])
        
        for vm in valid_moves:
            if (vm.start_row == from_row and vm.start_col == from_col and
                vm.end_row == to_row and vm.end_col == to_col):
                return vm, stats
    
    print(f"[Stockfish] Warning: Could not match move {best_move_str}, using first legal")
    return (valid_moves[0], stats) if valid_moves else (None, stats)
