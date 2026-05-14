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
