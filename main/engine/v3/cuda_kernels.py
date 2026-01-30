# V3 CUDA Kernels for GPU-Accelerated Chess Evaluation
# Uses Numba CUDA for batch position evaluation

import numpy as np
from typing import List, Any

# Try to import CUDA
try:
    from numba import cuda
    import numba
    CUDA_AVAILABLE = cuda.is_available()
except ImportError:
    CUDA_AVAILABLE = False
    cuda = None
    numba = None


# Piece encoding for GPU
# 0=empty, 1=wP, 2=wN, 3=wB, 4=wR, 5=wQ, 6=wK, 7=bP, 8=bN, 9=bB, 10=bR, 11=bQ, 12=bK
PIECE_TO_INT = {
    "--": 0,
    "wP": 1, "wN": 2, "wB": 3, "wR": 4, "wQ": 5, "wK": 6,
    "bP": 7, "bN": 8, "bB": 9, "bR": 10, "bQ": 11, "bK": 12,
}

# Piece values (positive for white, negative encoded separately)
PIECE_VALUES_GPU = np.array([
    0,     # empty
    100,   # wP
    320,   # wN
    330,   # wB
    500,   # wR
    900,   # wQ
    20000, # wK
    -100,  # bP
    -320,  # bN
    -330,  # bB
    -500,  # bR
    -900,  # bQ
    -20000 # bK
], dtype=np.int32)


if CUDA_AVAILABLE:
    @cuda.jit
    def evaluate_positions_kernel(boards, scores, piece_values):
        """
        CUDA kernel for batch position evaluation.
        
        Args:
            boards: 2D array of shape (num_positions, 64) with piece encodings
            scores: 1D array of shape (num_positions,) for output scores
            piece_values: 1D array of piece values
        """
        idx = cuda.grid(1)
        if idx < boards.shape[0]:
            score = 0
            for sq in range(64):
                piece = boards[idx, sq]
                if piece != 0:
                    score += piece_values[piece]
            scores[idx] = score
    
    
    @cuda.jit
    def evaluate_with_pst_kernel(boards, scores, piece_values, pst_white, pst_black):
        """
        CUDA kernel with piece-square table evaluation.
        
        Args:
            boards: 2D array (num_positions, 64)
            scores: 1D output array
            piece_values: 1D piece values
            pst_white: 2D PST for white pieces (13, 64)
            pst_black: 2D PST for black pieces (13, 64)
        """
        idx = cuda.grid(1)
        if idx < boards.shape[0]:
            score = 0
            for sq in range(64):
                piece = boards[idx, sq]
                if piece != 0:
                    # Material value
                    score += piece_values[piece]
                    # PST bonus
                    if piece <= 6:  # White piece
                        score += pst_white[piece, sq]
                    else:  # Black piece
                        score += pst_black[piece, sq]
            scores[idx] = score


def board_to_gpu_format(game_state) -> np.ndarray:
    """Convert a GameState board to GPU-compatible format."""
    board = np.zeros(64, dtype=np.int32)
    for row in range(8):
        for col in range(8):
            piece = game_state.board[row][col]
            sq = row * 8 + col
            board[sq] = PIECE_TO_INT.get(piece, 0)
    return board


def batch_evaluate_positions(positions: List[Any]) -> List[int]:
    """
    Evaluate multiple positions in parallel on GPU.
    
    Args:
        positions: List of GameState objects
    
    Returns:
        List of evaluation scores
    """
    if not CUDA_AVAILABLE or len(positions) == 0:
        # Fallback to CPU
        from .chess_heuristic_calculation import score_board
        return [score_board(pos) for pos in positions]
    
    num_positions = len(positions)
    
    # Convert all positions to GPU format
    boards_cpu = np.zeros((num_positions, 64), dtype=np.int32)
    for i, pos in enumerate(positions):
        boards_cpu[i] = board_to_gpu_format(pos)
    
    # Allocate GPU memory
    boards_gpu = cuda.to_device(boards_cpu)
    scores_gpu = cuda.device_array(num_positions, dtype=np.int32)
    piece_values_gpu = cuda.to_device(PIECE_VALUES_GPU)
    
    # Launch kernel
    threads_per_block = 256
    blocks_per_grid = (num_positions + threads_per_block - 1) // threads_per_block
    
    evaluate_positions_kernel[blocks_per_grid, threads_per_block](
        boards_gpu, scores_gpu, piece_values_gpu
    )
    
    # Copy results back
    scores_cpu = scores_gpu.copy_to_host()
    
    return scores_cpu.tolist()


def get_gpu_memory_usage() -> dict:
    """Get current GPU memory usage."""
    if not CUDA_AVAILABLE:
        return {"available": False}
    
    try:
        mem_info = cuda.current_context().get_memory_info()
        free_mb = mem_info[0] / (1024 * 1024)
        total_mb = mem_info[1] / (1024 * 1024)
        used_mb = total_mb - free_mb
        return {
            "available": True,
            "free_mb": round(free_mb, 1),
            "used_mb": round(used_mb, 1),
            "total_mb": round(total_mb, 1),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}
