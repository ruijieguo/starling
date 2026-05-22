# M0.0 ProfileCapability Skeleton 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭出 Starling Memory 的 C++20 + pybind11 项目骨架，落地 ProfileCapability 声明 / preflight 校验 / final query assertion guard / testing helper marker / CI 静态扫描五项 P1 出货门槛能力，并通过 TC-NEW-PREFLIGHT [CRITICAL]。

**Architecture:** CMake + Ninja 编译 C++20 静态库 `starling_core`；pybind11 暴露 Python 模块 `starling._core`；preflight 在进程启动期读取 capability declaration，缺一即 `RuntimeHealth = UNREADY` 并以退出码 78 fail-closed；final query assertion 在 Adapter 抽象层拒收缺 `tenant_id` / `holder_scope` 谓词的 SQL；testing helper 命名空间通过运行时 marker + CI grep 双防线隔离。

**Tech Stack:**
- C++20（CMake 3.27+ / Ninja / clang 17+ 或 gcc 13+）
- pybind11 2.13（vendored 子模块或系统包）
- GoogleTest 1.15（C++ 单测）
- pytest 8.x + pytest-mock（Python 单测）
- clang-tidy + clang-format（代码质量）
- Address/UB Sanitizer（debug build）
- 仅本地仓库；不引入外部数据库依赖（M0.0 不连任何 store）

**M0.0 不涉及**：SQLite / outbox（M0.2）、Schema 字段（M0.1）、LLM 调用（M0.4）。本里程碑是纯骨架 + 启动门槛。

**设计文档锚点**：
- system_design.md §15.2（M0.0 出货项）/ §15.3.4 TC-NEW-PREFLIGHT
- subsystems_design/04_substrate.md §"Capability 声明" / §"preflight 启动流程" / §"testing helper 双防线"
- subsystems_design/05_governance.md §"RuntimeHealth 状态机"

---

## 文件结构

> 本里程碑创建/修改的所有文件，每个职责单一、< 200 行（除自动生成的配置）。

```
starling/
├── CMakeLists.txt                                # 顶层 CMake
├── pyproject.toml                                # Python 包配置（PEP 621）
├── .clang-format                                 # C++ 代码风格
├── .clang-tidy                                   # C++ 静态检查规则
├── .github/workflows/ci.yml                      # CI（C++ 构建 + pytest + 静态扫描）
├── cmake/
│   └── StarlingOptions.cmake                     # 编译选项（warnings / sanitizers）
├── include/starling/
│   ├── profile_capability.hpp                    # ProfileCapability struct
│   ├── preflight.hpp                             # PreflightResult + preflight() 声明
│   ├── runtime_health.hpp                        # RuntimeHealth enum + state event
│   ├── adapter.hpp                               # Adapter 抽象基类（仅 declare_capability + final_query 钩子）
│   └── testing_marker.hpp                        # kStarlingTestingOnly 常量
├── src/
│   ├── preflight.cpp                             # preflight 校验实现
│   ├── final_query_assertion.cpp                 # final query 谓词检查
│   └── runtime_health.cpp                        # RuntimeHealth 状态机最小版
├── src/testing/
│   └── testing_marker.cpp                        # kStarlingTestingOnly = true 的实现单元
├── bindings/python/
│   ├── CMakeLists.txt                            # pybind11 子项目
│   └── module.cpp                                # 暴露 starling._core
├── python/starling/
│   ├── __init__.py                               # 公共 API re-export
│   ├── _core.pyi                                 # 类型存根
│   └── testing/
│       └── __init__.py                           # 子包 marker
├── tests/cpp/
│   ├── CMakeLists.txt                            # GoogleTest 配置
│   ├── test_profile_capability.cpp               # struct 默认值 + 序列化
│   ├── test_preflight.cpp                        # capability_has + preflight 决策
│   ├── test_final_query_assertion.cpp            # 缺谓词拒收
│   └── test_runtime_health.cpp                   # 状态机迁移
├── tests/python/
│   ├── conftest.py                               # 共享 fixture
│   ├── test_profile_capability.py                # binding 行为一致性
│   ├── test_preflight.py                         # binding preflight
│   ├── test_tc_new_preflight.py                  # TC-NEW-PREFLIGHT [CRITICAL] 完整覆盖
│   └── test_testing_marker_isolation.py          # 防线 2：运行时 marker
├── scripts/
│   └── ci_static_scan.py                         # 防线 1：grep 检查 prod entrypoint
└── docs/superpowers/plans/
    └── 2026-05-23-m0-0-profilecapability-skeleton.md  # 本文件
```

---

## Task 1: 项目骨架 (CMake + pybind11 + pytest)

**Files:**
- Create: `CMakeLists.txt`
- Create: `pyproject.toml`
- Create: `.clang-format`
- Create: `.clang-tidy`
- Create: `cmake/StarlingOptions.cmake`
- Create: `include/starling/version.hpp`
- Create: `bindings/python/CMakeLists.txt`
- Create: `bindings/python/module.cpp`
- Create: `python/starling/__init__.py`
- Create: `python/starling/_core.pyi`
- Create: `tests/cpp/CMakeLists.txt`
- Create: `tests/cpp/test_smoke.cpp`
- Create: `tests/python/conftest.py`
- Create: `tests/python/test_smoke.py`

- [ ] **Step 1: 写 CMake 顶层 + 选项**

`CMakeLists.txt`:
```cmake
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
```

`cmake/StarlingOptions.cmake`:
```cmake
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
```

- [ ] **Step 2: 写 pyproject.toml + Python 包占位**

`pyproject.toml`:
```toml
[build-system]
requires = ["scikit-build-core>=0.10", "pybind11>=2.13"]
build-backend = "scikit_build_core.build"

[project]
name = "starling-memory"
version = "0.0.1"
description = "Starling Memory — agent memory with multi-subject social mind"
requires-python = ">=3.11"
readme = "README.md"

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-mock>=3.12"]

[tool.scikit-build]
cmake.version = ">=3.27"
wheel.packages = ["python/starling"]
cmake.args = ["-DSTARLING_BUILD_PYTHON=ON"]

[tool.pytest.ini_options]
testpaths = ["tests/python"]
addopts = "-ra -v"
```

`python/starling/__init__.py`:
```python
"""Starling Memory public API."""
from starling import _core

__all__ = ["_core"]
__version__ = "0.0.1"
```

`python/starling/_core.pyi`: 留空文件（Step 4 起逐 task 增量补类型）

- [ ] **Step 3: 写 pybind11 stub 模块**

`bindings/python/CMakeLists.txt`:
```cmake
find_package(Python 3.11 COMPONENTS Interpreter Development.Module REQUIRED)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_core MODULE module.cpp)
target_link_libraries(_core PRIVATE starling_core)
target_compile_options(_core PRIVATE ${STARLING_WARNING_FLAGS})

set_target_properties(_core PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/python/starling
)

install(TARGETS _core DESTINATION starling)
```

`bindings/python/module.cpp`:
```cpp
#include <pybind11/pybind11.h>

#include "starling/version.hpp"

namespace py = pybind11;

PYBIND11_MODULE(_core, m) {
    m.doc() = "Starling Memory C++ core bindings";
    m.attr("__version__") = STARLING_VERSION_STRING;
}
```

`include/starling/version.hpp`:
```cpp
#pragma once

#define STARLING_VERSION_MAJOR 0
#define STARLING_VERSION_MINOR 0
#define STARLING_VERSION_PATCH 1
#define STARLING_VERSION_STRING "0.0.1"
```

- [ ] **Step 4: 写 C++ smoke test (GoogleTest)**

`tests/cpp/CMakeLists.txt`:
```cmake
include(FetchContent)
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.15.2
)
FetchContent_MakeAvailable(googletest)

add_executable(starling_tests
    test_smoke.cpp
)
target_link_libraries(starling_tests PRIVATE starling_core GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(starling_tests)
```

`tests/cpp/test_smoke.cpp`:
```cpp
#include <gtest/gtest.h>

#include "starling/version.hpp"

TEST(Smoke, VersionDefined) {
    EXPECT_STREQ(STARLING_VERSION_STRING, "0.0.1");
}
```

- [ ] **Step 5: 写 Python smoke test**

`tests/python/conftest.py`:
```python
import pytest


@pytest.fixture
def core():
    from starling import _core
    return _core
```

`tests/python/test_smoke.py`:
```python
def test_version_attribute(core):
    assert core.__version__ == "0.0.1"
```

- [ ] **Step 6: 写 .clang-format + .clang-tidy**

`.clang-format`:
```yaml
BasedOnStyle: Google
ColumnLimit: 100
IndentWidth: 4
PointerAlignment: Left
AllowShortFunctionsOnASingleLine: Inline
SortIncludes: CaseSensitive
```

`.clang-tidy`:
```yaml
Checks: >
  -*,
  bugprone-*,
  cert-*,
  clang-analyzer-*,
  cppcoreguidelines-*,
  modernize-*,
  performance-*,
  readability-*,
  -modernize-use-trailing-return-type,
  -readability-magic-numbers,
  -cppcoreguidelines-avoid-magic-numbers,
  -cppcoreguidelines-pro-bounds-array-to-pointer-decay
WarningsAsErrors: '*'
HeaderFilterRegex: 'include/starling/.*'
```

- [ ] **Step 7: 构建 + 跑测试，验证骨架编译**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build
cd build && ctest --output-on-failure
cd ..
pip install -e ".[dev]"
pytest
```

Expected:
- `cmake --build`: success, `starling_core.a` + `_core.cpython-*.so` 生成
- `ctest`: 1/1 passed (Smoke.VersionDefined)
- `pytest`: 1 passed (test_version_attribute)

- [ ] **Step 8: Commit**

```bash
git add CMakeLists.txt pyproject.toml .clang-format .clang-tidy \
        cmake include bindings python tests
git commit -m "feat(M0.0): project skeleton — CMake + pybind11 + GoogleTest + pytest"
```

---

## Task 2: ProfileCapability struct + Adapter 抽象

**Files:**
- Create: `include/starling/profile_capability.hpp`
- Create: `include/starling/adapter.hpp`
- Create: `tests/cpp/test_profile_capability.cpp`
- Modify: `tests/cpp/CMakeLists.txt`（加入 test_profile_capability.cpp）
- Modify: `bindings/python/module.cpp`（暴露 ProfileCapability）
- Create: `tests/python/test_profile_capability.py`

- [ ] **Step 1: 写失败测试 (C++)**

`tests/cpp/test_profile_capability.cpp`:
```cpp
#include <gtest/gtest.h>

#include "starling/profile_capability.hpp"

using starling::ProfileCapability;

TEST(ProfileCapability, DefaultsAreFailClosed) {
    ProfileCapability cap;
    EXPECT_TRUE(cap.profile_name.empty());
    EXPECT_FALSE(cap.cross_partition_transaction);
    EXPECT_FALSE(cap.transactional_outbox);
    EXPECT_FALSE(cap.consumer_checkpoint);
    EXPECT_FALSE(cap.engram_per_record_key);
    EXPECT_FALSE(cap.c_plus_plus_core);
    EXPECT_FALSE(cap.testing_helper_marker);
    EXPECT_EQ(cap.tenant_isolation, "");
}

TEST(ProfileCapability, LocalStoreProfilePopulatesAllFields) {
    ProfileCapability cap{
        .profile_name = "local-store",
        .relational_backend = "seekdb",
        .vector_backend = "seekdb",
        .graph_backend = "ladybugdb",
        .c_plus_plus_core = true,
        .cross_partition_transaction = true,
        .transactional_outbox = true,
        .consumer_checkpoint = true,
        .tenant_isolation = "storage_enforced",
        .engram_per_record_key = true,
        .engram_refcount = true,
        .projection_index_supported = false,
        .dimension_versions_supported = false,
        .testing_helper_marker = true,
    };
    EXPECT_EQ(cap.profile_name, "local-store");
    EXPECT_TRUE(cap.cross_partition_transaction);
    EXPECT_EQ(cap.tenant_isolation, "storage_enforced");
}
```

Modify `tests/cpp/CMakeLists.txt` — add `test_profile_capability.cpp` to `add_executable(starling_tests ...)`.

- [ ] **Step 2: 跑测试，确认失败**

Run: `cmake --build build && cd build && ctest -R ProfileCapability --output-on-failure`
Expected: FAIL — `starling/profile_capability.hpp` 不存在。

- [ ] **Step 3: 写 ProfileCapability struct**

`include/starling/profile_capability.hpp`:
```cpp
#pragma once

#include <string>

namespace starling {

// Capability declaration produced by every Adapter at startup.
// Source of truth: subsystems_design/04_substrate.md "Capability 声明".
// Defaults are intentionally fail-closed (all bools false, strings empty).
struct ProfileCapability {
    std::string profile_name;

    std::string relational_backend;
    std::string vector_backend;
    std::string graph_backend;

    bool c_plus_plus_core = false;

    bool cross_partition_transaction = false;
    bool transactional_outbox = false;
    bool consumer_checkpoint = false;

    std::string tenant_isolation;  // "app_filter" | "storage_enforced"

    bool engram_per_record_key = false;
    bool engram_refcount = false;

    bool projection_index_supported = false;
    bool dimension_versions_supported = false;

    bool testing_helper_marker = false;
};

}  // namespace starling
```

- [ ] **Step 4: 写 Adapter 抽象基类**

`include/starling/adapter.hpp`:
```cpp
#pragma once

#include <string>

#include "starling/profile_capability.hpp"

namespace starling {

// Minimal Adapter contract for M0.0. Concrete backends arrive in M0.2.
// Today the abstract class only fixes the two contracts every adapter must honor:
// (1) declare_capability returns the ProfileCapability used by preflight,
// (2) check_final_query gates every read/write SQL against tenant + holder predicates.
class Adapter {
public:
    virtual ~Adapter() = default;

    virtual ProfileCapability declare_capability() const = 0;

    // Returns true if the SQL string contains required tenant_id and holder_scope predicates.
    // Used by final_query_assertion. Concrete adapters should call this before issuing queries.
    virtual bool check_final_query(const std::string& sql) const = 0;
};

}  // namespace starling
```

- [ ] **Step 5: 跑测试，确认通过**

Run: `cmake --build build && cd build && ctest -R ProfileCapability --output-on-failure`
Expected: PASS — 2/2 tests.

- [ ] **Step 6: 写 Python binding 失败测试**

`tests/python/test_profile_capability.py`:
```python
def test_profile_capability_defaults_fail_closed(core):
    cap = core.ProfileCapability()
    assert cap.profile_name == ""
    assert cap.cross_partition_transaction is False
    assert cap.transactional_outbox is False
    assert cap.tenant_isolation == ""


def test_profile_capability_local_store_construct(core):
    cap = core.ProfileCapability(
        profile_name="local-store",
        relational_backend="seekdb",
        vector_backend="seekdb",
        graph_backend="ladybugdb",
        c_plus_plus_core=True,
        cross_partition_transaction=True,
        transactional_outbox=True,
        consumer_checkpoint=True,
        tenant_isolation="storage_enforced",
        engram_per_record_key=True,
        engram_refcount=True,
        projection_index_supported=False,
        dimension_versions_supported=False,
        testing_helper_marker=True,
    )
    assert cap.profile_name == "local-store"
    assert cap.tenant_isolation == "storage_enforced"
```

Run: `pytest tests/python/test_profile_capability.py -v`
Expected: FAIL — `core` 模块不暴露 `ProfileCapability`。

- [ ] **Step 7: 暴露 ProfileCapability 到 Python**

Modify `bindings/python/module.cpp`:
```cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "starling/profile_capability.hpp"
#include "starling/version.hpp"

namespace py = pybind11;

PYBIND11_MODULE(_core, m) {
    m.doc() = "Starling Memory C++ core bindings";
    m.attr("__version__") = STARLING_VERSION_STRING;

    py::class_<starling::ProfileCapability>(m, "ProfileCapability")
        .def(py::init<>())
        .def(py::init([](std::string profile_name,
                          std::string relational_backend,
                          std::string vector_backend,
                          std::string graph_backend,
                          bool c_plus_plus_core,
                          bool cross_partition_transaction,
                          bool transactional_outbox,
                          bool consumer_checkpoint,
                          std::string tenant_isolation,
                          bool engram_per_record_key,
                          bool engram_refcount,
                          bool projection_index_supported,
                          bool dimension_versions_supported,
                          bool testing_helper_marker) {
                  return starling::ProfileCapability{
                      .profile_name = std::move(profile_name),
                      .relational_backend = std::move(relational_backend),
                      .vector_backend = std::move(vector_backend),
                      .graph_backend = std::move(graph_backend),
                      .c_plus_plus_core = c_plus_plus_core,
                      .cross_partition_transaction = cross_partition_transaction,
                      .transactional_outbox = transactional_outbox,
                      .consumer_checkpoint = consumer_checkpoint,
                      .tenant_isolation = std::move(tenant_isolation),
                      .engram_per_record_key = engram_per_record_key,
                      .engram_refcount = engram_refcount,
                      .projection_index_supported = projection_index_supported,
                      .dimension_versions_supported = dimension_versions_supported,
                      .testing_helper_marker = testing_helper_marker,
                  };
              }),
              py::kw_only(),
              py::arg("profile_name") = "",
              py::arg("relational_backend") = "",
              py::arg("vector_backend") = "",
              py::arg("graph_backend") = "",
              py::arg("c_plus_plus_core") = false,
              py::arg("cross_partition_transaction") = false,
              py::arg("transactional_outbox") = false,
              py::arg("consumer_checkpoint") = false,
              py::arg("tenant_isolation") = "",
              py::arg("engram_per_record_key") = false,
              py::arg("engram_refcount") = false,
              py::arg("projection_index_supported") = false,
              py::arg("dimension_versions_supported") = false,
              py::arg("testing_helper_marker") = false)
        .def_readwrite("profile_name", &starling::ProfileCapability::profile_name)
        .def_readwrite("relational_backend",
                       &starling::ProfileCapability::relational_backend)
        .def_readwrite("vector_backend", &starling::ProfileCapability::vector_backend)
        .def_readwrite("graph_backend", &starling::ProfileCapability::graph_backend)
        .def_readwrite("c_plus_plus_core",
                       &starling::ProfileCapability::c_plus_plus_core)
        .def_readwrite("cross_partition_transaction",
                       &starling::ProfileCapability::cross_partition_transaction)
        .def_readwrite("transactional_outbox",
                       &starling::ProfileCapability::transactional_outbox)
        .def_readwrite("consumer_checkpoint",
                       &starling::ProfileCapability::consumer_checkpoint)
        .def_readwrite("tenant_isolation",
                       &starling::ProfileCapability::tenant_isolation)
        .def_readwrite("engram_per_record_key",
                       &starling::ProfileCapability::engram_per_record_key)
        .def_readwrite("engram_refcount",
                       &starling::ProfileCapability::engram_refcount)
        .def_readwrite("projection_index_supported",
                       &starling::ProfileCapability::projection_index_supported)
        .def_readwrite("dimension_versions_supported",
                       &starling::ProfileCapability::dimension_versions_supported)
        .def_readwrite("testing_helper_marker",
                       &starling::ProfileCapability::testing_helper_marker);
}
```

- [ ] **Step 8: 跑 Python 测试，确认通过**

Run: `cmake --build build && pip install -e . --no-deps --force-reinstall && pytest tests/python/test_profile_capability.py -v`
Expected: PASS — 2/2 tests.

- [ ] **Step 9: Commit**

```bash
git add include/starling/profile_capability.hpp \
        include/starling/adapter.hpp \
        bindings/python/module.cpp \
        tests/cpp/CMakeLists.txt \
        tests/cpp/test_profile_capability.cpp \
        tests/python/test_profile_capability.py
git commit -m "feat(M0.0): ProfileCapability struct + Adapter base + Python binding"
```

---

## Task 3: RuntimeHealth 状态机（最小版）

**Files:**
- Create: `include/starling/runtime_health.hpp`
- Create: `src/runtime_health.cpp`
- Modify: `CMakeLists.txt`（src/runtime_health.cpp 已在 Task 1 列出）
- Create: `tests/cpp/test_runtime_health.cpp`
- Modify: `tests/cpp/CMakeLists.txt`
- Modify: `bindings/python/module.cpp`（暴露 enum）
- Create: `tests/python/test_runtime_health.py`

- [ ] **Step 1: 写 C++ 失败测试**

`tests/cpp/test_runtime_health.cpp`:
```cpp
#include <gtest/gtest.h>

#include "starling/runtime_health.hpp"

using starling::RuntimeHealth;
using starling::RuntimeHealthMonitor;

TEST(RuntimeHealth, StartsUnready) {
    RuntimeHealthMonitor monitor;
    EXPECT_EQ(monitor.state(), RuntimeHealth::UNREADY);
}

TEST(RuntimeHealth, TransitionToReadyEmitsEvent) {
    RuntimeHealthMonitor monitor;
    bool event_seen = false;
    monitor.on_change([&](RuntimeHealth from, RuntimeHealth to,
                          const std::vector<std::string>& missing) {
        EXPECT_EQ(from, RuntimeHealth::UNREADY);
        EXPECT_EQ(to, RuntimeHealth::READY);
        EXPECT_TRUE(missing.empty());
        event_seen = true;
    });
    monitor.set_ready();
    EXPECT_EQ(monitor.state(), RuntimeHealth::READY);
    EXPECT_TRUE(event_seen);
}

TEST(RuntimeHealth, SetUnreadyCarriesMissingCapabilities) {
    RuntimeHealthMonitor monitor;
    std::vector<std::string> captured;
    monitor.on_change([&](RuntimeHealth, RuntimeHealth,
                          const std::vector<std::string>& missing) {
        captured = missing;
    });
    monitor.set_unready({"transactional_outbox", "idx_statement_id_tenant"});
    EXPECT_EQ(monitor.state(), RuntimeHealth::UNREADY);
    EXPECT_EQ(captured.size(), 2);
    EXPECT_EQ(captured[0], "transactional_outbox");
}
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cmake --build build && cd build && ctest -R RuntimeHealth --output-on-failure`
Expected: FAIL — header 不存在。

- [ ] **Step 3: 写 RuntimeHealth header + impl**

`include/starling/runtime_health.hpp`:
```cpp
#pragma once

#include <functional>
#include <string>
#include <vector>

namespace starling {

// 4-state runtime health, per subsystems_design/05_governance.md.
// M0.0 implements UNREADY <-> READY only; DEGRADED / DRAINING arrive in P2 with
// background scheduling. Forward-declared here so later milestones extend without
// breaking signatures.
enum class RuntimeHealth {
    UNREADY = 0,
    READY = 1,
    DEGRADED = 2,
    DRAINING = 3,
};

class RuntimeHealthMonitor {
public:
    using ChangeListener = std::function<void(RuntimeHealth from, RuntimeHealth to,
                                              const std::vector<std::string>& missing)>;

    RuntimeHealthMonitor() = default;

    RuntimeHealth state() const noexcept { return state_; }

    void on_change(ChangeListener listener);

    void set_ready();
    void set_unready(std::vector<std::string> missing_capabilities);

private:
    RuntimeHealth state_ = RuntimeHealth::UNREADY;
    ChangeListener listener_;
};

}  // namespace starling
```

`src/runtime_health.cpp`:
```cpp
#include "starling/runtime_health.hpp"

#include <utility>

namespace starling {

void RuntimeHealthMonitor::on_change(ChangeListener listener) {
    listener_ = std::move(listener);
}

void RuntimeHealthMonitor::set_ready() {
    const RuntimeHealth from = state_;
    state_ = RuntimeHealth::READY;
    if (listener_) {
        listener_(from, state_, {});
    }
}

void RuntimeHealthMonitor::set_unready(std::vector<std::string> missing_capabilities) {
    const RuntimeHealth from = state_;
    state_ = RuntimeHealth::UNREADY;
    if (listener_) {
        listener_(from, state_, std::move(missing_capabilities));
    }
}

}  // namespace starling
```

- [ ] **Step 4: 跑测试，确认通过**

Run: `cmake --build build && cd build && ctest -R RuntimeHealth --output-on-failure`
Expected: PASS — 3/3 tests.

- [ ] **Step 5: 暴露 enum 到 Python + 写测试**

Append to `bindings/python/module.cpp` 在 `PYBIND11_MODULE` 内：
```cpp
    py::enum_<starling::RuntimeHealth>(m, "RuntimeHealth")
        .value("UNREADY", starling::RuntimeHealth::UNREADY)
        .value("READY", starling::RuntimeHealth::READY)
        .value("DEGRADED", starling::RuntimeHealth::DEGRADED)
        .value("DRAINING", starling::RuntimeHealth::DRAINING);
```

`tests/python/test_runtime_health.py`:
```python
def test_runtime_health_enum_exposed(core):
    assert int(core.RuntimeHealth.UNREADY) == 0
    assert int(core.RuntimeHealth.READY) == 1
    assert int(core.RuntimeHealth.DEGRADED) == 2
    assert int(core.RuntimeHealth.DRAINING) == 3
```

Run: `cmake --build build && pip install -e . --no-deps --force-reinstall && pytest tests/python/test_runtime_health.py -v`
Expected: PASS — 1/1.

- [ ] **Step 6: Commit**

```bash
git add include/starling/runtime_health.hpp src/runtime_health.cpp \
        bindings/python/module.cpp \
        tests/cpp/CMakeLists.txt tests/cpp/test_runtime_health.cpp \
        tests/python/test_runtime_health.py
git commit -m "feat(M0.0): RuntimeHealth monitor — UNREADY/READY transitions with listener"
```

---

## Task 4: preflight 校验

**Files:**
- Create: `include/starling/preflight.hpp`
- Create: `src/preflight.cpp`
- Create: `tests/cpp/test_preflight.cpp`
- Modify: `tests/cpp/CMakeLists.txt`
- Modify: `bindings/python/module.cpp`
- Create: `tests/python/test_preflight.py`

- [ ] **Step 1: 写 C++ 失败测试**

`tests/cpp/test_preflight.cpp`:
```cpp
#include <gtest/gtest.h>

#include "starling/preflight.hpp"
#include "starling/profile_capability.hpp"

using starling::PreflightResult;
using starling::PreflightStatus;
using starling::ProfileCapability;
using starling::preflight;

namespace {

ProfileCapability make_local_store() {
    return ProfileCapability{
        .profile_name = "local-store",
        .relational_backend = "seekdb",
        .vector_backend = "seekdb",
        .graph_backend = "ladybugdb",
        .c_plus_plus_core = true,
        .cross_partition_transaction = true,
        .transactional_outbox = true,
        .consumer_checkpoint = true,
        .tenant_isolation = "storage_enforced",
        .engram_per_record_key = true,
        .engram_refcount = true,
        .projection_index_supported = false,
        .dimension_versions_supported = false,
        .testing_helper_marker = true,
    };
}

}  // namespace

TEST(Preflight, FullyCapableLocalStoreReturnsReady) {
    auto cap = make_local_store();
    auto required = std::vector<std::string>{
        "transactional_outbox",
        "consumer_checkpoint",
        "engram_per_record_key",
        "c_plus_plus_core",
        "tenant_isolation_storage_enforced",
        "cross_partition_transaction",
    };
    PreflightResult result = preflight(cap, required);
    EXPECT_EQ(result.status, PreflightStatus::READY);
    EXPECT_TRUE(result.missing.empty());
}

TEST(Preflight, MissingTransactionalOutboxReturnsUnready) {
    auto cap = make_local_store();
    cap.transactional_outbox = false;
    PreflightResult result = preflight(cap, {"transactional_outbox"});
    EXPECT_EQ(result.status, PreflightStatus::UNREADY);
    ASSERT_EQ(result.missing.size(), 1);
    EXPECT_EQ(result.missing[0], "transactional_outbox");
}

TEST(Preflight, AppFilterFailsStorageEnforcedRequirement) {
    auto cap = make_local_store();
    cap.tenant_isolation = "app_filter";
    PreflightResult result =
        preflight(cap, {"tenant_isolation_storage_enforced"});
    EXPECT_EQ(result.status, PreflightStatus::UNREADY);
    ASSERT_EQ(result.missing.size(), 1);
    EXPECT_EQ(result.missing[0], "tenant_isolation_storage_enforced");
}

TEST(Preflight, MissingCrossPartitionTransactionFailsLocalAtomic) {
    auto cap = make_local_store();
    cap.cross_partition_transaction = false;
    PreflightResult result = preflight(cap, {"cross_partition_transaction"});
    EXPECT_EQ(result.status, PreflightStatus::UNREADY);
    ASSERT_EQ(result.missing.size(), 1);
    EXPECT_EQ(result.missing[0], "cross_partition_transaction");
}

TEST(Preflight, TestingHelperMarkerMissingFailsLocalStore) {
    auto cap = make_local_store();
    cap.testing_helper_marker = false;
    PreflightResult result = preflight(cap, {"testing_helper_marker"});
    EXPECT_EQ(result.status, PreflightStatus::UNREADY);
}

TEST(Preflight, MultipleMissingPreservesOrder) {
    ProfileCapability cap;  // all defaults = false
    PreflightResult result = preflight(cap, {
        "transactional_outbox",
        "consumer_checkpoint",
        "engram_per_record_key",
    });
    EXPECT_EQ(result.status, PreflightStatus::UNREADY);
    ASSERT_EQ(result.missing.size(), 3);
    EXPECT_EQ(result.missing[0], "transactional_outbox");
    EXPECT_EQ(result.missing[1], "consumer_checkpoint");
    EXPECT_EQ(result.missing[2], "engram_per_record_key");
}
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cmake --build build && cd build && ctest -R Preflight --output-on-failure`
Expected: FAIL — header 不存在。

- [ ] **Step 3: 写 preflight header + impl**

`include/starling/preflight.hpp`:
```cpp
#pragma once

#include <string>
#include <vector>

#include "starling/profile_capability.hpp"

namespace starling {

enum class PreflightStatus {
    READY,
    UNREADY,
};

struct PreflightResult {
    PreflightStatus status;
    std::vector<std::string> missing;  // capability names absent in declaration
};

// Capability requirement names recognized by preflight (string-keyed for ease of
// listing in config + future extensibility):
//
//   "transactional_outbox"                     -> ProfileCapability::transactional_outbox
//   "consumer_checkpoint"                      -> ProfileCapability::consumer_checkpoint
//   "engram_per_record_key"                    -> ProfileCapability::engram_per_record_key
//   "c_plus_plus_core"                         -> ProfileCapability::c_plus_plus_core
//   "cross_partition_transaction"              -> ProfileCapability::cross_partition_transaction
//   "engram_refcount"                          -> ProfileCapability::engram_refcount
//   "projection_index_supported"               -> P2 only
//   "dimension_versions_supported"             -> P3 only
//   "tenant_isolation_storage_enforced"        -> tenant_isolation == "storage_enforced"
//   "testing_helper_marker"                    -> testing_helper_marker
//
// Unknown capability names are treated as missing (fail-closed).
PreflightResult preflight(const ProfileCapability& declared,
                          const std::vector<std::string>& required);

}  // namespace starling
```

`src/preflight.cpp`:
```cpp
#include "starling/preflight.hpp"

#include <string_view>

namespace starling {
namespace {

bool capability_has(const ProfileCapability& cap, std::string_view name) {
    if (name == "transactional_outbox") return cap.transactional_outbox;
    if (name == "consumer_checkpoint") return cap.consumer_checkpoint;
    if (name == "engram_per_record_key") return cap.engram_per_record_key;
    if (name == "c_plus_plus_core") return cap.c_plus_plus_core;
    if (name == "cross_partition_transaction") return cap.cross_partition_transaction;
    if (name == "engram_refcount") return cap.engram_refcount;
    if (name == "projection_index_supported") return cap.projection_index_supported;
    if (name == "dimension_versions_supported") return cap.dimension_versions_supported;
    if (name == "tenant_isolation_storage_enforced") {
        return cap.tenant_isolation == "storage_enforced";
    }
    if (name == "testing_helper_marker") return cap.testing_helper_marker;
    return false;  // unknown -> fail-closed
}

}  // namespace

PreflightResult preflight(const ProfileCapability& declared,
                          const std::vector<std::string>& required) {
    std::vector<std::string> missing;
    missing.reserve(required.size());
    for (const auto& cap_name : required) {
        if (!capability_has(declared, cap_name)) {
            missing.push_back(cap_name);
        }
    }
    if (!missing.empty()) {
        return {PreflightStatus::UNREADY, std::move(missing)};
    }
    return {PreflightStatus::READY, {}};
}

}  // namespace starling
```

- [ ] **Step 4: 跑测试，确认通过**

Run: `cmake --build build && cd build && ctest -R Preflight --output-on-failure`
Expected: PASS — 6/6 tests.

- [ ] **Step 5: 暴露 preflight 到 Python**

Append to `bindings/python/module.cpp` 内（PYBIND11_MODULE 块内）：
```cpp
    #include "starling/preflight.hpp"  // top of file

    py::enum_<starling::PreflightStatus>(m, "PreflightStatus")
        .value("READY", starling::PreflightStatus::READY)
        .value("UNREADY", starling::PreflightStatus::UNREADY);

    py::class_<starling::PreflightResult>(m, "PreflightResult")
        .def_readonly("status", &starling::PreflightResult::status)
        .def_readonly("missing", &starling::PreflightResult::missing);

    m.def("preflight", &starling::preflight,
          py::arg("declared"), py::arg("required"),
          "Validate a ProfileCapability against required capability names. "
          "Unknown names are treated as missing (fail-closed).");
```

(Move the `#include` to file top.)

- [ ] **Step 6: 写 Python preflight 测试**

`tests/python/test_preflight.py`:
```python
def _local_store(core):
    return core.ProfileCapability(
        profile_name="local-store",
        relational_backend="seekdb",
        vector_backend="seekdb",
        graph_backend="ladybugdb",
        c_plus_plus_core=True,
        cross_partition_transaction=True,
        transactional_outbox=True,
        consumer_checkpoint=True,
        tenant_isolation="storage_enforced",
        engram_per_record_key=True,
        engram_refcount=True,
        testing_helper_marker=True,
    )


def test_preflight_full_capability_returns_ready(core):
    cap = _local_store(core)
    result = core.preflight(cap, [
        "transactional_outbox",
        "consumer_checkpoint",
        "engram_per_record_key",
        "c_plus_plus_core",
        "tenant_isolation_storage_enforced",
        "cross_partition_transaction",
    ])
    assert result.status == core.PreflightStatus.READY
    assert result.missing == []


def test_preflight_missing_outbox_returns_unready(core):
    cap = _local_store(core)
    cap.transactional_outbox = False
    result = core.preflight(cap, ["transactional_outbox"])
    assert result.status == core.PreflightStatus.UNREADY
    assert result.missing == ["transactional_outbox"]


def test_preflight_app_filter_blocks_storage_enforced(core):
    cap = _local_store(core)
    cap.tenant_isolation = "app_filter"
    result = core.preflight(cap, ["tenant_isolation_storage_enforced"])
    assert result.status == core.PreflightStatus.UNREADY
    assert result.missing == ["tenant_isolation_storage_enforced"]


def test_preflight_unknown_capability_treated_as_missing(core):
    cap = _local_store(core)
    result = core.preflight(cap, ["totally_made_up_capability"])
    assert result.status == core.PreflightStatus.UNREADY
    assert result.missing == ["totally_made_up_capability"]
```

Run: `cmake --build build && pip install -e . --no-deps --force-reinstall && pytest tests/python/test_preflight.py -v`
Expected: PASS — 4/4.

- [ ] **Step 7: Commit**

```bash
git add include/starling/preflight.hpp src/preflight.cpp \
        bindings/python/module.cpp \
        tests/cpp/CMakeLists.txt tests/cpp/test_preflight.cpp \
        tests/python/test_preflight.py
git commit -m "feat(M0.0): preflight capability matcher with fail-closed unknown handling"
```

---

## Task 5: final query assertion guard

**Files:**
- Create: `include/starling/final_query_assertion.hpp`
- Create: `src/final_query_assertion.cpp`
- Create: `tests/cpp/test_final_query_assertion.cpp`
- Modify: `tests/cpp/CMakeLists.txt`
- Modify: `bindings/python/module.cpp`
- Create: `tests/python/test_final_query_assertion.py`

- [ ] **Step 1: 写 C++ 失败测试**

`tests/cpp/test_final_query_assertion.cpp`:
```cpp
#include <gtest/gtest.h>

#include "starling/final_query_assertion.hpp"

using starling::assert_final_query_safe;
using starling::FinalQueryAssertionError;

TEST(FinalQueryAssertion, AcceptsQueryWithBothPredicates) {
    EXPECT_NO_THROW(assert_final_query_safe(
        "SELECT id FROM statements "
        "WHERE tenant_id = ? AND holder_scope = ? AND consolidation_state = 'CONSOLIDATED'"));
}

TEST(FinalQueryAssertion, RejectsQueryMissingTenantId) {
    EXPECT_THROW(
        assert_final_query_safe(
            "SELECT id FROM statements WHERE holder_scope = ?"),
        FinalQueryAssertionError);
}

TEST(FinalQueryAssertion, RejectsQueryMissingHolderScope) {
    EXPECT_THROW(
        assert_final_query_safe(
            "SELECT id FROM statements WHERE tenant_id = ?"),
        FinalQueryAssertionError);
}

TEST(FinalQueryAssertion, RejectsBareSelectStar) {
    EXPECT_THROW(assert_final_query_safe("SELECT * FROM statements"),
                 FinalQueryAssertionError);
}

TEST(FinalQueryAssertion, IsCaseInsensitive) {
    EXPECT_NO_THROW(assert_final_query_safe(
        "select id from statements where Tenant_Id = ? and Holder_Scope = ?"));
}

TEST(FinalQueryAssertion, AcceptsParenthesizedPredicates) {
    EXPECT_NO_THROW(assert_final_query_safe(
        "SELECT id FROM statements "
        "WHERE (tenant_id = ?) AND (holder_scope IN (?, ?))"));
}

TEST(FinalQueryAssertion, RejectsOnlyInComment) {
    EXPECT_THROW(
        assert_final_query_safe(
            "SELECT * FROM statements -- tenant_id and holder_scope are mandatory"),
        FinalQueryAssertionError);
}

TEST(FinalQueryAssertion, ErrorMessageNamesMissingPredicates) {
    try {
        assert_final_query_safe("SELECT id FROM statements WHERE 1=1");
        FAIL() << "expected FinalQueryAssertionError";
    } catch (const FinalQueryAssertionError& err) {
        std::string what = err.what();
        EXPECT_NE(what.find("tenant_id"), std::string::npos);
        EXPECT_NE(what.find("holder_scope"), std::string::npos);
    }
}
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cmake --build build && cd build && ctest -R FinalQueryAssertion --output-on-failure`
Expected: FAIL — header 不存在。

- [ ] **Step 3: 写 final_query_assertion header + impl**

`include/starling/final_query_assertion.hpp`:
```cpp
#pragma once

#include <stdexcept>
#include <string>
#include <string_view>

namespace starling {

class FinalQueryAssertionError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

// Throws FinalQueryAssertionError if the SQL string lacks both required guard
// predicates: a tenant_id reference outside any -- comment AND a holder_scope
// reference outside any -- comment. Case-insensitive. Parenthesized predicates
// and IN(...) clauses are allowed.
//
// This is M0.0's runtime defense for TC-NEG-TENANT and TC-NEW-PREFLIGHT branch (c).
// Adapter implementations MUST call this before issuing any final SELECT/UPDATE/DELETE.
void assert_final_query_safe(std::string_view sql);

// Pure predicate variant for tests / programmatic checks. Returns true iff sql
// passes all guards.
bool is_final_query_safe(std::string_view sql) noexcept;

}  // namespace starling
```

`src/final_query_assertion.cpp`:
```cpp
#include "starling/final_query_assertion.hpp"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <string>

namespace starling {
namespace {

std::string strip_line_comments(std::string_view sql) {
    std::string out;
    out.reserve(sql.size());
    size_t i = 0;
    while (i < sql.size()) {
        if (i + 1 < sql.size() && sql[i] == '-' && sql[i + 1] == '-') {
            while (i < sql.size() && sql[i] != '\n') {
                ++i;
            }
        } else {
            out.push_back(sql[i]);
            ++i;
        }
    }
    return out;
}

std::string to_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return s;
}

}  // namespace

bool is_final_query_safe(std::string_view sql) noexcept {
    const std::string lowered = to_lower(strip_line_comments(sql));
    const bool has_tenant = lowered.find("tenant_id") != std::string::npos;
    const bool has_holder = lowered.find("holder_scope") != std::string::npos;
    return has_tenant && has_holder;
}

void assert_final_query_safe(std::string_view sql) {
    const std::string lowered = to_lower(strip_line_comments(sql));
    const bool has_tenant = lowered.find("tenant_id") != std::string::npos;
    const bool has_holder = lowered.find("holder_scope") != std::string::npos;
    if (has_tenant && has_holder) {
        return;
    }
    std::ostringstream msg;
    msg << "final query missing required guard predicates:";
    if (!has_tenant) msg << " tenant_id";
    if (!has_holder) msg << " holder_scope";
    throw FinalQueryAssertionError(msg.str());
}

}  // namespace starling
```

- [ ] **Step 4: 跑 C++ 测试，确认通过**

Run: `cmake --build build && cd build && ctest -R FinalQueryAssertion --output-on-failure`
Expected: PASS — 8/8.

- [ ] **Step 5: 暴露到 Python**

Append to `bindings/python/module.cpp`:
```cpp
    #include "starling/final_query_assertion.hpp"  // top of file

    py::register_exception<starling::FinalQueryAssertionError>(
        m, "FinalQueryAssertionError", PyExc_ValueError);

    m.def("assert_final_query_safe", &starling::assert_final_query_safe,
          py::arg("sql"),
          "Throws FinalQueryAssertionError if SQL lacks tenant_id + holder_scope "
          "predicates (outside SQL line comments).");

    m.def("is_final_query_safe",
          [](std::string_view sql) { return starling::is_final_query_safe(sql); },
          py::arg("sql"));
```

- [ ] **Step 6: 写 Python 测试**

`tests/python/test_final_query_assertion.py`:
```python
import pytest


def test_accepts_query_with_both_predicates(core):
    core.assert_final_query_safe(
        "SELECT id FROM statements WHERE tenant_id = ? AND holder_scope = ?"
    )
    assert core.is_final_query_safe(
        "SELECT id FROM statements WHERE tenant_id = ? AND holder_scope = ?"
    )


def test_rejects_missing_tenant_id(core):
    with pytest.raises(core.FinalQueryAssertionError) as exc:
        core.assert_final_query_safe(
            "SELECT id FROM statements WHERE holder_scope = ?"
        )
    assert "tenant_id" in str(exc.value)


def test_rejects_missing_holder_scope(core):
    with pytest.raises(core.FinalQueryAssertionError) as exc:
        core.assert_final_query_safe(
            "SELECT id FROM statements WHERE tenant_id = ?"
        )
    assert "holder_scope" in str(exc.value)


def test_rejects_only_in_comment(core):
    with pytest.raises(core.FinalQueryAssertionError):
        core.assert_final_query_safe(
            "SELECT * FROM statements -- tenant_id and holder_scope mandatory"
        )


def test_is_case_insensitive(core):
    assert core.is_final_query_safe(
        "select id from statements where Tenant_Id=? AND Holder_Scope=?"
    )
```

Run: `cmake --build build && pip install -e . --no-deps --force-reinstall && pytest tests/python/test_final_query_assertion.py -v`
Expected: PASS — 5/5.

- [ ] **Step 7: Commit**

```bash
git add include/starling/final_query_assertion.hpp src/final_query_assertion.cpp \
        bindings/python/module.cpp \
        tests/cpp/CMakeLists.txt tests/cpp/test_final_query_assertion.cpp \
        tests/python/test_final_query_assertion.py
git commit -m "feat(M0.0): final_query_assertion — reject SQL missing tenant_id/holder_scope"
```

---

## Task 6: testing helper marker（防线 2 — 运行时）

**Files:**
- Create: `include/starling/testing_marker.hpp`
- Create: `src/testing/testing_marker.cpp`
- Create: `python/starling/testing/__init__.py`
- Modify: `bindings/python/module.cpp`
- Create: `tests/python/test_testing_marker_isolation.py`

> **设计要点**：marker 是 testing-only 翻译单元中的常量。prod profile 不链接 `starling_testing_marker` target，因此该符号不存在于二进制；测试 / dev profile 显式链接它。M0.0 暴露一个 `core.testing_marker_loaded` 布尔，用于运行时检测。

- [ ] **Step 1: 写 marker header + 实现**

`include/starling/testing_marker.hpp`:
```cpp
#pragma once

namespace starling::testing {

// True iff the testing-only translation unit is linked into the current binary.
// Defined in a separate target (starling_testing_marker) that prod profiles MUST NOT
// link. preflight reads this at startup and refuses to enter READY when:
//   - profile == "prod" AND testing_marker_loaded() == true
//
// CI grep (defense-in-depth #1) further bans `starling::testing` references in prod
// entrypoints — see scripts/ci_static_scan.py.
bool testing_marker_loaded() noexcept;

}  // namespace starling::testing
```

`src/testing/testing_marker.cpp`:
```cpp
#include "starling/testing_marker.hpp"

namespace starling::testing {

bool testing_marker_loaded() noexcept { return true; }

}  // namespace starling::testing
```

- [ ] **Step 2: 修改 CMake — pybind 模块链接 testing 标记 target**

Modify `bindings/python/CMakeLists.txt` 末尾追加：
```cmake
# The Python module is the dev/test entrypoint and is allowed to link the marker.
target_link_libraries(_core PRIVATE starling_testing_marker)
```

> **不允许链接的目标**：未来任何 prod entrypoint（如 M0.7 部署的 daemon）须显式 *不* 链接 `starling_testing_marker`。CI grep（Task 7）防止意外引用。

- [ ] **Step 3: 暴露 marker 到 Python**

Append to `bindings/python/module.cpp`:
```cpp
    #include "starling/testing_marker.hpp"  // top of file

    auto testing_submodule = m.def_submodule("testing",
        "Testing-only helpers. Prod profiles MUST NOT link this submodule.");
    testing_submodule.def("marker_loaded", &starling::testing::testing_marker_loaded,
                          "True iff the testing-only translation unit is linked.");
```

- [ ] **Step 4: 写 Python testing 包占位**

`python/starling/testing/__init__.py`:
```python
"""Starling testing helpers — never import from production code paths."""
from starling._core import testing as _core_testing


def marker_loaded() -> bool:
    return _core_testing.marker_loaded()


__all__ = ["marker_loaded"]
```

- [ ] **Step 5: 写测试**

`tests/python/test_testing_marker_isolation.py`:
```python
def test_testing_marker_loaded_in_dev_build(core):
    # In M0.0, the dev/test build always links the marker target.
    assert core.testing.marker_loaded() is True


def test_testing_marker_via_python_helper():
    from starling.testing import marker_loaded
    assert marker_loaded() is True
```

Run: `cmake --build build && pip install -e . --no-deps --force-reinstall && pytest tests/python/test_testing_marker_isolation.py -v`
Expected: PASS — 2/2.

- [ ] **Step 6: Commit**

```bash
git add include/starling/testing_marker.hpp \
        src/testing/testing_marker.cpp \
        bindings/python/CMakeLists.txt bindings/python/module.cpp \
        python/starling/testing/__init__.py \
        tests/python/test_testing_marker_isolation.py
git commit -m "feat(M0.0): testing helper marker — runtime defense line for prod isolation"
```

---

## Task 7: CI 静态扫描（防线 1）

**Files:**
- Create: `scripts/ci_static_scan.py`
- Create: `.github/workflows/ci.yml`
- Create: `tests/python/test_ci_static_scan.py`

- [ ] **Step 1: 写 ci_static_scan 失败测试**

`tests/python/test_ci_static_scan.py`:
```python
import subprocess
import sys
from pathlib import Path
import textwrap

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER = REPO_ROOT / "scripts" / "ci_static_scan.py"


def _run_scanner(extra_args, cwd):
    return subprocess.run(
        [sys.executable, str(SCANNER), *extra_args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_scanner_passes_on_clean_tree(tmp_path):
    # Mirror minimum repo shape: a prod source file, a test source file.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "preflight.cpp").write_text(
        '#include "starling/preflight.hpp"\nvoid f() {}\n'
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_smoke.cpp").write_text(
        '#include "starling/testing_marker.hpp"\n'
        "namespace t = starling::testing;\n"
    )
    result = _run_scanner(
        ["--prod-roots", "src", "--allowed-roots", "tests"], cwd=tmp_path
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_scanner_fails_when_prod_imports_testing_namespace(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "leaky.cpp").write_text(
        textwrap.dedent("""\
            #include "starling/testing_marker.hpp"
            namespace t = starling::testing;
            void leak() { (void)t::testing_marker_loaded(); }
        """)
    )
    result = _run_scanner(["--prod-roots", "src"], cwd=tmp_path)
    assert result.returncode != 0
    assert "starling::testing" in result.stdout + result.stderr


def test_scanner_fails_when_prod_imports_python_testing(tmp_path):
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "app.py").write_text(
        "from starling.testing import marker_loaded\n"
    )
    result = _run_scanner(["--prod-roots", "python"], cwd=tmp_path)
    assert result.returncode != 0
    assert "starling.testing" in result.stdout + result.stderr


def test_scanner_allows_pyi_stub_with_block_comment(tmp_path):
    # .pyi files often re-export everything; scanner must not flag them when
    # the line is inside a doc comment marked NOLINT(starling-testing-isolation).
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "_core.pyi").write_text(
        '"""starling.testing helpers."""\n'
        "# NOLINT(starling-testing-isolation): re-export for type checkers only\n"
        "from starling.testing import marker_loaded as marker_loaded\n"
    )
    result = _run_scanner(["--prod-roots", "python"], cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
```

Run: `pytest tests/python/test_ci_static_scan.py -v`
Expected: FAIL — `scripts/ci_static_scan.py` 不存在。

- [ ] **Step 2: 写 ci_static_scan.py**

`scripts/ci_static_scan.py`:
```python
"""Defense-line #1: ban testing-namespace imports from prod entrypoints.

Scans configured prod roots for forbidden tokens:
  - `starling::testing`            (C++)
  - `starling.testing`             (Python imports / attribute access)
  - `starling_testing_marker`      (CMake target name in non-CMake source)

Lines tagged with `NOLINT(starling-testing-isolation)` are skipped.

Exit code 0 = clean. Exit code 1 = violations printed to stdout.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

FORBIDDEN_PATTERNS = (
    re.compile(r"\bstarling::testing\b"),
    re.compile(r"\bstarling\.testing\b"),
    re.compile(r"\bstarling_testing_marker\b"),
)
NOLINT_TAG = "NOLINT(starling-testing-isolation)"
SOURCE_SUFFIXES = {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".h", ".py", ".pyi", ".js", ".ts"}


def _iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in SOURCE_SUFFIXES:
            yield path


def scan(prod_roots: list[Path]) -> list[str]:
    violations: list[str] = []
    for root in prod_roots:
        if not root.exists():
            continue
        for path in _iter_source_files(root):
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if NOLINT_TAG in line:
                    continue
                for pattern in FORBIDDEN_PATTERNS:
                    if pattern.search(line):
                        violations.append(
                            f"{path}:{lineno}: forbidden testing reference: {line.strip()}"
                        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prod-roots",
        nargs="+",
        default=["src", "include", "bindings", "python/starling"],
        help="Roots that MUST NOT reference the testing namespace.",
    )
    parser.add_argument(
        "--allowed-roots",
        nargs="*",
        default=["tests", "src/testing", "python/starling/testing"],
        help="Roots intentionally allowed to import testing helpers (skipped).",
    )
    args = parser.parse_args()

    cwd = Path.cwd()
    prod_roots = [cwd / r for r in args.prod_roots]
    allowed_roots = [(cwd / r).resolve() for r in args.allowed_roots]

    def is_allowed(p: Path) -> bool:
        try:
            resolved = p.resolve()
        except OSError:
            return False
        return any(
            str(resolved).startswith(str(allowed)) for allowed in allowed_roots
        )

    filtered_roots = [r for r in prod_roots if not is_allowed(r)]
    violations = scan(filtered_roots)

    if violations:
        print("CI static scan FAILED — testing namespace leaked into prod roots:")
        for v in violations:
            print(f"  {v}")
        return 1
    print("CI static scan OK — no forbidden testing references in prod roots.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 跑测试，确认通过**

Run: `pytest tests/python/test_ci_static_scan.py -v`
Expected: PASS — 4/4.

- [ ] **Step 4: 写 GitHub Actions workflow**

`.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  cpp-build-test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - name: Install build deps
        run: |
          sudo apt-get update
          sudo apt-get install -y ninja-build clang-17 clang-tidy-17
      - name: Configure
        run: cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
        env:
          CC: clang-17
          CXX: clang++-17
      - name: Build
        run: cmake --build build
      - name: Test
        run: ctest --test-dir build --output-on-failure
      - name: clang-tidy
        run: |
          find src include bindings -name '*.cpp' -o -name '*.hpp' | \
            xargs clang-tidy-17 -p build

  python-test:
    runs-on: ubuntu-24.04
    needs: cpp-build-test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install
        run: pip install -e ".[dev]"
      - name: pytest
        run: pytest

  static-scan:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run defense-line #1
        run: python scripts/ci_static_scan.py
```

- [ ] **Step 5: 在仓库根跑扫描器，确认对当前代码绿**

Run: `python scripts/ci_static_scan.py`
Expected: `CI static scan OK — no forbidden testing references in prod roots.` 退出码 0。

> 当前 `bindings/python/module.cpp` 引用 `starling::testing::testing_marker_loaded`，scanner 配置应将 `bindings` 视为 prod 但允许通过 `NOLINT` 标注。修改 `module.cpp` 中相关行末尾追加 `// NOLINT(starling-testing-isolation): pybind exposes testing submodule`。

Modify the testing-binding lines in `bindings/python/module.cpp`:
```cpp
    auto testing_submodule = m.def_submodule("testing",
        "Testing-only helpers. Prod profiles MUST NOT link this submodule.");  // NOLINT(starling-testing-isolation)
    testing_submodule.def("marker_loaded", &starling::testing::testing_marker_loaded,
                          "True iff the testing-only translation unit is linked.");  // NOLINT(starling-testing-isolation)
```

Re-run: `python scripts/ci_static_scan.py` → exit 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/ci_static_scan.py .github/workflows/ci.yml \
        tests/python/test_ci_static_scan.py bindings/python/module.cpp
git commit -m "feat(M0.0): CI static scan defense-line #1 + GitHub Actions workflow"
```

---

## Task 8: TC-NEW-PREFLIGHT [CRITICAL] 端到端覆盖

> 该用例由 system_design.md §15.3.4 给出 4 个 fail-closed 触发条件 + 6 项断言。M0.0 必须以 Python 集成测试覆盖：用 stub Adapter 注入各分支，观察 `RuntimeHealth = UNREADY`、`runtime.health_changed` 事件、退出码 78、`Bus.append_evidence` 拒绝。
>
> M0.0 范围内 Bus / Engram 还未实现，因此本 task 的 "Bus.append_evidence 直接返回 PRECONDITION_FAILED" 用 stub bus 替代；M0.3 真正接入时会替换实现，但行为契约这里就锁定。

**Files:**
- Create: `python/starling/runtime.py`（Runtime supervisor — Adapter 装载 + preflight + RuntimeHealth）
- Create: `tests/python/test_tc_new_preflight.py`

- [ ] **Step 1: 写失败的 CRITICAL 集成测试**

`tests/python/test_tc_new_preflight.py`:
```python
"""TC-NEW-PREFLIGHT [CRITICAL] — system_design.md §15.3.4.

Covers all 4 fail-closed triggers plus the 6 post-conditions, gated through the
M0.0 Runtime supervisor. The Bus / EngramStore stubs used here freeze the
behavioral contract — M0.3 replaces them with real implementations.
"""
from __future__ import annotations

import pytest

from starling import _core
from starling.runtime import Runtime, RuntimeUnreadyError, EX_CONFIG


def _local_store_cap(**overrides):
    base = dict(
        profile_name="local-store",
        relational_backend="seekdb",
        vector_backend="seekdb",
        graph_backend="ladybugdb",
        c_plus_plus_core=True,
        cross_partition_transaction=True,
        transactional_outbox=True,
        consumer_checkpoint=True,
        tenant_isolation="storage_enforced",
        engram_per_record_key=True,
        engram_refcount=True,
        testing_helper_marker=True,
    )
    base.update(overrides)
    return _core.ProfileCapability(**base)


# ----- branch (a): missing idx_statement_id_tenant -----
# In M0.0 the index check is delegated to a callable; M0.2 replaces with real SQL.
def test_unready_when_idx_statement_id_tenant_missing():
    cap = _local_store_cap()
    rt = Runtime(
        capability=cap,
        idx_statement_id_tenant_present=lambda: False,
    )
    with pytest.raises(RuntimeUnreadyError) as exc:
        rt.start()
    assert rt.health() == _core.RuntimeHealth.UNREADY
    assert "idx_statement_id_tenant" in exc.value.missing_capabilities
    assert rt.exit_code == EX_CONFIG


# ----- branch (b): transactional_outbox = false -----
def test_unready_when_transactional_outbox_false():
    cap = _local_store_cap(transactional_outbox=False)
    rt = Runtime(capability=cap)
    with pytest.raises(RuntimeUnreadyError) as exc:
        rt.start()
    assert "transactional_outbox" in exc.value.missing_capabilities
    assert rt.exit_code == EX_CONFIG


# ----- branch (c): tenant_isolation = app_filter while profile expects storage_enforced -----
def test_unready_when_app_filter_violates_storage_enforced():
    cap = _local_store_cap(tenant_isolation="app_filter")
    rt = Runtime(capability=cap)
    with pytest.raises(RuntimeUnreadyError) as exc:
        rt.start()
    assert "tenant_isolation_storage_enforced" in exc.value.missing_capabilities
    assert rt.exit_code == EX_CONFIG


# ----- branch (d): cross_partition_transaction = false but profile claims local_store_atomic -----
def test_unready_when_cross_partition_false_for_local_store_atomic():
    cap = _local_store_cap(cross_partition_transaction=False)
    rt = Runtime(capability=cap)
    with pytest.raises(RuntimeUnreadyError) as exc:
        rt.start()
    assert "cross_partition_transaction" in exc.value.missing_capabilities
    assert rt.exit_code == EX_CONFIG


# ----- post-conditions on UNREADY -----
def test_unready_emits_runtime_health_changed_event():
    cap = _local_store_cap(transactional_outbox=False)
    events = []
    rt = Runtime(capability=cap, on_health_change=lambda evt: events.append(evt))
    with pytest.raises(RuntimeUnreadyError):
        rt.start()
    assert len(events) == 1
    evt = events[0]
    assert evt["event"] == "runtime.health_changed"
    assert evt["state"] == "UNREADY"
    assert "transactional_outbox" in evt["missing_capabilities"]


def test_unready_does_not_start_workers():
    cap = _local_store_cap(transactional_outbox=False)
    rt = Runtime(capability=cap)
    with pytest.raises(RuntimeUnreadyError):
        rt.start()
    assert rt.foreground_workers_started is False
    assert rt.background_workers_started is False


def test_unready_bus_calls_return_precondition_failed():
    cap = _local_store_cap(transactional_outbox=False)
    rt = Runtime(capability=cap)
    with pytest.raises(RuntimeUnreadyError):
        rt.start()
    assert rt.bus.append_evidence({"engram": "stub"}) == "PRECONDITION_FAILED"
    assert rt.bus.write({"stmt": "stub"}) == "PRECONDITION_FAILED"


def test_unready_writes_no_engram_or_statement():
    cap = _local_store_cap(transactional_outbox=False)
    rt = Runtime(capability=cap)
    with pytest.raises(RuntimeUnreadyError):
        rt.start()
    assert rt.engram_store.appended_count == 0
    assert rt.bus.written_count == 0


def test_ready_when_all_capabilities_present():
    cap = _local_store_cap()
    events = []
    rt = Runtime(
        capability=cap,
        on_health_change=lambda evt: events.append(evt),
        idx_statement_id_tenant_present=lambda: True,
    )
    rt.start()
    assert rt.health() == _core.RuntimeHealth.READY
    assert rt.foreground_workers_started is True
    assert rt.background_workers_started is True
    assert events[-1]["state"] == "READY"
```

Run: `pytest tests/python/test_tc_new_preflight.py -v`
Expected: FAIL — `starling.runtime` 不存在。

- [ ] **Step 2: 写 Runtime supervisor（Python，stub Bus / EngramStore）**

`python/starling/runtime.py`:
```python
"""Runtime supervisor — M0.0 minimum: load Adapter, run preflight, manage RuntimeHealth.

Bus / EngramStore are stubs in M0.0; M0.3 replaces with real adapters. The behavior
contract enforced here (PRECONDITION_FAILED on UNREADY, no worker start, exit code
78) is what TC-NEW-PREFLIGHT [CRITICAL] locks down for the rest of P1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from starling import _core

EX_CONFIG = 78  # POSIX sysexits.h

# Required capabilities for local-store profile in M0.0. M0.1 will pull these
# from the parsed profile config.
LOCAL_STORE_REQUIRED = (
    "transactional_outbox",
    "consumer_checkpoint",
    "engram_per_record_key",
    "c_plus_plus_core",
    "cross_partition_transaction",
    "tenant_isolation_storage_enforced",
    "testing_helper_marker",
)


class RuntimeUnreadyError(RuntimeError):
    def __init__(self, missing_capabilities: list[str]):
        super().__init__(
            "preflight failed: " + ", ".join(missing_capabilities)
        )
        self.missing_capabilities = missing_capabilities


@dataclass
class _StubBus:
    health_getter: Callable[[], _core.RuntimeHealth]
    written_count: int = 0

    def append_evidence(self, _engram) -> str:
        if self.health_getter() != _core.RuntimeHealth.READY:
            return "PRECONDITION_FAILED"
        self.written_count += 1
        return "OK"

    def write(self, _stmt) -> str:
        if self.health_getter() != _core.RuntimeHealth.READY:
            return "PRECONDITION_FAILED"
        self.written_count += 1
        return "OK"


@dataclass
class _StubEngramStore:
    appended_count: int = 0


@dataclass
class Runtime:
    capability: _core.ProfileCapability
    on_health_change: Optional[Callable[[dict], None]] = None
    idx_statement_id_tenant_present: Callable[[], bool] = field(
        default=lambda: True
    )

    foreground_workers_started: bool = False
    background_workers_started: bool = False
    exit_code: Optional[int] = None
    bus: _StubBus = field(init=False)
    engram_store: _StubEngramStore = field(default_factory=_StubEngramStore)

    _state: _core.RuntimeHealth = field(default=_core.RuntimeHealth.UNREADY)

    def __post_init__(self):
        self.bus = _StubBus(health_getter=lambda: self._state)

    def health(self) -> _core.RuntimeHealth:
        return self._state

    def start(self) -> None:
        missing: list[str] = []
        # Capability-level preflight.
        result = _core.preflight(self.capability, list(LOCAL_STORE_REQUIRED))
        if result.status == _core.PreflightStatus.UNREADY:
            missing.extend(result.missing)
        # Index-level preflight (branch a).
        if not self.idx_statement_id_tenant_present():
            missing.append("idx_statement_id_tenant")

        if missing:
            self._set_unready(missing)
            raise RuntimeUnreadyError(missing)

        self._set_ready()

    def _set_unready(self, missing: list[str]) -> None:
        self._state = _core.RuntimeHealth.UNREADY
        self.exit_code = EX_CONFIG
        self.foreground_workers_started = False
        self.background_workers_started = False
        if self.on_health_change:
            self.on_health_change({
                "event": "runtime.health_changed",
                "state": "UNREADY",
                "missing_capabilities": missing,
            })

    def _set_ready(self) -> None:
        self._state = _core.RuntimeHealth.READY
        self.foreground_workers_started = True
        self.background_workers_started = True
        if self.on_health_change:
            self.on_health_change({
                "event": "runtime.health_changed",
                "state": "READY",
                "missing_capabilities": [],
            })


__all__ = ["Runtime", "RuntimeUnreadyError", "EX_CONFIG"]
```

- [ ] **Step 3: 跑 TC-NEW-PREFLIGHT，确认通过**

Run: `pytest tests/python/test_tc_new_preflight.py -v`
Expected: PASS — 9/9 tests, including all 4 fail-closed branches and all 5 post-conditions.

- [ ] **Step 4: 跑全部测试，确认无回归**

Run:
```bash
cmake --build build && ctest --test-dir build --output-on-failure
pytest
python scripts/ci_static_scan.py
```
Expected:
- ctest: 全部 C++ 测试通过
- pytest: 全部 Python 测试通过（含 TC-NEW-PREFLIGHT）
- ci_static_scan: exit 0

- [ ] **Step 5: Commit**

```bash
git add python/starling/runtime.py tests/python/test_tc_new_preflight.py
git commit -m "feat(M0.0): Runtime supervisor + TC-NEW-PREFLIGHT [CRITICAL] coverage"
```

---

## Task 9: M0.0 验收 + roadmap 进度更新

**Files:**
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md`

- [ ] **Step 1: 全栈跑一遍确认绿**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling
cmake --build build
ctest --test-dir build --output-on-failure
pytest
python scripts/ci_static_scan.py
```

Expected: 全部通过。

- [ ] **Step 2: 更新 roadmap 进度表**

Modify `docs/superpowers/plans/2026-05-23-roadmap.md` 中的进度表行 M0.0：

替换：
```
| M0.0 | 已写 | 未实施 | — | — |
```
为：
```
| M0.0 | 已写 | ✅ 完成 | 2026-XX-XX | <commit-sha> |
```

（实际日期 / sha 由执行时填入。）

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-05-23-roadmap.md
git commit -m "chore(M0.0): mark milestone complete in roadmap"
```

---

## 验收标准（M0.0 完成 = 以下全绿）

1. **构建**：`cmake --build build` zero warnings (Werror 守门), zero errors
2. **C++ 测试**：`ctest` 100% 通过（≥ 19 测试用例：smoke + ProfileCapability ×2 + RuntimeHealth ×3 + Preflight ×6 + FinalQueryAssertion ×8）
3. **Python 测试**：`pytest` 100% 通过（≥ 25 用例，含 TC-NEW-PREFLIGHT 9 个）
4. **TC-NEW-PREFLIGHT [CRITICAL]**：4 fail-closed 分支 + 5 post-conditions 全绿
5. **CI 静态扫描**：`python scripts/ci_static_scan.py` 退出 0
6. **clang-tidy**：CI workflow 中 clang-tidy job 通过
7. **代码风格**：`clang-format --dry-run --Werror` 全绿（可选；M0.0 不强制 commit hook）
8. **Git 历史**：8-9 个 commit（每个 task 一个），`git log --oneline` 清晰

---

## 自检（writing-plans skill 强制项）

**1. Spec coverage** — system_design.md §15.2 M0.0 出货项逐条对照：

| 出货项 | 对应 task |
|---|---|
| ProfileCapability struct | Task 2 |
| final query assertion | Task 5 |
| testing helper marker | Task 6 |
| CI 静态扫描 | Task 7 |
| TC-NEW-PREFLIGHT [CRITICAL] 全绿 | Task 8 |

§16.3-1 `ProfileCapability cross_partition_transaction` 在 Task 4 preflight 中作为可选键支持。

**2. Placeholder 扫描**：
- 所有 `TODO` / `TBD` / `implement later` / `add appropriate handling` 字符串 = 0
- 每个步骤含完整代码（cmake / cpp / py / yaml）
- 文件路径 100% 绝对或仓库相对，无 `<path>` 占位

**3. Type / 名称一致性**：
- `ProfileCapability` 字段名（C++ struct vs pybind binding vs Python kwarg）一致
- `RuntimeHealth` enum 值 `UNREADY/READY/DEGRADED/DRAINING` 在 C++ 和 Python 同顺序同值
- `assert_final_query_safe` / `is_final_query_safe` 在 C++ 和 Python 同名
- `Runtime` 类的 `start / health / bus / engram_store / exit_code` 与测试断言完全对齐
- `EX_CONFIG = 78` 与 §15.3.4 `进程退出码 = 78（EX_CONFIG）` 一致
- `runtime.health_changed` 事件名与 §15.3.4 一致

无遗漏。
