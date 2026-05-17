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
// Build-order note: `#include "syzygy.hpp"` resolves at compile time because
// plan 05 lands include/syzygy.hpp in the same Wave 3; if plan 05's file is
// missing when this header compiles, the build fails fast — the correct
// failure mode (loud, not silent).

#pragma once

#include "board.hpp"
#include "search.hpp"         // for v7::RepStack, v7::SearchStack, v7::SearchInfo (Plan 03)
#include "syzygy.hpp"         // for v7::SyzygyState (Plan 05 sibling — same wave)
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
    // AND zeros history/counter_moves (Plan 03-01 D-03). Body in src/engine.cpp.
    void new_game();

    // search: real iterative-deepening body. Body lives in src/engine.cpp.
    SearchResult search(const std::string& fen, int depth, int time_ms);

    // set_option: D-06 UCI toggle dispatcher — recognizes all 12 D-06 names.
    // Unknown names emit "info string Unknown option: <name>"; no throw.
    // Body lives in src/engine.cpp (Task 2).
    void set_option(const std::string& name, const std::string& value);

    // stop: flips the atomic stop flag. Fast — the binding does NOT release
    // the GIL on this method (intentional; see python_bindings.cpp comment).
    void stop() { stop_flag_.store(true, std::memory_order_relaxed); }

    // tbhits: forwarded to syzygy_.tbhits() (Plan 05 increments inside
    // probe_wdl / probe_root_dtz). Inline for performance (read path).
    uint64_t tbhits() const { return syzygy_.tbhits(); }

    uint64_t nodes() const { return nodes_.load(std::memory_order_relaxed); }

private:
    std::atomic<bool>     stop_flag_{false};
    std::atomic<uint64_t> nodes_{0};

    TT          tt_{64};           // 64MB transposition table (matches V6 default)
    Board       board_;            // single working board; reset per search via from_fen
    RepStack    rep_stack_;        // Plan 03 — Engine-owned repetition stack (NOT on Board;
                                   // perft-clean invariant per checker issue #3)
    SyzygyState syzygy_;           // Plan 05 — Syzygy tablebase state owned here so the
                                   // include/engine.hpp file has exactly one Wave-3 owner

    // D-03 Plan 03-01 additions — persistent search state:
    SearchStack search_stack_;     // Triangular PV + per-ply killers + excluded_move
                                   // (Bug #2 + Bug #3 fix; zero-initialized by default ctor)
    int  history_[2][64][64] = {}; // History heuristic [side][from][to] (D-03 Bug #2)
                                   // Halved by age_history() before each search call (RESEARCH A11)
    Move counter_moves_[2][64][64] = {};  // Counter-move heuristic [side_that_moved][from][to]
                                          // Consumed by Plan 03-02; zero = MOVE_NONE per types.hpp

    // D-06 Plan 03-01 Task 2 — UCI option toggles (12 refinement gates)
    EngineOptions options_;        // Defaults: all Tier-1/2 ON, UseFortressEval OFF (D-11)

    // age_history: decay history by right-shift-1 before each iterative_deepening
    // call (Stockfish-style per-search aging, RESEARCH.md A11). Called from Engine::search.
    void age_history();
};

// Free-function perft entry: defined in src/perft.cpp (Plan 02 lands the
// real body backed by the ported movegen).
uint64_t perft_entry(const std::string& fen, int depth);

} // namespace v7
