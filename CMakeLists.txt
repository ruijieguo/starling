cmake_minimum_required(VERSION 3.27)
project(starling LANGUAGES CXX VERSION 0.0.1)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

include(cmake/StarlingOptions.cmake)

# OpenSSL discovery — Homebrew on Apple Silicon installs at /opt/homebrew.
# Provide a fallback hint before find_package so a bare `cmake -S . -B build`
# works without the caller passing -DOPENSSL_ROOT_DIR.
if(APPLE AND NOT DEFINED OPENSSL_ROOT_DIR)
    if(EXISTS "/opt/homebrew/opt/openssl@3")
        set(OPENSSL_ROOT_DIR "/opt/homebrew/opt/openssl@3")
    endif()
endif()
find_package(OpenSSL REQUIRED)

add_library(starling_core STATIC)
target_include_directories(starling_core PUBLIC include)
target_sources(starling_core PRIVATE
    src/preflight.cpp
    src/final_query_assertion.cpp
    src/runtime_health.cpp
    src/schema/canonicalize.cpp
)
target_compile_options(starling_core PRIVATE ${STARLING_WARNING_FLAGS})
target_link_libraries(starling_core PUBLIC OpenSSL::Crypto)
if(APPLE)
    target_link_libraries(starling_core PUBLIC "-framework CoreFoundation")
endif()

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
