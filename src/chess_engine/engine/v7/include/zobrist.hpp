#pragma once

// V7 zobrist header. V6 kept zobrist inlined in board.hpp; V7 hoists a
// dedicated zobrist.hpp shim so plan 03's search code can include just
// "zobrist.hpp" without pulling in the full Board API. Definitions still
// live in board.cpp (verbatim from V6) — this header only re-exports the
// Zobrist struct via board.hpp.

#include "board.hpp"

namespace v7 {
// v7::Zobrist is declared in board.hpp. Definitions live in src/board.cpp.
}  // namespace v7
