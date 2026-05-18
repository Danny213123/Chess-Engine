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

    // Plan 04-01 D-03 — zero per-thread tables in worker0_ and all pool workers.
    //
    // Pre-04-01 code memset'd Engine-owned history_/counter_moves_/etc. directly.
    // Those fields have moved into Worker (value-typed copies, Pitfall 1 mitigation).
    // new_game() now iterates over worker0_ (main thread) and all pool helpers.
    //
    // std::memset(0) on int arrays is well-defined. Move (uint16_t) MOVE_NONE == 0,
    // so memset(0) correctly initializes counter_moves to MOVE_NONE.
    auto zero_worker = [](Worker& w) {
        std::memset(w.history,              0, sizeof(w.history));
        std::memset(w.counter_moves,        0, sizeof(w.counter_moves));
        std::memset(w.continuation_history, 0, sizeof(w.continuation_history));
        std::memset(w.capture_history,      0, sizeof(w.capture_history));
    };

    // Zero main-thread worker
    zero_worker(worker0_);

    // Zero each helper worker in the pool
    for (int i = 0; i < pool_.worker_count(); ++i) {
        zero_worker(pool_.get_worker(i));
    }
}

// age_history: decay history values by right-shifting each entry once per
// search call (Stockfish-style per-search aging, RESEARCH.md A11). This
// prevents old search scores from dominating future move ordering while
// preserving directional signal from recent cutoffs.
// Plan 03-03: also ages continuation_history and capture_history.
// Plan 04-01: ages worker0_ tables only. Helper workers start each search
//             with fresh-zeroed tables (wired in thread_pool.cpp::wire_worker_info)
//             so their decay is implicit (they start from zero each search).
void Engine::age_history() {
    // Main history: worker0_.history[side][from][to]
    for (int s = 0; s < 2; ++s) {
        for (int from = 0; from < 64; ++from) {
            for (int to = 0; to < 64; ++to) {
                worker0_.history[s][from][to] >>= 1;  // D-03: aging — halve each entry
            }
        }
    }

    // Plan 03-03 SRCH-07: age continuation history [stm][prev_piece][prev_to][stm_now][piece][to]
    for (int stm = 0; stm < 2; ++stm) {
        for (int pp = 0; pp < 6; ++pp) {
            for (int pt = 0; pt < 64; ++pt) {
                for (int stm2 = 0; stm2 < 2; ++stm2) {
                    for (int cp = 0; cp < 6; ++cp) {
                        for (int ct = 0; ct < 64; ++ct) {
                            worker0_.continuation_history[stm][pp][pt][stm2][cp][ct] >>= 1;
                        }
                    }
                }
            }
        }
    }

    // Plan 03-03 SRCH-07: age capture history [stm][piece][to][captured]
    for (int stm = 0; stm < 2; ++stm) {
        for (int piece = 0; piece < 6; ++piece) {
            for (int to = 0; to < 64; ++to) {
                for (int cap = 0; cap < 6; ++cap) {
                    worker0_.capture_history[stm][piece][to][cap] >>= 1;
                }
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
    // *before* the per-worker SearchInfo::reset() calls so external_stop
    // propagation reads the fresh `false`.
    // -------------------------------------------------------------------------
    stop_flag_.store(false, std::memory_order_relaxed);

    // SRCH-14 — seed the ENGINE-OWNED rep_stack_ with the root position.
    // Each worker receives a COPY of this stack (see thread_pool.cpp
    // wire_worker_info: `w.rep_stack = *w.shared_rep_stack`). This way the
    // main rep_stack_ is the seeding source; worker push/pop is local.
    rep_stack_.clear();
    {
        Board root_board;
        root_board.from_fen(fen);
        rep_stack_.push(root_board.hash);
    }

    // D-03 Bug #1 fix: compute iteration cap once.
    int max_depth = std::min(std::max(depth, 1), MAX_PLY - 1);

    // SRCH-15 — TimeManager allocates a per-move budget with the ≥10% safety
    // clamp. time_ms here is the entire remaining budget for this single move.
    TimeManager tm = TimeManager::allocate(time_ms, /*increment_ms=*/0,
                                           /*moves_to_go=*/1);

    // Mark a new TT generation so the replacement strategy distinguishes
    // entries from this search from prior searches' leftovers.
    tt_.new_search();

    // D-03 Bug #2: decay history heuristic before each search call (RESEARCH A11).
    // Aging runs BEFORE distributing work so the first depth-1 iteration sees
    // decayed values. Only worker0_ tables are aged — helpers start fresh each search.
    age_history();

    // -------------------------------------------------------------------------
    // Plan 04-01 D-01: Wire worker0_ shared pointers (done ONCE per search
    // call; thread_pool.cpp wire_worker_info does the same for helper workers).
    //
    // Shared state (PAR-05 literal — the ONLY state accessible from all workers):
    //   external_stop -> &stop_flag_     (FOUND-04, Python-side cancellation)
    //   tt            -> &tt_            (D-01: lockless Hyatt-Mann TT)
    //   options       -> &options_       (D-06: UCI toggle struct, read-only during search)
    //   shared_syzygy -> &syzygy_        (Plan 05: read-only during search)
    //   shared_rep_stack -> &rep_stack_  (seeded above; workers copy this before search)
    //
    // Per-worker state (value-typed in Worker — Pitfall 1 mitigation):
    //   history, counter_moves, continuation_history, capture_history, search_stack
    //   (wire_worker_info sets these from the Worker's own value-typed arrays)
    // -------------------------------------------------------------------------
    worker0_.shared_tt        = &tt_;
    worker0_.shared_stop      = &stop_flag_;
    worker0_.shared_options   = &options_;
    worker0_.shared_syzygy    = &syzygy_;
    worker0_.shared_rep_stack = &rep_stack_;
    worker0_.worker_id        = 0;  // main thread — no depth-stagger

    // Wire helper workers' shared pointers before broadcasting the search.
    for (int i = 0; i < pool_.worker_count(); ++i) {
        Worker& hw = pool_.get_worker(i);
        hw.shared_tt        = &tt_;
        hw.shared_stop      = &stop_flag_;
        hw.shared_options   = &options_;
        hw.shared_syzygy    = &syzygy_;
        hw.shared_rep_stack = &rep_stack_;
        hw.worker_id        = i + 1;  // helpers: 1..N-1
    }

    // Build the SearchSpec POD passed to ThreadPool.
    SearchSpec spec;
    spec.fen              = fen;
    spec.depth            = depth;
    spec.time_ms          = time_ms;
    spec.max_depth        = max_depth;
    spec.soft_deadline_ms = tm.soft_deadline_ms;  // SRCH-15: iteration gate for worker0_
    spec.hard_deadline_ms = tm.hard_deadline_ms;  // SRCH-15: mid-iter cutoff for worker0_

    // Kick off helpers AND run worker0_ inline (ThreadPool::start_search).
    // This blocks until worker0_ finishes (iterative_deepening returns).
    // Helpers run concurrently; main thread is worker0_.
    pool_.start_search(spec, worker0_);

    // After main thread finishes, wait for all helpers to complete.
    pool_.wait_for_all();

    // Pop the root hash we seeded above. Symmetry with the push keeps
    // rep_stack_.top stable across repeated search() calls on the same Engine.
    rep_stack_.pop();

    // Sum node counts from all workers (worker0_ nodes + helpers).
    uint64_t total_nodes = worker0_.info.nodes.load(std::memory_order_relaxed);
    for (int i = 0; i < pool_.worker_count(); ++i) {
        total_nodes += pool_.get_worker(i).info.nodes.load(std::memory_order_relaxed);
    }

    // Mirror the per-search node count into the Engine atomic so Python-side
    // `Engine.nodes()` reflects the work done by the most-recent search.
    nodes_.store(total_nodes, std::memory_order_relaxed);

    // Canonical result: worker0_'s result (main thread).
    // Standard Lazy SMP pick: main thread explored the most deeply (no stagger);
    // helpers only seeded the TT for the next iteration (RESEARCH Open Question 3 RESOLVED).
    SearchResultFull& full = worker0_.result;
    full.nodes = total_nodes;  // Update node count to reflect total across all workers

    SearchResult r;
    r.best_move = full.best_move;
    r.score     = full.score;
    r.depth     = full.depth;
    r.nodes     = total_nodes;
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
    } else if (name_eq("Threads")) {
        // Plan 04-01 D-04 — Lazy SMP thread count.
        // Parse as int; reject non-integer and out-of-range values with info string.
        // Accepted range: [1, 256] per CONTEXT D-04 + T-04-01 threat mitigation.
        int n = 0;
        try {
            n = std::stoi(value);
        } catch (const std::exception&) {
            std::cout << "info string Invalid value for Threads: " << value << std::endl;
            return;
        }
        if (n < 1 || n > 256) {
            std::cout << "info string Threads out of range [1,256]: " << value << std::endl;
            return;
        }
        options_.Threads = n;
        pool_.resize(n);
    } else {
        // Unknown option — emit info string but do not throw (UCI convention)
        std::cout << "info string Unknown option: " << name << std::endl;
    }
}

// =============================================================================
// Plan 03-05 — test-only TT introspection surface (PAR-01 / PAR-02).
// =============================================================================
//
// Thin pass-through wrappers around Engine::tt_ so the lockless TT can be
// exercised end-to-end via the pybind11 module (tests/test_v7_tt_lockless.py).
// NOT used by alpha_beta — production search continues to call info.tt->probe
// / info.tt->store directly per the Plan 03-01 D-01 wiring contract.

Engine::TTProbeResult Engine::tt_probe(uint64_t hash) {
    TTEntry entry{};
    bool hit = tt_.probe(hash, entry);
    return TTProbeResult{
        hit,
        int(entry.best_move),
        int(entry.score),
        int(entry.depth),
        int(entry.flag),
        int(entry.age),
    };
}

void Engine::tt_store(uint64_t hash, int best_move, int score, int depth, int flag) {
    tt_.store(hash,
              static_cast<Move>(best_move & 0xFFFF),
              score,
              depth,
              static_cast<TTFlag>(flag & 0xFF));
}

void Engine::tt_clear()      { tt_.clear(); }
void Engine::tt_new_search() { tt_.new_search(); }

} // namespace v7
