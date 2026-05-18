// V7 Lazy SMP thread pool — Plan 04-01 (PAR-04, PAR-05, PAR-06).
//
// Provides:
//   struct Worker     — per-thread search state (value-typed copies of all
//                       heuristic tables so workers NEVER alias each other —
//                       Pitfall 1 mitigation per CONTEXT D-02 / RESEARCH §1).
//   class ThreadPool  — persistent cv-wake pool; workers park on cv_start_ and
//                       are broadcast by start_search(); design is V7-original
//                       (NOT a code copy from Stockfish/GPL — design-only reference
//                       per CONTEXT D-01, PATTERNS.md Shared Pattern for thread_pool).
//
// Ownership discipline (PAR-05 literal):
//   Workers communicate ONLY via the shared TT (Engine::tt_) and the shared
//   atomic stop_flag_ (Engine::stop_flag_). All other mutable state in Worker
//   is value-typed per-thread local data — no aliasing, no data races.
//
// Forward declarations avoid circular include with engine.hpp.
//
// Plan 04-01 D-01/D-02/D-03: ThreadPool + Worker are the sole new files in
// this plan. CMakeLists.txt adds src/thread_pool.cpp to V7_SOURCES (sub-step f).

#pragma once

#include "board.hpp"       // Board — per-worker board copy
#include "search.hpp"      // RepStack, SearchStack, SearchInfo, MAX_PLY
#include "types.hpp"       // Move, MOVE_NONE
#include "tt.hpp"          // TT (forward decl is enough for pointer members)
#include "search/options.hpp"  // EngineOptions (pointer member)

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <thread>
#include <vector>

namespace v7 {

// Forward declarations to avoid pulling engine.hpp (circular)
class Engine;
struct SyzygyState;

// =============================================================================
// SearchSpec — lightweight POD describing one search request.
// =============================================================================
//
// Passed from Engine::search to ThreadPool::start_search; carried into each
// worker's helper_loop iteration. All fields are read-only during the search.

struct SearchSpec {
    std::string fen;
    int         depth    = 64;
    int         time_ms  = 5000;
    int         max_depth = 0;   // Engine::search's computed cap (MIN(depth, MAX_PLY-1))
    int         soft_deadline_ms = 0;  // SRCH-15: main-thread soft deadline (helpers use 0)
    int         hard_deadline_ms = 0;  // SRCH-15: main-thread hard deadline (helpers use time_ms)
};

// =============================================================================
// Worker — per-thread search state (PAR-04/05, CONTEXT D-02)
// =============================================================================
//
// Design rules (RESEARCH Code Example §1 verbatim):
//   - All per-thread heuristic tables are VALUE-TYPED members, NOT references
//     (Pitfall 1 — worker tables silently shared via reference).
//   - Shared state is held as raw NON-OWNING pointers (Worker does NOT own).
//   - SearchInfo `info` is built per-worker in ThreadPool::start_search and
//     points into the value-typed members here (Shared Pattern 3).
//
// Memory footprint per worker:
//   board_copy  : ~several KB (Board internals)
//   rep_stack   : 1024 * 8 bytes = 8 KB
//   search_stack: ~34 KB (SearchStack)
//   history     : 2*64*64*4 = 32 KB
//   counter_moves: 2*64*64*2 = 16 KB
//   continuation_history: 2*6*64*2*6*64*4 ≈ 2.3 MB  (dominant)
//   capture_history: 2*6*64*6*4 ≈ 18 KB
// Total ≈ 2.4 MB per worker — acceptable for default Threads <= 8.

struct Worker {
    // -------------------------------------------------------------------------
    // Per-thread search state — VALUE-TYPED COPIES, NOT references (Pitfall 1)
    // -------------------------------------------------------------------------
    Board       board_copy;
    RepStack    rep_stack;
    SearchStack search_stack;

    // History heuristic [side][from][to]
    int  history[2][64][64] = {};

    // Counter-move heuristic [side_that_moved][from][to]
    Move counter_moves[2][64][64] = {};

    // Continuation history [stm][prev_piece][prev_to][stm_now][curr_piece][curr_to]
    // ~2.3 MB per worker — value-typed copy, NEVER a reference to Engine's table
    int  continuation_history[2][6][64][2][6][64] = {};

    // Capture history [stm][piece][to][captured] — ~18 KB per worker
    int  capture_history[2][6][64][6] = {};

    // SearchInfo for this worker — built by ThreadPool::start_search each search call.
    // Pointers inside info point to: value-typed members above (per-thread tables)
    // AND shared Engine state (tt, stop_flag, options, syzygy) per PAR-05.
    SearchInfo info;

    // Per-worker node counter (separate from shared nodes_ atomic on Engine to
    // avoid false-sharing). Summed by Engine::search after wait_for_all().
    uint64_t nodes = 0;

    // Worker ID: 0 = main thread (worker0_); 1..N-1 = helpers.
    int worker_id = 0;

    // SearchResult for this worker — set by the search function at the end of
    // iterative_deepening. Engine::search returns worker0_'s result (canonical
    // pick for Lazy SMP per CONTEXT D-01 / RESEARCH Open Question 3 RESOLVED).
    SearchResultFull result;

    // -------------------------------------------------------------------------
    // Shared state — raw NON-OWNING pointers (Worker does NOT own these)
    // -------------------------------------------------------------------------
    TT*                  shared_tt      = nullptr;  // Engine::tt_
    std::atomic<bool>*   shared_stop    = nullptr;  // Engine::stop_flag_
    const EngineOptions* shared_options = nullptr;  // Engine::options_
    SyzygyState*         shared_syzygy  = nullptr;  // Engine::syzygy_
    RepStack*            shared_rep_stack = nullptr; // Engine::rep_stack_ (root seeding)
};

// =============================================================================
// ThreadPool — persistent cv-wake pool (CONTEXT D-01, RESEARCH Pattern 1)
// =============================================================================
//
// Architecture (V7-original, NOT a Stockfish code copy):
//   - workers_    : vector of Worker values (one per helper; worker0_ stays on Engine)
//   - threads_    : std::thread handles for helpers (matches workers_ 1-to-1)
//   - generation_ : monotone counter; incremented by start_search; helpers wake
//                   when their seen generation lags behind generation_
//   - active_count_: helper threads currently executing; decremented on finish;
//                   Engine::wait_for_all() waits for active_count_ == 0
//   - shutting_down_: set by shutdown(); helpers check and exit their loop
//
// Thread count:
//   n = Threads (from EngineOptions) = total workers including main.
//   helpers spawned = n - 1.
//   worker0_ (on Engine) is the main thread's Worker — always exists.
//
// cv semantics:
//   cv_start_: helpers sleep on this; start_search() broadcasts to wake all
//   cv_done_:  engine main sleeps on this in wait_for_all(); helpers notify_one
//              when they finish each search

class ThreadPool {
public:
    // -------------------------------------------------------------------------
    // resize(n): adjust helper count to n-1 (main thread = worker0_).
    //   If growing: append new Workers + spawn std::thread(helper_loop, ...).
    //   If shrinking: set shutting_down temporarily for excess threads only.
    //   Called by Engine::set_option("Threads", ...).
    // -------------------------------------------------------------------------
    void resize(int n);

    // -------------------------------------------------------------------------
    // start_search(spec, worker0):
    //   Sets the search spec; increments generation_; broadcasts cv_start_;
    //   wires per-worker SearchInfo from Worker's value-typed members + shared
    //   engine pointers; runs the search on worker0 inline (main thread).
    //   Call wait_for_all() after this to synchronize helpers.
    // -------------------------------------------------------------------------
    void start_search(const SearchSpec& spec, Worker& worker0);

    // -------------------------------------------------------------------------
    // wait_for_all(): blocks until all helper threads have finished the current
    //   search iteration (active_count_ == 0). Called from Engine::search.
    // -------------------------------------------------------------------------
    void wait_for_all();

    // -------------------------------------------------------------------------
    // shutdown(): sets shutting_down_, broadcasts cv_start_, joins all threads.
    //   Called from ~ThreadPool() and resize() when shrinking.
    // -------------------------------------------------------------------------
    void shutdown();

    // -------------------------------------------------------------------------
    // worker_count(): number of helper workers (total threads = workers_.size()+1)
    // -------------------------------------------------------------------------
    int worker_count() const { return static_cast<int>(workers_.size()); }

    // -------------------------------------------------------------------------
    // get_worker(i): access helper Worker by index. Called by Engine::new_game()
    //   to zero helper tables between games. Index in [0, worker_count()-1].
    // -------------------------------------------------------------------------
    Worker& get_worker(int i) { return workers_[i]; }

    // Destructor ensures clean shutdown
    ~ThreadPool() { shutdown(); }

    // Non-copyable, non-movable (contains std::thread)
    ThreadPool() = default;
    ThreadPool(const ThreadPool&) = delete;
    ThreadPool& operator=(const ThreadPool&) = delete;

private:
    // -------------------------------------------------------------------------
    // helper_loop: the per-helper thread function.
    //   for(;;) { park on cv_start_; if shutdown break; run_search; --active; notify cv_done_; }
    // -------------------------------------------------------------------------
    void helper_loop(int helper_idx);

    // -------------------------------------------------------------------------
    // wire_worker_info: builds SearchInfo for a worker from its value-typed
    //   members + the shared engine pointers stored in the Worker itself.
    //   Called for each worker before search begins (per Shared Pattern 3).
    // -------------------------------------------------------------------------
    void wire_worker_info(Worker& w, const SearchSpec& spec);

    // -------------------------------------------------------------------------
    // run_search_on_worker: calls iterative_deepening on the worker's board_copy
    //   using the wired info. Stores result in w.result.
    // -------------------------------------------------------------------------
    void run_search_on_worker(Worker& w, const SearchSpec& spec);

    // --- shared pool state (protected by mtx_) ---
    std::mutex              mtx_;
    std::condition_variable cv_start_;   // helpers sleep here between searches
    std::condition_variable cv_done_;    // main sleeps here in wait_for_all

    // Generation counter — incremented by start_search; helpers compare to their
    // per-helper seen generation to detect new work.
    uint64_t                generation_   = 0;
    int                     active_count_ = 0;   // helpers currently running
    bool                    shutting_down_ = false;

    // Per-helper seen-generation tracker (indexed by helper_idx)
    std::vector<uint64_t>   helper_gen_seen_;

    // Workers (index = helper_idx 0..N-2) and their std::thread handles
    std::vector<Worker>     workers_;
    std::vector<std::thread> threads_;

    // Current search spec (set by start_search, read by helper_loop)
    SearchSpec              current_spec_;
};

} // namespace v7
