// V7 Engine class implementation.
//
// Plan 03 — pulls Engine::search and Engine::new_game out of
// python_bindings.cpp into this TU, wires SearchInfo.external_stop to
// stop_flag_ and SearchInfo.rep_stack to rep_stack_, and seeds the rep
// stack with the root position. Also implements Engine::set_syzygy_path as
// a thin forwarder to syzygy_.set_path() (Plan 05 implements the body of
// SyzygyState::set_path in src/syzygy.cpp).
//
// What this file owns this wave (Plan 03):
//   - Engine::new_game()
//   - Engine::search(fen, depth, time_ms)
//   - Engine::set_syzygy_path(path)   <- forwarder; real body is in syzygy_.set_path
//
// What this file does NOT own:
//   - Engine::stop / Engine::nodes / Engine::tbhits — inline in engine.hpp
//   - The pybind11 m.def block — lives in python_bindings.cpp (plan 04 also
//     edits the m.def block this wave; this TU does not touch it)

#include "engine.hpp"
#include "search.hpp"
#include "tt.hpp"
#include "types.hpp"

#include <algorithm>

namespace v7 {

void Engine::set_syzygy_path(const std::string& path) {
    // D-08 / SRCH-* — forward to the per-Engine SyzygyState. Plan 05
    // implements SyzygyState::set_path with the D-08 verbatim log strings,
    // filesystem checks, tb_init, and KRk smoke probe. Keeping the forwarder
    // here means include/engine.hpp's surface stays stable across waves.
    syzygy_.set_path(path);
}

void Engine::new_game() {
    // Reset cancellation + per-Engine counters.
    stop_flag_.store(false, std::memory_order_relaxed);
    nodes_.store(0, std::memory_order_relaxed);

    // Clear the transposition table so a new game doesn't inherit cached
    // scores from the previous one — stale entries from a different root
    // would confuse mate-distance correction (SRCH-13).
    tt_.clear();

    // SRCH-14 — clear the Engine-owned repetition stack. Without this, a
    // long previous game could leave hashes that spuriously trigger 3-fold
    // detection inside this new game's tree.
    rep_stack_.clear();
}

SearchResult Engine::search(const std::string& fen, int depth, int time_ms) {
    // -------------------------------------------------------------------------
    // FOUND-04 — drop any stop request from a PREVIOUS search before starting.
    // Without this, a stop() landing between two consecutive search() calls
    // would silently cancel the second search at its first poll. We clear
    // *before* the SearchInfo::reset() below so its external_stop propagation
    // reads the fresh `false`.
    // -------------------------------------------------------------------------
    stop_flag_.store(false, std::memory_order_relaxed);

    // Parse FEN into the working board. Board::from_fen recomputes the
    // Zobrist hash, which we need before pushing onto rep_stack_.
    board_.from_fen(fen);

    // SRCH-14 — seed the repetition stack with the ROOT position. Each child
    // make_move inside alpha_beta pushes the post-move hash and unmake pops;
    // having the root pre-pushed means the in-tree repetition check at any
    // ply correctly sees the root as one of the candidate prior positions.
    rep_stack_.clear();
    rep_stack_.push(board_.hash);

    // -------------------------------------------------------------------------
    // SearchInfo wiring:
    //   - external_stop -> &stop_flag_   (FOUND-04, Python-side cancellation)
    //   - rep_stack     -> &rep_stack_   (SRCH-14, Engine-owned RepStack)
    //   - soft/hard deadlines from TimeManager (SRCH-15, ≥10% safety margin)
    // -------------------------------------------------------------------------
    SearchInfo info;
    info.external_stop = &stop_flag_;
    info.rep_stack     = &rep_stack_;
    info.time_limit_ms = time_ms;

    // SRCH-15 — TimeManager allocates a per-move budget with the ≥10% safety
    // clamp. time_ms here is the entire remaining budget for this single
    // move; the upstream game manager / gauntlet owns longer-horizon
    // allocation. moves_to_go=1 makes the clamp the binding constraint.
    TimeManager tm = TimeManager::allocate(time_ms, /*increment_ms=*/0,
                                           /*moves_to_go=*/1);
    info.soft_deadline_ms = tm.soft_deadline_ms;
    info.hard_deadline_ms = tm.hard_deadline_ms;

    info.reset();   // sets start_time and propagates external_stop into stopped

    // Cap depth at the LMR-table-sized 64. V6 also caps here so LMR_TABLE
    // lookups stay bounded; we inherit the cap. Negative / zero depths still
    // produce a depth-1 search via iterative_deepening's `for depth = 1`.
    int max_depth = std::min(std::max(depth, 1), 64);
    info.depth = max_depth;

    // Mark a new TT generation so the replacement strategy distinguishes
    // entries from this search from prior searches' leftovers.
    tt_.new_search();

    // Run the iterative deepening loop. Returns SearchResultFull; we
    // translate to the pybind11-facing SearchResult below.
    SearchResultFull full = iterative_deepening(board_, info, /*verbose=*/false);

    // Pop the root hash we seeded above. Symmetry with the push keeps
    // rep_stack_.top stable across repeated search() calls on the same Engine.
    rep_stack_.pop();

    // Mirror the per-search node count into the Engine atomic so Python-side
    // `Engine.nodes()` reflects the work done by the most-recent search.
    nodes_.store(full.nodes, std::memory_order_relaxed);

    SearchResult r;
    r.best_move = full.best_move;
    r.score     = full.score;
    r.depth     = full.depth;
    r.nodes     = full.nodes;
    r.nps       = full.nps();
    return r;
}

} // namespace v7
