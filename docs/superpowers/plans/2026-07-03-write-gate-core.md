# Write-Gate Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把健康驱动的前台写门(`RuntimeSupervisor::check_write`)从生产死代码下沉进 C++ 核心写路径,使 DRAINING/UNREADY 真正拒绝所有 7 个前台写入口并抛统一 `WriteGateRejected`;READY/DEGRADED 行为不变。

**Architecture:** 新增一处 `governance::require_write_admission(sup)` helper(抛 `WriteGateRejected`)+ 一个类型化异常;7 个前台写的 **C++ 核心函数**顶端各调一行(binding 只转发 `RuntimeSupervisor&`,门绝不落在 pybind lambda)。`request_reconsolidation` 现无核心函数(写逻辑在 lambda,pre-existing 边界违规)→ 本 slice 顺手提取为 `memoryops::request_reconsolidation` 核心函数再 gate。Python `Runtime` 加公有 `supervisor` accessor 供 `MemoryCore` 转发。

**Tech Stack:** C++20 内核(`src/` + `include/starling/`)、pybind11 绑定、Python host、SQLite;ctest + pytest;spec `docs/superpowers/specs/2026-07-03-write-gate-core-design.md`。

## Global Constraints

- **架构边界(硬):** 门是核心语义 → 实现于 C++ 核心(`src/` + `include/starling/`),置于**核心函数顶端**,**非 pybind lambda**;Python/binding 只转发 `RuntimeSupervisor&`。判据「换绑定语言是否需重写」。
- **Behavior-neutral:** READY/DEGRADED 下 7 入口行为不变,现有 `pytest tests/python` 无改动即绿。
- **门前抛 = 零 DB 写**(early throw,不建 engram、不抽取、不开事务)。写后/订阅者路径仍用 SAVEPOINT 不用 BEGIN。
- **Lock order** engine→supervisor(`check_write` 短暂持 supervisor mutex,不跨写持锁),与 `note_health`/L8 一致,无逆序。
- 拒绝用 `check_write()`(自然覆盖 UNREADY+DRAINING);`remember()` 跨 mid-drain 的 belief-已写/general-fact-被拒部分完成为**已知可接受**边界,不做原子快照。
- **构建:** `python scripts/configure_build.py --build --python-editable`(C++ + 绑定重装 `_core`,只 `pip install -e .` 不够)。clang-tidy CI-only 门,新 C++ clean by construction(identifier-length≥3、sized enums、`[[nodiscard]]`、无 empty/comment-only catch、避免 NEW `const`/`&` 数据成员→Task 5 NOLINT)。提交门:全量 ctest + `pytest tests/python` 绿。
- **git:** 显式路径 `git add`(禁 `git add .` / `-A`);不用 `--no-verify` / `--amend`。分支 `feat/write-gate-core`。

## 现有接口(实现者据此,勿改语义)

- `include/starling/governance/runtime_supervisor.hpp`:`namespace starling::governance`;`enum class WriteGateDecision : std::uint8_t { kAccept, kPreconditionFailed };`;`class RuntimeSupervisor { ... [[nodiscard]] WriteGateDecision check_write() const; StartOutcome start(); void note_health(const HealthDecision&); void begin_drain(std::string trigger="admin_drain"); RuntimeHealth health() const; ... };`。
- `include/starling/memory/memory_ops.hpp`(`namespace starling::memoryops`,已 include governance headers,用到 `RuntimeHealth`/`governance::StageTiming`):
  - `RememberOutcome remember(persistence::SqliteAdapter& adapter, extractor::LLMAdapter& llm, std::string_view prompt_template, const RememberParams& params, const extractor::ValidationPolicy& policy = {});`
  - `ConverseOutcome converse(persistence::SqliteAdapter& adapter, extractor::LLMAdapter& chat_llm, extractor::LLMAdapter& extraction_llm, retrieval::SemanticRetriever& semantic, std::string_view extraction_prompt, const ConverseParams& params, const extractor::ValidationPolicy& policy = {}, const extractor::TokenSink& on_token = {});`
  - `int forget(persistence::SqliteAdapter& adapter, std::string_view tenant, const std::vector<std::string>& ids, std::string_view now_iso);`
  - `int approve_review(persistence::SqliteAdapter& adapter, std::string_view tenant, std::string_view stmt_id, std::string_view now_iso);`
- `include/starling/prospective/commitment_engine.hpp`(`namespace starling::prospective`):`class CommitmentEngine { explicit CommitmentEngine(persistence::SqliteAdapter& a); bool fulfill(persistence::Connection&, sv stmt_id, sv tenant_id, sv now_iso); bool withdraw(...); persistence::Connection& connection(); private: persistence::SqliteAdapter& adapter_; };`
- `request_reconsolidation`:当前是 `bind_09_brain_dynamics.cpp` 里 `m.def("request_reconsolidation", [](adapter, tenant_id, stmt_id, request_id, now_iso){ conn=adapter.connection(); TransactionGuard tx(conn); BusEvent ev{...reconsolidate.requested...}; ev.idempotency_key=compute_idempotency_key("reconsolidate.requested", stmt_id, stmt_id, request_id, now_iso.substr(0,10)); OutboxWriter w(conn); w.append(ev); tx.commit(); return ev.event_id; })`。**无核心函数**。
- Python:`Runtime`(`python/starling/runtime.py`,@dataclass)有 `_sup`(`_core.RuntimeSupervisor`)、`begin_drain(trigger)`、`note_health(decision)`、`health()`。`MemoryCore.__init__(rt, ...)`(`python/starling/_memory_core.py`)持 `self.rt`;line 109 `self.commitment_engine = _core.CommitmentEngine(rt.adapter)`;line 145/181 两次 `_core.memory_remember(self.rt.adapter, self.llm, prompt, ...)`;line 260 `_core.memory_converse(self.rt.adapter, ...)`;line 304 `_core.memory_forget(self.rt.adapter, ...)`;line 313 `_core.memory_approve_review(self.rt.adapter, ...)`;line 346 `_core.request_reconsolidation(self.rt.adapter, self.tenant, stmt_id, ...)`。

## Deferred / Out of Scope(在此声明)

- 清理 vestigial Python 门(`_StubBus`/`_SqliteBackedBus`/`rt.bus`/`BusFacade`)= 单独 cleanup slice(有 test churn)。
- 后台写门(`memory_tick_all` 已被 `should_run_stage` 覆盖)。
- `run_replay`(手动维护触发,replay offline-only 写不变式,默认排除)。
- #2 并发、query-embed cache、向量扫描。

---

### Task 1: 核心机制 — WriteGateRejected + require_write_admission

**Files:**
- Modify: `include/starling/governance/runtime_supervisor.hpp`(在 `WriteGateDecision` 之后、`RuntimeSupervisor` 之外加异常 + helper;加 `#include <stdexcept>`)
- Modify: `bindings/python/bind_14_governance.cpp`(`py::register_exception`)
- Test: `tests/cpp/test_write_gate_admission.cpp`(新建)+ 注册进 `tests/cpp/CMakeLists.txt`(或既有 ctest 收集机制——比照邻近 test 文件的注册方式)

**Interfaces:**
- Produces: `governance::WriteGateRejected`(public `std::runtime_error`,`explicit WriteGateRejected(const std::string&)`);`inline void governance::require_write_admission(const RuntimeSupervisor& sup)`(reject 抛,accept 返回)。后续 Task 3/4/5 全依赖此二者。
- Consumes: 现有 `RuntimeSupervisor::check_write()` + `WriteGateDecision`。

- [ ] **Step 1: 写 helper 单测(失败)** — `tests/cpp/test_write_gate_admission.cpp`

```cpp
// tests/cpp/test_write_gate_admission.cpp
#include "starling/governance/runtime_supervisor.hpp"
#include <gtest/gtest.h>
#include <functional>
using starling::ProfileCapability;
using starling::RuntimeHealth;
using namespace starling::governance;

namespace {
// COPY of tests/cpp/test_runtime_supervisor.cpp:18 all_present() — a fully
// populated capability set. RuntimeSupervisor holds a std::mutex → non-movable,
// so it MUST be constructed in-place per TEST (never returned by value from a
// factory). embedded=true + idx-present lambda → start() reaches READY (mirrors
// that file's EmbeddedStartReadyWithoutDeferredCaps at :75-81).
ProfileCapability all_present() {
    // 复制 test_runtime_supervisor.cpp:18-35 的 all_present() 字段(tests/cpp 不受
    // clang-tidy 门,保持其风格逐字复制;字段以该文件为准)。
    return ProfileCapability{ /* …copy verbatim from test_runtime_supervisor.cpp… */ };
}
}  // namespace

TEST(WriteGateAdmission, ReadyAdmits) {
    RuntimeSupervisor sup(all_present(), /*embedded=*/true,
                          std::function<bool()>([] { return true; }));
    sup.start();                                     // preflight passes → READY
    ASSERT_EQ(sup.health(), RuntimeHealth::READY);
    EXPECT_NO_THROW(require_write_admission(sup));    // READY → no throw
}

TEST(WriteGateAdmission, DrainingRejects) {
    RuntimeSupervisor sup(all_present(), /*embedded=*/true,
                          std::function<bool()>([] { return true; }));
    sup.start();                                     // → READY
    sup.begin_drain("test");                         // READY → DRAINING
    ASSERT_EQ(sup.health(), RuntimeHealth::DRAINING);
    EXPECT_THROW(require_write_admission(sup), WriteGateRejected);
}

TEST(WriteGateAdmission, UnreadyRejects) {
    RuntimeSupervisor sup(all_present(), /*embedded=*/true,
                          std::function<bool()>([] { return false; }));  // idx absent
    sup.start();                                     // preflight fails → UNREADY
    ASSERT_EQ(sup.health(), RuntimeHealth::UNREADY);
    EXPECT_THROW(require_write_admission(sup), WriteGateRejected);
}
```

> **关键:** `RuntimeSupervisor` 有 `std::mutex` 成员 → 非可拷贝/移动,**不能**用按值返回的 factory(编译失败),每个 TEST 内就地构造(现有 `test_runtime_supervisor.cpp` 正是此范式)。`all_present()` 从 `tests/cpp/test_runtime_supervisor.cpp:18` **逐字复制**(该 helper 是 test-local;tests/cpp 不受 clang-tidy 门)。DEGRADED 放行分支在 Task 6 的 pytest 覆盖;此处 READY/DRAINING/UNREADY 三态足证 helper。

- [ ] **Step 2: 跑测试确认失败(未声明)** — `cd` 后 `python scripts/configure_build.py --build`;预期编译失败 `WriteGateRejected` / `require_write_admission` 未声明。

- [ ] **Step 3: 加异常 + helper** — `include/starling/governance/runtime_supervisor.hpp`,在 `enum class WriteGateDecision ...;`(:25)之后加,并在文件顶 `#include` 区加 `#include <stdexcept>`:

```cpp
// 治理写拒绝:前台写在 UNREADY/DRAINING 被门拦下时抛此异常。std::runtime_error
// 子类 → pybind register_exception 映射成 _core.WriteGateRejected。fail-loud,
// 跨 7 个异构返回值的写入口统一(对齐 UNREADY 的 RuntimeUnreadyError 先例)。
class WriteGateRejected : public std::runtime_error {
 public:
  explicit WriteGateRejected(const std::string& what) : std::runtime_error(what) {}
};
```

并在 `RuntimeSupervisor` 类定义**之后**(class 已完整声明,helper 可调 `check_write`)、`namespace` 闭合**之前**加:

```cpp
// 前台写准入门(策略只此一份):UNREADY/DRAINING → 抛 WriteGateRejected;
// READY/DEGRADED → 返回。7 个前台写核心函数各在顶端调一行。check_write() 仅在
// 检查瞬间短暂持 supervisor mutex(lock order engine→supervisor,与 note_health 一致)。
inline void require_write_admission(const RuntimeSupervisor& sup) {
  if (sup.check_write() != WriteGateDecision::kAccept) {
    throw WriteGateRejected("write rejected: runtime not accepting writes");
  }
}
```

- [ ] **Step 4: 注册 pybind 异常** — `bindings/python/bind_14_governance.cpp`,在 `WriteGateDecision` enum 绑定(:37-39)附近加:

```cpp
    // 前台写门拒绝 → Python _core.WriteGateRejected(std::runtime_error 子类)。
    py::register_exception<gov::WriteGateRejected>(m, "WriteGateRejected");
```

（`gov` 为该文件既有的 `namespace gov = starling::governance;` 别名——比照文件顶已用的别名;若无则用全名。）

- [ ] **Step 5: 跑测试确认通过** — `python scripts/configure_build.py --build --test`;预期 `WriteGateAdmission.*` 三例 PASS,ctest 全绿。

- [ ] **Step 6: Commit**

```bash
git add include/starling/governance/runtime_supervisor.hpp bindings/python/bind_14_governance.cpp tests/cpp/test_write_gate_admission.cpp tests/cpp/CMakeLists.txt
git commit -m "feat(governance): WriteGateRejected + require_write_admission write-gate helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Python enabler — Runtime.supervisor accessor

**Files:**
- Modify: `python/starling/runtime.py`(`Runtime` 加 `supervisor` @property)
- Modify: `python/starling/_memory_core.py`(`MemoryCore.__init__` 加 `self._sup = rt.supervisor`)
- Test: `tests/python/test_runtime_supervisor_accessor.py`(新建)

**Interfaces:**
- Consumes: `Runtime._sup`(`_core.RuntimeSupervisor`);Task 1 的 `_core.WriteGateRejected`(不在本 task 用)。
- Produces: `Runtime.supervisor` → `_core.RuntimeSupervisor`;`MemoryCore._sup`。Task 3/4/5 的 Python 调用点从 `self._sup` 取。

- [ ] **Step 1: 写测试(失败)** — `tests/python/test_runtime_supervisor_accessor.py`

```python
from pathlib import Path
from starling import _core
from starling import runtime as rt_mod


def test_runtime_exposes_supervisor_accessor(tmp_path):
    rt = rt_mod._build_local_store_sqlite_runtime(tmp_path / "acc.db")
    rt.start()
    sup = rt.supervisor
    # accessor 返回活的 C++ supervisor:check_write 可达且 READY 下 accept。
    assert sup is rt._sup
    assert sup.check_write() == _core.WriteGateDecision.kAccept
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/python/test_runtime_supervisor_accessor.py -v`;预期 FAIL(`Runtime` 无 `supervisor`)。

- [ ] **Step 3: 加 accessor** — `python/starling/runtime.py`,在 `Runtime` 类里(`health()` 方法附近)加:

```python
    @property
    def supervisor(self):
        """The live C++ governance supervisor (for passing into gated C++ write
        entries). Read-only handle; mutate via begin_drain()/note_health()."""
        return self._sup
```

并在 `python/starling/_memory_core.py` `MemoryCore.__init__` 里(`self.rt = rt` 之后)加:

```python
        # 前台写门:把活 supervisor 传给 C++ 写入口(Task 3/4/5)。
        self._sup = rt.supervisor
```

- [ ] **Step 4: 跑测试确认通过 + 现有绿** — `pytest tests/python/test_runtime_supervisor_accessor.py -v`(PASS);`pytest tests/python -q`(全绿,behavior-neutral)。

- [ ] **Step 5: Commit**

```bash
git add python/starling/runtime.py python/starling/_memory_core.py tests/python/test_runtime_supervisor_accessor.py
git commit -m "feat(runtime): public Runtime.supervisor accessor + MemoryCore._sup

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Gate memory_ops 四入口(remember/converse/forget/approve_review)

**Files:**
- Modify: `include/starling/memory/memory_ops.hpp`(4 个签名加 `sup` 参;确认 include `runtime_supervisor.hpp`)
- Modify: `src/memory/memory_ops.cpp`(4 个定义加 `sup` 参 + 首行 gate)
- Modify: `bindings/python/bind_13_memory_ops.cpp`(4 个 `m.def` 加 `RuntimeSupervisor&` 入参 + 转发 + `py::arg`)
- Modify: `python/starling/_memory_core.py`(remember 两次 + converse + forget + approve_review 共 5 个调用点传 `self._sup`)
- Test: `tests/python/test_write_gate_memory_ops.py`(新建)

**Interfaces:**
- Consumes: `governance::require_write_admission`(Task 1)、`MemoryCore._sup`(Task 2)、`_core.WriteGateRejected`(Task 1)。
- Produces: 4 个入口的新签名 `sup` 紧随 `adapter`:`memoryops::remember(adapter, sup, llm, prompt, params, policy)`;`converse(adapter, sup, chat_llm, extraction_llm, semantic, extraction_prompt, params, policy, on_token)`;`forget(adapter, sup, tenant, ids, now_iso)`;`approve_review(adapter, sup, tenant, stmt_id, now_iso)`。Python `_core.memory_remember(adapter, sup, llm, ...)` 等(sup 第二位置参)。

- [ ] **Step 1: 写 DRAINING 拒绝测试(失败)** — `tests/python/test_write_gate_memory_ops.py`

```python
from pathlib import Path
import pytest
from starling import _core
from starling.memory import Memory, make_stub_llm

_STUB = '[]'  # 空抽取:门拒时根本不会用到,但 remember 需 llm 已配置(否则先抛 LLMNotConfigured)


def _drained(tmp_path, name="wg.db"):
    mem = Memory.open(tmp_path / name, llm=make_stub_llm(default_response=_STUB))
    mem._rt.begin_drain()            # READY → DRAINING
    assert mem._rt.health() == _core.RuntimeHealth.DRAINING
    return mem


def test_remember_rejected_when_draining(tmp_path):
    mem = _drained(tmp_path)
    with pytest.raises(_core.WriteGateRejected):
        mem.remember("Alice likes tea")
    # 门前抛 = 零写:recall(读,不 gate)返回空。
    assert mem.recall("tea") == []


def test_forget_rejected_when_draining(tmp_path):
    mem = _drained(tmp_path, "wg_forget.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.forget(["stmt-nonexistent"])


def test_approve_review_rejected_when_draining(tmp_path):
    mem = _drained(tmp_path, "wg_appr.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.approve_review("stmt-nonexistent")


def test_converse_rejected_when_draining(tmp_path):
    mem = _drained(tmp_path, "wg_conv.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.converse("hello")
```

> `mem._core` = `MemoryCore`;`forget`/`approve_review`/`converse` 是其方法(`MemoryCore.forget(ids)` / `.approve_review(stmt_id)` / `.converse(message)`)。门在核心函数顶端,故即便 stmt_id 不存在也先抛 `WriteGateRejected`。

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/python/test_write_gate_memory_ops.py -v`;预期 FAIL(当前无门,`remember` 返回正常 dict / `forget` 返回 0,不抛)。

- [ ] **Step 3: 核心签名 + gate(hpp)** — `include/starling/memory/memory_ops.hpp`,4 个声明的 `adapter` 参后各加 `const governance::RuntimeSupervisor& sup,`。例:

```cpp
RememberOutcome remember(persistence::SqliteAdapter& adapter,
                         const governance::RuntimeSupervisor& sup,
                         extractor::LLMAdapter& llm,
                         std::string_view prompt_template,
                         const RememberParams& params,
                         const extractor::ValidationPolicy& policy = {});
```
同法改 `converse`（`adapter` 后插 `sup`）、`forget`（`adapter` 后插 `sup`）、`approve_review`（`adapter` 后插 `sup`）。确认文件顶已 `#include "starling/governance/runtime_supervisor.hpp"`;若只 include 了 `runtime_health.hpp`,补上。

- [ ] **Step 4: 核心定义首行 gate(cpp)** — `src/memory/memory_ops.cpp`,4 个函数定义同步签名,并在**函数体第一行**(任何 DB/事务/LLM 之前)加 `governance::require_write_admission(sup);`。例 `remember`(:23):

```cpp
RememberOutcome remember(persistence::SqliteAdapter& adapter,
                         const governance::RuntimeSupervisor& sup,
                         extractor::LLMAdapter& llm,
                         std::string_view prompt_template,
                         const RememberParams& params,
                         const extractor::ValidationPolicy& policy) {
    governance::require_write_admission(sup);   // 门前抛 = 零 DB 写
    /* …既有函数体不变… */
```
`converse`(:103)体内首行同加(在 recall/generate 之前）；`forget`、`approve_review` 定义同法。**注意** `converse` 内部会调 `remember`(:176)——那次内部调用也需传 `sup`(见下),但 gate 只在最外层 `converse` 顶端一次即够;内部 `remember` 的 gate 会二次检查(无害,健康态未变)。

- [ ] **Step 5: 绑定转发(bind_13)** — `bindings/python/bind_13_memory_ops.cpp`,4 个 `m.def` 的 lambda 参数列表在 `SqliteAdapter& adapter` 后加 `starling::governance::RuntimeSupervisor& sup,`,转发给核心函数时把 `sup` 作第二实参,并在 `py::arg("adapter")` 后加 `py::arg("sup")`。例 memory_remember:

```cpp
    m.def("memory_remember",
          [](starling::persistence::SqliteAdapter& adapter,
             starling::governance::RuntimeSupervisor& sup,       // NEW
             starling::extractor::LLMAdapter& llm, /* …其余不变… */) {
              /* …构造 RememberParams rp… */
              auto out = starling::memoryops::remember(adapter, sup, llm, prompt, rp, policy);  // sup 第二参
              /* …既有 dict 组装不变… */
          },
          py::arg("adapter"), py::arg("sup"), /* …其余 py::arg 不变… */);
```
`memory_converse`、`memory_forget`、`memory_approve_review` 同法(各自 lambda 加 `sup` 参 + 转发 + `py::arg("sup")`)。

- [ ] **Step 6: Python 调用点传 sup** — `python/starling/_memory_core.py`:
  - `remember`(:145 belief 与 :181 general-fact 两处):`_core.memory_remember(self.rt.adapter, self._sup, self.llm, prompt, ...)`。
  - `converse`(:260):`_core.memory_converse(self.rt.adapter, self._sup, ...)`。
  - `forget`(:304):`_core.memory_forget(self.rt.adapter, self._sup, tenant=..., ...)`。
  - `approve_review`(:313):`_core.memory_approve_review(self.rt.adapter, self._sup, tenant=..., ...)`。
  （sup 为第二位置参,紧随 adapter,与 binding `py::arg` 顺序一致。）

- [ ] **Step 7: 重建 + 跑测试** — `python scripts/configure_build.py --build --python-editable`;`pytest tests/python/test_write_gate_memory_ops.py -v`(4 例 PASS);`pytest tests/python -q`(全绿 = behavior-neutral,READY 下 4 入口行为不变)。

- [ ] **Step 8: Commit**

```bash
git add include/starling/memory/memory_ops.hpp src/memory/memory_ops.cpp bindings/python/bind_13_memory_ops.cpp python/starling/_memory_core.py tests/python/test_write_gate_memory_ops.py
git commit -m "feat(memory): gate remember/converse/forget/approve_review foreground writes

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 提取 request_reconsolidation 为核心函数 + gate

**Files:**
- Modify: `include/starling/memory/memory_ops.hpp`(声明 `request_reconsolidation`)
- Modify: `src/memory/memory_ops.cpp`(定义:搬 lambda 体 + gate;确认 include `bus/bus_event.hpp`、`bus/outbox_writer.hpp`、`persistence/transaction_guard.hpp`——若未 include 则补,或若 include 变重则新建 `src/memory/reconsolidation_request.cpp` 同 namespace)
- Modify: `bindings/python/bind_09_brain_dynamics.cpp`(:200 lambda → 转发核心函数)
- Modify: `python/starling/_memory_core.py`(`request_reconsolidation` 传 `self._sup`)
- Test: `tests/python/test_write_gate_reconsolidation.py`(新建)

**Interfaces:**
- Consumes: `governance::require_write_admission`(Task 1)、`MemoryCore._sup`(Task 2)。
- Produces: `std::string memoryops::request_reconsolidation(persistence::SqliteAdapter& adapter, const governance::RuntimeSupervisor& sup, std::string_view tenant_id, std::string_view stmt_id, std::string_view request_id, std::string_view now_iso);`(返回 `event_id`)。Python `_core.request_reconsolidation(adapter, sup, tenant_id, stmt_id, request_id, now_iso)`。

- [ ] **Step 1: 写 DRAINING 拒绝测试(失败)** — `tests/python/test_write_gate_reconsolidation.py`

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

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/python/test_write_gate_reconsolidation.py -v`;预期 FAIL(当前 lambda 无门 → 正常 append + 返回 event_id)。

- [ ] **Step 3: 声明核心函数(hpp)** — `include/starling/memory/memory_ops.hpp`,`approve_review` 声明后加:

```cpp
// P3.a3 再巩固显式触发:发 reconsolidate.requested 事件(payload {stmt_id, request_id}),
// engine 异步开窗。前台写 → 经写门。返回 outbox event_id。(边界归位:原写逻辑在
// bind_09 lambda,本 slice 提取入核心以受门管辖 + 守「核心写在 C++」硬规。)
std::string request_reconsolidation(persistence::SqliteAdapter& adapter,
                                    const governance::RuntimeSupervisor& sup,
                                    std::string_view tenant_id,
                                    std::string_view stmt_id,
                                    std::string_view request_id,
                                    std::string_view now_iso);
```

- [ ] **Step 4: 定义核心函数(cpp)** — `src/memory/memory_ops.cpp`(或新建 `src/memory/reconsolidation_request.cpp`,`namespace starling::memoryops`),搬 lambda 体、首行 gate:

```cpp
std::string request_reconsolidation(persistence::SqliteAdapter& adapter,
                                    const governance::RuntimeSupervisor& sup,
                                    std::string_view tenant_id,
                                    std::string_view stmt_id,
                                    std::string_view request_id,
                                    std::string_view now_iso) {
    governance::require_write_admission(sup);            // 门前抛 = 零 DB 写
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
        "reconsolidate.requested", stmt_id, stmt_id, request_id,
        now_iso.substr(0, 10));                          // 同 request_id 当日去重
    bus::OutboxWriter w(conn);
    w.append(ev);
    tx.commit();
    return ev.event_id;
}
```
> 确认 include:`starling/bus/bus_event.hpp`、`starling/bus/outbox_writer.hpp`、`starling/persistence/transaction_guard.hpp`(或 memory_ops.cpp 里等价的 conn/tx 头)。字段名/去重逻辑与原 lambda **逐字一致**(behavior-neutral)。`std::string_view` 参转 `std::string` 供 BusEvent 字段(原 lambda 收 `const std::string&`,语义相同)。

- [ ] **Step 5: 绑定改转发(bind_09)** — `bindings/python/bind_09_brain_dynamics.cpp:200`,把整段 lambda 换成转发核心函数:

```cpp
    m.def("request_reconsolidation",
          [](starling::persistence::SqliteAdapter& adapter,
             starling::governance::RuntimeSupervisor& sup,
             const std::string& tenant_id, const std::string& stmt_id,
             const std::string& request_id, const std::string& now_iso) {
              return starling::memoryops::request_reconsolidation(
                  adapter, sup, tenant_id, stmt_id, request_id, now_iso);
          },
          py::arg("adapter"), py::arg("sup"), py::arg("tenant_id"),
          py::arg("stmt_id"), py::arg("request_id"), py::arg("now_iso"),
          "Emit reconsolidate.requested (explicit trigger #4); engine opens "
          "the plastic window asynchronously. Gated: rejected while DRAINING/UNREADY.");
```
（确认 `bind_09` 已 include `starling/memory/memory_ops.hpp`;若无则补。原先的 `TransactionGuard`/`BusEvent`/`OutboxWriter` include 若 bind_09 无其他用户可留可删,勿引入未用告警。)

- [ ] **Step 6: Python 传 sup** — `python/starling/_memory_core.py:346` `request_reconsolidation`:`_core.request_reconsolidation(self.rt.adapter, self._sup, self.tenant, stmt_id, request_id=request_id, now_iso=...)`(sup 第二位置参)。

- [ ] **Step 7: 重建 + 跑测试** — `python scripts/configure_build.py --build --python-editable`;`pytest tests/python/test_write_gate_reconsolidation.py -v`(PASS);既有再巩固相关用例(grep `request_reconsolidation` in tests/python)+ `pytest tests/python -q` 全绿(behavior-neutral)。

- [ ] **Step 8: Commit**

```bash
git add include/starling/memory/memory_ops.hpp src/memory/memory_ops.cpp bindings/python/bind_09_brain_dynamics.cpp python/starling/_memory_core.py tests/python/test_write_gate_reconsolidation.py
git commit -m "refactor(memory): extract request_reconsolidation to core + gate it

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Gate CommitmentEngine.fulfill/withdraw(构造注入 supervisor)

**Files:**
- Modify: `include/starling/prospective/commitment_engine.hpp`(ctor 加 `const RuntimeSupervisor&` 参 + 成员 + NOLINT)
- Modify: `src/prospective/commitment_engine.cpp`(`fulfill`/`withdraw` 首行 gate;确认 ctor 定义若在 cpp 则同步)
- Modify: `bindings/python/bind_12_prospective.cpp`(`CommitmentEngine` 构造绑定加 `RuntimeSupervisor&`)
- Modify: `python/starling/_memory_core.py:109`(`_core.CommitmentEngine(rt.adapter, rt.supervisor)`)
- Test: `tests/python/test_write_gate_commitment.py`(新建)

**Interfaces:**
- Consumes: `governance::require_write_admission`(Task 1)、`Runtime.supervisor`(Task 2)。
- Produces: `CommitmentEngine(persistence::SqliteAdapter& a, const governance::RuntimeSupervisor& sup)`;`fulfill`/`withdraw` DRAINING/UNREADY 抛 `WriteGateRejected`。Python `_core.CommitmentEngine(adapter, sup)`。

- [ ] **Step 1: 写 DRAINING 拒绝测试(失败)** — `tests/python/test_write_gate_commitment.py`

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

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/python/test_write_gate_commitment.py -v`;预期 FAIL(当前 fulfill/withdraw 对不存在的 commitment 返回 no-op dict,不抛)。

- [ ] **Step 3: ctor + 成员 + gate(hpp/cpp)** — `include/starling/prospective/commitment_engine.hpp`:ctor 改双参,加成员(带 NOLINT + 借用句柄理由),并 `#include "starling/governance/runtime_supervisor.hpp"`:

```cpp
    CommitmentEngine(persistence::SqliteAdapter& a,
                     const governance::RuntimeSupervisor& sup)
        : adapter_(a), sup_(sup) {}
```
```cpp
 private:
    persistence::SqliteAdapter& adapter_;
    // 借用句柄:supervisor 由调用方(Runtime)持有、生命周期长于本引擎;不可拷贝。
    // NOLINT: 有意的引用成员(与 adapter_ 同模式)。
    const governance::RuntimeSupervisor& sup_;  // NOLINT(cppcoreguidelines-avoid-const-or-ref-data-members)
```
`fulfill`/`withdraw` 定义(`src/prospective/commitment_engine.cpp`)体内**首行**加 `governance::require_write_admission(sup_);`(在任何 conn/查询之前)。

> clang-tidy:新增 `const&` 成员触 `cppcoreguidelines-avoid-const-or-ref-data-members` → 成员行尾 `// NOLINT(...)` 已加(见 [[clang-tidy-ci-only-gate-gotchas]]:NOLINT 必须在成员**本行**,不能置于上方注释块)。`adapter_` 已是引用成员(grandfathered);新成员不 grandfathered 故需显式 NOLINT。

- [ ] **Step 4: 绑定构造改双参(bind_12)** — `bindings/python/bind_12_prospective.cpp:68`,`py::class_<CommitmentEngine>` 的 `.def(py::init<...>())` 或构造 lambda 加 `RuntimeSupervisor&`:

```cpp
        .def(py::init<starling::persistence::SqliteAdapter&,
                      const starling::governance::RuntimeSupervisor&>(),
             py::arg("adapter"), py::arg("sup"))
```
（若原绑定用显式 lambda 构造,镜像其形式加 `sup` 参。确认 `bind_12` include `runtime_supervisor.hpp`。）

- [ ] **Step 5: Python 双参构造** — `python/starling/_memory_core.py:109`:`self.commitment_engine = _core.CommitmentEngine(rt.adapter, rt.supervisor)`。

- [ ] **Step 6: 重建 + 跑测试** — `python scripts/configure_build.py --build --python-editable`;`pytest tests/python/test_write_gate_commitment.py -v`(2 例 PASS);既有 commitment 用例(`test_p2c_commitment_lifecycle.py` 等)+ `pytest tests/python -q` 全绿(behavior-neutral)。

- [ ] **Step 7: Commit**

```bash
git add include/starling/prospective/commitment_engine.hpp src/prospective/commitment_engine.cpp bindings/python/bind_12_prospective.cpp python/starling/_memory_core.py tests/python/test_write_gate_commitment.py
git commit -m "feat(prospective): gate CommitmentEngine fulfill/withdraw via injected supervisor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 全量 quiesce 集成测试 + DEGRADED 放行

**Files:**
- Test: `tests/python/test_write_gate_draining.py`(新建)

**Interfaces:**
- Consumes: 全部 7 入口的门(Task 3/4/5)、`Runtime.begin_drain`/`note_health`、`_core.WriteGateRejected`、`_core.HealthSampler`/`degraded_decision`(驱 DEGRADED)。

- [ ] **Step 1: 写端到端测试** — `tests/python/test_write_gate_draining.py`

```python
"""端到端:DRAINING 拒全部 7 前台写(完整 quiesce);DEGRADED 仍放行(DEGRADED≠DRAINING)。"""
from pathlib import Path
import pytest
from starling import _core
from starling.memory import Memory, make_stub_llm

_BELIEF = ('[{"holder":"self","holder_perspective":"FIRST_PERSON",'
           '"subject":"cog-self","predicate":"likes","object":"tea",'
           '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]')


def _mem(tmp_path, name):
    return Memory.open(tmp_path / name, llm=make_stub_llm(default_response=_BELIEF))


def test_draining_rejects_all_foreground_writes(tmp_path):
    mem = _mem(tmp_path, "quiesce.db")
    mem._rt.begin_drain()
    assert mem._rt.health() == _core.RuntimeHealth.DRAINING
    core = mem._core
    with pytest.raises(_core.WriteGateRejected):
        mem.remember("Alice likes tea")
    with pytest.raises(_core.WriteGateRejected):
        core.converse("hello")
    with pytest.raises(_core.WriteGateRejected):
        core.forget(["s-x"])
    with pytest.raises(_core.WriteGateRejected):
        core.approve_review("s-x")
    with pytest.raises(_core.WriteGateRejected):
        core.request_reconsolidation("s-x", request_id="r-1")
    with pytest.raises(_core.WriteGateRejected):
        core.fulfill_commitment("s-x")
    with pytest.raises(_core.WriteGateRejected):
        core.withdraw_commitment("s-x")
    # 门前抛 = 零写:读路径证明库空。
    assert mem.recall("tea") == []


def test_degraded_still_allows_remember(tmp_path):
    """DEGRADED 只 shed 后台 Soft stage,不拒前台写。"""
    mem = _mem(tmp_path, "degraded.db")
    # 无 degraded_decision 自由函数:HealthDecision 是 Python-constructible
    # (bind_14_governance.cpp:68 def_readwrite target_status/trigger),note_health
    # 收它。READY→DEGRADED 合法转移。
    d = _core.HealthDecision()
    d.target_status = _core.RuntimeHealth.DEGRADED
    d.trigger = "test_backpressure"
    mem._rt.note_health(d)
    assert mem._rt.health() == _core.RuntimeHealth.DEGRADED
    r = mem.remember("Alice likes tea")     # DEGRADED 下写仍成功
    assert r.engram_ref                      # 有 engram → 写成功
    assert mem.recall("tea")                 # 可召回 → 真落库
```

> `_core.HealthDecision` 有 `target_status`(`_core.RuntimeHealth`)、`trigger`、`metrics_snapshot` 三个 def_readwrite 字段(`bind_14_governance.cpp:68-72`),默认构造 + 赋值即可;`note_health(decision)` 已绑定(:90)。这是驱 DEGRADED 的唯一 Python 途径(无 `degraded_decision` 自由函数)。

- [ ] **Step 2: 跑测试确认通过** — `pytest tests/python/test_write_gate_draining.py -v`(2 例 PASS)。

- [ ] **Step 3: 全量门 + Commit** — `python scripts/configure_build.py --build --python-editable --test`(C++ ctest 全绿)+ `pytest tests/python -q`(全绿)。

```bash
git add tests/python/test_write_gate_draining.py
git commit -m "test(write-gate): end-to-end quiesce (7 entries reject on DRAINING; DEGRADED allows)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## 执行后

全 6 task 完成后走 whole-branch review(subagent-driven-development 的终审,最强模型)→ PR → CI 绿 → 用户合并。**本 plan 先经 /plan-eng-review(outside-voice)锁定再执行。**
