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

# remember extraction 出锁(方案2 / 三相拆分)— Design Spec
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **2026-09-11 契约补充**：C++ 抽取与准入均在事务外；提交核验 prepared Engram。 当前扩展见 [已确认语义证据设计](2026-09-11-source-grounded-claim-contract-design.md)。下文保留本版本原有适用范围。


**Date:** 2026-07-12
**Slice:** 把 `remember` 的 extraction LLM 调用移出引擎锁 + DB 事务,消除摄入/对话/tick 期间的 dashboard 卡死。这是 #51(converse 生成段出锁)的下沉延伸——remember 的 extraction 是所有写路径的公共长腿。
**Branch:** `feat/remember-extraction-lock-free`(off `main@1fc4a5a`)。

## Problem / Context

`memoryops::remember` = ① `append_evidence`(engram 写)② `Extractor::run`。`Extractor::run` 在 `extractor.cpp:200` 开**一个** `TransactionGuard tx(conn_)`,重试循环在其内每轮调 `adapter_.extract`(LLM,`:230`),再写 attempt 行/events,成功则写 statements。**LLM 网络调用被 DB 事务 `BEGIN IMMEDIATE` 横跨**;host 侧 `engine.remember` 又持 `_lock` 横跨整个 remember。

**实测代价(dogfood A+B 双重证明):** 摄入一块 remember 期间并发 `/api/tick` 等锁 **37.8s**(A);extraction latency p95 **51s**,Clash 黑洞日 **247s**(B `/api/metrics/latency`)。#51 只修了 converse 的 chat 生成,没修 remember 的 extraction——而 remember 被摄入 worker、converse_commit、tick、直接写全用,是更中心的长腿。

**关键实情(勘察 `_memory_core.py:134-198`):`MemoryCore.remember` 跑三条带 LLM 的抽取管线**,不是两条:① **belief**(`_core.memory_remember` + belief_prompt,走 `Extractor`)② **episodic**(`_core.EpisodicExtractor.extract`,**独立类**,叙事→OCCURRED 事件)③ **general-fact**(`_core.memory_remember` + gf_prompt,也走 `Extractor`)。三条锁内顺序跑 ≈ 三次 LLM 之和 = 44s。**本 slice = option B**:只拆 `Extractor`(belief+gf 共用它,一拆两得),把这两条 LLM 出锁;**episodic 是独立 `EpisodicExtractor` 类,本 slice 保持单体、仍在锁内**(约 1/3 残留),留作 follow-up。预期 44s → ~15s(episodic 残留),而非归零——measure-first:先看 belief+gf 出锁后 episodic 残留是否还痛,再决定拆不拆 `EpisodicExtractor`。

**关键约束(决定设计,无捷径):** 不能只释放 host `_lock` 而不动 DB 事务——host 放锁后 extractor 仍持 `BEGIN IMMEDIATE`,并发写同一单写者连接照样 BEGIN 套 BEGIN 抛错/丢写(正是子项 A Task 3 撞的单写者隐患,见记忆 replay-write-reentrancy)。**必须同时**把 extractor 事务与 host 锁都挪出 extraction。

## Goal / Non-Goals

**Goal:** remember 的 belief+gf extraction LLM 调用**既不持引擎锁、也不在 DB 事务内**;摄入/对话/tick 期间 dashboard 保持可用。行为等价:落库**行内容/status/statements/latency_ms**、幂等、attempt 行、失败语义、statement_ids 顺序不变。**一处已知例外(plan-eng-review #8 裁定接受+文档化):** DB 写**时戳列**(pipeline_run.started_at、extraction_attempt.created_at、events)从「与 LLM 交错」位移到「persist 时刻聚簇」(所有 DB 写现跟在 LLM 后)——已核实无消费方依赖时戳铺开,latency_ms(真 LLM 往返)保留。

**Non-Goals:**
- embedding 出锁 / query-embed cache —— 仍 gated。
- 改 extraction 重试策略/prompt/attempt 语义 —— 只搬事务边界,不改语义。
- 多 remember 真并发 —— 非目标(prepare/commit 仍按锁序串行,同 #51)。
- **episodic(`EpisodicExtractor`)三相化** —— 本 slice 保持单体、其 LLM 仍在锁内(commit 段的残留);measure-first follow-up(见 §Blast Radius/§Out of Scope)。

## Design(三相,照 #51 converse)

### ① Extractor 拆两段(`src/extractor/extractor.cpp` + hpp)

`Extractor::run`(单体保留)拆成两个方法:
- **`extract_llm(payload_bytes, holder_id, existing_ref_map) → ExtractionLlmResult`**:跑重试循环**只做 `adapter_.extract` + `parse_extractor_json`**,把每轮收集进 `ExtractionLlmResult{prompt_body, prompt_input_hash, vector<ExtractionLlmAttempt>}`(每 attempt = `{attempt, LLMResponse resp, bool parsed, ParseResult parse, bool terminal}`,`terminal`=parse 成功那轮)。**零 DB、无 `TransactionGuard`**。**correctness crux:重试的决策(`!resp.ok` 或 `!parse.errors.empty()` 才重试;parse 成功 break)纯由 LLM 响应+parse 决定,不读任何 DB**——故 attempt 序列可无 DB 完整确定、persist 忠实重放。
- **`persist(engram_ref, holder_id, holder_tenant_id, interlocutor, const ExtractionLlmResult&) → ExtractionRunResult`**:开 `TransactionGuard`,遍历收集的 attempts 重放:失败/parse-error attempt → `record_attempt(Failed)` + `extraction.failed`(+`retry_scheduled` if attempt<max);terminal attempt → 逐 statement 写(StatementWriter + CognizerHub register-on-miss + holder 归属 + scope_parties + span_key noop 检查,**verbatim 移自 `run()` 现:283-421**,`resp`→`rec.resp`、`parsed`→`ParseResult parsed = rec.parse`)。终态计算 + `finish_run` + emit(移自 `run()` 现:424-444)。**FAILED 仍 COMMIT attempt 行**(现语义不变)。`take_cost` 语义搬运不变(cost 取自 `rec.resp`,per-attempt 归第一行)。
- **单体 `Extractor::run` 内联** `extract_llm` → `persist`(单一语义源,同 converse 单体)。既有全部 extractor 测试(driven via `run()`)照跑不改。

### ② remember 三相(`src/memory/memory_ops.cpp` + hpp)

见 §Design 开头「C++ 三相原语」块的三个签名(`remember_prepare`/`extract_llm`/`remember_commit`)+ 单体 `remember` 内联。`RememberPrepared{engram_ref, outcome, should_extract}` 新结构入 `memory_ops.hpp`;`ExtractionLlmResult` 入 `extractor.hpp`(§①)。

### ③ 绑定(`bindings/python/bind_13_memory_ops.cpp`)

照 converse 三相绑定范式(bind_13 现:166-254):
- opaque `py::class_<RememberPrepared>` + `py::class_<extractor::ExtractionLlmResult>`(无方法,只作句柄在三段间传递,Python 不解构)。
- `memory_remember_prepare(...) → RememberPrepared`(gil_release 包 engram 写)。
- `memory_extract_llm(adapter, llm, prompt_template, holder_id, payload, policy) → ExtractionLlmResult`(gil_release 包纯 LLM 段)。
- `memory_remember_commit(adapter, llm, prepared, tenant/holder/interlocutor/created_at, llm_result, policy) → dict`(gil_release 包 txn 写;返回 shape 与现 `memory_remember` 一致,含 `extraction_failed`)。
- 现 `memory_remember`(单体)**保留不动**。

### ④ host(`python/starling/dashboard/engine.py` + `_memory_core.py`)

**`MemoryCore.remember` 编排三条管线(belief+episodic+gf);本 slice 把 belief+gf 的 LLM 出锁,episodic 单体留 commit 内(残留)。** belief+gf 都走 `Extractor`(拆一个类两条都出锁);episodic 是独立 `EpisodicExtractor`,本 slice 不拆。三相在 `MemoryCore` 层编排(belief+episodic+gf 细节封在内):
- `MemoryCore.remember_prepare(text, holder, interlocutor, now) → bundle`:`_core.memory_remember_prepare` 写 engram **一次**(belief+gf 共用同一 idempotent engram);返回 bundle{prepared(engram_ref/outcome/should_extract), created_iso, holder_id, interlocutor, text}。
- `MemoryCore.remember_extract(bundle) → extracted`:**belief LLM + general-fact LLM 两次 `_core.memory_extract_llm`**(锁外无事务;should_extract=False 时短路空)。收进 extracted{belief_llm, gf_llm}。
- `MemoryCore.remember_commit(bundle, extracted) → dict`:belief `_core.memory_remember_commit`(txn 写 belief statements)→ **episodic 单体**(`EpisodicExtractor.extract` + `PerceptionReconstructor`,LLM+DB 仍在此锁内 = 残留)→ gf `_core.memory_remember_commit`(复用同 engram_ref,txn 写 gf statements);statement_ids 顺序 belief+episodic+gf 与现状逐字节一致。
- 现 `MemoryCore.remember()` 保留(内部改调三方法顺序内联,belief/episodic/gf 顺序不变)。
- `engine.remember` 三段化:锁内 `remember_prepare` + `_resolve` extraction adapter 局部引用 → **锁外** `remember_extract`(belief+gf 两次 LLM)→ 锁内 `remember_commit`(照 #51 `_converse_phased`)。provider 解析改局部引用(避拆锁后全局 slot 竞态,同 #51 `_resolve_chat`)。
- **payoff**:摄入 worker(`_ingest_drain_once` 调 `self.remember`)自动受益——belief+gf extraction 期不再持锁(episodic 残留 ~15s),A 实测 37.8s 卡顿大幅缩短。`ingest_remember_ms_total`(锁内墙钟)会显示骤降。

**C++ 三相原语是单次 extraction**(belief/gf 各调一遍),不感知 belief/gf/episodic——那是 host `MemoryCore` 的编排。`memoryops`:
- `remember_prepare(adapter, params) → RememberPrepared{engram_ref, outcome, should_extract}`:`require_write_admission`(fail-fast)+ `append_evidence`。
- `extract_llm(adapter, llm, prompt_template, params, policy) → extractor::ExtractionLlmResult`:构 `Extractor` → `ex.extract_llm`(纯 LLM+parse,无 DB/txn)。
- `remember_commit(adapter, llm, params, prepared, llm_result, policy) → RememberOutcome`:`require_write_admission`(捕中途转 DRAINING)+ `ex.persist`(txn 写)+ 写后泵;`should_extract=False` 时直接回 prepared 的 outcome/engram_ref(no_store/rejected 短路,不泵)。
- 单体 `remember` 内联三者(单一语义源)。`converse_commit` 仍调单体 `remember`(其 extraction 仍锁内——非摄入热路径,不动)。

### ⑤ 并发 hazard(单写者)

- extract_llm **既无锁也无事务** → 并发 tick/HTTP 写在 extract 期开 `BEGIN IMMEDIATE` 不再撞「事务内事务」。
- prepare/commit 短段仍持 `_lock`(单写者串行);engram 写(prepare)与 statement 写(commit)分两个短 txn,中间无开事务——安全。
- drain 语义(#45 写门)不变:prepare 门前抛/commit remember 门前抛处理中途 DRAINING。

## Blast Radius

`Extractor::run` / `memoryops::remember` 单体都保留 = 单一语义源;非 host 调用方**零感知**:`converse_commit`(内调单体 `remember`)、tick、facade `Memory`、以及所有 `ex.run(` 调用方行为不变。**仅 host `MemoryCore.remember`(→ `engine.remember`)改走三相**释放锁。
- **episodic 残留**:`MemoryCore.remember_commit` 内 episodic(`EpisodicExtractor` 单体)的 LLM 仍在锁内(~15s)。本 slice 接受(measure-first,option B);拆 `EpisodicExtractor` 是 follow-up。
- **converse_commit 残留**:仍走单体 `remember`,其 extraction 仍锁内——但 converse 的 chat 生成已 #51 出锁,extraction 短且非摄入热路径,本 slice 不动。
- **Extractor 是核心、blast radius 广**:全量 ctest 是回归网;`run()` 内联 `extract_llm→persist` 后行为须逐字节不变(既有 extractor/memory_ops 测试全绿 = 首道网);shared-caller 签名注入陷阱(见记忆 clang-tidy-gotchas)——`extract_llm`/`persist` 是**新增**方法,`run()` 签名不改,零调用方受影响。

## Testing

- **C++ Extractor parity 钉测**(`test_extractor_phases.cpp`):同输入 `extract_llm→persist` 组合与单体 `Extractor::run` 的 `ExtractionRunResult` + 落库 statements/attempt/pipeline_run/bus_events 行逐字段一致(FakeLLM,覆盖成功/parse失败/LLM失败重试满/重试后成功/noop 重忆)。
- **extract_llm 无事务证**:extract_llm 返回后 `sqlite3_get_autocommit(conn)==1`(无开事务)+ 执行期间零行写入(statements/attempt/pipeline_run 计数不变)——钉死「LLM 在事务外、零 DB」。
- **C++ remember 三相 parity**(`test_remember_phases.cpp`):prepare+extract_llm+commit ≡ 单体 remember(RememberOutcome 逐字段 + 落库);no_store/rejected 时 should_extract=false 短路(不 persist、不泵);FAILED 仍写 3 attempt 行;门中途转关 → commit 抛 `WriteGateRejected`。
- **锁纪律(Python)**:慢 stub extraction 驱动 `engine.remember` 三相,并发线程 `engine.recall`/tick 在 extract 段内拿到锁(拆锁前必阻塞;同 #51 锁测思路)。
- **belief+episodic+gf 顺序/输出 parity(Python)**:三相 `engine.remember` 的返回 dict(engram_ref/statement_ids/outcome)与旧单体路径一致(episodic 事件 + gf 事实都在,顺序不变)。
- **门**:全量 ctest + `.venv/bin/python -m pytest tests/python` 绿;改 C++/绑定后 `--python-editable` 重装;clang-tidy 由构清洁。

## Out of Scope

**`EpisodicExtractor` 三相化(episodic LLM 出锁)= measure-first follow-up**:本 slice 只拆 `Extractor`(belief+gf);episodic 单体的 LLM 仍在 commit 锁内(~15s 残留)。先跑起来看 B 的 latency 端点里 episodic 残留是否还痛,再决定拆。

**belief/gf 跨管线原子性(plan-eng-review #3 记 follow-up)**:`remember_commit` 顺序跑 belief→episodic→gf,每 C++ commit 重查门;drain 落在 belief 与 gf 之间会部分写入+抛。**属既存**(单体 belief→gf 也非原子),非本计划回归;follow-up = commit 段门检查一次而非每 commit 重查。本 slice 不动。

其余:embedding 出锁 / query-embed cache;converse_commit 内 remember 的 extraction(非摄入热路径,gated);多 remember 真并发。
