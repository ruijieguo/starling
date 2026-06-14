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

# P3.b1 phase 5: zvec 向量后端(ExternalProject + 2-bundle 链接)。默认 OFF —— ON
# 时 ExternalProject 完整编译 zvec 重栈(arrow/rocksdb/protobuf,首次数十分钟 + GB
# submodule 下载),产出 libzvec_{plugins,main}.a。见 cmake/StarlingZvec.cmake。
option(STARLING_VECTOR_ZVEC "Build zvec vector backend (heavy: arrow/rocksdb)" OFF)
