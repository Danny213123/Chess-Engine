# Pitfalls Research

**Domain:** V7 chess engine — classical HCE with Lazy SMP, Texel tuning, Syzygy probing, and a V7-vs-V6 gauntlet
**Researched:** 2026-05-15
**Confidence:** HIGH on search/threading/Texel/Syzygy pitfalls (these are well-documented in TalkChess, CPW, and Stockfish/Ethereal/Weiss commit history); HIGH on integration pitfalls (verified against the actual repo state in `.planning/codebase/`).

This file enumerates the *silent* failure modes that quietly burn Elo, weeks, or both. It deliberately does **not** repeat pitfalls already raised in `ARCHITECTURE.md` (e.g. "V6's binding ignores Python `SearchInfo`", "TT must be lockless under Lazy SMP") — instead it builds on them.

Phase labels reference the planned ordering:

> **A** foundation → **B** search ∥ **C** eval ∥ **D** Syzygy → **C1** smoke milestone → **D1** lockless TT → **D2** search refinements ∥ **D3** endgame eval → **E1** Lazy SMP ∥ **E2** Texel pipeline → **F1** gauntlet → **G1** ship

(Note: the ARCHITECTURE.md research uses slightly different phase letters — `A1/A2/B1/B2/B3/C1/D1/D2/D3/E1/E2/F1/G1`. This file uses the same letters and treats `B`, `C`, `D` as the parallel branches feeding C1.)

---

## Critical Pitfalls (will silently lose Elo or wreck a milestone)

### Pitfall 1: TT mate score not adjusted for ply (off-by-one in mate distance)

**What goes wrong:** A mate score stored at ply 12 (e.g. `MATE - 12`) is probed at ply 8 in another search and treated as `MATE - 12` from that ply, advertising a faster mate than exists, or worse, a slower one. The engine plays "mate in 4" announcements that aren't real, and at the root it prefers fake fast mates over real slower ones. Sometimes also produces draw-by-repetition because the engine "sees" a forced mate that disappears when actually played.

**Why it happens:** The standard fix (`store: score + ply`, `probe: score - ply` for mates only) is fiddly and easy to get backwards. Confusing because non-mate scores are stored as-is.

**How to avoid:**
- Implement and test the canonical helper pair:
  ```cpp
  int score_to_tt(int s, int ply) { return s >=  MATE_IN_MAX ? s + ply
                                         : s <= -MATE_IN_MAX ? s - ply : s; }
  int score_from_tt(int s, int ply) { return s >=  MATE_IN_MAX ? s - ply
                                           : s <= -MATE_IN_MAX ? s + ply : s; }
  ```
- Unit test: store `MATE - 5` at ply 10, probe at ply 3 → must read `MATE - 12`.
- Bench-driven detection: search Mate-in-N test suite (WAC, ECM, Eigenmann); any "mate found at depth X but PV is shorter than X" is a smoking gun.

**Warning signs:**
- Engine UI shows `Mate in 3` then plays a non-mating move.
- "info score mate N" announcements where N decreases non-monotonically as depth increases.
- Search instability around tactical positions (best move flips wildly between iterations).

**Phase to address:** **B1** (sequential search). Must be in place *before* C1 smoke, because the smoke milestone runs full games where mate scores will be hit.

---

### Pitfall 2: Aspiration window infinite re-search (fail-low / fail-high oscillation)

**What goes wrong:** On a fail-low, widen the alpha side and re-search; on a fail-high, widen beta. If both sides widen on the *wrong* search, the loop never terminates within the time budget and the engine returns no move (or a 1-ply move). A common variant: widen by `*2` each fail with no upper bound → integer overflow → undefined behaviour on the next compare.

**Why it happens:** The textbook pseudocode shows an unbounded `while`. Real implementations need (a) widening cap that falls back to `-INF/+INF` after N fails, (b) cancellation poll inside the re-search loop, (c) careful handling of the case where the score goes from a win to a loss across re-searches (must reset both sides, not just widen).

**How to avoid:**
- Cap re-searches at 3–5 fails per side, then open the window fully (`alpha = -INF`, `beta = +INF`).
- Keep `delta` from previous iteration as the seed; widen `delta *= 2` but clamp.
- Poll `info.stopped` inside the aspiration loop, not just inside `alpha_beta`.
- Test: feed a known fail-high position (e.g. fortress-breaking endgame) and assert search returns within 2× the time budget.

**Warning signs:**
- "info" lines stop appearing for several seconds during a single iteration.
- Time forfeits at long TC even when nodes-per-second is healthy.
- Best move at depth N is wildly different from N-1 with no PV continuity.

**Phase to address:** **B1** (sequential iterative deepening). Hardening the loop is part of "iterative deepening hardening" called out in `PROJECT.md`. Re-verify in **F1** (gauntlet) where time forfeits show up.

---

### Pitfall 3: Null-move pruning in zugzwang positions

**What goes wrong:** The engine prunes a null move in a king-and-pawn endgame and concludes "this position is great, beta cutoff." Real position is zugzwang and the side to move is losing. Engine throws drawn or won pawn endings.

**Why it happens:** Standard guard is "skip null move if side-to-move has no non-pawn material" — but implementations often check the wrong colour ("if non-PK material exists for *us*" vs "for *side-to-move*") or only disable in pure pawn endings, missing K+P+minor zugzwang. A second variant: verification search after a null cutoff is omitted at depth ≥ some threshold, missing zugzwang in deep null.

**How to avoid:**
- Disable null move when:
  - Side-to-move has only pawns and king (`pop_count(occ_us & ~(pawns | king)) == 0`), AND
  - Static eval ≥ beta is the only reason for trying it.
- For depth ≥ 12, do a verification re-search (Stockfish does this at `depth >= 12` historically).
- Never null-twice in a row (track `info.null_just_done`).

**Warning signs:**
- Loss in known KPK or KPPP endings that are tablebase-confirmed wins.
- Zugzwang test suite (`KPK.epd`, `endgame.epd`) score regression vs single-threaded V6.
- Engine evaluates trivially-lost zugzwang positions as 0.00.

**Phase to address:** **B1** (sequential search) for the basic guard; revisit in **D2** (search refinements) if multi-cut/probcut introduce another null path; double-check during **D3** (endgame eval) regression suite.

---

### Pitfall 4: LMR formula off-by-one or applied to forcing moves

**What goes wrong:** Reductions applied to:
- moves that give check (lose tactical sight),
- captures (especially TT move or PV move),
- killers,
- when in check ourselves (the move *escapes* check, must not reduce).

Or the reduction table is computed with `log(depth) * log(move_count)` but indexed with `move_count` starting at 0 instead of 1, producing `-inf` reductions. Or `int reduction = ...` truncates a fractional formula and accidentally adds a reduction of 0 to non-PV nodes (unintended over-reduction at depth 1 where reduction can take depth negative).

**Why it happens:** LMR is the single most Elo-dense and most fragile feature in modern engines. Stockfish's commit log has dozens of `Logistic LMR tweak` entries that each move ±5 Elo. Hand-coding the formula correctly the first time is rare.

**How to avoid:**
- Use a precomputed `int reductions[MAX_DEPTH][MAX_MOVES]` table built at engine init: `r = (int)(0.5 + log(d) * log(m) / 2.0)` (or your tuned variant). Index with `min(d, MAX_DEPTH-1)`, `min(m, MAX_MOVES-1)`.
- Apply LMR only when:
  - depth ≥ 3,
  - move is quiet (not capture, not promotion),
  - move is not killer/counter/TT move,
  - we are not in check,
  - move does not give check (compute *after* `make_move`).
- Compute final reduced depth as `max(1, depth - 1 - r)` to never go non-positive.
- After a reduced search returns score > alpha, re-search at `depth - 1` (not full depth — common bug is to "research at full depth" and lose all the LMR savings).
- Smoke test: with LMR on/off, NPS at fixed depth should drop ~5–10% with LMR off (because more nodes searched). Strength at fixed time should *rise* with LMR on by a clearly measurable margin in 100-game gauntlets.

**Warning signs:**
- LMR-on engine plays *worse* than LMR-off in self-play (every chess programmer's "I added LMR and lost 30 Elo" moment — almost always an off-by-one).
- Tactical test suite (WAC, STS) regression specifically on captures/checks.
- Search depth at fixed time *decreases* when LMR is added (should increase).

**Phase to address:** **D2** (search refinements). Add LMR off → measure → add LMR on → measure → compare. Never enable LMR untested.

---

### Pitfall 5: Singular extension verification depth too aggressive (search explosion)

**What goes wrong:** A "singular" extension verifies that the TT move is uniquely good by re-searching at `depth - 4` (or `depth/2`) with a window around `tt_score - margin`. If the verification depth is too high or the margin is too small, *every* TT move appears singular and the entire tree gets a +1 extension at every node → search depth halved → strength *loss*.

**Why it happens:** Stockfish's value (`depth/2 - 1`, margin = `2*depth`) is heavily co-tuned. Engines that copy the formula but not the surrounding context (depth threshold for trying singular at all, exclusion of TT moves at PV nodes, etc.) get an unstable singularity test.

**How to avoid:**
- Only attempt singular at depth ≥ 8.
- Only on TT-bound EXACT or LOWER entries with stored depth ≥ `depth - 3`.
- Verification depth `(depth - 1) / 2`. Margin ~`2 * depth`.
- Use `excludedMove` field in the search stack to avoid infinite recursion (the verification re-search must skip the candidate move).
- Bench: at fixed depth, NPS should change <10% when singular is enabled. If NPS *halves*, the extension is firing too often.

**Warning signs:**
- `info` reports `seldepth` >> `depth` by a factor of 2 or more.
- NPS halves overnight after enabling singular extensions.
- Engine plays the TT move suspiciously often even when other moves should look better.

**Phase to address:** **D2** (search refinements). Singular goes in *after* LMR and null-move are stable, so the baseline is known.

---

### Pitfall 6: Multi-cut and probcut margins too aggressive

**What goes wrong:**
- **Multi-cut:** searches the first M moves at reduced depth; if C of them produce a beta cutoff, prunes. Margins too low → tactical positions where a tactical move comes 4th in ordering are pruned away. Engine misses combinations.
- **Probcut:** at depth ≥ 5, if a capture's reduced search exceeds `beta + margin`, prune. Margin too low (e.g. 100 cp) → many pseudo-tactical lines lose Elo. Margin too high (e.g. 500 cp) → no pruning happens.

**Why it happens:** These are pure speed-vs-correctness knobs with no theoretical "right" value — must be tuned. Stockfish's probcut margin is ~`100 + improving*30` and was reached via SPRT, not first-principles.

**How to avoid:**
- Add multi-cut and probcut **last**, after LMR/null/futility are stable.
- Test with margins at conservative starting values (multi-cut: M=6, C=3, reduction=4; probcut margin=200cp at depth=5, +50 per depth).
- Run STS tactical suite after each change. Any test category drop ≥5% means the margin is too low.
- These are also legitimate Texel-tunable parameters but usually tuned by SPRT/SPSA, which is *out of scope* this milestone — use community defaults and don't over-optimise.

**Warning signs:**
- Tactical suite regression (WAC drops 10–50 points from baseline).
- Engine misses simple sacrificial combos in self-play games.
- Big NPS gain (>20%) but Elo loss in gauntlet — pure pruning, no compensating gain.

**Phase to address:** **D2** (search refinements) after LMR/null are validated. If gains are ambiguous, skip them — they are explicitly listed as "advanced techniques" in PROJECT.md, not table-stakes.

---

### Pitfall 7: Repetition detection wrong inside search vs only at root

**What goes wrong:** Engine claims a 3-fold repetition only at the root, but inside the tree treats repeated positions as non-draws. A losing side then "discovers" it can repeat to draw at depth 4 but the search never reports score 0, so the engine never plays the draw. Conversely: the engine treats *2-fold* as a draw inside the tree (Stockfish's optimisation), which is too aggressive without correct implementation, causing it to throw away wins that have a single repetition along the path.

**Why it happens:** The "cycle detection" idea is "any position seen on the path back to the last irreversible move counts as a draw" — easy to implement wrong because the position-history stack has to include the *played* moves before the search root, not just the search-internal moves.

**How to avoid:**
- Maintain a `position_keys[ply]` array that includes pre-root history (all played moves since last pawn move/capture).
- In search: scan from `ply - 4` backwards in steps of 2 (same side to move) up to `ply - halfmove_clock`; if any matches, return draw score.
- Two-fold optimisation: only enable when *both* repetitions are within the search tree (not crossing the root) — otherwise revert to true 3-fold.
- Test: position with a known forced repetition draw should return score 0 by depth 6.

**Warning signs:**
- Engine plays into 3-fold repetitions when winning (didn't see the repetition).
- Engine plays *out of* a repetition draw when losing (treated repetition as non-draw).
- Score oscillates between 0 and ±material in winning endings.

**Phase to address:** **B1** (sequential search) — repetition handling is fundamental, not an advanced feature.

---

### Pitfall 8: 50-move counter not respected by TT cutoffs

**What goes wrong:** TT entry at halfmove-clock=20 says "this position is +5 (depth 12 EXACT)". Probed at halfmove-clock=95 → cutoff returned, but at halfmove-clock=95 the position is moments from a 50-move draw and the score should approach 0. Engine "knows" it's winning, plays an irreversible-needs-pawn-move that *captures* and resets the clock — but only because of TT lying to the search.

**Why it happens:** Zobrist key does NOT include the halfmove clock (and shouldn't — would destroy TT hit rate). The fact that two positions with the same Zobrist key but different halfmove clocks are not equivalent for evaluation is easy to forget.

**How to avoid:**
- In `alpha_beta`, before TT cutoff: if `halfmove_clock >= 80`, do not use TT cutoff for non-mate scores (force re-search).
- Alternative (Stockfish-style): scale the TT score toward 0 as halfmove_clock → 100. Less invasive; preserves some hit rate.
- Test: position 1 move from 50-move draw with TT-stored "+5 depth 12" must not return cutoff.

**Warning signs:**
- Engine wins endings in self-play but gets disqualified in fixed-game external tournaments under 50-move rule.
- Score remains positive for 30+ plies in winning endings then suddenly drops to 0.
- Engine lets the halfmove counter run high before making a pawn move/capture.

**Phase to address:** **D3** (endgame eval) at the latest, but really should be in **D1** (TT rewrite) since the entry layout decision determines whether it's even possible to handle this efficiently.

---

### Pitfall 9: Lockless TT XOR trick implemented but probe still data-races

**What goes wrong:** The Hyatt-Mann scheme stores `(key XOR data, data)` so torn writes are detected. But: the probe reads `xkey`, *then* `data`, *then* checks `xkey == key XOR data`. If a different thread overwrites the same slot between the two loads, the probe falsely accepts a torn entry from a *different* probe pair — XOR check passes by coincidence (the new `xkey` happens to equal `key XOR new_data`).

The naive "wins" both fields atomically. The correct implementation uses two separate `std::atomic<uint64_t>` fields and reads them in the right order. Most engine bugs in this area aren't the algorithm — they're the memory ordering.

**Why it happens:** Lockless data structures need explicit memory ordering reasoning. `std::memory_order_relaxed` is fine for this *specific* algorithm because the XOR check provides the consistency, but using `volatile` instead of `atomic` (a still-common C++ chess-engine antipattern) is undefined behavior.

**How to avoid:**
- Both fields `std::atomic<uint64_t>` with `memory_order_relaxed` for both load and store.
- **Stress test:** spawn 16 threads that hammer a 64-MB TT for 60 seconds inserting and probing, with each thread tracking `(key, expected_data)` it stored. Any returned `data != expected_data` for `xkey == key XOR data` is a torn read. Should be exactly zero unless Zobrist collision.
- Tools: ThreadSanitizer (`-fsanitize=thread`) on a Linux dev machine catches *most* race issues. Note: Windows MSVC does not support TSan — must run TSan tests on Linux/macOS or WSL.

**Warning signs:**
- Crashes only in multi-threaded mode.
- Best move flips between identical runs of fixed-depth single-thread search (TT corruption persisted across calls).
- Search returns illegal best moves (TT move from a different position).

**Phase to address:** **D1** (lockless TT). Must precede E1 (Lazy SMP) — building Lazy SMP on a single-threaded TT means silent corruption from day one.

---

### Pitfall 10: Lazy SMP cancellation token missed by some workers

**What goes wrong:** Master thread sets `info.stopped = true` and joins workers. One worker is in a deep recursive call inside `alpha_beta`, polls `info.stopped` only every 4096 nodes, and is currently in the "long path" of a hot evaluation that doesn't cross node boundaries for ~5 ms. Master times out waiting on `join()` for that worker. UI hangs.

A subtler variant: worker checks `info.stopped` correctly but writes to a shared "best move so far" *after* the check, racing the master's read.

**Why it happens:** Cancellation polling intervals are tuned for low overhead, not low latency. A 4096-node interval at 5 Mnps is ~0.8 ms, which is fine — but with ProBcut/Singular re-searches there can be longer non-polling stretches.

**How to avoid:**
- Poll inside `alpha_beta` at every node: `if ((info.nodes & 1023) == 0 && info.stopped.load(std::memory_order_relaxed)) return 0;` — once per 1024 nodes is plenty.
- Also poll inside iterative deepening between depths.
- Add a hard timeout on `join()` (e.g. 1 second) and `std::terminate` if exceeded — it's a bug, but fail loud.
- Test: spawn search with 100 ms TC, after 50 ms call `engine.stop()`. Search must return within 5 ms.

**Warning signs:**
- `/api/stop` endpoint returns 200 but the next `/api/state` shows the search still running.
- UI "Stop" button feels laggy.
- After Ctrl-C uvicorn, process hangs and must be killed.

**Phase to address:** **E1** (Lazy SMP). Test cancellation explicitly with a unit test that calls `find_best_move` in a thread, calls `stop()` after 50 ms, and asserts return within 100 ms.

---

### Pitfall 11: GIL not released → Lazy SMP threads serialize → no parallelism

**What goes wrong:** Forget `py::gil_scoped_release` on the binding. Workers spawn but cannot acquire the GIL (or rather, only one of them can at a time). NPS at 4 threads is the same as NPS at 1 thread. Worse: a Python `/api/stop` request arriving during search blocks behind the GIL until the entire AI move finishes.

This is the *single most common* pybind11 multi-threading mistake.

**Why it happens:** "My C++ code doesn't touch Python objects, so the GIL doesn't matter" — wrong. The GIL is held by the Python thread that called into C++. The thread holds it for the entire C++ call unless explicitly released. Worker threads *don't need* the GIL to run, but the master still holds it, so every shared mutex/atomic gets serialised by the OS scheduler around the GIL-holding thread's wait state.

**How to avoid:**
- Use `py::call_guard<py::gil_scoped_release>()` on the `def(...)` declaration — sets it for every call.
- Belt-and-suspenders: also instantiate `py::gil_scoped_release no_gil;` at the top of `find_best_move`.
- Test: NPS at 4 threads must be ≥3.0× NPS at 1 thread. Anything below 2.5× means GIL contention or other serialisation.
- Add an integration test calling `engine.find_best_move()` from one Python thread while another Python thread polls `/api/state` — both must run concurrently (visible by timestamps).

**Warning signs:**
- `htop` shows 100% on one core and ~0% on the others during search.
- `engine.stop()` from a sibling thread takes seconds to take effect.
- NPS scaling worse than 1.5× from 1 → 4 threads.

**Phase to address:** **E1** (Lazy SMP) — but the binding skeleton from **A1/A2** should already include `py::gil_scoped_release` so the pattern is in place from day one.

---

### Pitfall 12: History/killer tables shared across Lazy SMP threads → search divergence collapses

**What goes wrong:** Threads share the history table "to save memory" or "for consistency". Result: all threads converge to the same move ordering at every node, defeating the whole point of Lazy SMP (which gains Elo from threads exploring *different* parts of the tree). NPS scales but Elo doesn't.

**Why it happens:** Intuition says "more shared data = more cooperation." Lazy SMP relies on the opposite — diversity through different per-thread state.

**How to avoid:**
- Per-thread:
  - history table (`int history[2][64][64]`)
  - killers (`Move killers[MAX_PLY][2]`)
  - counter-moves (`Move counter[12][64]`)
  - continuation history if you implement it
  - search stack (`Stack stack[MAX_PLY]`)
- Shared:
  - TT
  - Syzygy probe cache (read-only after init)
  - root move list (with per-thread current iteration depth)
- Test: at fixed time control, 4-thread Elo vs 1-thread Elo on a 200-game gauntlet must show ≥40 Elo gain. Anything <20 means insufficient divergence.

**Warning signs:**
- 4 threads → same move played as 1 thread on 90%+ of test positions (low diversity).
- 4-thread NPS scales ~3.5× but Elo gain is <15 in self-play.
- Threads all reach the same depth at exactly the same time (suspicious lockstep).

**Phase to address:** **E1** (Lazy SMP). The per-thread vs shared decision is the most important architectural call in this phase.

---

### Pitfall 13: Texel K-factor recomputed every iteration

**What goes wrong:** Texel's loss function is `Σ (sigmoid(K·eval) - result)²`. K is fitted *once* against the initial coefficients; using it as fitted is part of the algorithm's contract. Some implementations re-fit K every gradient step — this lets the loss drift toward whatever shape the current eval has, optimizing K instead of the eval and stalling the gradient.

**Why it happens:** "Why not refit K each iteration to keep loss meaningful?" — sounds reasonable, breaks the optimisation.

**How to avoid:**
- Fit K *once* at start using golden-section search or grid search (range typically `K ∈ [0.5, 2.0]`).
- Persist K to a file alongside the coefficient JSON.
- After tuning, optionally refit K once and re-tune as a "second pass" — but not per-iteration.
- Document K value in the coefficient export so re-runs are reproducible.

**Warning signs:**
- Loss curve is flat instead of monotonically decreasing.
- Coefficients oscillate between iterations.
- Tuned engine plays *worse* than untuned in gauntlet despite "loss decreased".

**Phase to address:** **E2** (Texel pipeline).

---

### Pitfall 14: Texel positions not actually quiet

**What goes wrong:** The Zurichess set is "quiet-labeled" but has small percentages of in-check or TT-noisy positions. Worse, some teams use their own EPD with `quiet` defined as "no captures available" — but a position with hanging pieces is "quiet" by that definition and still tactically unstable.

If the eval being tuned is the static eval (`eval()`) and the training positions are in-check, the gradient pulls eval coefficients toward valuing static positions that include checks specially — corrupting the eval for normal positions.

**Why it happens:** "Quiet" is dataset-defined, not an absolute property.

**How to avoid:**
- Filter: drop positions where `is_check(stm) == true`.
- Filter: drop positions where `qsearch(pos) != eval(pos)` (definition of "quiet" used by Stockfish's quiet-labeled set is exactly this).
- Drop positions where `eval(pos) > MATE_IN_MAX` or any TB endgame (those don't need eval tuning).
- Verify: after filter, ~95% of Zurichess positions should remain (it's already filtered, but always re-filter).

**Warning signs:**
- Eval coefficients for "king attacker count" or "pinned piece bonus" balloon to extreme values during tuning.
- Tuned engine performs *worse* in tactical suites (because static eval was distorted toward in-check positions).

**Phase to address:** **E2** (Texel pipeline) — explicit filter step before gradient loop.

---

### Pitfall 15: Texel coefficient extraction mismatch (tuner reads X, search uses Y)

**What goes wrong:** Tuner script optimises `coeffs.json["king_attacker_weight_mg"] = 50`. Search reads `coeffs.king_attack_weight_mg` (different spelling) and silently uses the default. Tuned coefficients never make it to the engine. Worst case: reads correctly *most* of the time but a typo on one term means the eval has 49 tuned terms and 1 default. Hard to spot.

This is also the place where bugs around tapered eval (mid-game vs end-game blending) hide — tuner outputs `(mg, eg)` pairs but search only reads `mg`.

**Why it happens:** Coefficient surface is wide (often 200+ parameters). Hand-mapping names between Python and C++ is error-prone.

**How to avoid:**
- **Single source of truth for coefficient names.** Generate `coeffs.cpp` from the JSON at build time using a small Python codegen script. Tuner and search both read from the JSON.
- Or: expose `get_coeff(name)` from the C++ binding so the tuner can read *back* what the engine actually uses, and assert equality.
- After tuning, run `eval_quiet(starting_pos)` from both tuner and engine binary and assert equality (catches mismatch).
- Always tune `(mg, eg)` together with explicit phase blending in the loss; never tune mg alone.

**Warning signs:**
- Tuner reports loss decreased 30% but gauntlet shows no Elo improvement.
- `eval_quiet(fen)` returns different values from tuner Python and from search C++ on the same coefficient set.
- Particular eval term has a "default-shaped" value (round number like 100, 50, 25) while neighbours have tuned-shaped values (47, 113, 22).

**Phase to address:** **E2** (Texel pipeline). Single-source-of-truth for names is a *design* requirement of the pipeline — not optional.

---

### Pitfall 16: Texel converges to bad local minimum due to seed positions

**What goes wrong:** Initial coefficients are V6's hand-tuned values. Texel does small steps; gets stuck near the V6 basin. Improvement is marginal and stops well before the global minimum.

**Why it happens:** Texel is gradient descent with no momentum or restart. Any non-convex loss surface (and chess eval definitely is) has many local minima.

**How to avoid:**
- Run from **two seeds**: V6's existing coefficients AND a "neutral" seed (PSQTs all zero, mobility weights all 1, king-safety weights all 0). Whichever converges to lower loss wins.
- Optionally a third seed of small random perturbation (`coeff *= (1 + uniform(-0.2, 0.2))`).
- Compare the three converged sets head-to-head in a small gauntlet. Pick the strongest, not the lowest-loss.
- Document seed choice in the coefficient JSON.

**Warning signs:**
- Tuning improves loss by <2% from V6 seed.
- Tuned coefficients are within 5% of V6 across the board (basin too narrow).

**Phase to address:** **E2** (Texel pipeline).

---

### Pitfall 17: Texel overfits Zurichess set (regression on other suites)

**What goes wrong:** Coefficients optimised against Zurichess. Engine plays Zurichess-style positions well but loses against V6 in middlegames (which Zurichess underrepresents) or endgames (which Zurichess has but with different style preferences).

**Why it happens:** A single dataset is a single phenotype. Texel doesn't have train/val split by default.

**How to avoid:**
- Hold out 10% of Zurichess as validation. If validation loss diverges from training loss, stop early.
- After tuning, run a separate suite (CCRL test positions, STS strategic suite) as out-of-distribution check. Score should not regress vs V6.
- Truly conclusive: gauntlet is the validation. **Tuning improvement is hypothesis; gauntlet is verdict.**

**Warning signs:**
- Train loss decreases monotonically, validation loss flat or increases after iteration 30.
- STS regression after tuning despite Zurichess loss improvement.
- V7-tuned vs V7-untuned gauntlet shows mixed result (some openings worse).

**Phase to address:** **E2** (Texel pipeline), validated in **F1** (gauntlet).

---

### Pitfall 18: Texel forgets phase interpolation

**What goes wrong:** Eval is `mg * phase + eg * (1 - phase)`. Tuner optimises `(mg, eg)` separately or only optimises one. Tuned mg conflicts with default eg, opening play goes haywire while endgame stays untuned.

**Why it happens:** Tapered eval is conceptually two evals. Tuner code is easier to write for "one set of weights" than "weight pair with phase blend."

**How to avoid:**
- Coefficients are `Score{mg, eg}` pairs throughout. Loss function computes phase from position and applies the blend before sigmoid.
- Tuner gradient updates mg and eg simultaneously per term.
- Test: opening test position should change when mg changes; endgame position should change when eg changes; mid-game should respond to both.

**Warning signs:**
- Tuned engine plays opening well but endgame poorly (or vice versa).
- All eg coefficients identical to defaults after tuning.

**Phase to address:** **E2** (Texel pipeline). This is a design decision in the loss function.

---

### Pitfall 19: Search params and eval co-tuned wrong (eval-only tuning without search retune)

**What goes wrong:** Texel-tunes the eval. Search params (LMR formula constants, null-move R, futility margins) were designed against the *old* eval. New eval has different score scales (e.g. tuned king-attack term is 30% larger), so futility margins are now too tight, RFP triggers too often, etc. Search prunes lines the new eval would have judged interesting.

**Why it happens:** Search and eval are coupled through score thresholds. Tuning one without the other shifts the balance.

**How to avoid:**
- After Texel converges, run a **single-position bench at fixed depth** before/after. If NPS changes >20% or depth reached changes by >2 plies, search params need re-tuning.
- Adjust margins proportionally: if avg `|eval|` increased 25%, scale all margin constants by 1.25.
- Out of scope: SPSA-tune search params. In scope: **at minimum, hand-adjust margins** based on the avg-eval shift, and gauntlet to verify.
- Treat search params as part of the V7 release artifact, not as orthogonal to eval.

**Warning signs:**
- Tuned eval improves on tactical suites in single-position tests but loses gauntlet vs untuned engine.
- Search depth at fixed time drops noticeably after tuning.
- Engine prunes captures that visibly should be considered.

**Phase to address:** **E2** (Texel pipeline) end-of-iteration sanity check; revisit in **F1** if gauntlet shows regression.

---

### Pitfall 20: Syzygy DTZ vs WDL confusion

**What goes wrong:** Engine probes `tb_probe_wdl` at the root, gets "WIN", picks any winning move. Plays a "winning" move that *is* winning by WDL but loses on DTZ50 (the move pushes past the 50-move counter into draw territory). Engine throws tablebase wins.

The correct usage is: at the root, probe `tb_probe_root` (which uses DTZ to pick a move that respects the 50-move rule). Inside the tree, probe WDL only (DTZ probes are too slow).

**Why it happens:** Fathom's API has both, and the README treats them similarly. The semantic difference (WDL ignores 50-move; DTZ accounts for it) is in fine print.

**How to avoid:**
- At root: `tb_probe_root_dtz()` only (not WDL). If it returns a move, play it (or use as ordering hint).
- Inside search: `tb_probe_wdl()` only. Never call DTZ probe inside search (NPS killer).
- Treat root DTZ result as authoritative — convert to score `MATE_IN_MAX_PLY - dtz` (or analogous) and use as fallback if main search returns inconclusive.
- Test: KRk position with halfmove_clock=80 and a "winning by WDL but draw by DTZ" move available. Engine must NOT play the DTZ-losing move.

**Warning signs:**
- Engine wins KQK in tablebase tests but draws KRkp.
- 50-move counter expires in tablebase positions that should be wins.
- TB hits in search are very slow (probably accidentally calling DTZ inside search).

**Phase to address:** **B3** (Syzygy integration) — the API call choice is a foundational decision.

---

### Pitfall 21: Syzygy probe failure silently treated as draw

**What goes wrong:** `tb_probe_wdl` returns `TB_RESULT_FAILED`. Engine treats `FAILED` as `DRAW`. Position is not actually a TB position (e.g., 7 men, en-passant unclear, castling rights present) and is in fact winning. Engine plays for a draw. Or worse: probe returns `TB_RESULT_CHECKMATE` or `TB_RESULT_STALEMATE` and the engine doesn't handle these special return codes.

**Why it happens:** Fathom's return codes are confusing — there are 7+ distinct outcomes encoded. Easy to write `if (probe == TB_WIN) ... else if (probe == TB_LOSS) ... else { return draw_score; }`.

**How to avoid:**
- Treat `TB_RESULT_FAILED` as "skip TB, fall back to search". Never as draw.
- Explicitly handle `TB_RESULT_CHECKMATE` (rare but real for KQK-style positions) as immediate mate.
- Add an `info_assert(stm_is_to_move_in_position)` before the probe to catch position-construction bugs.
- Bench probe-rate: count probes vs hits. Hit rate should be >50% inside the TB ply range; if it's <10%, probe construction is broken.

**Warning signs:**
- TB hit count in `info` is suspiciously low (e.g. 5% of probes).
- Engine draws TB-confirmed wins.
- `tb_probe_wdl` called with positions outside the TB range (probe should be guarded by `popcount <= TB_LARGEST`).

**Phase to address:** **B3** (Syzygy integration). Add an explicit probe-rate metric to the bench output for ongoing observability.

---

### Pitfall 22: Syzygy excessive probing inside search → NPS collapse

**What goes wrong:** Probe at every node in the search tree. Each probe is ~1 µs (fast disk cache) to ~50 µs (cold disk). At 5 Mnps, even 1 µs/probe halves NPS. Engine is "TB-aware" but searches a quarter as deep.

**Why it happens:** "It's free knowledge, why not always probe?" — because the I/O cost is real, even cached.

**How to avoid:**
- Probe inside search only when:
  - `popcount(occ) <= TB_LARGEST` (ideally `<=` 5 to keep probes cheap),
  - `halfmove_clock == 0` (no 50-move concerns inside the tree),
  - `castling == 0` (TBs ignore castling rights),
  - `depth >= some_threshold` (e.g. 4 or 8) — don't probe at every leaf.
- Cache the result in TT entry (TB hits get an EXACT score with effectively infinite depth).
- Bench: NPS with TB probing should drop ≤20% vs no-TB on a position outside TB range (no probes hit), and should give measurable Elo gain on TB-relevant positions.

**Warning signs:**
- NPS drops 50%+ after enabling TB probing.
- High TB hit rate but search depth halved.
- Disk activity during search.

**Phase to address:** **B3** (Syzygy integration). Tune probe gating before C1 smoke milestone.

---

### Pitfall 23: Syzygy TB files missing/corrupt → crash on first probe

**What goes wrong:** User downloads partial TB set or unzips wrong. Fathom's `tb_init()` succeeds (just sets paths) but the first `tb_probe` calls `read_tb_file` → `mmap` fails or returns garbage → crash inside Fathom.

**Why it happens:** Fathom is C, panics ungracefully. No checksums on TB files.

**How to avoid:**
- Validate TB directory at init: enumerate `*.rtbw` and `*.rtbz` files. Expected count for 5-piece Syzygy is 290 .rtbw + 290 .rtbz = 580 files. Refuse to enable TB if count is wrong.
- Or: at init, probe a known-valid position (KRk) and verify the result matches a hard-coded expected value. Disable TB if mismatch.
- Wrap the probe in a try/catch (well, signal handler — Fathom uses `assert`); on failure, set "TB disabled this session" flag and warn user.
- Never crash the Python process from a TB error; log + degrade.

**Warning signs:**
- Engine crashes only when TB path is set.
- Crash occurs on specific positions (e.g. only with rooks vs only with bishops).
- `tb_init` returns success but `tb_probe` returns garbage.

**Phase to address:** **B3** (Syzygy integration), with checksums/file-count validation in the download script (`tools/download_syzygy.py`).

---

### Pitfall 24: Windows file-path issues with Syzygy

**What goes wrong:** User configures `syzygyPath = "C:\\Users\\name\\TB"`. Fathom uses `:` as path separator (POSIX convention) → splits the path on the drive-letter colon. TB files not found.

A second variant: backslash escaping in JSON (`syzygyPath = "C:\Users\name\TB"`) → JSON parser fails, Python config falls back to default (TB disabled), engine plays without TBs and user thinks they're enabled.

**Why it happens:** Cross-platform path handling. Fathom doesn't document the separator; on Windows it's `;` (PATH-like) but the codebase predates clear documentation.

**How to avoid:**
- In `syzygy.cpp`, normalize paths: on Windows pass `;` separator; on POSIX pass `:`.
- In Python config, accept `syzygyPath` as a list-of-strings or single string and join with the platform separator before passing to C++.
- In `tools/download_syzygy.py`, write the path back to config using `pathlib.Path` (forward slashes work on Windows for read).
- Test on Windows with a path containing spaces (`C:\Users\Some User\TB`) — must also work.

**Warning signs:**
- TB hit count is zero on Windows but positive on Linux.
- Path is accepted by Python (config loads fine) but Fathom never finds files.
- Works for short paths, fails for long paths.

**Phase to address:** **B3** (Syzygy integration). The Windows-on-this-codebase note is critical: this project's environment is Windows 11 per env metadata, so this pitfall is *more* likely than usual.

---

### Pitfall 25: KPK eval contradicts Syzygy

**What goes wrong:** Engine has both an in-engine KPK bitbase (or evaluator) AND Syzygy probing for ≤5 men. KPK position is queried — KPK bitbase says "win", Syzygy says "draw" (because of stm/halfmove edge case the bitbase doesn't model). Engine gets contradictory eval scores depending on which path runs first.

**Why it happens:** Two sources of truth for endgame knowledge.

**How to avoid:**
- **Syzygy wins.** When TB is enabled and the position is in TB range, never call the in-engine endgame eval. Short-circuit before eval.
- When TB is disabled OR position is out of range, use in-engine eval (KPK bitbase, opposition, fortress).
- Test: same KPK position evaluated with TB on and off should give same *outcome* (win/draw/loss), even if scores differ.

**Warning signs:**
- Engine plays KPK consistently when TB on, inconsistently when TB off.
- Eval score for KPK position changes by huge amount between TB on/off.
- Engine plays a known-winning KPK as a draw (in-engine eval said draw, TB never queried due to gating bug).

**Phase to address:** **D3** (endgame eval) — this is a design call for how the eval entry path picks its source.

---

### Pitfall 26: Phase detection threshold wrong

**What goes wrong:** Phase computed from material count. Threshold for "endgame" is too high → mid-late-game positions evaluated with endgame eval (which over-values king activity, under-values king safety). Engine walks its king into a mid-game attack thinking it's an endgame.

Conversely too low → endgame positions evaluated with mid-game eval, missing zugzwang/opposition.

**Why it happens:** "Phase" is a continuous variable (Stockfish uses 0–256). Engines that quantize too early (binary "MG vs EG" branching) lose smoothness.

**How to avoid:**
- Use Stockfish-style continuous phase: `phase = sum(piece_phase[piece]) for non-pawn pieces`, normalized to `[0, 256]` where 256 = full board, 0 = K vs K.
- Eval is `(mg * phase + eg * (256 - phase)) / 256`.
- Never branch "if endgame: ... else: ..." — always blend.
- For specific endgame logic (KPK, fortress), gate on hard material counts (`popcount(occ) <= 5`) not on phase.
- Test: phase value should decrease monotonically as material is removed in a self-play game.

**Warning signs:**
- Engine evaluation is jumpy across single moves (suggests phase crossing a threshold).
- King-safety weighted positions in late mid-game where engine ignores king attacks.
- Endgame KPK plays well, but K+P vs K+N positions evaluated as full mid-game.

**Phase to address:** **D3** (endgame eval).

---

### Pitfall 27: Fortress detection false positives → engine throws drawn games

**What goes wrong:** Fortress hint says "this is a fortress, score = 0." Position is NOT a fortress and is winning. Engine accepts the hint, plays for a draw, throws the win.

Fortresses are notoriously hard to detect — Stockfish historically *removed* fortress detection because false-positive cost > true-positive gain.

**Why it happens:** Heuristic fortress detection (e.g. "opposite-coloured bishops + locked pawns = fortress") misses many cases (forced exchange of bishops breaks the fortress).

**How to avoid:**
- Be very conservative. Only declare fortress when ALL of:
  - Material is K+B+P vs K+B opposite colours, AND
  - All pawns are blockaded, AND
  - Defending king covers the promotion square,
  - depth ≥ 20 (enough plies tried already).
- Even then, give a *score scaling* (e.g. `score *= 0.5`), not score = 0. Lets search find a tactic if one exists.
- Skip fortress detection entirely in V7 if uncertain. It's "fortress hints" in PROJECT.md, not "fortress detection". Lean toward no-op.

**Warning signs:**
- Engine throws winning OCB endings vs V6.
- Engine evaluates known-won R+P endings as 0.
- Self-play games where one side has visible advantage but eval says 0.

**Phase to address:** **D3** (endgame eval). If ambiguous, *skip* this feature — it's a bonus, not a requirement.

---

### Pitfall 28: Wrong-coloured-bishop + rook-pawn rules misapplied

**What goes wrong:** Eval bonus for "wrong-coloured bishop with rook pawn = draw" applied without checking king proximity. Position with K close to promotion square is winning despite the wrong-coloured bishop, but eval scales it to 0.

**Why it happens:** The rule is well-known in three sentences but actually depends on king position relative to corner.

**How to avoid:**
- Apply the draw scaling only when:
  - Side has ONLY KB+P (no other pieces), AND
  - Bishop colour does NOT match promotion square colour, AND
  - Defending king is within 1 square of the promotion square (use `chebyshev_distance(defending_king, promotion_sq) <= 1`).
- Test: KBPk where defender's king is on g2 and promotion is h1 (defending king on h1) — engine should evaluate as draw. Same position with defender's king on a8 — engine should evaluate as winning.

**Warning signs:**
- Engine evaluates won wrong-bishop positions as 0.
- Engine evaluates drawn wrong-bishop positions as winning (forgot the rule).
- Tablebase confirms different result than engine eval in 5-man wrong-bishop positions.

**Phase to address:** **D3** (endgame eval). Test with explicit wrong-bishop test positions (Müller & Lamprecht has many).

---

### Pitfall 29: Gauntlet TC/hash/threads not identical between V6 and V7

**What goes wrong:** Gauntlet runs V6 with 64 MB hash and V7 with 256 MB. V7 wins by 80 Elo. User celebrates. Real Elo gain: 0; the difference is hash size. (Or: V7 runs with 4 threads, V6 with 1. Or: V7 gets 60+0.6, V6 gets 30+0.3.)

**Why it happens:** Easy to forget options when scripting fastchess. Default values differ between engines.

**How to avoid:**
- Both engines specified explicitly:
  ```
  fastchess
    -engine cmd=v6_uci.exe name=v6 option.Hash=128 option.Threads=1
    -engine cmd=v7_uci.exe name=v7 option.Hash=128 option.Threads=1
    -each tc=10+0.1
    -openings file=8moves_v3.pgn
    -games 1000
    -concurrency 4
    -sprt elo0=0 elo1=10 alpha=0.05 beta=0.05
  ```
- Run a sanity probe **before** the real gauntlet: V6-vs-V6 with these options. Result must be ~0 Elo (within statistical noise). Anything else means options aren't equal.
- Persist the exact command line in the gauntlet result file. Audit the command on review.

**Warning signs:**
- Massive Elo difference (V7 +200) at the start of the milestone — too good to be true.
- V6-vs-V6 sanity gauntlet shows nonzero Elo.
- Engine logs show different `option set Hash` values than expected.

**Phase to address:** **F1** (gauntlet harness). Sanity probe is a literal first test of the harness.

---

### Pitfall 30: SPRT misconfigured (wrong elo bounds, wrong alpha/beta)

**What goes wrong:** SPRT bounds set `elo0=0 elo1=5` (too tight) → SPRT requires 50,000+ games to terminate at typical TC, milestone never finishes. Or `elo0=-5 elo1=20` (too loose) → SPRT accepts H1 even for marginal improvements, false positives inflate Elo.

**Why it happens:** SPRT bounds are a tradeoff between sensitivity and game count. Stockfish's standard is `elo0=0 elo1=4` for STC, `elo0=0 elo1=2` for LTC. These are tuned for years of CI running 24/7 — too strict for a milestone.

**How to avoid:**
- For milestone gates, use `elo0=0 elo1=10` with `alpha=0.05 beta=0.05`. Typical termination in 1k–5k games at 10+0.1 TC.
- For "definitely improved" signal, run a separate gauntlet at fixed game count (1000 games) and report the LOS (likelihood-of-superiority).
- Document SPRT params in the gauntlet result; never pick params after seeing the result (cherry-picking).
- Pentanomial reporting (`-report penta=true` in fastchess) is more robust than win/loss/draw — use it.

**Warning signs:**
- SPRT runs >10k games without terminating.
- Multiple SPRT runs give different verdicts on the same change (suggests bounds too tight).
- SPRT terminates at 100 games (suggests bounds too loose).

**Phase to address:** **F1** (gauntlet harness).

---

### Pitfall 31: Opening book bias

**What goes wrong:** Gauntlet uses a balanced book (good). But: book is symmetric only at depth 1. By move 8 some positions are +0.3 for white, others -0.3, and the engine that "prefers" tactical white positions wins more games — the *opening selection* drove the result, not the engine quality.

**Why it happens:** "Balanced" books are typically balanced *on average* across many positions; per-position they have biases. With 100 games each from 50 positions you get ~50 games per position, plenty of room for opening bias to dominate.

**How to avoid:**
- Use a large, diverse book — fastchess `8moves_v3.pgn` (~10k positions) is the community standard.
- Always play **both colours** from each opening (`-rounds N -repeat`). Engine plays each opening once as white, once as black.
- Report results per-opening; check no opening dominates.
- For tournament-style rigor, use UHO_4060_v2 or Pohl Openings.

**Warning signs:**
- Result swings wildly between gauntlet runs with different books.
- Win rate as white very different from win rate as black.
- Specific opening explains 50%+ of the Elo delta.

**Phase to address:** **F1** (gauntlet harness).

---

### Pitfall 32: Insufficient game count for statistical significance

**What goes wrong:** Run 50 games, V7 wins 28-22, conclude "+50 Elo". Real margin of error at 50 games is roughly ±60 Elo. Result is noise.

**Why it happens:** "More games take more time, ship the milestone" pressure.

**How to avoid:**
- Minimum 1000 games for any "ship" verdict at typical Elo deltas (10–50 Elo).
- For confirming small gains (5–15 Elo), 5000+ games.
- Use SPRT termination: stops automatically when statistically significant.
- Always report the 95% CI alongside the Elo delta.

**Warning signs:**
- Reported "+50 Elo" with N <500.
- Re-running same gauntlet gives result swinging by >40 Elo.
- LOS (likelihood of superiority) <95%.

**Phase to address:** **F1** (gauntlet harness) and **G1** (ship gate).

---

### Pitfall 33: Time forfeits silently counted as losses

**What goes wrong:** V7's iterative deepening has a bug — uses 100% of allotted time on every move. Occasionally exceeds the time budget by ~50ms. Server-side time control flags V7 → loss recorded. Gauntlet shows V7 down 30 Elo. Real engine strength is +20 Elo, but the time forfeits dominate.

**Why it happens:** Time management bugs are subtle. Engines need ~10–20% safety margin to handle node-poll granularity.

**How to avoid:**
- Track time forfeits separately in gauntlet output.
- Investigate any time forfeit manually — it's almost always a bug, not "ran out of think time".
- Time-management rule: stop iterative deepening when `elapsed > 0.4 * allotted` (next iteration usually 2× current → would exceed budget). Stop mid-iteration when `elapsed > 0.95 * allotted`.
- In the gauntlet, configure `-each timemargin=50` (50ms tolerance) — but treat any usage of the margin as a bug to investigate.

**Warning signs:**
- Gauntlet result has nonzero "time loss" count for V7.
- V7 Elo improves dramatically when given extra TC margin.
- V7 uses >95% of budget consistently (no slack).

**Phase to address:** **B1** (time management) initially; verified in **F1** (gauntlet).

---

### Pitfall 34: Gauntlet on a laptop with CPU throttling / battery / thermal

**What goes wrong:** 1000-game gauntlet runs for 8 hours. Laptop thermally throttles after game 200. NPS for both engines drops 30%. Gauntlet completes but the result is biased toward engines with smaller search overhead (because they degrade more gracefully under throttling).

A second variant: laptop on battery — Windows applies aggressive power-saving, NPS drops 50%, results are unrelated to plugged-in performance.

**Why it happens:** Gauntlets are long. Heat sinks aren't designed for sustained 100% CPU. Battery vs AC is a one-bit difference.

**How to avoid:**
- Plug in. Disable Windows power saving (`powercfg /setactive SCHEME_MIN`).
- Run gauntlets on a desktop or rented cloud VM (e.g. Hetzner CCX22 EPYC, ~$0.05/hr) for repeatability.
- If laptop is the only option: cap concurrency to N-2 cores, run during cool weather, monitor `wmic cpu get LoadPercentage`.
- Sanity probe: run V6-vs-V6 100 games, then V6-vs-V6 100 games immediately after. Results should be statistically identical.

**Warning signs:**
- V6-vs-V6 sanity gauntlet shows nonzero Elo on second run.
- NPS reported in `info` lines drops over the gauntlet duration.
- `Concurrency=4` results differ from `Concurrency=1` results by more than noise.

**Phase to address:** **F1** (gauntlet harness) — environmental setup is part of the harness's responsibility.

---

### Pitfall 35: Lazy SMP non-determinism makes 1-thread vs 4-thread results differ

**What goes wrong:** Tune at 1 thread, gauntlet at 4 threads. The 4-thread engine sees different positions and the eval/search interaction is different. Tuned engine doesn't show the gain at 4 threads.

**Why it happens:** Lazy SMP is non-deterministic by design. Same position + same time + 4 threads = different best move possible.

**How to avoid:**
- Always do **fixed-depth** comparison for tuning (deterministic for a given coefficient set).
- Do **fixed-time** comparison only in the gauntlet, with the same thread count both engines will use in production.
- Document thread count in coefficient JSON: "tuned for 1 thread, validated at N threads."
- For final ship gate: gauntlet at 1 thread AND 4 threads; both should show improvement.

**Warning signs:**
- Tuning improvement appears at 1 thread but vanishes at 4 threads.
- 4-thread V7 vs 1-thread V7 gives a smaller margin than V7-vs-V6 at same thread count.
- Coefficients optimised for 1 thread cause regression at 4 threads.

**Phase to address:** **E1** (Lazy SMP) determines this constraint; **E2** (Texel) and **F1** (gauntlet) implement it.

---

## Critical Project-Management Pitfalls

### Pitfall 36: Building Lazy SMP before lockless TT

**What goes wrong:** E1 (Lazy SMP) starts before D1 (lockless TT) finishes. Search runs with single-threaded TT under 4 threads. TT corruption silently happens. Search returns illegal moves intermittently. Days lost debugging "intermittent illegal move bug" before realizing the TT is the culprit.

**Why it happens:** "Threads spawn fine, search returns a move, looks like it works" — the corruption is rare and hard to repro.

**How to avoid:**
- **D1 must finish before E1 starts.** Hard ordering. Document in the roadmap.
- Add a TT correctness stress test (described in Pitfall 9) as the *gate* between D1 and E1.
- If timeline forces parallelism: build E1 with `Threads=1` only as a placeholder, mark "parallel disabled until D1 done."

**Warning signs:**
- See Pitfall 9 warning signs.

**Phase to address:** **D1** must precede **E1**. Phase ordering is the prevention.

---

### Pitfall 37: Skipping the gauntlet harness early — flying blind for weeks

**What goes wrong:** F1 (gauntlet) is the *last* infrastructure built. Phases B/C/D/E ship without head-to-head verification. By the time F1 runs, V7 has accumulated subtle regressions in any of LMR/null/futility/etc. and the gauntlet shows -30 Elo. Now you don't know which change caused it.

**Why it happens:** Gauntlet harness feels like "validation infra" rather than "development infra". It's both.

**How to avoid:**
- Bring up F1 *as part of C1* (smoke milestone). At C1, V7 baseline plays a 50-game V6-vs-V7 gauntlet.
- Every D-phase change re-runs the 50-game (or 200-game) gauntlet. Regressions caught immediately.
- The harness need not be polished at C1 — a hacky `subprocess.run(["fastchess", ...])` with a JSON-printed result is fine.

**Warning signs:**
- "Let's gauntlet at the end" mindset.
- Multiple D/E features land without head-to-head testing.
- Bugs surface only in the final F1 run.

**Phase to address:** **F1** infrastructure should be built as part of **C1** (smoke), not delayed to the end.

---

### Pitfall 38: Re-introducing NNUE / opening book mid-milestone

**What goes wrong:** Mid-D2, someone says "while we're here, let's also add an opening book" or "NNUE wouldn't be that much work." Milestone scope expands. V7 doesn't ship in any reasonable time, or ships half-baked NNUE that loses Elo.

**Why it happens:** Adjacent improvements are tempting. "It's just a small addition."

**How to avoid:**
- PROJECT.md explicitly lists NNUE and opening books as out-of-scope. Re-read it at every weekly review.
- New ideas → add to a `IDEAS.md` file for a future V8 milestone. Do not implement.
- Definition of done = "V7 wins gauntlet vs V6 with the planned scope" — not "V7 has feature X."

**Warning signs:**
- "While I'm in this file, let me also..."
- Estimates for D-phase grow beyond initial scope.
- Out-of-scope features start being prototyped in branches.

**Phase to address:** **All phases** (project management, not technical).

---

### Pitfall 39: Refactoring v5/v6/`GameManager` while building V7

**What goes wrong:** Touch `GameManager.ai_move` to add V7 dispatch. While there, "fix" the engine ladder to a registry. Now V1–V6 dispatch behavior changes subtly. Tests for v3 fail. Hours debugging legacy engine paths that V7 didn't need to touch.

**Why it happens:** Anti-patterns are visible (documented in `.planning/codebase/CONCERNS.md`). Resisting cleanup feels wrong to engineers with taste.

**How to avoid:**
- PROJECT.md lists v5* consolidation and `GameManager` refactor as explicit out-of-scope.
- Add V7 dispatch via the *minimum* number of lines (mirror v6 pattern: `elif current_engine == "v7": ...`).
- Track cleanup ideas in a separate file or issue. Do not blend.
- Rule: V7 PRs should not touch v1/v2/v3/v4/v5 files (other than test fixtures). Lint this in code review.

**Warning signs:**
- V7 PR diff includes changes to `engine/v3/` or `engine/v5d/`.
- v3 tests start failing with "unrelated" V7 work.
- Engine selector behavior changes for non-V7 engines.

**Phase to address:** **All phases**.

---

## Integration Pitfalls (Specific to This Project)

### Pitfall 40: V6 still works after V7 lands

**What goes wrong:** Adding V7 to `GameManager.ai_move` accidentally breaks v1–v6 (typo in `elif`, missing import, shadowed name). Existing functionality regresses.

**Why it happens:** The string-comparison engine ladder is fragile (documented anti-pattern). Editing it is error-prone.

**How to avoid:**
- Add V7 as the *last* `elif` branch, after v6, never editing earlier branches.
- Run the existing pytest suite (`uv run pytest`) before AND after the V7 dispatch addition. Diff results.
- Add a smoke test that dispatches each of v1, v2, v3, v6, v7 and asserts a legal move is returned.

**Warning signs:**
- Existing engine tests fail after V7 dispatch added.
- `from chess_engine.engine.v7 ...` imports fail and cascade into other engine modules.

**Phase to address:** **A1** (V7 module skeleton — first dispatch wiring) and **C1** (smoke milestone).

---

### Pitfall 41: `native_build.py` failure on Windows MSVC vs MinGW

**What goes wrong:** V6's `native_build.py` works on the original developer's machine (MSVC 2022 + Python 3.11). New developer has MinGW + Python 3.12 → CMake picks the wrong generator → pybind11 fails to detect Python → build fails with cryptic linker errors.

This is the project's actual environment (Windows 11 per env metadata).

**Why it happens:** Auto-build hooks hide build complexity until they break. Then they break catastrophically.

**How to avoid:**
- In `native_build.py`, explicitly pass `-G "Visual Studio 17 2022"` (or whichever generator was tested) — don't rely on CMake auto-detection.
- Also explicitly pass `-DPython_EXECUTABLE=$(python -c "import sys; print(sys.executable)")`.
- Document required toolchain in `engine/v7/README.md`: "Windows: Visual Studio 2022 Build Tools or full IDE; Linux: gcc 9+; macOS: Xcode CLT."
- Add a build-time check: print compiler version, Python version, CMake version, and refuse if version requirements aren't met.
- Catch build failure in the auto-build path; print a clear error pointing at README rather than letting the import fail with `ModuleNotFoundError`.

**Warning signs:**
- New machine fails to build but gives no clear error.
- CMake silently picks MinGW when MSVC is also installed.
- Build succeeds but produces a `.pyd` that `import` fails on (ABI mismatch).

**Phase to address:** **A1** (module skeleton), revisited if issues surface in **C1** (smoke).

---

### Pitfall 42: `client/src/App.jsx` engine list drifts from backend

**What goes wrong:** Backend `GameManager.AVAILABLE_ENGINES` includes V7. Frontend `App.jsx` doesn't add the V7 `<option>` to one of the two dropdowns (white selector but not black selector, easy to miss). User can't select V7 for one colour.

A second variant: forget to update the "build may take a while" warning to fire for `"v7"` (currently fires only for `"v6"`).

**Why it happens:** Engine list is hardcoded JSX in two places per the architecture research. No single source of truth.

**How to avoid:**
- Diff `App.jsx` for *all* references to `"v6"` before adding V7. Add V7 next to each of them.
- Add a Python/JS integration test (or even a manual checklist in PR template): "Both white and black dropdowns include V7. Build warning fires for V7."
- Long-term (out of scope): expose engine list via `/api/engines` endpoint, frontend queries it. Track this as a follow-up.

**Warning signs:**
- V7 selectable for white but not black (or vice versa).
- No "build may take a while" warning when first selecting V7.
- Frontend "v6" matches don't all have a sibling "v7" match.

**Phase to address:** **C1** (smoke milestone) — UI must work for V7 to be selectable end-to-end.

---

### Pitfall 43: pybind11 module breaks imports of OTHER engines

**What goes wrong:** V7 module loads, but loading also pulls in a shared `Device` or `numba` import that interacts badly with V4b's CUDA initialization. After importing V7 once, V4b stops working.

**Why it happens:** Python imports are global. Side-effects in module-load order matter.

**How to avoid:**
- V7 `__init__.py` does NOT import V4b/CUDA-specific modules.
- V7 native module is named `v7_engine` (not `engine`), no name clash.
- Test: import V7 first, then import V1, V3, V4b, V6. All `find_best_move` calls succeed.
- Test: import V6 first, then V7. All `find_best_move` calls succeed.

**Warning signs:**
- V4b CUDA init fails after V7 imported.
- Import order matters (a sign of side-effects).
- V6 native module fails to load when V7 is loaded too.

**Phase to address:** **A1** (skeleton — get the import-isolation right early).

---

### Pitfall 44: V7 not added to the test bench / CLI

**What goes wrong:** `cli/src/index.js` has `chess-engine bench v6`. V7 is never added. `chess-engine perft v7` doesn't exist. Manual benchmarks omit V7. Regressions undetected.

**Why it happens:** CLI commands are added one-by-one per engine. Easy to forget.

**How to avoid:**
- Mirror every existing `v6` CLI command as a `v7` command.
- Add CLI tests in pytest: `subprocess.run(["chess-engine", "bench", "v7"])` returns 0.
- Document in `engine/v7/README.md`: "Run `chess-engine bench v7` to benchmark."

**Warning signs:**
- `chess-engine perft v6` works but `chess-engine perft v7` errors.
- New benchmarks omit V7.

**Phase to address:** **C1** (smoke milestone) and **A1** (skeleton).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| Copy `tt.cpp` from V6 to V7 unchanged | Fast V7 bring-up | TT under threads will silently corrupt | **Only at A1 skeleton stage; rewrite mandatory before C1** |
| Tune Texel coefficients with K refit per iteration | Loss curve looks smooth | Coefficients optimise K, not eval | Never |
| Hardcoded engine list in `App.jsx` | One-line frontend change | Must edit JSX every milestone | Acceptable for V7 (out of scope to fix); track as V8 task |
| `bare except:` blocks in V7 binding code | Hides build/probe failures | Swallows Ctrl-C, masks bugs | Never |
| Skip TB validation at init (just init and hope) | Faster startup | Crash on first probe with corrupt TBs | Never; the cost of validation (one probe) is negligible |
| Use `volatile` instead of `std::atomic` for stop flag | "It works" on x86 | Undefined behaviour, breaks on ARM | Never |
| Run gauntlet on laptop battery | Available when offline | Throttling biases results | Sanity probes only; never for ship-gate gauntlet |
| Tune at fixed depth, gauntlet at fixed time | Deterministic tuning | Tuned coeffs may not transfer to time-controlled play | Acceptable as long as gauntlet at fixed time confirms gain |
| Skip re-tuning search params after eval tuning | Less work | Search/eval co-tuning is missed | Acceptable for milestone if hand-checking margins; full SPSA out of scope |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| **Fathom (Syzygy)** | Use `tb_probe_wdl` at root, ignore 50-move | Use `tb_probe_root_dtz` at root, `tb_probe_wdl` inside search |
| **Fathom on Windows** | Use POSIX `:` separator in path list | Use `;` separator on Windows; normalise in C++ |
| **pybind11** | Forget `py::gil_scoped_release` on multi-threaded entry point | Always wrap blocking C++ in `py::call_guard<py::gil_scoped_release>()` |
| **pybind11** | Worker threads call back into Python | Workers strictly C++-only; queue Python work for the main thread |
| **fastchess** | Run with default engine options | Always specify Hash, Threads, TimeMargin explicitly per engine |
| **fastchess** | Trust the engine name in result | Sanity-probe engine vs itself first |
| **CMake `FetchContent`** | Use for Fathom (depends on network at first build) | Use git submodule for Fathom; `FetchContent` only for pybind11 |
| **Zurichess EPD** | Treat all positions as quiet | Re-filter: drop in-check, drop where qsearch differs from eval |
| **GameManager dispatch** | Refactor the engine ladder while adding V7 | Add V7 as last `elif`, leave structure unchanged |
| **`SearchInfo` cancellation** | Assume Python flag reaches C++ workers | Wire explicit `engine.stop()` call from `GameManager.stop_search` |
| **Numba JIT (existing)** | Import V7 imports Numba accidentally | V7 module imports nothing from `core/` Numba paths |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| Probe Syzygy at every node | NPS halves, disk I/O during search | Gate: `popcount<=5 && halfmove_clock==0 && depth>=4` | Always (any TB usage without gating) |
| LMR re-search at full depth | NPS gain from LMR vanishes | Re-search at `depth-1`, not `depth` | Always (textbook bug) |
| TT shared across threads but per-slot lock | NPS scales 1.5× from 1→4 threads | Use Hyatt-Mann XOR; no locks | At 4+ threads |
| `std::cout` from search hot path | NPS drops 50% with debug logging on | Buffer in C++, flush on iteration end | Always (debug builds, but easy to forget) |
| Per-call binding allocations (returning new lists) | NPS at root drops 5–10% | Return tuples, not lists; pre-allocate result objects | At fast TC (1+0.01) |
| Recompute attack tables per node | NPS halves vs cached attacks | Magic bitboard tables in static memory | Always |
| Rebuild TT per `find_best_move` call (V6's current behaviour) | First moves of new game are slow; no carry-over | Persist TT in process-singleton `V7Engine` instance with aging | Always |
| Worker thread acquires GIL for logging | Lazy SMP NPS scales <2× from 1→4 threads | Workers never touch Python; flush logs from main thread post-search | At 2+ threads |
| Call `popcount` instead of using cached piece counts | Eval cost ~20% higher | Maintain incremental piece counts in `make_move`/`unmake_move` | Always (eval-bound builds) |
| NUMA cross-socket TT access | NPS scales worse at >8 threads on dual-socket | Pin threads to one socket; use first-touch allocation for TT | Only on dual-socket workstations (rare in dev) |

---

## Validation Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| Single SPRT run as ship gate | Cherry-picked result | Run 3 independent SPRT runs; all must pass |
| Gauntlet on same opening book engine was tuned with | Overfit on book | Use a different book for gauntlet vs tuning if any tuning is book-aware (V7 has no book; mostly N/A) |
| Manual count of wins/draws/losses | Off-by-one, missing draws | Use fastchess pentanomial output exclusively |
| "It feels stronger" subjective review | Confirmation bias | Only gauntlet results count |
| Ship after one good gauntlet, ignoring next-day gauntlet showing regression | Variance treated as result | Gauntlet must be reproducible; require ≥2 independent runs |
| Tune on Zurichess, validate on Zurichess | No out-of-distribution test | Hold out 10% of Zurichess; also validate against STS or similar |
| Compare V7-tuned vs V6, not V7-tuned vs V7-untuned | Can't separate eval from search gains | Run *both* gauntlets; report both deltas |

---

## "Looks Done But Isn't" Checklist

A position is reachable that exposes each of these. Always verify before ship.

- [ ] **Lazy SMP search:** spawn 4 workers for 1s search. Verify with `htop` that 4 cores hit 100%, not 1. Verify NPS scales ≥3× vs 1 thread.
- [ ] **TT persistence across moves:** print TT hit rate on move 1 (should be ~0%) and move 5 (should be ≥10% — confirms TT survived).
- [ ] **Cancellation:** start a 5s search in one thread, call `engine.stop()` after 100 ms. Search must return within 50 ms of `stop()`.
- [ ] **GIL released:** while V7 is searching, another Python thread does `requests.get('/api/state')`. Must complete in <100 ms.
- [ ] **Mate scores correct:** play a known forced-mate position (e.g. KQk with mate in 5). Engine reports `mate 5` then `mate 4` then `mate 3` etc. on consecutive moves, not `mate 5` repeating.
- [ ] **Repetition draw:** play out a known forced-repetition. Engine reports score 0 from depth 6+, not non-zero.
- [ ] **50-move counter:** position with `halfmove_clock=95` and tablebase win available. Engine plays the win, doesn't run out the counter.
- [ ] **Syzygy at root:** position in TB range. Engine reports `tbhits > 0` in info. Best move matches a TB-optimal move.
- [ ] **Syzygy disabled cleanly:** unset `syzygyPath`. Engine still plays; no errors; `tbhits = 0`.
- [ ] **Texel coefficients applied:** print `eval_quiet(starting_pos)` from Python tuner and from C++ search. Must match.
- [ ] **V7 in both colour selectors:** open the UI. Both dropdowns include V7.
- [ ] **Build warning on V7 selection:** select V7 for the first time in the UI. "Build may take a while" message appears.
- [ ] **V1–V6 still work:** dispatch each of v1, v2, v3, v4b, v6 after V7 is added. Each returns a legal move.
- [ ] **CLI bench V7:** `chess-engine bench v7` runs to completion.
- [ ] **Gauntlet sanity:** run V6-vs-V6 100 games. Result is statistically zero Elo (within ~30 Elo CI).
- [ ] **Gauntlet result reproducible:** same gauntlet command, two consecutive runs, results within statistical noise of each other.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| TT torn writes (Pitfall 9) | LOW (algorithmic; rewrite ~50 lines) | Rewrite tt.cpp with Hyatt-Mann XOR + atomic loads/stores; re-run TSan stress test |
| LMR off-by-one (Pitfall 4) | LOW (1–10 lines) | Audit reduction table indexing; A/B vs LMR-disabled at fixed depth |
| Texel converges wrong (Pitfall 13–18) | MEDIUM (re-tune cost: 1–4 hours per run) | Rerun tuning with K fixed once, multiple seeds, filtered positions |
| Texel tuned wrong terms (Pitfall 15) | LOW–MEDIUM (codegen + retest) | Generate `coeffs.cpp` from JSON; re-tune; verify with `eval_quiet` round-trip |
| Syzygy path bug on Windows (Pitfall 24) | LOW (path normalisation) | Add platform-aware separator handling in `syzygy.cpp` |
| Gauntlet run with mismatched options (Pitfall 29) | LOW (re-run gauntlet) | Run V6-vs-V6 sanity probe, then re-run V6-vs-V7 with explicit options |
| Lazy SMP no parallelism due to GIL (Pitfall 11) | LOW (1 line) | Add `py::call_guard<py::gil_scoped_release>()` |
| V6 broken by V7 dispatch (Pitfall 40) | LOW (revert + add carefully) | `git diff` GameManager; find the typo; re-run pytest |
| Tuning hill-climbed Zurichess but lost gauntlet (Pitfall 17) | MEDIUM | Hold out validation set; rerun with early-stop |
| Search forfeits time (Pitfall 33) | LOW–MEDIUM (time mgmt audit) | Tighten iterative-deepening stop condition; re-run gauntlet |
| Singular extensions exploding tree (Pitfall 5) | LOW (gate change) | Increase depth threshold for singular; verify NPS |
| KPK contradicts Syzygy (Pitfall 25) | LOW (eval gating) | Short-circuit eval when TB hit available |
| Fortress false positives (Pitfall 27) | LOW–MEDIUM | Disable fortress detection; ship without it; revisit in V8 |
| V7 ships with NPS regression beyond 20% (Pitfall 19, 22) | MEDIUM (search/eval profiling pass) | Profile with perf/vtune; identify hot paths added by V7; consider TT-size or coefficient changes |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| 1. TT mate score adjustment | B1 | Unit test: store/probe round-trip with mate scores |
| 2. Aspiration window infinite loop | B1 | Iteration completes within 2× time budget; bounded re-searches |
| 3. Null-move zugzwang | B1, D2, D3 | KPK suite passes; Stockfish-style pawn-only guard; verification at depth ≥12 |
| 4. LMR off-by-one | D2 | LMR-on > LMR-off at gauntlet (≥30 Elo gain at 4-thread); STS no regression |
| 5. Singular extension explosion | D2 | NPS change <10% after enabling singular |
| 6. Multi-cut/probcut margins | D2 | Tactical suite no regression; gauntlet positive |
| 7. Repetition detection | B1 | Forced-repetition position returns 0 by depth 6 |
| 8. 50-move TT cutoff | D1, D3 | Halfmove≥80 forces re-search; TB win at halfmove=95 still played |
| 9. Lockless TT torn writes | D1 | TSan + 16-thread stress test passes |
| 10. Cancellation token missed | E1 | Stop within 50 ms test passes |
| 11. GIL not released | A1 (skeleton), E1 (verified) | NPS scales ≥3× from 1→4 threads |
| 12. History/killer shared | E1 | 4-thread Elo gain ≥40 in self-play |
| 13. Texel K refit | E2 | K fixed in tuner; documented in JSON |
| 14. Texel non-quiet positions | E2 | Filter step before gradient loop |
| 15. Texel coefficient mismatch | E2 | Codegen from JSON; round-trip eval test |
| 16. Texel local minimum | E2 | Multi-seed tuning; gauntlet picks winner |
| 17. Texel overfit | E2, F1 | Holdout validation; STS check; gauntlet verdict |
| 18. Texel phase interpolation | E2 | (mg, eg) pair tuned together; phase blend in loss |
| 19. Search/eval co-tuning | E2, F1 | Bench depth/NPS check; margin re-scaling |
| 20. Syzygy DTZ vs WDL | B3 | Root: DTZ; tree: WDL; halfmove=80 win test |
| 21. Syzygy probe failure | B3 | Failed probe → fall back, not draw; init-time validation |
| 22. Syzygy excessive probing | B3 | NPS drops ≤20% with TB enabled outside TB range |
| 23. Syzygy file validation | B3 | File-count check at init; KRk probe at init |
| 24. Windows Syzygy path | B3 | Path separator test on Windows |
| 25. KPK vs Syzygy | D3 | Eval short-circuits when TB hit available |
| 26. Phase detection | D3 | Continuous phase blend; monotonic decrease in self-play |
| 27. Fortress false positive | D3 | Conservative gating OR feature skipped |
| 28. Wrong-bishop rule | D3 | KBPk test positions both win and draw cases |
| 29. Gauntlet TC/hash/threads | F1 | V6-vs-V6 sanity probe gives 0 Elo |
| 30. SPRT misconfigured | F1 | Termination at <5k games; documented bounds |
| 31. Opening book bias | F1 | `8moves_v3.pgn`; play both colours per opening |
| 32. Insufficient game count | F1, G1 | ≥1000 games for ship gate; LOS reported |
| 33. Time forfeits as losses | B1, F1 | Track separately; investigate every forfeit |
| 34. Laptop throttling | F1 | AC power; sanity probe of repeatability |
| 35. Lazy SMP non-determinism | E1, E2, F1 | Tune at fixed depth; gauntlet at production thread count |
| 36. Lazy SMP before lockless TT | D1 → E1 ordering | Stress test gates D1 → E1 transition |
| 37. Skipping gauntlet harness | F1 built at C1 | Gauntlet runs after every D-phase change |
| 38. NNUE/book scope creep | All phases | Weekly PROJECT.md re-read |
| 39. Refactoring V5/V6 mid-V7 | All phases | V7 PRs lint: no changes outside `engine/v7/` (other than dispatch) |
| 40. V6 broken by V7 dispatch | A1, C1 | Run pytest before/after dispatch addition |
| 41. Windows MSVC vs MinGW | A1, C1 | Document toolchain; explicit CMake generator; build-version check |
| 42. App.jsx engine list drift | C1 | Diff App.jsx for "v6"; add V7 next to each |
| 43. pybind11 import side-effects | A1 | Cross-engine import order test |
| 44. V7 missing from CLI/bench | A1, C1 | CLI smoke test for `bench v7`, `perft v7` |

---

## Sources

- **Chess Programming Wiki** — Lazy SMP, Shared Hash Table, LMR, Singular Extensions, Null Move Pruning, Multi-Cut, ProbCut, Mate Distance Pruning. https://www.chessprogramming.org/
- **Hyatt & Mann (2002)** — A Lockless Transposition Table Implementation for Parallel Search. The XOR trick used in Stockfish, Ethereal, Komodo. https://www.craftychess.com/hyatt/
- **Stockfish source / commit history** — canonical reference for LMR formula, singular extension constants, time management. https://github.com/official-stockfish/Stockfish
- **Ethereal source** — clean Lazy SMP + lockless TT reference (smaller and more readable than Stockfish). https://github.com/AndyGrant/Ethereal
- **Texel's Tuning Method (Peter Österlund)** — original write-up of Texel-style tuning. https://www.chessprogramming.org/Texel%27s_Tuning_Method
- **Andrew Grant — Evaluation & Tuning in a Chess Engine** (paper). Coefficient extraction patterns, K-factor handling.
- **Fathom (jdart1)** — official Syzygy probing library; README for `tb_probe_root` vs `tb_probe_wdl`. https://github.com/jdart1/Fathom
- **fastchess docs** — gauntlet harness, SPRT options, pentanomial output. https://github.com/Disservin/fastchess
- **pybind11 docs — Misc / GIL** — `py::gil_scoped_release` semantics. https://pybind11.readthedocs.io/en/stable/advanced/misc.html
- **pybind11 issue #1446** — GIL holding causing thread starvation. https://github.com/pybind/pybind11/issues/1446
- **pybind11 issue #2215** — `gil_scoped_release` daemon-thread interpreter-shutdown crash.
- **TalkChess forum** — countless threads on Texel pitfalls (K refit, quiet filtering), Lazy SMP per-thread vs shared state, Syzygy probe gating. http://talkchess.com/forum3/
- **Octavi Font — pybind11 multithreading parallellism Python** — practical write-up of GIL release patterns for parallel C++ workers. https://octavifs.com/post/pybind11-multithreading-parallellism-python/
- **Existing repo context** — `.planning/codebase/CONCERNS.md` (engine sprawl, GameManager ladder, V6 native build issues), `.planning/codebase/ARCHITECTURE.md` (anti-patterns documentation), `.planning/research/ARCHITECTURE.md` (V6 binding ignores Python `SearchInfo`, lockless TT requirement).

---
*Pitfalls research for: V7 chess engine — HCE + Lazy SMP + Texel + Syzygy*
*Researched: 2026-05-15*
