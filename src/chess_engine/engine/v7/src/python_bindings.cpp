// V7 pybind11 module entry point.
//
// REPLACES V6's binding pattern (counter-example: v6/src/python_bindings.cpp).
// The two non-negotiables that V6 got wrong:
//   1. SearchInfo cancellation must be observable from another Python thread
//      (FOUND-04). Achieved here via a stateful Engine class with a stop()
//      method backed by std::atomic<bool>.
//   2. The search call must NOT hold the GIL (FOUND-05, Pitfall #11). The
//      binding wraps search / set_syzygy_path / perft in a GIL-release
//      call guard (see the three .def(...) sites below). stop() is
//      intentionally excluded — a single atomic write is fast and is
//      invoked from another Python thread that already holds the GIL.
//
// Plan 02 update: removed the plan-01 `perft_entry` `return 0;` stub from
// this TU. The real body lives in src/perft.cpp (free function
// v7::perft_entry) and is bound below via `&v7::perft_entry`. The Engine
// stub bodies (set_syzygy_path / new_game / search) remain here through
// Plan 02 — Plan 03 moves Engine::search and Engine::new_game into
// src/engine.cpp, and Plan 05 moves Engine::set_syzygy_path into
// src/syzygy.cpp.

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cstdint>
#include <iostream>
#include <string>

#include "engine.hpp"
#include "eval.hpp"

namespace py = pybind11;

// --- Engine stub implementations (Plans 02-pending; final in Plans 03/05) --
//
// These live in this TU until the owning plan moves them: Plan 03 takes
// Engine::new_game + Engine::search into src/engine.cpp; Plan 05 takes
// Engine::set_syzygy_path into src/syzygy.cpp.

namespace v7 {

void Engine::set_syzygy_path(const std::string& path) {
    // D-08 verbatim log strings (plan 05 will add the "no tablebase files
    // at <path>" and "smoke probe failed" variants once Fathom is wired).
    if (path.empty()) {
        std::cerr << "[v7] syzygy: no path configured; tbhits will be 0\n";
        return;
    }
    std::cerr << "[v7] syzygy: path not found: " << path
              << "; tbhits will be 0\n";
}

// Plan 03 — Engine::new_game and Engine::search now live in src/engine.cpp
// (real iterative-deepening body wiring SearchInfo.external_stop and
// SearchInfo.rep_stack). Engine::set_syzygy_path inline body remains above
// through Plan 03 and is moved to src/syzygy.cpp by Plan 05.
//
// perft_entry lives in src/perft.cpp (Plan 02) — no stub here.

} // namespace v7

// --- pybind11 module -------------------------------------------------------

PYBIND11_MODULE(v7_engine, m) {
    m.doc() = "V7 Chess Engine - C++17 pybind11 with SearchInfo wiring + GIL release";

    py::class_<v7::SearchResult>(m, "SearchResult")
        .def_readonly("best_move", &v7::SearchResult::best_move)
        .def_readonly("score",     &v7::SearchResult::score)
        .def_readonly("depth",     &v7::SearchResult::depth)
        .def_readonly("nodes",     &v7::SearchResult::nodes)
        .def_readonly("nps",       &v7::SearchResult::nps);

    py::class_<v7::Engine>(m, "Engine")
        .def(py::init<>())
        .def("set_syzygy_path", &v7::Engine::set_syzygy_path,
             py::arg("path"),
             py::call_guard<py::gil_scoped_release>())   // FOUND-05: filesystem I/O blocks
        .def("new_game",        &v7::Engine::new_game)
        .def("search",          &v7::Engine::search,
             py::arg("fen"),
             py::arg("depth")   = 6,
             py::arg("time_ms") = 5000,
             py::call_guard<py::gil_scoped_release>())   // FOUND-05 + Pitfall #11
        // stop() intentionally has NO call_guard — single atomic write,
        // and stop_engine() in Python must be callable while holding the
        // GIL from another thread without round-tripping through a
        // release/acquire cycle (pure overhead on a fast write).
        .def("stop", &v7::Engine::stop)
        .def("tbhits", &v7::Engine::tbhits)
        .def("nodes", &v7::Engine::nodes);

    // Plan 02: real perft now lives in src/perft.cpp; the binding wires
    // &v7::perft_entry directly so the FOUND-06 corpus has a working
    // entry point even before Engine::search is real (Plan 03).
    m.def("perft", &v7::perft_entry,
          py::arg("fen"), py::arg("depth"),
          py::call_guard<py::gil_scoped_release>());     // FOUND-06 parity

    // Plan 04: expose evaluate() so Python tests (test_v7_eval.py) and
    // the future Phase 4 Texel tuner harness can score positions
    // directly without going through Engine::search. Releases the GIL
    // (FOUND-05) — eval iterates magic-bitboard attack tables and is
    // pure C++ work with no Python interaction.
    m.def("evaluate", &v7::evaluate_entry,
          py::arg("fen"),
          py::call_guard<py::gil_scoped_release>());
}
