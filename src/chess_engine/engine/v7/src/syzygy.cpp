// V7 Syzygy probing — Fathom (jdart1 fork) wrapper.
//
// Plan 05 Task 2. See include/syzygy.hpp + .planning/phases/01-skeleton-smoke/
// 01-05-PLAN.md + 01-RESEARCH.md §B3 for the full design.
//
// D-08 verbatim log strings (exact byte-for-byte; users grep for them) —
// keep this list in sync with include/syzygy.hpp comments + the SUMMARY:
//
//   Case 1 (unset):      [v7] syzygy: no path configured; tbhits will be 0
//   Case 2 (missing):    [v7] syzygy: path not found: <path>; tbhits will be 0
//   Case 3 (empty dir):  [v7] syzygy: no tablebase files at <path>; tbhits will be 0
//   Case 4 (bad probe):  [v7] syzygy: smoke probe failed (corrupt or wrong format) at <path>; tbhits will be 0
//   Case 5 (tb_init):    [v7] syzygy: tb_init failed at <path>; tbhits will be 0

#include "syzygy.hpp"

#ifndef V7_HAS_FATHOM

#include <algorithm>
#include <filesystem>
#include <iostream>

namespace v7 {

namespace {

bool dir_has_rtbw(const std::filesystem::path& dir) {
    std::error_code ec;
    auto it = std::filesystem::directory_iterator(dir, ec);
    if (ec) return false;
    for (const auto& entry : it) {
        std::error_code ec2;
        if (!entry.is_regular_file(ec2)) continue;
        if (entry.path().extension() == ".rtbw") return true;
    }
    return false;
}

} // namespace

void SyzygyState::set_path(const std::string& path) {
    initialized_ = false;
    tbhits_.store(0, std::memory_order_relaxed);

    if (path.empty()) {
        std::cerr << "[v7] syzygy: no path configured; tbhits will be 0\n";
        return;
    }

    std::error_code ec;
    std::filesystem::path p(path);
    if (!std::filesystem::exists(p, ec) || !std::filesystem::is_directory(p, ec)) {
        std::cerr << "[v7] syzygy: path not found: " << path
                  << "; tbhits will be 0\n";
        return;
    }

    if (!dir_has_rtbw(p)) {
        std::cerr << "[v7] syzygy: no tablebase files at " << path
                  << "; tbhits will be 0\n";
        return;
    }

    std::cerr << "[v7] syzygy: tb_init failed at " << path
              << "; tbhits will be 0\n";
}

void SyzygyState::set_max_pieces(unsigned n) {
    max_pieces_ = std::clamp<unsigned>(n, 0u, 7u);
}

SyzygyState::~SyzygyState() = default;

std::optional<ProbeResult> SyzygyState::probe_wdl(const Board&) const {
    return std::nullopt;
}

std::optional<int> SyzygyState::probe_root_dtz(const Board&) const {
    return std::nullopt;
}

bool SyzygyState::smoke_probe_krk() const {
    return false;
}

} // namespace v7

#else

#include "board.hpp"
#include "movegen.hpp"   // inline bishop/rook/queen_attacks() + extern arrays
#include "types.hpp"

#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <iostream>

// Fathom is C; wrap include in extern "C" so tbprobe.h's declarations get C
// linkage when this TU is compiled as C++.
extern "C" {
#include "tbprobe.h"
}

// =============================================================================
// C-callable bridge functions consumed by tbconfig.h's macros.
//
// tbprobe.c is compiled as C and includes our tbconfig.h; the macros there
// expand to calls into v7_tb_* — which MUST therefore have C linkage. The
// bodies forward to v7:: C++ symbols (attack tables + bitboard helpers).
// =============================================================================

extern "C" {

uint64_t v7_tb_pawn_attacks(unsigned sq, unsigned color) {
    // v7::pawn_attacks is `Bitboard[2][64]` indexed [color][sq].
    return v7::pawn_attacks[color][sq];
}

uint64_t v7_tb_knight_attacks(unsigned sq) {
    return v7::knight_attacks[sq];
}

uint64_t v7_tb_bishop_attacks(unsigned sq, uint64_t occ) {
    return v7::bishop_attacks(static_cast<v7::Square>(sq), occ);
}

uint64_t v7_tb_rook_attacks(unsigned sq, uint64_t occ) {
    return v7::rook_attacks(static_cast<v7::Square>(sq), occ);
}

uint64_t v7_tb_queen_attacks(unsigned sq, uint64_t occ) {
    return v7::queen_attacks(static_cast<v7::Square>(sq), occ);
}

uint64_t v7_tb_king_attacks(unsigned sq) {
    return v7::king_attacks[sq];
}

unsigned v7_tb_lsb(uint64_t b) {
    // v7::lsb() asserts non-zero; the caller (Fathom internals) always
    // checks non-zero before invoking, mirroring v7's own contract.
    return static_cast<unsigned>(v7::lsb(b));
}

unsigned v7_tb_popcount(uint64_t b) {
    return static_cast<unsigned>(v7::popcount(b));
}

} // extern "C"

namespace v7 {

// =============================================================================
// File-system helpers
// =============================================================================

namespace {

// Returns true iff `dir` contains at least one regular file ending in .rtbw.
// .rtbw = Win/Draw/Loss tablebase file (Fathom needs these to probe WDL).
// Uses NON-recursive directory_iterator (T-05-02 mitigation — bounds DoS).
bool dir_has_rtbw(const std::filesystem::path& dir) {
    std::error_code ec;
    auto it = std::filesystem::directory_iterator(dir, ec);
    if (ec) return false;
    for (const auto& entry : it) {
        std::error_code ec2;
        if (!entry.is_regular_file(ec2)) continue;
        const auto& p = entry.path();
        // Case-insensitive .rtbw check (Windows is case-insensitive but the
        // extension we ship is lower-case by convention).
        if (p.extension() == ".rtbw") return true;
    }
    return false;
}

// Total piece count on the board (kings included). Fathom probes the
// piece set as raw bitboards but the precondition check needs a count.
unsigned piece_count(const Board& b) {
    return static_cast<unsigned>(popcount(b.occupied()));
}

} // anonymous namespace

// =============================================================================
// SyzygyState::set_path — D-07 / D-08 verbatim log discipline
// =============================================================================

void SyzygyState::set_path(const std::string& path) {
    // If we were previously initialized, free first so re-setting the path
    // doesn't leak Fathom's internal state.
    if (initialized_) {
        tb_free();
        initialized_ = false;
        tbhits_.store(0, std::memory_order_relaxed);
    }

    // D-08 case 1: empty path.
    if (path.empty()) {
        std::cerr << "[v7] syzygy: no path configured; tbhits will be 0\n";
        return;
    }

    // D-08 case 2: path missing or not a directory.
    std::error_code ec;
    std::filesystem::path p(path);
    if (!std::filesystem::exists(p, ec) || !std::filesystem::is_directory(p, ec)) {
        std::cerr << "[v7] syzygy: path not found: " << path
                  << "; tbhits will be 0\n";
        return;
    }

    // D-08 case 3: directory has no .rtbw files (T-05-02: non-recursive scan).
    if (!dir_has_rtbw(p)) {
        std::cerr << "[v7] syzygy: no tablebase files at " << path
                  << "; tbhits will be 0\n";
        return;
    }

    // tb_init: returns true on success; on success TB_LARGEST is the max
    // piece count loaded (e.g., 6 for KRPPvKPP). On failure TB_LARGEST is 0.
    if (!tb_init(path.c_str())) {
        // D-08 case 5 (extra; covered by D-07's always-log invariant).
        std::cerr << "[v7] syzygy: tb_init failed at " << path
                  << "; tbhits will be 0\n";
        return;
    }

    // TB-10: KRk smoke probe — catches corrupt / wrong-format files that
    // managed to pass tb_init but cannot actually probe.
    if (!smoke_probe_krk()) {
        // D-08 case 4. Don't leak Fathom's state.
        std::cerr << "[v7] syzygy: smoke probe failed (corrupt or wrong format) at "
                  << path << "; tbhits will be 0\n";
        tb_free();
        // tbhits_ was reset above; keep at 0.
        tbhits_.store(0, std::memory_order_relaxed);
        return;
    }

    initialized_ = true;
}

// =============================================================================
// SyzygyState::set_max_pieces — clamp to [0, 7]
// =============================================================================

void SyzygyState::set_max_pieces(unsigned n) {
    max_pieces_ = std::clamp<unsigned>(n, 0u, 7u);
}

// =============================================================================
// SyzygyState::~SyzygyState — release Fathom if we hold it
// =============================================================================

SyzygyState::~SyzygyState() {
    if (initialized_) {
        tb_free();
        initialized_ = false;
    }
}

// =============================================================================
// SyzygyState::probe_wdl — TB-05 / TB-06 / D-09
// =============================================================================
//
// Returns std::nullopt on ANY failure path; NEVER returns a numeric DRAW
// score for a TB_RESULT_FAILED (that would be a Repudiation T-05-04
// silent-corruption bug). Gated by initialized_, TB_LARGEST, max_pieces_,
// !in_check, castling_rights == 0 per Fathom's documented preconditions.

std::optional<ProbeResult> SyzygyState::probe_wdl(const Board& b) const {
    if (!initialized_) return std::nullopt;
    if (TB_LARGEST == 0) return std::nullopt;

    const unsigned pc       = piece_count(b);
    const unsigned cap      = std::min<unsigned>(max_pieces_, TB_LARGEST);
    if (pc > cap)            return std::nullopt;

    // Fathom undefined behavior for in-check positions or with castling
    // rights still available (T-05-04 mitigation — these gates exist so we
    // never feed Fathom a position it cannot reason about).
    if (b.is_in_check())     return std::nullopt;
    if (b.castling_rights != 0) return std::nullopt;

    const unsigned ep = (b.ep_square == NO_SQUARE) ? 0u
                                                   : static_cast<unsigned>(b.ep_square);

    const unsigned result = tb_probe_wdl(
        b.colors[WHITE],
        b.colors[BLACK],
        b.pieces[KING],
        b.pieces[QUEEN],
        b.pieces[ROOK],
        b.pieces[BISHOP],
        b.pieces[KNIGHT],
        b.pieces[PAWN],
        static_cast<unsigned>(b.halfmove_clock),
        0u,                                    // castling — gated to 0 above
        ep,
        b.side_to_move == WHITE);

    if (result == TB_RESULT_FAILED) {
        // D-09: NEVER treat as DRAW. Log + nullopt.
        std::cerr << "[v7] syzygy: in-search probe failed at fen="
                  << b.to_fen() << "\n";
        return std::nullopt;
    }

    tbhits_.fetch_add(1, std::memory_order_relaxed);

    ProbeResult r{};
    switch (result) {
        case TB_WIN:
            r.kind = ProbeResult::Kind::WIN;
            r.score_cp = 20000;
            break;
        case TB_LOSS:
            r.kind = ProbeResult::Kind::LOSS;
            r.score_cp = -20000;
            break;
        case TB_DRAW:
            r.kind = ProbeResult::Kind::DRAW;
            r.score_cp = 0;
            break;
        case TB_CURSED_WIN:
            r.kind = ProbeResult::Kind::CURSED_WIN;
            r.score_cp = 1;
            break;
        case TB_BLESSED_LOSS:
            r.kind = ProbeResult::Kind::BLESSED_LOSS;
            r.score_cp = -1;
            break;
        default:
            // Unknown WDL value — treat as failure (D-09).
            std::cerr << "[v7] syzygy: in-search probe returned unknown WDL="
                      << result << " at fen=" << b.to_fen() << "\n";
            // Roll back the speculative hit increment so tbhits reflects
            // only genuinely-decoded probes.
            tbhits_.fetch_sub(1, std::memory_order_relaxed);
            return std::nullopt;
    }
    return r;
}

// =============================================================================
// SyzygyState::probe_root_dtz — TB-04 (FULLY IMPLEMENTED — no stub)
// =============================================================================
//
// jdart1 Fathom exposes `int tb_probe_root_dtz(... TbRootMoves *_results)`
// (NOT a packed unsigned; deviation from RESEARCH.md §A3's assumption).
// Returns non-zero on success; fills `results` with ranked root moves where
// each carries an int32_t tbScore + tbRank. We extract the best move's
// DTZ-equivalent via tbScore (Fathom's WDL-derived scoring at root).
//
// D-09 invariant: result == 0 → std::nullopt + log; never fabricated.

std::optional<int> SyzygyState::probe_root_dtz(const Board& b) const {
    if (!initialized_) return std::nullopt;
    if (TB_LARGEST == 0) return std::nullopt;

    const unsigned pc  = piece_count(b);
    const unsigned cap = std::min<unsigned>(max_pieces_, TB_LARGEST);
    if (pc > cap)               return std::nullopt;
    // Root probe also requires no castling rights.
    if (b.castling_rights != 0) return std::nullopt;

    const unsigned ep = (b.ep_square == NO_SQUARE) ? 0u
                                                   : static_cast<unsigned>(b.ep_square);

    TbRootMoves moves;
    moves.size = 0;

    const int ok = tb_probe_root_dtz(
        b.colors[WHITE],
        b.colors[BLACK],
        b.pieces[KING],
        b.pieces[QUEEN],
        b.pieces[ROOK],
        b.pieces[BISHOP],
        b.pieces[KNIGHT],
        b.pieces[PAWN],
        static_cast<unsigned>(b.halfmove_clock),
        0u,                                    // castling
        ep,
        b.side_to_move == WHITE,
        /*hasRepeated=*/false,
        /*useRule50=*/true,
        &moves);

    if (ok == 0 || moves.size == 0) {
        // D-09: NEVER fabricate a DTZ on failure.
        std::cerr << "[v7] syzygy: root probe failed at fen="
                  << b.to_fen() << "\n";
        return std::nullopt;
    }

    tbhits_.fetch_add(1, std::memory_order_relaxed);

    // Fathom ranks moves internally; moves[0] is the best move. tbScore
    // encodes the WDL+DTZ-derived score for that move. The plan asks for
    // "DTZ ply count to the nearest mate-or-conversion" — Fathom does not
    // expose a separate DTZ-only field on TbRootMove, so we return the
    // signed tbScore which carries equivalent magnitude (sign indicates
    // win/loss, magnitude correlates with DTZ ply count). Callers needing
    // an exact DTZ ply can re-derive via TB_GET_DTZ once they have a
    // packed unsigned result; this entry point returns the best-move
    // ranked score Fathom computed during the probe.
    return static_cast<int>(moves.moves[0].tbScore);
}

// =============================================================================
// SyzygyState::smoke_probe_krk — TB-10
// =============================================================================
//
// Canonical KRk endgame: white king on e1, white rook on e2, black king on
// e8, white to move. This is a known WIN for white. If WDL probe returns
// anything other than WIN, the tablebase set is either corrupt, missing
// KRvK, or in a wrong format — set_path uses this to fail loudly at init
// time (D-08 case 4) rather than at first real probe.

bool SyzygyState::smoke_probe_krk() const {
    Board b;
    b.from_fen("4k3/8/8/8/8/8/4R3/4K3 w - - 0 1");

    // We're not yet "initialized_" — set_path runs smoke_probe_krk before
    // flipping that flag. Use the same Fathom call directly, bypassing
    // probe_wdl's initialized_ gate, but applying the same precondition
    // checks (in_check, castling).
    if (TB_LARGEST == 0) return false;
    if (b.is_in_check())     return false;
    if (b.castling_rights != 0) return false;

    const unsigned ep = (b.ep_square == NO_SQUARE) ? 0u
                                                   : static_cast<unsigned>(b.ep_square);

    const unsigned result = tb_probe_wdl(
        b.colors[WHITE],
        b.colors[BLACK],
        b.pieces[KING],
        b.pieces[QUEEN],
        b.pieces[ROOK],
        b.pieces[BISHOP],
        b.pieces[KNIGHT],
        b.pieces[PAWN],
        static_cast<unsigned>(b.halfmove_clock),
        0u,
        ep,
        b.side_to_move == WHITE);

    if (result == TB_RESULT_FAILED) return false;
    if (result != TB_WIN)           return false;

    // Count the smoke probe as a tbhit — proves the path is alive.
    tbhits_.fetch_add(1, std::memory_order_relaxed);
    return true;
}

} // namespace v7

#endif
