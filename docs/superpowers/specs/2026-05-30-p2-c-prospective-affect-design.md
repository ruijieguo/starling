# P2.c 前瞻与情感 — 设计规格

## 0. 背景与范围

roadmap 把 P2 分为 P2.a(社会心智 Schema,已交付)、P2.b(类脑动力学,已交付 = M0.8 无向量核心 + M0.9 向量基础层)、P2.c(前瞻与情感)。本 spec 是 **P2.c**,P2 的第三个也是最后一个子阶段。前序 P2.b 已全部合并 main(M0.8 merge `4e70c82`,M0.9 merge `d47fcae`)。

P2.c 出货项(roadmap / system_design.md §1673):Commitment 五态机 + 4 类 Trigger(time/event/state/compound)、Prospective Loop 调度器(PolicyEngine)、AffectVector 五维 + salience 公式、优先级重放权重、ActionGuard 最小子集。

### Brainstorming 锁定的 3 个决策

1. **范围**:**单一里程碑**(整个 P2.c 一个 spec/plan/execute 周期)。P2.c 无 P2.b 式的硬基础设施缺口——所有底座(Bus/SubscriberPump、ReplayScheduler decay、proj_commitment_due、AffectVector 公式、swr_sampler arousal 槽)均已存在,只需在其上接 commitment/affect/action 逻辑。
2. **PolicyEngine 结构**:**stateless-per-tick,SQL-backed**(对齐 ReplayScheduler/EmbeddingWorker/ProjectionMaintainer 的既有模式)。保护集不用 in-memory set,改 SQL EXISTS(受保护 stmt ∩ `commitments.state='ACTIVE'`);SQLite 持久性满足 boot-replay 意图(TC-A9-003 = 重启后保护仍生效),无需显式 boot-replay 机制。设计文档的 in-memory trigger_index/time_heap/boot-replay 在此重构为 SQL-backed。
3. **验收标准**:**tests-only gate**——5 个 §16.3-8 CRITICAL(TC-A2-001/002 + TC-A9-001/002/003)+ 全面确定性 unit/integration。无 live-LLM eval 门。roadmap 的"100 条承诺履行集 detection>80%/timeliness<3turns"后置/单独追踪。

### §16.3 准入对照

P2.c 覆盖 **§16.3-8 commitment 契约**(5 个 CRITICAL)。§16.3-3/-4/-6/-7/-9 已由 P2.a/P2.b 覆盖;§16.3-10(评测体系)P2.c 不动。

---

## 1. 目标与非目标

### 目标
- Commitment 五态机(created→ACTIVE→{FULFILLED/BROKEN/RENEGOTIATED/WITHDRAWN})+ broken_count auto-WITHDRAWN + renegotiation 链长守护。
- PolicyEngine:4 类 Trigger 评估 + commitment.* 状态迁移 + commitment.fire 发布(stateless SQL-backed,post-write subscriber + time-driven tick 双入口)。
- active_holding 反向保护:未结清 Commitment 关联 stmt 不被 decay ARCHIVED(SQL EXISTS,重启 durable)。
- AffectVector 五维 + salience C++ 移植,采样时驱动优先级重放权重(写路径零改动)。
- ActionGuard 最小子集:护栏结构 + fail-closed check + action.policy_blocked。
- 无向量层 / 写路径 / M0.8 6 类 SQL 投影 regression。

### 非目标(本期明确不做,留后续/P3)
- ActionPolicyGraph 8 规则完整图、外部 tool 执行 / action dispatch、idempotency 执行追踪 → P3。
- Working Set `pending_commitments` 渲染注入 → Hippocampus/P3(P2.c 只 emit `commitment.fire`)。
- `induce_norm`(Commitment→Norm 凝结)→ 后续。
- AffectVector 写时计算 / Affect Buffer 入队 → P3(P2.c 采样时算)。
- 100 条承诺履行 detection eval → 后置(tests-only gate)。

---

## 2. 架构总览

```
写路径(不变)
  Bus.write commit modality=COMMITS statement + outbox 事件        ← 零改动

PolicyEngine 入口 1:post-write subscriber(SubscriberPump 第 6 个)
  consume statement.written:
    modality=COMMITS → INSERT commitments(ACTIVE) + 注册 Trigger + emit active_holding + 写 commitment_protection
    评估 EventTrigger / StateTrigger → emit commitment.fire
  consume commitment.*:状态迁移 + Trigger 清理 + (auto_withdrawn → trust_priors)

PolicyEngine 入口 2:time-driven tick(runtime 驱动,类比 ReplayScheduler.run_idle)
  tick(now):
    到期 TimeTrigger(commitment_triggers/proj_commitment_due, state=ACTIVE)→ emit commitment.fire
    deadline 过期 → BROKEN / (broken_count≥3) auto-WITHDRAWN

Replay decay(consolidation_ops.op_decay)
  active_grounded = SQL EXISTS(commitment_protection ∩ commitments.state='ACTIVE')  ← 保护

Replay 采样(swr_sampler.sample_weight)
  affect_json → AffectVector → salience + arousal → 喂 sample_weight                ← 优先级
```

| 组件 | 职责 | 层 |
|---|---|---|
| `CommitmentEngine` | 五态机迁移 + broken_count + 链长守护 | C++ core |
| `PolicyEngine` | Trigger 评估 + commitment.* 处理 + fire 发布(post-write + tick)| C++ core |
| `AffectVector` | 五维 + salience()(移植 affect.py)+ 采样时喂权重 | C++ core |
| `ActionGuard` | 最小护栏 check(fail-closed)| C++ core |

---

## 3. 组件设计

### 3.1 CommitmentEngine

```cpp
// include/starling/prospective/commitment_engine.hpp
namespace starling::prospective {

enum class CommitmentState { created, ACTIVE, FULFILLED, BROKEN, RENEGOTIATED, WITHDRAWN };

class CommitmentEngine {
public:
    explicit CommitmentEngine(persistence::SqliteAdapter&);
    // 从 modality=COMMITS statement 建 ACTIVE commitment + emit active_holding。
    void create_from_statement(persistence::Connection&, std::string_view stmt_id,
                               std::string_view tenant_id, std::string_view deadline,
                               std::string_view now_iso);
    void fulfill(persistence::Connection&, std::string_view stmt_id, std::string_view now_iso);
    void withdraw(persistence::Connection&, std::string_view stmt_id, std::string_view now_iso);
    // deadline 过期处理:broken_count<3 → BROKEN;>=3 → auto-WITHDRAWN + trust_priors。
    void on_deadline_expired(persistence::Connection&, std::string_view stmt_id, std::string_view now_iso);
    // renegotiation:链长<3 → 旧打 supersedes + 新 ACTIVE;>=3 → 拒绝 emit renegotiation_blocked。
    bool renegotiate(persistence::Connection&, std::string_view old_stmt_id,
                     std::string_view new_stmt_id, std::string_view now_iso);
    persistence::Connection& connection();  // pybind helper
};

}  // namespace starling::prospective
```
`MAX_BROKEN_COUNT = 3`、`MAX_RENEGOTIATION_CHAIN = 3`(可配置)。supersedes 链复用既有 `statement_edges` edge_kind='supersedes' + `commitments` 行。

### 3.2 PolicyEngine

```cpp
// include/starling/prospective/policy_engine.hpp
struct PolicyTickStats { int fired=0; int broken=0; int auto_withdrawn=0; };

class PolicyEngine {
public:
    explicit PolicyEngine(persistence::SqliteAdapter&);
    // 入口 1:post-write(SubscriberPump 调)。消费 statement.written + commitment.*。
    void run_post_write(persistence::Connection&, std::string_view now_iso);
    // 入口 2:time-driven tick(runtime 调)。TimeTrigger 到期 + deadline 过期。
    PolicyTickStats tick(persistence::Connection&, std::string_view now_iso);
    persistence::Connection& connection();
private:
    CommitmentEngine commitment_engine_;
};
```
post-write 用 checkpoint(同 belief_tracker/projection 模式)消费 bus_events;tick 查 `commitment_triggers`/`proj_commitment_due`。所有外发 commitment.*/action.* 经 outbox `emit_event`(复用 projection_maintainer file-local helper 模式)。

### 3.3 Trigger 系统
4 类存 `commitment_triggers(kind, spec_json)`。`TimeTrigger`(tick 轮询 deadline)、`EventTrigger`(post-write 匹配 event_type+filter)、`StateTrigger`(post-write 扫描 statement 谓词)、`CompoundTrigger`(递归 DFS + 短路,all_of 遇首个未命中即停 / any_of 遇首个命中即停)。

### 3.4 AffectVector

```cpp
// include/starling/affect/affect_vector.hpp
struct AffectVector { float valence, arousal, dominance, novelty, stakes; };
double salience(const AffectVector&, double surprise_decay = 1.0);
AffectVector parse_affect_json(std::string_view);  // 解析 affect_json;缺字段默认 0
```
`salience` 公式与 `python/starling/schema/affect.py` 逐项对拍:
`(0.4+0.6·|valence|)·(0.4+0.6·arousal)·(0.3+0.7·novelty)·(0.3+0.7·stakes)·(0.6+0.4·surprise_decay)`。

### 3.5 ActionGuard

```cpp
// include/starling/prospective/action_guard.hpp
struct ActionGuard {
    std::string profile_name;
    std::set<std::string> allowed_actions;
    std::set<std::string> requires_approval;
    std::map<std::string,int> idempotency_window_sec;
};
enum class GuardVerdict { Allow, RequiresApproval, Blocked };
GuardVerdict check(const ActionGuard&, std::string_view action_name);  // fail-closed
```
`∉ allowed_actions` → `Blocked`(emit `action.policy_blocked`);`∈ requires_approval` → `RequiresApproval`。P2.c **不接执行器**(代码库无 tool-calling)——护栏 primitive + 测试就绪,P3 接 tool 执行 + idempotency 追踪。

---

## 4. Schema delta(migrations 0018–0020,当前最高 0017)

### 0018_commitments.sql
```sql
-- P2.c Commitment 五态机 (per spec §5)。绑定 modality=COMMITS statement。
CREATE TABLE commitments (
    stmt_id      TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    state        TEXT NOT NULL DEFAULT 'ACTIVE'
                 CHECK (state IN ('created','ACTIVE','FULFILLED','BROKEN','RENEGOTIATED','WITHDRAWN')),
    broken_count INTEGER NOT NULL DEFAULT 0,
    deadline     TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX idx_commitments_state ON commitments(tenant_id, state);
CREATE INDEX idx_commitments_deadline ON commitments(state, deadline);
```

### 0019_commitment_triggers.sql
```sql
-- P2.c PolicyEngine Trigger 注册 (per spec §6)。
CREATE TABLE commitment_triggers (
    id                TEXT PRIMARY KEY,
    commitment_stmt_id TEXT NOT NULL,
    tenant_id         TEXT NOT NULL,
    kind              TEXT NOT NULL CHECK (kind IN ('time','event','state','compound')),
    spec_json         TEXT NOT NULL DEFAULT '{}',
    status            TEXT NOT NULL DEFAULT 'armed' CHECK (status IN ('armed','fired','cleared')),
    created_at        TEXT NOT NULL
);
CREATE INDEX idx_commitment_triggers_kind ON commitment_triggers(tenant_id, kind, status);
```

### 0020_commitment_protection.sql
```sql
-- P2.c active_holding 反向保护映射 (per spec §7)。decay EXISTS-join commitments.state='ACTIVE'。
CREATE TABLE commitment_protection (
    commitment_stmt_id TEXT NOT NULL,
    protected_stmt_id  TEXT NOT NULL,
    PRIMARY KEY (protected_stmt_id, commitment_stmt_id)
);
```
AffectVector / ActionGuard 无迁移。

---

## 5. Commitment 五态机迁移

```
created ──Validator 通过──→ ACTIVE             (emit commitment.active_holding)
ACTIVE  ──fulfill──────────→ FULFILLED          (emit commitment.fulfilled + commitment.released)
ACTIVE  ──deadline 过期(broken_count<3)→ BROKEN (broken_count++, emit commitment.broken)
ACTIVE/BROKEN ──renegotiate(链长<3)→ RENEGOTIATED(旧打 supersedes,新 ACTIVE, emit commitment.renegotiated)
        ──renegotiate(链长≥3)──→ 拒绝          (emit commitment.renegotiation_blocked,state 不变)
broken_count≥3 后到期 ─────→ WITHDRAWN          (emit commitment.auto_withdrawn(chronic_failure) + trust_priors 下调)
ACTIVE/RENEGOTIATED ──withdraw→ WITHDRAWN        (emit commitment.withdrawn + commitment.released)
FULFILLED / WITHDRAWN = 终态
```
`on_deadline_expired` 伪码(沿 12_prospective.md §3):`if broken_count >= 3: WITHDRAWN + auto_withdrawn + trust_priors; else: BROKEN + broken_count++`。

---

## 6. Trigger 评估
（见 §3.3 表)TimeTrigger 由 `tick(now)` 轮询 `commitment_triggers WHERE kind='time' AND status='armed'` 且关联 commitment `state='ACTIVE'` 且 deadline<=now → emit `commitment.fire` + status='fired'。EventTrigger/StateTrigger 在 `run_post_write` 评估当前 batch 的 statement.written/cognizer.observed。CompoundTrigger 递归短路。

---

## 7. 保护与解除(SQL-backed)
**protected_stmt_id 范围(P2.c)**:`active_holding` 至少保护 commitment 自身的 COMMITS statement(`commitment_stmt_id == protected_stmt_id`);更广的 related-stmt 派生(derived_from 等)留后续扩展。TC-A9-001/002/003 以保护 commitment 自身 statement 为准。

```
active_holding → INSERT commitment_protection(commitment_stmt_id, protected_stmt_id)  -- P2.c: 自身 stmt_id
op_decay(consolidation_ops.cpp): active_grounded =
  EXISTS(SELECT 1 FROM commitment_protection cp
         JOIN commitments c ON c.stmt_id = cp.commitment_stmt_id
         WHERE cp.protected_stmt_id = <candidate> AND c.state = 'ACTIVE')
  → true → 不 ARCHIVE
terminal(FULFILLED/WITHDRAWN): c.state≠'ACTIVE' → EXISTS 假 → 保护自动解除(commitment.released 供可观测)
boot: 保护全 SQL durable → 新 PolicyEngine/runtime 实例跑 decay 仍生效(无显式 boot-replay)
```
**红线**:`op_decay` 现 `active_grounded=false`(consolidation_ops.cpp:115)→ 改 SQL EXISTS;不动 decay 其余逻辑;M0.8 decay 测试须回归通过。

---

## 8. AffectVector → 优先级重放权重(采样时,写路径零改动)
`ReplayScheduler` 构造 `SamplerInputs`:解析 `statements.affect_json` → `AffectVector` → `salience()` 作 `in.salience`;`arousal` 喂 `in.affect_arousal`(现硬编码 0,replay_scheduler.cpp:159)。`affect_json` 为 `{}`/无效 → 回退 column salience(或默认)、arousal=0。`swr_sampler.sample_weight` 已有 `salience` 基数 + `(1+arousal_bonus·arousal)` 项 → 喂真值即激活优先级。

---

## 9. ActionGuard
（见 §3.5)`check` fail-closed:未在 allowed_actions → Blocked + emit `action.policy_blocked`;在 requires_approval → RequiresApproval。P2.c 不接执行器,独立单测。

---

## 10. 错误处理
| 场景 | 处理 |
|---|---|
| commitment.* 事件 idempotency 冲突 | tolerate(同 emit_event 模式)|
| deadline 缺失(COMMITS 无 event_time_end)| 用 observed_at + 默认窗口;无则不注册 TimeTrigger |
| renegotiate 链长超限 | 拒绝 + emit renegotiation_blocked,state 不变(调用方先 withdraw 再新建)|
| protected stmt 已删 | EXISTS 自然为假,decay 正常 |
| PolicyEngine subscriber 异常 | SubscriberPump SAVEPOINT 隔离(同其余 5 subscriber)|
| affect_json 解析失败 | 回退 column salience,不抛 |

---

## 11. 测试矩阵(tests-only gate,CI 确定性,无 live-LLM)
| 层 | 用例 |
|---|---|
| C++ unit | CommitmentEngine 每条迁移 + broken_count + auto-withdrawn + 链长守护;Trigger 4 类 + compound 短路;AffectVector salience/arousal(与 affect.py 对拍);ActionGuard check(allow/approval/blocked fail-closed)|
| C++ integration | PolicyEngine run_post_write(建 commitment + 注册 trigger + event/state fire);PolicyEngine tick(time fire + deadline→BROKEN);op_decay 保护 EXISTS;**5 个 §16.3-8 CRITICAL** |
| Python integration | bindings smoke;commitment 生命周期端到端;AffectVector replay-weight 优先采样 |
| 回归 | M0.8 + M0.9 + P2.a 全绿;SubscriberPump 第 6 subscriber 不 regress 前 5;§16.3-9 TC-NEW-CONFLICT-SEVERE 仍过;M0.8 decay 测试回归 |

### CRITICAL 测试(§16.3-8 准入)
- **TC-A2-001**:broken_count 累至 3 → 下次到期 → WITHDRAWN + 1 条 commitment.auto_withdrawn + trust_priors 下调。
- **TC-A2-002**:renegotiate 链长达 3 → 第 3 次拒绝 + commitment.renegotiation_blocked,state 不变。
- **TC-A9-001**:ACTIVE commitment 保护 stmt → run_decay → stmt 未 ARCHIVED。
- **TC-A9-002**:commitment→FULFILLED/WITHDRAWN → run_decay → stmt 被 ARCHIVED(保护解除)。
- **TC-A9-003**:ACTIVE 保护落 SQL → 新建 PolicyEngine/runtime 实例 → run_decay → stmt 仍未 ARCHIVED(durable)。

---

## 12. 实施偏序(供 writing-plans)
1. Schema:migrations 0018(commitments)/0019(commitment_triggers)/0020(commitment_protection)。
2. 纯计算:AffectVector + salience(单测对拍);ActionGuard check(单测)。
3. CommitmentEngine:五态机迁移 + broken_count + 链长守护(单测 + TC-A2-001/002)。
4. Trigger 系统:4 类评估 + compound 短路。
5. PolicyEngine:run_post_write(建 commitment + trigger 评估 + commitment.* 迁移)+ tick(time + deadline)。
6. 保护:commitment_protection 写 + op_decay SQL EXISTS(TC-A9-001/002/003)。
7. AffectVector replay-weight:ReplayScheduler 喂 sample_weight(优先采样测试)。
8. SubscriberPump:接第 6 subscriber policy_engine(不 regress 前 5)。
9. pybind:暴露 CommitmentEngine / PolicyEngine / AffectVector / ActionGuard;cmake --install + pip reinstall。
10. 回归 + 里程碑关闭(roadmap flip + final review + merge)。

---

## 13. 元数据
- **里程碑**:P2.c(前瞻与情感)
- **依赖**:P2.b close(M0.9 merge `d47fcae`)
- **后继**:P3(ActionPolicyGraph / tool 执行 / Affect Buffer 写时 / Working Set 渲染)
- **roadmap 行**:P2.c(第 73 行)
- **分支**:worktree-p2-c-prospective-affect,--no-ff 合并 main
- **2026-05-30 v1**:初版。基于 brainstorming 3 决策(单一里程碑 / stateless SQL-backed PolicyEngine / tests-only gate)+ Section A-C 逐段确认。
