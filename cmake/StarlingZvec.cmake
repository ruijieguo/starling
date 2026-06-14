# StarlingZvec.cmake — zvec 向量后端集成(STARLING_VECTOR_ZVEC=ON)。P3.b1 phase 5。
#
# zvec(github.com/alibaba/zvec) 是完整向量 DB,不导出 C++ target,30+ 依赖库散在
# 深层 ExternalProject 路径,直接链接极脆弱。策略:ExternalProject 完整编译 zvec,
# post-build 用 libtool 合并为两个稳定 bundle(见 cmake/merge_zvec_bundles.sh),
# starling 经 zvec_backend INTERFACE 库链接 force_load plugins + 普通 main。
#
# 当前仅 macOS(libtool/-framework/force_load);Linux 适配(whole-archive + 不同
# 系统库)后置。option 默认 OFF,不影响默认构建。
include(ExternalProject)

if(NOT APPLE)
    message(FATAL_ERROR
        "STARLING_VECTOR_ZVEC 当前仅支持 macOS(Linux 链接适配后置)")
endif()

set(_zvec_bundle_dir "${CMAKE_BINARY_DIR}/zvec-bundle")
set(_zvec_plugins "${_zvec_bundle_dir}/libzvec_plugins.a")
set(_zvec_main "${_zvec_bundle_dir}/libzvec_main.a")
set(_zvec_prefix "${CMAKE_BINARY_DIR}/zvec-ext")
set(_zvec_src "${_zvec_prefix}/src/zvec_ext")
set(_zvec_include "${_zvec_src}/src/include")

# 完整 build(含 core_knn 插件)→ 合并脚本产出 2 bundle。POLICY flag 透传给
# zvec(其旧 googletest submodule 的 cmake_minimum_required<3.5)。
ExternalProject_Add(zvec_ext
    PREFIX "${_zvec_prefix}"
    GIT_REPOSITORY https://github.com/alibaba/zvec.git
    GIT_TAG v0.5.0
    GIT_SHALLOW ON
    GIT_SUBMODULES_RECURSE ON
    UPDATE_DISCONNECTED ON
    CMAKE_ARGS
        -DCMAKE_BUILD_TYPE=Release
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5
        -DBUILD_PYTHON_BINDINGS=OFF
        -DBUILD_TOOLS=OFF
        -DBUILD_TESTING=OFF
    BUILD_COMMAND ${CMAKE_COMMAND} --build <BINARY_DIR> -j
    INSTALL_COMMAND
        bash "${CMAKE_SOURCE_DIR}/cmake/merge_zvec_bundles.sh"
             <BINARY_DIR> "${_zvec_bundle_dir}"
    BUILD_BYPRODUCTS "${_zvec_plugins}" "${_zvec_main}"
)

# zvec headers 在 build 后填充;configure 时建占位避免 include dir 不存在告警。
file(MAKE_DIRECTORY "${_zvec_include}")

# INTERFACE 库聚合链接配置:force_load plugins(插件注册)+ 普通 main + macOS
# 系统框架。STARLING_HAS_ZVEC 宏供条件编译。
add_library(zvec_backend INTERFACE)
add_dependencies(zvec_backend zvec_ext)
# SYSTEM:抑制 zvec 第三方 header 的告警(starling_core 用 -Werror)。
target_include_directories(zvec_backend SYSTEM INTERFACE "${_zvec_include}")
target_link_libraries(zvec_backend INTERFACE
    "-Wl,-force_load,${_zvec_plugins}"
    "${_zvec_main}"
    "-framework CoreFoundation"
    "-framework Security"
    "-framework SystemConfiguration"
    z)
target_compile_definitions(zvec_backend INTERFACE STARLING_HAS_ZVEC=1)
