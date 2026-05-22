# Runtime Governance

## 功能定义

Runtime Governance 不是业务子系统，是运行时的健康监控、背压控制与长任务账本。它管辖：READY / DEGRADED / DRAINING / UNREADY 四态转换、PipelineRun 长任务追踪与断点恢复、ScopedWorkGate 分域并发限流、critical lane 优先级保护与 trace retention 分级。它不管：Statement 内容、检索质量、抽取准确率，以及任何业务语义。

## 主要流程

**启动 preflight**

1. 读取 `ProfileCapability`，逐项校验硬能力（主表可用、outbox 可提交、tenant isolation 存在、向量存储就绪）。
2. 任一硬能力缺失 → 直接进入 `UNREADY`，fail-closed，前台与后台均不启动。
3. 全部通过 → 进入 `READY`，后台 worker 开始 claim 任务。

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
    pipeline_version: str                 # P0 简单版本号；P2+ 升级为 revision token
    step_contracts: list[dict] = []       # P2+ 启用；P0/P1 不启用通用 step graph
    status: Literal["QUEUED","RUNNING","PAUSED","COMPLETED","PARTIAL_SUCCESS",
                    "DEGRADED_COMPLETED","FAILED","CANCELLED","DEAD_LETTERED"]
    checkpoint_sequence: Optional[int]
    watermark: dict                       # last_outbox_sequence / last_sqlite_id / last_drawer_cursor
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
