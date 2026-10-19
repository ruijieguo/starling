# 候选形态 S：带日期的原文通道进入生产召回（草稿，待 E2 top-20 结果）

> 状态：2026-10-19 起草。**不实现**。等待 `2026-10-18-temporal-recall-rendering-design.md` 的 top-20 阶段与 E3 结果。本文只记录已核实的代码事实与待决问题，不含结论。

## 1. 为什么需要这份设计

E2 oracle 诊断给出：带日期原文 95.6% vs 带日期三元组 23.0%，决策映射指向路径 S。但 95.6% 是 oracle 上界。top-20 阶段在真实检索行集上回答"带日期的原文是否仍然胜过三元组"，E3 回答"召回深度如何影响"。**这两项结果出来之前，本文的取舍不作数。**

## 2. 已核实的底座（2026-10-19 只读勘察）

形态 S 不需要新建投影层，现有原语已经覆盖写入、存储、检索、渲染四段：

| 段 | 现有实现 | 位置 |
|---|---|---|
| 写入 | `retain_source_turns(adapter, tenant, allowed_holders, turns_json, created_at, preserve_invalid_time)` | `src/retrieval/source_retriever.cpp:1267` |
| 存储 | `source_documents(tenant_id, holder_id, engram_ref, registered_at)` + engram（`retention_mode='audit_retain'`，payload_inline） | 同上 |
| 单位契约 | `claim_source_turn_payload` / `claim_source_units`：逐 unit 的 `speaker`、`utterance`、`observed_at`、`session_id`、`turn_id`、`turn_index`、`clause_id`、`time_status` | `src/extractor/*` |
| 检索 | `ObserverRetriever::run(ObserverQuery)`：as-of 截断、BM25 打分、去重、预算裁剪、可选 claim 链接 | `src/retrieval/source_retriever.cpp:1310+` |
| 渲染 | `[SOURCE] {speaker, observed_at, session_id, turn_index} text="..."` | 同上 `:1437` |
| 授权 | 显式 `allowed_holders`；写入时 `source speaker outside allowed_holders` 直接抛错 | 同上 `:1286` |
| Python | 全部已绑定 | `bindings/python/bind_05_retrieval.cpp:81-102` |

**结论性事实**：原文通道在生产里已经存在且可用，不是从零新建。

## 3. 与评测臂的三处已知差距（必须在设计里处理）

1. **检索方式不同**。评测的 S 臂用 text-embedding-v4（1024 维）对平铺话轮做向量 top-k；生产的 source 腿默认 `source_strategy="bm25"`，是词法检索（`bm25_scores`）。`semantic_` 只用于语句腿（`RetrievalPlanner`）与 v7/v8 的 claim 链接，不参与原文单位的选取。**同一份语料、同样的行数，词法 vs 向量会给出不同行集**，top-20 结论不能直接搬到 BM25 上。设计必须决定：给 source 腿加向量通道，还是接受词法并在评测里重测。
2. **渲染格式不同**。评测臂是 `- [2023-05-27 Sat 00:34] user: <原文>`；生产是 `[SOURCE] {"speaker":"user","observed_at":"...","session_id":"...","turn_index":n} text="<原文>"`。后者更贵（JSON 键名重复），对模型也更啰嗦。设计要决定生产渲染是否向评测形态收敛。
3. **时间来源不同**。评测臂的日期取数据集的会话日期，直接写进渲染；生产取 unit 的 `observed_at`，缺失时是 `time_status=unknown` 且默认被过滤（`include_unknown_time=false`）。这与"只渲染可信时间"的硬约束一致，但意味着**没有 observed_at 的原文会被静默丢弃**，覆盖率会低于评测臂。

## 4. 待决问题（结果出来后再定）

- Q1：source 腿是否加向量通道？若加，是否与语句腿共用一个索引？
- Q2：生产渲染是否改成评测形态（`- [日期] speaker: 原文`），还是保持 `[SOURCE]` JSON？两者对模型的影响需要一个对照。
- Q3：与右脑语句行的融合比例。`ObserverQuery.min_source_items` 已存在，但那是 observer 评测口径；通用召回需要另定。
- Q4：查询改写与多跳（P2 立项）与形态 S 的关系——LoCoMo multi-hop 51.4% / open-domain 37.0% 说明检索本身有缺口，S 只解决"行取到之后怎么渲染"，解决不了"行取不到"。
- Q5：写入侧。现有 Dashboard 摄入走 `memory_remember_all`（抽取成语句），**不写 source_documents**；要让原文通道持续有货，摄入必须同时调 `retain_source_turns`。这是形态 S 真正的改动面，也是它最大的成本项。

### Q5 的代码落点（2026-10-19 核实）

- 调用点唯一：`python/starling/dashboard/engine.py:892`，摄入 worker 内 `for chunk in chunks: self.remember(chunk, ...)`。形态 S 要在这个循环里增加一次 `retain_source_turns`。
- 话轮结构已经现成：同一函数上方的 `chunk_dialogue(clean_turns(lines))` 里，`clean_turns` 返回 `[(role, text)]`，speaker 保留，可直接映射为 source unit 的 `speaker`。
- **但时间没有**：`clean_turns` 只取 `role` 与 `text`，transcript 事件本身不带时间戳。`retain_source_turns` 要求 `created_at` 为显式 UTC，unit 的 `observed_at` 缺失则 `time_status=unknown`、默认被检索过滤（`include_unknown_time=false`）。因此在摄入侧，**要么全部填摄入时刻（ingest clock）**——这是诚实的来源，但会把"三天前说过的话"标成"今天"；**要么留空并接受这些原文不可召回**。两者都需要用户在设计评审时裁定，不能默认选一个。
- 一条重要边界：这与本设计"只渲染可信时间"的硬约束直接冲突。若摄入侧只能提供 ingest clock，那么形态 S 在**生产**里拿不到评测臂那种"会话真实日期"，因为评测数据集的日期是数据集自带的，生产 transcript 没有。这是形态 S 最大的可行性风险，比 BM25-vs-向量那一条更根本。

## 5. 边界

遵守 C++/Python 边界裁定：检索、融合、渲染全在 C++；Python 只做开关透传与 DTO 构造。不新建投影表（E2 已证明 chunk 层不是瓶颈）。不改六态机与 §0.1 吸收原则。
