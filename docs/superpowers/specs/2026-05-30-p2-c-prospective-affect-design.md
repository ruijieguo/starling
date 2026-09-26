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

# P2.c 前瞻与情感 — 设计规格
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

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
