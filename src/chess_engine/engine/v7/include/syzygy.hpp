// V7 Syzygy probing state — wraps Fathom (jdart1 fork) behind a small C++ API.
//
// Plan 05 (this file) provides the SyzygyState class. Plan 03's
// include/engine.hpp will add a `v7::SyzygyState syzygy_;` member to
// v7::Engine and a `#include "syzygy.hpp"` near the top — that wiring is
// NOT done in this file (Wave 3 file-ownership invariant: this plan owns
// only syzygy.hpp / syzygy.cpp / .gitmodules / extern/fathom / tbconfig.h
// and tests/test_v7_syzygy.py).
//
// Invariants (see RESEARCH.md §B3 + plan 01-05-PLAN.md acceptance):
// - D-07: set_path always logs, never throws.
// - D-08: 5 verbatim log strings — exact byte-for-byte match required.
// - D-09: probe failure NEVER maps to DRAW / fabricated DTZ — always
//         std::nullopt + stderr log.
// - TB-08: probes gated on piece_count <= min(max_pieces_, TB_LARGEST)
//         AND !in_check AND castling_rights == 0 (Fathom undefined
//         behavior outside those constraints).

#pragma once

#include <atomic>
#include <cstdint>
#include <optional>
#include <string>

namespace v7 {

// Forward-declare Board so this header is light to include from engine.hpp.
// syzygy.cpp pulls in the full board.hpp.
struct Board;

// =============================================================================
// Probe result
// =============================================================================
//
// score_cp is mapped from WDL: WIN ~ +20000, LOSS ~ -20000, DRAW = 0,
// CURSED_WIN = +1 (cursed = 50-move-rule draw), BLESSED_LOSS = -1.
// Search will replace these with real mate-distance scores when it has
// DTZ info; the raw WDL mapping is enough for the in-search "endpoint"
// case where the engine just needs to know which side is winning.

struct ProbeResult {
    int score_cp;
    enum class Kind {
        WIN,
        DRAW,
        LOSS,
        CURSED_WIN,
        BLESSED_LOSS,
    } kind;
};

// =============================================================================
// SyzygyState
// =============================================================================
//
// Owns the global Fathom state (Fathom is process-global — there can only be
// one initialized tablebase set at a time). The Engine class owns ONE
// SyzygyState as a private member; the destructor calls tb_free() if init
// ever succeeded.

class SyzygyState {
public:
    SyzygyState() = default;
    ~SyzygyState();

    // set_path: D-07 / D-08 invariants.
    //   - Empty path                          → log case 1, return.
    //   - Path does not exist / not directory → log case 2, return.
    //   - Directory has no .rtbw files        → log case 3, return.
    //   - tb_init() fails                     → log case 5, return.
    //   - tb_init() succeeds but smoke probe  → log case 4, tb_free, return.
    //   - All checks pass                     → initialized_ = true.
    // NEVER throws; never propagates an exception across the FFI boundary.
    void set_path(const std::string& path);

    // Probe gating max: clamps to [0, 7] (Fathom supports up to 7-piece TBs
    // in some builds, but 6 is the typical default).
    void set_max_pieces(unsigned n);

    bool      initialized() const noexcept { return initialized_; }
    uint64_t  tbhits()      const noexcept { return tbhits_.load(std::memory_order_relaxed); }

    // In-search WDL probe (TB-05 / TB-06 / D-09).
    // Returns std::nullopt on:
    //   - Not initialized OR TB_LARGEST == 0
    //   - piece_count > min(max_pieces_, TB_LARGEST)
    //   - side-to-move in check (Fathom undefined behavior)
    //   - castling rights != 0 (Fathom requires no castling for WDL)
    //   - tb_probe_wdl returned TB_RESULT_FAILED (D-09: log + nullopt, NEVER 0/DRAW)
    std::optional<ProbeResult> probe_wdl(const Board& b) const;

    // Root DTZ probe (TB-04 — FULLY IMPLEMENTED per locked decision; no stub).
    // Returns the DTZ ply count to mate-or-conversion for the best move at
    // the root, or std::nullopt on failure (D-09 invariant — never fabricated).
    std::optional<int> probe_root_dtz(const Board& b) const;

private:
    // smoke_probe_krk: constructs the canonical KRk endgame
    // (FEN "4k3/8/8/8/8/8/4R3/4K3 w - - 0 1") and probes WDL. White-to-move
    // with KR vs k is a known WIN; this catches corrupt or wrong-format
    // tablebases at init time per TB-10 / D-08 case 4. Returns true iff the
    // probe returned ProbeResult::Kind::WIN.
    bool smoke_probe_krk() const;

    bool                            initialized_ = false;
    unsigned                        max_pieces_  = 6;
    mutable std::atomic<uint64_t>   tbhits_{0};
};

} // namespace v7
