set(STARLING_WARNING_FLAGS
    -Wall -Wextra -Wpedantic
    -Wconversion -Wshadow
    -Werror
)

option(STARLING_ENABLE_ASAN "Enable AddressSanitizer + UBSan" OFF)
if(STARLING_ENABLE_ASAN)
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address,undefined)
endif()
