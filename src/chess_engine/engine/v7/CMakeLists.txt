cmake_minimum_required(VERSION 3.15)
# NB: add C to LANGUAGES because Fathom's tbprobe.c (plan 05) is C99.
# Declared from plan 01 so plan 05 doesn't need to re-touch this line.
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

# Sources for the pybind11 module. Plan 01 only ships the python_bindings
# translation unit (everything else is stubbed in the header). Subsequent
# plans add their sources via the TODO markers below.
set(V7_SOURCES
    src/python_bindings.cpp
    # TODO(plan-02): add board.cpp, movegen.cpp, magic.cpp, tt.cpp here
    # TODO(plan-03): add search.cpp
    # TODO(plan-04): add eval.cpp + generated src/coeffs.cpp
    # TODO(plan-05): add syzygy.cpp + Fathom subdirectory (extern/fathom/src/tbprobe.c)
)

pybind11_add_module(v7_engine MODULE ${V7_SOURCES})

target_include_directories(v7_engine PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

find_package(OpenMP QUIET)
if (OpenMP_CXX_FOUND)
    target_link_libraries(v7_engine PRIVATE OpenMP::OpenMP_CXX)
endif()

# v7_uci standalone executable (FOUND-07). Plan 01 ships a stub uci_main.cpp
# that implements the minimal handshake required by the FOUND-07 existence
# check; full UCI loop (position/go/stop/etc.) lands in plan 06. Plans
# 03/04/05 will extend the source list via target_sources() as they add
# the real engine body.
add_executable(v7_uci src/uci_main.cpp)
target_include_directories(v7_uci PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
if (OpenMP_CXX_FOUND)
    target_link_libraries(v7_uci PRIVATE OpenMP::OpenMP_CXX)
endif()
