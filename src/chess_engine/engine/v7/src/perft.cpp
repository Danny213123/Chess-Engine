// V7 perft entry — verbatim port of V6's bindings-side perft (V6
// python_bindings.cpp lines 61-88). V6 re-FENs every node (slow but
// deterministic); V7 keeps the same shape for perft parity per
// RESEARCH.md §A2 Gotchas. Phase 4 may optimize.
//
// Replaces Plan 01's `return 0;` stub in src/python_bindings.cpp;
// python_bindings.cpp now forward-declares this symbol and the
// PYBIND11_MODULE wires it as `m.def("perft", &v7::perft_entry, ...)`.

#include "board.hpp"
#include "movegen.hpp"
#include "magic.hpp"
#include "engine.hpp"
#include <atomic>

namespace v7 {

// One-shot magic-table initialization. V6's bindings-side `ensure_init()`
// flag lives in python_bindings.cpp; V7 hoists it to perft.cpp so that the
// perft entry is self-sufficient (it can be called before any Engine method).
static std::atomic<bool> g_perft_initialized{false};

static void perft_ensure_init() {
    // memory_order_acquire/release pair to guarantee init_magics()'s table
    // writes are visible to any thread that observes initialized == true.
    if (!g_perft_initialized.load(std::memory_order_acquire)) {
        init_magics();
        g_perft_initialized.store(true, std::memory_order_release);
    }
}

uint64_t perft_entry(const std::string& fen, int depth) {
    perft_ensure_init();

    Board board;
    board.from_fen(fen);

    if (depth == 0) return 1;

    MoveList moves;
    generate_legal_moves(board, moves);

    if (depth == 1) return moves.count;

    uint64_t nodes = 0;
    for (int i = 0; i < moves.count; ++i) {
        Move m = moves[i];
        Piece captured = board.piece_at(move_to(m));
        int prev_castling = board.castling_rights;
        Square prev_ep = board.ep_square;
        int prev_halfmove = board.halfmove_clock;

        board.make_move(m);
        // V6 pattern: recurse via to_fen() (slow but matches V6 bit-exactly).
        nodes += perft_entry(board.to_fen(), depth - 1);
        board.unmake_move(m, captured, prev_castling, prev_ep, prev_halfmove);
    }

    return nodes;
}

} // namespace v7
