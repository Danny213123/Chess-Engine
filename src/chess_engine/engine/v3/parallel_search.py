# V3 Parallel Search Manager
# Handles multi-threaded CPU search and GPU batch evaluation

import threading
import concurrent.futures
from typing import List, Tuple, Any, Callable, Optional
from queue import Queue
import time

from .device import get_device, DeviceType


class ParallelSearchManager:
    """Manages parallel search across CPU threads or GPU."""
    
    def __init__(self):
        self._device = get_device()
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._lock = threading.Lock()
    
    def _get_executor(self) -> concurrent.futures.ThreadPoolExecutor:
        """Get or create thread pool executor."""
        if self._executor is None:
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self._device.num_threads,
                thread_name_prefix="chess_search"
            )
        return self._executor
    
    def parallel_root_search(
        self,
        moves: List[Any],
        search_fn: Callable[[Any], Tuple[Any, int]],
    ) -> List[Tuple[Any, int]]:
        """
        Search root moves in parallel.
        
        Args:
            moves: List of moves to evaluate
            search_fn: Function that takes a move and returns (move, score)
        
        Returns:
            List of (move, score) tuples
        """
        # Always use multi-threading for root search if multiple threads are available
        # This allows CPU parallelism (Lazy SMP) even if we have a GPU
        if self._device.num_threads > 1:
            executor = self._get_executor()
            futures = [executor.submit(search_fn, move) for move in moves]
            results = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    print(f"[V3] Search error: {e}")
            return results
        else:
            # Single-threaded fallback
            return [search_fn(move) for move in moves]
    
    def shutdown(self):
        """Shutdown the thread pool."""
        if self._executor is not None:
            self._executor.shutdown(wait=False)
            self._executor = None


class BatchEvaluator:
    """Batch evaluation for GPU or CPU."""
    
    def __init__(self):
        self._device = get_device()
        self._cuda_evaluator = None
    
    def evaluate_batch(
        self,
        positions: List[Any],
        eval_fn: Callable[[Any], int]
    ) -> List[int]:
        """
        Evaluate multiple positions in batch.
        Uses GPU if available, otherwise CPU.
        
        Args:
            positions: List of game states to evaluate
            eval_fn: CPU evaluation function
        
        Returns:
            List of scores
        """
        if self._device.is_cuda:
            return self._evaluate_batch_cuda(positions, eval_fn)
        else:
            return self._evaluate_batch_cpu(positions, eval_fn)
    
    def _evaluate_batch_cpu(
        self,
        positions: List[Any],
        eval_fn: Callable[[Any], int]
    ) -> List[int]:
        """CPU batch evaluation using thread pool."""
        device = get_device()
        
        if device.num_threads > 1 and len(positions) > 10:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=device.num_threads
            ) as executor:
                return list(executor.map(eval_fn, positions))
        else:
            return [eval_fn(pos) for pos in positions]
    
    def _evaluate_batch_cuda(
        self,
        positions: List[Any],
        eval_fn: Callable[[Any], int]
    ) -> List[int]:
        """
        GPU batch evaluation using CUDA kernels.
        Falls back to CPU if CUDA fails.
        """
        try:
            from .cuda_kernels import batch_evaluate_positions
            return batch_evaluate_positions(positions)
        except ImportError:
            print("[V3] CUDA kernels not available, falling back to CPU")
            return self._evaluate_batch_cpu(positions, eval_fn)
        except Exception as e:
            print(f"[V3] CUDA evaluation failed: {e}, falling back to CPU")
            return self._evaluate_batch_cpu(positions, eval_fn)


# Singleton instances
_search_manager: Optional[ParallelSearchManager] = None
_batch_evaluator: Optional[BatchEvaluator] = None


def get_search_manager() -> ParallelSearchManager:
    global _search_manager
    if _search_manager is None:
        _search_manager = ParallelSearchManager()
    return _search_manager


def get_batch_evaluator() -> BatchEvaluator:
    global _batch_evaluator
    if _batch_evaluator is None:
        _batch_evaluator = BatchEvaluator()
    return _batch_evaluator
