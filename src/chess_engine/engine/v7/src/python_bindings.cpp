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

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cstdint>
#include <iostream>
#include <string>

#include "engine.hpp"

namespace py = pybind11;

// --- Engine stub implementations (plan 01) ---------------------------------
//
// These live in the same translation unit as the binding for plan 01 only:
// plans 02/03/05 will move the real implementations into their own .cpp
// files and add them to CMakeLists' V7_SOURCES via the TODO markers.

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

void Engine::new_game() {
    stop_flag_.store(false, std::memory_order_relaxed);
    tbhits_.store(0, std::memory_order_relaxed);
    nodes_.store(0, std::memory_order_relaxed);
    // plan 02/03: also tt_.clear() + rep_stack_.clear() here.
}

SearchResult Engine::search(const std::string& fen, int depth, int time_ms) {
    // plan 01 stub: bump nodes_ once so the GIL-release test has observable
    // work, then return a neutral SearchResult. Plan 03 lands the real
    // iterative deepening body.
    (void)fen;
    (void)time_ms;
    nodes_.fetch_add(1, std::memory_order_relaxed);
    SearchResult r;
    r.best_move = MOVE_NONE;
    r.depth = depth;
    r.nodes = nodes_.load(std::memory_order_relaxed);
    return r;
}

uint64_t perft_entry(const std::string& fen, int depth) {
    // plan 02 lands the real perft body backed by the ported movegen.
    (void)fen;
    (void)depth;
    return 0;
}

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

    m.def("perft", &v7::perft_entry,
          py::arg("fen"), py::arg("depth"),
          py::call_guard<py::gil_scoped_release>());     // FOUND-06 parity readiness
}
