<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](../../superpowers/specs/2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

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

# ToM Engine
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **语义证据契约状态（2026-09-12）**：已实现并通过完整工程验证；真实诊断已完成并核验，质量门槛未通过，默认关闭，设计见 [Source-Grounded Claim Contract](../../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md)。ToM 推断继续使用 derived_from 与 perspective_take；按已确认契约 reported/conditional/questioned scope 不得被提升为 holder 的 asserted belief，除非有新的直接证据。

## 2026-09-11 语义证据契约

实验声明中的 REPORTED/CONDITIONAL/HYPOTHETICAL/QUESTIONED 不等价于 holder 的实际当前状态。范围和来源随检索注释保留；ToM 新命题只记录 derived_from，不继承直接证据证书。实验谓词不扩展现有 ToM 算子规则，任何未来将非实际范围输入新推断的路径都必须保留该范围。

实现状态与评测证据统一见 [同步清单](../claim_contract_sync.md)。

## 功能定义

ToM Engine 是多阶信念追踪与心智推理子系统。承担五项职责：（1）二阶信念物理实现，通过嵌套 Statement 加 `nesting_depth` 字段展平存储；（2）`perspective_take` 算子，从任意 Cognizer 视角重建可见世界与信念子图；（3）7 个 Mentalizing Primitives，提供可查询的高阶认知原语 API，将 LLM 从每次重新模拟中解放；（4）Grounding Acts 共识池更新，维护 CommonGround 条目的生命周期；（5）Adaptive ToM Order，由 `ToMDepthEstimator` 实时估计 partner 的 ToM 阶数，动态调整 `nesting_depth` 上限。

---

## 输入

- perspective_take(target, time) 调用（来自 Retrieval Planner）
- Mentalizing Primitive 调用（7 个 API：what_does_X_believe 等）
- Bus 事件流（statement.written 用于 Belief Tracker 增量更新）
- Grounding Act 触发（来自 conversation event）

## 输出

- Context 数据结构（visible / target_beliefs / cg）
- 嵌套 Statement（nesting_depth ≥ 1，写入 Bus 时标 provenance=tom_inferred）
- Mentalizing API 结果（自然语言或结构化 belief 集合）
- CommonGround 更新事件（grounded / suspected_diverge / RECANTED 迁移）
- ToMDepthEstimator 输出（partner 当前 ToM order 估计值）

---

## 主要流程

### 1. Belief Tracker 每回合更新

```
1. 抽取本回合产生的新 Statement（LLM tool-call，XML 严格约束）
2. 判断是否更新某主体的 belief 集
3. 与现有信念冲突 → 打 CONFLICTS_WITH 边
4. confidence 漂移：同主体反复确认 → 上调；反例 → 下调
5. 检测信念修正事件（"其实我之前理解错了"）→ 触发 Reconsolidation
6. perceived_by 推断：谁在场、谁可见
7. holder 归属判定（说话人 ≠ holder，如"Bob 说他喜欢……"）
```

**双限流保护**（先检查链长，再检查窗口）：

- 链长限流：按事件 `causation_chain` 长度限制所有派生事件传播深度；若 `stmt.derived_depth >= 3` 或链路中出现 `ToM → Replay → Container → ToM`，暂停自动增量推断，仅在用户显式 `META_BELIEF` / `perspective_take` 查询时即时计算。
- 窗口限流：同一 `(holder, subject, predicate, object)` 的 ToM 推断在 10 分钟窗口内最多自动写入 1 条；其余仅作 transient context，不落库、不 emit `statement.written`。
- 两限流同时触发时，链长保护无限递归，窗口保护抖动写入。

### 2. perspective_take(target, time) 算子

```python
def perspective_take(target: CognizerRef, query: str, time: datetime) -> Context:
    visible        = filter_by_frontier(engram_store, target, time)  # KnowledgeFrontier 遮蔽
    target_beliefs = neocortex.query(holder=target, time=time)       # 取 holder=target 子图
    cg             = common_ground(self, target)                     # 共识池
    return Context(visible, target_beliefs, cg)
```

任何对话生成、规划、协商均先调用 `perspective_take(other)` 取对方视角再决策。`filter_by_frontier` 依赖 [Cognizer Hub](08_cognizer.md) 维护的 KnowledgeFrontier；`neocortex.query` 依赖 [Neocortex](07_neocortex.md) 的 holder 子图族。

### 3. Grounding Acts 五类动作流程

```
Assert      → 一方陈述 → 进 asserted_unack
Acknowledge → 对方确认 → 升级为 grounded
Repair      → 对方质疑 → 退回 suspected_diverge
Withdraw    → 一方撤回 → 标 RECANTED，从池中移除
SupersedeGround → 新共识覆盖旧共识 → 旧 grounded 标 superseded_by，
                  新 Statement 进 grounded
ExpireGround    → 共识过时 / 项目结束 / retention 到期 →
                  grounded → expired，不再享受 is_grounded 衰减保护
Unground        → 共同知识被显式否认或 evidence 擦除 →
                  grounded → suspected_diverge 或移除
```

### 4. grounded 判定四规则

CommonGround 条目满足以下任一条件，从 `asserted_unack` 升级为 `grounded`：

| 规则 | 条件 |
|---|---|
| 显式确认 | parties 中任一其他成员对该 Statement 显式回应、引用、复述或执行相关动作 |
| 共同在场推定 | `perceived_by` 覆盖所有 parties，且后续 N=3 轮内无人 Repair / Withdraw / 显式否认 |
| 重复确认 | 同一 Statement 或 canonical 等价 Statement 被不同 parties 成员独立提及 ≥ M=2 次 |
| 人工确认 | human review 或 policy rule 显式设为 grounded，必须保留审计 actor |

**超时降级**：`asserted_unack` 超过 T=24 小时且无任何 Acknowledge / Repair，自动降级为 `suspected_diverge`，不得推定 grounded。

### 5. Adaptive ToM Order 动态调整流程

```
1. ToMDepthEstimator.estimate(partner, context) 返回 partner 已展现的
   ToM 阶数（任意 int，非帽在 0/1/2）
2. 自动路径（belief_tracker handler）：镜像观察到的他者信念到任意深度，
   不受估计器 gate（mirror = 复述既有事实，不是过度推理）
3. 显式路径 persist_meta_belief：把 depth-k 源包成 self 的 depth-(k+1) 信念，
   仅当 estimate(partner) >= source_depth+1 才放行——过度推理在此路径上
   是 fabrication（凭空虚构 partner 未展现的更深心智），受估计器 gate
4. 软上限 max_nesting_depth（默认 32）+ 级联上限 max_cascade_depth（默认 8）
   兜底 runaway，与认知阶数无关
```

---

## 核心算法

### 1. 嵌套 Statement 展平

二阶信念存储为多条带 `nesting_depth` 的 Statement，`object` 字段为 `StatementRef` 时 `nesting_depth` 加 1：

```
Outer:
  holder=self, subject=Alice, predicate=BELIEVES,
  object=ref(Inner), nesting_depth=1

Inner:
  holder=Alice, subject=Bob, predicate=KNOWS,
  object=ref(Innermost), nesting_depth=2

Innermost:
  subject=Project_X, predicate=delayed, polarity=POS,
  nesting_depth=2   # 内容陈述
```

嵌套深度任意（arbitrary multi-order），不设认知容量帽。深度由三道护栏界定：无环性（cycle guard，祖先链 id 重复即拒）+ 软上限 `max_nesting_depth`（默认 32）+ 级联上限 `max_cascade_depth`（默认 8，单次自动生产事件级联的派生深度）。这些是 runaway 护栏，不是“成人三阶 ToM 容量约束”。

### 2. 双限流：先链长，再窗口

```python
def should_persist_tom_statement(stmt, causation_chain) -> bool:
    # 链长限流（§5.4）：约束所有派生事件传播深度
    if len(causation_chain) >= CHAIN_MAX:        # 默认触发阈值
        return False
    if stmt.derived_depth >= MAX_CASCADE_DEPTH:   # 默认 8（级联 runaway 护栏）
        return False
    if has_cycle_pattern(causation_chain):        # ToM→Replay→Container→ToM
        return False

    # 窗口限流（§9.2）：仅约束 provenance=tom_inferred 的写入频率
    key = (stmt.holder, stmt.subject, stmt.predicate, canonical(stmt.object))
    if window_count(key, window=600) >= 1:        # 10 分钟窗口
        return False                              # 作 transient context，不落库

    return True
```

### 3. Adaptive ToM Order 估计

```python
class ToMDepthEstimator:
    """基于 partner 的 prior interactions 估计其 ToM order"""
    def estimate(self, partner: CognizerRef, context: Situation) -> int:
        # 0: partner 不追踪任何人的信念（零阶）
        # 1: partner 追踪我方信念（一阶）
        # 2: partner 追踪"我方以为他们相信什么"（二阶）
        ...
```

输入：`CognizerRef`（partner 标识）+ `Situation`（当前交互上下文）。
输出：`int`（0 / 1 / 2），驱动 Belief Tracker 的 `nesting_depth` 上限与是否持久化 depth=2 Statement。

### 4. grounded 状态机

```
asserted_unack
    │ Acknowledge / 共同在场推定（N=3轮）/ 重复确认（M=2次）/ 人工确认
    ▼
grounded ──── SupersedeGround ──→ superseded_by（旧）/ grounded（新）
    │          ExpireGround ───→ expired
    │          Unground ────────→ suspected_diverge
    │          Withdraw ────────→ RECANTED
    │
asserted_unack ─── 超时 T=24h 无 Ack/Repair ──→ suspected_diverge
```

### 5. CommonGround 过时治理

`is_grounded` 仅表示"曾经达成共同知识"，不等于永久真。维护字段：`grounded_at`、`last_confirmed_at`、`superseded_by`、`expired_at`。

触发路径：
- ConflictProbe（§5.2）产生 `superseding` 等级 → CommonGround Builder 执行 SupersedeGround（主触发器）。
- evidence 被 crypto_erasure 且无独立证据 → Unground。
- Norm / Commitment 已终止且长期无确认 → Replay 产候选，降低 `is_grounded` 因子。
- Container.rebuild 做 fallback 一致性校验与补审计（非直接修改 CommonGround）。

---

## 数据结构

### 嵌套 Statement 字段

```python
@dataclass
class Statement:
    holder:        CognizerRef | None        # 信念持有者；None 表示客观事实
    subject:       EntityRef
    predicate:     PredicateType
    object:        EntityRef | StatementRef  # StatementRef 时触发 nesting_depth +1
    nesting_depth: int                       # 无界：0=一阶，1=二阶，2=三阶，…（至软上限 max_nesting_depth）
    polarity:      Literal["POS", "NEG"]
    confidence:    float
    provenance:    Literal["observed", "inferred", "tom_inferred", ...]
    derived_depth: int                       # ToM 派生链深度
    derived_from:  StatementRef | None       # 直接前驱
    perceived_by:  list[CognizerRef]
    is_grounded:   float                     # CommonGround 衰减因子
```

### Mentalizing Primitives（7 个 API）

| API | 含义 | 对应脑区 |
|---|---|---|
| `what_does_X_believe(about=Y)` | X 关于 Y 的信念集 | rTPJ |
| `what_does_X_think_Y_believes(about=Z)` | 二阶 ToM | mPFC |
| `does_X_know(fact)` | X 是否知道（查 X 的 evidence + frontier） | 知识归因 |
| `predict_X_would(in_situation)` | 模拟 X 在某情境下的反应 | simulation theory |
| `find_misalignment(between=[X,Y], about=Z)` | 找 X 和 Y 对 Z 的认知差异 | 冲突检测 |
| `shared_with(members)` | N 主体的 SharedGround | common ground |
| `who_committed(to=Y)` | 关于 Y 的所有未决承诺 | prospective + 社会 |

### GroundingAct 枚举

```python
class GroundingAct(Enum):
    ASSERT          = "assert"           # 进 asserted_unack
    ACKNOWLEDGE     = "acknowledge"      # 升级为 grounded
    REPAIR          = "repair"           # 退回 suspected_diverge
    WITHDRAW        = "withdraw"         # RECANTED，移除
    SUPERSEDE_GROUND = "supersede"       # 旧 superseded_by，新 grounded
    EXPIRE_GROUND   = "expire"           # grounded → expired
    UNGROUND        = "unground"         # grounded → suspected_diverge 或移除
```

### CommonGround 条目

```python
@dataclass
class CommonGroundEntry:
    statement:        StatementRef
    status:           Literal["asserted_unack", "grounded",
                               "suspected_diverge", "expired", "RECANTED"]
    parties:          list[CognizerRef]
    grounded_at:      datetime | None
    last_confirmed_at: datetime | None
    superseded_by:    StatementRef | None
    expired_at:       datetime | None
    audit_actor:      CognizerRef | None   # 人工确认时必填
```

### Context（perspective_take 返回值）

```python
@dataclass
class Context:
    visible:        list[EngramRef]      # 经 KnowledgeFrontier 过滤的可见记忆
    target_beliefs: list[Statement]      # holder=target 的信念子图
    cg:             list[CommonGroundEntry]  # self 与 target 的共识池交集
```

### ToMDepthEstimator

```python
class ToMDepthEstimator:
    def estimate(
        self,
        partner:  CognizerRef,   # 交互对象标识
        context:  Situation,     # 当前情境（对话历史、任务类型等）
    ) -> int:                    # 返回 0 / 1 / 2
        ...
```

---

上述 Python 示例为绑定层接口契约。核心实现为 C++ 抽象类，Python/JS/Rust 等绑定通过 pybind11 / NAPI / cxx 自动生成存根。

## 相关概念

**二阶 ToM / nesting_depth**：`nesting_depth=0` 为一阶信念（X 相信 P），`nesting_depth=1` 为二阶（self 相信 X 相信 P），`nesting_depth=2` 为三阶，依此类推——深度无界，仅由软上限 `max_nesting_depth`（默认 32）与无环性护栏约束，无固定认知容量帽。

**StatementRef 嵌套**：`Statement.object` 指向另一条 Statement 时构成嵌套。展平存储保留全部中间节点，通过 `derived_from` 链接。

**perspective_take**：算子名。输入 `(target, time)`，输出 `Context(visible, target_beliefs, cg)`。依赖 [Cognizer Hub](08_cognizer.md) 的 `KnowledgeFrontier` 执行 `filter_by_frontier`，依赖 [Neocortex](07_neocortex.md) 的 holder 子图族执行 `neocortex.query(holder=target)`。

**Mentalizing Primitives**：7 个高阶认知原语 API，将心智状态查询结构化，避免 LLM 每次对话重新全量模拟。

**Grounding Acts**：CommonGround 条目状态迁移动作集。包含 Assert / Acknowledge / Repair / Withdraw / SupersedeGround / ExpireGround / Unground 七种。

**grounded**：CommonGround 条目达成共同知识的状态。满足显式确认、共同在场推定（N=3）、重复确认（M=2）、人工确认之一即可升级。

**suspected_diverge**：认知分歧待确认状态。来源：Repair 触发、Unground 触发、或 `asserted_unack` 超时 T=24h 降级。

**RECANTED**：Withdraw 后的终态。Statement 仍保留（审计用），不再参与推理。

**Adaptive ToM Order**：`ToMDepthEstimator` 实时估计 partner 已展现的 ToM 阶数（任意 int）。自动路径按观察到的深度镜像信念、不 gate；显式 `persist_meta_belief` 路径用估计器 gate（`estimate(partner) < source_depth+1` → `gated_order`），拦的是 fabrication——凭空虚构 partner 未展现的更深心智，而非镜像。

**KnowledgeFrontier（外部依赖）**：由 [Cognizer Hub](08_cognizer.md) 维护，描述每个 Cognizer 在指定时刻的可见知识边界，`perspective_take` 的 `filter_by_frontier` 步骤依赖此结构。

**holder 子图族（外部依赖）**：[Neocortex](07_neocortex.md) 按 `holder` 字段组织的 Statement 子集，支持 `neocortex.query(holder=target, time=time)` 查询。

- 配置：所有 Adapter 与运行时配置采用 JSON 格式，统一 schema 见主文档 §2.0

---

## 实现补记(2026-06-12 P3.a2)

P3.a2 交付:**Grounding Acts 七幕齐全**(expire_ground/unground/
acknowledge_manual 补全,migration 0024 放行七幕 CHECK;人工确认落
audit_actor 列);**治理接线**——`statement.superseded` → SupersedeGround
联动(CG 订阅者消费仲裁 payload,主触发器断线修复)+ 24h 超时降级每批自动
运行 + canonical cg_ref 的完整 parties 集合过滤（普通双方兼容 `a::b`，N 元或
含分隔符 ID 使用 `cg:v1:<canonical-parties-json>`）;**双限流补全**
(`tom/limiting`:链长 derived_depth>=3 ‖ 链长>=3 对齐 Bus 深度帽,
复用 10min 窗口);**二阶生产端**(`tom/second_order`:belief_tracker 的
statement.written handler 自动把他者一手语句建模为 self 的 depth=1 嵌套行,
tom_inferred + 置信折减 0.9 + salience 继承 ×0.8 + 永久幂等;显式
`persist_meta_belief` depth=2 受 ToMDepthEstimator order>=2 门控——Adaptive
ToM Order 首个 driver 消费点);**mentalizing 7/7**(补
what_does_X_think_Y_believes / predict_X_would(诚实契约:返回可审计
PredictionBasis,不编造预测文本)/ who_committed);二阶准入评测
`eval_tom_bench.py --order second`(阈 0.70,fixture 入 CI,真模型 gated)。

**触发面注记**:单 agent 抽取流所有语句 holder=self("X 信 P"是扁平一阶
表示),自动二阶建模的触发面是**多 holder 写入**(dashboard 演示数据/
程序化/多智能体 ingestion)。扁平→嵌套的再抽取(LLM 嵌套抽取)归 P3+。
grounded 判定规则 #3(M=2 重复确认)由订阅者「同命题异方→acknowledge」
路径覆盖(与 #1 同路),未另设计数器。


## 来源话轮实现核对（2026-09-12）

版本化来源话轮由 C++ 生成与解析，直接证据回读共用严格验证。该子系统继续消费已有证据与时间契约，不新增语言 binding 中的语义逻辑。来源观察时间不作为绝对事件时间；本轮核对与诊断统一见 [设计同步清单](../claim_contract_sync.md) 和 [来源话轮评测报告](../../eval/2026-09-12-socialmem-source-turn.md)。


## 生成契约完整性同步（2026-09-12）

按 [中文生成契约设计](../../superpowers/specs/2026-09-12-claim-generation-design.md)，C++ 在抽取提示中明确对象、逐字主题、原始时间限定和字段类型约束，并提供与本次来源隔离的通用中英文参考示例。模型输出校验、准入、存储/检索与默认开关保持既有约束，Python 仅绑定和评测编排；参考示例不作为当前证据。本轮 C++ 实现、完整回归、离线核验及历史响应 140/140 一致性重放已完成；真实诊断于北京时间 2026-09-13 完成核验，为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、独立对象 12/14、主题/联合各 1/14，原生技术失败 5；主题字面匹配分数不能解释为字段缺失。P1 兼容与逐例不退步门槛仍失败，Q1/Q9 结构化及链接组仍为 0/3，默认关闭。详见 [生成契约评测报告](../../eval/2026-09-12-socialmem-generation.md)。其他专项职责沿用设计同步清单，历史快照保持。

## 输出协议与偏好边界同步（2026-09-13）

按 [中文修复设计](../../superpowers/specs/2026-09-13-claim-protocol-boundary-design.md) 继续已批准优化：C++ 提示强调键唯一、时间原文及同话轮引用，准入与解析共用合法原因目录，窄范围拒绝把明确偏好对象写成 feels。真情绪不因同源其他偏好句被拒；Bus/回读复用共享契约，Python 仅绑定与编排。当前已完成 RED、C++ 实现与复审修复后的完整回归（C++ 1,062 项，Python 1,319 项通过/15 项跳过）；旧响应重解析 137/140 一致，3 条偏好误标候选提前拒绝。复合/因果情绪及被动 preferred 感受保留准入，句尾标点边界有正反例覆盖。独立复审发现均已关闭，最终离线 140 条/144 数据库核验通过；真实诊断已完成并由原生验证器核验为 `verified / complete_with_errors`：140 条重放、144 个数据库；固定候选 56/64（TP 30、TN 26、误收 0、误拒 1、技术失败 7），synthetic 冻结 11/16、契约 11/16（有效分母 15/16），P1 combined F1 为 holder 0.7317、holder/perspective 0.6829、predicate/object 0.7683；扩展标签 object/topic/scope/time/joint 为 12/14、2/14、12/14、12/14、2/14（有效目标 13）；Q1/Q9 的 baseline、structured、linked 均为 0/3，full 均为 3/3；实际证据链仍受入库与证据聚合限制。原生技术失败共 10 条，主要为重复 JSON 键和准入 JSON 后追加文本；无效裁判票 0。`promotion_ready=false`，生产默认保持关闭，不运行 1,031 题全量。默认、原标签、检索与历史归档保持。

## 2026-09-16 能力与得分路线修订（已授权自主迭代）

人物社会认知重点验证 holder/actor/转述者/认知目标与层次的区别。跨 holder 查询须传入显式授权范围，不因评测需要自动扩大到租户全部私有记忆。 具体范围、测试与验收见[统一方案](../../superpowers/specs/2026-09-16-socialmem-capability-and-score-design.md)。本段描述计划，不代表已经实现或获得新分数。

最新执行顺序已按用户指令调整：先冻结当前默认 Starling 并完成全部 1031 题基线，再按真实失分执行中文文档→失败测试→C++ 改进→同条件复测，循环自主迭代，无需重复申请常规步骤授权。基线前仅补评测编排及题目允许来源范围，不预修被测能力。详见[基线优先执行计划](../../superpowers/plans/2026-09-16-socialmem-baseline-first.md)。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
