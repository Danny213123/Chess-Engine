// V7 Engine class header.
//
// Plan 01 shipped this with stubs and forward-declared TT/Board/SyzygyState
// opaques. Plan 02 (this) wires the real Board and TT members (the data
// structures forked from V6 into v7::). Plans 03/05 add rep_stack_ and
// real syzygy state behind the same public surface so callers don't change.

#pragma once

#include "board.hpp"
#include "tt.hpp"
#include "types.hpp"

#include <atomic>
#include <cstdint>
#include <string>

namespace v7 {

// MOVE_NONE is now provided by types.hpp (real v7::Move type). Plan 01's
// placeholder `constexpr int MOVE_NONE = 0;` was removed here; the typed
// version from types.hpp covers the same value (uint16_t 0).

// Forward declaration of types that land in later plans. Syzygy lives in
// Plan 05.
struct SyzygyState;

// Minimal SearchResult struct. Plan 03 expands with PV vector and full
// search stats. The Python binding exposes these as read-only properties.
struct SearchResult {
    Move best_move = MOVE_NONE;  // real v7::Move (uint16_t) from types.hpp
    int score = 0;
    int depth = 0;
    uint64_t nodes = 0;
    int nps = 0;
};

class Engine {
public:
    Engine() = default;

    // set_syzygy_path: plan 01 ships the D-08 verbatim "no path configured"
    // / "path not found" log lines. Plan 05 replaces with real filesystem
    // checks + tb_init + KRk smoke probe.
    void set_syzygy_path(const std::string& path);

    // new_game: resets atomics AND clears the TT. Plan 03 also clears the
    // repetition stack (rep_stack_.clear()).
    void new_game();

    // search: plan 01 ships a stub bumping nodes_ by 1. Plan 03 implements
    // the real iterative deepening body.
    SearchResult search(const std::string& fen, int depth, int time_ms);

    // stop: flips the atomic stop flag. Fast — the binding does NOT release
    // the GIL on this method.
    void stop() { stop_flag_.store(true, std::memory_order_relaxed); }

    uint64_t tbhits() const { return tbhits_.load(std::memory_order_relaxed); }
    uint64_t nodes()  const { return nodes_.load(std::memory_order_relaxed); }

private:
    std::atomic<bool>     stop_flag_{false};
    std::atomic<uint64_t> tbhits_{0};
    std::atomic<uint64_t> nodes_{0};

    // Plan 02 wires the real subsystem members. Plan 03 adds rep_stack_
    // here as `RepStack rep_stack_;` (NOT on Board — checker issue #3).
    // Plan 05 adds `SyzygyState syzygy_;`.
    TT    tt_{64};   // 64MB transposition table (matches V6 default)
    Board board_;    // single working board; reset per search via from_fen
    // SyzygyState syzygy_;   // populated in Plan 05
};

// Free-function perft entry: defined in src/perft.cpp (Plan 02 lands the
// real body backed by the ported movegen).
uint64_t perft_entry(const std::string& fen, int depth);

} // namespace v7
