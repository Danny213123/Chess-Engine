#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "board.hpp"
#include "movegen.hpp"
#include "search.hpp"
#include "eval.hpp"
#include "magic.hpp"

namespace py = pybind11;

// Global initialization flag
static bool initialized = false;

void ensure_init() {
    if (!initialized) {
        v6::init_magics();
        initialized = true;
    }
}

// Main search function exposed to Python
std::tuple<std::string, int, int, uint64_t, int> find_best_move(
    const std::string& fen, 
    int time_limit_ms,
    int num_threads
) {
    ensure_init();
    
    v6::Board board;
    board.from_fen(fen);
    
    v6::SearchResult result;
    if (num_threads > 1) {
        result = v6::search_parallel(board, time_limit_ms, num_threads, true);
    } else {
        result = v6::search(board, time_limit_ms, true);
    }
    
    std::string move_str = v6::move_to_string(result.best_move);
    return std::make_tuple(move_str, result.score, result.depth, result.nodes, result.nps());
}

// Get PV string
std::string get_pv(const std::string& fen, int time_limit_ms) {
    ensure_init();
    
    v6::Board board;
    board.from_fen(fen);
    
    v6::SearchResult result = v6::search(board, time_limit_ms, false);
    
    std::string pv;
    for (v6::Move m : result.pv) {
        if (!pv.empty()) pv += " ";
        pv += v6::move_to_string(m);
    }
    return pv;
}

// Perft for testing move generation
uint64_t perft(const std::string& fen, int depth) {
    ensure_init();
    
    v6::Board board;
    board.from_fen(fen);
    
    if (depth == 0) return 1;
    
    v6::MoveList moves;
    v6::generate_legal_moves(board, moves);
    
    if (depth == 1) return moves.count;
    
    uint64_t nodes = 0;
    for (int i = 0; i < moves.count; ++i) {
        v6::Move m = moves[i];
        v6::Piece captured = board.piece_at(v6::move_to(m));
        int prev_castling = board.castling_rights;
        v6::Square prev_ep = board.ep_square;
        int prev_halfmove = board.halfmove_clock;
        
        board.make_move(m);
        nodes += perft(board.to_fen(), depth - 1);
        board.unmake_move(m, captured, prev_castling, prev_ep, prev_halfmove);
    }
    
    return nodes;
}

// Evaluate a position
int evaluate_position(const std::string& fen) {
    ensure_init();
    
    v6::Board board;
    board.from_fen(fen);
    
    return v6::evaluate(board);
}

// Get number of legal moves
int count_legal_moves(const std::string& fen) {
    ensure_init();
    
    v6::Board board;
    board.from_fen(fen);
    
    v6::MoveList moves;
    v6::generate_legal_moves(board, moves);
    
    return moves.count;
}

// Python module definition
PYBIND11_MODULE(v6_engine, m) {
    m.doc() = "V6 Chess Engine - C++ with OpenMP parallel search";
    
    m.def("find_best_move", &find_best_move,
          "Find best move for a position",
          py::arg("fen"),
          py::arg("time_limit_ms") = 5000,
          py::arg("num_threads") = 4);
    
    m.def("get_pv", &get_pv,
          "Get principal variation string",
          py::arg("fen"),
          py::arg("time_limit_ms") = 5000);
    
    m.def("perft", &perft,
          "Perft test for move generation",
          py::arg("fen"),
          py::arg("depth"));
    
    m.def("evaluate", &evaluate_position,
          "Evaluate a position",
          py::arg("fen"));
    
    m.def("count_legal_moves", &count_legal_moves,
          "Count legal moves in position",
          py::arg("fen"));
}
