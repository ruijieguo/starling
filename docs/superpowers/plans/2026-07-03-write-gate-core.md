<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Write-Gate Core Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

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
