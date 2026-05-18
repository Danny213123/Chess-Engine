// V7 Lazy SMP ThreadPool implementation — Plan 04-01 (PAR-04, PAR-05, PAR-06).
//
// V7-original code: NOT a copy from Stockfish (GPL). Design pattern transcribed
// from public Stockfish ThreadPool architecture (cv-wake state machine) and
// adapted for V7's specific constraints:
//   - Each Worker owns value-typed search tables (Pitfall 1 mitigation).
//   - Workers share ONLY TT + stop_flag (PAR-05 literal; no other shared state).
//   - Berserk-style depth-stagger for helper divergence (PAR-06 / D-03).
//   - Cancellation poll at % 1024 nodes (tightened in search.cpp — Pitfall 10).
//   - SearchInfo per-worker wiring follows PATTERNS Shared Pattern 3 verbatim.
//
// std::thread construction failure (OS thread limit hit) propagates as
// std::system_error — V7 "fail loud on OS resource exhaustion" convention.
//
// GIL note: thread_pool.cpp never touches Python objects. The GIL is released
// by python_bindings.cpp at the Engine::search m.def site (FOUND-05 preserved).

#include "thread_pool.hpp"
#include "engine.hpp"      // for Engine type (not strictly needed — used for types only)
#include "search.hpp"      // SearchInfo, iterative_deepening, SearchResultFull
#include "tt.hpp"
#include "magic.hpp"       // init_magics() — called before board setup

#include <algorithm>
#include <cstring>
#include <mutex>
#include <condition_variable>

namespace v7 {

// =============================================================================
// wire_worker_info — build SearchInfo for worker w from its value-typed members
// =============================================================================
//
// PATTERNS Shared Pattern 3 (verbatim per-worker wiring discipline):
//   Shared pointers: tt, external_stop, options, syzygy (read-only during search)
//   Per-worker pointers: history, counter_moves, continuation_history,
//                        capture_history, search_stack, rep_stack (value-typed copies)
//
// After wiring all pointers, info.reset() is called — it preserves every
// non-owning pointer (search.hpp:208-212 contract: reset() does NOT clobber
// external_stop, soft/hard deadlines, rep_stack, max_depth, tt, search_stack,
// history, counter_moves, options, continuation_history, capture_history).

void ThreadPool::wire_worker_info(Worker& w, const SearchSpec& spec) {
    SearchInfo& info = w.info;

    // --- Shared state (PAR-05: the ONLY shared mutable state) ---
    info.external_stop       = w.shared_stop;    // Engine::stop_flag_
    info.tt                  = w.shared_tt;       // Engine::tt_ (lockless XOR TT)
    info.options             = w.shared_options;  // Engine::options_ (read-only)

    // --- Per-worker value-typed state (Pitfall 1 mitigation — never &engine.history_) ---
    info.history             = &w.history;               // int (*)[64][64] — worker's own table
    info.counter_moves       = &w.counter_moves;         // Move (*)[64][64]
    info.continuation_history = &w.continuation_history; // int (*)[6][64][2][6][64]
    info.capture_history     = &w.capture_history;       // int (*)[6][64][6]
    info.search_stack        = &w.search_stack;          // triangular PV + killers

    // Rep stack is per-worker (push/pop within tree; shared rep_stack is only
    // for the root seeding by Engine::search — workers get their own copy).
    // We give each worker its own rep_stack seeded with the root position from
    // the shared_rep_stack (seeded by Engine before calling start_search).
    w.rep_stack = *w.shared_rep_stack;  // copy root-seeded stack into worker's own
    info.rep_stack = &w.rep_stack;

    // --- worker_id for depth-stagger (PAR-06) ---
    info.worker_id  = w.worker_id;
    info.num_threads = static_cast<int>(threads_.size()) + 1;  // helpers + main

    // --- Time control ---
    // worker0_ (worker_id==0): receives the full TimeManager soft/hard deadlines
    //   so SRCH-15 gates work correctly (soft deadline prevents starting a new
    //   iteration the engine probably can't finish; hard deadline stops mid-iter).
    // Helper workers (worker_id>0): only poll via stop_flag_ (external_stop).
    //   They set time_limit_ms to the same wall-clock budget so check_time has
    //   a sensible fallback, but soft_deadline_ms=0 suppresses the iteration gate.
    info.time_limit_ms    = spec.time_ms;
    info.soft_deadline_ms = (w.worker_id == 0) ? spec.soft_deadline_ms : 0;
    info.hard_deadline_ms = (w.worker_id == 0) ? spec.hard_deadline_ms : 0;

    // --- Depth cap ---
    info.max_depth = spec.max_depth > 0 ? spec.max_depth : 64;
    info.depth     = 0;

    // reset() propagates external_stop → stopped, sets start_time, zeros nodes/seldepth/score
    info.reset();
}

// =============================================================================
// run_search_on_worker — calls iterative_deepening on w.board_copy
// =============================================================================

void ThreadPool::run_search_on_worker(Worker& w, const SearchSpec& spec) {
    // Set up the board from FEN
    init_magics();
    w.board_copy.from_fen(spec.fen);

    // Wire per-worker SearchInfo (do this fresh every search — shared_stop etc. may change)
    wire_worker_info(w, spec);

    // Run iterative deepening — result stored in w.result
    // verbose=false for all workers (UCI output is main-thread only)
    w.result = iterative_deepening(w.board_copy, w.info, /*verbose=*/false);
    w.nodes  = w.info.nodes.load(std::memory_order_relaxed);
}

// =============================================================================
// resize(n) — adjust helper count to n-1 helpers
// =============================================================================
//
// If growing: append new Worker + spawn std::thread(helper_loop, this, idx).
// If shrinking: set shutting_down_ + broadcast to stop excess helpers + join them.
// If same: no-op.
//
// std::system_error on thread spawn failure propagates (fail loud).

void ThreadPool::resize(int n) {
    // n = total Threads (including main); helpers = n - 1
    int target_helpers = std::max(0, n - 1);
    int current_helpers = static_cast<int>(threads_.size());

    if (target_helpers == current_helpers) return;

    if (target_helpers > current_helpers) {
        // Growing: add workers and spawn threads
        helper_gen_seen_.resize(target_helpers, generation_);
        for (int i = current_helpers; i < target_helpers; ++i) {
            workers_.emplace_back();
            workers_.back().worker_id = i + 1;  // main=0, helpers start at 1
            // IMPORTANT: capture by index into workers_, not by pointer —
            // push_back may reallocate the vector. Use the index to re-fetch.
            threads_.emplace_back([this, i]() { helper_loop(i); });
        }
    } else {
        // Shrinking: signal excess helpers to exit and join them
        {
            std::lock_guard<std::mutex> lk(mtx_);
            shutting_down_ = true;
        }
        cv_start_.notify_all();

        for (int i = target_helpers; i < current_helpers; ++i) {
            if (threads_[i].joinable()) {
                threads_[i].join();
            }
        }

        // Reset shutting_down_ (only excess threads were stopped)
        {
            std::lock_guard<std::mutex> lk(mtx_);
            shutting_down_ = false;
        }

        threads_.resize(target_helpers);
        workers_.resize(target_helpers);
        helper_gen_seen_.resize(target_helpers, generation_);
    }
}

// =============================================================================
// start_search(spec, worker0) — broadcast + run main inline
// =============================================================================
//
// Order of operations:
//   1. Store spec in current_spec_ (helpers read this after waking)
//   2. Increment generation_ + set active_count_ = n_helpers
//   3. Broadcast cv_start_ to wake all helpers
//   4. Run iterative_deepening on worker0 INLINE (main thread path)
//
// Note: main thread runs inline; helpers run concurrently. Both paths
// call run_search_on_worker which calls wire_worker_info fresh.

void ThreadPool::start_search(const SearchSpec& spec, Worker& worker0) {
    int n_helpers = static_cast<int>(threads_.size());

    {
        std::lock_guard<std::mutex> lk(mtx_);
        current_spec_ = spec;
        ++generation_;
        active_count_ = n_helpers;
    }

    if (n_helpers > 0) {
        cv_start_.notify_all();
    }

    // Main thread (worker0) runs its search inline.
    // worker0.worker_id == 0 so iterative_deepening will NOT apply depth-stagger.
    run_search_on_worker(worker0, spec);
}

// =============================================================================
// wait_for_all() — block until all helpers complete
// =============================================================================

void ThreadPool::wait_for_all() {
    std::unique_lock<std::mutex> lk(mtx_);
    cv_done_.wait(lk, [this] { return active_count_ == 0; });
}

// =============================================================================
// helper_loop(helper_idx) — the per-helper thread function
// =============================================================================
//
// State machine (V7-original, NOT a Stockfish code copy):
//   for(;;) {
//       unique_lock lk(mtx_);
//       cv_start_.wait(lk, [&]{ return helper_gen_seen_[i] < generation_ || shutting_down_; });
//       if (shutting_down_) return;
//       helper_gen_seen_[i] = generation_;
//       SearchSpec spec = current_spec_;
//       lk.unlock();
//
//       run_search_on_worker(workers_[i], spec);
//
//       { lock_guard l(mtx_); --active_count_; }
//       cv_done_.notify_one();
//   }

void ThreadPool::helper_loop(int helper_idx) {
    while (true) {
        SearchSpec spec;
        {
            std::unique_lock<std::mutex> lk(mtx_);
            cv_start_.wait(lk, [this, helper_idx] {
                return helper_gen_seen_[helper_idx] < generation_ || shutting_down_;
            });
            if (shutting_down_) return;
            helper_gen_seen_[helper_idx] = generation_;
            spec = current_spec_;
        }

        // Run the search. This helper applies depth-stagger because worker_id > 0.
        run_search_on_worker(workers_[helper_idx], spec);

        {
            std::lock_guard<std::mutex> lk(mtx_);
            --active_count_;
        }
        cv_done_.notify_one();
    }
}

// =============================================================================
// shutdown() — stop all helpers and join
// =============================================================================

void ThreadPool::shutdown() {
    {
        std::lock_guard<std::mutex> lk(mtx_);
        shutting_down_ = true;
    }
    cv_start_.notify_all();
    for (auto& t : threads_) {
        if (t.joinable()) t.join();
    }
    threads_.clear();
    workers_.clear();
    helper_gen_seen_.clear();
    // Don't reset shutting_down_ — shutdown is terminal.
}

} // namespace v7
