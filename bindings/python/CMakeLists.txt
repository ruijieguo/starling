find_package(Python 3.11 COMPONENTS Interpreter Development.Module REQUIRED)

# Auto-discover pybind11's CMake config from the active Python interpreter so a
# plain `cmake -S . -B build` works in any venv that has pybind11 installed.
# scikit-build-core injects this hint when building the wheel; we replicate it
# here for direct CMake invocations.
if(NOT pybind11_DIR)
    execute_process(
        COMMAND "${Python_EXECUTABLE}" -c
                "import pybind11, sys; sys.stdout.write(pybind11.get_cmake_dir())"
        OUTPUT_VARIABLE _pybind11_cmake_dir
        RESULT_VARIABLE _pybind11_cmake_dir_rc
    )
    if(_pybind11_cmake_dir_rc EQUAL 0 AND _pybind11_cmake_dir)
        set(pybind11_DIR "${_pybind11_cmake_dir}" CACHE PATH "pybind11 CMake config dir")
    endif()
endif()

find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_core MODULE module.cpp)
target_link_libraries(_core PRIVATE starling_core)
target_compile_options(_core PRIVATE ${STARLING_WARNING_FLAGS})

set_target_properties(_core PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/python/starling
)

install(TARGETS _core DESTINATION starling)
