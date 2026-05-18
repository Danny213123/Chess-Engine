// tt_tsan_stress.cpp — PAR-03 stress driver for V7's lockless TT.
//
// Source-of-truth reference for the data structure under test: V7's lockless
// Hyatt-Mann XOR TT (src/tt.cpp + include/tt.hpp, Plan 03-05 Task 1). The
// harness only exercises the PUBLIC TT::probe / TT::store / TT::new_search
// surface — no peek into AtomicEntry internals — so a passing TSan run is
// evidence that the public API is race-free under concurrent multi-thread
// access (CONTEXT D-08 acceptance gate for PAR-03).
//
// Wrapper: scripts/tt_tsan_stress.sh builds this with -fsanitize=thread,
// runs it for 60 seconds, captures stderr, and greps for "WARNING:
// ThreadSanitizer". If any warning is detected, the wrapper exits 1.
// This binary itself ALWAYS exits 0 on completion (TSan reports flow to
// stderr — exit-code interpretation is the shell wrapper's job).
//
// Build: only compiled when CMAKE_CXX_COMPILER_ID is GNU or Clang (see
// CMakeLists.txt — TSan is unavailable on MSVC). The main v7_engine pybind
// module continues to build unaffected by this target's -fsanitize=thread
// flags (additive-target discipline per Shared Pattern of v6_uci).

#include "tt.hpp"

#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <random>
#include <thread>
#include <vector>

int main() {
    // 64 MB TT — matches Engine::tt_ production size (engine.hpp:90).
    v7::TT tt(64);

    std::atomic<bool> stop{false};
    constexpr int N_THREADS    = 16;   // PAR-03 acceptance constant (D-08)
    constexpr int DURATION_SEC = 60;   // PAR-03 acceptance constant (D-08)

    std::vector<std::thread> workers;
    workers.reserve(static_cast<std::size_t>(N_THREADS));

    for (int t = 0; t < N_THREADS; ++t) {
        workers.emplace_back([&tt, &stop, t]() {
            // Per-thread RNG seed — distinct so two workers do not produce
            // identical key streams (would mask probe/store interleavings).
            std::mt19937_64 rng(0xC0FFEEull + static_cast<std::uint64_t>(t));

            while (!stop.load(std::memory_order_relaxed)) {
                std::uint64_t k = rng();
                if (rng() & 1ULL) {
                    // Probe path.
                    v7::TTEntry e{};
                    (void)tt.probe(k, e);
                } else {
                    // Store path — exercise the full pack/replacement codepath.
                    tt.store(
                        k,
                        static_cast<v7::Move>(rng() & 0xFFFFULL),     // move (16b)
                        static_cast<int>(static_cast<std::int16_t>(rng() & 0xFFFFULL)),  // score
                        static_cast<int>(static_cast<std::int8_t>(rng() & 0x7FULL)),     // depth
                        v7::TT_EXACT);                                // flag
                }
            }
        });
    }

    std::this_thread::sleep_for(std::chrono::seconds(DURATION_SEC));
    stop.store(true, std::memory_order_relaxed);
    for (auto& w : workers) w.join();

    // Always exit 0 — TSan emits its own report on stderr; the shell wrapper
    // greps for "WARNING: ThreadSanitizer" and converts that into the
    // process exit code consumed by CI / human checkpoint.
    return 0;
}
