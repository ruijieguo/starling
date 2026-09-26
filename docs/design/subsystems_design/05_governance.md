<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../../superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Runtime Governance
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **语义证据契约状态（2026-09-12）**：已实现并通过完整工程验证；真实诊断已完成并核验，质量门槛未通过，默认关闭，设计见 [Source-Grounded Claim Contract](../../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md)。准入策略保持 fail-closed：技术失败、证据跨度失败与合法语义范围拒绝分别计数；技术失败阻止运行被标为无错误完成，语义错误阻止质量门槛通过。

## 2026-09-11 语义证据契约

两次模型调用都由 C++ Extractor 控制并位于存储事务外；ExtractionLlmResult 回执保留实际 prompt/hash/raw/error 和 token/耗时。scope guard 的合法语义拒绝与缺字段、错误引用、传输失败分别计数。评测遇到技术错误必须为 `complete_with_errors`，失败保留在固定分母；仅通过全部质量门槛才可讨论启用默认策略。

实现状态与评测证据统一见 [同步清单](../claim_contract_sync.md)。

## 功能定义

Runtime Governance 不是业务子系统，是运行时的健康监控、背压控制与长任务账本。它管辖：READY / DEGRADED / DRAINING / UNREADY 四态转换、PipelineRun 长任务追踪与断点恢复、ScopedWorkGate 分域并发限流、critical lane 优先级保护与 trace retention 分级。它不管：Statement 内容、检索质量、抽取准确率，以及任何业务语义。

## 输入

- 子系统 capability 声明（启动期）
- 子系统运行时心跳（队列深度、错误率、依赖状态）
- 长任务 claim/confirm/cancel 请求（来自 Replay / Extractor / Projection 等）
- ScopedWorkGate acquire/release 请求

## 输出

- RuntimeHealth 状态变更事件（READY / DEGRADED / DRAINING / UNREADY）
- PreflightResult（启动准入决策 + 缺失能力清单）
- PipelineRun 账本（含 run_id / status / counters / watermark）
- ScopedWorkGate 决策（accept / reject + reject_reason）

## 主要流程

**启动 preflight**

1. 读取 `ProfileCapability`，逐项校验硬能力（主表可用、outbox 可提交、tenant isolation 存在、向量存储就绪）。
2. 任一硬能力缺失 → 直接进入 `UNREADY`，fail-closed，前台与后台均不启动。
3. 全部通过 → 进入 `READY`，后台 worker 开始 claim 任务。

> **实现状态(P3.c1 Phase 1，2026-06-28，commits 114a9cf..ad5f23c)：** 启动 preflight 的决策语义已归位 C++（消除原 Python 边界违规）。能力策略 = `required_capabilities(embedded)`（纯函数，`src/governance/capability_policy.cpp`，替换原 `runtime.py` 全局可变 relax）；准入决策 = `RuntimeSupervisor`（`src/governance/runtime_supervisor.cpp`：capability+index preflight → READY/UNREADY、fail-closed `EX_CONFIG`=78 退出码、READY 写门 `check_write()`）；index preflight = `SqliteAdapter::has_index`（C++，legacy-compat 存在性探针，非 tenant-isolation 证明）。`PreflightResult` 复用既有 `include/starling/preflight.hpp`；supervisor 暴露薄 `PreflightReport{passed, missing_capabilities, warnings}` 视图（映射既有 `PreflightResult`，非平行核心类型）。生产探针走 C++ `has_index`（supervisor 取 `SqliteAdapter&` 构造），`std::function<bool()>` 构造仅作 C++ 单测缝。绑定为 flat `_core.RuntimeSupervisor`（`bindings/python/bind_14_governance.cpp`）。Python `runtime.py` 收为薄 forwarder：只构造 supervisor、转发 `runtime.health_changed` 宿主通知、暴露 facade 外壳（无能力清单/preflight 算法/裸 `sqlite_master` 读/可变治理全局）。**仅 Phase 1**：DEGRADED/DRAINING 完整四态机 + 事件日志 + `events()` 为 Phase 2；PipelineRun 账本/ScopedWorkGate/RestartGuard/背压为 Phase 3-5；trace retention 分级与 PipelineStepContract 通用校验顺延。下方接口契约为完整目标态(c1 全程)，非 Phase 1 现状。

**健康降级**

1. 健康守护进程持续采样：`outbox_lag_sequence`、`subscriber_failure_rate`、`extraction_queue_depth`、`projection_lag_seconds`、`runtime_event_loop_lag_ms`、`vector_delete_lag`、`erased_evidence_visible_count`。
2. 任一指标超阈值但主表仍可用 → `READY → DEGRADED`：前台写入继续，高成本副作用延后；Replay / Projection 非关键批处理暂停；Compliance erase / Commitment fire 仍正常运行。
3. 主表不可用、outbox 不可提交、tenant isolation 缺失 → `DEGRADED → UNREADY`，fail-closed。
4. `RestartGuard` 双阈值（滑动窗口重启次数 + 连续无成功处理次数）任一超限 → 暂停该 worker lane，emit `runtime.health_changed(DEGRADED)`。

**DRAINING 流程**

1. 进程关闭 / 迁移 / profile 切换 / 管理员 drain → 进入 `DRAINING`。
2. worker 停止 claim 新任务，flush inbox / checkpoint，等待持有 lease 内的任务完成。
3. 前台读仍可服务；写入按策略返回 `retry_after`；新后台 run 一律拒绝。
4. 所有 lease 释放后进程安全退出。

**PipelineRun 生命周期**

1. 请求到达：检查是否已存在同 `(kind, aggregate_id, input_hash)` 的 active run；若有，返回已有 `run_id`，不重复入队。
2. `QUEUED → RUNNING`：worker `claim(run_id, worker_id, lease_until)`，写入 lease 时间戳。
3. 执行中：按阶段边界写 `checkpoint_sequence / watermark`；stage_timings_ms 逐阶段记录。
4. lease 到期但任务未 confirm：其他 worker 可 `reclaim`，按 `idempotency_key` + checkpoint 跳过已完成部分，续跑。
5. 成功：`confirm(run_id, checkpoint)` → `COMPLETED`；部分失败 → `PARTIAL_SUCCESS` 或 `DEGRADED_COMPLETED`。
6. cooperative cancel：worker 在阶段边界检查 cancel flag，写 `CANCELLED` 并释放 lease。
7. 失败：指数退避重试；超阈值 → `DEAD_LETTERED`；若属于 Compliance lane，必须告警并维持 `RuntimeHealth=DEGRADED/UNREADY`，不得静默跳过。

**ScopedWorkGate 并发控制**

1. 每个后台任务以 `(tenant_id, holder_scope, aggregate_id, lane)` 为 gate_key 申请 slot。
2. 同一 task / run 对同一 gate_key 可重入，递增 depth；跨 aggregate 消耗新 slot。
3. critical lane（Compliance erase、outbox delivery、commitment due）使用独立 quota，不被 soft work 占满。
4. soft lane 满时可丢弃可重建任务，但必须递增 `dropped_soft_work_count` 并保留从 outbox / watermark 重建的依据；不得丢弃 outbox、Compliance erase、Commitment fire、ExtractionAttempt 终态。
5. task 结束必须释放全部 depth；守护进程定期扫描 leaked leases / gates，超时释放并 emit `runtime.health_changed(DEGRADED)`。

## 数据模型

```python
class PipelineRun(BaseEntity):
    id: UUID
    kind: Literal["extraction","replay","projection_rebuild","container_rebuild",
                  "compliance_erase","retrieval_eval","migration"]
    aggregate_id: str
    business_task_id: Optional[str]       # 业务可见任务 id，可聚合多个 item run
    parent_run_id: Optional[UUID]
    item_run_ids: list[UUID]
    profile_name: str
    input_hash: str
    idempotency_key: str
    pipeline_name: str
    pipeline_version: str                 # P1 简单版本号；P3 升级为 revision token
    metadata_json: dict = {}              # 调用方 run metadata；受 trace_retention 约束
    step_contracts: list[dict] = []       # P3 启用；P1 不启用通用 step graph
    status: Literal["QUEUED","RUNNING","PAUSED","COMPLETED","PARTIAL_SUCCESS",
                    "DEGRADED_COMPLETED","FAILED","CANCELLED","DEAD_LETTERED"]
    checkpoint_sequence: Optional[int]
    watermark: dict                       # last_outbox_sequence / last_sqlite_id / last_engram_cursor
    progress: dict                        # total / done / skipped / retried
    counters: dict                        # accepted / rejected / noop / conflicts / erased
    warnings: list[dict]                  # non_fatal / skip_downstream 降级原因，可审计
    stage_timings_ms: list[dict]          # 层级阶段计时
    error_kind: Optional[str]
    retry_count: int
    lease_until: Optional[datetime]
    started_at: datetime
    updated_at: datetime
```

```python
class PipelineStepContract(BaseModel):
    step_id: str
    requires: set[str]
    produces: set[str]
    capabilities: set[str]
    config_hash: str
    failure_policy: Literal["critical","non_fatal","skip_downstream"] = "critical"
```

**RuntimeHealth 状态机**

| 状态 | 进入条件 | 前台读写 | 后台任务 |
|---|---|---|---|
| `READY` | 所有硬能力 preflight 通过，lag/queue 在 SLA 内 | 正常 | 正常 |
| `DEGRADED` | outbox lag、projection lag、extraction queue depth、event loop lag、subscriber failure rate 任一超阈值但主表可用 | 写入继续，高成本副作用延后；检索可降级主表或跳过 rerank | 暂停 Replay / Projection 非关键批处理，保留 Compliance / Commitment |
| `DRAINING` | 进程关闭、迁移、profile 切换或管理员 drain | 拒绝新后台 run；前台读可继续；写入返回 retry_after | worker 停止 claim，等待 lease 内任务完成 |
| `UNREADY` | capability preflight 失败、主表不可用、outbox 不可提交、tenant isolation 缺失 | fail-closed | 不启动 |

**Trace retention 分级**

| `trace_retention` | 内容 | 默认场景 |
|---|---|---|
| `metadata_only` | step 名、耗时、状态、hash、计数，不保存 prompt/response 正文 | production 默认 |
| `hash_only` | 只保留 input/output hash 与错误分类 | sensitive / regulated |
| `redacted_debug` | 保存脱敏后的 prompt/response，有 TTL | staging / debug |
| `full_debug` | 保存完整 prompt/response，有短 TTL、访问审计，禁止 sensitive profile 默认启用 | 本地排障 |

## 接口契约

**RuntimeHealth**

```python
class RuntimeHealthEvent(DomainEvent):
    event_type: Literal["runtime.health_changed"]
    previous_status: Literal["READY","DEGRADED","DRAINING","UNREADY"]
    current_status: Literal["READY","DEGRADED","DRAINING","UNREADY"]
    trigger: str                          # 触发条件描述
    metrics_snapshot: dict                # 触发时的指标快照

class PreflightResult(BaseModel):
    passed: bool
    missing_capabilities: list[str]
    warnings: list[str]
```

**PipelineRun 操作**

```python
# claim 任务
def claim(run_id: UUID, worker_id: str, lease_until: datetime) -> PipelineRun: ...

# confirm 完成，写入 checkpoint
def confirm(run_id: UUID, checkpoint: dict) -> PipelineRun: ...

# reclaim 超时任务
def reclaim(run_id: UUID, worker_id: str, lease_until: datetime) -> PipelineRun: ...

# 查询同 (kind, aggregate_id, input_hash) 是否有 active run
def find_active_run(kind: str, aggregate_id: str, input_hash: str) -> Optional[PipelineRun]: ...
```

**ScopedWorkGate**

```python
gate_key = (tenant_id, holder_scope, aggregate_id, lane)
# lane: "critical" | "soft"

# 申请 slot（可重入同一 gate_key）
def acquire(gate_key: tuple, task_id: str) -> int: ...   # 返回当前 depth

# 释放 slot
def release(gate_key: tuple, task_id: str) -> None: ...

# 守护进程定期调用，释放超时 lease / gate
def sweep_leaked(now: datetime) -> list[str]: ...        # 返回被强制释放的 run_id 列表
```

**前台降级响应字段**

```python
class BusWriteResponse(BaseModel):
    run_id: Optional[UUID]
    runtime_degraded: bool = False
    projection_stale: bool = False
    retry_after: Optional[int] = None     # 秒；DRAINING 时返回
```

## 不变式与边界

1. 同一 `(kind, aggregate_id, input_hash)` 不得有两个 active run（QUEUED 或 RUNNING）同时存在。
2. Compliance erase、outbox delivery、commitment fire 的 `failure_policy` 固定为 `critical`，不得被覆盖为 `non_fatal` 或 `skip_downstream`。
3. Projection rebuild 完成前不替换 active projection，必须使用 shadow table + atomic swap。
4. `DEAD_LETTERED` 的 Compliance lane run 必须触发告警并将 RuntimeHealth 维持在 `DEGRADED` 或 `UNREADY`，不得静默。
5. soft lane 满时丢弃任务必须保留从 outbox / watermark 重建的依据，`dropped_soft_work_count` 必须递增。
6. full / redacted_debug trace 不得作为普通 EngramStore evidence 持久化；合规擦除触发时，trace 中对应 raw payload 必须同步 redaction 或 crypto erasure。
7. `business_task_id` 聚合的多 item run：至少一个成功、至少一个失败 → `PARTIAL_SUCCESS`；全部 NOOP → `NOOP`，不得报 `SUCCESS`。
8. Pipeline mutation 只能产生新 revision，不得原地改写旧 revision；`step_contracts` 验证上游 produces 必须覆盖下游 requires，profile capability 必须覆盖 step capabilities，不满足则拒绝 run start。


## 来源话轮实现核对（2026-09-12）

版本化来源话轮由 C++ 生成与解析，直接证据回读共用严格验证。该子系统继续消费已有证据与时间契约，不新增语言 binding 中的语义逻辑。来源观察时间不作为绝对事件时间；本轮核对与诊断统一见 [设计同步清单](../claim_contract_sync.md) 和 [来源话轮评测报告](../../eval/2026-09-12-socialmem-source-turn.md)。


## 生成契约完整性同步（2026-09-12）

按 [中文生成契约设计](../../superpowers/specs/2026-09-12-claim-generation-design.md)，C++ 在抽取提示中明确对象、逐字主题、原始时间限定和字段类型约束，并提供与本次来源隔离的通用中英文参考示例。模型输出校验、准入、存储/检索与默认开关保持既有约束，Python 仅绑定和评测编排；参考示例不作为当前证据。本轮 C++ 实现、完整回归、离线核验及历史响应 140/140 一致性重放已完成；真实诊断于北京时间 2026-09-13 完成核验，为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、独立对象 12/14、主题/联合各 1/14，原生技术失败 5；主题字面匹配分数不能解释为字段缺失。P1 兼容与逐例不退步门槛仍失败，Q1/Q9 结构化及链接组仍为 0/3，默认关闭。详见 [生成契约评测报告](../../eval/2026-09-12-socialmem-generation.md)。其他专项职责沿用设计同步清单，历史快照保持。

## 输出协议与偏好边界同步（2026-09-13）

按 [中文修复设计](../../superpowers/specs/2026-09-13-claim-protocol-boundary-design.md) 继续已批准优化：C++ 提示强调键唯一、时间原文及同话轮引用，准入与解析共用合法原因目录，窄范围拒绝把明确偏好对象写成 feels。真情绪不因同源其他偏好句被拒；Bus/回读复用共享契约，Python 仅绑定与编排。当前已完成 RED、C++ 实现与复审修复后的完整回归（C++ 1,062 项，Python 1,319 项通过/15 项跳过）；旧响应重解析 137/140 一致，3 条偏好误标候选提前拒绝。复合/因果情绪及被动 preferred 感受保留准入，句尾标点边界有正反例覆盖。独立复审发现均已关闭，最终离线 140 条/144 数据库核验通过；真实诊断已完成并由原生验证器核验为 `verified / complete_with_errors`：140 条重放、144 个数据库；固定候选 56/64（TP 30、TN 26、误收 0、误拒 1、技术失败 7），synthetic 冻结 11/16、契约 11/16（有效分母 15/16），P1 combined F1 为 holder 0.7317、holder/perspective 0.6829、predicate/object 0.7683；扩展标签 object/topic/scope/time/joint 为 12/14、2/14、12/14、12/14、2/14（有效目标 13）；Q1/Q9 的 baseline、structured、linked 均为 0/3，full 均为 3/3；实际证据链仍受入库与证据聚合限制。原生技术失败共 10 条，主要为重复 JSON 键和准入 JSON 后追加文本；无效裁判票 0。`promotion_ready=false`，生产默认保持关闭，不运行 1,031 题全量。默认、原标签、检索与历史归档保持。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
