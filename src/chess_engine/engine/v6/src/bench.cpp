#include "board.hpp"
#include "search.hpp"
#include "magic.hpp"
#include <iostream>
#include <vector>
#include <chrono>
#if defined(_OPENMP)
#include <omp.h>
#else
static inline int omp_get_max_threads() { return 1; }
#endif

using namespace v6;

int main() {
    init_magics();
    
    std::cout << "V6 Engine Benchmark\n";
    std::cout << "===================\n\n";
    
    // Test positions
    std::vector<std::pair<std::string, std::string>> positions = {
        {"startpos", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"},
        {"kiwipete", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"},
        {"position3", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"},
        {"position4", "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1"},
    };
    
    int num_threads = omp_get_max_threads();
    std::cout << "Threads available: " << num_threads << "\n\n";
    
    uint64_t total_nodes = 0;
    int total_time = 0;
    
    for (const auto& [name, fen] : positions) {
        std::cout << "Position: " << name << "\n";
        std::cout << "FEN: " << fen << "\n";
        
        Board board;
        board.from_fen(fen);
        
        // Single-threaded
        auto result1 = search(board, 5000, true);
        std::cout << "Single-thread: depth=" << result1.depth 
                  << " nodes=" << result1.nodes 
                  << " nps=" << result1.nps()
                  << " best=" << move_to_string(result1.best_move) << "\n";
        
        // Multi-threaded
        auto result_mt = search_parallel(board, 5000, num_threads, true);
        std::cout << "Multi-thread (" << num_threads << "): depth=" << result_mt.depth 
                  << " nodes=" << result_mt.nodes 
                  << " nps=" << result_mt.nps()
                  << " best=" << move_to_string(result_mt.best_move) << "\n\n";
        
        total_nodes += result_mt.nodes;
        total_time += result_mt.time_ms;
    }
    
    std::cout << "===================\n";
    std::cout << "Total nodes: " << total_nodes << "\n";
    std::cout << "Total time: " << total_time << "ms\n";
    std::cout << "Average NPS: " << (total_time > 0 ? (total_nodes * 1000) / total_time : 0) << "\n";
    
    return 0;
}
