// V7 Engine class implementation.
//
// Plan 03 — pulls Engine::search and Engine::new_game out of
// python_bindings.cpp into this TU, wires SearchInfo.external_stop to
// stop_flag_ and SearchInfo.rep_stack to rep_stack_, and seeds the rep
// stack with the root position. Also implements Engine::set_syzygy_path as
// a thin forwarder to syzygy_.set_path() (Plan 05 implements the body of
// SyzygyState::set_path in src/syzygy.cpp).
//
// Plan 03-01 additions (D-01, D-03):
//   - Bug #1 fix: info.max_depth = max_depth (new field); info.depth = 0 so
//     iterative_deepening's loop counter never clobbers the caller's cap.
//   - g_tt migration: info.tt = &tt_ wired alongside external_stop/rep_stack
//     (D-01: severs search.cpp's dependency on the g_tt global before Plan
//     03-05's lockless rewrite).
//   - Persistent history/counter_moves wiring via info.search_stack, info.history,
//     info.counter_moves pointers (D-03 Bug #2 fix).
//   - age_history() called before iterative_deepening (RESEARCH.md A11 decay).
//   - Engine::new_game() extended with memset(history_/counter_moves_).
//   - Engine::set_option() dispatcher for all 12 D-06 UCI toggles (Task 2).
//
// What this file owns this wave (Plan 03):
//   - Engine::new_game()
//   - Engine::search(fen, depth, time_ms)
//   - Engine::set_syzygy_path(path)   <- forwarder; real body is in syzygy_.set_path
//   - Engine::age_history()
//   - Engine::set_option(name, value) <- D-06 UCI toggle dispatcher
//
// What this file does NOT own:
//   - Engine::stop / Engine::nodes / Engine::tbhits — inline in engine.hpp
//   - The pybind11 m.def block — lives in python_bindings.cpp (plan 04 also
//     edits the m.def block this wave; this TU does not touch it)

#include "engine.hpp"
#include "magic.hpp"
#include "search.hpp"
#include "tt.hpp"
#include "types.hpp"

#include <algorithm>
#include <cctype>
#include <cstring>
#include <iostream>
#include <string>

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

    // D-03 Plan 03-01 Bug #2 fix — reset persistent history and counter_moves.
    // std::memset(0) on int arrays is well-defined (sets all bits to zero,
    // which equals integer 0). On Move arrays, MOVE_NONE == 0 (types.hpp),
    // so memset(0) correctly initializes all counter_moves to MOVE_NONE.
    // SearchStack PV/killers/excluded reset is a no-op here: the stack is
    // stack-owned (Engine member), and alpha_beta initializes pv_length[ply]=0
    // at every entry point before using pv[ply][*].
    std::memset(history_,      0, sizeof(history_));
    std::memset(counter_moves_, 0, sizeof(counter_moves_));
}

// age_history: decay history values by right-shifting each entry once per
// search call (Stockfish-style per-search aging, RESEARCH.md A11). This
// prevents old search scores from dominating future move ordering while
// preserving directional signal from recent cutoffs.
void Engine::age_history() {
    for (int s = 0; s < 2; ++s) {
        for (int from = 0; from < 64; ++from) {
            for (int to = 0; to < 64; ++to) {
                history_[s][from][to] >>= 1;  // D-03: aging — halve each entry
            }
        }
    }
}

SearchResult Engine::search(const std::string& fen, int depth, int time_ms) {
    init_magics();

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
    // SearchInfo wiring (Plan 03-01 D-01, D-03):
    //   - external_stop -> &stop_flag_     (FOUND-04, Python-side cancellation)
    //   - rep_stack     -> &rep_stack_     (SRCH-14, Engine-owned RepStack)
    //   - soft/hard deadlines from TimeManager (SRCH-15, ≥10% safety margin)
    //   - tt            -> &tt_            (D-01: replaces g_tt global reference)
    //   - search_stack  -> &search_stack_  (D-03 Bug #2+#3: triangular PV + killers)
    //   - history       -> &history_       (D-03 Bug #2: persistent history table)
    //   - counter_moves -> &counter_moves_ (Plan 03-02 counter-move heuristic)
    //   - options       -> &options_       (D-06: UCI toggle struct — Task 2)
    // -------------------------------------------------------------------------
    SearchInfo info;
    info.external_stop = &stop_flag_;
    info.rep_stack     = &rep_stack_;
    info.time_limit_ms = time_ms;

    // D-01: wire TT non-owning pointer — migrates g_tt global per PATTERNS.md Shared Pattern 4
    info.tt = &tt_;

    // D-03: wire persistent search state pointers
    info.search_stack  = &search_stack_;
    info.history       = &history_;         // int (*)[64][64] — pointer to history_[2]...
    info.counter_moves = &counter_moves_;   // Move (*)[64][64] — pointer to counter_moves_[2]...

    // D-06: wire options pointer (Task 2; consumed by Plans 03-02/03/04)
    info.options = &options_;

    // SRCH-15 — TimeManager allocates a per-move budget with the ≥10% safety
    // clamp. time_ms here is the entire remaining budget for this single
    // move; the upstream game manager / gauntlet owns longer-horizon
    // allocation. moves_to_go=1 makes the clamp the binding constraint.
    TimeManager tm = TimeManager::allocate(time_ms, /*increment_ms=*/0,
                                           /*moves_to_go=*/1);
    info.soft_deadline_ms = tm.soft_deadline_ms;
    info.hard_deadline_ms = tm.hard_deadline_ms;

    info.reset();   // sets start_time and propagates external_stop into stopped

    // D-03 Bug #1 fix: split info.depth = max_depth into two distinct fields.
    // info.max_depth = caller's upper bound (never overwritten by search loop).
    // info.depth = 0 = per-iteration counter (written by iterative_deepening).
    // Without this split, iterative_deepening's `info.depth = depth` loop line
    // silently overwrote the caller's max_depth cap — causing the engine to
    // keep searching past the intended ceiling (Phase 1 perf bug #1).
    int max_depth = std::min(std::max(depth, 1), MAX_PLY - 1);
    info.max_depth = max_depth;  // D-03 Bug #1 fix: new field; replaces `info.depth = max_depth`
    info.depth     = 0;          // reset iteration counter (iterative_deepening writes this)

    // Mark a new TT generation so the replacement strategy distinguishes
    // entries from this search from prior searches' leftovers.
    // D-01: call via info.tt (not g_tt) to validate the pointer contract.
    info.tt->new_search();

    // D-03 Bug #2: decay history heuristic before each search call (RESEARCH A11).
    // Aging runs AFTER reset() so history is not zeroed, and BEFORE
    // iterative_deepening so the first depth-1 iteration sees decayed values.
    age_history();

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
    r.time_ms   = full.time_ms;
    r.nps       = full.nps();
    return r;
}

// =============================================================================
// Engine::set_option — D-06 UCI toggle dispatcher
// =============================================================================
//
// Recognizes all 12 D-06 toggle names case-insensitively. On unknown name:
// emits "info string Unknown option: <name>" to stdout (matches the Phase 2
// uci_main.cpp:247-269 convention). On known name with malformed value:
// emits "info string Invalid value for <name>: <value>" and leaves options_
// unchanged. No exception is thrown — UCI protocol tolerates graceful ignore.

void Engine::set_option(const std::string& name, const std::string& value) {
    // Case-insensitive value interpretation: true/True/TRUE and false/False/FALSE
    auto ci_eq = [](const std::string& a, const char* b) -> bool {
        if (a.size() != std::strlen(b)) return false;
        for (size_t i = 0; i < a.size(); ++i) {
            if (std::tolower(static_cast<unsigned char>(a[i])) !=
                std::tolower(static_cast<unsigned char>(b[i]))) return false;
        }
        return true;
    };

    bool bool_val = false;
    bool is_true  = ci_eq(value, "true");
    bool is_false = ci_eq(value, "false");
    if (is_true)  { bool_val = true; }
    else if (is_false) { bool_val = false; }

    // Case-insensitive name mapping for all 12 D-06 toggles.
    auto name_eq = [&](const char* expected) -> bool {
        return ci_eq(name, expected);
    };

    if (name_eq("UseNullMove")) {
        if (!is_true && !is_false) {
            std::cout << "info string Invalid value for UseNullMove: " << value << std::endl;
            return;
        }
        options_.UseNullMove = bool_val;  // D-06
    } else if (name_eq("UseLMR")) {
        if (!is_true && !is_false) {
            std::cout << "info string Invalid value for UseLMR: " << value << std::endl;
            return;
        }
        options_.UseLMR = bool_val;  // D-06
    } else if (name_eq("UseRFP")) {
        if (!is_true && !is_false) {
            std::cout << "info string Invalid value for UseRFP: " << value << std::endl;
            return;
        }
        options_.UseRFP = bool_val;  // D-06
    } else if (name_eq("UseFutility")) {
        if (!is_true && !is_false) {
            std::cout << "info string Invalid value for UseFutility: " << value << std::endl;
            return;
        }
        options_.UseFutility = bool_val;  // D-06
    } else if (name_eq("UseLMP")) {
        if (!is_true && !is_false) {
            std::cout << "info string Invalid value for UseLMP: " << value << std::endl;
            return;
        }
        options_.UseLMP = bool_val;  // D-06
    } else if (name_eq("UseIIR")) {
        if (!is_true && !is_false) {
            std::cout << "info string Invalid value for UseIIR: " << value << std::endl;
            return;
        }
        options_.UseIIR = bool_val;  // D-06
    } else if (name_eq("UseCheckExt")) {
        if (!is_true && !is_false) {
            std::cout << "info string Invalid value for UseCheckExt: " << value << std::endl;
            return;
        }
        options_.UseCheckExt = bool_val;  // D-06
    } else if (name_eq("UseRecaptureExt")) {
        if (!is_true && !is_false) {
            std::cout << "info string Invalid value for UseRecaptureExt: " << value << std::endl;
            return;
        }
        options_.UseRecaptureExt = bool_val;  // D-06
    } else if (name_eq("UseSingular")) {
        if (!is_true && !is_false) {
            std::cout << "info string Invalid value for UseSingular: " << value << std::endl;
            return;
        }
        options_.UseSingular = bool_val;  // D-06
    } else if (name_eq("UseMultiCut")) {
        if (!is_true && !is_false) {
            std::cout << "info string Invalid value for UseMultiCut: " << value << std::endl;
            return;
        }
        options_.UseMultiCut = bool_val;  // D-06
    } else if (name_eq("UseProbCut")) {
        if (!is_true && !is_false) {
            std::cout << "info string Invalid value for UseProbCut: " << value << std::endl;
            return;
        }
        options_.UseProbCut = bool_val;  // D-06
    } else if (name_eq("UseFortressEval")) {
        if (!is_true && !is_false) {
            std::cout << "info string Invalid value for UseFortressEval: " << value << std::endl;
            return;
        }
        options_.UseFortressEval = bool_val;  // D-06 + D-11
    } else {
        // Unknown option — emit info string but do not throw (UCI convention)
        std::cout << "info string Unknown option: " << name << std::endl;
    }
}

} // namespace v7
