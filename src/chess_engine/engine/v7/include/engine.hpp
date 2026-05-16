// V7 Engine class header.
//
// Plan 01 ships stub bodies that compile and load cleanly so the pybind11
// binding contract can be locked from day one (FOUND-04 / FOUND-05). Plans
// 02/03/05 fill in the real Board / TT / Search / Syzygy state behind the
// same public surface — callers should never need to be modified.

#pragma once

#include <atomic>
#include <cstdint>
#include <string>

namespace v7 {

// MOVE_NONE: plan 01 placeholder. Plan 02 replaces with the real Move type.
constexpr int MOVE_NONE = 0;

// Forward declarations of types that land in later plans. Declaring them
// opaque here keeps engine.hpp from pulling in the full subsystem headers
// (which don't exist yet) while letting the Engine class hold them by
// reference / pointer once plans 02 / 05 land.
class TT;
class Board;
struct SyzygyState;

// Minimal SearchResult struct. Plan 03 expands with PV vector, full search
// stats, and a proper Move type for best_move. The Python binding exposes
// these as read-only properties so chess_algorithm.py can read them.
struct SearchResult {
    int best_move = MOVE_NONE;   // plan 02: becomes v7::Move
    int score = 0;
    int depth = 0;
    uint64_t nodes = 0;
    int nps = 0;
};

class Engine {
public:
    Engine() = default;

    // set_syzygy_path: plan 01 logs the D-08 verbatim "no path configured"
    // line on empty path, "path not found" on missing dir; plan 05 replaces
    // with real filesystem checks + tb_init + KRk smoke probe.
    void set_syzygy_path(const std::string& path);

    // new_game: resets atomics. Plans 02/03 also clear TT + rep stack.
    void new_game();

    // search: plan 01 ships a stub returning SearchResult{} with
    // best_move=MOVE_NONE; bumps nodes_ by 1 so the GIL-release test has
    // observable work. Plan 03 implements the real iterative deepening
    // body.
    SearchResult search(const std::string& fen, int depth, int time_ms);

    // stop: flips the atomic stop flag. Fast — the binding does NOT release
    // the GIL on this method; stop_engine() in Python may be called while
    // another thread holds the GIL.
    void stop() { stop_flag_.store(true, std::memory_order_relaxed); }

    uint64_t tbhits() const { return tbhits_.load(std::memory_order_relaxed); }
    uint64_t nodes()  const { return nodes_.load(std::memory_order_relaxed); }

private:
    std::atomic<bool>     stop_flag_{false};
    std::atomic<uint64_t> tbhits_{0};
    std::atomic<uint64_t> nodes_{0};
    // TT          tt_;          // populated in plan 02
    // Board       board_;       // populated in plan 02
    // SyzygyState syzygy_;      // populated in plan 05
};

// Free-function perft entry: plan 02 implements the real body backed by
// the ported move generator. Plan 01 returns 0 so the binding contract is
// stable and the GIL-release call_guard wraps it from day one (FOUND-06
// readiness).
uint64_t perft_entry(const std::string& fen, int depth);

} // namespace v7
