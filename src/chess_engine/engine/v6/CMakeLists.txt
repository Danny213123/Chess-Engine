cmake_minimum_required(VERSION 3.15)
project(v6_engine LANGUAGES CXX)

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

set(V6_SOURCES
    src/board.cpp
    src/eval.cpp
    src/magic.cpp
    src/movegen.cpp
    src/search.cpp
    src/tt.cpp
    src/python_bindings.cpp
)

pybind11_add_module(v6_engine MODULE ${V6_SOURCES})

target_include_directories(v6_engine PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

find_package(OpenMP QUIET)
if (OpenMP_CXX_FOUND)
    target_link_libraries(v6_engine PRIVATE OpenMP::OpenMP_CXX)
endif()

# =============================================================================
# v6_uci standalone executable (Phase 2 GAUNT-02)
# =============================================================================
#
# Satisfies project_v6_v7_uci_gaps.md gap #1: fastchess requires a process to
# exec, but V6 historically shipped only the v6_engine pybind11 module. This
# target mirrors V7's add_executable(v7_uci ...) block (PATTERNS §"CMake
# additive-target discipline") and is purely additive — the v6_engine module
# above MUST continue to build (INT-08 invariant from Phase 1).
#
# Source list = intersection of (V6 source files) and (files the UCI loop
# actually references). Excludes:
#   - python_bindings.cpp  (pybind11 symbols won't link without Python)
#   - bench.cpp            (defines its own main())
#   - perft.cpp            (defines its own main())
add_executable(v6_uci
    ${CMAKE_CURRENT_SOURCE_DIR}/src/uci_main.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/board.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/eval.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/magic.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/movegen.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/search.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/tt.cpp
)
target_include_directories(v6_uci PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
if (OpenMP_CXX_FOUND)
    target_link_libraries(v6_uci PRIVATE OpenMP::OpenMP_CXX)
endif()
