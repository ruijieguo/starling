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

# EpisodicExtractor 三相化(方案2 option B 收尾)— Design Spec
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

**Date:** 2026-07-14
**Slice:** 把 remember commit 写锁内**唯一残留的 LLM 调用**(EpisodicExtractor 的 ~20-50s 抽取)移出锁——收尾方案2(PR #54)有意保留的 option B 残留,让 remember 的写锁持有变成纯 DB(ms 级)。

## Problem / Context

方案2(PR #54 main@c0e2fdd)把 remember 的 belief + general-fact extraction 移出写锁(三相:prepare 持锁 → belief+gf extract 锁外 → commit 持锁),但**有意保留** episodic 管线的 LLM 调用在 commit 锁内(option B:`EpisodicExtractor` 是独立类,当时判为 measure-first follow-up)。

**measure-first 已坐实该残留真实且可观(2026-07-14):**

- **结构(确定性 FakeLLM,零网络,不受 Clash 影响)**:后台跑 `eng.remember`(每次 extract 睡 D=1000ms),主线程高频探测 `eng.tick`(取同一写锁)计时。147 次锁外 tick 中位阻塞 **0.3ms**;**1 次撞进 episodic 锁内窗口的 tick 阻塞 1003ms = 1.00×D**。remember 总时长 3.03s = 2×D 锁外(belief+gf extract)+ 1×D 锁内(episodic)。→ `max_block/D = 1.00`:**并发写被 episodic 楔住 ≈ 其 LLM 全时长**。
- **量级(真库 dashboard.db,Clash 过滤后 14 个干净样本 <60s)**:单次 LLM 延迟 **p50=20.2s、p90=48.4s、tail=51.5s**(另 17 个 ≥60s 是 Clash 黑洞重试耗尽,已剔除)。episodic 是同模型单次调用 → **并发写被楔 ≈ 20s(p50)~ 51s(尾)**。

**关键洞察**:方案2 验证时「并发 tick 0.01s 秒回」是 tick 撞在 **extract 锁外段**(占 remember ~2/3)的最好情况;若撞进 **episodic 锁内窗口**(占 ~1/3),仍等 20-50s。残留不是舍入误差——**每次 remember 都有 ~1/3 时间是 20-50s 的写锁窗口**,dashboard 的周期后台 pump/tick 必然命中。

**用户裁定(2026-07-14,measure-first 后)**:三相化 EpisodicExtractor,现在做。

## Goal / Non-Goals

**Goal:** 照方案2 option A 的三相模式,把 `EpisodicExtractor::extract` 拆成 `extract_llm`(纯 LLM+parse,锁外无 txn)+ `persist`(事件落库,锁内),让 episodic 的 ~20-50s LLM 调用移到 remember 的锁外 extract 相。修后:remember 写锁持有 = 纯 DB(belief/episodic/gf persist + perception + 写后泵),无任何 LLM 网络调用。

**Non-Goals:**
- 不动 perception reconstruct / 写后泵 / belief·gf persist —— 它们**已核实纯 DB**(签名只接 `SqliteAdapter&`+`Connection&`,物理上无法发 LLM),留在缩短后的 commit 锁内(单写者要求在写事务内)。
- 不改三相落锁的骨架(prepare/extract/commit 三段 `with self._lock`)—— 只把 episodic LLM 从相③挪到相②。
- 不改 episodic 的抽取语义 / prompt / 事件 schema / 幂等——纯粹是「LLM 与 DB 写解耦」的行为中立重构。
- 不碰 converse 路径(C++ 单体 memory_converse 只跑 belief,不含 episodic)。

## Design

### ① 范围边界(measure-first 背书)

勘察结论(带证据):`remember_commit`(`_memory_core.py:186-232`,写锁内)四步中,**唯一发起 LLM 网络调用的是 `EpisodicExtractor::extract`**(`src/extractor/episodic_extractor.cpp:88` 的 `adapter_.extract`):

| 锁内步骤 | LLM/网络? | 处置 |
|---|---|---|
| belief persist(`memory_remember_commit`)| 否(persist 遍历已算好的 `llm_result.attempts`,只写 DB)| 留锁内 |
| **episodic `.extract`** | **是(~20-50s,唯一)** | **拆分,LLM 出锁** |
| perception `.reconstruct` | 否(纯 DB:从 episodic_events/statements 重建 presence,只用 SqliteAdapter)| 留锁内 |
| gf persist | 否(同 belief persist)| 留锁内 |
| 写后泵 7 订阅者 | 否(全接 SqliteAdapter+Connection)| 留锁内 |

**否决的替代**:把整个 commit 移出锁——违反单写者(DB 写必须在 `BEGIN IMMEDIATE` 写事务 + 单一写锁内),错。

### ② C++ 拆分(镜像 `Extractor::extract_llm` / `persist`,`src/extractor/extractor.cpp:185-447`)

把 `EpisodicExtractor::extract`(现 `episodic_extractor.cpp:77-216`,LLM+DB 单体)拆成:

**`EpisodicLlmResult extract_llm(std::string_view passage)`(锁外,零 DB,无 `TransactionGuard`):**
- `build_prompt(passage)` → `adapter_.extract`(LLM)→ 若 `!resp.ok` 回空。
- `extract_array` + `nlohmann::json::parse`;非数组/空/解析失败 → 回空。
- 逐事件抽 raw 字段(actor/action/theme/location/time/participants)+ 完整性过滤(actor/action/theme 任一空则 skip,保持 seq 密集)+ 密集赋 1-based `seq` + 纯计算 `normalize_theme(theme)` 与 `canonicalize_object`(算 `canonical_object_hash`)。
- 产出 `EpisodicLlmResult`:携带 `bool ok` + `vector<ParsedEpisodicEvent>`(每个含 seq、actor_raw、action、object_value、canonical_object_hash、location、event_time、participants_raw)。**actor/participants 保持 raw surface**——`resolve_name` 会写 CognizerHub,必须留在 persist。

**`EpisodicExtractionResult persist(engram_ref, tenant, agent_self, now, const EpisodicLlmResult&)`(锁内):**
- `persistence::TransactionGuard tx(conn_)` → `StatementWriter` + `EpisodicEventStore` + 可选 `CognizerHub`。
- 逐事件:`resolve_name(actor)` + `resolve_name(每个 participant)`(CognizerHub register-on-miss 写本事务)→ 用锁外算好的 `canonical_object_hash` 构 `ExtractedStatement`(holder=agent_self、subject=resolved actor、predicate=action、object=normalized theme、modality=OCCURRED、chunk_index=seq、source_hash="episodic-"+seq、perceived_by=self)→ `compute_extraction_span_key` → `writer.write` → 收 stmt_id → best-effort `ep_store.upsert`(扩展行失败不回滚语句)。
- `tx.commit()`。返回 `event_statement_ids`(seq 升序)。

**`extract(...)` = 内联 `persist(engram_ref, …, extract_llm(passage))`**(单一语义源,镜像 `Extractor::run`;供 C++ 单测 parity 与任何单体调用)。

**接口**:头文件加 `struct EpisodicLlmResult`(值语义,可跨 pybind 传)+ `extract_llm` / `persist` 两个公开方法(保留 `extract`)。原双 ctor(conn+llm / conn+llm+store)不变;`extract_llm` 不触 `conn_`/`store_adapter_`。

### ③ Host 编排(`python/starling/_memory_core.py` + `bindings/python/bind_06_extractor.cpp`)

- **`remember_extract`(相②,锁外)**:现返回 `{belief, gf}`。加 episodic:构 `EpisodicExtractor(self.conn, extraction_llm, self.rt.adapter, self._extraction.episodic_prompt)` → 调 `.extract_llm(text)` → 返回 `{belief, gf, episodic_llm}`。episodic 的 ~20-50s LLM 就此出锁,与 belief+gf extract 并列锁外。(构造对象只存引用、`extract_llm` 零 DB → 相②调用安全。)
- **`remember_commit`(相③,锁内)**:episodic 由 `.extract(...)` 改为构 `EpisodicExtractor(...)`.`persist(engram_ref=engram_ref, tenant=…, agent_self=holder_id, now=created_iso, llm_result=extracted["episodic_llm"])` → 纯 DB(persist 不再取 passage——已被相② extract_llm 消费)。**锁内次序不变**:belief persist → episodic persist → `if event_ids: reconstruct`(纯 DB,读 episodic_events 故须在其后)→ gf persist。`statement_ids` 顺序 belief+episodic+gf 与单体逐字段一致。
- **绑定**:`bind_06_extractor.cpp` 加 `EpisodicLlmResult` opaque py::class_(镜像 belief 的 `ExtractionLlmResult`;**注意 `bugprone-unused-raii` NOLINT** + GIL 释放包住 `extract_llm` 的 LLM 调用,见 [[clang-tidy-ci-only-gate-gotchas]])+ `extract_llm` / `persist` 两个方法绑定。
- `engine.remember`(`engine.py:426-442`)三段落锁骨架不变;单用户 `Memory.remember` → `MemoryCore.remember` 单体复用同原语,**自动覆盖**。

### ④ 行为中立不变式

- **statement_ids 顺序**:belief + episodic + gf,persist 相内次序不变 → 顺序不变。
- **created_at 权威**:episodic 的 `now` 仍取 `prepared.created_at_iso8601`(#6 权威时戳,不在相②/③间漂移)。
- **best-effort 语义**:episodic LLM 失败/空数组 → `extract_llm` 回 `ok=false`/空事件 → `persist` 零写入返回(不重试、不抛),与单体一致。
- **幂等**:span_key / chunk_index(=seq)/ source_hash 计算不变 → 重复 remember 的折叠行为不变。

## Testing

- **C++ parity(新)** `tests/cpp/test_episodic_phases.cpp`:同一 passage,分相 `extract_llm`+`persist` 的产物 ≡ 单体 `extract`——逐字段断言 `event_statement_ids`、`statements` 行(subject/predicate/object/modality/canonical_object_hash)、`episodic_events` 行(seq/location/participants/action)。镜像 `test_extractor_phases`。
- **锁纪律回归(扩展)** `tests/python/test_remember_lock_release.py`:加一例——采样落在 **episodic 锁内窗口**(sleep 过 belief+gf extract 段)的并发 `tick` 现在必须 `<阈值`(episodic LLM 出锁后不再阻塞)。即把「残留」测量反转为回归守卫;确定性 FakeLLM,零真 LLM。
- **before/after 佐证(非门)**:scratchpad 的确定性测量脚本(`max_block/D`)前后对照——修后 episodic 窗口探测 `max_block/D ≈ 0`。进 PR body。
- **门**:全量 ctest + `.venv/bin/python -m pytest tests/python` 绿;改 C++/绑定 → `python scripts/configure_build.py --build --python-editable` 重装 `_core`;clang-tidy CI-only(新绑定 opaque handle + GIL 释放注意 NOLINT)。真 LLM 端到端 = 手动验证,不进 CI。

## Out of Scope(重申)

- perception reconstruct / 写后泵 / belief·gf persist(纯 DB,留锁内);三相落锁骨架;episodic 抽取语义/prompt/schema;converse 路径。
- 真机端到端量级复测(Clash 静默窗口手动)——结构由 parity + 锁纪律测试确定性覆盖,量级已由 measure-first 实测坐实。
