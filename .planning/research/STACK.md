# Stack Research — V7 Engine

**Domain:** Classical chess engine (alpha-beta + HCE), forked from V6 native C++17 pybind11 module
**Researched:** 2026-05-15
**Confidence:** HIGH (all major recommendations cross-verified against official repos / chessprogramming.org / current 2025-2026 community usage)

This document covers ONLY the new stack pieces V7 needs on top of V6's existing C++17 / pybind11 / CMake / OpenMP / FetchContent baseline. The V6 baseline (magic bitboards, alpha-beta, TT, classical eval) is not re-researched here — see `.planning/codebase/STACK.md` for the inherited stack.

---

## Recommended Stack

### Core Technologies (NEW for V7)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Fathom (jdart1 fork)** | master @ git pin (~2024-2025 commit; package versions stamp it as `1.0+git.YYYYMMDD`) | In-engine Syzygy tablebase WDL/DTZ probing for 3/4/5/6-men endgames | The de-facto portable Syzygy probing library used by virtually every modern engine that isn't Stockfish (Stockfish has its own copy). MIT licensed, single C99/C++ TU pair (`tbprobe.c` + `tbchess.c`), thread-safe `tb_probe_wdl`, supports up to 7-men, derived from Cfish's tbprobe.c by Ronald de Man and reorganized by Jon Dart. The original `basil00/Fathom` is unmaintained; **use `jdart1/Fathom`**. |
| **fastchess** | 1.4.x (current stable as of early 2026; check `Disservin/fastchess` Releases) | Engine vs engine gauntlet runner (V7 vs V6, SPRT, time-controlled matches) | Drop-in cutechess-cli replacement, actively maintained, soon to be adopted by Fishtest (Stockfish CI). Pentanomial SPRT support, much better high-concurrency stability than cutechess (10/20000 timeouts at concurrency 250 in stress tests). MIT licensed, prebuilt Windows/Linux/macOS binaries, identical CLI syntax to cutechess. UCI only — fine for V7 (UCI-only too). |
| **GediminasMasaitis/texel-tuner** | master @ git pin (no semver releases; pin a specific commit) | Texel tuning of HCE weights against Zurichess quiet-labeled.epd | Standalone, reusable C++ tuner specifically built to drop into other engines. SGD with Adam, learning-rate scheduling, multithreaded, configurable. Bypasses the "every engine reinvents tuning" pattern. License: MIT. Alternative: hand-rolled tuner inside V7 — only if the eval doesn't decompose into a linear coefficient vector. |
| **Zurichess quiet-labeled.epd** | `quiet-labeled.epd` from `tuner.7z` (~725k positions; specified as ~750k in milestone) | Texel ground-truth dataset (positions labeled with 1.0 / 0.5 / 0.0 game results) | The canonical public Texel dataset; used by Zurichess, ROFCHADE, and dozens of mid-strength engines. Quiet positions filtered by quiescence, labeled by Stockfish 080916 self-play. ROFCHADE reported +75-80 Elo from PST/material tuning on this set alone. License: not formally stated by the author but distributed for unrestricted research use; mirror at KierenP/ChessTrainingSets. |
| **pybind11** | **stay on v2.12.0** (already pinned in V6) | C++ ↔ Python bridge for the V7 module | Do NOT bump for V7. Reasons in "Version Compatibility" below — v3.0 introduces an ABI break and changes CMake variable names, neither of which V7 needs. v2.12.0 is stable, supports CPython 3.10–3.13, and matches V6 byte-for-byte so V7 builds reuse the V6 build path with zero risk. |
| **CMake** | **keep `cmake_minimum_required(VERSION 3.15)`** (matches V6) | Build system | V7 reuses V6's CMakeLists structure verbatim. 3.15 is sufficient (FetchContent, Python3 with `Development.Module`, OpenMP all work). No need for 3.28+ (C++20 modules) — V7 is C++17. Latest CMake stable is 4.3.2 (April 2026) but bumping the minimum gains nothing for this milestone and risks breaking developer machines on Ubuntu 22.04 (default 3.22). |
| **C++17** | unchanged | Language standard | V7 is a fork of V6; bumping to C++20 for V7 is out of scope (no compelling V7 feature requires it; concepts/ranges aren't needed for HCE search). Stay on C++17 for binary/source compat with V6's toolchain. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **OpenMP** | system-provided (already optional in V6 CMake) | Optional parallel hint for any embarrassingly-parallel eval helper | Already linked optionally by V6 — V7 keeps the same `find_package(OpenMP QUIET)` + `OpenMP::OpenMP_CXX` pattern. **Note:** Lazy SMP itself does NOT use OpenMP — it uses raw `std::thread` + `std::atomic`. OpenMP stays only for any per-position parallel inner loops the eval might use. |
| **C++17 `<thread>` + `<atomic>`** | standard library | Lazy SMP thread pool, atomic stop flag, atomic TT entry slot writes | Hand-rolled is the universal choice — Stockfish, Ethereal, Berserk, Invictus, Lishex all hand-roll this. No engine in the top 100 uses a third-party thread pool library for Lazy SMP. The pattern is ~150 lines and standard: a `ThreadPool` class owning `std::vector<std::thread>`, a shared `std::atomic<bool>` stop, and TT entries packed into 16-byte slots written with relaxed `std::atomic<uint64_t>` stores using the Hyatt-Mann XOR trick (no locks). Adding e.g. Boost.Asio or `BS::thread_pool` would be over-engineering. |
| **Hyatt–Mann lockless XOR hashing** | technique, not a library | Lock-free TT entry validation under concurrent writes from N threads | Standard pattern (`stored_key = key XOR data`; reader recomputes XOR to validate). Already documented on chessprogramming.org. V7 needs it because once Lazy SMP is on, multiple threads write TT slots concurrently and torn writes must be detectable without a mutex per bucket. |
| **Fathom** (already listed above) | — | (see core table) | — |
| **UCI protocol layer** (hand-written or borrowed from a reference engine) | — | If V7 is exposed as a standalone UCI binary for fastchess to drive | V7's primary integration is via pybind11 into the existing Python `find_best_move(...)` adapter. For the gauntlet, V7 must also expose a UCI binary (fastchess speaks UCI to subprocess engines). Two options: (a) build a thin C++ UCI shim around the same engine code that pybind11 wraps (~200 lines, recommended), or (b) write a Python UCI wrapper that calls into the pybind11 module (slower process startup, more moving parts). Recommend (a). |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **fastchess** | Run V7-vs-V6 gauntlets, SPRT, fixed-time matches | CLI: `fastchess -engine cmd=./v7_uci name=V7 -engine cmd=./v6_uci name=V6 -each tc=10+0.1 -rounds 1000 -repeat -concurrency 4 -sprt elo0=0 elo1=10 alpha=0.05 beta=0.05`. Outputs cutechess-compatible PGN + result tables. |
| **STS rating tool** (`fsmosca/STS-Rating`) | Compute strategic-test-suite scores against `STS1-STS15_LAN.epd` | Optional but valuable mid-development sanity check. Drives any UCI engine. Apache 2 license. |
| **OpenBench** (optional, defer) | Distributed SPRT testing if local hardware is the bottleneck | GPL. Self-host on PythonAnywhere or skip — for a single-developer V7 milestone, fastchess locally is sufficient. Mention only as a future option if iteration speed becomes the constraint. |
| **Standard EPD test suites** | Strategic / tactical regression checks | STS (15 chapters, themed positional), WAC ("Win at Chess", 300 tactical), Bratko-Kopec (24 strategic + tactical, classic). All EPD format. See "Test Position Suites" section below. |
| **Syzygy 3-4-5 men tablebases (~1 GB)** | Required for any meaningful endgame strength gain | Download from `tablebase.lichess.ovh/tables/standard/3-4-5-{wdl,dtz}/` or `tablebase.sesse.net`. NOT bundled in repo (project constraint). The download script V7 ships should default to 3-4-5 only; 6-men (~150 GB) opt-in. |

---

## Installation

```bash
# --- C++ build dependencies (already in V6, kept for V7) ---
# pybind11 v2.12.0 — fetched via CMake FetchContent (existing pattern)
# OpenMP — system package (gcc/clang/MSVC built-in)
# CMake >= 3.15, C++17 compiler

# --- New for V7: vendor Fathom into V7 source tree ---
# Add as a git submodule OR vendored copy under:
#   src/chess_engine/engine/v7/third_party/fathom/
# Fathom is two files (tbprobe.c + tbchess.c) compiled directly into the V7 module.
git submodule add https://github.com/jdart1/Fathom.git \
    src/chess_engine/engine/v7/third_party/fathom

# --- Tuning toolchain (separate executable, not linked into the engine) ---
# Vendor texel-tuner under tools/texel_tuner/ or fetch on demand.
git clone https://github.com/GediminasMasaitis/texel-tuner.git tools/texel_tuner

# --- Gauntlet harness (developer-only, not a runtime dep) ---
# Download fastchess prebuilt binary for the host platform from
# https://github.com/Disservin/fastchess/releases
# Place under tools/fastchess/ (gitignored) or document in a setup script.

# --- Tuning data (download script, NOT bundled) ---
# scripts/fetch_tuning_data.py downloads:
#   https://bitbucket.org/zurichess/tuner/downloads/tuner.7z
# and extracts quiet-labeled.epd to data/tuning/ (gitignored).

# --- Tablebases (optional download script, NOT bundled) ---
# scripts/fetch_syzygy.py downloads from tablebase.lichess.ovh
# Default: 3-4-5 men WDL+DTZ (~1 GB).
# Flag --six-men adds 6-men WDL+DTZ (~150 GB).
```

V7 CMakeLists additions (delta from V6):

```cmake
# Add Fathom sources to the V7 module
set(V7_FATHOM_SOURCES
    third_party/fathom/src/tbprobe.c
    third_party/fathom/src/tbchess.c
)
set_source_files_properties(${V7_FATHOM_SOURCES} PROPERTIES LANGUAGE C)
target_sources(v7_engine PRIVATE ${V7_FATHOM_SOURCES})
target_include_directories(v7_engine PRIVATE third_party/fathom/src)
# Fathom is thread-safe by default; do NOT define TB_NO_THREADS.

# Optional: build a standalone v7_uci executable for fastchess
add_executable(v7_uci src/uci_main.cpp ${V7_SOURCES} ${V7_FATHOM_SOURCES})
target_include_directories(v7_uci PRIVATE include third_party/fathom/src)
if (OpenMP_CXX_FOUND)
    target_link_libraries(v7_uci PRIVATE OpenMP::OpenMP_CXX)
endif()
```

---

## Lazy SMP — Reference Implementations to Study

Recommended reading order, easiest → hardest:

1. **Berserk** (`jhonnold/berserk`, C, ~4500 lines) — cleanest readable Lazy SMP. Look at `src/thread.c` and `src/search.c`. Influenced by Stockfish + Ethereal but smaller and more linear.
2. **Ethereal** (`AndyGrant/Ethereal`, C) — mid-complexity, well-commented, the canonical "study this to learn modern alpha-beta." Same author as OpenBench.
3. **Stockfish PR #467** (`official-stockfish/Stockfish#467` by Marco Costalba) — the original Lazy SMP merge. Historical but shows the minimal diff that made Stockfish switch from YBWC. Includes Ivan Ivec's log-formula depth staggering.
4. **Chessprogramming wiki: `Lazy_SMP`** — theory + pseudocode.
5. **University of Oslo MSc thesis "A Complete Chess Engine Parallelized Using Lazy SMP"** — academic walkthrough of the implementation choices and Elo measurements.

**Key implementation notes for V7:**
- Helper threads start at the root and run iterative deepening at staggered depths (Stockfish uses a log-based skip pattern; simpler engines just skip even depths on odd helpers).
- Only the main thread owns the time/stop logic; helpers poll a shared `std::atomic<bool> stop`.
- TT must be sized in MB (configurable, default 64–256 MB) and use lockless XOR validation.
- Realistic Elo gain: **~20–32 Elo from 1→16 threads** at fast TC. Don't expect linear scaling — chess engines are memory-bandwidth-bound at high core counts.

---

## Test Position Suites

| Suite | Format | Source | Use Case |
|-------|--------|--------|----------|
| **STS (Strategic Test Suite)** | EPD, 15 themed chapters, 100 positions each | https://sites.google.com/site/strategictestsuite/ ; reformatted combined `STS1-STS15_LAN.epd` at `fsmosca/STS-Rating` on GitHub | Long-term positional/strategic understanding. Score out of 1500 with rating tool. Best mid-development sanity check. |
| **WAC (Win at Chess)** | EPD, 300 tactical positions (`bm` field) | Original: Fred Reinfeld's 1958 book; EPD versions widely mirrored — see chessprogramming.org `Win_at_Chess`. Also in `ChrisWhittington/Chess-EPDs` on GitHub. | Tactical regression — fast (per-position timeout 1-5s), "did V7 break tactics that V6 solves?" |
| **Bratko-Kopec** | EPD, 24 mixed strategic+tactical | Original: Bratko & Kopec (1982); recalibrated by Benn & Kopec (1993). EPD posted by Steven J. Edwards on CCC (1998), reproduced on chessprogramming.org `Bratko-Kopec_Test`. | Classic small benchmark; useful as a cheap smoke test rather than a strength signal. |

All three are in EPD format. V7 should ship a tiny EPD runner script (Python is fine) that takes an EPD file + UCI engine binary + per-position time and reports score / mismatches. Do not depend on external rating tools as a hard dependency.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **fastchess** | cutechess-cli | Only if engines speak xboard/WinBoard (fastchess is UCI-only). V7 is UCI, so fastchess wins. cutechess-cli is also OK for ad-hoc one-off matches if you already have it installed and concurrency is low. |
| **fastchess** | OpenBench | If a single developer machine becomes the iteration bottleneck (running 10k-game SPRTs takes too long). OpenBench requires self-hosting a Django server + worker setup — meaningful infra cost. Defer until needed. |
| **jdart1/Fathom** | basil00/Fathom (original) | Never. The original is unmaintained and lacks 7-men support. |
| **jdart1/Fathom** | Roll-your-own Syzygy probe | Never. Probing logic is intricate (tablebase indexing, symmetry handling, DTZ vs WDL semantics) and Fathom is already MIT licensed and battle-tested across dozens of engines. |
| **GediminasMasaitis/texel-tuner** | Hand-rolled tuner inside V7 | If V7's evaluation is non-linear in its parameters (e.g., piece-relative king safety multipliers that aren't a sum of weighted features). Linear coefficient-vector eval → use texel-tuner. Otherwise hand-roll an SGD loop in C++ that reuses the engine's own eval function (this is how Stockfish, Berserk historically tuned). |
| **GediminasMasaitis/texel-tuner** | Texel engine's built-in tuner (peterosterlund2/texel) | Only if you want the original reference. It depends on Armadillo + GSL and is **GPL v3** — license-incompatible with the MIT-licensed V7. |
| **pybind11 v2.12.0** | pybind11 v3.0.4 (latest) | Only if V7 needs `py::smart_holder`, free-threaded Python 3.13t support, or PyPy compatibility. None apply to V7. v3.0 is ABI-incompatible with v2.13 and renames `PYTHON_*` CMake vars to `Python_*` — gratuitous churn for this milestone. |
| **CMake 3.15 minimum** | CMake 3.28 (C++20 modules) | Never for V7 — V7 is C++17. Bump only when the project as a whole moves to C++20 modules (a future, separate decision). |
| **`std::thread` + `std::atomic`** | Boost.Asio thread pool, `BS::thread_pool`, Intel TBB | Never for Lazy SMP. Every reference engine uses raw threads. The pattern is small, deterministic, and dependency-free. |
| **Zurichess quiet-labeled.epd (~725k)** | Jon Dart's `big3.epd` (~5M) or `lichess-new-labeled.epd` (~2.5M) | If 725k positions saturate (tuning loss plateaus before convergence). big3/lichess-new use the same EPD `c2 "1.0"` label format as Zurichess, so the tuner needs only minor parsing changes. Defer until needed. |
| **Zurichess quiet-labeled.epd** | Leorik selfplay dataset (DATA-L26-3443372.zip) | If self-play data outperforms Zurichess in V7's tuning runs. Out of milestone scope (Zurichess is the chosen baseline). |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **basil00/Fathom** | Unmaintained since 2015. Missing 7-men tablebase support and several Cfish-derived correctness fixes. | `jdart1/Fathom` |
| **pybind11 v3.0.x** for this milestone | ABI break vs. v2.13. Renames `PYTHON_*` → `Python_*` CMake vars (would touch V6's CMakeLists indirectly). Gains zero functionality V7 needs. | Pin v2.12.0 (already done in V6 CMake) |
| **cutechess-cli** for high-concurrency runs | Reports of premature test termination (5000-round match stopping after ~127–168 games), engine startup failures with non-Stockfish binaries, no pentanomial SPRT, no longer the active ecosystem standard. | fastchess |
| **Texel engine's built-in tuner** as a vendored library | GPL v3 — would force V7 (and the parent repo) to GPL. The repo is MIT (per `pyproject.toml`). | GediminasMasaitis/texel-tuner (MIT) |
| **Bundling tablebases in the repo** | 3-4-5 = ~1 GB; 6-men = ~150 GB. Repo bloat, git LFS cost, license/distribution concerns. | Optional download script (`scripts/fetch_syzygy.py`) — explicit project constraint. |
| **Bundling Zurichess `tuner.7z` in the repo** | ~50–100 MB of binary EPDs not needed at runtime. Author-distributed dataset; treat as external. | Download script (`scripts/fetch_tuning_data.py`) into `data/tuning/` (gitignored). |
| **Numba / NumPy / CUDA** for V7 | V7 is pure C++17 in the hot path. Mixing Numba (used by V3) into V7's eval would defeat the point of native speed. | Plain C++ in the V7 module; pybind11 only at the FFI boundary. |
| **Building V7 as a Python-side wrapper that calls V6 internals** | Locks V7 to V6's API; defeats "fork V6 and evolve" decision. Also makes UCI binary harder. | True fork: copy `v6/` → `v7/`, evolve independently, share nothing at the C++ level. |
| **YBW / DTS / ABDADA** for parallelism | All historically valid but Lazy SMP has displaced them in every modern engine. Stockfish switched in v7 (2016) and never looked back. Implementation cost is also higher. | Lazy SMP. |
| **Singular extensions before LMR/null-move are tuned** | Singular extension search overhead is high; without solid base pruning it loses Elo. | Implement in milestone order: aspiration windows → null-move → LMR → futility → LMP → SEE-pruning → THEN singular/check/recapture extensions → THEN multi-cut/probcut. |

---

## Stack Patterns by Variant

**If the V7 milestone needs a UCI binary (it does, for fastchess):**
- Add a `v7_uci` executable target in CMake alongside the `v7_engine` Python module target.
- Both link the same translation units; only the entry point differs.
- The UCI shim is ~200 lines: parse `uci`, `isready`, `position`, `go`, `stop`, `setoption` (`Threads`, `Hash`, `SyzygyPath`); emit `bestmove`.

**If Texel tuning is run on Linux (recommended):**
- Use the Linux fastchess binary (faster than Windows for high-concurrency).
- Run texel-tuner with `--threads = physical_cores` (NOT logical — hyperthreads hurt for this workload per the tuner's README).

**If 6-men tablebases are NOT downloaded:**
- Fathom still works fine in 3-4-5-only mode; `tb_init("/path/to/tables")` reports the available `TB_LARGEST` count and the engine should clamp probing to that.
- Document in V7 README that the engine is correct without tablebases — they are a strength upgrade, not a correctness requirement.

**If the developer is on Windows (V6 builds work there per existing CMake):**
- All recommended tools (fastchess, jdart1/Fathom, texel-tuner) build/run on Windows. Use MSVC 2019+ or MinGW-w64.
- Windows defender often quarantines fastchess.exe — whitelist the directory.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| pybind11 v2.12.0 | CPython 3.10–3.13 | Already verified by V6 (Python 3.12 is the project default). Do not bump. |
| pybind11 v2.12.0 | CMake ≥ 3.15 | Confirmed in V6 CMakeLists. Same minimum for V7. |
| Fathom (jdart1) | C99 OR C++17 (compiles as either) | Compile `tbprobe.c` and `tbchess.c` as C with `set_source_files_properties(... LANGUAGE C)` to avoid name-mangling surprises. Header is `extern "C"`-safe. |
| Fathom (jdart1) | `std::thread` + multiple workers | Thread-safe by default; only set `TB_NO_THREADS` if single-threaded. V7 keeps threading ON. |
| fastchess | UCI engines only | V7 must expose a UCI binary (see above). pybind11-only is not sufficient for fastchess. |
| fastchess | Windows / Linux / macOS | Prebuilt binaries on GitHub Releases for all three. |
| texel-tuner | C++17 + a CSV of `(EPD path, weight)` | Needs the engine's eval rewritten as a coefficient extractor. One-time integration cost ~1–2 days. |
| Zurichess `quiet-labeled.epd` | EPD with `c9 "1-0" / "1/2-1/2" / "0-1"` label (in this dataset's specific encoding) | Some forks use `c2 "1.0/0.5/0.0"`. Verify the label field name when wiring into texel-tuner. |
| OpenMP | Optional | Already optional in V6; keep `find_package(OpenMP QUIET)` pattern. **Do not** require it; macOS clang lacks OpenMP by default. |
| Lazy SMP `std::atomic` TT | Requires 64-bit aligned 16-byte TT entries | Pack `{key64, move16, score16, depth8, bound8, age8, padding8}` to 16 bytes; use `std::atomic<uint64_t>` for the two halves OR rely on the Hyatt-Mann XOR-of-key-and-data trick for lock-free validation. |

---

## License Summary (for a permissive-target repo)

The parent repo declares `license = "MIT"` in `pyproject.toml` but has no `LICENSE` file. All recommended additions are MIT-compatible:

| Component | License | MIT-compatible? |
|-----------|---------|-----------------|
| pybind11 v2.12.0 | BSD-style (pybind11 license) | Yes |
| Fathom (jdart1) | MIT (with original Ronald de Man portions "may be redistributed without restrictions") | Yes |
| fastchess | MIT | Yes (and it's a developer tool, not linked) |
| GediminasMasaitis/texel-tuner | MIT | Yes (and it's a developer tool, not linked) |
| Zurichess quiet-labeled.epd | Distributed by author for unrestricted use; no formal license file | Treat as research data; cite Alexandru Moșoi; safe to redistribute via download script (we do NOT redistribute, we download from origin). |
| Syzygy tablebases (Ronald de Man) | Released for unrestricted distribution | Safe; download from lichess.ovh / sesse.net at user request. |
| OpenBench (if ever used) | GPL | Developer tool only; not linked → no contamination. |
| Texel engine (NOT used) | GPL v3 | Avoided — would contaminate the repo. |
| STS / WAC / Bratko-Kopec EPDs | Public test data, no restrictive license | Safe for ad-hoc inclusion in a `tests/epd/` directory. |

---

## Sources

### Primary (HIGH confidence — official repos / chessprogramming wiki / verified in 2025-2026)

- [jdart1/Fathom](https://github.com/jdart1/Fathom) — current Syzygy probe library, MIT, 7-men support
- [jdart1/Fathom README](https://github.com/jdart1/Fathom/blob/master/README.md) — provenance, license split, thread safety
- [basil00/Fathom](https://github.com/basil00/Fathom) — confirmed unmaintained predecessor
- [Disservin/fastchess](https://github.com/Disservin/fastchess) — gauntlet/SPRT runner, MIT
- [fastchess man.md](https://github.com/Disservin/fastchess/blob/master/man.md) — CLI reference
- [GediminasMasaitis/texel-tuner](https://github.com/GediminasMasaitis/texel-tuner) — standalone tuner, MIT
- [Texel's Tuning Method (chessprogramming.org)](https://www.chessprogramming.org/Texel%27s_Tuning_Method) — algorithm reference
- [Zurichess tuner.7z download](https://bitbucket.org/zurichess/tuner/downloads/) — official dataset host
- [training data for Texel Tuning (TalkChess)](https://www.talkchess.com/forum3/viewtopic.php?t=61427) — dataset composition (725k, generation method)
- [KierenP/ChessTrainingSets](https://github.com/KierenP/ChessTrainingSets) — mirror collection including Zurichess + larger Jon Dart sets
- [Lazy SMP (chessprogramming.org)](https://www.chessprogramming.org/Lazy_SMP) — algorithm reference
- [Stockfish PR #467: Lazy SMP](https://github.com/official-stockfish/Stockfish/pull/467) — original Stockfish merge
- [Berserk (chessprogramming.org)](https://www.chessprogramming.org/Berserk) — feature list including Lazy SMP
- [University of Oslo MSc thesis on Lazy SMP](https://www.duo.uio.no/bitstream/handle/10852/53769/1/master.pdf) — academic walkthrough
- [pybind11 Releases](https://github.com/pybind/pybind11/releases) — confirms 3.0.4 is latest stable (Apr 2026), v2.13.6 is last v2.x
- [pybind11 changelog (v3.0 ABI break notes)](https://pybind11.readthedocs.io/en/stable/changelog.html) — confirms ABI/CMake var rename rationale
- [CMake 3.28 release notes](https://cmake.org/cmake/help/latest/release/3.27.html) — C++20 modules support context (not needed for V7)
- [Strategic Test Suite (official)](https://sites.google.com/site/strategictestsuite/) — STS official site
- [STS-Rating tool (Mosca)](https://github.com/fsmosca/STS-Rating) — combined `STS1-STS15_LAN.epd` + scoring
- [Bratko-Kopec Test (chessprogramming.org)](https://www.chessprogramming.org/Bratko-Kopec_Test) — EPD source
- [Test-Positions index (chessprogramming.org)](https://www.chessprogramming.org/Test-Positions) — WAC + others
- [OpenBench](https://github.com/AndyGrant/OpenBench) — distributed SPRT (deferred)
- [lichess tablebase server](https://github.com/lichess-org/lila-tablebase) — confirms `tablebase.lichess.ovh` host
- [Syzygy Bases (chessprogramming.org)](https://www.chessprogramming.org/Syzygy_Bases) — sizes (3-4-5 ~1 GB, 6-men ~150 GB)

### Secondary (MEDIUM confidence — community discussion / engine author reports)

- [TalkChess: 7-man syzygy probe Fathom](https://talkchess.com/viewtopic.php?t=70348) — confirms 7-men in jdart1 fork via Cfish merge
- [TalkChess: fastchess](https://talkchess.com/viewtopic.php?t=84427) — community adoption signal
- [OpenChess: Fastchess SPRT guide](https://open-chess.org/viewtopic.php?t=4360) — practical SPRT command examples
- [ROFCHADE technical page](https://rofchade.nl/?page_id=116) — reports +75-80 Elo from Texel on Zurichess
- [Sesse tablebase mirror](http://tablebase.sesse.net/) — alternative Syzygy host

### Confidence Notes

- **HIGH**: All version pins, library identities, license claims, and dataset descriptions cross-verified against official sources within the last 12 months.
- **MEDIUM**: Specific Elo deltas (+75 ROFCHADE, +20-32 Lazy SMP 1→16 threads) come from individual reports, not controlled measurements — treat as order-of-magnitude expectations, not promises.
- **LOW** (none in this document — all recommendations rest on at least HIGH confidence for identity/version and MEDIUM for performance expectations).

---

*Stack research for: V7 chess engine (forked from V6 native pybind11 module)*
*Researched: 2026-05-15*
