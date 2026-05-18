// V7 Engine class header.
//
// Plan 01 shipped this with stubs and forward-declared TT/Board/SyzygyState
// opaques. Plan 02 wired the real Board and TT members. Plan 03 (THIS plan
// — Wave 3 sole owner of include/engine.hpp) adds rep_stack_ (Engine-owned
// per checker issue #3 — Board stays perft-clean) AND declares syzygy_ so
// plan 05's SyzygyState type lands inside Engine in the SAME edit (Wave 3
// file-ownership invariant; plan 05 does NOT touch this file).
//
// Plan 03-01 additions (D-01, D-03):
//   - SearchStack search_stack_  — triangular PV + per-ply killers/excluded
//     (Bug #3 and Bug #2 fix; owned here so alpha_beta accesses via info.search_stack)
//   - int history_[2][64][64]    — persistent history heuristic (D-03 Bug #2 fix)
//   - Move counter_moves_[2][64][64] — counter-move heuristic (Plan 03-02 consumes)
//   - EngineOptions options_     — D-06 UCI toggles (Task 2 wires; Plan 03-02 reads)
//   - void age_history()         — right-shift history by 1 per search call (RESEARCH A11)
//   - void set_option(name,value)— D-06 dispatcher (Task 2 implements)
//
// Plan 04-01 additions (D-01, D-02, D-04) — Lazy SMP:
//   - ThreadPool pool_  — persistent cv-wake pool of N-1 helper threads (D-01)
//   - Worker worker0_   — main thread's own Worker (holds the per-thread tables
//     that were previously direct Engine members: history_, counter_moves_,
//     continuation_history_, capture_history_, search_stack_; board_ and rep_stack_
//     also now live in worker0_ for consistency; see thread_pool.hpp for Worker layout)
//   - board_ and rep_stack_ remain as direct Engine members for root-seeding
//     (rep_stack_ is pushed by Engine::search before pool_.start_search so each
//     worker.rep_stack is initialized with the root hash)
//   - int thread_count() const — test-only accessor returning options_.Threads
//   - peek_* accessors route through worker0_ (minimum-blast-radius refactor
//     so test_v7_history.py keeps passing without edits)
//
// Build-order note: `#include "syzygy.hpp"` resolves at compile time because
// plan 05 lands include/syzygy.hpp in the same Wave 3; if plan 05's file is
// missing when this header compiles, the build fails fast — the correct
// failure mode (loud, not silent).

#pragma once

#include "board.hpp"
#include "search.hpp"         // for v7::RepStack, v7::SearchStack, v7::SearchInfo (Plan 03)
#include "syzygy.hpp"         // for v7::SyzygyState (Plan 05 sibling — same wave)
#include "thread_pool.hpp"    // Plan 04-01: ThreadPool + Worker struct
#include "tt.hpp"
#include "types.hpp"
#include "search/options.hpp" // D-06: EngineOptions with 12 UCI toggles (Plan 03-01 Task 2)

#include <atomic>
#include <cstdint>
#include <string>

namespace v7 {

// MOVE_NONE is now provided by types.hpp (real v7::Move type). Plan 01's
// placeholder `constexpr int MOVE_NONE = 0;` was removed here; the typed
// version from types.hpp covers the same value (uint16_t 0).

// Minimal SearchResult struct exposed via pybind11 (read-only properties).
// The full v7::SearchResultFull lives in search.hpp; this struct is the
// trimmed Python-facing view.
struct SearchResult {
    Move best_move = MOVE_NONE;  // real v7::Move (uint16_t) from types.hpp
    int score = 0;
    int depth = 0;
    uint64_t nodes = 0;
    int time_ms = 0;
    int nps = 0;
};

class Engine {
public:
    Engine() = default;

    // set_syzygy_path: forwards to syzygy_.set_path() (Plan 05 implements the
    // D-08 verbatim log strings + filesystem checks + KRk smoke probe). Body
    // lives in src/engine.cpp.
    void set_syzygy_path(const std::string& path);

    // new_game: resets atomics, clears the TT, clears the repetition stack,
    // AND zeros history/counter_moves (Plan 03-01 D-03).
    // Plan 04-01: also zeros per-worker tables in worker0_ (and any helpers).
    // Body in src/engine.cpp.
    void new_game();

    // search: real iterative-deepening body. Body lives in src/engine.cpp.
    // Plan 04-01: internally drives ThreadPool + returns worker0_ result.
    // Signature unchanged (RESEARCH Open Question 3 RESOLVED).
    SearchResult search(const std::string& fen, int depth, int time_ms);

    // set_option: D-06 UCI toggle dispatcher — recognizes all 12 D-06 names
    // plus the Plan 04-01 D-04 "Threads" option (clamped to [1, 256]).
    // Unknown names emit "info string Unknown option: <name>"; no throw.
    // Body lives in src/engine.cpp.
    void set_option(const std::string& name, const std::string& value);

    // stop: flips the atomic stop flag. Fast — the binding does NOT release
    // the GIL on this method (intentional; see python_bindings.cpp comment).
    void stop() { stop_flag_.store(true, std::memory_order_relaxed); }

    // tbhits: forwarded to syzygy_.tbhits() (Plan 05 increments inside
    // probe_wdl / probe_root_dtz). Inline for performance (read path).
    uint64_t tbhits() const { return syzygy_.tbhits(); }

    uint64_t nodes() const { return nodes_.load(std::memory_order_relaxed); }

    // ------------------------------------------------------------------
    // Plan 04-01 D-04 — test-only accessor for Threads option.
    // Returns options_.Threads. Used by tests/test_v7_lazy_smp.py and
    // tests/test_v7_uci_threads.py to verify the Threads UCI option
    // without inspecting private members.
    // ------------------------------------------------------------------
    int thread_count() const { return options_.Threads; }

    // ------------------------------------------------------------------
    // Plan 03-05 — test-only TT introspection surface (PAR-01/02).
    // ------------------------------------------------------------------
    // Exposed for tests/test_v7_tt_lockless.py so the lockless XOR/replacement
    // contract can be exercised end-to-end via the Python binding without a
    // C++ test runner. NOT part of the production search API; never called
    // by alpha_beta. Public so &v7::Engine::tt_* pointer-to-member works.

    // tt_probe(hash) → dict-like tuple (hit, best_move, score, depth, flag, age)
    //   On miss returns (false, 0, 0, 0, 0, 0).
    struct TTProbeResult {
        bool hit;
        int best_move;
        int score;
        int depth;
        int flag;
        int age;
    };
    TTProbeResult tt_probe(uint64_t hash);
    void          tt_store(uint64_t hash, int best_move, int score, int depth, int flag);
    void          tt_clear();
    void          tt_new_search();
    uint64_t      tt_num_entries() const { return tt_.num_entries(); }
    uint64_t      tt_hits()        const { return tt_.hits(); }
    uint64_t      tt_misses()      const { return tt_.misses(); }

private:
    // -------------------------------------------------------------------------
    // Shared state (PAR-05 literal: the ONLY state accessible from all workers)
    // -------------------------------------------------------------------------
    std::atomic<bool>     stop_flag_{false};
    std::atomic<uint64_t> nodes_{0};

    TT          tt_{64};           // 64MB lockless XOR TT (Plan 03-05; shared by all workers)
    RepStack    rep_stack_;        // Engine-owned root rep stack — seeded before each search;
                                   // each worker gets its own copy in Worker::rep_stack
    SyzygyState syzygy_;           // Plan 05 — Syzygy tablebase state (shared, read-only during search)

    // -------------------------------------------------------------------------
    // Plan 04-01: ThreadPool + main-thread Worker
    //
    // worker0_  = main thread's Worker — holds the per-thread search tables that
    //   were previously direct Engine members (history_, counter_moves_, etc.).
    //   worker0_.worker_id = 0 (never applies depth-stagger).
    //
    // pool_     = helper thread pool (N-1 helpers for Threads=N).
    //   pool_.workers_ and pool_.threads_ are the helper Workers and threads.
    //
    // The table fields PREVIOUSLY on Engine (history_[2][64][64], etc.) are
    // now IN worker0_ as worker0_.history, worker0_.counter_moves, etc.
    // The peek_* accessors below route through worker0_ for test compatibility.
    // -------------------------------------------------------------------------
    Worker      worker0_;          // Main thread's per-thread state
    ThreadPool  pool_;             // Helper thread pool (empty at Threads=1)

    // -------------------------------------------------------------------------
    // D-06 Plan 03-01 Task 2 — UCI option toggles (12 refinement gates)
    // Plan 04-01 D-04: adds Threads field to EngineOptions.
    // -------------------------------------------------------------------------
    EngineOptions options_;        // Defaults: all Tier-1/2 ON, UseFortressEval OFF, Threads=1

    // age_history: decay history by right-shift-1 before each iterative_deepening
    // call (Stockfish-style per-search aging, RESEARCH.md A11). Called from Engine::search.
    // Plan 04-01: ages worker0_ tables (helpers have fresh-zeroed tables per search).
    void age_history();

    // -------------------------------------------------------------------------
    // peek_* test-only accessors — re-routed through worker0_ (Plan 04-01)
    // so test_v7_history.py keeps passing without edits.
    // Minimum-blast-radius refactor: only the routing target changes.
    // -------------------------------------------------------------------------

    // peek_history: test-only accessor for the main history table.
    // Returns worker0_.history[side][from][to].
    int peek_history(int side, int from, int to) const {
        return worker0_.history[side][from][to];  // was: history_[side][from][to]
    }

    // peek_continuation_history: test-only accessor.
    int peek_continuation_history(int stm, int prev_piece, int prev_to,
                                  int stm_now, int curr_piece, int curr_to) const {
        return worker0_.continuation_history[stm][prev_piece][prev_to][stm_now][curr_piece][curr_to];
    }

    // peek_capture_history: test-only accessor.
    int peek_capture_history(int stm, int piece, int to, int captured) const {
        return worker0_.capture_history[stm][piece][to][captured];
    }
};

// Free-function perft entry: defined in src/perft.cpp (Plan 02 lands the
// real body backed by the ported movegen).
uint64_t perft_entry(const std::string& fen, int depth);

} // namespace v7
