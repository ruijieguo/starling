<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Starling Memory: Agent Memory with Multi-Subject Social Cognition and Brain-Like Dynamics
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **最新输出协议与偏好边界结果（2026-09-13 核验）**：中文文档→失败测试→C++ 实现及评测已完成，C++ 1,062 项、Python 1,319 项通过（15 项跳过）。真实诊断 `verified / complete_with_errors`；固定候选 56/64、synthetic 契约 11/16（有效分母 15/16），P1 combined F1 为 0.7317/0.6829/0.7683，Q1/Q9 仅 full 阶段 3/3，质量门槛未通过。详见 [输出协议与偏好边界报告](eval/2026-09-13-socialmem-protocol-boundary.md)。此前各阶段数字保留各自证据时间。

> **来源话轮阶段进展（2026-09-12）**：C++ 版本化输入及独立扩展标签已实现，完整回归及离线/真实原生核验通过；真实质量门槛未通过。此前各阶段“时间输入/扩展标签未完成”的描述为当时状态；当前交付范围与剩余限制见 [来源话轮评测报告](eval/2026-09-12-socialmem-source-turn.md)。

> **JSON mode 请求实验（2026-09-12）**：C++ `OpenAIAdapter::Config::json_object_output` 默认关闭，仅约束抽取请求格式并保留响应原文，普通生成单独绕开。旧数组抽取使用默认实例；非法枚举继续严格拒绝。配置不代表服务器支持或 schema 保证，评测显式开启并归档参数；Python 仅绑定与编排。完整范围及待验证状态见 [中文优化设计](superpowers/specs/2026-09-12-socialmem-optimization-design.md)。

### A Technical Report

**中文版: [Starling_Technical_Report.zh-CN.md](Starling_Technical_Report.zh-CN.md)**

---

## Abstract

Endowing large language model (LLM) agents with Theory of Mind (ToM) — the capacity to infer others' beliefs, intentions, and knowledge states and to act on them appropriately — is usually pursued as a *reasoning* problem, attacked with prompting, chain-of-thought, or reinforcement learning that coaxes the model to "think through" what another mind holds. This report argues an orthogonal position: **Theory of Mind is first a problem of representation, not of inference.** Once the structure of social cognition — who believes what, on what evidence, from whose perspective, and for whom it is mutual — is encoded into the memory substrate itself, mental-state attribution turns from a brittle reasoning chain into a query over a typed graph of beliefs.

On this stance we built Starling Memory and offer three contributions. **First, a multi-subject social-mind representation.** We replace the subject-less *fact* with a holder-attributed *statement* as memory's atomic unit, collapsing five concerns that conventional memory treats separately — attribution, contradiction, retraction, perspective, and recursive belief — into facets of a single representational primitive. **Second, a dual representation of higher-order belief.** We distinguish *symbolic* nesting of propositional attitudes from *situated* reconstruction of perceptual access, and argue that the latter — grounding false belief in *which world-states each agent could observe, and when* — is the cognitively correct basis for higher-order ToM, and the source of our largest gains on nested-belief benchmarks. **Third, brain-like memory dynamics.** Drawing on Complementary Learning Systems (CLS), consolidation, and reconsolidation, we model memory as a dynamical system with fast encoding and slow consolidation, prioritized replay, recall-induced plasticity, adaptive forgetting, and prospective self-cueing — not as a static store.

On the HiToM higher-order ToM benchmark, injecting Starling's deterministic nested-tracking machinery into zing-14b (a 14-billion-parameter reasoning model built on Qwen3-14B) raises overall accuracy from 0.793 to 0.834, with the gain **monotonically concentrated at the deepest reasoning orders** (+10.8 points at order 3, +8.3 at order 4); for a stronger reasoning model (deepseek-v4-pro) the deepest-order gain is larger still, roughly +14 to +18 points at orders 3–4. We characterize the **boundary** with equal rigor: deterministic structure yields a net gain only in the narrow regime where it is more reliable than the model's own reasoning (deep nested tracking), and is redundant or harmful where a strong model already succeeds. That boundary — a falsifiable account of *when structured memory beats free reasoning* — is itself one of our empirical contributions.

---

## 1 Introduction

### 1.1 Theory of Mind: from a reasoning puzzle to a representation puzzle

Theory of Mind is a cornerstone of human social intelligence: understanding that others hold beliefs that may differ from one's own and may be false (false belief) underwrites cooperation, deception, teaching, and empathy. Developmental psychology measures it with the classic Sally–Anne false-belief task (Wimmer & Perner, 1983), and stacks it into higher-order mentalizing — "A thinks B doesn't know that C has changed her mind."

A growing literature asks whether LLMs possess Theory of Mind. The findings are in tension: models do passably on canonical first-order tasks yet degrade sharply under mild perturbation or deeper nesting (Ullman, 2023), suggesting reliance on **superficial patterns rather than robust social reasoning** (Shapira et al., 2024). The dominant response pushes on the *reasoning* side — longer chains of thought, process rewards, adversarial training.

We offer a different diagnosis. In standard retrieval-augmented memory, a memory is a subject-less proposition (a triple or a span of text), and social information is flattened: the speaker, the subject, and the belief-holder collapse into one layer; perspective and evidence become unaddressable. On such a substrate, any question about "who thinks whom believes what" must be reconstructed at reasoning time — brittle and unauditable. We therefore argue: **rather than have the model reason out social structure each time, encode that structure into the representation of memory.** Mental-state attribution should be a *query* over a typed, perspectival, nestable belief graph, not a stochastic inference.

### 1.2 Memory: from retrieval to a brain-like dynamical system

A second tension concerns memory itself. Agent memory has matured into a capable retrieval stack, but its implicit ontology is **static**: written-then-fixed — no consolidation, no forgetting curve, no revise-on-recall, and no prospection that wakes the agent without an external query. Biological memory is precisely a *dynamical system*: Complementary Learning Systems theory (McClelland et al., 1995) holds that the hippocampus's fast encoding and the neocortex's slow consolidation cooperate to balance rapid learning against catastrophic forgetting; a memory becomes briefly labile when retrieved and must re-stabilize (reconsolidation, Nader et al., 2000); emotional salience modulates what is preferentially consolidated (McGaugh, 2004).

We hold that a memory system for long-horizon human-AI collaboration should treat these dynamics as first-class design goals, not after-the-fact patches. This is more than biological analogy: consolidation buffers against extraction noise, the no-overwrite character of reconsolidation preserves the provenance of beliefs for audit and mentalizing, and salience modulation focuses finite computation on what matters.

### 1.3 Contributions

1. **An attribution-first memory ontology (§3.1–3.2):** an argument that taking the *statement* as the atomic unit and the *cognizer* as a first-class subject resolves multi-subject attribution, perspective, contradiction, and recursive belief at the representational level.
2. **A dual representation of higher-order belief, with a cognitive argument (§3.3):** distinguishing symbolic belief-nesting from perception-grounded false-belief reconstruction, arguing why the latter is the correct basis for higher-order ToM, and supporting the claim empirically (§5).
3. **A structural account of common knowledge (§3.4):** characterizing common knowledge as a fixpoint over events co-witnessed by a group, distinct from distributed knowledge.
4. **Memory as a brain-like dynamical system (§4):** unifying the consolidation lifecycle, prioritized replay, no-overwrite reconsolidation, salience modulation, and prospective cueing under CLS, each with its neuroscientific grounding and computational rationale.
5. **A boundary characterization of when structure helps (§5):** a falsifiable criterion — deterministic memory structure yields a net gain on a task iff it is more accurate than the model's free reasoning there — empirically delimited across benchmarks.

---

## 2 Design Philosophy and System Overview

### 2.1 Three axioms

Every mechanism in Starling is generated by three axioms, each grounded in a result from cognitive science or neuroscience.

**Axiom I (Attribution): there are no isolated facts, only statements attributed to a subject.** Every memory is a judgment indexed to the mind that holds it, the perspective by which that mind acquired it (firsthand, quoted, inferred, or hearsay), and the evidence on which it rests. This commitment makes attribution, contradiction, retraction, perspective, and second-order ToM facets of one representation rather than separate engineering problems.

**Axiom II (Two timescales): memory is a cooperation of subsystems at two timescales (Complementary Learning Systems).** New information first enters a fast, labile "hippocampal" form and only settles, after replay, pattern separation, and reconsolidation, into stable "neocortical" semantics, norms, and personas. The fast channel resists catastrophic forgetting; the slow channel accretes structure.

**Axiom III (Goal reconstruction): memory is reconstructed for the current goal, not replayed like a tape (Conway's Self-Memory System).** Retrieval returns a "mind summary" shaped by the querier's perspective and intent, and abstains explicitly when evidence is insufficient, rather than mechanically stitching similar fragments.

### 2.2 Architecture: cognitive middleware with a statement spine

Starling does not rewrite the vector store; it layers a cognitive tier — attribution, Theory of Mind, brain-like replay, and prospection — atop existing memory stacks, and can coexist with mem0, Letta, cognee, or Graphiti. Internally it is organized around a single **statement bus** through which all reads and writes are serialized (yielding cross-subsystem consistency, idempotency, and recoverability); around the bus sit cooperating subsystems for evidence retention, fast/slow memory, subject modeling, mentalizing, replay-driven consolidation, reconsolidation, prospection, and perspective-aware retrieval.

The cognitive kernel is implemented in modern C++ for predictable latency on the hot path, exposed to applications through language bindings. One objective signal is worth noting: among all kernel modules, the **Theory-of-Mind module is the largest by code volume** — social cognition is a first-class, deeply-implemented concern here, not a prompt-layer veneer.

---

## 3 Multi-Subject Social-Mind Representation

This section presents the representational core that separates Starling from retrieval memory. We discuss, in turn: the statement as a unifying primitive (§3.1), the cognizer as an epistemic agent (§3.2), the dual representation of higher-order belief (§3.3), common knowledge as a fixpoint (§3.4), and perspective-aware retrieval with epistemic honesty (§3.5).

### 3.1 An attribution-first commitment: the statement as a unifying primitive

Starling's central representational commitment is that **no proposition exists unowned.** Formally, memory's atomic unit is a *statement*, a nine-tuple:

> Statement = ⟨ holder, subject, predicate, object, modality, polarity, time, evidence, confidence ⟩

where *holder* is the cognizer who holds the judgment; *subject/predicate/object* form the propositional content; *modality* is the propositional attitude (belief, knowledge, desire, intention, commitment, norm, …); *polarity* is affirmation/negation/unknown; *evidence* anchors provenance; *time* distinguishes "when observed" from "when the fact holds"; and *confidence* records graded belief and preserves its revision history.

The theoretical economy of this single shape is that it unifies, as facets of one primitive, five things retrieval memory treats as separate engineering problems:

- **Attribution** is carried directly by *holder* and the perspective field — the same proposition reported firsthand, quoted, inferred, or as hearsay is one shape with a different perspective value, not four special cases.
- **Contradiction** is not resolved by overwrite: two content-equivalent statements of opposite polarity coexist via an explicit conflict relation, because they typically belong to different subjects' perspectives, and the difference is a cognitive cue, not noise.
- **Retraction** is a new statement in a "recanted" attitude layered over the old, the prior version archived rather than deleted, preserving the history of "I once believed otherwise."
- **Recursive belief** — second- and higher-order mentalizing — arises naturally by letting the *object* slot recursively reference another statement (§3.3).

Making the propositional attitude (*modality*) explicit, and in particular promoting **commitments** and **norms** to first-class attitudes, has an under-appreciated consequence: only thus can a memory like "I promised to deliver by Friday" drive runtime behavior — prospective reminders, fulfillment tracking, trust updates — rather than lie inert as text. This is where Starling parts ways with stashing social information in metadata.

> **A principle running throughout.** Whatever a representational structure can stably solve, we do not delegate to runtime model inference. Theory of Mind is a data-structure problem, not a prompt-engineering one; only in the representation does it become stably queryable, auditable, and free of LLM stochasticity.

### 3.2 The cognizer as an epistemic agent

Rather than model a user as an opaque isolation key (`user_id`), Starling promotes every user, agent, group, or role into a first-class *cognizer* — an addressable epistemic agent carrying: a cross-source stable identity (the same physical person under a different role is a different subject); **directional trust** that rises and falls with fulfilled commitments (A's trust in B is neither B's in A nor the system's in A); a **social relation graph** stored from the observer's vantage, so each party may hold an independent view of the same relationship (informed by Fiske's four relational models: communal, authority, equality, market); and a **knowledge frontier** characterizing what this subject *could* know.

The significance of this promotion is more than tidiness. A subject can be the *referent* of another's belief, or the nested *object* of a deeper one — it is precisely this "a subject can be referenced by a belief" property that makes arbitrary-order mentalizing expressible at the representational level (§3.3). By contrast, a non-cognizer *entity* (a thing, a concept) has no beliefs, trust, or knowledge frontier and may only be talked about, never hold a belief — so "who is entitled to hold a belief" is controlled at the type level.

### 3.3 The dual representation of higher-order belief (a core contribution)

"I think you think X" has two complementary representations in Starling. Distinguishing them is the key to why the system gains on higher-order benchmarks.

**(a) Symbolic nesting: attitudes about attitudes.** A meta-belief is a statement whose *object* recursively references another statement; nesting depth descends along the holder→subject chain. This expresses arbitrary-order propositional attitudes directly as graph structure: in "self believes ⟨Alice believes ⟨the project is delayed⟩⟩," each layer's holder is that layer's believing subject. The chain is queried by a recursive unwind operator; depth is bounded not by a cognitive cap but only by acyclicity and a loose ceiling. A subtle and important design is the **mirror-vs-fabrication distinction**: when a partner has actually expressed a belief, the system may unconditionally form a corresponding meta-belief (a faithful mirror); but to *infer* the partner's order-k belief as a self-held order-(k+1) model requires an **order estimator** to confirm the partner has demonstrated mentalizing at the relevant depth — otherwise it refuses, lest it fabricate deeper mental states the partner never exhibited. The estimator adaptively reads "how many orders deep to model this partner" from the nesting-depth distribution of their recent behavior, no longer saturating at second order as early designs did.

**(b) Perception-grounded false-belief reconstruction (our thesis).** Symbolic nesting expresses beliefs that have been *stated*, but does not explain the *origin* of false belief. We argue: **false belief is fundamentally a question about perceptual access evolving over time, not bare propositional nesting.** Sally wrongly believes the marble is still in the basket because she was *absent* when it was moved. Accordingly, Starling maintains a mechanism independent of symbolic nesting: from the objective events of a scene it reconstructs *the world-state each subject could observe at each moment*, and answers "what does X currently believe the state to be" by X's *last firsthand* observation — and whether that state is "stale" (≠ the current truth) is precisely the false-belief signal.

The higher-order generalization is the crucial part. To answer "c₁ thinks c₂ thinks … cₙ thinks the theme is where," the system takes the holder's last firsthand state **among the events that every observer on the chain co-witnessed** — a cross-subject **co-witness intersection**. It further enforces an **observation-primacy** principle: telling and informing (and even lies) must not override firsthand observation, and only fill gaps for an agent never present. It is this perception-grounded mechanism — not the symbolic nesting — that yields the largest gains on higher-order nested benchmarks (§5). This aligns with a cognitive insight: robust higher-order ToM rests on tracking *information flow* (who learned what, and when), not on formal manipulation of nested clauses.

### 3.4 Common knowledge as a fixpoint over co-witnessed events

Social coordination often relies on *common knowledge* — not merely that everyone knows, but that everyone knows that everyone knows, ad infinitum. It is strictly stronger than distributed knowledge: if Anne privately tells A, B, and C the same thing, all three know it (distributed knowledge holds), yet it is not common knowledge, because A does not know that B knows. Rather than approximate the concept by infinite nesting, Starling gives it a structural fixpoint characterization: **for a group G, the current state of X becomes common knowledge iff the latest relevant event any member of G perceived was co-witnessed by all of G** (a public establishment). Its computation reuses the co-witness intersection of §3.3(b): a private telling cannot satisfy all-co-witnessed and so does not constitute common knowledge; only joint co-presence at a public event closes the infinite regress. Establishing common ground further involves grounding acts (assert, acknowledge, repair, withdraw) and promotion rules — e.g. an assertion can be promoted from "asserted-but-unacknowledged" to "grounded" once all parties were present and no one objected within a few rounds — with timeout downgrades that prevent presuming consensus.

### 3.5 Perspective-aware retrieval and epistemic honesty

By Axiom III, retrieval is a reconstruction for the current goal. Given the querier, perspective, intent, and goal, the planner first does something retrieval memory usually does not: **perspective masking precedes semantic ranking.** It masks by the target subject's knowledge frontier, removing — *before* ranking — what that subject could not possibly know. This is a non-bypassable privacy and epistemic constraint, because the system holds metadata such as "A thinks B doesn't know X," which must never leak under the wrong perspective. This mask-then-rank order is what lets Starling answer counterfactual-perspective questions like "standing in Bob's shoes, how would he understand this?"

What retrieval returns is not undifferentiated text but a **mind summary** with pragmatic annotation: each item is labeled by its epistemic status — settled consensus, a party's belief (with confidence), single-source hearsay, behavioral inference, a pending commitment, or an *unresolved conflict*. When evidence is insufficient, only recanted, in unresolved conflict, or below a relevance threshold, the system **abstains explicitly**, giving a structured "I don't know, because …" rather than confabulating. This epistemic honesty — knowing what one does not know — is, in collaboration premised on reliability, as important as recall.

---

## 4 Brain-Like Memory Dynamics

If Pillar 1 answers "what to remember, and for whom," Pillar 2 answers "how memory lives over time." Starling treats neuroscience not as rhetoric but lands its dynamics as computable, auditable mechanisms. A governing design choice: the hippocampus and neocortex are not two physical stores but two logical *phases* of one memory population, distinguished by a **consolidation state** — "moving" a memory between them is a phase transition. This is the system's reading of CLS as "memory as cross-phase flow."

### 4.1 Complementary Learning Systems: why two timescales

CLS theory supplies the computational motive for two systems (McClelland et al., 1995): a single fast-plastic network learning continually would catastrophically overwrite old knowledge, while a single slow network could not encode new experience promptly. The brain's solution is a division of labor — the hippocampus rapidly encodes episodes, and offline replay during rest slowly interleaves them into neocortical semantic structure. Starling accordingly admits new statements in a labile phase into fast memory, settling them into stable semantics, norms, and personas only after replay and reconsolidation. Slow memory accepts no direct writes, updating only through the consolidation channel — which both preserves the anti-catastrophic-forgetting buffer and provides a gate against LLM extraction noise: statements that fail the consolidation threshold never pollute the stable semantic layer.

### 4.2 The consolidation lifecycle: memory as a continuant

A memory's "consolidation state" is a continuant spanning its whole life, tracing a trajectory from labile, to first consolidation, to settled, to (long-unrecalled) archived, to forgotten — permitting a single retrograde step when recalled, back into the plastic phase (§4.4). This lifecycle unifies operations that retrieval memory keeps disjoint (write, dedup, expire, delete) into transitions of one state machine, letting a few invariants govern global correctness: transitions are mostly one-way, provenance is frozen on write, and only a severe contradiction begets a new version while preserving the old via archival and a supersession chain. Compared with a "draft–stable–tombstone" trichotomy, the richer lifecycle carries the biological distinction between consolidation and reconsolidation, at the cost only of a slightly larger state space.

### 4.3 Prioritized replay: the computational principle of offline reactivation

Consolidation is driven by a **replay scheduler** that emulates the hippocampus's offline reactivation during rest and sleep. Two computational principles run through it.

First, **forgetting is active and structured.** We model a memory's retrievability as exponential decay, S(t) = exp(−Δt / S₀), whose characteristic lifetime S₀ scales with rehearsal frequency (the spacing effect), intrinsic salience, whether the memory is under an active social commitment, and the propositional attitude — a **commitment** resists decay far more strongly than an **assumption** (a lifetime ratio of roughly 8:1). This renders the intuition "important memories decay slowly" as a tunable, cognitively grounded curve (fusing the Ebbinghaus curve with Anderson's active forgetting).

Second, **replay is prioritized.** Inspired by preferential reactivation during hippocampal sharp-wave ripples (Buzsáki) and by prioritized experience replay in machine learning (Schaul et al., 2015; Mattar & Daw, 2018), the scheduler samples by a composite weight: salience, novelty, involvement in an unresolved conflict, emotional arousal, and goal-relevance raise a memory's replay probability, while it decays with the number of prior replays to reflect diminishing returns. A key structural constraint: memories the system itself derived are excluded from the sampling pool, severing the "derive–replay–re-derive" self-excitation loop — a stability condition that must be imposed explicitly when engineering biological replay. Sleep-phase replay also performs **semantic abstraction**: when enough independent subjects assert the same proposition, the system, gated by a double LLM entailment check, pools it into a generalized norm — the engineering counterpart of CLS's "hippocampal detail rising into a neocortical schema."

### 4.4 No-overwrite reconsolidation: the labile-to-restabilize cycle and its epistemic meaning

In neuroscience, a retrieved memory becomes briefly labile and must re-stabilize (reconsolidation, Nader et al., 2000); within this window it can be modified. Starling accordingly stipulates: **a memory becomes plastic only after being recalled or encountering conflict, and a revision never overwrites the prior version.** Recall or conflict opens a **plastic window** (whose duration adapts to the propositional attitude, from minutes to hours, with the ceiling taken from the neuroscience of reconsolidation); when it closes, the system aggregates the evidence accumulated meanwhile and arbitrates: weak corroboration merely nudges confidence without a new version, while a severe contradiction **forks** a new version, links it to the old by a supersession relation, and archives — not deletes — the old.

This "no overwrite" design has a deep **epistemic meaning**, not merely versioning hygiene: preserving a belief's history and provenance lets the system answer "when, and on what basis, did I change my mind," supporting audit, rollback, and second-order reflection on the evolution of its own beliefs; and it categorically avoids the amnesia of destructive updates — "I said X, but memory has overwritten it." Identity-bearing fields (holder, source, perspective) are forbidden in-place edits; every correction must go through the explicit supersession path — elevating "the traceability of memory" to a system invariant.

### 4.5 Salience modulation and prospective memory

**Affect as salience.** Emotion in biological memory is not decoration but a modulator of what is preferentially consolidated, how slowly it decays, and in what mood it is more readily recalled (McGaugh, 2004; Bower, 1981). Starling reduces a low-dimensional affect vector (valence, arousal, novelty, stakes — rooted in the PAD dimensional model) to a salience scalar, and lets it modulate a memory's fate at write, replay, forgetting, and retrieval-reranking. We note candidly that content-driven affective appraisal is currently early-stage, with most affect signals running on neutral defaults — an honest maturity boundary, not a finished capability.

**Prospective memory: woken without a query.** Reactive retrieval returns memory only when asked; prospective memory lets an agent act *proactively* at the right moment — the cognitive prerequisite for fulfilling commitments and intentions (the multiprocess framework of McDaniel & Einstein). Starling realizes it with a **commitment state machine** (active → fulfilled / broken / renegotiated / withdrawn) and typed **triggers** (time, event, state, and their compounds): a background rhythm, with no external query whatsoever, still inspects due time-triggers and raises the corresponding commitment, spontaneously surfacing "it's time to follow up" into working memory. An active commitment also **shields its associated memories from decay** — the engineering image of the psychological "intention-superiority effect" (uncompleted intentions retain heightened accessibility, Goschke & Kuhl). For external actions, a fail-closed **action guard** ensures unauthorized behavior is blocked by default.

### 4.6 Neuroscience anchors, summarized

| Mechanism | Neuroscience / cognitive-science basis |
|---|---|
| Fast/slow dual systems, consolidation lifecycle | Complementary Learning Systems (McClelland et al., 1995); episodic/semantic memory (Tulving, 1985) |
| Prioritized replay | Hippocampal sharp-wave ripples (Buzsáki); prioritized experience replay (Schaul et al., 2015; Mattar & Daw, 2018) |
| Adaptive forgetting | Ebbinghaus forgetting curve; active forgetting (Anderson) |
| Pattern separation / completion | Dentate-gyrus sparse coding / CA3 autoassociation (Yassa & Stark, 2011) |
| No-overwrite reconsolidation | The plastic window of reconsolidation (Nader et al., 2000) |
| Salience modulation | Amygdalar modulation of emotional-memory consolidation (McGaugh, 2004); mood-congruent recall (Bower, 1981) |
| Goal-reconstructed retrieval | Self-Memory System (Conway & Pleydell-Pearce, 2000) |
| Prospective memory | Multiprocess framework (McDaniel & Einstein); intention-superiority (Goschke & Kuhl) |
| Social-relation modeling | Four elementary forms of sociality (Fiske, 1992) |

---

## 5 High-Order Belief Reasoning: An Empirical Study

This section tests the central thesis empirically: does encoding the structure of social cognition into memory improve higher-order belief reasoning? We report gains, and characterize their boundary with equal rigor — the latter being itself a finding.

### 5.1 Research questions and method

We ask three questions. **(Q1)** Can deterministic nested-tracking structure improve a model on higher-order mentalizing tasks? **(Q2)** If so, how is the gain distributed across reasoning orders? **(Q3)** Under what conditions does it hold, vanish, or reverse?

To isolate "the contribution of memory structure," we adopt a **same-model-in-the-loop** paradigm: one LLM both extracts memory from a story and answers the question; Starling sits between, injecting the extracted structured mental state as scaffolding. Because the answerer and the extractor are the *same* model, this paradigm directly measures whether structured memory *helped the model itself*, rather than swapping in a stronger solver. As controls, we add a "bare model" (no injection) and a "machine-only" mode (the deterministic operators answer directly, isolating the memory mechanism). Evaluation spans HiToM (zero- to fourth-order nested false belief), ToMBench (eight social-cognition abilities), and commitment-fulfillment and long-horizon tasks; significance is estimated by item-matched paired tests. Models range from a 14-billion-parameter model (zing-14b) to stronger reasoning models.

### 5.2 Principal finding: the order-dependence of the gain

We evaluate the same mechanism on two models of differing strength: a 14-billion-parameter model reinforcement-tuned for reasoning (zing-14b, trained on Qwen3-14B — our cleanest measurement, a same-day paired run with zero extraction failure on both arms) and a stronger reasoning model (deepseek-v4-pro). In both cases, injecting Starling's nested tracking raises overall HiToM accuracy (zing-14b: 0.793 → 0.834, +4.2 points, paired p ≈ 2×10⁻⁵; deepseek: 0.751 → 0.803, +5.2 points). But the aggregate hides a more meaningful structure — **for both models the gain is monotonically concentrated at the deepest reasoning orders**:

| Order | zing-14b — base → +Starling (Δ) | deepseek-v4-pro — base → +Starling (Δ) |
|---|---|---|
| 0 (fact) | 1.000 → 1.000 (0.0) | 0.992 → 0.933 (−5.8) |
| 1 | 0.913 → 0.925 (+1.3) | 0.958 → 0.921 (−3.8) |
| 2 | 0.729 → 0.733 (+0.4) | 0.675 → 0.733 (+5.8) |
| **3** | 0.663 → **0.771** (**+10.8**) | 0.588 → **0.746** (**+15.8**) |
| **4** | 0.658 → **0.742** (**+8.3**) | 0.542 → **0.679** (**+13.8**) |

This distribution answers Q1 and Q2 for both models: the gain is real, and it appears exactly where each model's own reasoning begins to fail. Orders 0–1 carry no gain — the models are already competent there, and the injection is best gated off; only when nesting deepens beyond what working memory sustains does deterministic co-witness tracking pay off.

The *comparison between the two models* is itself informative. The larger deep-order deltas for deepseek (+15.8 / +13.8 vs. zing-14b's +10.8 / +8.3) do **not** indicate that structure helps stronger models more; they reflect a **lower untutored baseline** — deepseek degrades more steeply with depth (order-4 at 0.542) than the reasoning-tuned zing-14b (0.658), leaving more room to recover. Tellingly, *after* injection the two models converge toward a common deep-order band (order-3 ≈ 0.75 for both; order-4 in 0.68–0.74), because that band is set largely by the deterministic tracker's own accuracy rather than by the base model — Starling supplies a near model-independent floor for deep-order tracking. The two diverge only at the shallow end, where the stronger deepseek is near-ceiling (order-0/1 ≈ 0.95–0.99) and the scaffold can only add noise (−5.8 / −3.8) — a divergence partly confounded, since the deepseek arms, unlike zing-14b's, were not same-day paired. (The deepseek baseline here is a clean run with zero extraction failure; the widely-cited +6.4-point figure uses an earlier, fallback-depleted baseline, and against clean baselines the overall lift is +5.2 to +5.7 points, while the deep-order lift is robust across every baseline choice: +14 to +18 points at orders 3–4.)

What underwrites the gain are three generalizable mechanism refinements, all within the perception-grounded representation of §3.3(b): **room-scope awareness** (a subject who has left is no longer mistaken for having witnessed moves elsewhere), **observation/hearsay separation** (firsthand observation is primary; telling and lies only fill gaps), and a **competence gate** (inject only at order ≥ 2, avoiding interference where the model is already competent). Notably, none of these is a benchmark-specific special case; each is a faithful realization of the principle "false belief is perceptual access."

### 5.3 The boundary: when deterministic structure helps

The answer to Q3 is the most scientifically interesting part of the study. We find a simple criterion governs everything:

> **Deterministic structure yields a net gain iff it is more accurate than the model's free reasoning on the task** (det_acc > cot_acc).

Because the same model walks both paths in the in-loop paradigm, injection helps only when the deterministic operator captures multi-step mechanical tracking (deep co-witness intersection) that the model's reasoning drops. That regime is narrow. We delimit its boundary across benchmarks and report failures candidly:

- **On shallow / flat tasks, the gain vanishes.** In end-to-end ToMBench evaluation, injection is statistically indistinguishable from baseline (flat overall). A strong model already reads first-order beliefs, desires, and intentions straight from the story; the deterministic scaffold is redundant.
- **Beware "gains" that are artifacts.** A +9.2-point gain observed on one common-knowledge subtask proved, on inspection, to be a **definitional artifact**: the gold answers happened to adopt our operator's own co-witness definition, so injection merely overrode the model's more conservative reading; on a harder variant whose gold does not favor the operator, the gain falls to non-significance.
- **On out-of-distribution narratives, injection hurts.** On literary, Chinese-language, or scaffold-restructured narratives, extraction degrades under complex prose, the downstream machinery miscomputes, and the net effect is −9 to −20 points.

Together these boundaries support a conclusion that is unsurprising yet often evaded: **when the augmented model is already strong, it is itself an excellent belief tracker**; the value of deterministic structure lies not in "making the model reason better" but in "tracking for it within the narrow seam where its mechanical tracking fails." The HiToM gain is, in essence, the *enforcement of conventions* on an under-specified benchmark (making room-scope and observation-primacy explicit), not a lift in reasoning capability. We therefore stop at the generalizable ceiling, declining to chase higher fitted scores by reverse-engineering the benchmark's generator.

### 5.4 From boundary to deployable safety

Since the helpful regime is narrow and the harmful regime is real, deploying deterministic injection unconditionally is not robust. We therefore introduce a **semantic-routing gate**: a lightweight discriminator decides whether a question falls within deterministic structure's helpful regime, injecting only when it does. The gate pulls the worst-case degradation of indiscriminate injection on out-of-distribution narratives from −9 points to −0.7 points (near-neutral), converting the system from "sometimes hurts" to "helps or at least does no harm." This is a falsifiable, deployable design distilled from an honest negative result — and it echoes our overall methodology: treat memory structure as a *conditional* augmentation, not an unconditional panacea.

> **On evidence levels.** This section's HiToM per-order results and ToMBench tables come from controlled, reproducible eval artifacts; the magnitudes for out-of-distribution narratives (literary, cross-lingual, scaffolded) and some paired p-values come from exploratory runs and are reported as directional, not primary. All "gains" presume the same-model-in-the-loop setting and measure the marginal contribution of memory structure to that model.

---

## 6 An Illustrative Scenario

Suppose Alice announces in a group chat: "Bob is no longer on auth; Carol takes over." This one utterance exercises all three pillars at once. **At the representational layer**, the system extracts several perspectival statements: that self believes Bob is no longer responsible and Carol now is; a second-order belief — that self believes *Alice believes* Carol is now responsible; and a statement held by Alice (she asserts Bob is no longer responsible). The old "Bob owns auth" statement severely contradicts the new information, so reconsolidation triggers: a new version is forked and the old is archived and linked by supersession rather than deleted — the history "Bob owned it for ~8 months" is preserved for later reference.

When the user later asks "Is Bob still on auth?", the **retrieval layer** follows the supersession chain to the current fact, attaches the evidence span of Alice's original words, and checks whether this is yet common ground with the user — if not, it proactively notes "this is the first time I'm telling you." And when asked "Does Bob know this?", the **social-cognition layer** does not retrieve a record but queries Bob's knowledge frontier: if he was absent from the announcement and has no other visible path to learn it, the system judges that he *does not yet know*, and accordingly suggests syncing it to him. That "Bob doesn't know" judgment is exactly the epistemic distinction a subject-less vector store cannot express and an attribution-first representation yields naturally.

---

## 7 Related Work

**Theory of Mind and LLMs.** A line of work probes LLM social reasoning with false-belief tasks (ToMBench, HiToM, FanToM) and reveals fragility under perturbation and depth (Ullman, 2023; Shapira et al., 2024). The dominant improvements push on the reasoning side — stronger prompts, process rewards, adversarial and trajectory-level training. Starling is complementary and orthogonal: it does not train the model but supplies a deterministic, auditable memory substrate that makes social structure explicit; and our evaluation (§5) precisely delimits the regime where this structure augments a strong reasoning model versus where it is redundant or harmful.

**Agent memory and cognitive architectures.** Mainstream stacks (mem0, Letta, cognee, Graphiti/Zep) are capable at fact retention but take subject-less facts as their ontology and isolation keys for multi-user separation. Starling differs at the ontological layer: it replaces the subject-less fact with a perspectival, nestable, lifecycle-bearing *belief*, and can thus express what these systems structurally cannot — recursive mentalizing, knowledge frontiers, common-ground closure, perspective-aware abstention. It does not replace them but layers atop them as cognitive middleware. Earlier symbolic cognitive architectures (e.g. ACT-R's declarative memory, computational CLS models) are an intellectual lineage for this work; Starling can be read as an engineering synthesis that lands these classic ideas — with modern LLM extraction as the front end and an auditable graph as the substrate — in the new setting of agent memory.

---

## 8 Limitations and Outlook

We close on an honest characterization of boundaries, both as scientific discipline and in the diagnostic spirit of §5.

- **The helpful regime is narrow.** Deterministic structure is robustly helpful only on deep nested tracking; its generalization to broader social-cognition tasks is mostly neutral or harmful. The semantic-routing gate converts this risk into "helps or does no harm," but does not widen the helpful regime itself — an open research question.
- **Strong dependence on extraction quality.** The entire social-cognition machine takes extraction output as input; a weak model or out-of-distribution prose degrades it at the extraction seam. Improving extraction robustness (especially on literary and cross-lingual text) is a prerequisite for unlocking this representation's potential.
- **Several brain-like mechanisms are not yet fully instantiated.** Content-driven affective appraisal and more complete prospective action execution are, at present, more design than implementation. We label maturity honestly and do not overclaim.
- **Privacy–mentalizing tension.** The system holds sensitive metadata like "A thinks B doesn't know X," whose safety depends on perspective masking running early in retrieval and being non-bypassable — a safety boundary requiring continued audit.
- **Statistical power.** Some conclusions rest on moderate-scale paired experiments; larger-scale replication across more model families is future work.

Looking ahead, we see the most promising direction as generalizing "memory structure as a conditional augmentation" from higher-order ToM to broader social reasoning (responsibility attribution, normative conflict, trust propagation), and exploring finer-grained synergy between representational structure and model reasoning.

---

## 9 Conclusion

This report argues a position and supports it with a system and an empirical study: **Theory of Mind is first a problem of representation, and memory is first a dynamical system.** When the structure of social cognition — attribution, perspective, recursive belief, common ground, perceptual access — is encoded into the memory substrate, higher-order mentalizing turns from a brittle inference into an auditable query; and when memory is endowed with brain-like dynamics of consolidation, forgetting, reconsolidation, and prospection, it turns from a static store into a cognitive organ that evolves with goals and time. Our gains on higher-order nested benchmarks — whose monotonic concentration at the deepest orders is itself instructive — together with our precise characterization of *when* deterministic structure helps, suggest that making social cognition an auditable data structure and dynamics, rather than a prompt-layer patch, offers a clear, falsifiable, and honest direction for the memory systems behind long-horizon human-AI collaboration.

---

## References (selected)

- Wimmer, H., & Perner, J. (1983). *Beliefs about beliefs: Representation and constraining function of wrong beliefs in young children's understanding of deception.* Cognition.
- McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). *Why there are complementary learning systems in the hippocampus and neocortex.* Psychological Review.
- Tulving, E. (1985). *Memory and consciousness.* Canadian Psychology.
- Conway, M. A., & Pleydell-Pearce, C. W. (2000). *The construction of autobiographical memories in the self-memory system.* Psychological Review.
- Nader, K., Schafe, G. E., & LeDoux, J. E. (2000). *Fear memories require protein synthesis in the amygdala for reconsolidation after retrieval.* Nature.
- Yassa, M. A., & Stark, C. E. L. (2011). *Pattern separation in the hippocampus.* Trends in Neurosciences.
- McGaugh, J. L. (2004). *The amygdala modulates the consolidation of memories of emotionally arousing experiences.* Annual Review of Neuroscience.
- Bower, G. H. (1981). *Mood and memory.* American Psychologist.
- Mattar, M. G., & Daw, N. D. (2018). *Prioritized memory access explains planning and hippocampal replay.* Nature Neuroscience.
- Schaul, T., Quan, J., Antonoglou, I., & Silver, D. (2015). *Prioritized Experience Replay.* arXiv:1511.05952.
- McDaniel, M. A., & Einstein, G. O. (2000). *Strategic and automatic processes in prospective memory retrieval: a multiprocess framework.* Applied Cognitive Psychology.
- Goschke, T., & Kuhl, J. (1993). *Representation of intentions: Persisting activation in memory.* Journal of Experimental Psychology.
- Fiske, A. P. (1992). *The four elementary forms of sociality.* Psychological Review.
- Ullman, T. (2023). *Large language models fail on trivial alterations to theory-of-mind tasks.* arXiv:2302.08399.
- Shapira, N., et al. (2024). *Clever Hans or neural theory of mind? Stress testing social reasoning in large language models.* EACL.
- Chen, Z., et al. (2024). *ToMBench: Benchmarking Theory of Mind in Large Language Models.* ACL.
- He, Y., et al. (2023). *HI-TOM: A benchmark for evaluating higher-order theory of mind reasoning in large language models.* EMNLP Findings.
- Kim, H., et al. (2023). *FANToM: A benchmark for stress-testing machine theory of mind in interactions.* EMNLP.

## 2026-09-11 Source-grounded claim contract

The approved optional claim contract is implemented in C++; language bindings map types/configuration and forward native calls. Full build, 1273 Python tests (15 skipped), 1025 C++ tests and independent review are complete. The real diagnostic completed with errors on 2026-09-12; 140 native ingestion replays and 144 databases verified.

Fixed controls scored 59/64. Strict synthetic sufficiency changed from 13/16 to 9/16, including identical-prompt judge disagreement and a technical failure. P1 base semantics were preserved but combined metrics declined. Selected source excerpts helped Q1 (2/3 votes); Q9 linked/full answers were unavailable after SSL transport failures. Overall accuracy improvement and production readiness are not established; defaults remain off. See the [design synchronization inventory](design/claim_contract_sync.md) and [diagnostic report](eval/2026-09-11-socialmem-claim-contract.md). These results remain separate from the historical benchmarks above.

## 2026-09-12 可空主题与情绪误拒后续修复

原生解析器修复可空主题与部分中文情绪误拒；新增裁判一致率和有效语义分母。C++ 1,033 项测试（含本地 HTTP 补跑）及 Python 1,278 项测试通过，离线 140 次原生重放/144 个数据库核验通过。真实诊断已在新目录核验为 `verified / complete_with_errors`：原生技术失败 8 个，固定对照 59/64、synthetic 契约组 8/16（冻结组 12/16），P1 combined 仍低于 base；Q1/Q9 的前三臂均为 0/3、full 为 3/3。质量门槛未通过，结果入口为 [中文修复报告](eval/2026-09-12-socialmem-repair.md)。此前整体设计“全部完成”的描述需要收窄：结构化输出能力声明、完整扩展标签和来源时间输入尚未交付。历史分数不改写，生产默认关闭。

## JSON mode 本轮验证状态（2026-09-12）

C++ 1,041 项、Python 1,282 项测试通过（Python 15 项跳过），离线 140 记录/144 数据库核验通过。独立审查发现的中文尾随文本错误回执已用 C++ 修复，原文及技术失败状态保持；服务端最小探测接受参数但未严格输出裸 JSON。140 条真实诊断已完成并核验；最新中文边界结果见 JSON mode 报告。完整证据见 [中文 JSON mode 报告](eval/2026-09-12-socialmem-json-mode.md)。完整 schema、能力协商、扩展标签与时间输入继续列为未完成。


## 中文边界真实评测结论（2026-09-12）

`build/socialmem_20260912_chinese_unicode_real/` 已核验 `verified / complete_with_errors`。固定候选 56/64，synthetic 冻结 10/16、契约 8/16，P1 combined holder/perspective/predicate-object F1 为 0.7101/0.6627/0.7456，原生技术失败 8；契约裁判两两一致率 100%。中文职责/情绪混合句误拒已消除，但固定与 P1 下降，不能宣称整体质量提升或生产就绪；Unicode 规则已由 C++ 回归覆盖，当前 cohort 未含对应固定样本。


## 来源时间与独立扩展标签（2026-09-12）

按已批准优化范围执行 [中文来源话轮设计](superpowers/specs/2026-09-12-source-turn-evaluation-design.md)。C++ 生成并解析版本化话轮，保留原始消息时间与 UTF-8 来源位置，正文与元数据分开校验；Bus/检索重建 source_turn 防止篡改。Python 仅映射和统计，独立扩展标签不进入模型输入，不修改原 P1 金标。真实时间不推断为事件时间或 UTC；已完成 C++ 实现、全量测试、离线与真实核验；真实诊断为 verified / complete_with_errors，质量门槛未通过。普通正文冒号保留完整语义，直接写入/回读使用共享严格解析器拒绝嵌套重复键。详见 [来源话轮评测报告](eval/2026-09-12-socialmem-source-turn.md)。


## 生成契约完整性同步（2026-09-12）

按 [中文生成契约设计](superpowers/specs/2026-09-12-claim-generation-design.md)，C++ 在抽取提示中明确对象、逐字主题、原始时间限定和字段类型约束，并提供与本次来源隔离的通用中英文参考示例。模型输出校验、准入、存储/检索与默认开关保持既有约束，Python 仅绑定和评测编排；参考示例不作为当前证据。本轮 C++ 实现、完整回归、离线核验及历史响应 140/140 一致性重放已完成；真实诊断于北京时间 2026-09-13 完成核验，为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、独立对象 12/14、主题/联合各 1/14，原生技术失败 5；主题字面匹配分数不能解释为字段缺失。P1 兼容与逐例不退步门槛仍失败，Q1/Q9 结构化及链接组仍为 0/3，默认关闭。详见 [生成契约评测报告](eval/2026-09-12-socialmem-generation.md)。其他专项职责沿用设计同步清单，历史快照保持。

## 输出协议与偏好边界同步（2026-09-13）

按 [中文修复设计](superpowers/specs/2026-09-13-claim-protocol-boundary-design.md) 继续已批准优化：C++ 提示强调键唯一、时间原文及同话轮引用，准入与解析共用合法原因目录，窄范围拒绝把明确偏好对象写成 feels。真情绪不因同源其他偏好句被拒；Bus/回读复用共享契约，Python 仅绑定与编排。当前已完成 RED、C++ 实现与复审修复后的完整回归（C++ 1,062 项，Python 1,319 项通过/15 项跳过）；旧响应重解析 137/140 一致，3 条偏好误标候选提前拒绝。复合/因果情绪及被动 preferred 感受保留准入，句尾标点边界有正反例覆盖。独立复审发现均已关闭，最终离线 140 条/144 数据库核验通过；真实诊断已核验为 `verified / complete_with_errors`，140 条重放/144 个数据库、10 条原生技术失败、固定候选 56/64、synthetic 契约 11/16；质量门槛未通过，默认关闭。详见[最终报告](eval/2026-09-13-socialmem-protocol-boundary.md)。

## 声明范围与覆盖诊断职责（2026-09-15）

采用 C++ 受限句首定位缓解整话轮问号误拒，并提供原始行到候选的诊断索引。该工作已实现并通过本地回归，不改变历史基准分数；真实语义质量、完整状态召回和生产默认仍未通过后继验收。

详见[声明范围定位与生成覆盖诊断设计](superpowers/specs/2026-09-15-claim-scope-localization-design.md)。

## 2026-09-17 独立来源与观察者检索

新增C++来源保留接口经既有Bus写入Engram，0035的source_documents只登记tenant/holder/Engram及首次登记时间，不复制正文。旧来源不猜测owner回填。宿主提供显式授权holder，核心执行范围、擦除、保留策略、完整性哈希与时间截止过滤；SourceTurn保留说话人、来源时间和会话/话轮身份，未经声明抽取也可独立召回。

ObserverRetriever将跨holder声明融合收进C++，并提供statements/sources/hybrid三种显式模式，统一去重、整行UTF-8字节预算和原生渲染；sources当前是确定性BM25，hybrid交替来源与声明。旧默认路径不变，新路径不会扫描整个租户来扩大权限。来源以SOURCE标记原始发言，不自动变成已认证事实；时间表示来源时间，不推断事件发生时间。Python和其他binding只转发接口。

设计、验收和本轮开发评测状态见[独立来源专项](superpowers/specs/2026-09-17-socialmem-independent-source-design.md)。现有39项原生与53项Python聚焦回归通过；两轮6题四臂已终态，回答关闭思考后声明/来源/融合/全文为1/6、2/6、2/6、3/6，零技术失败。1031题原始来源模式全量复测已完成，201题正确（19.50%），1007题成功评分、24题来源失败；其后的57题姓名词项候选未晋升。


## 2026-09-17 来源可靠性与上下文回执更新

C++在认证与时间过滤之后、BM25统计之前按可靠话轮身份及原文/来源时间去掉增量批次重复候选；缺身份或不同内容版本保留。登记与查询截止要求明确合法UTC时间，原始来源观察时间不改写。SOURCE模型输入保留说话人、观察时间、会话和位置及转义正文；完整Engram/clause/turn身份保留在按行对应的source_refs回执，避免把内部标识重复占用模型上下文。k=30/8000字节仅在显式开发候选配置测试，未切换旧默认记忆路径。实测与边界见[候选报告](eval/2026-09-17-source-context-density.md)。

## 显式人物来源检索契约（2026-09-17）

ObserverQuery新增source_strategy，默认bm25；focused与focused_window仅适用于sources模式。C++在授权/时间/擦除/哈希过滤后完成完整姓名匹配、人物队列轮转、全局证据及同会话±1话轮扩展，共享k与UTF-8字节预算；按原时间与数值话轮顺序渲染并保持引用对齐。无人物匹配时复用旧BM25输出。Python只映射字段和编排实验。已完成本轮开发及保留集验证，默认保持bm25；完整算法与验收以本文件顶部当前报告及其设计链接为准。

## 2026-09-18 原生两阶段证据回答边界

新增`evidence_answer.hpp/.cpp`提供`source_evidence_prompt`、`verify_source_evidence`、`evidence_answer_prompt`及`answer_with_evidence`。输入仅为已授权召回的SOURCE块及问题；C++为来源分配局部编号，发起证据选择，核验source_id、实际发言人与连续原文引语，再以完整原来源和通过引用核验的证据生成答案。Python绑定只暴露DTO和原生调用，评测脚本只负责路由、三阶段回执与预算结算。

该能力只认证引语与来源匹配，`interpretation`仍为未验证模型解释；不能把被描述主体、时间顺序或因果关系当成已经获得语义认证。未新增持久化事实、推断谓词或隐式授权，也没有将`select_temporal_evidence`的有序早晚声明视为因果验证。规划失败按固定策略回到原grounded提示，保留失败与成本记录；适配器异常标记未知预算，并按上界结算。

`evidence_v1`为显式实验政策，sources自由回答最多增加一次模型调用；默认legacy及选择题原协议保持。工程契约和733题真实开发评测均已完成：313/733＝42.70%，相对同1024容量父下降4.37个百分点，未晋升。实验设计和诊断见文档首部；引用来源核验不表示社会语义推断已验证。

## 两阶段证据回答验收结论（2026-09-18）

C++实现和733开发题真实评测完成：313/733＝42.70%，相对同1024容量父345/733净减32题（−4.37个百分点），33网络95%差值区间[−7.89,−0.86]个百分点；自由题236→203/581。观测tokens5,397,777（+69.46%），1894 HTTP，24裁判超时和1回答截断全计零，4次规划降级。预注册五项仅截断与观测用量通过，拒绝晋升；通过门槛的推荐配置仍为grounded_v1/512，默认legacy不变。

引用核验成功不表示解释正确：本轮2631条合格引语、115条不连续引用被拒；双方技术正常690题仍净减26题，不能仅用超时解释下降。固定案例暴露目标事件和时间错配、双向互动链遗漏；后续优先验证C++事件指向、主体归属与回应关系，先文档、再独立测试、最后实现，不追加本轮候选搜索。全部模型请求已结束，主评分保持原协议；保存的模型响应驱动581最终提示原生回放一致。完整诊断见本轮评测报告。

## 2026-09-18 连续话轮扩展接口

ObserverQuery新增focused_dialogue策略及source_seed_k、source_seed_max_context_bytes、source_dialogue_radius三个参数。C++在既有权限/时间/完整性过滤后复用focused_window选种子，再加入同会话、连续位置的原文；预算先保障种子，邻接不等于已验证的回复或因果边。Python仅暴露字段与透传配置。其他策略维持原行为。

本轮固定30条/8000字节种子、半径2、总60条/16000字节，grounded_v1/1024，无额外模型规划。新增原生14项与实际绑定3项已通过；733题旧路径兼容、真实准确率及成本仍待冻结评测。与容量父比较同时改变组织和容量，不声称等预算的单因素收益。

本接口开发验收：旧focused_window的733份block/refs/prompt全部逐字复现，focused_dialogue的733份实际来源完整保留原种子；39来源库不变。真实成绩376/733，相对345净增31，观测tokens+52.21%，未达到净增37的预注册门槛，因此不作为推荐默认。剩余主要限制是问题范围、时序、冲突陈述和答案覆盖；邻接仅提供来源上下文，不证明因果。原生54项、新Python31项、既有回归42项及封存辅助10项通过。完整结果见本页顶部链接。


## 单次综合回答接口（2026-09-18）

C++在evidence_answer.hpp/.cpp提供synthesis_source_answer_packet与synthesis_source_answer_prompt，复用来源解析器，将已授权的原生SOURCE块转换为synthesis_v1证据包。保留来源顺序、说话人、会话、话轮、陈述时间、未知时间元数据及原文；source_id是包内位置，text是正文保留字段，输入元数据不得占用这两个名称；空白说话人与损坏来源在请求前拒绝。证据包不是权限过滤器，也不补写事件时间或认证答案语义，semantic_verified始终为false。

新提示引导单次模型回答注意问题范围、事件时序、实际触发、回应与反证、推断强度和多成员覆盖；规则没有实现自动语义校验。Python仅暴露接口和路由；synthesis_v1只允许sources召回，自由题一次回答、至多一次原裁判，选择题保持旧提示。旧政策与推荐默认不变。本轮固定上一轮733题来源和1024回答容量，仅证据表示与生成政策改变；输入token数可能因表示而变化，真实效果见本节终态验证及文档首部报告。

单次综合回答终态验证：61项原生、37项新Python、22项旧政策、27项基线与账本、10项封存辅助测试通过。733题预检来源相同，581证据包无损，152选择题提示不变；实际可用上下文733题、证据包581题、选择题提示152题完成核验。真实成绩309/733，较376净增-67，观测tokens为4,857,066；未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。此结果只评估固定开发集单次生成政策，不证明已实现问题范围、时序、关系或因果的自动语义校验。

本轮成本口径补充：回答显式关闭thinking，裁判沿用旧协议且未显式设置此参数；原始HTTP usage中裁判有821,168个reasoning_tokens。judge_max_tokens=64不是观测总completion tokens的上限。后续若修改裁判配置须作为独立实验，不混入当前配对成绩。

## 2026-09-18 回答表示与指导消融设计

已新增C++显式实验接口source_answer_ablation_prompt，组合SOURCE/JSON表示与grounded/synthesis指导。两个历史对角提示逐字兼容，Python仅绑定和实验编排；模型qwen3.8-27b、固定来源、1024回答上限、原裁判不变。按33开发网络各3题抽样，99题四组合、上限792次请求，结果仅作机制诊断，不晋升。来源包保真不等于人物归属、因果或社会推断已验证。详见本文件顶部本轮报告。

## 2026-09-19 回答消融结果与结构化能力边界

99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。 五项配对区间均包含0，没有达到完整开发集验证条件的方向。C++已提供显式source_answer_ablation_prompt，两个历史对角提示逐字复现，Python只做绑定和实验编排；默认推荐未改。39个来源库的statements与非空semantic_claim_json均为0，本轮不检验结构化抽取/记忆闭环。

事后原文核对确认关键发言漏召回、人物归属错误及否认未约束推断；部分原裁判YES也包含错误归属。跨时段重复中另有3例相同答案与相同裁判提示标签翻转，不能当作总体误判率或修改主评分。下一阶段先用独立用例诊断召回选择，再复用现有claim_contract、claim_evidence、temporal_evidence，单独验收抽取→校验→写入→检索→回答；这些后续改动尚未执行。来源/字段完整性不认证人物归属或因果语义，补充契约的五类关系不代表全量谓词。评分稳定性校准须独立记录，不与旧主分数混比。

## 2026-09-19 人物与会话覆盖检索设计

显式focused_coverage候选已在既有来源过滤及focused_window种子后，用剩余条数与字节预算的一半按人物/会话轮转补充本人发言，再围绕原种子扩展；保持整行原文、总预算和授权范围。选择与trace均由C++实现，Python只绑定和实验编排。C++与99题同期对照已完成；99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。结构化记忆闭环和裁判校准仍待独立验证。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 已完成离线、真实复评和最终封存核验，详见[中文诊断报告](eval/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.6 原结果保留；本轮检索 19/57、原生回答 17/57，涨分尚不能归因于代码修复，不晋升。

<!-- r53-evaluation-boundary:start -->

## R5.3 实现、真实检索与历史归因边界（2026-09-25）

R5.3 的 `evidence_profile_v8` 已在 C++ 实现来源独立预算与声明附加区：先按 k 选择来源，再从剩余字节预算中追加最多 3 条、能够回链到已选来源且通过相关性和证据约束的声明。来源与声明分别计数和记录字节，Python 只负责绑定、编排及统计。产品默认仍为 `bm25`，开发对照为 `v6`。

R5.1 的 v6 共 345 次嵌入尝试全部进入降级路径，v7 无此降级；R5.2 复用这些冻结上下文进行回答与裁判。因此，R5.2 历史得分保留，但检索健康状态存在混杂，不能将主要退化或全部退化归因于来源与声明共享名额。C++ 中 v7 将来源上限压为 7 再加入 3 条声明的机制已确认，该机制证据不等于其对问答分数的独立因果效应。

R5.3 本轮同库真实语义检索的三臂均健康、来源控制一致，但 v8 来源锚点低于 v6，门槛未通过，未启动新鲜回答与裁判评测，不晋升。检索请求成本、逐题证据、声明附加区诊断及冻结核心与后续修复的区别，以 [R5.3 中文评测报告](eval/2026-09-25-socialmem-r53-source-sidecar.md) 为准；完整合同见 [R5.3 中文设计](superpowers/specs/2026-09-25-socialmem-r53-source-sidecar-design.md)。

<!-- r53-evaluation-boundary:end -->

## R5.4 来源预算与有效期合同（2026-09-25）

实验策略 `evidence_profile_v9` 在 C++ 复用 v6 的来源选择顺序和 v8 的独立来源预算/严格 sidecar 准入；不启用 v8 的直接命中优先排序，也不启用 v7/v8 的 semantic/event 来源排序。`k` 只约束来源，先渲染来源，再按共同 UTF-8 字节预算追加最多三条声明，不能挤掉来源。v9 `sources` 不调用 planner/embedding，v9 `hybrid` 才查询声明候选。Python 仅透传和编排，不复制这些决策。

语义 planner 和 source claim metadata 的声明有效期统一为 `[valid_from, valid_to)`，NULL/空界无界；复用既有结构化资格过滤并保持 semantic DTO、cosine 及 salience/activation/provenance，不用 observed_at 推断有效期。原行为兼容仅针对合法时间数据，未来/过期声明的旧准入属于已修复漏洞。

同核心57题四臂检索完成：baseline/source7锚点51/104，source10/sidecar为67/104，228条回执全健康；两对来源控制逐题一致，source10无声明且无嵌入请求。source10通过预注册QA门槛，问答结论以当前R5.4评测报告为准。没有声明时相关性指标“不适用”；sidecar仍为诊断臂。fresh QA只比较baseline/source10的组合效果，不把锚点增量当作答题增量，不更改产品默认。

## R5.6 原生分批声明抽取补记（2026-09-25）

新增候选能力 `ValidationPolicy.claim_batch_size`：默认0保留原行为，1至32仅用于semantic claim，当前实验为8。C++用完整payload规划互斥的全局来源单元批，每批保留全部上下文；模型只能输出目标clause，原生在语义过滤前拒绝越界行。证据的原始字节坐标、来源hash及SourceTurn身份保持，不把批号写入声明身份。Python配置仅映射该字段；general_fact派生policy清零，episodic独立。

原生 `claim_extraction_batch_plan(payload, policy)` 给出计划与请求上界；分批回执保留全局attempt编号、batch_index、target_clause_ids和 `claim_batches_complete`。全部批成功才允许该holder分批claim写入；后批失败保留全部原始回执与成本，0条分批claim落库。持久化重新验证计划、policy与候选来源，批间写异常由事务回滚；跨分批大小重放保持幂等。完整上下文重复输入增加成本，有限来源单元不等于token硬上限。

本轮本地验证已通过，真实同输入验收与扩大评测尚待完成；不把测试结果当QA增益。完整设计与当前证据见[R5.6中文设计](superpowers/specs/2026-09-25-socialmem-r56-bounded-claim-design.md)，历史评测继续按各自冻结核心解释。

## R6.7 原生语义来源选择与评测边界（2026-09-26）

新增独立实验模块 `include/starling/retrieval/source_selection.hpp` 和 `src/retrieval/source_selection.cpp`。`collect_selection_pool(observer, query)` 复制查询，以sources/bm25收集经租户、holder、时间、保留和擦除策略过滤的来源，最多1000条、131072字节；`eligible_sources`必须与池实际条数相同，溢出或不完整池显式失败。C++按观察时间、会话、turn_index和稳定身份排序，未知时间置后。模型输入只含问题、来源编号、原文、speaker/session/time及预算，不包含标准答案、题型或公开锚点。

`source_selection_prompt`生成选择提示词，`select_sources`最多进行一次原生LLM调用，`apply_source_selection`验证并渲染回执。模型仅提议整数`source_ids`；C++拒绝额外字段、重复键/编号、未知编号、布尔/浮点编号、超过20条或8000 UTF-8字节的计划。来源整行、归属和引用保真，按原池时序呈现，不截断、不补齐、不回退。空池零调用；模型失败或异常保留原始响应和费用不确定性。纯回放接口消费已授权池，不是新的授权入口。

这些规则只在C++实现，Python绑定仅透传；Python评测层负责快照、任务调度、started回执、HTTP账本、冻结和统计。选择核心与历史回答/审计核心在不同进程使用。候选无声明附加区，不证明谓词、人物状态或因果关系能力已被补齐，也不改变默认检索路径。

R6.7已完成文档、RED、实现及评测：13项新增原生反例包含在1389项完整C++回归中，12项binding、14项选择编排和16项QA编排测试通过。同八库、六网络、133题来源选择129题成功，锚点194→205/263。同期v9→selector正确50→56/133（37.59%→42.11%，+4.51个百分点），聚类95%区间[-4.58,17.17]；正常130→125/133。共同正常123题正确49→55。增益、区间和健康门槛未全部满足，未晋升；不是全量、保留集或生产结论。

本轮已证实尚未修复的边界：`OpenAIAdapter::generate()`调用`complete(prompt,false)`，选择工厂设置的`json_object_output`不会在此路径启用结构化输出。四次选择合同失败按完整分母计错；下一轮须在C++修复真实调用路径并测试HTTP请求体，不能在Python剥除围栏后事后修分。群体反例丢失、变化事件直接行为被压缩、回答遗漏已有证据分别进入后续设计；格式修复本身不等于质量晋升。

真实调用共602/611 HTTP、零重试、零新增embedding；已知tokens为3,679,744，7次QA超时缺用量，总消费未知，账本无未结算预约。候选读取完整池的额外选择开销必须计入收益评估。详细数据、逐题机制及复现入口见[本轮中文诊断报告](eval/2026-09-26-socialmem-r67-source-selection.md)。

## R6.8 显式结构化来源选择合同（2026-09-26）

新增C++ `select_sources_structured(question,pool,llm,k,max_context_bytes)`，显式传递`SourceSelectionV1/JsonObject`至已有`extract_with_contract`路径，实际HTTP体含`response_format.type=json_object`。SourceSelectionV1限定唯一键source_ids及最多20个互异正整数；池内编号与UTF-8动态预算继续由原生apply_source_selection验证。新旧入口共用一个执行器，旧select_sources保留自由生成以支持历史对照，Python只做绑定和实验编排。

新入口核对响应合同、模式、schema哈希和原始内容一致性；不支持、超量、围栏或不健康响应直接失败，不隐式能力探测、不重试或回退。JSON mode只约束传输格式，不能保证来源选择语义正确或满足20条预算。既有显式能力探测API新增空来源列表夹具与可重放证据，真实评测不自动调用它。

本地1395项C++回归、20项绑定/localhost HTTP、14项选择编排和16项QA编排测试通过。R6.8已完成133题结构化来源选择与同期QA：v9为52/133，selector为60/133，净增6.02个百分点；六网络聚类95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升。选择合同失败从R6.7的4题降为3题，均为超过20条预算；Markdown围栏失败为0。来源池、选择提示词、预算及回答政策保持R6.7合同；群体反例、事件角色和裁判规则本轮不改。完整设计见[中文设计](superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)，详细结果见[中文评测报告](eval/2026-09-26-socialmem-r68-structured-selection.md)，历史R6.7原始结果保留。

2026-09-27 收尾审查补充：`S_star`/`S_star_oracle` 只通过 Python binding 调用原生 `observer_holders` 与 `ObserverRetriever(mode="statements")`；holder 枚举、跨holder候选融合、去重、排序、预算和渲染均由 C++ 执行。空库仍返回原生 `[ABSTAIN]` 拒答块；评测编排层规范化查询时间，C++ 校验并回传 `as_of_iso`。本轮最终 C++ 回归为1395项（1372通过、23跳过），当前 native binding 专项59/59通过；历史封存程序对已改写的评测源码报告漂移并拒绝复用，封存结果不重写。
