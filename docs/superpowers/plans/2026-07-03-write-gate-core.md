# Write-Gate Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把健康驱动的前台写门(`RuntimeSupervisor::check_write`)从生产死代码下沉进 C++ 核心写路径,使 DRAINING/UNREADY 真正拒绝所有前台**用户**写(经 C++ 核心的 7 个入口)并抛统一 `WriteGateRejected`;READY/DEGRADED 行为不变。

**Architecture(eng-review pivot — adapter-hook):** `SqliteAdapter` 持一个可空 `std::function<bool()>` 写门钩子;production `Runtime` 构造时 `install_write_gate(adapter, supervisor)` 设一次(钩子内 `sup.check_write() == kAccept`)。7 个核心写函数首行 `governance::require_write_admission(adapter)` —— 钩子未设(bare-adapter 测试)→ 放行;设了且 reject → 抛 `WriteGateRejected`。**零签名改动、零调用方破坏、behavior-neutral by construction**(bare adapter = 无钩子 = 放行)。门在 `src/` 核心,换绑定不可绕。

**Tech Stack:** C++20 内核(`src/` + `include/starling/`)、pybind11、Python host、SQLite;ctest + pytest;spec `docs/superpowers/specs/2026-07-03-write-gate-core-design.md`。

> **为何 adapter-hook 而非参数注入(eng-review Finding #1/#2,已验证):** 给 `fulfill`/`withdraw` 加 `sup` 参会破**生产** `src/prospective/policy_engine.cpp:415/421`(自动 commitment 结算调 `commitment_engine_.fulfill/withdraw`,PolicyEngine 无 supervisor → 编译挂)+ 11 个直调测试(`test_commitment_engine.cpp:68…129`、`test_commitment_protection_decay.cpp:45`、`test_commitment_tenant_isolation.cpp:74`、`test_p2c_commitment_lifecycle.py:37`)。给 5 个 free fn 加参虽只破 `test_tom2_e2e.py:333`,但为一致性 + 溶解全部破坏,7 入口统一用 adapter-hook。

## Global Constraints

- **架构边界(硬):** 门是核心语义 → 实现于 C++ 核心(`src/` + `include/starling/`),门检查置于**核心函数顶端**,**非 pybind lambda**;`persistence`(SqliteAdapter)只持一个 `std::function<bool()>` 钩子(返回 bool,**不 `#include` governance**);`governance` 定义异常 + `require_write_admission`/`install_write_gate`。判据「换绑定语言是否需重写」。
- **Behavior-neutral by construction:** bare adapter(无钩子)→ `write_admitted()==true` → 放行。只有 production `Runtime` 设钩子。**现有 ctest + pytest 无一改动即绿**(除本 slice 新增测试)。
- **门前抛 = 零 DB 写**(early throw,不建 engram、不抽取、不开事务)。写后/订阅者路径仍用 SAVEPOINT 不用 BEGIN。
- **Lock order** engine→supervisor(钩子内 `check_write` 短暂持 supervisor mutex,不跨写持锁),与 `note_health`/L8 一致,无逆序。
- 拒绝用 `check_write()`(自然覆盖 UNREADY+DRAINING);`remember()` 跨 mid-drain 的 belief-已写/general-fact-被拒部分完成为已知可接受边界。
- **构建:** `python scripts/configure_build.py --build --python-editable`(C++ + 绑定重装 `_core`)。clang-tidy CI-only 门,新 C++ clean by construction(identifier-length≥3、sized enums、`[[nodiscard]]`、无 empty/comment-only catch;`std::function` 成员非 const/ref → 无 NOLINT)。提交门:全量 ctest + `pytest tests/python` 绿。
- **git:** 显式路径 `git add`(禁 `git add .`/`-A`);不用 `--no-verify`/`--amend`。分支 `feat/write-gate-core`。

## 现有接口(实现者据此)

- `include/starling/persistence/sqlite_adapter.hpp:19`:`class SqliteAdapter : public starling::Adapter { public: static std::unique_ptr<SqliteAdapter> open(...); ProfileCapability declare_capability() const; bool has_index(std::string_view); Connection& connection() noexcept; private: Connection conn_; };`。**未** include `<functional>`。
- `include/starling/governance/runtime_supervisor.hpp`:`enum class WriteGateDecision : std::uint8_t { kAccept, kPreconditionFailed };`;`RuntimeSupervisor::check_write() const → WriteGateDecision`(READY/DEGRADED→kAccept;UNREADY/DRAINING→kPreconditionFailed);`start()`/`note_health(HealthDecision)`/`begin_drain(trigger)`/`health()`。已 fwd-decl `persistence::SqliteAdapter`(:17)。
- 7 个前台写**核心函数(签名全部不变)**:
  - `memoryops::remember(SqliteAdapter& adapter, LLMAdapter& llm, sv prompt, const RememberParams&, const ValidationPolicy&={})`(memory_ops.cpp:23)
  - `memoryops::converse(SqliteAdapter& adapter, LLMAdapter& chat, LLMAdapter& extraction, SemanticRetriever&, sv prompt, const ConverseParams&, const ValidationPolicy&={}, const TokenSink&={})`(:103;内部 :176 调 `remember`,包在 :186 `catch(std::exception)`)
  - `memoryops::forget(SqliteAdapter& adapter, sv tenant, const std::vector<std::string>& ids, sv now)`
  - `memoryops::approve_review(SqliteAdapter& adapter, sv tenant, sv stmt_id, sv now)`
  - `request_reconsolidation`:**现为 `bind_09_brain_dynamics.cpp:200` 的 lambda(无核心函数)** → Task 4 提取为 `memoryops::request_reconsolidation(SqliteAdapter& adapter, ...)`。
  - `prospective::CommitmentEngine::fulfill(Connection& conn, sv stmt_id, sv tenant, sv now)` / `withdraw(...)`(commitment_engine.cpp:253/270;类持 `SqliteAdapter& adapter_`;**被 `src/prospective/policy_engine.cpp:415/421` + 11 测试直调 → 签名绝不能改**)。
- Python:`_build_local_store_sqlite_runtime`(runtime.py:178)→ `Runtime(adapter=...)`;`Runtime.__post_init__`(:110)adapter 分支创建 `self._sup = _core.RuntimeSupervisor(cap, embedded, adapter)`(:119);`begin_drain`/`note_health` 已在 Runtime。`Memory.open`(memory.py:144)与 `DashboardEngine`(engine.py:156)都经此工厂。

## Deferred / Out of Scope(在此声明)

- **`plan_query` 的 `statement.recalled` emit(eng-review #5 = exempt):** `retrieval_planner.cpp:445-467` 每命中 fire-and-forget 写一条 `statement.recalled` 审计事件到 outbox。这是**读侧审计写、非用户 write 意图 → 不 gate**(gate 一个读路径会 throw 断查询;drain 窗口短 + 几条审计行无害)。故本 slice「所有前台写」= **所有经 C++ 核心的前台用户写**,读侧 recalled-audit 显式豁免。
- **`_reembed` + `run_replay`(eng-review #8 = out-of-scope):** `dashboard/engine.py:321 _reembed`(配置保存:裸 `DELETE FROM statement_vectors` + `worker.tick_one_batch`,绕 C++ 核心用不了核心门)与 `run_replay`(engine.py:443,重 DB 写)。均 dashboard admin/config 操作,本 slice 不 gate;要完整 quiesce 另开 host-gate 切片(Python 侧 `if rt.health()==DRAINING` skip)。
- vestigial Python 门清理(`_StubBus`/`_SqliteBackedBus`/`rt.bus`/`BusFacade`)= 单独 cleanup slice。
- 后台 tick 写(`memory_tick_all` 已被 `should_run_stage` 覆盖)。#2 并发、query-embed cache、向量扫描。

---

### Task 1: 核心机制 — 钩子 + WriteGateRejected + require_write_admission + install_write_gate

**Files:**
- Modify: `include/starling/persistence/sqlite_adapter.hpp`(加 `<functional>` + 钩子成员 + `set_write_admit`/`write_admitted`)
- Create: `include/starling/governance/write_gate.hpp`(`WriteGateRejected` + 两个自由函数声明)
- Create: `src/governance/write_gate.cpp`(定义;注册进 governance 的 CMake 源列表)
- Modify: `bindings/python/bind_14_governance.cpp`(`register_exception` + `install_write_gate` 绑定)
- Test: `tests/cpp/test_write_gate_admission.cpp`(新建)+ 注册进 `tests/cpp/CMakeLists.txt`(比照邻近 test)

**Interfaces:**
- Produces: `SqliteAdapter::set_write_admit(std::function<bool()>)` + `[[nodiscard]] bool SqliteAdapter::write_admitted() const`;`governance::WriteGateRejected`;`void governance::require_write_admission(const persistence::SqliteAdapter&)`;`void governance::install_write_gate(persistence::SqliteAdapter&, const RuntimeSupervisor&)`。Task 2-5 全依赖。

- [ ] **Step 1: SqliteAdapter 钩子(hpp)** — `include/starling/persistence/sqlite_adapter.hpp`:顶部 `#include <functional>`;public 加:

```cpp
    // 写门钩子(P3.c write-gate):未设 → 放行(behavior-neutral by construction)。
    // 返回 bool 避免 persistence 依赖 governance。production Runtime 经
    // governance::install_write_gate 设一次:钩子内读 supervisor 健康态。
    void set_write_admit(std::function<bool()> fn) { write_admit_ = std::move(fn); }
    [[nodiscard]] bool write_admitted() const { return !write_admit_ || write_admit_(); }
```
private 加成员:`std::function<bool()> write_admit_;`。

- [ ] **Step 2: write_gate.hpp** — `include/starling/governance/write_gate.hpp`:

```cpp
#pragma once
#include <stdexcept>
#include <string>

namespace starling::persistence { class SqliteAdapter; }

namespace starling::governance {

class RuntimeSupervisor;  // fwd

// 治理写拒绝。std::runtime_error 子类 → pybind register_exception → _core.WriteGateRejected。
class WriteGateRejected : public std::runtime_error {
 public:
  explicit WriteGateRejected(const std::string& what) : std::runtime_error(what) {}
};

// 前台写准入门(策略一处):adapter 无钩子 → 放行;钩子 reject → 抛 WriteGateRejected。
// 7 个核心写函数各首行调一次。
void require_write_admission(const persistence::SqliteAdapter& adapter);

// production Runtime 构造时调一次:把 adapter 的钩子接到 sup.check_write()。
void install_write_gate(persistence::SqliteAdapter& adapter, const RuntimeSupervisor& sup);

}  // namespace starling::governance
```

- [ ] **Step 3: write_gate.cpp** — `src/governance/write_gate.cpp`:

```cpp
#include "starling/governance/write_gate.hpp"
#include "starling/governance/runtime_supervisor.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::governance {

void require_write_admission(const persistence::SqliteAdapter& adapter) {
  if (!adapter.write_admitted()) {
    throw WriteGateRejected("write rejected: runtime not accepting writes");
  }
}

void install_write_gate(persistence::SqliteAdapter& adapter, const RuntimeSupervisor& sup) {
  // 引用捕获:production 下 adapter 与 sup 同由 Runtime 持有,sup 生命周期不短于
  // adapter 的写调用(sup 本身也持 adapter 的 has_index 引用,互引用,Runtime 共管)。
  adapter.set_write_admit([&sup]() { return sup.check_write() == WriteGateDecision::kAccept; });
}

}  // namespace starling::governance
```
把 `src/governance/write_gate.cpp` 加进 governance 的 CMake 源列表(比照 `runtime_supervisor.cpp` 所在 target)。

- [ ] **Step 4: 写 helper 单测(失败)** — `tests/cpp/test_write_gate_admission.cpp`:

```cpp
// tests/cpp/test_write_gate_admission.cpp
#include "starling/governance/write_gate.hpp"
#include "starling/governance/runtime_supervisor.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <filesystem>
#include <functional>
using starling::ProfileCapability;
using starling::RuntimeHealth;
using namespace starling::governance;

namespace {
// COPY of tests/cpp/test_runtime_supervisor.cpp:18 all_present() (逐字复制;
// tests/cpp 不受 clang-tidy 门)。RuntimeSupervisor 有 std::mutex → 非可移动,
// 就地构造,勿按值返回。
ProfileCapability all_present() {
  return ProfileCapability{ /* …copy verbatim from test_runtime_supervisor.cpp… */ };
}
std::unique_ptr<starling::persistence::SqliteAdapter> open_tmp(const char* name) {
  return starling::persistence::SqliteAdapter::open(
      std::filesystem::temp_directory_path() / name);
}
}  // namespace

TEST(WriteGateAdmission, NoHookAdmits) {
  auto a = open_tmp("wg_nohook.db");
  EXPECT_TRUE(a->write_admitted());
  EXPECT_NO_THROW(require_write_admission(*a));   // 无钩子 → 放行
}
TEST(WriteGateAdmission, HookRejectThrows) {
  auto a = open_tmp("wg_reject.db");
  a->set_write_admit([] { return false; });
  EXPECT_FALSE(a->write_admitted());
  EXPECT_THROW(require_write_admission(*a), WriteGateRejected);
}
TEST(WriteGateAdmission, HookAdmitPasses) {
  auto a = open_tmp("wg_admit.db");
  a->set_write_admit([] { return true; });
  EXPECT_NO_THROW(require_write_admission(*a));
}
TEST(WriteGateAdmission, InstallWiresSupervisorDraining) {
  auto a = open_tmp("wg_install.db");
  RuntimeSupervisor sup(all_present(), /*embedded=*/true,
                        std::function<bool()>([] { return true; }));
  sup.start();                                    // → READY
  install_write_gate(*a, sup);
  EXPECT_NO_THROW(require_write_admission(*a));    // READY 放行
  sup.begin_drain("test");                        // → DRAINING
  EXPECT_THROW(require_write_admission(*a), WriteGateRejected);
}
```

- [ ] **Step 5: 跑测试确认失败** — `python scripts/configure_build.py --build`;预期编译失败(`write_admitted`/`require_write_admission`/`install_write_gate` 未声明)。

- [ ] **Step 6: 实现 Step 1-3 的代码,再跑** — 已在 Step 1-3 给出。`python scripts/configure_build.py --build --test`;预期 `WriteGateAdmission.*` 4 例 PASS,ctest 全绿。

- [ ] **Step 7: pybind 异常 + install 绑定** — `bindings/python/bind_14_governance.cpp`:`#include "starling/governance/write_gate.hpp"`;在 `WriteGateDecision` 绑定附近加:

```cpp
    py::register_exception<gov::WriteGateRejected>(m, "WriteGateRejected");
    m.def("install_write_gate", &gov::install_write_gate,
          py::arg("adapter"), py::arg("supervisor"),
          "Wire adapter's write gate to supervisor.check_write() (production only).");
```

- [ ] **Step 8: Commit**

```bash
git add include/starling/persistence/sqlite_adapter.hpp include/starling/governance/write_gate.hpp src/governance/write_gate.cpp bindings/python/bind_14_governance.cpp tests/cpp/test_write_gate_admission.cpp tests/cpp/CMakeLists.txt
git commit -m "feat(governance): adapter write-gate hook + WriteGateRejected + require_write_admission

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 生产 Runtime 接线 install_write_gate

**Files:**
- Modify: `python/starling/runtime.py`(`Runtime.__post_init__` adapter 分支接线)
- Test: `tests/python/test_write_gate_wired.py`(新建)

**Interfaces:**
- Consumes: `_core.install_write_gate`(Task 1)。
- Produces: production runtime 的 adapter 钩子已接到 supervisor —— `rt.begin_drain()` 后 `rt.adapter.write_admitted()` 为 False。

- [ ] **Step 1: 写测试(失败)** — `tests/python/test_write_gate_wired.py`:

```python
from pathlib import Path
from starling import _core
from starling import runtime as rt_mod


def test_production_runtime_wires_write_gate(tmp_path):
    rt = rt_mod._build_local_store_sqlite_runtime(tmp_path / "wired.db")
    rt.start()
    assert rt.adapter.write_admitted() is True     # READY → 放行
    rt.begin_drain()
    assert rt.adapter.write_admitted() is False     # DRAINING → 拒
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/python/test_write_gate_wired.py -v`;预期 FAIL(`write_admitted()` 恒 True,未接线)。

- [ ] **Step 3: 接线** — `python/starling/runtime.py` `Runtime.__post_init__` 的 **adapter 分支**(:116-121),在 `self._sup = _core.RuntimeSupervisor(self.capability, self.embedded, self.adapter)` 之后加:

```python
            # 前台写门(P3.c):把 adapter 钩子接到 supervisor 健康态。仅 production
            # (adapter 提供)接线;test-seam(adapter=None)与 bare-adapter 测试无钩子 → 放行。
            _core.install_write_gate(self.adapter, self._sup)
```
（test-seam 分支 adapter=None 不加。）

- [ ] **Step 4: 跑测试确认通过 + 现有绿** — `pytest tests/python/test_write_gate_wired.py -v`(PASS);`pytest tests/python -q`(全绿,behavior-neutral)。

- [ ] **Step 5: Commit**

```bash
git add python/starling/runtime.py tests/python/test_write_gate_wired.py
git commit -m "feat(runtime): wire adapter write-gate to supervisor in production Runtime

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Gate memory_ops 四入口(remember/converse/forget/approve_review)

**Files:**
- Modify: `src/memory/memory_ops.cpp`(4 个函数首行 gate;含 converse 内部 remember 的说明)
- Modify: `include/starling/memory/memory_ops.hpp`(确认 include `write_gate.hpp`;签名**不改**)
- Test: `tests/python/test_write_gate_memory_ops.py`(新建)

> **签名/绑定/Python 调用点全部不改** —— gate 仅是每个核心函数体内首行加 `governance::require_write_admission(adapter);`。

**Interfaces:** Consumes `governance::require_write_admission`(Task 1)、production 接线(Task 2)、`_core.WriteGateRejected`(Task 1)。

- [ ] **Step 1: 写 DRAINING 拒绝测试(失败,直接查表证明零写)** — `tests/python/test_write_gate_memory_ops.py`:

```python
from pathlib import Path
import sqlite3
import pytest
from starling import _core
from starling.memory import Memory, make_stub_llm

_STUB = '[]'


def _row_counts(db_path):
    # 直接查表证明「零写」(eng-review #4:recall()==[] 无法证明,remember 不 embed)。
    con = sqlite3.connect(str(db_path))
    try:
        n = {}
        for t in ("engrams", "statements", "bus_events"):
            try:
                n[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.OperationalError:
                n[t] = None   # 表不存在则跳过
        return n
    finally:
        con.close()


def _drained(tmp_path, name):
    db = tmp_path / name
    mem = Memory.open(db, llm=make_stub_llm(default_response=_STUB))
    mem._rt.begin_drain()
    assert mem._rt.health() == _core.RuntimeHealth.DRAINING
    return mem, db


def test_remember_rejected_when_draining(tmp_path):
    mem, db = _drained(tmp_path, "wg.db")
    before = _row_counts(db)
    with pytest.raises(_core.WriteGateRejected):
        mem.remember("Alice likes tea")
    assert _row_counts(db) == before          # 门前抛 = 零新行


def test_forget_rejected_when_draining(tmp_path):
    mem, _ = _drained(tmp_path, "wg_forget.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.forget(["stmt-nonexistent"])


def test_approve_review_rejected_when_draining(tmp_path):
    mem, _ = _drained(tmp_path, "wg_appr.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.approve_review("stmt-nonexistent")


def test_converse_rejected_when_draining(tmp_path):
    mem, _ = _drained(tmp_path, "wg_conv.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.converse("hello")           # drain-at-start → 顶端 gate 抛
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/python/test_write_gate_memory_ops.py -v`;预期 FAIL(无门,不抛)。

- [ ] **Step 3: 首行 gate(cpp)** — `src/memory/memory_ops.cpp`:确认 `#include "starling/governance/write_gate.hpp"`;在 `remember`(:23)/`converse`(:103)/`forget`/`approve_review` 每个函数体**第一行**(任何 DB/事务/LLM 之前)加:

```cpp
    governance::require_write_admission(adapter);   // 门前抛 = 零 DB 写
```

- [ ] **Step 4: converse 二次 gate 已验证安全(eng-review #7,记录)** — `converse` 顶端 gate 抛 = drain-at-start(整轮拒,尚未 recall/generate)。converse 内部 `remember`(:176)也首行 gate;若 drain 恰落在 converse 开头与 :176 之间,内部 remember 抛的 `WriteGateRejected` 被 `:186` 现有 `catch (const std::exception& e){ r.remember_ok=false; r.remember_error=e.what(); }` **吃掉**(`WriteGateRejected` 是 `std::exception` 子类)→ 回复保留、`remember_ok=false`,符合 converse「回复绝不因 remember 失败而丢」不变式。**这是 converse 对 spec §6「统一传播」的有意例外**(spec §6 已注)。无需额外代码;不要在 :186 之前 rethrow(那会破坏 converse 不变式)。

- [ ] **Step 5: 重建 + 跑测试** — `python scripts/configure_build.py --build --python-editable`;`pytest tests/python/test_write_gate_memory_ops.py -v`(4 例 PASS);`pytest tests/python -q`(全绿,behavior-neutral;签名未改,现有调用方无影响)。

- [ ] **Step 6: Commit**

```bash
git add src/memory/memory_ops.cpp include/starling/memory/memory_ops.hpp tests/python/test_write_gate_memory_ops.py
git commit -m "feat(memory): gate remember/converse/forget/approve_review at core-fn entry

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 提取 request_reconsolidation 为核心函数 + gate

**Files:**
- Modify: `include/starling/memory/memory_ops.hpp`(声明 `request_reconsolidation`)
- Modify: `src/memory/memory_ops.cpp`(定义:搬 lambda 体 + 首行 gate)
- Modify: `bindings/python/bind_09_brain_dynamics.cpp:200`(lambda → 转发核心函数;**签名/py::arg 不变**)
- Test: `tests/python/test_write_gate_reconsolidation.py`(新建)

> **绑定签名不变** → `test_tom2_e2e.py:333` 直调 `_core.request_reconsolidation(adapter, ...)` 用 bare adapter(无钩子)→ 放行 → **不破**(eng-review Finding B 被 adapter-hook 溶解,无需改该测试)。

**Interfaces:** Produces `std::string memoryops::request_reconsolidation(persistence::SqliteAdapter& adapter, std::string_view tenant_id, std::string_view stmt_id, std::string_view request_id, std::string_view now_iso);`(返回 outbox event_id)。

- [ ] **Step 1: 写 DRAINING 拒绝测试(失败)** — `tests/python/test_write_gate_reconsolidation.py`:

```python
from pathlib import Path
import pytest
from starling import _core
from starling.memory import Memory, make_stub_llm


def test_request_reconsolidation_rejected_when_draining(tmp_path):
    mem = Memory.open(tmp_path / "wg_recon.db", llm=make_stub_llm(default_response='[]'))
    mem._rt.begin_drain()
    assert mem._rt.health() == _core.RuntimeHealth.DRAINING
    with pytest.raises(_core.WriteGateRejected):
        mem._core.request_reconsolidation("stmt-x", request_id="req-1")
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/python/test_write_gate_reconsolidation.py -v`;预期 FAIL(lambda 无门)。

- [ ] **Step 3: 声明核心函数(hpp)** — `include/starling/memory/memory_ops.hpp`,`approve_review` 声明后加:

```cpp
// P3.a3 再巩固显式触发:发 reconsolidate.requested 事件,engine 异步开窗。返回 outbox
// event_id。(边界归位:原写逻辑在 bind_09 lambda,本 slice 提取入核心以受门管辖。)
std::string request_reconsolidation(persistence::SqliteAdapter& adapter,
                                    std::string_view tenant_id,
                                    std::string_view stmt_id,
                                    std::string_view request_id,
                                    std::string_view now_iso);
```

- [ ] **Step 4: 定义核心函数(cpp)** — `src/memory/memory_ops.cpp`,搬 `bind_09:200` lambda 体 + 首行 gate:

```cpp
std::string request_reconsolidation(persistence::SqliteAdapter& adapter,
                                    std::string_view tenant_id,
                                    std::string_view stmt_id,
                                    std::string_view request_id,
                                    std::string_view now_iso) {
    governance::require_write_admission(adapter);        // 门前抛 = 零 DB 写
    auto& conn = adapter.connection();
    persistence::TransactionGuard tx(conn);
    bus::BusEvent ev;
    ev.tenant_id    = std::string(tenant_id);
    ev.event_type   = "reconsolidate.requested";
    ev.primary_id   = std::string(stmt_id);
    ev.aggregate_id = std::string(stmt_id);
    ev.payload_json = std::string("{\"stmt_id\":\"") + std::string(stmt_id) +
        "\",\"request_id\":\"" + std::string(request_id) + "\"}";
    ev.version = "v1";
    ev.idempotency_key = bus::compute_idempotency_key(
        "reconsolidate.requested", stmt_id, stmt_id, request_id, now_iso.substr(0, 10));
    bus::OutboxWriter w(conn);
    w.append(ev);
    tx.commit();
    return ev.event_id;
}
```
> 确认 include `bus/bus_event.hpp`、`bus/outbox_writer.hpp`、`persistence/transaction_guard.hpp`。字段/去重与原 lambda **逐字一致**(behavior-neutral,eng-review 已核实原 lambda 字段匹配)。`compute_idempotency_key` 若形参是 `std::string_view` 则直接传 `now_iso.substr(0,10)`(sv 的 substr 返回 sv);若是 `const std::string&` 则包 `std::string(...)`。

- [ ] **Step 5: 绑定改转发(bind_09)** — `bindings/python/bind_09_brain_dynamics.cpp:200`,lambda 体换成转发(**py::arg 保持不变**):

```cpp
    m.def("request_reconsolidation",
          [](starling::persistence::SqliteAdapter& adapter,
             const std::string& tenant_id, const std::string& stmt_id,
             const std::string& request_id, const std::string& now_iso) {
              return starling::memoryops::request_reconsolidation(
                  adapter, tenant_id, stmt_id, request_id, now_iso);
          },
          py::arg("adapter"), py::arg("tenant_id"), py::arg("stmt_id"),
          py::arg("request_id"), py::arg("now_iso"),
          "Emit reconsolidate.requested (explicit trigger #4); gated: rejected while DRAINING/UNREADY.");
```
确认 `bind_09` include `starling/memory/memory_ops.hpp`。

- [ ] **Step 6: 重建 + 跑测试** — `python scripts/configure_build.py --build --python-editable`;`pytest tests/python/test_write_gate_reconsolidation.py -v`(PASS);`test_tom2_e2e.py`、`test_dashboard_intervention.py` + `pytest tests/python -q` 全绿(behavior-neutral;绑定签名未改)。

- [ ] **Step 7: Commit**

```bash
git add include/starling/memory/memory_ops.hpp src/memory/memory_ops.cpp bindings/python/bind_09_brain_dynamics.cpp tests/python/test_write_gate_reconsolidation.py
git commit -m "refactor(memory): extract request_reconsolidation to gated core fn

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Gate CommitmentEngine.fulfill/withdraw(首行,签名不变)

**Files:**
- Modify: `include/starling/prospective/commitment_engine.hpp`(`#include write_gate.hpp`;签名**不改**)
- Modify: `src/prospective/commitment_engine.cpp`(`fulfill`/`withdraw` 首行 gate)
- Test: `tests/python/test_write_gate_commitment.py`(新建)

> **签名不改 → `policy_engine.cpp:415/421` + 全部 11 个直调测试(`test_commitment_engine.cpp` 等)不受影响**(bare adapter 无钩子 → 放行)。gate 用类成员 `adapter_` 的钩子。**无新成员 → 无 clang-tidy NOLINT。** DRAINING 时 policy_engine 的自动结算不冲突:Policy stage 在 DRAINING 被 `should_run_stage` shed(只留 Outbox),且无新前台写触发结算级联。

**Interfaces:** Consumes `governance::require_write_admission`(Task 1)。`fulfill`/`withdraw` 在钩子 reject 时抛 `WriteGateRejected`。

- [ ] **Step 1: 写 DRAINING 拒绝测试(失败)** — `tests/python/test_write_gate_commitment.py`:

```python
from pathlib import Path
import pytest
from starling import _core
from starling.memory import Memory, make_stub_llm


def _drained(tmp_path, name):
    mem = Memory.open(tmp_path / name, llm=make_stub_llm(default_response='[]'))
    mem._rt.begin_drain()
    assert mem._rt.health() == _core.RuntimeHealth.DRAINING
    return mem


def test_fulfill_rejected_when_draining(tmp_path):
    mem = _drained(tmp_path, "wg_ful.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.fulfill_commitment("stmt-nonexistent")


def test_withdraw_rejected_when_draining(tmp_path):
    mem = _drained(tmp_path, "wg_wd.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.withdraw_commitment("stmt-nonexistent")
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/python/test_write_gate_commitment.py -v`;预期 FAIL(无门,对不存在的 commitment 返回 no-op)。

- [ ] **Step 3: 首行 gate(hpp/cpp)** — `include/starling/prospective/commitment_engine.hpp`:`#include "starling/governance/write_gate.hpp"`(**ctor/成员/签名全不改**)。`src/prospective/commitment_engine.cpp` 的 `fulfill`(:253)/`withdraw`(:270)体内**首行**(任何 conn 查询之前)加:

```cpp
    governance::require_write_admission(adapter_);   // 门前抛 = 零 DB 写(用类成员 adapter_ 的钩子)
```

- [ ] **Step 4: 重建 + 跑测试** — `python scripts/configure_build.py --build --python-editable --test`(C++ ctest 含 policy_engine/commitment 测试全绿,签名未改);`pytest tests/python/test_write_gate_commitment.py -v`(2 例 PASS);既有 commitment 用例 + `pytest tests/python -q` 全绿。

- [ ] **Step 5: Commit**

```bash
git add include/starling/prospective/commitment_engine.hpp src/prospective/commitment_engine.cpp tests/python/test_write_gate_commitment.py
git commit -m "feat(prospective): gate CommitmentEngine fulfill/withdraw at core (adapter hook)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 全量 quiesce 集成测试 + DEGRADED 放行

**Files:**
- Test: `tests/python/test_write_gate_draining.py`(新建)

**Interfaces:** Consumes 全部 7 入口的门(Task 3/4/5)、`Runtime.begin_drain`/`note_health`、`_core.WriteGateRejected`、`_core.HealthDecision`。

- [ ] **Step 1: 写端到端测试** — `tests/python/test_write_gate_draining.py`:

```python
"""端到端:DRAINING 拒全部 7 前台写(完整 quiesce,查表证零写);DEGRADED 仍放行。"""
from pathlib import Path
import sqlite3
import pytest
from starling import _core
from starling.memory import Memory, make_stub_llm

_BELIEF = ('[{"holder":"self","holder_perspective":"FIRST_PERSON",'
           '"subject":"cog-self","predicate":"likes","object":"tea",'
           '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]')


def _mem(tmp_path, name):
    db = tmp_path / name
    return Memory.open(db, llm=make_stub_llm(default_response=_BELIEF)), db


def _total_rows(db):
    con = sqlite3.connect(str(db))
    try:
        total = 0
        for (t,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall():
            total += con.execute(f"SELECT COUNT(*) FROM \"{t}\"").fetchone()[0]
        return total
    finally:
        con.close()


def test_draining_rejects_all_foreground_writes(tmp_path):
    mem, db = _mem(tmp_path, "quiesce.db")
    mem._rt.begin_drain()
    assert mem._rt.health() == _core.RuntimeHealth.DRAINING
    core = mem._core
    before = _total_rows(db)
    for call in (
        lambda: mem.remember("Alice likes tea"),
        lambda: core.converse("hello"),
        lambda: core.forget(["s-x"]),
        lambda: core.approve_review("s-x"),
        lambda: core.request_reconsolidation("s-x", request_id="r-1"),
        lambda: core.fulfill_commitment("s-x"),
        lambda: core.withdraw_commitment("s-x"),
    ):
        with pytest.raises(_core.WriteGateRejected):
            call()
    assert _total_rows(db) == before        # 门前抛 = 全库零新行


def test_degraded_still_allows_remember(tmp_path):
    """DEGRADED 只 shed 后台 Soft stage,不拒前台写。"""
    mem, _ = _mem(tmp_path, "degraded.db")
    d = _core.HealthDecision()               # 无 degraded_decision 自由函数;手构 HealthDecision
    d.target_status = _core.RuntimeHealth.DEGRADED   # bind_14_governance.cpp:70 def_readwrite
    d.trigger = "test_backpressure"
    mem._rt.note_health(d)
    assert mem._rt.health() == _core.RuntimeHealth.DEGRADED
    r = mem.remember("Alice likes tea")      # DEGRADED 下写成功(不抛)
    assert r.engram_ref                       # 有 engram → 写落库
    mem.tick("2026-06-01T10:00:00Z")          # eng-review #3:remember 不 embed;recall 需先 tick
    assert mem.recall("tea")                  # tick 后可召回 → 真落库 + 可检索
```

- [ ] **Step 2: 跑测试确认通过** — `pytest tests/python/test_write_gate_draining.py -v`(2 例 PASS)。

- [ ] **Step 3: 全量门 + Commit** — `python scripts/configure_build.py --build --python-editable --test`(C++ ctest 全绿)+ `pytest tests/python -q`(全绿)。

```bash
git add tests/python/test_write_gate_draining.py
git commit -m "test(write-gate): end-to-end quiesce (7 entries reject on DRAINING; DEGRADED allows)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## 执行后

全 6 task 完成后走 whole-branch review(subagent-driven-development 终审,最强模型)→ PR → CI 绿 → 用户合并。

## eng-review 已解决项(2026-07-03,adapter-hook pivot)

- **#1/#2(P1,已验证):** 参数注入破 `policy_engine.cpp:415/421`(生产)+ 11 测试 → **pivot 到 adapter-hook,7 签名全不改,零破坏。**
- **#3/#4(P1/P2):** `remember` 不 embed → DEGRADED 测试 `tick` 后再 recall;DRAINING「零写」证明改**直接查表 COUNT**(非 `recall()==[]`)。
- **#5(exempt):** `plan_query` 的 `statement.recalled` = 读侧审计,不 gate(见 Deferred)。
- **#7:** converse `:186 catch` 吞内部 gate = 有意例外,已文档化(Task 3 Step 4)。
- **#8(out-of-scope):** `_reembed`/`run_replay` = dashboard admin 写,列 Deferred。
- Finding B(request_reconsolidation 直调测试)被 adapter-hook 溶解(绑定签名不变)。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_found → all resolved | 8 findings (2×P1), all folded via adapter-hook pivot |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **Outside voice:** Codex timed out (5min, high-effort reading files) → **Claude subagent** ran (fresh context). It caught what the section review + I missed: param-injection breaks production `policy_engine.cpp:415/421` + 11 direct test callers (P1×2), `remember` doesn't embed so the DEGRADED/DRAINING test assertions were invalid (P1/P2), `plan_query` writes the outbox (P2), `_reembed`/`run_replay` ungated (P3), converse propagate-vs-swallow (P3). All verified against code, all resolved.
- **CROSS-MODEL:** Section review said "param-inject, blast radius 8→1"; outside voice said "param-inject breaks src policy_engine + 11 callers → adapter-hook." Verified: outside voice correct → **pivoted to adapter-hook** (zero signature changes, behavior-neutral by construction).
- **VERDICT:** ENG CLEARED (after adapter-hook pivot) — ready to implement. The reworked design (adapter-hook) is grounded in the independent outside voice + code verification; the subagent-driven whole-branch review validates the actual implementation before PR.

NO UNRESOLVED DECISIONS
