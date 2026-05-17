// V6 UCI binary — minimal subset for fastchess (Phase 2 GAUNT-02).
//
// Closes project_v6_v7_uci_gaps.md gap #1: V6 historically shipped only the
// v6_engine pybind11 module, which fastchess cannot drive (it spawns
// processes, not Python modules). This loop mirrors v7_uci's structure
// (src/chess_engine/engine/v7/src/uci_main.cpp) verbatim with a handful of
// V6-specific adaptations spelled out below.
//
// Adaptations from V7:
//   1. V6 has NO engine.hpp / Engine class. Search is the free function
//      v6::search(Board&, int time_ms, bool verbose) declared in
//      include/search.hpp (verified via src/python_bindings.cpp line 36).
//      Therefore main() calls v6::init_magics() up front (mirroring
//      python_bindings.cpp::ensure_init) instead of instantiating an
//      Engine object.
//   2. `ucinewgame` calls v6::TT.clear() — V6's global TT singleton lives
//      at the namespace scope (include/tt.hpp line 75) — instead of
//      V7's engine.new_game().
//   3. `stop` is a no-op. V6 has no in-search cancellation primitive
//      exposed to the UCI thread (SearchInfo::stopped is an internal
//      atomic; nothing forwards UCI-level stop to it without a refactor).
//      Phase 4 may add an atomic flag the UCI loop can set; this is
//      Phase-2-scope per the plan.
//   4. V6 search takes (Board&, time_ms, verbose) and does its own
//      iterative deepening. There is no `depth` parameter — depth-fixed
//      mode (`go depth N`) falls back to a generous time cap so depth
//      remains the *soft* binding constraint.
//
// Phase-2 extensions added beyond what V7 currently has (mirrored in
// v7_uci by Plan 02-01):
//   - `setoption` branch: silent accept. fastchess sends
//     `setoption name Hash value N` / `setoption name Threads value N`
//     before every match. V6's TT is construction-time only (no resize
//     API exposed — A4 per 02-RESEARCH §10 Q4), so Hash setter is an
//     accept-and-ignore; document the asymmetry inline.
//   - `go` parses wtime/btime/winc/binc with budget = (my_time / 30) +
//     my_inc (RESEARCH §7 simple heuristic; SRCH-15 10% safety margin is
//     a Phase 1 responsibility, not Phase 2).
//
// Threading note (mirrors V7): search runs synchronously per command.
// `stop` from the same stdin reader thread cannot fire mid-search because
// we won't read the next line until search returns. For fastchess
// time-controlled games this is fine — fastchess spawns each engine as
// its own process and `wtime/btime` budget elapses naturally.
//
// Move-application policy: a fresh local Board tracks the position so
// `position startpos moves m1 m2 ...` can be replayed. Search receives
// the live Board reference (V6 quirk — V7 hands over a FEN string).

#include "board.hpp"
#include "magic.hpp"
#include "movegen.hpp"
#include "search.hpp"
#include "tt.hpp"
#include "types.hpp"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

// Apply a UCI move string (e.g. "e2e4", "g1f3", "e7e8q") to a Board by
// matching against generated legal moves. Returns true on success.
bool apply_uci_move(v6::Board& board, const std::string& uci) {
    if (uci.size() < 4) return false;
    v6::Square from = v6::string_to_square(uci.substr(0, 2));
    v6::Square to   = v6::string_to_square(uci.substr(2, 2));
    if (from == v6::NO_SQUARE || to == v6::NO_SQUARE) return false;

    char promo_char = (uci.size() >= 5) ? std::tolower(uci[4]) : '\0';

    v6::MoveList legal;
    v6::generate_legal_moves(board, legal);
    for (int i = 0; i < legal.count; ++i) {
        v6::Move m = legal.moves[i];
        if (v6::move_from(m) != from) continue;
        if (v6::move_to(m)   != to)   continue;
        // Disambiguate promotion vs non-promotion by promo char if present
        if (v6::move_type(m) == v6::PROMOTION) {
            if (promo_char == '\0') continue;  // need promo char to match a promotion move
            v6::Piece p = v6::promo_piece(m);
            char want = '\0';
            switch (p) {
                case v6::KNIGHT: want = 'n'; break;
                case v6::BISHOP: want = 'b'; break;
                case v6::ROOK:   want = 'r'; break;
                case v6::QUEEN:  want = 'q'; break;
                default: break;
            }
            if (want != promo_char) continue;
        } else if (promo_char != '\0') {
            // UCI says promotion but this candidate is not a promotion — skip
            continue;
        }
        board.make_move(m);
        return true;
    }
    return false;
}

// Reset a Board to the starting position via FEN.
void set_startpos(v6::Board& board) {
    board.from_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
}

// Tokenize a line on whitespace.
std::vector<std::string> tokenize(const std::string& line) {
    std::vector<std::string> out;
    std::istringstream iss(line);
    std::string tok;
    while (iss >> tok) out.push_back(tok);
    return out;
}

}  // namespace

int main() {
    // Disable buffering on the UCI streams so a gauntlet manager sees our
    // responses immediately. Mirror Stockfish/most engines.
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(nullptr);

    // V6 has no Engine class — initialize magic bitboards once at program
    // start (mirrors python_bindings.cpp::ensure_init()). Subsequent
    // search() calls assume init_magics() has run.
    v6::init_magics();

    v6::Board board;
    set_startpos(board);

    // Default go arguments when client just says "go" with no parameters.
    constexpr int DEFAULT_GO_TIME_MS = 5000;
    constexpr int UCI_MAX_TIME_MS    = 1'000'000'000;  // ~11 days; large enough for "depth N" runs

    std::string line;
    while (std::getline(std::cin, line)) {
        auto toks = tokenize(line);
        if (toks.empty()) continue;
        const std::string& cmd = toks[0];

        if (cmd == "uci") {
            std::cout << "id name V6\n"
                      << "id author Chess-Engine V7 milestone\n"
                      << "uciok" << std::endl;
        } else if (cmd == "isready") {
            std::cout << "readyok" << std::endl;
        } else if (cmd == "ucinewgame") {
            // V6 substitute for V7's engine.new_game(): clear the global
            // transposition table singleton (include/tt.hpp line 75).
            v6::TT.clear();
            set_startpos(board);
        } else if (cmd == "setoption") {
            // Format: setoption name <NAME> value <VALUE>
            // Phase 2: accept silently. fastchess sends
            // `setoption name Hash value N` and `setoption name Threads
            // value N` on every match start. V6's TranspositionTable is
            // constructed once at process load with size_mb=64 (see
            // include/tt.hpp line 39) and exposes no resize API — Hash
            // is therefore accept-and-ignore here (A4 per
            // 02-RESEARCH §10 Q4). Threads is also accept-and-ignore for
            // Phase 2 since V6-vs-V6 sanity runs single-threaded
            // (D-08a in 02-CONTEXT).
            // Do NOT print anything for unknown option names; per UCI
            // protocol unknown options are silently ignored.
        } else if (cmd == "position") {
            // Forms:
            //   position startpos [moves m1 m2 ...]
            //   position fen <fenfield1> ... <fenfield6> [moves ...]
            if (toks.size() < 2) continue;
            size_t i = 1;
            if (toks[i] == "startpos") {
                set_startpos(board);
                ++i;
            } else if (toks[i] == "fen") {
                ++i;
                // Reassemble FEN: standard FEN has 6 space-separated fields.
                std::string fen;
                int field_count = 0;
                while (i < toks.size() && toks[i] != "moves" && field_count < 6) {
                    if (!fen.empty()) fen += ' ';
                    fen += toks[i];
                    ++i;
                    ++field_count;
                }
                try {
                    board.from_fen(fen);
                } catch (...) {
                    // Malformed FEN — ignore silently
                    continue;
                }
            } else {
                // Unrecognized position form; ignore
                continue;
            }
            // Optional `moves m1 m2 ...` tail
            if (i < toks.size() && toks[i] == "moves") {
                ++i;
                for (; i < toks.size(); ++i) {
                    if (!apply_uci_move(board, toks[i])) {
                        // Illegal move in the input stream — stop applying
                        // but don't crash. The next `go` will search from
                        // whatever position we managed to reach.
                        break;
                    }
                }
            }
        } else if (cmd == "go") {
            // Parse go args. Recognized: `depth N`, `movetime MS`,
            // `wtime MS`, `btime MS`, `winc MS`, `binc MS`.
            int time_ms     = DEFAULT_GO_TIME_MS;
            bool has_depth     = false;
            bool has_movetime  = false;
            int wtime = 0, btime = 0, winc = 0, binc = 0;
            bool has_wtime = false, has_btime = false;
            for (size_t i = 1; i + 1 < toks.size(); ++i) {
                if (toks[i] == "depth") {
                    // V6 search has no depth parameter — we record it for
                    // soft-mode bookkeeping only (depth-fixed runs get a
                    // generous time cap below). Parsing keeps the loop
                    // tolerant of fastchess depth-mode probes.
                    try { (void)std::stoi(toks[i + 1]); has_depth = true; }
                    catch (...) {}
                    ++i;
                } else if (toks[i] == "movetime") {
                    try { time_ms = std::stoi(toks[i + 1]); has_movetime = true; }
                    catch (...) {}
                    ++i;
                } else if (toks[i] == "wtime") {
                    try { wtime = std::stoi(toks[i + 1]); has_wtime = true; }
                    catch (...) {}
                    ++i;
                } else if (toks[i] == "btime") {
                    try { btime = std::stoi(toks[i + 1]); has_btime = true; }
                    catch (...) {}
                    ++i;
                } else if (toks[i] == "winc") {
                    try { winc = std::stoi(toks[i + 1]); }
                    catch (...) {}
                    ++i;
                } else if (toks[i] == "binc") {
                    try { binc = std::stoi(toks[i + 1]); }
                    catch (...) {}
                    ++i;
                }
                // movestogo / nodes / mate / infinite — Phase 2 ignores
            }

            // Time-budget priority: movetime > wtime/btime > depth > default.
            // - movetime is an explicit fixed budget (highest precedence).
            // - wtime/btime: classic clock TC. Budget heuristic per
            //   02-RESEARCH §7: (my_time / 30) + my_inc. This is the
            //   Phase-2-scope simple heuristic; SRCH-15 (10% safety margin)
            //   is Phase 1's responsibility, not here.
            // - depth-only (no movetime, no clock): generous time cap so
            //   the search's own iterative deepening runs many iterations.
            //   V6's search has no depth parameter, so this falls back to
            //   movetime semantics — depth becomes a soft signal.
            if (!has_movetime && (has_wtime || has_btime)) {
                int my_time = (board.side_to_move == v6::WHITE) ? wtime : btime;
                int my_inc  = (board.side_to_move == v6::WHITE) ? winc  : binc;
                if (my_time > 0) {
                    time_ms = (my_time / 30) + my_inc;
                    if (time_ms < 1) time_ms = 1;  // guard against zero/negative
                }
            } else if (has_depth && !has_movetime) {
                // Depth-fixed search: give a generous time cap so depth is
                // the binding constraint. V6 has no depth API, but the
                // search will simply iterate until time elapses.
                time_ms = UCI_MAX_TIME_MS;
            }

            // V6 search takes a Board reference directly (no FEN round-trip).
            v6::SearchResult r = v6::search(board, time_ms, false);

            std::string mv = v6::move_to_string(r.best_move);
            std::cout << "bestmove " << mv << std::endl;
        } else if (cmd == "stop") {
            // V6 has no exposed in-search cancellation primitive — kept as
            // a no-op for UCI protocol compliance. Phase 4 may add an
            // atomic-flag bridge between this branch and SearchInfo::stopped.
            // For Phase 2 (TC-bounded games via wtime/btime above) the
            // engine returns when its computed budget elapses; mid-search
            // stop is not exercised.
        } else if (cmd == "quit") {
            return 0;
        } else {
            // Unknown commands silently ignored per UCI protocol.
        }
    }
    return 0;
}
