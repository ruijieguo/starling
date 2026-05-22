cmake_minimum_required(VERSION 3.27)
project(starling LANGUAGES CXX VERSION 0.0.1)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

include(cmake/StarlingOptions.cmake)

add_library(starling_core STATIC)
target_include_directories(starling_core PUBLIC include)
target_sources(starling_core PRIVATE
    src/preflight.cpp
    src/final_query_assertion.cpp
    src/runtime_health.cpp
)
target_compile_options(starling_core PRIVATE ${STARLING_WARNING_FLAGS})

# Testing-only translation unit lives in its own target so prod can omit it.
add_library(starling_testing_marker STATIC src/testing/testing_marker.cpp)
target_include_directories(starling_testing_marker PUBLIC include)

option(STARLING_BUILD_PYTHON "Build pybind11 bindings" ON)
if(STARLING_BUILD_PYTHON)
    add_subdirectory(bindings/python)
endif()

enable_testing()
option(STARLING_BUILD_TESTS "Build C++ tests" ON)
if(STARLING_BUILD_TESTS)
    add_subdirectory(tests/cpp)
endif()
