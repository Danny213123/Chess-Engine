// V7 standalone UCI binary (FOUND-07).
//
// Plan 01 ships the minimal handshake required by the existence check in
// tests/test_v7_bindings.py::test_uci_binary_exists and by the Phase 2
// fastchess gauntlet prereq (which only needs `id name` + `uciok` +
// `readyok` to launch). Plan 06 expands this loop with `position`,
// `go depth N`, `go movetime MS`, `stop`, and `ucinewgame`.

#include <iostream>
#include <string>

int main() {
    // Disable buffering on the UCI streams so a gauntlet manager sees our
    // responses immediately. Mirror Stockfish/most engines.
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::string line;
    while (std::getline(std::cin, line)) {
        if (line == "uci") {
            std::cout << "id name V7\n"
                      << "id author Chess-Engine V7 milestone\n"
                      << "uciok" << std::endl;
        } else if (line == "isready") {
            std::cout << "readyok" << std::endl;
        } else if (line == "quit") {
            return 0;
        } else {
            // Plan 06 will implement `position`, `go ...`, `stop`,
            // `ucinewgame`. Until then surface a clearly-marked stub
            // response so a gauntlet log makes the gap obvious.
            std::cout << "info string V7 phase 1 stub - command ignored: "
                      << line << std::endl;
        }
    }
    return 0;
}
