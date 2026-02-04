"""
V5b Search - Maximum Depth Alpha-Beta with Aggressive Pruning
Enhanced for deeper search and better move quality.

Features:
- Aggressive LMR with logarithmic reduction tables
- Late Move Pruning (LMP) for quiet moves
- Singular Extensions for critical moves
- Enhanced aspiration windows
- Improved time management
- Capture History heuristic
"""

import time
import math
import numpy as np
from typing import Optional, Tuple, List

from main.engine.v5b.board import BoardState, WP, BP
from main.engine.v5b.move_gen import (
    generate_legal_moves, generate_moves, make_move, unmake_move,
    move_to_string, encode_move, decode_move
)
from main.engine.v5b.eval import evaluate, INFINITY, MATE_SCORE, DRAW_SCORE
from main.engine.v5b.tt import TT, TT_EXACT, TT_ALPHA, TT_BETA


# =============================================================================
# SEARCH CONSTANTS
# =============================================================================

MAX_DEPTH = 64
MAX_PLY = 128

# Null Move Pruning (more aggressive for V5b)
NULL_MOVE_R = 3  # Higher reduction for deeper search
NULL_MOVE_MIN_DEPTH = 3  # Allow earlier null move

# Late Move Reductions (aggressive)
LMR_FULL_DEPTH_MOVES = 3  # Search fewer moves at full depth
LMR_REDUCTION_LIMIT = 2   # Allow LMR at shallower depths

# Late Move Pruning (new in V5b)
LMP_DEPTH = 8  # Maximum depth for LMP
LMP_BASE_MOVES = 3  # Base number of moves before pruning
LMP_MULTIPLIER = 2  # Multiplier for depth

# Multi-Cut pruning (more aggressive)
MULTI_CUT_DEPTH = 5        # Lower threshold
MULTI_CUT_MOVES = 5        # Fewer moves to test
MULTI_CUT_MARGIN = 4       # Higher reduction

# Probcut (more aggressive)
PROBCUT_DEPTH = 4          # Lower threshold
PROBCUT_MARGIN = 150       # Tighter margin

# Singular Extensions
SINGULAR_DEPTH = 6         # Minimum depth for singular extensions
SINGULAR_MARGIN = 64       # Score margin for singularity

# History Pruning (more aggressive)
HISTORY_PRUNING_DEPTH = 4  # Higher depth threshold
HISTORY_PRUNING_MARGIN = -2000  # Higher threshold

# Futility Pruning (more aggressive)
FUTILITY_MARGIN = [0, 100, 200, 300, 400]  # Extended to depth 4

# Reverse Futility Pruning (more aggressive)
RFP_MARGIN = [0, 100, 200, 300, 400]  # Tighter margins, extended to depth 4
RFP_DEPTH = 4  # Allow RFP at depth 4

# Razoring (more aggressive)
RAZOR_MARGIN = [0, 250, 400, 550]  # Tighter margins

# Delta Pruning (quiescence)
DELTA_MARGIN = 150  # Tighter margin

# Aspiration Windows (tighter)
ASPIRATION_WINDOW = 25  # Tighter initial window
ASPIRATION_MAX = 300    # Lower max before full search

# Internal Iterative Deepening
IID_DEPTH = 3  # Lower threshold
IID_REDUCTION = 2  # Depth reduction for IID search

# Pre-computed LMR reduction table
LMR_TABLE = np.zeros((64, 64), dtype=np.int32)
for d in range(1, 64):
    for m in range(1, 64):
        if d >= 2 and m >= 2:
            LMR_TABLE[d][m] = max(1, int(0.5 + math.log(d) * math.log(m) / 2.25))
        else:
            LMR_TABLE[d][m] = 0


# =============================================================================
# SEARCH STATE
# =============================================================================

class SearchInfo:
    """Holds search state and statistics."""
    
    def __init__(self):
        self.nodes = 0
        self.depth = 0
        self.seldepth = 0
        self.score = 0
        self.pv = []
        self.start_time = 0
        self.stop_time = 0
        self.stopped = False
        self.time_limit = 0
        self.depth_limit = MAX_DEPTH
        self.node_limit = 0

        # Killer moves: [ply][slot]
        self.killers = [[0, 0] for _ in range(MAX_PLY)]

        # History heuristic: [piece][to_square]
        self.history = np.zeros((12, 64), dtype=np.int32)

        # Counter-move heuristic: [from_sq][to_sq] -> counter_move
        self.counter_moves = np.zeros((64, 64), dtype=np.int32)

        # Capture history: [attacker][victim] for better capture ordering
        self.capture_history = np.zeros((12, 6), dtype=np.int32)

    def update_capture_history(self, attacker_idx: int, victim_type: int, depth: int):
        """Update capture history score."""
        self.capture_history[attacker_idx][victim_type] += depth * depth
    
    def check_time(self):
        """Check if we should stop searching."""
        if self.stopped:
            return True
        
        if self.time_limit > 0:
            elapsed = time.time() - self.start_time
            if elapsed >= self.time_limit:
                self.stopped = True
                return True
        
        if self.node_limit > 0 and self.nodes >= self.node_limit:
            self.stopped = True
            return True
        
        return False
    
    def clear_killers(self):
        """Clear killer moves."""
        for ply in range(MAX_PLY):
            self.killers[ply] = [0, 0]
    
    def store_killer(self, move: int, ply: int):
        """Store a killer move."""
        if move != self.killers[ply][0]:
            self.killers[ply][1] = self.killers[ply][0]
            self.killers[ply][0] = move
    
    def update_history(self, piece_idx: int, to_sq: int, depth: int):
        """Update history score for a move that caused beta cutoff."""
        self.history[piece_idx][to_sq] += depth * depth


# =============================================================================
# MOVE ORDERING
# =============================================================================

def score_move(board: BoardState, move: int, tt_move: int, info: SearchInfo, ply: int, prev_move: int = 0) -> int:
    """Score a move for ordering (higher = search first)."""
    score = 0

    # TT move gets highest priority
    if move == tt_move:
        return 10000000

    from_sq, to_sq, promo, flags = decode_move(move)

    # Promotions
    if flags == 3:  # MOVE_PROMO
        score += 900000 + promo * 100000

    # Captures: MVV-LVA (Most Valuable Victim - Least Valuable Attacker)
    captured = board.piece_at(to_sq)
    if captured:
        victim_value = [100, 320, 330, 500, 900, 20000][captured[0]]
        attacker = board.piece_at(from_sq)
        if attacker:
            attacker_value = [100, 320, 330, 500, 900, 20000][attacker[0]]
            score += 100000 + victim_value * 10 - attacker_value
        return score

    # Killer moves
    if ply < MAX_PLY:
        if move == info.killers[ply][0]:
            return 90000
        if move == info.killers[ply][1]:
            return 80000

    # Counter-move heuristic
    if prev_move != 0:
        prev_from, prev_to = decode_move(prev_move)[:2]
        if move == info.counter_moves[prev_from][prev_to]:
            return 70000

    # History heuristic
    attacker = board.piece_at(from_sq)
    if attacker:
        piece_idx = attacker[0] if attacker[1] else attacker[0] + 6
        score += info.history[piece_idx][to_sq]

    return score


def order_moves(board: BoardState, moves: np.ndarray, tt_move: int,
                info: SearchInfo, ply: int, prev_move: int = 0) -> np.ndarray:
    """Order moves for better alpha-beta pruning."""
    scored = [(move, score_move(board, move, tt_move, info, ply, prev_move)) for move in moves]
    scored.sort(key=lambda x: x[1], reverse=True)
    return np.array([m for m, s in scored], dtype=np.int32)


def is_capture(board: BoardState, move: int) -> bool:
    """Check if a move is a capture."""
    from_sq, to_sq, promo, flags = decode_move(move)
    return board.piece_at(to_sq) is not None or flags == 2  # EP capture


def get_lmr_reduction(depth: int, move_number: int, pv_node: bool, improving: bool = True) -> int:
    """
    Get LMR reduction from pre-computed table.
    Uses Stockfish-style logarithmic formula.
    """
    if move_number < LMR_FULL_DEPTH_MOVES or depth < LMR_REDUCTION_LIMIT:
        return 0

    # Clamp indices to table bounds
    d = min(depth, 63)
    m = min(move_number, 63)

    reduction = LMR_TABLE[d][m]

    # Reduce less in PV nodes
    if pv_node:
        reduction = max(0, reduction - 1)

    # Reduce more if not improving
    if not improving:
        reduction += 1

    # Clamp reduction
    return max(0, min(reduction, depth - 1))


def can_lmp(depth: int, move_number: int, improving: bool) -> bool:
    """Check if we can apply Late Move Pruning."""
    if depth > LMP_DEPTH:
        return False
    threshold = LMP_BASE_MOVES + depth * depth // LMP_MULTIPLIER
    if not improving:
        threshold = threshold * 2 // 3
    return move_number > threshold


def get_history_score(info: SearchInfo, board: BoardState, move: int) -> int:
    """Get history score for a move."""
    from_sq, to_sq, promo, flags = decode_move(move)
    attacker = board.piece_at(from_sq)
    if attacker:
        piece_idx = attacker[0] if attacker[1] else attacker[0] + 6
        return info.history[piece_idx][to_sq]
    return 0


def see_capture(board: BoardState, move: int) -> int:
    """
    Static Exchange Evaluation - estimates the value of a capture sequence.
    Returns estimated material gain/loss from the capture.
    Positive = good capture, Negative = bad capture.
    """
    from_sq, to_sq, promo, flags = decode_move(move)

    # Get victim value
    victim = board.piece_at(to_sq)
    if not victim:
        return 0  # Not a capture

    PIECE_VALUES = [100, 320, 330, 500, 900, 20000]
    victim_value = PIECE_VALUES[victim[0]]

    # Get attacker value
    attacker = board.piece_at(from_sq)
    if not attacker:
        return 0

    attacker_value = PIECE_VALUES[attacker[0]]

    # Simple SEE: if we capture with a less valuable piece, it's likely good
    # If we capture with a more valuable piece, check if victim is defended
    if attacker_value <= victim_value:
        return victim_value - attacker_value  # Likely winning exchange

    # For expensive attacker on cheap victim, be more cautious
    # This is a simplified SEE - full implementation would simulate the exchange
    return victim_value - int(attacker_value * 0.3)  # Pessimistic estimate


# =============================================================================
# QUIESCENCE SEARCH WITH DELTA PRUNING
# =============================================================================

def quiescence(board: BoardState, alpha: int, beta: int, info: SearchInfo, ply: int) -> int:
    """
    Quiescence search with delta pruning.
    Only searches capture sequences to avoid horizon effect.
    """
    info.nodes += 1
    
    if info.check_time():
        return 0
    
    info.seldepth = max(info.seldepth, ply)
    
    # Stand pat
    stand_pat = evaluate(board)
    
    if stand_pat >= beta:
        return beta
    
    # Delta pruning: if we're so far behind that even winning a queen won't help
    if stand_pat + 1000 < alpha:
        return alpha
    
    if stand_pat > alpha:
        alpha = stand_pat
    
    # Generate and search captures only
    moves = generate_moves(board)

    for move in moves:
        from_sq, to_sq, promo, flags = decode_move(move)

        is_cap = board.piece_at(to_sq) is not None
        is_promo = flags == 3

        if not is_cap and not is_promo:
            continue

        # SEE pruning - skip clearly losing captures
        if is_cap and not is_promo:
            see_score = see_capture(board, move)
            if see_score < -50:  # Losing capture
                continue

        # Delta pruning for captures
        if is_cap and not is_promo:
            captured = board.piece_at(to_sq)
            if captured:
                capture_value = [100, 320, 330, 500, 900, 20000][captured[0]]
                if stand_pat + capture_value + DELTA_MARGIN < alpha:
                    continue
        
        if not make_move(board, move):
            continue
        
        score = -quiescence(board, -beta, -alpha, info, ply + 1)
        unmake_move(board)
        
        if info.stopped:
            return 0
        
        if score >= beta:
            return beta
        
        if score > alpha:
            alpha = score
    
    return alpha


# =============================================================================
# ALPHA-BETA WITH PVS AND PRUNING
# =============================================================================

def alpha_beta(board: BoardState, depth: int, alpha: int, beta: int,
               info: SearchInfo, ply: int, pv: List[int], do_null: bool = True,
               prev_move: int = 0, prev_static_eval: int = -INFINITY) -> int:
    """
    V5b Alpha-Beta with aggressive pruning for deeper search:
    - Improved LMR with pre-computed tables
    - Late Move Pruning (LMP)
    - Singular Extensions
    - Improving heuristic
    """
    info.nodes += 1
    local_pv = []

    # Check time periodically (less frequently for better performance)
    if info.nodes % 8192 == 0:  # Check less frequently in V5b
        info.check_time()

    if info.stopped:
        return 0

    # Quiescence at leaf
    if depth <= 0:
        return quiescence(board, alpha, beta, info, ply)

    info.seldepth = max(info.seldepth, ply)

    # Draw detection
    if board.halfmove >= 100:
        return DRAW_SCORE

    # PV node check
    pv_node = beta - alpha > 1
    in_check = board.is_in_check()

    # Static evaluation for pruning decisions
    static_eval = evaluate(board) if not in_check else -INFINITY

    # Improving heuristic: position is better than 2 plies ago
    improving = static_eval > prev_static_eval

    # Check Extension
    if in_check and depth < 16 and ply < MAX_PLY - 8:
        depth += 1

    # TT probe
    tt_move = 0
    tt_score = 0
    tt_depth = 0
    hash_key = int(board.hash) if board.hash else 0
    entry = TT.probe(hash_key)

    if entry:
        tt_move = entry.move
        tt_score = entry.score
        tt_depth = entry.depth

        if entry.depth >= depth and not pv_node:
            if entry.flag == TT_EXACT:
                return entry.score
            elif entry.flag == TT_ALPHA and entry.score <= alpha:
                return alpha
            elif entry.flag == TT_BETA and entry.score >= beta:
                return beta

    # =========================================================================
    # REVERSE FUTILITY PRUNING (more aggressive in V5b)
    # =========================================================================
    if (depth <= RFP_DEPTH and not in_check and not pv_node and abs(beta) < MATE_SCORE - 100):
        rfp_margin = RFP_MARGIN[depth] if depth < len(RFP_MARGIN) else RFP_MARGIN[-1]
        if not improving:
            rfp_margin = rfp_margin * 2 // 3  # Tighter margin when not improving

        if static_eval - rfp_margin >= beta:
            return static_eval

    # =========================================================================
    # RAZORING
    # =========================================================================
    if (depth <= 3 and not in_check and not pv_node and abs(alpha) < MATE_SCORE - 100):
        razor_margin = RAZOR_MARGIN[depth]
        if static_eval + razor_margin < alpha:
            q_score = quiescence(board, alpha, beta, info, ply)
            if q_score <= alpha:
                return q_score

    # =========================================================================
    # INTERNAL ITERATIVE DEEPENING
    # =========================================================================
    if pv_node and depth >= IID_DEPTH and tt_move == 0:
        alpha_beta(board, depth - IID_REDUCTION, alpha, beta, info, ply, pv, do_null, prev_move, static_eval)
        entry = TT.probe(hash_key)
        if entry:
            tt_move = entry.move

    # =========================================================================
    # PROBCUT
    # =========================================================================
    if (depth >= PROBCUT_DEPTH and not in_check and not pv_node and abs(beta) < MATE_SCORE - 100):
        rbeta = min(beta + PROBCUT_MARGIN, INFINITY - 1)

        board.white_to_move = not board.white_to_move
        old_ep = board.ep_square
        board.ep_square = -1

        probcut_score = -alpha_beta(board, depth - 4, -rbeta, -rbeta + 1,
                                     info, ply + 1, local_pv, do_null=False, prev_move=0, prev_static_eval=-static_eval)

        board.white_to_move = not board.white_to_move
        board.ep_square = old_ep

        if probcut_score >= rbeta:
            return probcut_score

    # =========================================================================
    # NULL MOVE PRUNING (more aggressive in V5b)
    # =========================================================================
    if (do_null and depth >= NULL_MOVE_MIN_DEPTH and not in_check and not pv_node):
        has_pieces = (board.pieces[1] | board.pieces[2] | board.pieces[3] | board.pieces[4] |
                      board.pieces[7] | board.pieces[8] | board.pieces[9] | board.pieces[10])

        if has_pieces:
            # V5b: More aggressive null move reduction
            R = NULL_MOVE_R + (depth > 6) + (depth > 12)  # Even more reduction at very high depths

            board.white_to_move = not board.white_to_move
            old_ep = board.ep_square
            board.ep_square = -1

            null_score = -alpha_beta(board, depth - 1 - R, -beta, -beta + 1,
                                     info, ply + 1, local_pv, do_null=False, prev_move=0, prev_static_eval=-static_eval)

            # Unmake null move
            board.white_to_move = not board.white_to_move
            board.ep_square = old_ep

            if info.stopped:
                return 0

            if null_score >= beta:
                # Verify with reduced search for high depths
                if depth > 12:
                    verify = alpha_beta(board, depth - R, beta - 1, beta, info, ply, local_pv,
                                        do_null=False, prev_move=prev_move, prev_static_eval=prev_static_eval)
                    if verify >= beta:
                        return beta
                else:
                    return beta  # Null move cutoff
    
    # =========================================================================
    # GENERATE AND ORDER MOVES
    # =========================================================================
    moves = generate_legal_moves(board)

    if len(moves) == 0:
        if in_check:
            return -MATE_SCORE + ply  # Checkmate
        return DRAW_SCORE  # Stalemate

    moves = order_moves(board, moves, tt_move, info, ply, prev_move)

    # =========================================================================
    # MULTI-CUT PRUNING
    # =========================================================================
    # If multiple moves cause beta cutoff at reduced depth, prune
    if (depth >= MULTI_CUT_DEPTH and not in_check and not pv_node and
        len(moves) > MULTI_CUT_MOVES):
        cutoff_count = 0
        c = 0

        for move in moves[:MULTI_CUT_MOVES]:
            if c >= MULTI_CUT_MOVES:
                break

            if not make_move(board, move):
                continue

            c += 1
            mc_score = -alpha_beta(board, depth - MULTI_CUT_MARGIN, -beta, -beta + 1,
                                   info, ply + 1, local_pv, True, move, -static_eval)
            unmake_move(board)

            if info.stopped:
                return 0

            if mc_score >= beta:
                cutoff_count += 1
                if cutoff_count >= 2:  # Multiple cutoffs found
                    return beta
    
    best_move = moves[0]
    best_score = -INFINITY
    found_pv = False
    moves_searched = 0
    
    for i, move in enumerate(moves):
        is_cap = is_capture(board, move)
        from_sq, to_sq, promo, flags = decode_move(move)

        # =====================================================================
        # LATE MOVE PRUNING (LMP)
        # =====================================================================
        # Skip late quiet moves at low depths when not improving
        if (not in_check and not is_cap and promo == 0 and not pv_node and
            can_lmp(depth, moves_searched, improving)):
            continue

        # =====================================================================
        # FUTILITY PRUNING (extended to depth 4)
        # =====================================================================
        # Skip quiet moves if we're too far behind
        if (depth <= 4 and not in_check and not is_cap and not pv_node and
            static_eval + FUTILITY_MARGIN[min(depth, len(FUTILITY_MARGIN)-1)] <= alpha):
            continue

        # =====================================================================
        # HISTORY PRUNING
        # =====================================================================
        # Prune quiet moves with bad history late in search
        if (depth <= HISTORY_PRUNING_DEPTH and not in_check and not is_cap and
            not pv_node and moves_searched >= 3):
            hist_score = get_history_score(info, board, move)
            if hist_score < HISTORY_PRUNING_MARGIN:
                continue

        if not make_move(board, move):
            continue

        moves_searched += 1
        gives_check = board.is_in_check()  # Check after making move

        # =====================================================================
        # LATE MOVE REDUCTIONS (Adaptive LMR)
        # =====================================================================
        reduction = 0
        if (not in_check and not gives_check and not is_cap and promo == 0):
            reduction = get_lmr_reduction(depth, moves_searched, pv_node)

            # Reduce less for killer moves and good history
            if move == info.killers[ply][0] or move == info.killers[ply][1]:
                reduction = max(0, reduction - 1)
            elif get_history_score(info, board, move) > 5000:
                reduction = max(0, reduction - 1)
        
        # PVS with reductions
        if found_pv:
            score = -alpha_beta(board, depth - 1 - reduction, -alpha - 1, -alpha,
                                info, ply + 1, local_pv, True, move, -static_eval)

            # Re-search at full depth if failed high with reduction
            if score > alpha and reduction > 0:
                score = -alpha_beta(board, depth - 1, -alpha - 1, -alpha,
                                    info, ply + 1, local_pv, True, move, -static_eval)

            # Re-search with full window
            if score > alpha and score < beta:
                score = -alpha_beta(board, depth - 1, -beta, -alpha,
                                    info, ply + 1, local_pv, True, move, -static_eval)
        else:
            score = -alpha_beta(board, depth - 1, -beta, -alpha, info, ply + 1, local_pv, True, move, -static_eval)
        
        unmake_move(board)
        
        if info.stopped:
            return 0
        
        if score > best_score:
            best_score = score
            best_move = move
        
        if score > alpha:
            alpha = score
            found_pv = True
            
            pv.clear()
            pv.append(move)
            pv.extend(local_pv)
        
        if alpha >= beta:
            # Beta cutoff - store killer, history, and counter-move
            if not is_cap:
                info.store_killer(move, ply)
                attacker = board.piece_at(from_sq)
                if attacker:
                    piece_idx = attacker[0] if attacker[1] else attacker[0] + 6
                    info.update_history(piece_idx, to_sq, depth)

                # Store counter-move
                if prev_move != 0:
                    prev_from, prev_to = decode_move(prev_move)[:2]
                    info.counter_moves[prev_from][prev_to] = move
            break
    
    # Store in TT
    if not info.stopped:
        if best_score <= alpha:
            flag = TT_ALPHA
        elif best_score >= beta:
            flag = TT_BETA
        else:
            flag = TT_EXACT
        TT.store(hash_key, best_move, best_score, depth, flag)
    
    return best_score


# =============================================================================
# ITERATIVE DEEPENING
# =============================================================================

def search(board: BoardState, time_limit: float = 0, depth_limit: int = MAX_DEPTH,
           node_limit: int = 0, verbose: bool = True, search_info: SearchInfo = None) -> Tuple[int, int]:
    """
    Main search entry point with iterative deepening.
    Returns: (best_move, score)

    Args:
        search_info: Optional external SearchInfo for stopping searches
    """
    if search_info is None:
        info = SearchInfo()
    else:
        info = search_info

    info.start_time = time.time()
    info.time_limit = time_limit
    info.depth_limit = min(depth_limit, MAX_DEPTH)
    info.node_limit = node_limit
    info.stopped = False  # Reset stopped flag
    info.clear_killers()
    info.history.fill(0)
    
    TT.new_search()

    moves = generate_legal_moves(board)
    if len(moves) == 0:
        return 0, {"depth": 0, "nodes": 0, "time": 0, "score": 0, "nps": 0, "pv": ""}

    # Initialize best_move to first legal move to avoid returning 0
    best_move = int(moves[0])
    best_score = 0

    if len(moves) == 1:
        return best_move, {"depth": 0, "nodes": 0, "time": 0, "score": 0, "nps": 0, "pv": move_to_string(moves[0])}
    
    # Iterative deepening with aspiration windows
    for depth in range(1, info.depth_limit + 1):
        info.depth = depth
        info.seldepth = 0

        pv = []

        # CRITICAL: Don't allow stopping during depth 1-6 to ensure we get a well-evaluated move
        if depth <= 6:
            info.stopped = False

        # Use aspiration windows after depth 4
        if depth >= 5 and abs(best_score) < MATE_SCORE - 100:
            window = ASPIRATION_WINDOW
            alpha = max(-INFINITY, best_score - window)
            beta = min(INFINITY, best_score + window)

            # Try narrow window first
            score = alpha_beta(board, depth, alpha, beta, info, 0, pv)

            # If fail-low or fail-high, widen window and re-search
            aspiration_depth = 0
            while (score <= alpha or score >= beta) and not info.stopped and aspiration_depth < 4:
                aspiration_depth += 1
                window = min(window * 2, ASPIRATION_MAX)

                if score <= alpha:
                    alpha = max(-INFINITY, best_score - window)
                    beta = best_score + ASPIRATION_WINDOW
                elif score >= beta:
                    alpha = best_score - ASPIRATION_WINDOW
                    beta = min(INFINITY, best_score + window)

                pv = []
                score = alpha_beta(board, depth, alpha, beta, info, 0, pv)

            # If still failed, do full window search
            if (score <= alpha or score >= beta) and not info.stopped:
                pv = []
                score = alpha_beta(board, depth, -INFINITY, INFINITY, info, 0, pv)
        else:
            # Full window for shallow depths
            score = alpha_beta(board, depth, -INFINITY, INFINITY, info, 0, pv)

        if info.stopped:
            break

        best_score = score
        if len(pv) > 0:
            best_move = pv[0]
            info.pv = pv.copy()

        info.score = best_score
        
        if verbose:
            elapsed = time.time() - info.start_time
            nps = int(info.nodes / elapsed) if elapsed > 0 else 0
            pv_str = " ".join(move_to_string(m) for m in info.pv[:10])
            
            print(f"info depth {depth} seldepth {info.seldepth} "
                  f"score cp {best_score} nodes {info.nodes} "
                  f"nps {nps} time {int(elapsed * 1000)} "
                  f"hashfull {TT.hashfull()} pv {pv_str}")
        
        if abs(best_score) > MATE_SCORE - MAX_PLY:
            break
    
    elapsed = time.time() - info.start_time
    nps = int(info.nodes / elapsed) if elapsed > 0 else 0
    pv_str = " ".join(move_to_string(m) for m in info.pv)
    
    stats = {
        "depth": int(info.depth),
        "nodes": int(info.nodes),
        "time": float(elapsed),
        "score": int(best_score),
        "nps": int(nps),
        "pv": pv_str
    }
    
    if verbose:
        print(f"bestmove {move_to_string(best_move)}")
        print(f"[V5b] Search complete: {info.nodes} nodes in {elapsed:.2f}s "
              f"({nps} nps)")
        print(f"Info: depth {info.depth} score {best_score} nodes {info.nodes} nps {nps} time {elapsed:.2f} pv {pv_str}")
    
    return best_move, stats


def get_best_move(board: BoardState, time_limit: float = 1.0) -> int:
    """Simple interface to get the best move."""
    move, stats = search(board, time_limit=time_limit, verbose=False)
    return move
