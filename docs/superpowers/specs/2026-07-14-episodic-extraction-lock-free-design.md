# EpisodicExtractor 三相化(方案2 option B 收尾)— Design Spec

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
