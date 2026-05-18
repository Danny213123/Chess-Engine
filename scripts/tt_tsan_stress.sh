#!/usr/bin/env bash
# PAR-03 TSan stress harness for V7 lockless TT (Plan 03-05 Task 2).
#
# Build host gate (D-08): Windows dev host CANNOT run this — TSan is
# unavailable on MSVC. Run on WSL / Linux / macOS with clang or gcc.
#
# Steps:
#   1. Configure CMake in src/chess_engine/engine/v7/build-tsan/ with Debug + clang++.
#   2. Build the tt_tsan_stress target (TSan flags scoped to this target only —
#      see CMakeLists.txt; main v7_engine pybind module is unaffected).
#   3. Run the binary for ~60s. Capture stderr to a temp log.
#   4. grep stderr for the TSan warning marker. If found, dump the log and
#      exit 1 (FAIL). Otherwise print PASS and exit 0.
#
# Exit codes:
#   0 — TSan clean (PASS — PAR-03 gate sealed)
#   1 — TSan reported races (FAIL — block Plan 03-06 ship-SPRT)
#
# Reference: CONTEXT D-08 (16 threads × 60 seconds blocking gate), PATTERNS.md
# Shared Pattern 5 (build-host-only deferred gate).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V7_DIR="${ROOT}/src/chess_engine/engine/v7"
BUILD_DIR="${V7_DIR}/build-tsan"

# Prefer clang++ for TSan (cleaner reports than gcc on most platforms).
# Caller may override via TSAN_CXX env var (e.g. TSAN_CXX=g++).
CXX_COMPILER="${TSAN_CXX:-clang++}"

echo "[tt_tsan_stress] ROOT=${ROOT}"
echo "[tt_tsan_stress] BUILD_DIR=${BUILD_DIR}"
echo "[tt_tsan_stress] CXX=${CXX_COMPILER}"

cmake -S "${V7_DIR}" -B "${BUILD_DIR}" \
      -DCMAKE_BUILD_TYPE=Debug \
      -DCMAKE_CXX_COMPILER="${CXX_COMPILER}"

cmake --build "${BUILD_DIR}" --target tt_tsan_stress -j

BIN="${BUILD_DIR}/tt_tsan_stress"
if [ ! -x "${BIN}" ]; then
    echo "[tt_tsan_stress] FAIL: binary not built at ${BIN}" >&2
    exit 1
fi

LOG="$(mktemp -t tt_tsan_stress.XXXXXX.log)"
trap 'rm -f "${LOG}"' EXIT

echo "[tt_tsan_stress] running ${BIN} for ~60s (16 threads × 60s probe/store)..."
"${BIN}" 2>"${LOG}"

if grep -q "WARNING: ThreadSanitizer" "${LOG}"; then
    echo "FAIL: TSan reported races" >&2
    echo "----- TSan log -----" >&2
    cat "${LOG}" >&2
    echo "----- end log -----" >&2
    exit 1
fi

echo "PASS: TSan clean over 16 threads x 60s"
exit 0
