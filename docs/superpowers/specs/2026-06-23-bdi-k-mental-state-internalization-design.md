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

# BDI+K 心智态内化 (Mental-State Internalization) — 设计 (SP-A)
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> 「把多维社会认知能力内化进 Starling 核心」arc 的第一个子项目。承接 ToMBench 逐家族 gap 分析:Starling 只有 belief 接通了「抽取→查询→注入」三层,Knowledge/Desire/Intention 家族表征底座在、管线没通。

## 1. 动机 (Motivation)

ToMBench 实测(400 样本,Starling-in-loop vs 裸 deepseek):整体 ≈ baseline(81.2 vs 82.5),仅 **Belief 家族 +0.8**;**Knowledge −4.4 / Desire −3.6 / Intention −2.4**。根因不是 Starling 不能表征这些心智态——modality 菜单已含 `BELIEVES/DESIRES/INTENDS/COMMITS`,原语 `what_does_X_believe`/`does_X_know`/`predict_X_would` 俱在——而是**两处管线断裂**:
1. **抽取偏 belief**:`prompts.py` 的 modality 菜单列了 `DESIRES/INTENDS/COMMITS`,但 worked example 几乎全 `believes`/`prefers` → LLM 非信念心智态**抽取率低**。
2. **无聚合查询面**:没有一个「X 的完整心智态」核心能力把已抽的 beliefs/knowledge/desires/intentions/commitments 一次性吐给消费方;Belief 之外的家族拿不到 X 的相关心智内容。

**内化原则(用户裁定)**:能力做进核心(C++),开箱即用;评测 server / OpenClaw / 未来绑定只是瘦消费方,不在外围重实现。

## 2. 目标 / 非目标 (Goals / Non-Goals)

**目标**
- 抽取可靠捕获 **BDI+K**(beliefs / desires / intentions / commitments / knowledge / preferences),不止 beliefs。
- 新增**核心 C++ 聚合** `mental_state_of(X)`:一次调用返回 X 的全部心智态,按 attitude 分组。开箱即用(ToMEval、OpenClaw、未来绑定共享)。
- 瘦消费方(eval server)按家族 gated 注入 `mental_state_of`,验证 Knowledge/Desire/Intention 家族提升。

**非目标 (YAGNI)**
- 不做 `reconcile_desires`(欲望调和)、`detect_faux_pas`(SP-B)、`appraise_emotion`(SP-C)——本 SP 只铺**抽取地基 + 心智态聚合面**。
- 不在 server 写社会认知逻辑(faux-pas/路由/调和)——那违反内化原则。
- 不改 `what_does_X_think`/`what_does_X_believe`/`does_X_know` 本体(加性);不改 canonicalize、perceived_by_json、schema(复用现有 modality/predicate/StatementRow)。

## 3. 已锁决策 (Locked Decisions)

| # | 决策 | 选择 |
|---|---|---|
| D1 | arc 定序 | SP-A 抽取地基先行(B faux-pas / C emotion-appraisal 顺延) |
| D2 | 内化形态 | `mental_state_of` 是**核心 C++ 聚合原语**(`src/tom/`),非 server 路由 |
| D3 | 抽取增强 | prompt 加 DESIRES/INTENDS/knows/prefers worked example(配置数据,加性);抽取机器不改(已支持全 modality) |
| D4 | 消费方 | server 瘦调用 + 按家族 gated 注入(只对 Knowledge/Desire/Intention,不对 emotion/belief-only) |

## 4. 架构 (Architecture) — 两个内化件 + 一个瘦消费方

```
story
 └─ remember() [belief/episodic/general-fact passes]
      belief pass 现可靠抽 BDI+K (组件①,prompt 增强)
 └─ mental_state_of(X)  (组件②,核心 C++ 聚合,新)
      → {beliefs, knowledge, desires, intentions, commitments, preferences}
 └─ server 瘦注入(组件③,gated to Knowledge/Desire/Intention)
      → answerer 读 X 的心智态作答
```

| 组件 | 落点 | 边界 |
|---|---|---|
| ① 抽取增强 | `python/starling/extractor/prompts.py`(配置数据) | prompt=数据;抽取机器=C++(不改) |
| ② `mental_state_of` | `src/tom/mentalizing_profile.cpp`(新)+ `include/starling/tom/mentalizing.hpp`(声明)+ `bindings/python/bind_08_tom.cpp` + `python/starling/tom/primitives.py` | **核心 ToM 逻辑=C++**;绑定/包装瘦转发 |
| ③ 瘦消费 | `scripts/starling_tomeval_server.py` | 评测适配(Python),只调用+格式化 |

## 5. 组件② `mental_state_of(X)` 核心聚合 (C++)

### 5.1 接口

`include/starling/tom/mentalizing.hpp`(在既有结构体附近新增):
```cpp
// X 的完整心智态快照:按 attitude(BDI + 知识/偏好)分组 X 持有(holder_id=x)
// 的语句,observed_at <= as_of。开箱即用的「X 心里有什么」聚合。
struct MentalState {
    std::vector<retrieval::StatementRow> beliefs;       // modality BELIEVES
    std::vector<retrieval::StatementRow> knowledge;     // modality KNOWS 或 predicate='knows'
    std::vector<retrieval::StatementRow> desires;       // modality DESIRES
    std::vector<retrieval::StatementRow> intentions;    // modality INTENDS
    std::vector<retrieval::StatementRow> commitments;   // modality COMMITS
    std::vector<retrieval::StatementRow> preferences;   // predicate='prefers'
};

MentalState mental_state_of(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view tenant,
    std::string_view as_of);
```

### 5.2 语义与分组

- 单次查询 `statements WHERE tenant_id=? AND holder_id=x AND observed_at<=as_of`(复用既有 StatementRow 列;不另查)。
- 按 (modality, predicate) 分桶。**确切的 stored modality 字符串大小写由 ctest 钉死**——ctest 用真实 stored 值 seed(参 `test_mentalizing_think.cpp` 的 seed_helper:stored modality 形如 `'occurred'` 小写),实现匹配该契约。已知映射意图:
  - `modality` ∈ {believes→beliefs, desires→desires, intends→intentions, commits→commitments}
  - `predicate='knows'`(或 modality=knows)→ knowledge
  - `predicate='prefers'` → preferences
- 分桶优先级(一条语句**恰好一个**桶):**先按 predicate**——`prefers`→preferences、`knows`→knowledge;**其余按 modality**——believes→beliefs、desires→desires、intends→intentions、commits→commitments。OCCURRED / NORM_* / ENFORCES / OBSERVES 不入任何桶(非 X 的命题态度)。predicate 优先解决「modality=BELIEVES 且 predicate=prefers」的归属歧义。
- 排序:每桶按 observed_at(或 rowid)升序(可读时间线)。
- 复用 holder 隔离(P3.a1 多 holder 隔离已有):只取 holder_id=x 的语句 → 是 X 自己的心智态,不混他人。
- 落点 `src/tom/mentalizing_profile.cpp`(单一职责,进 starling_core);`what_does_X_*` 本体不动。

### 5.3 绑定
- `bindings/python/bind_08_tom.cpp`:`MentalState` POD(`def_readonly` 6 字段)+ `mental_state_of` `.def`(镜像 `what_does_X_believe`,GIL release 围查询)。
- `python/starling/tom/primitives.py`:瘦包装 `mental_state_of(adapter, *, x, tenant_id='default', as_of=None)`(`_iso_now_or_convert`)。

## 6. 组件① 抽取增强 (extraction-side)

`python/starling/extractor/prompts.py`:在既有 worked example 后**加性**补 DESIRES/INTENDS/knows/prefers 的示例(belief 示例不动)。

**关键:desires/intentions 由 `modality`(DESIRES/INTENDS)承载** —— 现有 predicate 词表(responsible_for/knows/prefers/promises/forbids/requires/located_at/member_of/believes/doubts)**没有干净的「想要做 X」动词**,所以欲望/意图语句用最接近的 predicate,真正的信号是 modality。`mental_state_of` 的 desires/intentions 桶**按 modality 分(predicate-agnostic)**,故分桶对 predicate 不敏感、稳健。

确切示例:
- **INTENDS**(predicate 干净):`"Mei: I'm going to finish the report tonight"` → `{holder:"Mei", subject:"Mei", predicate:"responsible_for", object:"report", modality:"INTENDS", ...}`。
- **DESIRES**(predicate 取最近似):`"Li Hua: I want to spend the weekend outdoors"` → `{holder:"Li Hua", subject:"Li Hua", predicate:"prefers", object:"outdoors", modality:"DESIRES", ...}`(prefers 作最近似;modality=DESIRES 是分桶信号)。
- **KNOWS**:`"Tom: I know the keys are in the drawer"` → `predicate:"knows"`(抽取 prompt 当前把 `knows` 列为 predicate;knowledge 桶据此 `predicate='knows'`)。
- 守卫:示例须与既有 OBJECT BREVITY / HOLDER vs SUBJECT 规则一致;不引入与 belief 示例冲突的 holder/subject 归属。

**plan 评估点(非本 spec 强制)**:是否给 predicate 词表加 `wants`(prompt 配置数据 + general-fact predicate constexpr 类,**非 schema**)以让欲望对象更自然。若加,desires 桶仍按 modality 分,向后兼容。

> 注:抽取增强的真实效果(LLM 是否可靠产出这些 modality)由**真模型重测**衡量;stub-LLM 钉测只锁「给定这些 modality 的语句,mental_state_of 正确分组」的下游契约。

## 7. 组件③ 瘦消费方 + dump-gating (server)

`scripts/starling_tomeval_server.py`:
- 问题分类(轻量,意图级):识别 Knowledge / Desire / Intention 类问题(关键词/句式),对这些题在 dump 注入相关角色的 `mental_state_of`(beliefs/knowledge/desires/intentions/preferences 的紧凑文本)。
- **dump-gating**:belief-only / emotion / non-literal 题**不注入** mental_state(避免上轮发现的「无关 dump 噪声拖累非目标家族」)。
- 失败/空 → 回落现有 dump。绝不破坏作答。
- server 只**调用核心 `mental_state_of` + 格式化**,无社会认知逻辑(内化原则)。

## 8. 错误处理 / 退化
- `mental_state_of` 空(X 无语句 / 未知 cognizer)→ 返回空 MentalState(各桶空向量),不抛。
- cognizer 查询侧 lookup-only best-effort(镜像现有 ToM 查询);未知 surface 透传。
- server 注入异常 → `contextlib.suppress` 回落裸 dump(沿用既有 best-effort)。

## 9. 测试 (Testing, TDD)
- **C++ ctest**(`tests/cpp/test_mental_state.cpp`,直接 seed statements):seed X 持有 believes/knows/desires/intends/commits/prefers 各一 + 他人语句 + OCCURRED → `mental_state_of(X)` 各桶恰含对应行、不含他人/OCCURRED;未知 X → 全空;as_of 早于某语句 → 该语句不入桶。**此测试钉死 modality/predicate→桶 的确切 stored 值契约**。
- **绑定 smoke**(pytest):`_core.mental_state_of` 可调 + `primitives.mental_state_of` 包装存在。
- **round-trip**(stub-LLM,pytest):一段含 desire+intention+knowledge 的对话 → `remember` → `mental_state_of` 各桶非空且归类正确。
- **抽取回归**:既有 belief/extractor 钉测不变(prompt 加性)。
- **出口**:全量 ctest/pytest 绿(纯加性:新 `mental_state_of` + 新 prompt 例 + 绑定 + server 注入;canonicalize parity、既有 ToM/belief/六态/冲突/感知/grounding/#3 链 钉测全绿)。

## 10. 约束 (Constraints)
- 核心 ToM 逻辑全 C++(`src/tom/mentalizing_profile.cpp`);抽取 prompt=配置数据;绑定/包装/server 瘦转发。
- 不改 `canonicalize_*`、`what_does_X_think`/`what_does_X_believe`/`does_X_know` 本体、`perceived_by_json`、schema/migration(复用现有 modality/predicate/StatementRow)。
- cognizer 查询侧 lookup-only;holder 隔离复用 P3.a1。
- TDD 先红后绿;构建 repo 根 `configure_build.py --build`,改 C++/绑定后 `--python-editable`(+ 必要 `cmake --install`);ctest 用 `.venv/bin/ctest`。
- explicit-path `git add`;无 `--no-verify`/`--amend`;不推/合 main/登记 roadmap(需显式 consent)。

## 11. 成功标准 / 测量 (Success Criteria)
- **首要**:`mental_state_of` 作为开箱即用核心能力落地(ctest 钉死分组契约)+ 抽取可靠捕获 BDI+K。
- **次要**:重跑 ToMBench(server gated 注入 mental_state)→ Knowledge/Desire/Intention 家族相对当前(−4.4/−3.6/−2.4)回升,不拖累其它家族(gating)。**不许诺固定升幅**;出口按需重跑(设计/实现阶段不烧 API)。
