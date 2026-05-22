# Prospective Loop

## 功能定义

Prospective Loop 实现"前瞻"，在没有用户 query 的情况下主动想起承诺、触发提醒、检测履行或违约。它承担四项职责：（1）Trigger 类型系统；（2）Commitment 五态机；（3）ActionGuard 动作护栏；（4）Norm 监听。所有 Trigger 命中均经 [Statement Bus](v23_05_bus.md) emit `commitment.fire`，PolicyEngine 不绕过 Bus 直接调用消费者。

## 输入

- modality=COMMITS 的 Statement 写入（Validator 通过后转 ACTIVE）
- Trigger 注册请求（TimeTrigger / EventTrigger / StateTrigger / CompoundTrigger）
- Bus 事件流（用于 EventTrigger / StateTrigger 评估，含 statement.written / cognizer.observed）
- Commitment 履行检测信号（来自 Retrieval 或外部反馈）
- ActionGuard 配置（allowed_actions / requires_approval / idempotency_window）

## 输出

- commitment.fire（Trigger 命中，注入 Working Set pending_commitments）
- commitment.active_holding / commitment.released（保护事件，对接 Replay decay scheduler）
- commitment.fulfilled / broken / renegotiated / withdrawn（状态迁移事件）
- commitment.auto_withdrawn（BROKEN 累计 ≥ 3 次时）
- action.policy_blocked（ActionGuard 拒绝时）

## PolicyEngine 子模块

PolicyEngine 是 Prospective Loop 的内部触发器引擎，负责 Trigger Index 维护、命中判定、Bus 事件发布。它不是独立子系统，是 Prospective Loop 的核心组件，本节单列以便引用。

### 职责

1. **Trigger Index 维护**：所有 ACTIVE Commitment 注册的 Trigger 进入索引（哈希表 + 时间堆）；状态终态时清理索引项。
2. **命中判定**：根据 Trigger 类型选择评估策略：
   - `TimeTrigger`：基于时间堆轮询，到点 emit
   - `EventTrigger`：订阅 Bus 事件流，匹配 event_type + filter 谓词
   - `StateTrigger`：每次 Bus 事件落库后扫描，检查 Statement 字段谓词
   - `CompoundTrigger`：递归深度优先评估子节点，短路求值（all_of 遇首个未命中即停止）
3. **事件发布**：命中条件满足时调用 `Bus.emit("commitment.fire", ...)`；状态迁移（ACTIVE / FULFILLED / BROKEN / RENEGOTIATED / WITHDRAWN）时 emit 对应 commitment.* 事件。所有外发事件经 Bus，不绕过。
4. **Bus 订阅**：订阅 `commitment.fulfilled` / `commitment.broken` / `commitment.renegotiated` / `commitment.withdrawn`，用于 Trigger 清理与 trust_priors 调整。

### 输入

- Bus 事件流（订阅 commitment.* 与 statement.written 用于 EventTrigger / StateTrigger 评估）
- TimeTrigger 时间堆（来自 Commitment 注册）
- 系统时钟（用于 TimeTrigger 触发判定）

### 输出

- `commitment.fire`（经 Bus.emit）
- `commitment.active_holding`（转 ACTIVE 时）
- `commitment.released`（转 FULFILLED / WITHDRAWN 时）
- `commitment.broken`（deadline 过期未履行时）
- `commitment.auto_withdrawn`（BROKEN 累计 ≥ 3 次自动撤回时）
- `action.policy_blocked`（ActionGuard 拒绝时，P3 高阶）

### 数据结构

```python
class PolicyEngine:
    trigger_index: dict[CommitmentId, list[Trigger]]  # 哈希表
    time_heap: list[tuple[datetime, CommitmentId, TriggerId]]  # min-heap
    event_subscriptions: dict[BusEventType, list[Trigger]]
    state_predicates: list[StatePredicate]

class StatePredicate:
    target: Literal["statement", "container", "cognizer"]
    field: str
    op: Literal["eq", "ne", "gt", "lt", "in"]
    value: Any
```

### 与 Bus 的关系

PolicyEngine 是 [Statement Bus](v23_05_bus.md) 的 publisher 与 subscriber：
- Publisher：所有 commitment.* 事件
- Subscriber：commitment 终态事件用于内部清理；statement.written / cognizer.observed 用于 StateTrigger / EventTrigger 评估

满足"所有读写必经 Bus"硬约束。

## 主要流程

### 1. Commitment 创建

`modality=COMMITS` 的 Statement 经 Validator 通过后，Bus 自动将其状态由 `created` 转为 `ACTIVE`。转 ACTIVE 时 PolicyEngine emit `commitment.active_holding(commitment_id, related_stmt_ids)`，通知 [Replay Scheduler](v23_10_replay.md) decay scheduler 将关联 stmt_id 加入 in-memory 保护集，阻止相关 Statement 被 ARCHIVED。

### 2. Trigger 命中

PolicyEngine 内部维护 Trigger Index 与时间堆，持续监听四类 Trigger。命中条件满足时经 `Bus.emit("commitment.fire", ...)` 发布事件；Working Set 随即注入 `pending_commitments` block，作为对话上下文的提醒插槽。

### 3. ACTIVE 保护

`commitment.active_holding` 的 Consumer 是 Replay decay scheduler。scheduler 在 in-memory set 中持有被保护的 stmt_id 集合，decay 选取候选时 O(1) 排除集合内 Statement，执行 §3.4 例外条款"未结清 Commitment 不允许相关 Statement 进入 ARCHIVED"。

### 4. 终态释放

Commitment 转 `FULFILLED` 或 `WITHDRAWN` 时，emit `commitment.released(commitment_id)`，decay scheduler 从保护集移除对应 stmt_id，解除 ARCHIVED 约束。

### 5. RENEGOTIATED 链长限制

supersedes 链长 `>= 3` 时，Validator 拒绝新的 RENEGOTIATED 请求，emit `commitment.renegotiation_blocked`，要求调用方先执行 WITHDRAWN 再重新 COMMIT。这使 supersedes 链 O(N) 展开成本（ToM 推断、衰减公式）保持可控，上限 3 次协商已覆盖绝大多数现实场景。

### 6. BROKEN 计数自动 WITHDRAWN

同一 `commitment_id` 累计进入 BROKEN 状态 `>= MAX_BROKEN_COUNT`（默认 3）次后，下一次 deadline 过期不再转 BROKEN，而是自动转 WITHDRAWN，emit `commitment.auto_withdrawn(reason="chronic_failure")`。同步触发 [Cognizer Hub](v23_08_cognizer.md) 中对应 holder 的 `trust_priors` 下调（具体公式见 §8.3）。设计意图：防止单一 commitment_id 长期占用 supersedes 链与 Replay 资源，语义上反映"反复失信后系统不再跟踪"。

### 7. dispatcher 重启 boot replay

dispatcher 重启时必须重放最近 7 天内的 `commitment.active_holding` 和 `commitment.released` 事件，重建 in-memory 保护集。若跳过此步骤，未结清 Commitment 关联的 Statement 可能被误 ARCHIVED（critical failure mode，见测试 TC-A9-003）。

## 核心算法

### 1. Commitment 五态机完整迁移表

```
created
  └─ Validator 通过 → ACTIVE  (emit commitment.active_holding)

ACTIVE
  ├─ user 履行          → FULFILLED       (emit commitment.fulfilled)
  │                                        (emit commitment.released)
  ├─ deadline 过期       → BROKEN         (emit commitment.broken)
  │   └─ 累计 >= MAX_BROKEN_COUNT 次后
  │      下次 deadline → WITHDRAWN        (emit commitment.auto_withdrawn)
  ├─ 双方协商           → RENEGOTIATED    (emit commitment.renegotiated)
  │   └─ 新版 supersedes 旧；链长 >= 3 时 Validator 拒绝
  └─ 主动撤回           → WITHDRAWN       (emit commitment.withdrawn)
                                           (emit commitment.released)

BROKEN
  └─ 双方协商           → RENEGOTIATED    (emit commitment.renegotiated)
     (旧 BROKEN 保留，新 RENEGOTIATED 经 supersedes 链关联)

FULFILLED / WITHDRAWN  →  终态，不可再迁移
```

状态迁移规则：

| 迁移 | 触发条件 | 副作用 | emit 事件 |
|---|---|---|---|
| created → ACTIVE | Validator 通过 | PolicyEngine 注册 Trigger Index | `commitment.active_holding` |
| ACTIVE → FULFILLED | user 履行确认 | 清理 Trigger；Working Set 移除 block | `commitment.fulfilled`、`commitment.released` |
| ACTIVE → BROKEN | deadline 过期（未满 MAX_BROKEN_COUNT） | BROKEN 计数 +1 | `commitment.broken` |
| ACTIVE → BROKEN → auto-WITHDRAWN | deadline 过期且 BROKEN 计数 >= MAX_BROKEN_COUNT | trust_priors 下调 | `commitment.auto_withdrawn` |
| ACTIVE / BROKEN → RENEGOTIATED | 双方协商，链长 < 3 | 旧版打 supersedes；新版转 ACTIVE | `commitment.renegotiated` |
| ACTIVE / RENEGOTIATED → WITHDRAWN | 主动撤回 | 清理 Trigger；Working Set 移除 block | `commitment.withdrawn`、`commitment.released` |

### 2. RENEGOTIATED 链长上限算法

```python
def validate_renegotiation(commitment_id: str, store) -> bool:
    chain_len = store.supersedes_chain_length(commitment_id)
    if chain_len >= 3:
        bus.emit("commitment.renegotiation_blocked", {"commitment_id": commitment_id})
        return False
    return True
```

调用方需先执行 WITHDRAWN，再新建 Commitment，绕过链长限制重新开始计数。

### 3. BROKEN 计数累计与自动 WITHDRAWN 判定

```python
MAX_BROKEN_COUNT = 3

def on_deadline_expired(commitment_id: str, store, bus):
    broken_count = store.broken_count(commitment_id)
    if broken_count >= MAX_BROKEN_COUNT:
        store.transition(commitment_id, "WITHDRAWN")
        bus.emit("commitment.auto_withdrawn", {
            "commitment_id": commitment_id,
            "reason": "chronic_failure",
        })
        cognizer_hub.downgrade_trust_priors(store.holder(commitment_id))
    else:
        store.transition(commitment_id, "BROKEN")
        store.increment_broken_count(commitment_id)
        bus.emit("commitment.broken", {"commitment_id": commitment_id})
```

### 4. 四类 Trigger 命中判定

| Trigger 类型 | 命中条件 |
|---|---|
| `TimeTrigger(at=datetime)` | 系统时钟到达指定时刻 |
| `TimeTrigger(every="1d at 09:00")` | 每日循环，Trigger Index 时间堆轮询 |
| `EventTrigger(when=...)` | Bus 事件流中出现匹配事件（如 `cognizer:Alice.observed`、`statement.written: predicate=mentions, object=X`） |
| `StateTrigger(predicate=...)` | EngramStore 中指定谓词当前为真（如 `goal:onboarding.completed`） |
| `CompoundTrigger(all_of=[...])` | 子 Trigger 全部命中（AND 组合） |
| `CompoundTrigger(any_of=[...])` | 子 Trigger 任一命中（OR 组合） |

CompoundTrigger 递归嵌套，PolicyEngine 按深度优先顺序评估子节点，短路求值（all_of 遇到第一个未命中即停止）。

### 5. ActionGuard 三件套

P3 默认 ActionGuard：

```python
class ActionGuard(BaseModel):
    profile_name: str
    allowed_actions: set[str]       # 允许直接执行的动作名称集合
    requires_approval: set[str]     # 需要人工审批才能执行的动作名称集合
    idempotency_window: dict[str, timedelta]  # 每个动作的幂等窗口
```

执行规则：

- `commitment.fire` 默认仅将 pending reminder 注入 Working Set，不调用外部 tool。
- 调用外部 tool/action 须满足 `action_name in allowed_actions`。
- 命中 `requires_approval` 的动作进入 human approval 队列，不得由 LLM 自行确认。
- 每个外部动作须携带 `business_idempotency_key`，窗口规则沿用 [Statement Bus](v23_05_bus.md) §5.4。
- Guard 失败默认 fail-closed，emit `action.policy_blocked`，并在 `PipelineRun.warnings/counters` 中可见。

## 数据结构

### Commitment 五态枚举

```python
class CommitmentState(str, Enum):
    created      = "created"
    ACTIVE       = "ACTIVE"
    FULFILLED    = "FULFILLED"
    BROKEN       = "BROKEN"
    RENEGOTIATED = "RENEGOTIATED"
    WITHDRAWN    = "WITHDRAWN"
```

### 四类 Trigger

```python
class Trigger(BaseModel):
    kind: Literal["time", "event", "state", "compound"]
    spec: TriggerSpec

# 具体类型
TimeTrigger(at=datetime(...))
TimeTrigger(every="1d at 09:00")
EventTrigger(when="cognizer:Alice.observed")
EventTrigger(when="statement.written: predicate=mentions, object=X")
StateTrigger(predicate="goal:onboarding.completed")
CompoundTrigger(all_of=[...])   # AND
CompoundTrigger(any_of=[...])   # OR
```

### ActionGuard（P3 默认）

```python
class ActionGuard(BaseModel):
    profile_name: str
    allowed_actions: set[str]
    requires_approval: set[str]
    idempotency_window: dict[str, timedelta]
```

### Bus 事件 schema

| 事件 | 字段 | 说明 |
|---|---|---|
| `commitment.active_holding` | `commitment_id`, `related_stmt_ids: list[str]` | 转 ACTIVE 时 emit，保护关联 Statement |
| `commitment.released` | `commitment_id` | 转 FULFILLED 或 WITHDRAWN 时 emit，解除保护 |
| `commitment.fire` | `commitment_id`, `trigger_kind`, `triggered_at` | Trigger 命中时 emit |
| `commitment.fulfilled` | `commitment_id` | 用户履行时 emit |
| `commitment.broken` | `commitment_id`, `broken_count` | deadline 过期未达上限时 emit |
| `commitment.auto_withdrawn` | `commitment_id`, `reason` | 慢性失信自动 WITHDRAWN |
| `commitment.renegotiated` | `commitment_id`, `supersedes` | 协商成功时 emit |
| `commitment.withdrawn` | `commitment_id` | 主动撤回时 emit |
| `commitment.renegotiation_blocked` | `commitment_id`, `chain_len` | 链长超限时 emit |
| `action.policy_blocked` | `action_name`, `commitment_id` | ActionGuard 拒绝时 emit |

### Norm 与 Commitment 的关系

Norm 是 Group 内的默认行为规则；违反时 emit `norm.violated`，作为高 salience EpisodicEvent 进入 Affect Buffer。Commitment 是个体对个体的具体承诺。两者通过 `induce_norm` 操作（§10.3）连接：多次相似 Commitment 模式可凝结为 Norm 候选，由 Cognizer Hub 写入群组级 Norm 表。

### ActionPolicyGraph（P3 高阶完整版）

```python
class ActionPolicyRule(BaseModel):
    kind: Literal[
        "init",                 # 动作链入口
        "parent_child",         # 父动作允许子动作
        "conditional",          # 条件分支
        "max_count",            # 限制单次执行次数（防重复投递）
        "terminal",             # 结束当前 Prospective run
        "required_before_exit", # 前后置保证（如"发送提醒后必须记录 delivery receipt"）
        "requires_approval",    # 人工审批才能执行
    ]
    action_name: str
    target_actions: list[str] = []
    condition: Optional[str]
    max_count: Optional[int]
    prefilled_args: dict = {}

class ActionPolicyGraph(BaseModel):
    profile_name: str
    rules: list[ActionPolicyRule]
    audit_mode: Literal["enforce", "dry_run", "disabled"] = "enforce"
```

`max_count` 与 [Statement Bus](v23_05_bus.md) §5.4 `business_idempotency_window` 互补：前者限制单次 action graph 内执行次数，后者限制 at-least-once 事件重复。`terminal` 动作结束该 Prospective run，后续动作须新建 `causation_chain`。

上述 Python 示例为绑定层接口契约。核心实现为 C++ 抽象类，Python/JS/Rust 等绑定通过 pybind11 / NAPI / cxx 自动生成存根。

## 相关概念

**Trigger 类型系统**
PolicyEngine 内部维护 Trigger Index（哈希表）和时间堆（min-heap），TimeTrigger 基于堆轮询，EventTrigger 订阅 Bus 事件流，StateTrigger 在每次 Bus 事件落库后检查谓词，CompoundTrigger 递归组合。

**Commitment 五态机**
`created → ACTIVE → {FULFILLED / BROKEN / RENEGOTIATED / WITHDRAWN}`，所有终态都须经 Bus outbox 发布事件。BROKEN 不是终态，允许 `BROKEN → RENEGOTIATED` 迁移（对应现实"后来又答应了"场景）。

**ACTIVE 保护事件 commitment.active_holding**
设计意图：Replay decay scheduler 需要排除"未结清 Commitment 的关联 Statement"，若每次 decay 选取候选时查询 Commitment 表，代价为 O(N×M)（N 条 Statement × M 个活跃 Commitment）。改用 in-memory set + Bus 事件维护，命中检查降为 O(1)，且 set 状态通过 boot replay 保证持久化语义。

**ActionGuard**
最小动作护栏，三字段控制"哪些动作可执行、哪些需审批、幂等窗口多长"。P3 默认仅 ActionGuard；P3+ 升级为 ActionPolicyGraph，支持多步前后置、条件分支与复杂工具链。

**ActionPolicyGraph（P3 高阶）**
完整动作策略图，8 种规则类型覆盖 init / parent_child / conditional / max_count / terminal / required_before_exit / requires_approval。`audit_mode` 支持 enforce / dry_run / disabled 三挡。

**PolicyEngine 与 Bus 关系**
PolicyEngine 是 [Statement Bus](v23_05_bus.md) 的 publisher 之一，同时也是 Bus 订阅者（订阅 commitment.fulfilled / broken / renegotiated / withdrawn 用于 Trigger 清理和 trust_priors 调整）。所有外发事件经 `Bus.emit`，所有内入事件来自 Bus，满足 §5"所有读写必经 Bus"硬约束。

**Norm 与 Commitment 的关系**
Norm 作用于 Group 级默认规则，Commitment 作用于个体间具体约定。`induce_norm` 操作将高频 Commitment 模式提炼为 Norm 候选；Norm 违反产生的 `norm.violated` 事件与 Commitment 的 `commitment.broken` 事件在 Affect Buffer 均作为高 salience EpisodicEvent 处理，但归属层次不同。

**引用**
- 事件总线契约：[Statement Bus](v23_05_bus.md)
- trust_priors 下调公式：[Cognizer Hub](v23_08_cognizer.md) §8.3
- decay scheduler 例外条款：[Replay Scheduler](v23_10_replay.md) §3.4
- ToM 推断 supersedes 链展开：[ToM Engine](v23_09_tom.md) §9.2
- 配置：所有 Adapter 与运行时配置采用 JSON 格式，统一 schema 见主文档 §2.0
