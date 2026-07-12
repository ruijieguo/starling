# remember extraction 出锁(方案2 / 三相拆分)— Design Spec

**Date:** 2026-07-12
**Slice:** 把 `remember` 的 extraction LLM 调用移出引擎锁 + DB 事务,消除摄入/对话/tick 期间的 dashboard 卡死。这是 #51(converse 生成段出锁)的下沉延伸——remember 的 extraction 是所有写路径的公共长腿。
**Branch:** `feat/remember-extraction-lock-free`(off `main@1fc4a5a`)。

## Problem / Context

`memoryops::remember` = ① `append_evidence`(engram 写)② `Extractor::run`。`Extractor::run` 在 `extractor.cpp:200` 开**一个** `TransactionGuard tx(conn_)`,重试循环在其内每轮调 `adapter_.extract`(LLM,`:230`),再写 attempt 行/events,成功则写 statements。**LLM 网络调用被 DB 事务 `BEGIN IMMEDIATE` 横跨**;host 侧 `engine.remember` 又持 `_lock` 横跨整个 remember。

**实测代价(dogfood A+B 双重证明):** 摄入一块 remember 期间并发 `/api/tick` 等锁 **37.8s**(A);extraction latency p95 **51s**,Clash 黑洞日 **247s**(B `/api/metrics/latency`)。#51 只修了 converse 的 chat 生成,没修 remember 的 extraction——而 remember 被摄入 worker、converse_commit、tick、直接写全用,是更中心的长腿。

**关键约束(决定设计,无捷径):** 不能只释放 host `_lock` 而不动 DB 事务——host 放锁后 extractor 仍持 `BEGIN IMMEDIATE`,并发写同一单写者连接照样 BEGIN 套 BEGIN 抛错/丢写(正是子项 A Task 3 撞的单写者隐患,见记忆 replay-write-reentrancy)。**必须同时**把 extractor 事务与 host 锁都挪出 extraction。

## Goal / Non-Goals

**Goal:** remember 的 extraction LLM 调用**既不持引擎锁、也不在 DB 事务内**;摄入/对话/tick 期间 dashboard 保持可用。行为(落库终态、幂等、attempt 行、失败语义)字节级不变。

**Non-Goals:**
- embedding 出锁 / query-embed cache —— 仍 gated。
- 改 extraction 重试策略/prompt/attempt 语义 —— 只搬事务边界,不改语义。
- 多 remember 真并发 —— 非目标(prepare/commit 仍按锁序串行,同 #51)。
- MemoryCore 的 general-fact 第二次 remember 调用的独立三相化 —— 若单体三相化后它自动受益则免;否则记 follow-up(见 §blast radius)。

## Design(三相,照 #51 converse)

### ① Extractor 拆两段(`src/extractor/extractor.cpp` + hpp)

`Extractor::run`(单体保留)拆成:
- **`extract_llm(engram_ref, payload, holder, tenant, existing_ref_map, interlocutor) → ExtractionLlmResult`**:跑重试循环**只做 LLM 调用 + parse**,把每轮 `{attempt, status, raw_output, error, cost, parsed_statements?}` 收集进 `ExtractionLlmResult`(纯内存,**零 DB 写、无 TransactionGuard**)。LLM 只吃 `payload`+`existing_ref_map`,不需 engram 在库。
- **`persist(engram_ref, holder, tenant, ExtractionLlmResult) → ExtractionRunResult`**:开 `TransactionGuard`,按收集的结果写 ledger(start_run)+ 逐 attempt 行 + events + 成功 attempt 的 statements(StatementWriter + CognizerHub register-on-miss,都 join 此 txn)。**FAILED 仍 COMMIT attempt 行**(现语义不变)。终态与现单体逐字节等价(同一 txn 原子写,只是所有 DB 写集中在 LLM 之后)。
- **单体 `Extractor::run` 内联** `extract_llm` → `persist`(单一语义源,同 converse 单体)。既有全部 extractor 测试照跑。

注意点:CognizerHub resolve-or-register 的写必须留在 `persist` 的 txn 内(现在就在 txn 内);`take_cost`/span-key/幂等 dedup 语义搬运不变。

### ② remember 三相(`src/memory/memory_ops.cpp` + hpp)

- **`remember_prepare(adapter, params) → RememberPrepared`**:`append_evidence`(engram 写,DB)。返回 `{engram_ref, outcome, should_extract}`(no_store/rejected → should_extract=false,提前收尾)。锁内短。
- **(extract:host 驱动)`Extractor::extract_llm`**:LLM,**锁外无事务**。
- **`remember_commit(adapter, extraction_llm, extraction_prompt, params, prepared, llm_result) → RememberOutcome`**:`Extractor::persist`(txn 写 statements/attempt/events)。填 `statement_ids`/`extraction_failed`。锁内短。
- **单体 `remember` 内联** prepare → extract_llm → commit(单一语义源)。

### ③ 绑定(`bindings/python/bind_13_memory_ops.cpp`)

- `memory_remember_prepare(...) → RememberPrepared`(gil_release 包 engram 写)。
- `memory_extract_llm(extraction_llm, <payload/params>) → ExtractionLlmResult`(gil_release 包纯 LLM 段)。
- `memory_remember_commit(..., prepared, llm_result) → dict`(gil_release 包 txn 写;返回 shape 与现 `memory_remember` 一致,含 `extraction_failed`)。
- 现 `memory_remember`(单体)**保留不动**。`ExtractionLlmResult`/`RememberPrepared` 需 opaque 绑定(只作句柄在三段间传递,Python 不解构)。

### ④ host(`python/starling/dashboard/engine.py` + `_memory_core.py`)

**关键:`MemoryCore.remember` 跑两次 extraction**——belief(`_core.memory_remember`,`_memory_core.py:152`)+ general-fact(同一 idempotent engram 再跑一次 general prompt,`:184-188`)。要真释放锁,**两次 LLM 都必须锁外**(否则 commit 段还含 general-fact 的 LLM 调用就不「短」)。故三相在 `MemoryCore` 层编排,把 belief+gf 细节封在内:
- `MemoryCore.remember_prepare(text, ...) → prepared`:`append_evidence` 写 engram **一次**(belief+gf 共用同一 engram)。
- `MemoryCore.extract_llm(chat_llm, prepared) → llm_result`:**belief LLM + general-fact LLM 两次调用都在此**(锁外无事务),结果收进 `llm_result`。
- `MemoryCore.remember_commit(prepared, llm_result, ...) → dict`:txn 持久化 belief + gf 两路 statements/attempt/events;返回 dict shape 与现 `remember` 一致。
- 现 `MemoryCore.remember()` 保留(单体走 prepare→extract→commit 内联,belief+gf 顺序不变)。
- `engine.remember` 三段化:锁内 prepare + `_resolve` extraction adapter 局部引用 → **锁外** extract_llm(含两次 LLM)→ 锁内 commit(照 #51 `_converse_phased`)。`_role_override("llm",provider)` 改局部解析(避拆锁后全局 slot 竞态,同 #51 `_resolve_chat`)。
- **payoff**:摄入 worker(`_ingest_drain_once` 调 `self.remember`)自动受益——两次 extraction 期都不再持锁,A 实测 37.8s 卡顿消除。`ingest_remember_ms_total` 会显示锁外时长骤降。

### ⑤ 并发 hazard(单写者)

- extract_llm **既无锁也无事务** → 并发 tick/HTTP 写在 extract 期开 `BEGIN IMMEDIATE` 不再撞「事务内事务」。
- prepare/commit 短段仍持 `_lock`(单写者串行);engram 写(prepare)与 statement 写(commit)分两个短 txn,中间无开事务——安全。
- drain 语义(#45 写门)不变:prepare 门前抛/commit remember 门前抛处理中途 DRAINING。

## Blast Radius

`remember` 单体保留 = 单一语义源;非 host 调用方**零感知**:`converse_commit`(memory_ops 内调 remember)、tick、`MemoryCore.remember` 的 belief + general-fact 两次调用都走单体,行为不变。**仅 `engine.remember` 显式改走三相**释放锁。converse_commit 内部仍走单体 remember(其 extraction 仍持锁)——但 converse 的 chat 生成已 #51 出锁,extraction 段短且非摄入热路径,本 slice 不动(若实测 converse extraction 仍痛再 follow-up)。Extractor 是核心、blast radius 广:全量 ctest 是回归网;shared-caller 签名注入陷阱(见记忆)——grep `src/` + `tests/` 的 `::run(`/`.run(` 全调用方确认。

## Testing

- **C++ parity 钉测**:同输入 `extract_llm+persist` 组合与单体 `Extractor::run` 的 `ExtractionRunResult` + 落库 statements/attempt 行逐字段一致(FakeLLM,覆盖成功/parse失败/LLM失败/重试后成功)。
- **extract_llm 无事务证**:extract_llm 执行期间 `sqlite3_get_autocommit(conn)` 为真(无开事务)——钉死「LLM 在事务外」。
- **remember 三相 parity**:prepare+extract_llm+commit ≡ 单体 remember(RememberOutcome 逐字段 + 落库);no_store/rejected 短路;FAILED 仍写 attempt 行。
- **锁纪律(Python)**:慢 stub extraction(`set_delay_ms`)驱动 `engine.remember`,并发线程 `engine.tick` 在生成段内 <阈值 拿到锁(拆锁前必阻塞;同 #51 锁测)。
- **摄入端到端**:样例 job → 摄入 worker → 消化期并发 `/api/tick` 秒回(A 的 37.8s 卡顿消除)。
- **门**:全量 ctest + pytest 绿;`--python-editable` 重装;clang-tidy 由构清洁。

## Out of Scope

embedding 出锁 / query-embed cache;converse_commit 内 remember 的 extraction(非摄入热路径,gated);general-fact 第二次 remember 独立三相化(若单体三相化不自动惠及则 follow-up);多 remember 真并发。
