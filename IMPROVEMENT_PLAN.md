# Chess Engine Improvement Plan

## Executive Summary

Analysis of the v5b vs v5c match (96 moves) reveals several critical weaknesses:

| Issue | Evidence | Impact |
|-------|----------|--------|
| Tactical blindness | Move 45-46: -224 to +396 (620cp swing on Bxf2) | Game-losing blunders |
| Endgame evaluation | Move 79-80: -156 to +376 swing in K+P ending | Won positions drawn/lost |
| Fixed time management | All moves use exactly 3s regardless of complexity | Wasted time in simple positions |
| Depth collapse in endgame | Moves 103-105: depth 2-4 despite simple positions | Missing forced wins |
| NPS variance | 4,474 to 22,541 NPS range | Inefficient move ordering |

---

## Phase 1: Critical Tactical Fixes (High Impact, Low Effort)

### 1.1 Improve Static Exchange Evaluation (SEE)

**Problem**: Current SEE only compares victim vs attacker values without simulating recapture sequences.

**Evidence**: Move 46 (Bxf2) shows engine missed tactical consequences.

**Implementation**:
```python
# Current (simplified):
def see_capture(board, move):
    return PIECE_VALUES[victim] - PIECE_VALUES[attacker]

# Improved (full sequence simulation):
def see_capture(board, move):
    gain = [0] * 32
    d = 0
    from_sq, to_sq = move & 0x3F, (move >> 6) & 0x3F

    # Get attackers and defenders
    attackers = get_all_attackers(board, to_sq)

    # Simulate capture sequence
    gain[0] = PIECE_VALUES[board.piece_at(to_sq)]
    piece = board.piece_at(from_sq)

    while attackers:
        d += 1
        gain[d] = PIECE_VALUES[piece] - gain[d-1]
        if max(-gain[d-1], gain[d]) < 0:
            break
        # Remove piece, find next attacker
        attackers ^= (1 << from_sq)
        piece, from_sq = get_least_valuable_attacker(attackers)

    # Negamax the gain array
    while d > 0:
        d -= 1
        gain[d] = -max(-gain[d], gain[d+1])

    return gain[0]
```

**Files to modify**:
- [eval.py](main/engine/v5c/eval.py) - Add full SEE implementation
- [search.py](main/engine/v5c/search.py) - Use SEE for capture ordering and pruning

**Testing**: Create tactical test suite (WAC, ECM positions)

---

### 1.2 Fix Quiescence Search Depth

**Problem**: QSearch limited to 8-10 plies but can miss long tactical sequences.

**Evidence**: The Bxf2 tactical sequence required looking beyond QSearch horizon.

**Implementation**:
```python
# Current:
MAX_QSEARCH_DEPTH = 8

# Improved: Dynamic based on position volatility
def quiescence(board, alpha, beta, info, ply, q_ply=0):
    # Allow deeper QSearch for checks and promotions
    if q_ply > 12 and not board.in_check:
        return stand_pat

    # Always search checks up to q_ply 6
    if q_ply <= 6:
        moves = get_captures_and_checks(board)
    else:
        moves = get_captures_only(board)
```

**Files to modify**:
- [search.py](main/engine/v5c/search.py) - Enhance quiescence search

---

### 1.3 Add Check Extensions in QSearch

**Problem**: Checks in quiescence aren't fully searched.

**Implementation**:
```python
def quiescence(board, alpha, beta, info, ply, q_ply=0):
    if board.in_check:
        # Don't stand pat in check - must escape
        best = -MATE_SCORE + ply
        moves = get_all_legal_moves(board)  # All moves, not just captures
    else:
        stand_pat = evaluate(board)
        if stand_pat >= beta:
            return beta
        best = stand_pat
        moves = get_captures_and_promos(board)
```

---

## Phase 2: Time Management Overhaul (High Impact, Medium Effort)

### 2.1 Dynamic Time Allocation

**Problem**: Fixed 3s per move wastes time in simple positions, lacks time for complex ones.

**Evidence**:
- Simple endgame moves (103-105) used 0.01-0.14s after time expired
- Complex middlegame positions all capped at 3s

**Implementation**:
```python
class TimeManager:
    def __init__(self, wtime, btime, winc=0, binc=0, movestogo=40):
        self.base_time = wtime if white else btime
        self.increment = winc if white else binc
        self.moves_to_go = movestogo

    def get_move_time(self, board, move_number):
        # Base allocation
        if self.moves_to_go:
            base = self.base_time / self.moves_to_go + self.increment * 0.9
        else:
            base = self.base_time / 30 + self.increment * 0.9

        # Complexity factor (more pieces = more time)
        piece_count = popcount(board.all_occ)
        complexity = min(1.5, 0.5 + piece_count / 20)

        # Position volatility (eval changed significantly = more time)
        if abs(self.last_eval - self.current_eval) > 50:
            complexity *= 1.3

        # Critical positions (low eval = take more time)
        if abs(self.current_eval) < 100:
            complexity *= 1.2

        return base * complexity

    def should_stop_early(self, depth, score, best_move_stable):
        # Stop if best move hasn't changed for 3 depths
        if best_move_stable >= 3 and depth >= 10:
            return True
        # Stop if we found a mate
        if abs(score) > MATE_THRESHOLD:
            return True
        return False
```

**Files to modify**:
- [search.py](main/engine/v5c/search.py) - Add TimeManager class
- [chess_engine.py](main/engine/v5c/chess_engine.py) - Integrate time management

---

### 2.2 Iterative Deepening Improvements

**Problem**: Engine doesn't use previous iteration info effectively.

**Implementation**:
```python
def iterative_deepening(board, time_limit):
    best_move = None
    best_move_changes = 0

    for depth in range(1, MAX_DEPTH):
        score, move = search(board, depth, alpha, beta)

        if move != best_move:
            best_move = move
            best_move_changes = 0
        else:
            best_move_changes += 1

        # Early termination if best move stable
        if best_move_changes >= 3 and elapsed > time_limit * 0.3:
            break

        # Use score from previous iteration for aspiration
        alpha = score - ASPIRATION_WINDOW
        beta = score + ASPIRATION_WINDOW
```

---

## Phase 3: Endgame Improvements (Medium Impact, Medium Effort)

### 3.1 Enhanced Endgame Evaluation

**Problem**: Multiple evaluation swings in the pawn endgame (moves 74-90).

**Evidence**:
- Move 74: -42 (h4)
- Move 80: +376 (Kf5)
- Engine misjudged passed pawn races

**Implementation**:
```python
def evaluate_endgame(board):
    score = 0

    # King activity in endgame (crucial)
    white_king = get_king_square(board, WHITE)
    black_king = get_king_square(board, BLACK)

    # Centralization bonus
    score += KING_CENTRALIZATION[white_king] * 3
    score -= KING_CENTRALIZATION[black_king] * 3

    # King proximity to passed pawns
    for pawn in get_passed_pawns(board, WHITE):
        score += (7 - rank(pawn)) * 20  # Advancement bonus
        score -= distance(black_king, pawn) * 5  # Opponent king distance
        score += distance(white_king, promotion_square(pawn)) * -3

    # Opposition and key squares
    if is_pawn_endgame(board):
        score += evaluate_opposition(white_king, black_king)
        score += evaluate_key_squares(board)

    # Rule of the square
    for pawn in get_passed_pawns(board, WHITE):
        if not can_catch_pawn(black_king, pawn, board.to_move):
            score += 500  # Unstoppable pawn

    return score
```

**Files to modify**:
- [eval.py](main/engine/v5c/eval.py) - Add endgame-specific evaluation
- [constants.py](main/engine/v5c/constants.py) - Add KING_CENTRALIZATION table

---

### 3.2 Passed Pawn Race Detection

**Problem**: Engine doesn't properly evaluate racing passed pawns.

**Implementation**:
```python
def evaluate_pawn_race(board):
    white_fastest = get_fastest_pawn(board, WHITE)
    black_fastest = get_fastest_pawn(board, BLACK)

    white_dist = 7 - rank(white_fastest)
    black_dist = 7 - rank(black_fastest)

    # Account for who moves first
    if board.to_move == WHITE:
        black_dist += 1
    else:
        white_dist += 1

    if white_dist < black_dist:
        return 500 + (black_dist - white_dist) * 100
    elif black_dist < white_dist:
        return -500 - (white_dist - black_dist) * 100

    # Race is tied - evaluate piece activity
    return 0
```

---

### 3.3 Add Endgame Tablebases (Syzygy)

**Problem**: Engine struggles with theoretical endgames.

**Implementation**:
```python
# Integration with python-chess Syzygy tablebase
from chess import syzygy

class SyzygyProbe:
    def __init__(self, path="syzygy"):
        self.tablebase = syzygy.open_tablebase(path)

    def probe_wdl(self, board):
        """Returns Win/Draw/Loss from white's perspective"""
        if popcount(board.all_occ) <= 6:
            try:
                return self.tablebase.probe_wdl(board.to_chess_board())
            except:
                return None
        return None

    def probe_dtz(self, board):
        """Returns Distance To Zeroing (50-move rule aware)"""
        if popcount(board.all_occ) <= 6:
            try:
                return self.tablebase.probe_dtz(board.to_chess_board())
            except:
                return None
        return None
```

**Files to create**:
- [tablebase.py](main/engine/v5c/tablebase.py) - Syzygy integration

---

## Phase 4: Search Enhancements (Medium Impact, High Effort)

### 4.1 Improve Move Ordering

**Problem**: NPS varies from 4,474 to 22,541 - indicates inefficient ordering.

**Evidence**: Lower NPS in complex middlegame positions.

**Implementation**:
```python
def order_moves(board, tt_move, killers, history, countermove):
    moves = []

    for move in legal_moves:
        score = 0

        # TT move is always first
        if move == tt_move:
            score = 10_000_000

        # Winning captures (SEE > 0)
        elif is_capture(move):
            see = see_capture(board, move)
            if see >= 0:
                score = 1_000_000 + see + mvv_lva(move)
            else:
                score = -100_000 + see  # Bad captures last

        # Promotions
        elif is_promotion(move):
            score = 900_000 + promotion_piece_value(move)

        # Killer moves
        elif move in killers:
            score = 90_000 - killers.index(move) * 10_000

        # Counter-move
        elif move == countermove:
            score = 70_000

        # History heuristic (with aging)
        else:
            score = min(history[piece][to_sq], 50_000)

        moves.append((score, move))

    return sorted(moves, reverse=True)
```

---

### 4.2 History Heuristic Improvements

**Problem**: History values can overflow and don't decay.

**Implementation**:
```python
class HistoryTable:
    def __init__(self):
        self.table = np.zeros((12, 64), dtype=np.int32)
        self.max_value = 400_000

    def update(self, piece, to_sq, depth, is_cutoff):
        bonus = depth * depth
        if is_cutoff:
            self.table[piece][to_sq] += bonus
        else:
            self.table[piece][to_sq] -= bonus // 2

        # Aging: scale down if exceeding max
        if self.table[piece][to_sq] > self.max_value:
            self.table *= 0.5

    def get(self, piece, to_sq):
        return self.table[piece][to_sq]
```

---

### 4.3 Add Countermove Heuristic

**Problem**: Engine doesn't track moves that refute opponent's moves.

**Implementation**:
```python
class CountermoveTable:
    def __init__(self):
        # countermove[piece][to_square] = best response
        self.table = np.zeros((12, 64), dtype=np.int32)

    def update(self, opponent_move, our_response):
        piece = get_piece(opponent_move)
        to_sq = get_to_square(opponent_move)
        self.table[piece][to_sq] = our_response

    def get(self, opponent_move):
        piece = get_piece(opponent_move)
        to_sq = get_to_square(opponent_move)
        return self.table[piece][to_sq]
```

---

## Phase 5: Evaluation Refinements (Low-Medium Impact, Medium Effort)

### 5.1 Improved King Safety

**Problem**: Current king safety only checks file openness.

**Implementation**:
```python
def evaluate_king_safety(board, king_sq, is_white):
    score = 0

    # Pawn shield
    shield_squares = get_pawn_shield_squares(king_sq, is_white)
    for sq in shield_squares:
        if has_friendly_pawn(board, sq, is_white):
            score += 10
        elif has_enemy_pawn(board, sq, is_white):
            score -= 15

    # Attacking pieces near king
    king_zone = get_king_zone(king_sq)
    attackers = 0
    attack_weight = 0

    for enemy_piece in get_enemy_pieces(board, is_white):
        attacks = get_attacks(board, enemy_piece) & king_zone
        if attacks:
            attackers += 1
            attack_weight += ATTACK_WEIGHTS[piece_type(enemy_piece)] * popcount(attacks)

    # Scale by number of attackers
    if attackers >= 2:
        score -= attack_weight * ATTACK_SCALE[min(attackers, 4)]

    return score

ATTACK_WEIGHTS = {KNIGHT: 2, BISHOP: 2, ROOK: 3, QUEEN: 5}
ATTACK_SCALE = [0, 0, 50, 75, 100]  # 0, 1, 2, 3, 4+ attackers
```

---

### 5.2 Piece Coordination

**Problem**: No evaluation of piece coordination.

**Implementation**:
```python
def evaluate_coordination(board):
    score = 0

    # Bishop pair
    if has_bishop_pair(board, WHITE):
        score += 30 + (32 - popcount(board.all_occ))  # More valuable in open positions
    if has_bishop_pair(board, BLACK):
        score -= 30 + (32 - popcount(board.all_occ))

    # Rook on open/semi-open file
    for rook_sq in get_pieces(board, ROOK, WHITE):
        file = rook_sq % 8
        if is_open_file(board, file):
            score += 25
        elif is_semi_open_file(board, file, WHITE):
            score += 12

    # Rooks connected
    white_rooks = get_pieces(board, ROOK, WHITE)
    if len(white_rooks) == 2:
        if rooks_connected(board, white_rooks):
            score += 10

    # Rook on 7th rank with enemy king on 8th
    for rook_sq in get_pieces(board, ROOK, WHITE):
        if rank(rook_sq) == 6:  # 7th rank (0-indexed)
            if rank(get_king_sq(board, BLACK)) == 7:
                score += 40

    return score
```

---

## Phase 6: Infrastructure Improvements (Low Impact, High Effort)

### 6.1 Opening Book Integration

**Problem**: No opening book loaded for v5 variants.

**Implementation**:
- Use Polyglot format (.bin files)
- Integrate with `chess.polyglot` library
- Add book move randomization for variety

---

### 6.2 Improved Transposition Table

**Problem**: Single-entry per hash slot causes collisions.

**Implementation**:
```python
# Use bucket system: 4 entries per slot
class TranspositionTable:
    BUCKET_SIZE = 4

    def __init__(self, size_mb=64):
        entries = (size_mb * 1024 * 1024) // (16 * self.BUCKET_SIZE)
        self.buckets = entries
        self.keys = np.zeros((entries, self.BUCKET_SIZE), dtype=np.uint64)
        self.data = np.zeros((entries, self.BUCKET_SIZE), dtype=np.int64)

    def probe(self, key):
        idx = key % self.buckets
        for i in range(self.BUCKET_SIZE):
            if self.keys[idx][i] == key:
                return self.data[idx][i]
        return None

    def store(self, key, depth, score, flag, move, age):
        idx = key % self.buckets

        # Find slot: prefer empty, then lowest depth, then oldest
        best_slot = 0
        for i in range(self.BUCKET_SIZE):
            if self.keys[idx][i] == 0 or self.keys[idx][i] == key:
                best_slot = i
                break
            if self.depths[idx][i] < self.depths[idx][best_slot]:
                best_slot = i

        self.keys[idx][best_slot] = key
        self.data[idx][best_slot] = pack(depth, score, flag, move, age)
```

---

### 6.3 Parallel Search (Lazy SMP)

**Problem**: Engine is single-threaded.

**Implementation**:
```python
class LazySMP:
    def __init__(self, num_threads=4):
        self.threads = num_threads
        self.shared_tt = TranspositionTable()
        self.stop_flag = Value('b', False)

    def search(self, board, time_limit):
        with Pool(self.threads) as pool:
            # Each thread searches with slightly different depth
            results = pool.starmap(
                search_thread,
                [(board, self.shared_tt, depth_offset, self.stop_flag)
                 for depth_offset in range(self.threads)]
            )

        # Return best result
        return max(results, key=lambda x: x.depth)
```

---

## Implementation Priority Matrix

| Phase | Task | Impact | Effort | Priority |
|-------|------|--------|--------|----------|
| 1.1 | Full SEE implementation | High | Low | **P0** |
| 1.2 | QSearch depth fix | High | Low | **P0** |
| 1.3 | Check extensions in QSearch | High | Low | **P0** |
| 2.1 | Dynamic time allocation | High | Medium | **P1** |
| 2.2 | Iterative deepening improvements | Medium | Low | **P1** |
| 3.1 | Enhanced endgame evaluation | Medium | Medium | **P2** |
| 3.2 | Passed pawn race detection | Medium | Low | **P2** |
| 3.3 | Syzygy tablebases | Medium | Medium | **P2** |
| 4.1 | Move ordering improvements | Medium | Medium | **P3** |
| 4.2 | History heuristic fixes | Low | Low | **P3** |
| 4.3 | Countermove heuristic | Low | Low | **P3** |
| 5.1 | King safety improvements | Low | Medium | **P4** |
| 5.2 | Piece coordination | Low | Medium | **P4** |
| 6.1 | Opening book | Low | Low | **P5** |
| 6.2 | TT bucket system | Low | High | **P5** |
| 6.3 | Lazy SMP | Medium | High | **P5** |

---

## Testing Strategy

### Unit Tests
- SEE correctness on known positions
- Evaluation consistency (symmetric positions)
- TT store/probe accuracy

### Tactical Tests
- Win At Chess (WAC) - 300 positions
- ECM (Encyclopedia of Chess Middlegames)
- Silent But Deadly (SBD) - tactical positions

### Self-Play Testing
- 100+ games at 3s/move
- Compare Elo change between versions
- Track tactical blunder rate

### Regression Tests
- Ensure no Elo regression on tactical suites
- Verify time usage patterns
- Monitor nodes/second stability

---

## Success Metrics

| Metric | Current (v5c) | Target |
|--------|---------------|--------|
| Tactical test accuracy | ~60% | >80% |
| Avg search depth | 8.2 | 10+ |
| NPS stability | 4K-22K range | 10K-15K range |
| Endgame accuracy | ~70% | >90% |
| Time utilization | 100% (fixed) | 60-120% (dynamic) |
| Blunder rate (>200cp) | ~5% of moves | <1% of moves |

---

## Appendix: Key Observations from Game Log

### Move 45-46 Analysis (Critical Blunder)
```
Move 45: Nh6 (eval: -224, depth: 7)
Move 46: Bxf2 (eval: +396, depth: 11)
```
- 620 centipawn swing indicates tactical miss
- v5b (white) only searched to depth 7 before playing Nh6
- v5c (black) found Bxf2 at depth 11 but eval swing suggests neither saw full consequences
- Root cause: Insufficient quiescence search or SEE errors

### Endgame Evaluation Instability (Moves 74-92)
```
Move 74: h4 (eval: -42)
Move 76: c5 (eval: 0)
Move 77: Ke4 (eval: -129)
Move 80: Kf5 (eval: +376)
Move 82: Kf4 (eval: +660)
```
- Wild swings in simple K+P endgame
- Engine clearly doesn't understand opposition and key squares
- Missing passed pawn race calculation

### Time Management Issues
- All 96 moves used exactly 3.0 seconds (hard limit)
- Final moves (103-105) used 0.01-0.14s (time expired, forced quick play)
- No early termination despite stable best moves
