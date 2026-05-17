// V7 UCI binary — minimal subset for fastchess (Phase 2).
// Phase 4 will add setoption Threads/Hash/SyzygyPath.
// Phase 2: extended with setoption (silent accept) and wtime/btime parsing
// (RESEARCH §7 budget heuristic: time_ms = (my_time / 30) + my_inc).
//
// Plan 06 expansion (FOUND-07): full minimal UCI loop replacing plan 01's
// handshake stub. Implements `uci`, `isready`, `ucinewgame`, `position
// (startpos|fen) [moves ...]`, `go (depth N|movetime MS)`, `stop`, `quit`.
// Unknown commands are silently ignored per Phase 1 scope (no setoption /
// debug / register).
//
// Threading note (documented limitation): search runs synchronously per
// command. `stop` from the SAME stdin reader thread cannot fire mid-search
// because we won't process the next line until search returns. For
// fastchess depth-fixed games this is fine — fastchess runs each engine as
// a separate process and uses time controls + the `stop` UCI command only
// at end-of-allocation. Phase 4 may add async search via std::thread for
// `go infinite` / pondering.
//
// Move-application policy: a fresh local Board is used to track the
// position so `position startpos moves m1 m2 ...` can be replayed. The
// resulting FEN is handed to Engine::search; Engine does its own from_fen
// + repetition seeding internally. This keeps the Engine API stable and
// the UCI loop's state minimal.

#include "board.hpp"
#include "engine.hpp"
#include "movegen.hpp"
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
bool apply_uci_move(v7::Board& board, const std::string& uci) {
    if (uci.size() < 4) return false;
    v7::Square from = v7::string_to_square(uci.substr(0, 2));
    v7::Square to   = v7::string_to_square(uci.substr(2, 2));
    if (from == v7::NO_SQUARE || to == v7::NO_SQUARE) return false;

    char promo_char = (uci.size() >= 5) ? std::tolower(uci[4]) : '\0';

    v7::MoveList legal;
    v7::generate_legal_moves(board, legal);
    for (int i = 0; i < legal.count; ++i) {
        v7::Move m = legal.moves[i];
        if (v7::move_from(m) != from) continue;
        if (v7::move_to(m)   != to)   continue;
        // Disambiguate promotion vs non-promotion by promo char if present
        if (v7::move_type(m) == v7::PROMOTION) {
            if (promo_char == '\0') continue;  // need promo char to match a promotion move
            v7::Piece p = v7::promo_piece(m);
            char want = '\0';
            switch (p) {
                case v7::KNIGHT: want = 'n'; break;
                case v7::BISHOP: want = 'b'; break;
                case v7::ROOK:   want = 'r'; break;
                case v7::QUEEN:  want = 'q'; break;
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

// Reset a Board to the starting position via FEN. Encapsulates the magic
// string so callers don't have to know it.
void set_startpos(v7::Board& board) {
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

    v7::Engine engine;
    v7::Board  board;
    set_startpos(board);

    // Default go arguments when client just says "go" with no parameters
    // (matches D-04 smoke default of depth 6).
    constexpr int DEFAULT_GO_DEPTH    = 6;
    constexpr int DEFAULT_GO_TIME_MS  = 5000;
    constexpr int UCI_MAX_TIME_MS     = 1'000'000'000;  // ~11 days; large enough for "depth N" runs

    std::string line;
    while (std::getline(std::cin, line)) {
        auto toks = tokenize(line);
        if (toks.empty()) continue;
        const std::string& cmd = toks[0];

        if (cmd == "uci") {
            std::cout << "id name V7\n"
                      << "id author Chess-Engine V7 milestone\n"
                      // D-06 (Plan 03-02): emit 8 Tier-1 UCI toggle declarations.
                      // Order: alphabetical for stable diff inspection.
                      // Plans 03-03 (3 more) and 03-04 (UseFortressEval) extend this.
                      << "option name UseCheckExt type check default true\n"
                      << "option name UseFutility type check default true\n"
                      << "option name UseIIR type check default true\n"
                      << "option name UseLMR type check default true\n"
                      << "option name UseLMP type check default true\n"
                      << "option name UseMultiCut type check default true\n"
                      << "option name UseNullMove type check default true\n"
                      << "option name UseProbCut type check default true\n"
                      << "option name UseRFP type check default true\n"
                      << "option name UseRecaptureExt type check default true\n"
                      << "option name UseSingular type check default true\n"
                      << "uciok" << std::endl;
        } else if (cmd == "isready") {
            std::cout << "readyok" << std::endl;
        } else if (cmd == "ucinewgame") {
            engine.new_game();
            set_startpos(board);
        } else if (cmd == "position") {
            // Forms:
            //   position startpos [moves m1 m2 ...]
            //   position fen <fenfield1> <fenfield2> ... <fenfield6> [moves ...]
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
                    // Malformed FEN — ignore silently per Phase 1 robustness target
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
                        // Illegal move in the input stream — stop applying but
                        // don't crash. The next `go` will search from whatever
                        // position we managed to reach.
                        break;
                    }
                }
            }
        } else if (cmd == "go") {
            // Parse go args. Recognized: `depth N`, `movetime MS`,
            // `wtime W`, `btime B`, `winc I`, `binc J`, `movestogo M`.
            int depth = DEFAULT_GO_DEPTH;
            int time_ms = DEFAULT_GO_TIME_MS;
            bool has_depth = false;
            bool has_movetime = false;
            int wtime = -1, btime = -1, winc = 0, binc = 0;
            bool has_wtime = false, has_btime = false;
            // movestogo parsed for protocol compliance; Phase 2 heuristic does
            // not use it (RESEARCH §7 uses the simple (my_time/30)+my_inc form).
            for (size_t i = 1; i + 1 < toks.size(); ++i) {
                if (toks[i] == "depth") {
                    try { depth = std::stoi(toks[i + 1]); has_depth = true; }
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
                } else if (toks[i] == "movestogo") {
                    // Parsed for protocol compliance; heuristic ignores it.
                    try { (void)std::stoi(toks[i + 1]); }
                    catch (...) {}
                    ++i;
                }
                // nodes/mate/infinite — Phase 2 ignores
            }
            if (has_depth && !has_movetime) {
                // Depth-fixed search: give a generous time cap so depth is the
                // binding constraint (matches fastchess depth-mode behavior).
                time_ms = UCI_MAX_TIME_MS;
            } else if (!has_depth && !has_movetime && (has_wtime || has_btime)) {
                // RESEARCH §7 Phase-2 budget heuristic: time_ms = (my_time / 30) + my_inc.
                // Pick white-side vs black-side based on Board::side_to_move
                // (accessor verified in include/board.hpp: public Color field).
                int my_time = (board.side_to_move == v7::WHITE) ? wtime : btime;
                int my_inc  = (board.side_to_move == v7::WHITE) ? winc  : binc;
                if (my_time < 0) my_time = 0;
                if (my_inc  < 0) my_inc  = 0;
                int budget = (my_time / 30) + my_inc;
                // Floor at 10ms so a near-flag emergency does not produce a 0ms search.
                if (budget < 10) budget = 10;
                time_ms = budget;
            }

            // Snapshot current position FEN; Engine::search will from_fen +
            // seed its own rep_stack internally.
            std::string fen = board.to_fen();
            v7::SearchResult r = engine.search(fen, depth, time_ms);

            std::string mv = v7::move_to_string(r.best_move);
            std::cout << "bestmove " << mv << std::endl;
        } else if (cmd == "stop") {
            // Sync-search caveat: this flips the atomic but we won't actually
            // observe a mid-search stop because we don't read stdin while
            // search runs. Kept for protocol compliance — Phase 4 may add an
            // async search thread that polls this flag.
            engine.stop();
        } else if (cmd == "quit") {
            return 0;
        } else if (cmd == "setoption") {
            // D-06 (Plan 03-02): real setoption dispatcher.
            //
            // Replaces the Phase 2 silent-accept block. Parses:
            //   setoption name <NAME> value <VALUE>
            // Dispatches to engine.set_option(name, value) for all 12 D-06
            // UCI toggles. Unknown options are handled by Engine::set_option's
            // "Unknown option: <name>" branch (T-03-X1 threat mitigation).
            //
            // Canonical form: setoption name <NAME> [value <VALUE>]
            // Multi-word names are concatenated until "value" token is seen.
            // Single-token boolean values: "true" or "false".
            //
            // Log: emits "info string option <name> = <value>" for gauntlet log
            // forensics (T-03-X2: accepted per D-06 ablation evidence intent).
            size_t i = 1;
            std::string opt_name, opt_value;
            if (i < toks.size() && toks[i] == "name") {
                ++i;
                // Collect option name tokens until "value" keyword or end
                while (i < toks.size() && toks[i] != "value") {
                    if (!opt_name.empty()) opt_name += ' ';
                    opt_name += toks[i];
                    ++i;
                }
                if (i < toks.size() && toks[i] == "value") {
                    ++i;
                    // Collect value tokens (all remaining for multi-word values)
                    while (i < toks.size()) {
                        if (!opt_value.empty()) opt_value += ' ';
                        opt_value += toks[i];
                        ++i;
                    }
                }
            }

            if (!opt_name.empty() && !opt_value.empty()) {
                // Dispatch to Engine::set_option for all known toggles.
                // Engine::set_option handles: Unknown option, Invalid value.
                // For truly unknown options (Hash, Threads) that fastchess sends,
                // Engine::set_option emits "info string Unknown option: <name>"
                // and continues — protocol-compliant graceful ignore.
                engine.set_option(opt_name, opt_value);
                // Log for gauntlet forensics (D-06 ablation evidence)
                std::cout << "info string option " << opt_name
                          << " = " << opt_value << std::endl;
            }
            // If name or value is missing, silently ignore (malformed setoption).
        } else {
            // Phase 1: unknown commands silently ignored (no debug / register).
            // setoption is handled by its own branch above.
        }
    }
    return 0;
}
