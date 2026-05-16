# Feature Landscape

**Domain:** Classical hand-crafted-evaluation (HCE) chess engine — V7 fork of V6 (C++17 + pybind11, magic bitboards, alpha-beta + TT)
**Researched:** 2026-05-15
**Baseline (V6) — what is already shipped:**

From `src/chess_engine/engine/v6/include/search.hpp` and `eval.hpp`:

- Search: alpha-beta + quiescence, iterative deepening, aspiration windows (`±25`), null-move pruning (fixed `R=4`, min-depth 3), LMR with a precomputed `LMR_TABLE[64][64]`, late move pruning (depth ≤ 8), futility pruning + reverse futility pruning (margin tables), OpenMP-flavored parallel `search_parallel` entry point.
- Eval: tapered MG/EG PSTs, mobility per piece type, bishop pair, pawn structure (passed/isolated/doubled/backward), rook on open/semi-open file, rook on 7th, knight outposts, bad-bishop penalty, king pawn-shield + open-file penalties + attacker-weight king-safety, tempo bonus, opening-development heuristics, SEE.

V7's job is therefore not to *introduce* search/eval — it is to **harden, extend, tune, and parallelize** what V6 already roughly has, plus add Syzygy and an endgame eval module. The categorization below is calibrated to that.

## Table Stakes

Features V7 must have, or it will not be meaningfully stronger than V6 (and may even regress). Most of these tighten or extend things V6 already has.

### Search

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---|---|---|---|---|
| Iterative deepening + aspiration windows (hardened) | V6 has both, but V7 must add re-search-on-fail-high/low with widening windows and proper fallback to full window. Without this, aspiration loses Elo at deeper depths. | S | — | Already roughly in V6; needs polish, not net-new. |
| Principal Variation Search (PVS) | Standard alpha-beta refinement: full window for first move, null window for the rest, re-search on fail-high. Free Elo on top of plain alpha-beta. V6's `alpha_beta` should be audited — confirm/convert to PVS. | S | iterative deepening | If V6 is plain alpha-beta, this is a no-brainer first patch. |
| Null-move pruning (adaptive R) | V6 uses fixed `R=4`. Modern engines use `R = 3 + depth/4 + min((eval-beta)/200, 3)` or similar adaptive formula. Adaptive R is worth ~20-40 Elo over fixed. Must include zugzwang guard (skip if side-to-move has only K+pawns). | S | eval, in-check detection | One of the highest Elo/effort-ratio changes for V7. |
| Late Move Reductions (log-based table) | V6 already has `LMR_TABLE[64][64]`. V7 must populate it with the modern `0.75 + log(depth)*log(moveNum)/2.25`-style formula and add contextual adjustments (in-check, PV node, improving flag, cut node, killer/TT/capture, history score). | M | move ordering, history tables, killers | Likely the single biggest Elo lever. Must NOT reduce in-check, captures, promotions, killers (or reduce them less). |
| Late Move Pruning (LMP) | V6 has it (depth ≤ 8). V7 should keep but tune the `move_count > LMP_LIMIT[depth]` table; common formula `(3 + depth*depth) / (2 - improving)`. | S | improving-flag tracking | Already present; tune. |
| Futility pruning + Reverse futility (RFP / static null) | V6 has both with margin tables. Standard. RFP: if `eval - margin*depth >= beta` at depth ≤ ~8, return eval. Tune margins via gauntlet. | S | eval | Already present; tune. |
| Razoring (light) | At depth 1-3, if `eval + margin < alpha`, drop to qsearch. ~10-15 Elo when other pruning is present. Optional but standard. | S | qsearch | Mild; some modern engines drop razoring entirely once LMP/RFP are well-tuned. Worth gauntlet-testing both ways. |
| Check extensions | Extend by 1 ply when in check. Universal. ~20 Elo, near-zero risk. V6 likely has it; verify. | S | in-check detection | Cheap and standard. |
| Killer moves (2 per ply) | V6 likely has these. Two killer slots indexed by ply, used between TT move and quiet-move scoring. | S | move ordering | Standard. |
| History heuristic (butterfly `[color][from][to]` or `[piece][to]`) | Standard quiet-move scoring. Increment on beta cutoff, decay/age between iterations. | S | move ordering | V6 status unknown; if missing, mandatory. |
| Counter-move heuristic | `[prev_piece][prev_to] -> Move`. Cheap (~20 Elo), 30 lines of code. Slot in move ordering after killers. | S | history table, prev-move tracking on stack | Cheap win. |
| SEE for move ordering and pruning | V6 has `see()`. V7 must use it (a) to split captures into winning/losing in move ordering, (b) to prune obviously bad captures in qsearch (`SEE < 0` → skip), (c) optionally as an LMR/LMP gate. | S | SEE already exists | Use what V6 already implemented. |
| Transposition-table best-move first in move ordering | TT move scored above all others. Guaranteed in V6 (TT exists), but verify ordering integration. | S | TT | Free. |

### Eval

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---|---|---|---|---|
| Tapered MG/EG PSTs | V6 has these. Keep, but **all values become Texel-tuned** in V7 rather than hand-set. | S | Texel pipeline | Texel is where most eval Elo comes from. |
| Mobility per piece type (excluding pawn-attacked / own-blocker squares) | V6 has it but uses fixed weights. In V7, define mobility as "safe mobility" (squares not attacked by lower-value enemy pieces, not blocked by own pieces) and let Texel tune the per-piece curves. | M | attack maps | Modern engines use indexed tables `mobility[piece][num_squares]` rather than linear weights. |
| Pawn structure: passed (with rank scaling), isolated, doubled, backward, connected, phalanx, chain | V6 covers passed/isolated/doubled/backward. V7 should add **connected/phalanx** and **passed-pawn king-distance / blocker / unstoppable** terms. | M | pawn attack maps | Connected + phalanx alone is ~15-25 Elo. |
| King safety: attacker count, attacker weight, pawn shield, open/semi-open files near king, king tropism | V6 has all of these. Keep, but consider the standard "attack-units → indexed safety table" approach where `safety_score = SAFETY_TABLE[attack_units]` (non-linear). | M | attack maps, king zone definition | Indexed safety table is the modern norm. |
| Bishop pair, knight outposts, rook on open/semi-open, rook on 7th | All in V6. Keep + Texel-tune. | S | — | Just retune. |
| Tempo bonus | V6 has `+10`. Keep + tune. | S | — | Trivial. |
| Phase interpolation by non-pawn material | V6 has `PHASE_TOTAL` and tapered PSTs. Keep. | S | — | Reuse V6's. |

### Endgame / Tablebase

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---|---|---|---|---|
| In-engine endgame eval: KPK (king-pawn vs king), opposition, wrong-colored bishop + rook pawn draw | Without these, V7 will misevaluate basic theoretical endings even with tablebases off. KPK from a precomputed bitbase or a hand-coded rule is standard. Wrong-bishop+RP is a 4-line check. | M | game-phase detection | Required for the "in-engine endgame eval" milestone item. KPK bitbase is ~24KB. |
| Syzygy WDL probing in search (3-4-5) | The PROJECT.md milestone explicitly requires this. Use Fathom's `tb_probe_wdl` at non-root nodes when `popcount ≤ TB_LARGEST` and `rule50 == 0` and remaining depth ≥ ProbeDepth. Returns immediately with WDL-derived score — perfect leaf eval for endgames. | M | Fathom integration, optional download script | Universally table-stakes for any modern engine claiming endgame strength. |
| Syzygy DTZ probing at root | Required for 50-move-rule-aware play. `tb_probe_root_dtz` ranks moves; engine plays the move with the lowest DTZ to win / highest DTZ to defend. Without DTZ at root, engine can convert won positions but blunder into 50-move draws. | M | Fathom integration | Standard pattern; one-time integration. |
| Configurable `SyzygyProbeDepth` and `SyzygyProbeLimit` | UCI-style options so users can disable or tune (`ProbeDepth=1` aggressive, `5+` conservative). Even though V7 has no UCI, expose these via the engine constructor / `find_best_move` kwargs. | S | Syzygy integration | Cheap configurability. |

### Tuning

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---|---|---|---|---|
| Texel gradient descent on Zurichess `quiet-labeled.epd` | The ship signal of V7's eval. MSE between sigmoid(qsearch_score) and game result; iterate. Standard since 2014. | M | qsearch must be reachable from the tuning harness | Required by PROJECT.md. |
| K-factor auto-tuning (one-time) | Compute K once on the un-tuned eval by minimizing MSE over K ∈ [0.5, 2.0]. **Do not** recompute K per Texel iteration — that destroys the optimization (everything collapses to material). Texel used K = -1.13 / `qScore` units. | S | Texel framework | Standard; one-shot before the main loop. |
| Sparse coefficient vectors per position | Most eval terms are zero for most positions. Extract a sparse `(coef_index, value)` list per position once, then per-iteration cost is `O(non-zero terms)` not `O(num_params)`. Difference between minutes-per-iteration and hours-per-iteration. | M | eval refactored to emit feature vectors | Mandatory for fast iteration on a 725k-position dataset. |
| Held-out validation split | Hold out ~10% of positions; report MSE on both train and held-out per epoch. Catches overfitting and broken regularization. | S | Texel pipeline | Cheap insurance. |

### Gauntlet / Validation

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---|---|---|---|---|
| V7-vs-V6 gauntlet harness at fixed time control | The shipping signal. Required by PROJECT.md. | M | both engines callable via a common adapter | Re-use existing CLI self-play scripts as the starting point if possible. |
| Time-control parity (ms-per-move identical) | Without this, the result measures hardware not strength. Use a fixed-time-per-move (e.g. 1000ms / move) or a real TC with identical clocks. | S | gauntlet harness | Trivial discipline issue. |
| Hash size + thread count parity | Both engines must run with the same TT size and the same thread count (or both single-threaded). Otherwise the comparison is meaningless. | S | gauntlet harness | Trivial discipline issue. |
| Opening book seeding (8-move balanced book, e.g. `8moves_v3.pgn` or similar PGN/EPD) | Without an opening book, every game starts from the same position and the same opening preferences will fire repeatedly. ~50 unique 8-ply positions is the minimum for a meaningful gauntlet. | S | book file in repo (small enough) or a download script | PROJECT.md says "no opening book" for *play*, but a *test-suite* opening book is different and required. Call this out. |
| Position deduplication / side-swap | Each opening played twice (once each side) so opening color advantage cancels. Standard `cutechess-cli -repeat` semantics. | S | gauntlet harness | Standard. |
| SPRT early-stop with [Elo0, Elo1] = [0, 5] or similar | Ends matches as soon as the result is statistically conclusive. Saves hours per patch. The standard tool is `fast-chess` or `cutechess-cli`; Python wrappers around the same math are also fine. | M | gauntlet harness | Required for productive iteration speed during V7 development. |
| Pentanomial Elo computation | Score game *pairs* (5 outcomes: WW, WD, WL/DD, DL, LL) instead of single games — significantly lower variance, ~30% fewer games to reach the same confidence. `cutechess-cli` does NOT do this natively; `fast-chess` does. | M | gauntlet harness, paired games | Strongly recommended; not strictly mandatory if SPRT is in place. |

## Differentiators

Features that would push V7 meaningfully beyond V6, but are not strictly required for "stronger than V6". Prioritize after table stakes work.

### Search

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---|---|---|---|---|
| Singular extensions | If the TT move is "singular" (all other moves fail low under a reduced-depth null-window verification search at margin `beta - depth*2`), extend it by 1-2 ply. ~30-60 Elo in modern engines. | L | TT move retrieval, null-window infrastructure, careful depth bookkeeping | One of the highest-Elo single features V7 doesn't have. Tricky to get right but well-documented. |
| Multi-cut bolt-on to singular search | Once SE is in place, if multiple of the verification-search moves fail high (≥ beta), prune the whole node returning beta. ~10-20 Elo on top of SE for ~5 lines of code. | S | singular extensions | Free given SE. |
| ProbCut | At depth ≥ 5, do a null-window search at `beta + margin` with reduced depth `depth - 4`. If it fails high, prune. Historically struggled in chess (overlaps with NMP) but Stockfish proved it gains net Elo (~30-50). | M | null-window infrastructure | Worth a gauntlet-gated experiment after SE is in. |
| Internal Iterative Reductions (IIR) | Modern replacement for IID. If no TT move at PV/cut nodes with depth ≥ 4, reduce depth by 1. Cheap, ~10-20 Elo. | S | TT | Lower-cost than IID, mostly subsumes it. |
| Recapture extensions | Extend by 1 ply when a move recaptures on the same square as the previous capture. ~5-15 Elo. | S | move-stack tracking | Small but cheap. |
| Continuation history (1-ply, 2-ply) | Beyond plain history: index by `(prev_piece, prev_to, this_piece, this_to)`. Strict superset of counter-move heuristic. ~20-40 Elo. | M | history tables, ply stack with previous moves | High value; standard in all top modern engines. |
| Capture history (`[piece][to][captured]`) | Replaces MVV-LVA among captures with a learned ordering. ~10-15 Elo. | S | history infrastructure | Cheap upgrade. |
| Lazy SMP (multi-threaded shared TT) | PROJECT.md requires this. Multiple threads search the same root, sharing only the TT (with lockless XOR-trick entries). Per-thread killers/history/eval cache. ~80 Elo at 4 threads, ~120 at 8. | L | thread-safe TT (XOR trick), per-thread search state, root distribution strategy | **Required by milestone** — listed here because it's a parallelism feature that lifts strength rather than a base-search heuristic. |
| Aspiration window widening on fail | Start at ±25, widen to ±100, then full window on repeated fails. V6 has fixed window only. ~10 Elo at deep depths. | S | iterative deepening | Cheap enhancement. |

### Eval

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---|---|---|---|---|
| Threats and hanging pieces | "Piece X attacked by lower-valued piece Y, undefended" → bonus for attacker side. ~20-40 Elo, well-known. | M | attack maps for both colors | Standard differentiator over V6's current eval. |
| Space evaluation (centre control by pawns + pieces in opponent's half) | ~10-20 Elo, helps closed positions. | M | pawn attack maps | Optional but well-trodden. |
| King attack-units with non-linear `SAFETY_TABLE[]` lookup | Replaces linear `KING_ATTACK_WEIGHT[]` summation in V6. Indexed table allows safety to grow super-linearly with attacker count → much sharper king-attack play. | M | king zone, attacker enumeration | Significant strength gain (~30-50 Elo) when combined with Texel-tuning the table. |
| Pawn hash table (cache pawn-structure eval) | Pawn structure changes rarely; cache the pawn-only eval keyed by pawn-only Zobrist. 5-15% NPS gain → directly helps the "within 20% of V6 NPS" constraint. | M | separate pawn Zobrist key | Cheap NPS, helps the perf budget. |
| Material imbalance table (e.g. "two bishops vs N+B" bonus) | Stockfish-classical-style material-combination corrections beyond raw piece values. ~10-20 Elo. | M | material counting | Lower priority; eval-tuner can absorb most of this. |

### Endgame

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---|---|---|---|---|
| Phase-aware king activity bonus (king centralization in EG, king safety in MG already in V6) | Tapered: in EG, king-centralization is huge; in MG, kings stay home. Probably already in V6's EG PST but worth confirming. | S | tapered PST | Likely covered by EG PST. |
| 6-piece Syzygy support (TB_LARGEST = 6) | 5-piece is ~1GB, 6-piece is ~150GB. PROJECT.md mentions "3-4-5-6 men" — confirm Fathom is built with 6-piece support and the download script can fetch up to 6. | S | Fathom build flag | Just a build flag in Fathom. |
| Fortress hints (basic): same-color bishops + blocked pawn chain → cap eval | Helps avoid hopelessly trying to convert drawn positions. PROJECT.md mentions "basic fortress hints" → in scope. | M | structural detection | Tricky; keep heuristics simple to avoid false positives. |

### Tuning

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---|---|---|---|---|
| L1 / L2 regularization in Texel objective | Prevents term explosion (e.g. mobility weights running off to infinity). Zurichess used L1. ~5-10 Elo more robust convergence. | S | Texel framework | Cheap improvement. |
| Compile-time coefficient extraction (constexpr / codegen) | Compile a "tuning build" where eval terms are gathered into a feature vector at compile time, vs. a "release build" with hard-coded constants. Cleanest design; alternative is runtime params via lookup. | L | Texel framework, build system tweak | Higher engineering cost; pure-runtime params is simpler and barely slower. **Recommend runtime params for V7** to keep complexity down. |
| ADAM / AdaGrad optimizer instead of vanilla SGD | Faster convergence. ~2-5x fewer epochs. Implementation cost low. | S | Texel framework | Quality-of-life. |

### Gauntlet

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---|---|---|---|---|
| Bayes-Elo or Ordo-style multi-engine rating | Useful if V7 is also compared to V5/V4/etc. PROJECT.md only requires V7-vs-V6, so this is nice-to-have. | M | tournament harness | Skip unless time permits. |
| `fast-chess` integration (vs. cutechess-cli or homegrown) | `fast-chess` supports pentanomial SPRT natively; significantly faster convergence than cutechess-cli. | M | UCI adapter for V7 (V7 isn't natively UCI; adapter needed) | Recommended if pentanomial is in scope. |

## Anti-Features

Features to **explicitly NOT build** in V7. Listed here so the requirements doc and roadmap can reject scope creep with a citation.

| Anti-Feature | Why Avoid | What to Do Instead | Source of "out of scope" |
|---|---|---|---|
| **NNUE / neural-network evaluation** | Out of scope per PROJECT.md. Requires training infrastructure, dataset generation, separate weight-file distribution. Deferred to a possible V8. | Stick with hand-crafted eval + Texel tuning. | PROJECT.md "Out of Scope" |
| **AlphaZero-style full-NN + MCTS engine** | Out of scope per PROJECT.md. Wrong direction for an alpha-beta-derived codebase. | Stick with alpha-beta + selective extensions. | PROJECT.md "Out of Scope" |
| **SPSA self-play parameter tuning** | Out of scope per PROJECT.md. Texel on the Zurichess set is the chosen tuning method this milestone. | Texel only. SPSA can be a future milestone. | PROJECT.md "Out of Scope" |
| **Opening book at play time** | Out of scope per PROJECT.md. V7 plays from the starting position with no book. | A *test-suite* opening book for the gauntlet is a separate concern (and IS in scope). Don't conflate. | PROJECT.md "Out of Scope" |
| **Bundled Syzygy tablebases in repo / releases** | Out of scope per PROJECT.md. 6-piece TBs are ~150GB. | Optional download script + run-time path config. Document the script in README. | PROJECT.md "Out of Scope" |
| **MultiPV mode (returning N principal variations)** | No analysis-UI consumer for it. The frontend asks for one move; multi-PV would only add code without a user. PROJECT.md restricts UI changes to the dropdown. | Single-PV only. | PROJECT.md "Out of Scope" — UI surface |
| **Engine ladder refactor in `GameManager`** | Out of scope per PROJECT.md. V7 is engine-only. | Add V7 to the existing `if/elif` ladder; defer the ladder refactor. | PROJECT.md "Out of Scope" |
| **`GameManager` singleton replacement** | Out of scope per PROJECT.md. | Live with the module-global. | PROJECT.md "Out of Scope" |
| **v5/v5b/v5c/v5d fork consolidation** | Out of scope per PROJECT.md. Separate cleanup track. | Don't touch v5*. | PROJECT.md "Out of Scope" |
| **CUDA / GPU acceleration in V7** | Per PROJECT.md "CUDA is not a target (V7 is CPU/OpenMP-style parallel via Lazy SMP)." | Lazy SMP CPU threads only. | PROJECT.md "Constraints" |
| **New eval-breakdown / search-stats UI** | Out of scope per PROJECT.md (frontend is dropdown-only). | None. | PROJECT.md "Out of Scope" |
| **In-app gauntlet UI** | Out of scope per PROJECT.md. | CLI gauntlet harness only. | PROJECT.md "Out of Scope" |
| **Hard ELO targets (+50/+100/+200)** | Out of scope per PROJECT.md. Replaced by gauntlet "meaningfully stronger." | Gauntlet result is the ship signal. | PROJECT.md "Out of Scope" |
| **Native UCI binary** | Not required for the integration path (Python pybind11 module called by `GameManager`). UCI would only be needed if running under cutechess-cli; a thin adapter script can wrap V7 for that case. | Optional thin Python UCI wrapper *only* if needed by the gauntlet harness — and only as a test-time tool, not as a shipped binary. | Inferred from PROJECT.md "no new UI / no new abstractions" |
| **Fixed-depth search-time tuning instead of fixed-time** | Fixed-depth gauntlets favor whichever engine has the lower NPS at equal depth — i.e. they reward eval cost rather than playing strength. | Fixed time-per-move (or full TC) for all gauntlet games. | Standard practice |

## Feature Dependencies

```
Texel pipeline ─────┐
                    ├─> tuned PSTs ─────────────┐
sparse extraction ──┘                            │
                                                 ├──> stronger eval ──┐
king-safety table  ──────────────────────────────┤                    │
threats/hanging   ──────────────────────────────┘                     │
connected/phalanx pawns ─────────────────────────────────────────────┘
                                                                       │
                                                                       v
in-engine endgame eval (KPK, opposition) ──────────────────────> V7 strength
                                                                       ^
Syzygy WDL (in-search) ──────┐                                        │
Syzygy DTZ (root)     ───────┴──> endgame perfection ─────────────────┤
                                                                       │
PVS ──> aspiration windows hardened ──┐                                │
                                       │                               │
adaptive null-move ────────────────────┤                               │
                                       │                               │
LMR (log-table + ctx) ─> needs ──> history + counter-move ─> killers ──┤
                                                ^                      │
SEE (V6 has) ─> move-ordering buckets ──────────┤                      │
                                                │                      │
LMP (V6 has) ──────────────────────────────────┤                      │
RFP / futility (V6 has) ───────────────────────┤                      │
                                                │                      │
Singular Extensions ──> Multi-Cut bolt-on ──────┤                      │
ProbCut ────────────────────────────────────────┤                      │
IIR ────────────────────────────────────────────┘                      │
                                                                       │
Lazy SMP ──> needs ──> thread-safe TT (XOR trick) ────────────────────┤
                       per-thread search state                         │
                                                                       │
gauntlet harness ──> SPRT ──> meaningful comparison ──> ship signal ───┘
                  ├─> opening book file
                  ├─> TC parity / hash parity / thread parity
                  └─> (pentanomial via fast-chess, optional)
```

Critical sequencing implications:

1. **Texel pipeline must come before deep eval changes.** Adding new eval terms is cheap; tuning them is the value. Build the pipeline early so every eval-term experiment can be validated.
2. **Move ordering (history + counter-move + killers + SEE buckets) must come before LMR retuning.** LMR's effectiveness is dominated by move-ordering quality; retuning LMR on a bad ordering produces wrong conclusions.
3. **Thread-safe TT must come before Lazy SMP.** XOR-trick entries are a 5-line change but absolutely required.
4. **Gauntlet harness + SPRT must come before any other feature lands.** Otherwise V7 development is flying blind — every patch needs an Elo-confidence answer.
5. **Syzygy + in-engine endgame eval are independent of search work** and can be parallelized into a separate work-stream.

## MVP Recommendation

Suggested ordering for the V7 milestone, derived from "highest-Elo / lowest-risk-first, with infrastructure before features":

**Phase A — Infrastructure (must come first):**
1. Fork V6 → `src/chess_engine/engine/v7/`. Identical behavior to V6 on day 1 (regression baseline).
2. Gauntlet harness (V7 vs V6) with SPRT + TC/hash/thread parity + opening book seeding.
3. Texel tuning pipeline against `quiet-labeled.epd` with sparse coefficient vectors and a held-out validation split.

**Phase B — Highest-confidence search wins:**
4. PVS audit + hardened aspiration windows.
5. Move-ordering: history + counter-move + killers + SEE-bucketed captures.
6. Adaptive null-move R + zugzwang guard.
7. LMR table re-derivation (`log(d)*log(m)/2.25`) + context-aware adjustments.
8. Texel-tune all PST + material + mobility + king-safety + pawn-structure terms (continuous, with each subsequent change re-tuned).

**Phase C — Selectivity (gauntlet-gated):**
9. Internal Iterative Reductions (IIR).
10. Singular extensions + multi-cut bolt-on.
11. ProbCut (gauntlet-gated; may not gain net Elo, accept that result).
12. Recapture extensions.

**Phase D — Eval depth:**
13. King-safety attack-units → indexed safety table.
14. Threats / hanging pieces.
15. Connected + phalanx pawn terms.
16. Pawn hash table (NPS recovery).

**Phase E — Endgame & tablebases (parallelizable with B/C/D):**
17. Fathom integration + Syzygy WDL in-search.
18. Syzygy DTZ at root.
19. KPK bitbase + opposition eval + wrong-bishop-RP rule + basic fortress hints.
20. Optional Syzygy download script.

**Phase F — Parallelism (last; everything else must be stable first):**
21. Thread-safe TT (XOR trick).
22. Lazy SMP with per-thread search state.
23. Final gauntlet vs V6 at the target hardware/thread count.

Defer (out of scope, listed for completeness):
- NNUE, MCTS, SPSA, opening book at play time, bundled tablebases, MultiPV, UI work, GameManager refactor, v5* cleanup, GPU. *(All per PROJECT.md.)*

## Sources

- [Late Move Reductions — Chessprogramming wiki](https://www.chessprogramming.org/Late_Move_Reductions) — HIGH confidence (authoritative reference).
- [Stockfish — Chessprogramming wiki](https://www.chessprogramming.org/Stockfish) — HIGH.
- [Stockfish docs (terminology)](https://official-stockfish.github.io/docs/stockfish-wiki/Terminology.html) — HIGH.
- [Lazy SMP — Chessprogramming wiki](https://www.chessprogramming.org/Lazy_SMP) — HIGH.
- [Shared Hash Table — Chessprogramming wiki](https://www.chessprogramming.org/Shared_Hash_Table) — HIGH.
- [Østensen (2016) — A Complete Chess Engine Parallelized Using Lazy SMP (MSc)](https://www.duo.uio.no/bitstream/handle/10852/53769/1/master.pdf) — HIGH.
- [Texel's Tuning Method — Chessprogramming wiki](https://www.chessprogramming.org/Texel's_Tuning_Method) — HIGH.
- [Zurichess evaluation improvements (Alexandru Moșoi)](https://medium.com/@brtzsnr/hi-all-a73c1b7b7a73) — HIGH (author of the dataset).
- [Syzygy Bases — Chessprogramming wiki](https://www.chessprogramming.org/Syzygy_Bases) — HIGH.
- [Fathom (jdart1 fork)](https://github.com/jdart1/Fathom) — HIGH (canonical embeddable Syzygy probe lib).
- [Stockfish Syzygy integration — DeepWiki](https://deepwiki.com/official-stockfish/Stockfish/7.3-syzygy-tablebases) — MEDIUM (third-party documentation, but matches Fathom + Stockfish behavior).
- [Singular Extensions — Chessprogramming wiki](https://www.chessprogramming.org/Singular_Extensions) — HIGH.
- [Multi-Cut — Chessprogramming wiki](https://www.chessprogramming.org/Multi-Cut) — HIGH.
- [ProbCut — Chessprogramming wiki](https://www.chessprogramming.org/ProbCut) — HIGH.
- [Counter-move Heuristic — Chessprogramming wiki](https://www.chessprogramming.org/Countermove_Heuristic) — HIGH.
- [History Heuristic — Chessprogramming wiki](https://www.chessprogramming.org/History_Heuristic) — HIGH.
- [Sequential Probability Ratio Test — Chessprogramming wiki](https://www.chessprogramming.org/Sequential_Probability_Ratio_Test) — HIGH.
- [SPRT testing — Rustic chess engine docs](https://rustic-chess.org/progress/sprt_testing.html) — MEDIUM (developer-blog).
- [LCZero testing guide](https://lczero.org/dev/wiki/testing-guide/) — HIGH (community-maintained official docs).

**Internal sources verified directly:**
- `src/chess_engine/engine/v6/include/search.hpp` (V6's existing search constants).
- `src/chess_engine/engine/v6/include/eval.hpp` (V6's existing eval terms).
- `.planning/PROJECT.md` (V7 milestone scope and out-of-scope list).
- `.planning/codebase/ARCHITECTURE.md` (existing engine adapter contract).
