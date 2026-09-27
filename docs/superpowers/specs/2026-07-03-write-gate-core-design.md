<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Write-Gate Core — Design Spec
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> Slice: D-latent 写门修复。把健康驱动的前台写门(`RuntimeSupervisor::check_write`)从**生产死代码**下沉进 C++ 核心写路径,使 DRAINING/UNREADY 真正拒绝**所有前台写**。

> **⚠ REVISION(2026-07-03,eng-review pivot — 以 plan 为准):** 本 spec 原设计为「7 个核心写函数各加 `const RuntimeSupervisor& sup` 参 + `require_write_admission(sup)`」。/plan-eng-review 的 outside voice 验证发现**参数注入破生产 `policy_engine.cpp:415/421` + 11 个直调测试**(fulfill/withdraw 被 PolicyEngine 自动结算 + 大量测试直调,无 supervisor)。**机制已 pivot 为 adapter-hook**:`SqliteAdapter` 持可空 `std::function<bool()>` 写门钩子,`Runtime` 构造时 `install_write_gate` 设一次,7 个核心写函数首行 `require_write_admission(adapter)`(§4/§5 的「传 sup」全部作废,改「读 adapter 钩子」)。**零签名改动、behavior-neutral by construction**。另:`plan_query` 的 `statement.recalled` emit = 读侧审计**豁免**;`_reembed`/`run_replay` = dashboard admin 写**列 out-of-scope**;converse `:186 catch` 吞内部 gate = 对 §6「统一传播」的有意例外。完整修订见 `docs/superpowers/plans/2026-07-03-write-gate-core.md`(含「eng-review 已解决项」)。

**状态:** 设计已定(brainstorm 决策 D1=A 完整切片、D2=A 所有前台写、D3=A 统一异常),待用户过 spec → writing-plans → /plan-eng-review(outside-voice)→ subagent 执行。

**分支:** `feat/write-gate-core`(off main @ 2846188)。

---

## 1. 问题(已由 /investigate 2026-07-03 确认)

`RuntimeSupervisor::check_write()`(`src/governance/runtime_supervisor.cpp:86-94`)语义正确:`accept = READY || DEGRADED`,即 **UNREADY / DRAINING → `kPreconditionFailed`**。但它是**每一条生产写路径上的死代码**:

- `check_write` **零 C++ 调用者**(grep 仅 def + decl + `bind_14_governance.cpp` 绑定)。
- 唯一调用者是两个 Python bus wrapper `_StubBus` / `_SqliteBackedBus`(`python/starling/runtime.py`),写前查门。
- 生产工厂 `_build_local_store_sqlite_runtime`(`runtime.py:186-198`)先在 `Runtime.__post_init__` 建带门的 `_SqliteBackedBus`,紧接着 `rt.bus = BusFacade(adapter)`(:197)**覆盖**掉;`BusFacade` 无门、不持 supervisor,且**生产代码根本不调 `rt.bus`**。
- 真实前台写路径 = `Memory.remember → MemoryCore.remember → _core.memory_remember(self.rt.adapter, ...)`(`_memory_core.py:145`,直接 C++);`src/memory/` + `src/bus/` 对 `check_write`/`RuntimeSupervisor` **零引用**;C++ `Bus` 构造 `explicit Bus(SqliteAdapter&)` 无 supervisor 句柄 → 结构上无从查门。

**关键不对称:** 后台 tick 路径**已**按健康态 shed(`memory_ops.cpp:214-291` 的 `should_run_stage`,DRAINING→只留 Outbox),所以系统「看起来受治理」而前台写照穿。健康治理是半接线的:后台守、前台漏。

**严重度:当前 latent,但对 dashboard 异步 host 更接近 live。** DRAINING 生产上仅经 `begin_drain()`(优雅关机)到达——嵌入式 `Memory` facade 单进程同步,天然无 drain↔write 竞态;但 **dashboard 异步 host**(`dashboard/app.py:73-74` 关机调 `begin_drain`,`engine.py` 与 `Memory` 共用同一 `MemoryCore`)下,「drain 时仍有 in-flight remember/converse」是真实竞态。门本该是「关机时 quiesce 前台写、收敛 outbox、干净退出」的执行点,而它什么都不执行;并发/背压落地(M0.9+「when concurrency lands」)后成真实正确性洞。

---

## 2. 目标 / 非目标

**目标:** DRAINING/UNREADY 时,**所有前台(同步、facade 驱动)写入口**在**任何 DB 变更之前**被拒,以统一、fail-loud、无法静默吞的方式向调用方表达;READY/DEGRADED 下行为**逐字节不变**(behavior-neutral)。门实现于 **C++ 核心**,换绑定语言无需重写。

**非目标(本 slice 不做):**
- 后台 tick 写(已被 `should_run_stage` 覆盖)。
- 清理 vestigial Python 门(`_StubBus`/`_SqliteBackedBus`/`rt.bus`/`BusFacade`)—— 列为 §7 follow-up 债。
- #2 并发、query-embed cache、向量扫描。
- 改 `check_write` 的状态语义、改健康状态机、给 DRAINING 加 retry_after。

---

## 3. 前台写入口(gating 范围,~7 个,跨 3 子系统)

| Python facade 方法 | C++ 核心函数 | 绑定文件 | 写什么 |
|---|---|---|---|
| `MemoryCore.remember` | `memoryops::remember`(remember() 的首个核心写;见下方短路注) | `bind_13_memory_ops.cpp` | engram + statements + 事件 |
| `MemoryCore.converse` | `memoryops::converse` | `bind_13_memory_ops.cpp` | chat turn 证据(binding 注释确认 "the reply is still generated + persisted") |
| `MemoryCore.forget` | `memoryops::memory_forget` 核心 | `bind_13_memory_ops.cpp` | tombstone/删除 |
| `MemoryCore.approve_review` | `memoryops::memory_approve_review` 核心 | `bind_13_memory_ops.cpp` | review 状态变更 |
| `MemoryCore.request_reconsolidation` | `request_reconsolidation` 核心 | `bind_09_brain_dynamics.cpp:200` | 开再巩固窗口 |
| `MemoryCore.fulfill_commitment` | `prospective::CommitmentEngine::fulfill` | `bind_12_prospective.cpp` | 承诺状态变更 |
| `MemoryCore.withdraw_commitment` | `prospective::CommitmentEngine::withdraw` | `bind_12_prospective.cpp` | 承诺状态变更 |

**排除(读路径,无需门):** `recall` / `plan_query` / `build_working_set` / `latest_event_location`。
**排除(后台):** `tick` → `memory_tick_all`(内部 `should_run_stage` 已覆盖)。`run_replay`(手动维护触发,replay 语义)本 slice **不纳入**——它不是标准前台数据写,且 replay 有自己的 offline-only 写不变式([[replay-write-reentrancy-offline-only]]);如需可另议,默认排除。

> **remember() 短路注:** `MemoryCore.remember` 内有多个写子步——belief `memoryops::remember` → `EpisodicExtractor.extract` → `PerceptionReconstructor.reconstruct` → general-fact `memoryops::remember`(第二次同函数)。gate 在 `memoryops::remember` 顶端,故 remember() 的**首个**写(belief)在 DRAINING 时先抛 `WriteGateRejected`,异常传播出 remember() → episodic/perception/general-fact 子步天然不执行。因此**无需**单独给 `EpisodicExtractor` / `PerceptionReconstructor` 加门(它们仅在 remember() 内、belief 写之后被调,belief 门已短路整体)。已核实二者无其他前台调用点。

> **架构约束(硬):** 门必须置于上表**「C++ 核心函数」列的 src/ 函数顶端**,**不是** pybind lambda。否则换绑定语言直调核心函数仍绕过门——正是本 slice 要修的 bug。binding 层只负责把 supervisor 转发进核心函数。

---

## 4. 机制(核心,一处)

新增于 `starling::governance`(`include/starling/governance/` + `src/governance/`):

```cpp
// 类型化异常:治理写拒绝。std::runtime_error 子类,pybind register_exception。
class WriteGateRejected : public std::runtime_error {
public:
    explicit WriteGateRejected(const std::string& what) : std::runtime_error(what) {}
};

// 共享 admission helper:策略只此一份。7 个前台写核心函数各调一行。
// health != accept(即 UNREADY/DRAINING)→ throw;READY/DEGRADED → 直接返回。
inline void require_write_admission(const RuntimeSupervisor& sup) {
    if (sup.check_write() != WriteGateDecision::kAccept) {
        throw WriteGateRejected("write rejected: runtime not accepting writes");
    }
}
```

**为何 supervisor-param + 共享 helper(考虑过的替代):**
- **选中:** 每个核心写函数签名加 `const RuntimeSupervisor& sup`,首行 `require_write_admission(sup)`。最小、显式、可测;策略集中一处。
- 弃 **B2 新造 `WriteGate` 抽象**:单一策略下是 YAGNI(一个消费者不值一个新类型)。
- 弃 **B3 把 7 个写全 route 进 Bus 单咽喉**:大重构;Bus 被后台共用,DRAINING 时 Outbox 仍要写,盲目 gate Bus 会阻断 drain。

---

## 5. 接线

**C++ 核心(src/,7 处):**
- `memoryops::remember` / `converse` / `memory_forget` 核心 / `memory_approve_review` 核心(`src/memory/memory_ops.cpp` 及同 namespace):签名加 `const governance::RuntimeSupervisor& sup`,首行 `governance::require_write_admission(sup)`。
- `request_reconsolidation` 核心(brain_dynamics TU):同样。
- `prospective::CommitmentEngine`:**构造时**持 `const governance::RuntimeSupervisor&`(对象型入口,构造注入比每调用传参干净);`fulfill` / `withdraw` 首行 gate。

**绑定(bindings/,转发):**
- `bind_14_governance.cpp`:`py::register_exception<governance::WriteGateRejected>(m, "WriteGateRejected")`。
- `bind_13` / `bind_09` / `bind_12`:各 `m.def` / lambda / `CommitmentEngine` 构造签名加 `RuntimeSupervisor&` 入参并转发给核心函数。

**Python(python/starling/):**
- `Runtime` 加公有 accessor `supervisor`(property 返回 `self._sup`)——避免 `MemoryCore` reach 私有 `rt._sup`,call site 读得干净。
- `MemoryCore.__init__` 抓 `self._sup = rt.supervisor`;7 个写调用点把 `self._sup` 传下去;`CommitmentEngine` 构造改 `_core.CommitmentEngine(rt.adapter, rt.supervisor)`。

---

## 6. 拒绝契约与语义

- **每个前台写核心函数** DRAINING/UNREADY 抛 `governance::WriteGateRejected`;pybind 映射成 Python 异常 `_core.WriteGateRejected`。
- **`Memory.remember/converse/forget/approve_review/request_reconsolidation/fulfill_commitment/withdraw_commitment` 让它传播**(对齐 `RuntimeUnreadyError` 传播先例;dashboard async host 在请求边界 catch → 返错给 client)。
- **门前抛 = 零 DB 写**:异常在核心函数首行、任何 engram/抽取/statement 写入之前抛出。remember 的 episodic/general-fact/perception 子步骤天然不执行(第一步就抛)。
- **UNREADY 覆盖:** 用 `check_write()`(自然含 UNREADY + DRAINING),语义统一。运行时 UNREADY 另已被 `start()` raise `RuntimeUnreadyError` + exit 78 覆盖(worker 不启动),故门的 UNREADY 分支实践中冗余但无害。
- **admission-at-start 语义(TOCTOU 明确为预期):** 门在写**开始**处做准入检查。check→write 之间健康态若翻转(如 check 过后 `begin_drain`),已准入的 in-flight 写照常完成——这正是「draining = 等 in-flight 写排空、拒新写」的语义,非 bug。`check_write` 仅在检查瞬间短暂持 supervisor mutex 后即释放,不跨写持锁。
- **remember() 跨 mid-drain 的部分完成(已知、可接受、非本 slice 消除):** 单个 `remember()` 有两次 `memoryops::remember`(belief、general-fact),各自独立 gate。若 drain 恰在两者之间落地(仅 dashboard 异步 host、且 ~ms 级窗口),belief 已写入、general-fact 被拒 → remember() 抛 `WriteGateRejected` 但 belief engram 已落。这**非数据损坏**(belief 是合法 engram),是 admission-at-start 的自然结果。嵌入式 `Memory` facade 单进程同步无此竞态。让 remember() 对门原子(开头快照一次 admission、后续子步不再 gate)属过度设计,本 slice 不做;记录在案。
- **Lock order(与 L8 一致,无逆序):** dashboard 调写时持 engine-RLock;核心函数首行 `require_write_admission → check_write` 取 supervisor mutex → engine→supervisor 顺序,与 `note_health` 相同。核心函数不在持 supervisor mutex 时再取 engine 锁。

---

## 7. 测试策略

1. **helper 单测(C++ ctest):** `require_write_admission` —— READY/DEGRADED 放行(不抛);UNREADY/DRAINING 抛 `WriteGateRejected`。驱动一个真 `RuntimeSupervisor`(start→READY;begin_drain→DRAINING;preflight-fail→UNREADY)。
2. **Behavior-neutral(现有 pytest 全绿即证):** READY(及 DEGRADED)下 7 个入口行为逐一不变——现有 `tests/python` 覆盖 remember/converse/forget/approve/reconsolidation/commitment 的用例应无一改动即绿。
3. **DRAINING 真拒(驱动真实 facade 路径,不只单测 helper):** 按 [[replay-count-tops-at-one]] 教训——`_build_local_store_sqlite_runtime` → `start()` → `rt.begin_drain()` → 逐个调 7 个写入口 → 断言各抛 `_core.WriteGateRejected` **且** DB 无新行(engram/statements/commitment 状态未变)。新增 `tests/python/test_write_gate_draining.py`。
4. **DEGRADED 仍放行(区分 DEGRADED≠DRAINING):** note_health 驱到 DEGRADED,remember 仍成功写(证明门只拒 UNREADY/DRAINING)。

---

## 8. Follow-up 债(非本 slice,记录在案)

- **清理 vestigial Python 门:** `_StubBus` / `_SqliteBackedBus` 的 check_write 分支、`rt.bus` 覆盖、`BusFacade`(多 test 直接构造)现已确认生产死代码。本 slice 加真门后它们双重死。清理有 test churn(touches `runtime.py` 的 `Runtime` dataclass + 若干 test),单独一个 cleanup slice 处理。见 [[health-write-gate-dead-code-on-prod-path]]。

---

## 9. 全局约束(copy 进 plan 的 Global Constraints)

- **架构边界(硬):** 门是核心语义 → 实现于 C++ 核心(src/ + include/starling/),置于**核心函数顶端非 pybind lambda**;Python/binding 只转发 supervisor。判据「换绑定语言是否需重写」。
- **Behavior-neutral:** READY/DEGRADED 下 7 个入口行为不变,现有 pytest 无改动即绿。
- **写不变式:** 门前抛 = 零 DB 写(early throw,不建 engram、不抽取)。写后/订阅者路径仍用 SAVEPOINT 不用 BEGIN([[replay-write-reentrancy-offline-only]] 不受本 slice 影响)。
- **构建:** `python scripts/configure_build.py --build --python-editable`(C++ + 绑定重装 `_core`)。clang-tidy CI-only 门,新 C++ clean by construction(identifier-length≥3、sized enums、nodiscard、无 empty catch、避免 NEW const/ref 数据成员;`CommitmentEngine` 新增 `const RuntimeSupervisor&` 成员会触 `cppcoreguidelines-avoid-const-or-ref-data-members` → 需 `// NOLINT` + 借用句柄理由注释,见 [[clang-tidy-ci-only-gate-gotchas]])。ctest + `pytest tests/python` 必须绿。
- **git:** 显式路径 `git add`(禁 `git add .`/`-A`);不用 `--no-verify`/`--amend`。

---

## 10. spec 阶段已核实项

- ✅ `memory_converse` **确实写**(binding 注释 "the reply is still generated + persisted")→ 留在 scope。
- ✅ `Runtime._sup` → 加公有 `supervisor` accessor(§5),不 reach 私有。
- ✅ Lock order engine→supervisor 与 L8/`note_health` 一致(§6),无逆序。
- ✅ TOCTOU = 预期的 admission-at-start 语义(§6),非缺陷。
