# remember extraction 出锁(方案2 / 三相拆分)— Design Spec

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
