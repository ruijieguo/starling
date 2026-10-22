# 形态 S（左脑原文召回 lane）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 让 Starling 具备一条**按感知授权**的原文召回 lane：原始话轮按 `(场景, 听众)` 存储、按向量检索、以 `[SOURCE]` 渲染，与右脑语句在同一个 planner 里 RRF 融合；lane 默认关闭，关闭时行为逐字节不变。

**Architecture:** 权威元数据（听众、场景、时间、来源）落 `source_unit_meta`，向量索引 `source_unit_vectors` 只是可整表重建的派生数据；授权用已实现的 `KnowledgeFrontier::visible_engrams_at`，左脑**无条件**套用（右脑 planner 只在 `perspective != querier` 时遮罩）；融合在 `RetrievalPlanner` 内、按名次做 RRF(60)。

**Tech Stack:** C++20（`src/` + `include/starling/`）、pybind11（`bindings/python/`）、SQLite migrations、Python 3.14 适配层、pytest/ctest。

**Spec:** `docs/superpowers/specs/2026-10-19-form-s-source-lane-design.md`（v4.3，经五轮 Codex 评审）。

## Global Constraints

- **C++/Python 边界**：授权、分组、融合、渲染、预算全在 C++；Python 只做 transcript 信封适配与参数透传。
- **默认关闭**：`source_lane.enabled=false` 时，planner 输出、receipt、Python 返回结构、渲染字节与改动前相同。
- **唯一触碰右脑的改动**是 §3.4b 的 `perceived_by` 权威统一（用户 2026-10-20 已批准），且必须带"两人场景逐字节不变 + SocialMemBench/HiToM 不下降"的回归。
- **在场先写、抽取后读**：同一事务、同一连接；反序会让抽取推断的听众永久并入可见集。
- **迁移编号 `0037`**（仓内最新为 `0036`，已确认无冲突）。
- git 只用显式路径 `git add`；不用 `--no-verify` / `--amend`。
- 提交门：全量 ctest 与 `pytest tests/python` 绿。**先在当前 HEAD 记录一次基线数，之后只增不减**（不引用历史计划里的旧基线）。
- 提交门补充（2026-10-21 踩过一次）：`--build` 只编译不安装。**任何 C++ / migration / 绑定改动后、跑 pytest 前，必须先跑 `--python-editable` 重装 `_core`**，否则 pytest 导入的是 `.venv` 里的旧 `.so`，回归是**假绿**。Task 4 因改了 migration 的 DDL 触发过一次假的 NOT NULL 失败。核验方式：`python -c "import starling._core as m; print(m.__file__)"` 确认导入路径，并与 `build-macos/python/starling/_core*.so` 比时间戳。
- 构建：`python scripts/configure_build.py --build --test`；改 C++/绑定/migration 后必须再跑 `--python-editable` 重装 `_core`。

---

### Task 0: 记录基线

**Files:** 无（只记录）

- [ ] **Step 1:** 在干净 HEAD 上跑 `python scripts/configure_build.py --build --test`，记录 ctest 通过/总数。
- [ ] **Step 2:** 跑 `.venv/bin/python -m pytest tests/python -q`，记录 passed/skipped/failed。
- [ ] **Step 3:** 把两个数字写进本文件末尾的「基线」小节，提交。

**Acceptance:** 两个数字已记录；若已有失败，先单独立项修，不在本计划内推进。

---

### Task 1: 迁移 0037（两张表 + 成员历史表）

**Files:**
- Create: `migrations/0037_source_unit_meta.sql`
- Test: `tests/python/test_migration_0037.py`

**Interfaces:**
- Produces: 表 `source_unit_meta`、`source_unit_vectors`、`cognizer_group_membership`（DDL 见 spec §5.3、§3.2b）。

- [ ] **Step 1:** 写失败测试：迁移后三张表存在、主键与索引正确、`provenance` 的 CHECK 拒绝非法值、`status` 的 CHECK 拒绝非法值、`cognizer_group_membership` 主键含 `joined_at` 时同一 (组,成员) 不同时刻可并存、同一时刻重复写入被忽略。
- [ ] **Step 2:** 跑测试确认因表不存在而失败。
- [ ] **Step 3:** 写迁移 SQL，严格按 spec §5.3 与 §3.2b 的 DDL。
- [ ] **Step 4:** 重跑测试，全绿。

**Acceptance:** 新库迁移成功；旧库升级成功；`pytest tests/python/test_migration_0037.py -q` 全绿。

---

### Task 2: KnowledgeFrontier —— 成员 as-of 查询 + 幂等修复

**Files:**
- Modify: `include/starling/cognizer/knowledge_frontier.hpp`
- Modify: `src/cognizer/knowledge_frontier.cpp`
- Test: `tests/cpp/test_knowledge_frontier_groups.cpp`

**Interfaces:**
- Produces: `std::vector<std::string> group_members_as_of(tenant_id, group_id, as_of_iso8601) const`
- Produces: `void record_group_membership(...)` 改为写 `cognizer_group_membership`（含 `joined_at`/`left_at`/`recorded_at`），不再写 `cognizer_frontier_facts`
- Produces: `void end_group_membership(tenant_id, group_id, cognizer_id, left_at, conn)`

- [ ] **Step 1:** 写失败测试：as-of 查询在加入前返回空、加入后返回成员、离开后不再返回；同一 (组,成员,joined_at) 重复写入只留一行；历史成员在 `left_at` 之前仍可见。
- [ ] **Step 2:** 跑测试确认失败。
- [ ] **Step 3:** 实现两处改动；`visible_engrams_at` **不动**（spec 明确不扩展它）。
- [ ] **Step 4:** 回归：现有 frontier 测试全绿；确认 `cognizer_frontier_facts` 里旧的 membership 行不参与可见性（写一条断言测试固定这个事实）。

**Acceptance:** 新测试全绿；既有 ToM/frontier 测试无变化。

---

### Task 3: 契约 v3（audience / session_id / provenance）

**Files:**
- Modify: `src/extractor/claim_contract.cpp`（`source_turn` 校验与 `turn_prefix` 分派）
- Modify: `include/starling/extractor/claim_contract.hpp`
- Test: `tests/cpp/test_claim_source_turn_v3.cpp`

**Interfaces:**
- Produces: 前缀 `@starling/source-turn-v3 ` 的解析；字段必填规则见 spec §6.1（`speaker`/`text`/`audience`/`session_id`/`turn_index`/`provenance` 必填，`turn_id` 可空，`observed_at` 视 provenance）
- Produces: v1/v2 payload 仍可解析（`audience` 回填为 `{speaker}`）

- [ ] **Step 1:** 写失败测试：v3 合法载荷解析成功；缺 `audience`、空 `audience`、`provenance` 非法、`session_id` 缺失分别被拒且错误码可区分；v1 载荷仍可解析且 `audience={speaker}`；同批次内 `session_id` 冲突被拒。
- [ ] **Step 2:** 跑测试确认失败。
- [ ] **Step 3:** 实现 v3 解析与版本分派，保持 v1/v2 路径字节不变。
- [ ] **Step 4:** 全绿。

**Acceptance:** 新旧载荷都通过；旧路径的解析输出逐字节不变。

---

### Task 4: 写入路径（分组、展开、原子性）

**Files:**
- Modify: `src/retrieval/source_retriever.cpp`（`retain_source_turns` 及其分组）
- Modify: `include/starling/retrieval/source_retriever.hpp`
- Test: `tests/cpp/test_source_turns_write.cpp`
- Test: `tests/python/test_source_turns_write.py`

**Interfaces:**
- Produces: 分组键 `(session_id, 展开后的 audience 集合)`；组名 `group:*` 由 C++ 展开
- Produces: 单事务内完成：原文 engram → `source_unit_meta` 行 → 逐 agent presence → pending 向量行

- [ ] **Step 1:** 写失败测试：同一说话人跨场景不再合并；同一场景不同听众拆成两个 engram；`group:*` 展开为当时成员；空听众拒收；同一输入两次写入幂等（不产生新 engram）；注入故障（在写 presence 后抛异常）后整体回滚、无半成品。
- [ ] **Step 2:** 跑测试确认失败。
- [ ] **Step 3:** 实现写入路径；外层用 `TransactionGuard` 包住（`connection.hpp:44` 支持嵌套，不改内部提交方式）。
- [ ] **Step 4:** 全绿；确认旧 `source_documents` 写入路径仍工作（observer 评测依赖它）。

**Acceptance:** 新测试全绿；`scripts/run_socialmem_baseline.py` 的 sources 模式在固定行集上产出不变。

---

### Task 5: 抽取读权威听众（唯一触碰右脑的改动）

**Files:**
- Modify: `src/extractor/extractor.cpp`（`perceived_by` 赋值处）
- Test: `tests/cpp/test_perceived_by_authority.cpp`
- Test: `tests/python/test_socialmem_source_mode_regression.py`

**Interfaces:**
- Produces: 若 engram 有 `source_unit_meta` 记录，`perceived_by` 强制取自其 `audience`；抽取给出不同集合即 `perceived_by_conflict`

- [ ] **Step 1:** 写失败测试：预填 `perceived_by` 与声明听众冲突时被拒；顺序测试（听众先写 vs 抽取先写）证明先写者的集合胜出且反序被禁止；普通 `remember`（无 `source_unit_meta`）保持 `{holder, interlocutor}` 回退。
- [ ] **Step 2:** 跑测试确认失败。
- [ ] **Step 3:** 实现；在抽取入口加一条显式检查（不是只改默认值分支——`extractor.cpp:872-874` 只在空时填）。
- [ ] **Step 4:** 回归：两人场景下 `perceived_by` 逐字节不变；`does_X_know` 在固定用例上结果不变；SocialMemBench 0.7825 不下降；HiToM 嵌套信念不下降。

**Acceptance:** 新测试全绿；两个基准回归数值持平或更好。**若任一基准下降，停止并在本任务内修，不得带病推进。**

---

### Task 6: SourceVectorIndex 抽象 + SQLite 后端

**Files:**
- Create: `include/starling/vector/source_vector_index.hpp`
- Create: `src/vector/sqlite_source_vector_index.cpp`
- Modify: `CMakeLists.txt`（加源文件）
- Modify: `bindings/python/bind_10_embedding.cpp`（若需要暴露给评测）
- Test: `tests/cpp/test_source_vector_index.cpp`

**Interfaces:**
- Produces: `upsert(conn, key, meta, vec, model, dim)`、`search(conn, query_vec, k, scope) -> vector<SourceVectorHit>`、`erase(conn, tenant, engram_ref)`
- Produces: `SourceSearchScope{tenant_id, visible_engrams, as_of, include_unknown_time}`

- [ ] **Step 1:** 写失败测试：写入后能按相似度取回；`visible_engrams` 过滤在排序前生效；`dim`/`model` 不匹配的行不参与；`erase` 后不再返回；`search` 结果带 `(engram_ref, clause_id, speaker, session_id, score)`。
- [ ] **Step 2:** 跑测试确认失败。
- [ ] **Step 3:** 实现（全量扫描 + 排序，与现有 SQLite 实现同构）；`search` 需 `JOIN source_unit_meta` 取 `observed_at`/`session_id`。
- [ ] **Step 4:** 全绿。

**Acceptance:** 功能测试全绿；记录一次延迟基准（1k / 10k unit 的 p50），写进本文件。

**延迟基准（2026-10-21，Apple Silicon，`SourceVectorIndex.LatencyCurveIsRecorded`，dim=64，top_k=20，单连接全量扫描）：**

| unit 数 | p50（5 次取中位） |
|---|---|
| 1k | 0.53 ms |
| 10k | 5.95 ms |

曲线线性（10 倍数据约 11 倍耗时，≈0.6 µs/unit），与 §5.2 对"全量扫描 + 排序"的预期一致，未出现超线性退化。测试只打印数值、不设阈值——机器差异会让阈值变成假红；真正的护栏是曲线形状。

**落地结果：** 8 个功能用例 + 1 个延迟基准全绿。实现中修正了两处设计稿没写到的坑：(1) `SELECT` 漏选 `m.observed_at` 会让 C++ 侧的"无可信时间"判断永远为真，所有行都被跳过；(2) `include_unknown_time` 必须在 SQL 内判断——留到 C++ 判时 NULL 行已被 `WHERE` 丢弃，开关永远无效。空可见集按 fail-closed 处理（返回空），不是"不过滤"。

---

### Task 7: 嵌入生命周期（kind 分发）

**Files:**
- Modify: `src/embedding/embedding_worker.cpp`（扫描与写回按 kind 分支）
- Modify: `include/starling/embedding/embedding_worker.hpp`
- Test: `tests/cpp/test_embedding_worker_source_kind.cpp`

**Interfaces:**
- Produces: source 分支扫 `status IN ('pending','failed') AND retry_count < max_retry`；成功后置 `embedded`，失败 `retry_count+1`
- Produces: 模型/维度变更时清空 source 向量并**重置 `retry_count=0`**、状态置 `pending`

- [ ] **Step 1:** 写失败测试：pending→embedded；失败三次后转 failed 且不再被扫；模型变更后重置为 pending 且不被 `retry_count>=3` 卡死；语句分支行为不变。
- [ ] **Step 2:** 跑测试确认失败。
- [ ] **Step 3:** 实现分支；不改语句分支的 SQL 语义。
- [ ] **Step 4:** 全绿。

**Acceptance:** 新测试全绿；既有 embedding 测试无变化。

---

### Task 8: Planner 接入（候选、感知过滤、RRF、渲染、abstain、receipt）

**Files:**
- Modify: `include/starling/retrieval/retrieval_planner.hpp`（`SourceCandidate`、`SourceLaneDeps`、`source_entries`）
- Modify: `src/retrieval/retrieval_planner.cpp`
- Modify: `include/starling/retrieval/context_pack.hpp`（追加 `SOURCE` 标签）
- Modify: `bindings/python/bind_05_retrieval.cpp`（标签镜像、`source_entries`）
- Test: `tests/cpp/test_planner_source_lane.cpp`
- Test: `tests/cpp/test_context_pack.cpp`（追加用例，不改既有断言）

**Interfaces:**
- Produces: `PlannerQuery.source_lane`（`optional`，默认 `nullopt`）、`PlannerResult.source_entries`、`RetrievalReceipt.source_*` 计数
- Produces: `ContextPackLabel::SOURCE`（追加在末尾）

- [ ] **Step 1:** 写失败测试：
  - `source_lane=nullopt` 时 planner 输出与现状逐字节相同（固定行集快照）；
  - 开启后 source 行以 `[SOURCE] [日期] speaker: text` 出现，多行原文被转义、不产生伪造的 `[FACT]` 行；
  - 感知过滤**无条件**生效（`perspective == querier` 时也过滤）：X 召回不到自己不在场的话；
  - RRF(60) 名次计算与同分稳定排序；
  - 字节预算截断计数正确；
  - abstain：只有 source 且全低于 `tau_source` 时拒答；入选但被预算截掉不算证据；
  - `neutralize_recall_fence` 仍作用于 SOURCE 行。
- [ ] **Step 2:** 跑测试确认失败。
- [ ] **Step 3:** 实现 fetch → fuse → render → abstain；`tau_source` 未标定前 lane 不得开启（配置校验里强制）。
- [ ] **Step 4:** 全绿；审计所有 `ContextPackLabel` 的遍历与长度断言。

**Acceptance:** 新测试全绿；关闭 lane 时快照逐字节一致。

---

### Task 9: Python 返回结构

**Files:**
- Modify: `python/starling/memory.py`、`python/starling/dashboard/engine.py`
- Test: `tests/python/test_source_entries_return.py`

- [ ] **Step 1:** 写失败测试：`Memory.query` 返回 `{"row": ...}` 形态且 source 条目带 `kind:"source"`；Dashboard 返回扁平形态且同样带 source；statement 条目补 `kind:"statement"`；lane 关闭时返回结构与现状相同。
- [ ] **Step 2:** 跑测试确认失败。
- [ ] **Step 3:** 实现两处（注意两者结构不同，spec §4.6 已写明）。
- [ ] **Step 4:** 全绿。

**Acceptance:** 新测试全绿；关闭时 Python 返回与基线逐字段相同。

---

### Task 10: 摄入适配（transcript 作为测试消费者）

**Files:**
- Modify: `python/starling/dashboard/ingest_filter.py`（新增 `clean_turns_ts`，不动 `clean_turns`）
- Modify: `python/starling/dashboard/engine.py`（摄入点调用，generation 检查内）
- Test: `tests/python/test_ingest_source_lane.py`

- [ ] **Step 1:** 写失败测试：`clean_turns_ts` 返回 `(role, text, event_time, turn_index)` 且毫秒截断到秒；`chunk_dialogue` 不受影响；摄入在 generation 过期时作废、不回填；`source_missing` 语义一致。
- [ ] **Step 2:** 跑测试确认失败。
- [ ] **Step 3:** 实现；`audience` 填 `{user, assistant}`，`session_id` 用 job 已有的会话 id。
- [ ] **Step 4:** 全绿。

**Acceptance:** 新测试全绿；既有摄入测试无变化。

---

### Task 11: 开关与配置透传

**Files:**
- Modify: `python/starling/dashboard/config.py`、`python/starling/extractor/config.py`（若需）
- Modify: `src/memory/memory_ops.cpp`（`ConverseParams` 透传）
- Test: `tests/python/test_source_lane_switches.py`

- [ ] **Step 1:** 写失败测试：三个开关默认全 `false`；`render_time` 从属于 `enabled`；`tau_source` 未配置时拒绝开启；关闭时 planner 输出不变。
- [ ] **Step 2:** 实现。
- [ ] **Step 3:** 全绿。

**Acceptance:** 默认全关；配置校验拒绝"开启但未标定阈值"。

---

### Task 12: 全量回归与提交门

- [ ] **Step 1:** `python scripts/configure_build.py --build --test`；ctest 全绿，计数 ≥ Task 0 基线。
- [ ] **Step 2:** `--python-editable` 重装 `_core`，再跑 `pytest tests/python -q`，passed ≥ 基线。
- [ ] **Step 3:** 跑 SocialMemBench 固定行集，确认 0.7825 不下降。
- [ ] **Step 4:** 跑 HiToM 嵌套信念固定用例，确认不下降。
- [ ] **Step 5:** 用显式路径提交。

**Acceptance:** 四项全绿/持平；任何一项下降都停下修，不带病提交。

**执行结果（2026-10-21，afe8314）：**

| 项 | 结果 | 依据 |
|---|---|---|
| ctest | 1474/1474（基线 1416） | 实跑 |
| pytest | 2737 passed / 630 skipped（基线 2701） | 实跑；`--run-historical` 计数与 main 相同（149 failed / 465 errors，全部为 `build/socialmem_*` 封存产物缺失） |
| SocialMemBench 0.7825 | **未重跑，按构造论证不变** | 见下 |
| HiToM 嵌套信念 | **未重跑，按构造论证不变** | 见下 |

**两项基准为何不重跑、论证是否充分：**

本机没有 0.7825 的封存产物（`build/socialmem_20260917_focus_validation/`、`build/stage2/` 均不存在），无法做 spec 要求的"固定行集回放"；重采样一次真实分数既不是 2026-10-18 设计评审认可的守护方式，也要真实调模型。因此改为逐环节论证本分支没有改到这两条评测链路走到的代码：

1. **读路径未动**：0.7825 出自 `ObserverRetriever` 的 `sources` 模式。`git diff main...HEAD -- src/retrieval/source_retriever.cpp` 的 hunk 只落在 `retain_source_turns`（写路径）与文件头 include。
2. **写路径逐字节不变**：`run_socialmem_baseline.py:518-523` 与 `eval_ladder.py` 调 `retain_source_turns` 时 turn 都不带 `audience`，走 legacy 分支；`SourceTurnsWrite.LegacyPathUnchangedWithoutAudience` 钉住该分支不写任何新表。
3. **右脑抽取逐字节不变**：legacy 路径不写 `source_unit_meta` → `lookup_source_audience` 必为空 → `perceived_by` 走原分支。Task 5 的 A/B 转储（HEAD vs 改动，同一 legacy 场景）证明 statements / presence / frontier / source_documents 逐行一致。
4. **HiToM 走的是 `remember`**：`scripts/starling_tomeval_server.py:446,506` 只调 `mem.remember(story)`，不经 `retain_source_turns`、不设 `source_lane`，因此同样落在第 3 条的不变区间内。
5. **planner 关闭时不变**：所有新增分支都以 `q.source_lane.has_value()` 或 `!source_hits.empty()` 为前提；`PlannerSourceLane.DisabledLaneLeavesOutputUnchanged` 与 Python 端到端 `test_lane_closed_leaves_planner_untouched` 钉住。
6. **clear_tenant 新增三步**：只删三张新表；legacy 路径下这三张表为空，删除是空操作。

**未能验证的部分（如实记录）：** 上述是代码层面的不变性证明，不是一次新的分数读数。若需要实测数字，前提是恢复封存产物（或重建 1031 题基线库）并按 `docs/eval/2026-10-13-socialmem-stage2-reserved.md:163` 的复现命令重跑——这需要用户确认预算与产物来源。

---

### Task 13: 阶段 A 试点（`tau_source` 候选值）

**Files:** 评测脚本（`build/` 下，gitignored），按 spec §10.1 的预注册执行

- [ ] **Step 1:** 从 LongMemEval-S 全量取 92 道未用过的单会话题（脚本要复现筛选条件并断言 92）。
- [ ] **Step 2:** 每题构造正例 / 随机负例 / 难负例（难负例人工复核不含答案）。
- [ ] **Step 3:** 46/46 分层切分；标定半上在难负例 FPR ≤ 10% 约束下取 TPR 最大阈值。
- [ ] **Step 4:** 留出半报 TPR/FPR 与 Wilson 区间。**结论只作候选，不授权上线。**

**Acceptance:** 报告含两个 FPR（随机、难负）、两个半区的区间、以及每个阈值的样本量。

**执行结果（2026-10-21）：候选 `tau_source = 0.56`**。产物在 `build/dual_brain_20261017/spike/tau_a/`（gitignored）：`PREREG.md`（sha256 `bdd27762…`，测量前冻结）、`DEVIATIONS.md`、`plan.json`、`raw.jsonl`（276 条）、`REPORT.md`。嵌入 text-embedding-v4 / 1024 维，走仓内真实路径（retain → EmbeddingWorker → RetrievalPlanner）。92 题全测，0 失败、0 嵌入失败。

| 半区（n=46） | TPR（top-10 含证据） | TPR@1 | 随机负 FPR | 难负 FPR |
|---|---|---|---|---|
| 标定（选阈值） | 36 = 78.3% [64.4, 87.7] | 18 = 39.1% | 0 = 0.0% [0.0, 7.7] | 4 = 8.7% [3.4, 20.3] |
| **留出（只报一次）** | **34 = 73.9% [59.7, 84.4]** | 23 = 50.0% | **0 = 0.0% [0.0, 7.7]** | **2 = 4.3% [1.2, 14.5]** |

读法：
- **检索不是瓶颈，阈值是**：留出半 12 个漏检**全部**是"证据话轮已在 top-10、但 best < 0.56"；标定半 10 个漏检里 9 个同此。降 tau 能换回 TPR，代价是难负 FPR 上升（tau=0.50 时留出 TPR 44/46、难负 FPR 5/46）。扫描表见 `REPORT.md`。
- **难负与随机负差距大**：best 中位数正例 0.672 / 难负 0.382 / 随机 0.229。随机负在 0.44 以上即为 0，难负要到 0.62 才为 0——**以难负为准是对的**，用随机负标定会把阈值定得过松。
- **题型差异明显**：assistant 类留出 TPR 18/18，user 类只有 12/23。user 类是用户的短陈述，问句与之词面重合低、余弦偏低。偏好类每半只有 5 题，不可解读。
- **难负 FPR 区间上界 14.5% 超过 10% 的约束线**：点估计达标，但样本量撑不起"FPR ≤ 10%"的结论。这正是 spec 把本阶段定为试点、上线门槛交给阶段 B 的原因。

**本阶段不能回答的**：时序题（92 题中 0 题，spec 已列为已知偏移）；短陈述之外的分布；BEAM 上的分数分布是否与 LongMemEval 一致（嵌入分数对语料风格敏感，0.56 迁移到 BEAM 不是定论）。

**执行中修掉一个 C++ bug（0a196b9）**：真实嵌入冒烟时发现原文证据被语句侧 `tau_recall=0.25` 误杀（详见 DEVIATIONS.md §2）。若未修，阶段 B 会把所有余弦低于 0.25 的原文证据判为拒答。

---

### Task 14: 阶段 B 验收（BEAM-100K，上线门槛）

**Files:** 评测脚本（`build/` 下），预算已批（约 1-2e7 tokens）

- [ ] **Step 1:** 写 BEAM-100K 适配器；预注册判据（置信下界/上界 + 时序类单独达标）在跑前冻结并提交。
- [ ] **Step 2:** 走**完整 planner**（语句候选 + RRF + 预算 + abstain），测"支持答案的原文证据实际被渲染"的比例。
- [ ] **Step 3:** 报三档数值：完整案例 / 失败记错 / 最坏情形；时序类单列。
- [ ] **Step 4:** 按判据决定 lane 是否开启。

**Acceptance:** 判据达成才开启；未达成则保持关闭，且**不得**在验收集上调阈值重试。

**执行结果（2026-10-22）：C3 未通过，lane 保持关闭。** 详见 `docs/eval/2026-10-22-form-s-stage-b-beam-results.md`。C1 证据渲染率 76.3% [71.6, 80.5] 通过；C2 时序 95.0% [83.5, 98.6] 通过；C3 弃答错误作答 20.0% [10.5, 34.8]，上界超 25%，未通过。失败在作答层而非检索层：8 道失败中 7 道是 OFF 臂答对、ON 臂答错——前提部分为真的题，lane 召回了相关原话，模型据此作答而非弃答。修复方向是作答提示，不是阈值；BEAM-100K 已用掉，修复须在新验收集上验。

执行中另做的三件事：补齐 Task 11 漏掉的 `ConverseParams` 透传（785f7f9），让阶段 B 用生产提示作答；给 `OpenAIAdapter` 加 `thinking_type`（4762342），真正关掉推理，右脑 152 块抽取 0 失败；预注册修订 1（1d2f063）更正官方计分的事实错误，在任何裁判调用之前。

---

## 已知风险（实现期需盯）

1. **`source_unit_meta` 与 payload 的双写**：两者可能不一致。缓解：同事务写入 + 启动时一致性检查（unit 数 == payload 有效行数）。
2. **旧数据几乎不可召回**：迁移后 `audience={speaker}`。缓解：在迁移报告里给出受影响 unit 数，并明确这是保守选择。
3. **SQLite 全量扫描**：Task 6 的延迟基准若明显退化，需在验收前决定是否缩小默认 k。
4. **右脑改动的爆炸半径**：Task 5 是唯一触碰右脑的任务，它的两个基准回归是硬门。

## 基线

在 `671b74a`（本计划提交）上实测，2026-10-21：

- **ctest：1416/1416 通过，0 失败**（`python scripts/configure_build.py --build --test`，28.0 s）
- **pytest：2701 passed, 630 skipped**（`.venv/bin/python -m pytest tests/python -q`，173 s）；0 failed

后续所有回归以这两个数字为底线，只增不减。注意：仓库内历史计划记的是 2404 passed / ctest 1401，那是几个月前的数字，不可引用。
