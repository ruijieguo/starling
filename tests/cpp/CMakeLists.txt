include(FetchContent)
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.15.2
)
FetchContent_MakeAvailable(googletest)

# GoogleTest 1.15.2's gtest-printers.h emits an implicit char8_t -> char32_t
# conversion that Apple Clang 21+ flags under -Wcharacter-conversion. The
# warning is upstream and harmless; suppress it on gtest's own targets so our
# own -Werror build stays clean. Remove once we bump GoogleTest past the fix.
foreach(_gt_target IN ITEMS gtest gtest_main gmock gmock_main)
    if(TARGET ${_gt_target})
        target_compile_options(${_gt_target} PRIVATE -Wno-character-conversion)
    endif()
endforeach()

add_executable(starling_tests
    test_smoke.cpp
    test_profile_capability.cpp
    test_runtime_health.cpp
)
target_link_libraries(starling_tests PRIVATE starling_core GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(starling_tests)
