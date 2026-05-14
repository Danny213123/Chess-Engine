
import threading
import time
import queue
from typing import List, Tuple, Any, Optional

# NOTE: We defer importing cuda_kernels until the service starts.
# This allows device.py to set up CUDA paths first.

class EvaluationRequest:
    """A request for board evaluation."""
    def __init__(self, game_state):
        self.game_state = game_state
        self.result = None
        self.event = threading.Event()
        self.error = None

class GPUBatchService:
    """
    Singleton service that collects single evaluation requests from multiple threads,
    batches them, runs them on the GPU, and returns results.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GPUBatchService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.queue = queue.Queue()
        self.running = False
        self.worker_thread = None
        self.MAX_BATCH_SIZE = 4096  # Huge batch size capacity
        self.BATCH_TIMEOUT = 0.010  # 10ms waiting for more items (bigger batches = better GPU use)
        self._batch_count = 0  # For debug logging
        self._batch_evaluate_fn = None # Will be set on start()
        
        # Defer CUDA check until start() is called explicitly
        # This allows device.py to initialize CUDA paths first

    def start(self):
        """Start the GPU batch service. Must be called after device.py has initialized CUDA."""
        if self.running: return
        
        # Now it's safe to import cuda_kernels (device.py should have run by now)
        try:
            from chess_engine.engine.v3.cuda_kernels import batch_evaluate_positions, CUDA_AVAILABLE
            if not CUDA_AVAILABLE:
                print("[V4b] CUDA kernels report CUDA_AVAILABLE=False")
                return
            self._batch_evaluate_fn = batch_evaluate_positions
        except Exception as e:
            print(f"[V4b] Failed to import CUDA kernels: {e}")
            return
            
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, name="GPU_Batch_Worker", daemon=True)
        self.worker_thread.start()
        print("[V4b] GPUBatchService started.")

    def stop(self):
        self.running = False
        if self.worker_thread:
             # We rely on daemon thread to die, or could add poison pill
             pass

    def submit(self, game_state) -> int:
        """
        Submit a game state for evaluation and wait for the result.
        Returns the score (int).
        """
        if not self.running:
            # Fallback if service not running (e.g. no CUDA)
            # Avoid circular import if possible, or import locally
            from chess_engine.engine.v3.chess_heuristic_calculation import score_board
            return score_board(game_state)
            
        req = EvaluationRequest(game_state)
        self.queue.put(req)
        
        # Block until result is ready
        req.event.wait()
        
        if req.error:
            raise req.error
        return req.result

    def _worker_loop(self):
        """Main loop for the batching thread."""
        batch = []
        
        while self.running:
            try:
                # 1. Blocking get for the first item (idle wait)
                # If we have nothing to do, we sleep here effectively
                first_req = self.queue.get(timeout=1.0) 
                batch.append(first_req)
                
                # 2. Try to grab more items to fill the batch
                # We spin briefly or check queue size
                start_collect = time.time()
                
                while len(batch) < self.MAX_BATCH_SIZE:
                    try:
                        # Non-blocking get
                        req = self.queue.get_nowait()
                        batch.append(req)
                    except queue.Empty:
                        # Queue is empty, should we wait a tiny bit more?
                        if time.time() - start_collect < self.BATCH_TIMEOUT:
                           # Busy wait / yield could be better than sleep for micro-latency
                           # time.sleep(0.00001) 
                           continue
                        else:
                            # Timeout reached, go with what we have
                            break
                            
                # 3. Process the batch
                self._process_batch(batch)
                batch = []
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[V4b] Critical Batch Service Error: {e}")
                # Don't crash the thread, try to recover
                time.sleep(1)

    def _process_batch(self, batch: List[EvaluationRequest]):
        """Run the batch through CUDA."""
        if not batch: return
        
        # Extract game states
        positions = [req.game_state for req in batch]
        batch_size = len(positions)
        
        # Debug: Log batch sizes periodically
        self._batch_count += 1
        if self._batch_count % 100 == 1:  # Log every 100th batch
            print(f"[V4b] Batch #{self._batch_count}: {batch_size} positions")
        
        try:
            # Run GPU Kernel
            # This handles memory transfer and execution
            scores = self._batch_evaluate_fn(positions)
            
            # Distribute results
            if len(scores) != len(batch):
                raise RuntimeError(f"GPU returned {len(scores)} scores for {len(batch)} requests")
                
            for req, score in zip(batch, scores):
                req.result = score
                req.event.set()
                
        except Exception as e:
            print(f"[V4b] Batch Processing Failed: {e}")
            # Fail all requests in this batch so threads don't hang
            for req in batch:
                req.error = e
                req.event.set()

# Singleton Accessor
_gpu_service = None

def get_gpu_service():
    global _gpu_service
    if _gpu_service is None:
        _gpu_service = GPUBatchService()
    return _gpu_service

def is_gpu_service_running():
    """Check if GPU batch service is active."""
    svc = get_gpu_service()
    return svc.running
