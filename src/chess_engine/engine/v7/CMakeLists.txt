cmake_minimum_required(VERSION 3.15)
# NB: C is added conditionally inside the Fathom block below via
# `enable_language(C)`. Plan 01 ALSO listed C up-front; we keep it here so
# CMake's first-pass language scan succeeds even if Fathom is absent and the
# Fathom block is short-circuited by its EXISTS guard.
project(v7_engine LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Default to Release for single-config generators
if (NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

find_package(Python3 COMPONENTS Interpreter Development.Module REQUIRED)

# Try to locate pybind11 from a Python install first
execute_process(
    COMMAND "${Python3_EXECUTABLE}" -m pybind11 --cmakedir
    RESULT_VARIABLE PYBIND11_CMAKE_RESULT
    OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
if (PYBIND11_CMAKE_RESULT EQUAL 0 AND EXISTS "${PYBIND11_CMAKE_DIR}")
    list(APPEND CMAKE_PREFIX_PATH "${PYBIND11_CMAKE_DIR}")
endif()

find_package(pybind11 CONFIG QUIET)

if (NOT pybind11_FOUND)
    include(FetchContent)
    message(STATUS "pybind11 not found via CMake config; fetching with FetchContent")
    FetchContent_Declare(
        pybind11
        GIT_REPOSITORY https://github.com/pybind/pybind11.git
        GIT_TAG v2.12.0
    )
    FetchContent_MakeAvailable(pybind11)
endif()

# =============================================================================
# COEFFS CODEGEN (Plan 04 supplies coeffs.json + tools/gen_coeffs.py)
# =============================================================================
#
# Pre-staged here so Plan 04 does not need to touch CMakeLists.txt. When
# coeffs.json is absent (Plan 02 timeline), we write a placeholder coeffs.cpp
# so CMake configure succeeds. Plan 04's first build re-triggers configure
# (CMakeLists hash + gen_coeffs.py touch) and the real add_custom_command path
# becomes active.
set(COEFFS_JSON ${CMAKE_CURRENT_SOURCE_DIR}/coeffs.json)
set(COEFFS_CPP  ${CMAKE_CURRENT_SOURCE_DIR}/src/coeffs.cpp)
if(EXISTS ${COEFFS_JSON})
    add_custom_command(
        OUTPUT ${COEFFS_CPP}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_coeffs.py
                ${COEFFS_JSON} ${COEFFS_CPP}
        DEPENDS ${COEFFS_JSON} ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_coeffs.py
        COMMENT "Generating coeffs.cpp from coeffs.json"
        VERBATIM
    )
else()
    # Plan 04 has not landed yet — write a transient empty coeffs.cpp so CMake
    # configure + build succeed. Plan 04 replaces this via the real add_custom_command.
    if(NOT EXISTS ${COEFFS_CPP})
        file(WRITE ${COEFFS_CPP}
             "// placeholder until Plan 04 lands coeffs.json + tools/gen_coeffs.py\n")
    endif()
endif()

# =============================================================================
# KPK BITBASE CODEGEN (Plan 03-04 — mirrors COEFFS_CPP pattern above)
# =============================================================================
#
# Pre-staged here so Plan 03-04 does not need to re-open CMakeLists.txt.
# tools/gen_kpk.py enumerates all legal KPK positions, classifies via BFS,
# cross-checks against Fathom (deferred on Windows dev host — see PATTERNS.md
# Shared Pattern 5), and emits src/kpk_bitbase.cpp containing a packed
# uint8_t[] table. The emitted .cpp is gitignored (D-10/D-12).
set(KPK_CPP ${CMAKE_CURRENT_SOURCE_DIR}/src/kpk_bitbase.cpp)
add_custom_command(
    OUTPUT ${KPK_CPP}
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_kpk.py
            ${KPK_CPP}
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_kpk.py
    COMMENT "Generating kpk_bitbase.cpp via tools/gen_kpk.py"
    VERBATIM
)

# =============================================================================
# FULL V7 SOURCE LIST (Wave-collapse enabler — Plans 03/04/05 do NOT touch this)
# =============================================================================
#
# Every Wave-3 source is enumerated here so Plans 03 (search/engine), 04
# (eval/coeffs), and 05 (syzygy) only write CONTENT into existing files and
# never modify CMakeLists.txt. This is the structural precondition for
# running Plans 03/04/05 in parallel as Wave 3 (zero file-conflict overlap).
set(V7_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/src/board.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/movegen.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/magic.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/tt.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/perft.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/search.cpp     # Plan 03 fills (currently stub)
    ${CMAKE_CURRENT_SOURCE_DIR}/src/engine.cpp     # Plan 03 fills (currently stub)
    ${CMAKE_CURRENT_SOURCE_DIR}/src/eval.cpp       # Plan 04 fills (currently stub)
    ${COEFFS_CPP}                                  # Plan 04 generates via add_custom_command
    ${CMAKE_CURRENT_SOURCE_DIR}/src/syzygy.cpp     # Plan 05 fills (currently stub)
    ${CMAKE_CURRENT_SOURCE_DIR}/src/python_bindings.cpp
    # Plan 03-01 cross-Wave-2 scaffold: MovePicker stub (Plan 03-02 Task 2 fills body)
    ${CMAKE_CURRENT_SOURCE_DIR}/src/search/move_picker.cpp
    # Plan 03-04: endgame eval + KPK bitbase codegen
    ${CMAKE_CURRENT_SOURCE_DIR}/src/endgame.cpp
    ${KPK_CPP}
)

pybind11_add_module(v7_engine MODULE ${V7_SOURCES})

target_include_directories(v7_engine PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

find_package(OpenMP QUIET)
if (OpenMP_CXX_FOUND)
    target_link_libraries(v7_engine PRIVATE OpenMP::OpenMP_CXX)
endif()

# =============================================================================
# v7_uci standalone executable (FOUND-07)
# =============================================================================
#
# Plan 01 shipped a stub uci_main.cpp that satisfies the FOUND-07 existence
# check; the full UCI loop (position/go/stop/etc.) lands in Plan 06. Reuses
# V7_SOURCES so Wave-3 plans don't need to extend a separate source list.
add_executable(v7_uci
    ${CMAKE_CURRENT_SOURCE_DIR}/src/uci_main.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/board.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/movegen.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/magic.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/tt.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/perft.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/search.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/engine.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/eval.cpp
    ${COEFFS_CPP}
    ${CMAKE_CURRENT_SOURCE_DIR}/src/syzygy.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/search/move_picker.cpp  # Plan 03-01 scaffold
    # Plan 03-04: endgame eval + KPK bitbase codegen
    ${CMAKE_CURRENT_SOURCE_DIR}/src/endgame.cpp
    ${KPK_CPP}
)
target_include_directories(v7_uci PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
if (OpenMP_CXX_FOUND)
    target_link_libraries(v7_uci PRIVATE OpenMP::OpenMP_CXX)
endif()

# =============================================================================
# tt_tsan_stress — Plan 03-05 Task 2 (PAR-03 TSan stress harness)
# =============================================================================
#
# Standalone executable that drives the lockless TT with 16 threads × 60s of
# random probe/store under ThreadSanitizer (CONTEXT D-08). Only built on
# GNU/Clang — MSVC has no TSan support. The -fsanitize=thread flags are
# scoped to this target alone so the main v7_engine pybind module continues
# to build unaffected (additive-target discipline mirroring v6/CMakeLists.txt's
# v6_uci block).
#
# Build/run wrapper: scripts/tt_tsan_stress.sh — configures build-tsan/ with
# clang++, builds this target, runs the binary, greps stderr for
# "WARNING: ThreadSanitizer". The PAR-03 acceptance gate (Plan 03-05 Task 3)
# is a build-host-only human checkpoint.
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    add_executable(tt_tsan_stress
        ${CMAKE_CURRENT_SOURCE_DIR}/tt_tsan_stress.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/src/tt.cpp
    )
    target_include_directories(tt_tsan_stress PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    )
    target_compile_options(tt_tsan_stress PRIVATE -fsanitize=thread -g -O1)
    target_link_options(tt_tsan_stress PRIVATE -fsanitize=thread)
endif()

# =============================================================================
# Fathom (Syzygy probing) — pre-staged in Wave 2 with EXISTS guard
# =============================================================================
#
# Plan 05 adds the submodule at extern/fathom. Until then this block
# short-circuits so CMake configure succeeds without the source tree.
#
# CRITICAL ORDERING (TB-02): V7's own include/ MUST precede Fathom's so the
# project-owned tbconfig.h override wins during Fathom's preprocessor pass.
set(FATHOM_DIR ${CMAKE_CURRENT_SOURCE_DIR}/extern/fathom)
if(EXISTS ${FATHOM_DIR}/src/tbprobe.c)
    enable_language(C)  # Fathom's tbprobe.c is C99
    target_compile_definitions(v7_engine PRIVATE V7_HAS_FATHOM=1)

    target_include_directories(v7_engine PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include   # OUR tbconfig.h (Plan 05 creates) — FIRST
        ${FATHOM_DIR}/src                     # Fathom headers (tbprobe.h)
    )
    target_sources(v7_engine PRIVATE ${FATHOM_DIR}/src/tbprobe.c)

    target_include_directories(v7_uci PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${FATHOM_DIR}/src
    )
    target_compile_definitions(v7_uci PRIVATE V7_HAS_FATHOM=1)
    target_sources(v7_uci PRIVATE ${FATHOM_DIR}/src/tbprobe.c)

    set_source_files_properties(${FATHOM_DIR}/src/tbprobe.c PROPERTIES LANGUAGE C)
else()
    message(STATUS "[v7] Fathom submodule absent; Syzygy probing disabled at build (Plan 05 will add submodule)")
endif()
