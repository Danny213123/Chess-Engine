#include "board.hpp"
#include "movegen.hpp"
#include "magic.hpp"
#include <iostream>
#include <chrono>

using namespace v6;

uint64_t perft(Board& board, int depth) {
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
        nodes += perft(board, depth - 1);
        board.unmake_move(m, captured, prev_castling, prev_ep, prev_halfmove);
    }
    
    return nodes;
}

int main() {
    init_magics();
    
    std::cout << "V6 Engine Perft Test\n";
    std::cout << "====================\n\n";
    
    Board board;
    board.from_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    
    for (int depth = 1; depth <= 6; ++depth) {
        auto start = std::chrono::high_resolution_clock::now();
        uint64_t nodes = perft(board, depth);
        auto end = std::chrono::high_resolution_clock::now();
        
        auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
        uint64_t nps = ms > 0 ? (nodes * 1000) / ms : nodes;
        
        std::cout << "Depth " << depth << ": " << nodes << " nodes in " << ms << "ms (" << nps << " nps)\n";
    }
    
    // Known perft results for starting position
    std::cout << "\nExpected values:\n";
    std::cout << "Depth 1: 20\n";
    std::cout << "Depth 2: 400\n";
    std::cout << "Depth 3: 8902\n";
    std::cout << "Depth 4: 197281\n";
    std::cout << "Depth 5: 4865609\n";
    std::cout << "Depth 6: 119060324\n";
    
    return 0;
}
