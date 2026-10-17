# 双脑记忆：在 Starling 上增设左脑（通用记忆）通道

日期 2026-10-17。状态：v2，已按第三方（Codex）评审修订；待用户审阅后进入实施计划。修订依据与逐条处置见文末“评审记录”。

## 目标与口径

补齐 Starling 的通用记忆能力，在国际记忆评测上取得有说服力的成绩；架构上从单脑扩到双脑：**左脑**擅长通用记忆（原文、时间、更新），**右脑**即现有社会心智通道（归属、嵌套信念、共同基础、感知、再巩固）。双脑是一个系统，不对现有架构做颠覆性改动。

用户已裁定：
- **SOTA 口径 = 同 backbone 相对胜出**：同一回答模型（deepseek-v4-pro）、同一 embedder 下，超过自建的强基线臂与全上下文臂，按官方 judge 口径分项报告。不追厂商自报的绝对榜单值。
- **评测预算 = 开发级**：每轮 ≤ 5e7 tokens。记账口径见“评测预算”一节，LongMemEval 开发期只用分层子集。
- 资金路径沿用 tokenkey.dev 的 deepseek-v4-pro 与 dashscope embedding。
- **事实层后移**（v2 修订，用户 2026-10-17 确认）：P1 只做 chunk 投影与一条稠密 lane；开放谓词事实层与 `episode_gist` 推迟到 chunk 层有实测增益之后，与查询改写合并为 P2。

## 评测目标

| 基准 | 角色 | 规模（本机实测） | 官方口径 | 注意 |
|---|---|---|---|---|
| LongMemEval-S cleaned | **主基准，进攻判据主要押在这里** | 500 题，每题约 12.2 万 tokens，500 套独立 haystack，不可摊薄建库 | 按题型 5 套 yes/no judge 模板，30 题 abstention | MIT；开发用每题型 20 题的分层子集 |
| LoCoMo | 开发迭代与“不劣化”守护 | 10 组共约 19 万 tokens，1540 非对抗题，10 库覆盖全部 | 官方 token-F1；社区 mem0 判分松 | CC BY-NC，只作评测；标注错约 6.4%；同时报 F1 与 judge |
| BEAM-100K | 分项能力 | 20 会话 × 20 题，10 能力各 40 题 | rubric nugget judge | CC BY-SA；probing_questions 是 Python repr 字符串，需 `ast.literal_eval`；P2 起接入 |

不选：LongMemEval-M、MemoryAgentBench、SocialMemBench（保留为右脑守护基准）。

对标线（子代理转述，**未独立核实**）：LongMemEval-S 上 Zep 71.2%（gpt-4o）、全上下文约 60%；LoCoMo 上 Zep 自跑 75.14、Memobase 75.78（gpt-4o-mini），mem0 论文里全上下文 72.9 高于其测的所有记忆系统。换 backbone 后不可直接比，必须自跑同 backbone 的 RAG 与全上下文臂。

## 现状诊断：六个漏斗

均已用代码或既有实测核对（Codex 评审再次核对了 1–3）。

1. **抽取过窄且有损**：三条抽取 prompt 把文本压成受控谓词加短名词（OBJECT BREVITY）。free31 有 16/31 题库内无被支持语句。
2. **出生 VOLATILE，检索只看 consolidated**：`statement_writer.cpp:173-196` 写 volatile；`retrieval_planner.cpp:72-78` 的 `kStableTail` 与 `sqlite_blob_vector_index.cpp:60-68` 都要求 consolidated/archived。实测 31 库只有 13.5% 语句可见。注意 `visible_only` 并非唯一开关：`semantic_retriever.cpp:35-47` 无条件置 `visible_only=true`，planner 另有 `kStableTail`、时间界、claim 证据校验和 frontier mask。
3. **检索信号单一**：只有 `subject predicate object` 文本的 cosine 与结构化精确匹配；无词法通道、无时间过滤。
4. **渲染丢原文与时间**：Context Pack 只渲染三元组、置信度、holder。
5. **巩固不产生抽象**：`op_compress` 只翻状态位；#38-C gist 在真实数据上惰性。
6. **单一 holder 语义**：通用事实被归于叙述者，多说话人被抹平。

结果：SocialMemBench free31 上 S_star 0/31 < S_rag 3/31 < S_full 10/31；现得分来源是 sources 模式（原文检索），结构层增益区间含零（WP2.B）。**漏斗 1 的根因不被“再加一道 LLM 抽取”解决**，这是事实层后移的依据。

## 参考系统

VoiceMem（xzf-thu/VoiceMem，Apache-2.0，2026-08 发布）是同构的“流式双脑”：左脑用 Schema 与 Entity 管事实（底层依赖 mem0ai），右脑管情绪、人格、跨实体关系；自报 LoCoMo 91.2%（Top-5）、每轮 430 记忆 token。其右脑没有信念归属、嵌套 ToM、共同基础、感知可见性。自报数字未复现，不作对标线。

借鉴的机制均映射到 system_design §0.1 允许的原语：混合检索（BM25 + 稠密 + RRF）、原文一等召回（mempalace “索引不 gate 原档”）、三时间事实更新（graphiti）、增量会话摘要（graphiti SagaNode）、粗到细多粒度（EverOS HyperMem）。

覆盖说明：前沿系统与 GitHub 动量两路调研因网关中断未产出报告，该部分依赖仓内 2026-05 历史调研和本机对 VoiceMem、mem0 benchmarks 的直接核实；MemOS、EverMemOS、LightMem、MIRIX 等新进展未复核。

## 架构

```
              Application (Memory.query / converse / dashboard)
                              │
                  RetrievalPlanner（扩展，需类型化候选）
   parse → mask → plan → fetch ─┬─ statement_main / semantic_index / graph_index   右脑 lane（不变）
                                └─ engram_chunks   （chunk 稠密）                  左脑 lane（P1，新）
                → fuse（跨 lane，类型化候选）→ ground → abstain
                              │
              Context Pack：右脑 8 标签行 + 左脑 [SOURCE] 原文行（带时间）

   Statement Bus（单入口，不变）
     append_evidence → Engram ─┬─ Extractor（右脑三通道，不变）
                               └─ chunk_projector（左脑，P1）→ engram_chunks + chunk 向量
   P2：lexical_index（FTS5）、general_fact_projector、episode_gist、查询改写
```

左脑 = **Engram 的只读投影**。chunk 层是 Projection Index 第 8 类（可由 engrams 全量重建，走 repair guard），不是事实源。

### 不变量

1. Bus 单入口：`chunk_projector` 不开旁路；其触发边界见“写入路径”。
2. 事实权威只在 Statement 图：chunk 在 Context Pack 里标 `[SOURCE]`，不混入 `[FACT]`。
3. 六态机不变：chunk 无状态。右脑 lane 保持只取 consolidated/archived。
4. **perspective filter 先于排序，且授权在话轮粒度**（v2 重写，见下）。
5. C++ 与 Python 边界：切块、索引、融合、渲染、预算全在 C++；Python 只透传配置与 prompt 数据。
6. 无新一等实体（§0.1）：chunk 是 Engram 的投影。

### chunk 授权模型（v2 重写）

v1 写“chunk 命中按 `engram_ref ∈ visible_engrams_at(perspective)` 过滤，天然兼容”是错的：现有 mask 对 `evidence_json` 做**子串匹配**（`retrieval_planner.cpp:342-358`），不是类型化授权；且一个 engram 可含多说话人，engram 级可见不等于话轮级可见。

v2 规则：
- **授权单位 = chunk（话轮）**。`engram_chunks` 每行带 `speaker_surface` 与归一后的 `holder_id`。左脑 lane 只返回 `holder_id ∈ allowed_holders` 的 chunk，`allowed_holders` 为显式授权集合，沿用 ObserverRetriever 的契约（它已在 `source_retriever.cpp:1396-1412` 对每个话轮做 `speaker != holder 则丢弃`），不自动扩到租户全部。
- **perspective 视角下的可见性**用类型化 join，不用子串：`engram_chunks.engram_ref IN (SELECT engram_ref FROM <KnowledgeFrontier 可见 engram 集>)`，在候选生成的 SQL 里下推，发生在排序之前。右脑 lane 的子串 mask 不动（既有行为，另列为已知缺陷，不在本设计范围内修）。
- 混合说话人 engram 必须有测试：同一 engram 内 A、B 两个说话人的 chunk，对仅授权 A 的 querier 只返回 A 的 chunk。
- chunk 带 holder（用户 2026-10-17 裁定）：`holder_id` = speaker 经 `resolve_or_register_cognizer` 归一后的 canonical name；仅对带显式 speaker 字段的话轮注册 cognizer，自由文本 holder = agent（self），避免重现认知体过度注册。

## 写入路径（P1）

### chunk_projector

- **触发边界（v2 重写）**：v1 写“订阅 `evidence.appended` 事件”不准确。泵（`SubscriberPump::run_post_write`）是固定顺序调用的 SAVEPOINT 隔离订阅者列表，每个订阅者自带 checkpoint 并自己扫 outbox，泵本身不分发事件；`append_evidence` 自己 commit 后**不调用泵**（`bus.cpp:322-381`）。生产中泵只在 `memory_ops.cpp:150`（remember 尾部）与 `Bus::write` 末尾（`bus.cpp:592`）被调用。因此 `chunk_projector` 实现为**checkpoint 扫描式订阅者**（照 `belief_tracker` 处理 `evidence.appended` 的方式，`belief_tracker.cpp:113-135`），挂入泵的第 8 位；并且把它也加入 `tick_all` 的一个阶段作为兜底，保证仅调用 `append_evidence` 的路径（如评测驱动、OpenClaw 外部写入）也能在下次 tick 追平。投影滞后以 `projection_lag_events` 暴露。
- **切块（C++，确定性）**：payload 符合 `claim_source_turn_payload` 合同时一轮一块，超过 1200 字节的话轮按句边界再切（按 UTF-8 码点边界，不切断多字节字符）；自由文本按段落或句群切到约 800–1200 字节，observed_at 取 created_at。
- 表 `engram_chunks(tenant_id, engram_ref, chunk_index, holder_id, speaker_surface, session_id, turn_index, observed_at, text, byte_start, byte_end)`，主键 `(tenant_id, engram_ref, chunk_index)`。
- **向量（v2 修正）**：新表 `chunk_vectors`，但**不声称复用 EmbeddingWorker 现有实现**。现有 worker 的待嵌入查询是 `statements ⟕ statement_vectors`（`embedding_worker.cpp:214-240`），并做 statement 邻居的模式分离。P1 先把待嵌入队列抽成按 kind 分发的泛型接口（`statement` 与 `chunk` 各自的取数、渲染、命名空间、重试与健康计数），chunk 不做模式分离。`VectorIndex` 增 chunk 命名空间，主键前缀 `starling:chunk:v1:`，与 statement 隔离。
- 幂等与重建：engram 幂等命中不重切；`projection_rebuild_state` 登记 `engram_chunks`，`rebuild_projection("engram_chunks")` 从 engrams 重建并走 repair guard。
- 成本：写入零 LLM 调用，每 chunk 一次 embedding。队列深度、吞吐、重试与滞后进入验收指标（见“评测与验收”）。

## 检索路径（P1）

`PlannerQuery` 增 `lanes`（`auto | right | left | both`，默认 `auto`）、`chunk_k`、`chunk_byte_budget`（默认 8000）、`allowed_holders`。

| Intent | 右脑 lanes（不变） | 左脑 lane（新，`auto`） |
|---|---|---|
| FACT_LOOKUP | statement_main + semantic_index | engram_chunks |
| HISTORY | statement_main（时间序）+ graph_index | engram_chunks，按 observed_at 排序 |
| PREFERENCE | statement_main（PREFERS） | engram_chunks |
| ABSTAIN_CHECK | 全部（exhaustive） | engram_chunks |
| BELIEF_OF_OTHER、META_BELIEF、COMMON_GROUND、COMMITMENT_DUE、NORM_LOOKUP | 现状 | 不开 |

- **类型化候选（v2 新增）**：现有 `FetchedRow`、`RerankCandidate`、`StatementRow`、按 statement ID 去重、claim 证据校验、标签分类全是 statement 形状（`retrieval_planner.cpp:372-385`）。P1 引入 `Candidate = StatementCandidate | ChunkCandidate` 的 variant，各自带 identity（statement id 或 `(engram_ref, chunk_index)`）、来源 lane、分数、可见性证明。fuse 在 variant 上做；这是一次 planner 内部重构，不是“加一条 lane”，工作量计入 P1。
- **融合**：P1 只有一条左脑 lane，用 **RRF（k=60）** 在右脑候选与左脑候选之间融合；同一 engram 的 chunk 与 Statement 不去重，渲染时同一 chunk 只出现一次。`score_breakdown` 每行增 `lane` 与 `rrf_rank`。
- **abstain**：四条件不变，`max_score` 取融合后最高分。
- **Context Pack**：新增第 9 个标签 `[SOURCE]`，格式 `[SOURCE] (holder, observed_at, session s / turn t) "原文…"`，按 observed_at 升序排在右脑 8 标签行之后，总字节受 `chunk_byte_budget` 约束，按整块截断；`neutralize_recall_fence` 同样作用于 SOURCE 行。
- `converse_prepare` 默认 `lanes=auto`，`recall_k` 语义保持。
- 评测专用的 ObserverRetriever（sources/hybrid）不动，历史回放依赖它；新 lane 不复用它的 lane 启发式（代码自注为 EXPERIMENTAL）。
- **已知既有缺陷，P0 先修**：`retrieval_planner.cpp:312-315` 的 HISTORY 沿 supersedes 补链处，`if (!have.contains(other)) { continue; }` 跳过了所有尚未取到的邻居，导致 supersedes 链永远补不上。本设计的 HISTORY 依赖此路径，必须先修并加回归测试。

## P2：查询侧与事实层（在 P1 有实测增益后启动）

原因：LongMemEval 的 temporal-reasoning（133 题）与 knowledge-update（78 题）占 42%，仅靠 chunk 召回加 RRF 解决不了——RRF 不看时间有效性、最新性与更新状态（Codex P2）。

- **查询改写与时间意图（独立于事实层）**：识别 as-of / latest / earlier-than 等时间意图，抽出时间约束与实体，生成多路子查询；这是 C++ 内核功能，prompt 为配置数据。
- **当前态 vs 历史态**检索策略显式化：HISTORY 取全链，FACT_LOOKUP 取最新有效版本。
- **词法 lane（FTS5）**：`lexical_index`。**前置**：构建期检测 SQLite 的 `SQLITE_ENABLE_FTS5`（CMake 里用 `check_c_source_compiles` 或 `pragma compile_options`），缺失时不创建虚表，因为 `CREATE VIRTUAL TABLE ... USING fts5` 会在迁移期失败，来不及运行期降级；同时 `ProfileCapability` 增 `lexical_fts5`。tokenizer 对英文用 `unicode61`；**中文不适用**：实测 `unicode61` 把整句中文当一个 token，`MATCH '素食'` 返回 0，`trigram` 对 ≥3 字可匹配、2 字仍为 0。基准均为英文，中文词法检索不在本轮范围。外部内容表须同时给出 insert/update/delete 触发器、重建与 repair 验证，否则索引会静默漂移。
- **开放谓词事实层**（`general_fact_projector`）：保持 spec v1 的设计要点（单通道、`open_predicates`、`preserve_text_objects`、span_key 幂等），并补足 Codex 指出的缺口：supersede 回填 `valid_to` 需定义取值（新版 `observed_at`）、并发到达的两个更新如何定序、replay/rebuild 是否可复现同一区间历史；回填目前是合法的（migrations 0006/0007 的触发器不保护 `valid_to`），但是新的时间变更路径，需单独测试。
- **`episode_gist`**：保持 v1 设计，推迟到事实层有增益之后。

## 评测与验收

- **适配器**：`longmemeval_official`、`locomo_official`（cat5 排除但保留字段）；`beam` 在 P2 加。
- **judge 注册表**：`eval_official_protocol` 按基准注册 `official` 与 `community` 两套模板，同一回答双裁。**judge 纪律（v2 新增）**：模板与阈值在跑前冻结并记 sha256；裁判看不到臂名；回答顺序随机化；α_judge 用事先定好的对抗审计流程算，不当作通用容差。
- **阶梯新增臂**：`S_left`（`lanes=left`）、`S_dual`（`lanes=both`）；`S_star` 保持“仅右脑”。
- **同 backbone 的完整定义（v2 修订）**：除回答模型与 embedder 外，每臂必须报告并尽量对齐：抽取调用次数与 token、检索上下文字节、重试次数、延迟。P1 的 S_left 不含 LLM 抽取，其与 S_rag 的差只来自“原文 chunk + 类型化融合 + 授权”，这是 P1 归因干净的原因。
- **预注册判据（v2 重写，按基准分别判定，不合并）**：
  - **LongMemEval-S 分层子集（主）**：进攻判据 `S_dual − max(S_full, S_rag) ≥ max(5pp, α_judge)`，网络级重采样区间不跨零；temporal-reasoning、knowledge-update、multi-session、abstention 各自单列；abstention 报真阳/假阳率而非仅准确率。
  - **LoCoMo（守护）**：只判“不劣化”：`S_dual ≥ S_rag − α_judge` 且 `S_dual ≥ S_star`。**不设“超过全上下文”的进攻门槛**——每组仅约 2 万 tokens，全上下文臂是上限参照，不是要击败的对象；按类别（multi-hop / temporal / open-domain / single-hop）分项报告，并报告在多跳等全上下文臂较弱的类别上是否有净增。
  - 成本必报：写入 token、每题检索字节、p50/p95 延迟、投影滞后。
- **泄漏与留出**：开发子集与保留子集在跑前固定；保留子集每个里程碑只跑一次；任何机制改动不得针对具体失败题加规则（沿用 06-28 纪律）。`volatile_penalty` 不再作为 P1 参数（事实层后移后无 volatile 左脑候选）。
- **守护基准**：SocialMemBench 1031 题来源路径读数（0.7825）不得下降；ctest 与 pytest 全绿；新增 parity 钉测（切块确定性含 UTF-8 边界、混合说话人授权、chunk 命名空间隔离、RRF 顺序、投影重建 repair guard、HISTORY 链补全回归）。
- **可重放 trace**：每题落盘检索到的 ID（statement / chunk）、字节预算占用、模型调用次数，使任一结论可复核。

## 评测预算（v2 统一记账）

口径：**输入 tokens 总和，含历史灌入、抽取、答题、judge，不含重试**；embedding 单列。

| 配置 | 估算 | 说明 |
|---|---|---|
| LoCoMo 全量，S0/S_rand/S_full/S_rag/S_left/S_dual 六臂（P1 无抽取）| ≈ 3e7 | 答题 1540 × 6 臂 × 约 2–8K；历史极小；judge 双口径 |
| LongMemEval-S 分层子集 120 题（每题型 20），同上六臂 | ≈ 3e7 | S_full 臂 120 题 × 约 12.2 万 = 1.46e7；S_rag/S_left/S_dual 三臂以检索上下文为主（每题约 2–8K，合计约 3e6）；S_rag/S_left/S_dual 的建库 embedding 另计（120 题 × 12.2 万 = 1.46e7 tokens 的 embedding，不计入输入 tokens）；judge 双口径约 2e6 |
| LongMemEval-S 全量 S_full 一臂 | ≈ 6.1e7 | 单臂已超开发级预算，只在里程碑收口时按需申请 |
| S_star 含右脑三通道抽取（不在 P1 新增）| 另计 | 沿用既有阶梯数据，不重跑 |

因此：**开发级预算只覆盖 LoCoMo 全量加 LongMemEval 子集，LongMemEval 全量一律需另批**。v1 的“S_star≈2e8”仅指含三通道抽取的右脑臂，P1 不新增该臂。

## 路线（v2）

| 阶段 | 内容 | 主要落点 |
|---|---|---|
| P0 前置与评测地基（约 1.5 周）| 修 HISTORY 邻居跳过 bug；三基准适配器（LongMemEval/LoCoMo 先）与双 judge 注册及冻结；S_left/S_dual 臂与可重放 trace；跑 S0/S_rand/S_full/S_rag/S_star 基线，量化“现在差多少”；预注册开发/保留切分 | `retrieval_planner.cpp`、`scripts/eval_*` |
| P1 左脑 chunk 通道（约 3 周）| migration `0037_engram_chunks`（表、`chunk_vectors`、projection 注册）；checkpoint 扫描式 `chunk_projector` 与 `tick_all` 兜底；泛型待嵌入队列；`VectorIndex` chunk 命名空间；类型化 Candidate 与 RRF fuse；话轮级授权；`[SOURCE]` 渲染；绑定透传；dashboard brain_map 增“左脑原文”区 | `include/starling/{projection,retrieval,vector,embedding}/`、`src/…`、`bindings/python/bind_05_retrieval.cpp`、`migrations/0037` |
| P2 查询侧与事实层（约 3 周，P1 有增益才启动）| 构建期 FTS5 检测与 `lexical_index`；查询改写与时间意图；当前态/历史态策略；开放谓词事实层与 supersede 回填 `valid_to`；BEAM 接入 | `CMakeLists.txt`、`src/retrieval/`、`src/projection/general_fact_projector.cpp`、`src/bus/bus.cpp` |
| P3 巩固与规模（约 2 周，视 P2）| `episode_gist`、弃答校准（留出集上校准阈值）、答案落地校验、写入成本报告、规模曲线 | `src/replay/episode_gist.cpp` |

每阶段：中文设计 → RED 测试 → C++ 实现 → `python scripts/configure_build.py --build --test`，再 `--python-editable` → pytest → 预注册评测；不晋升则如实降级。文档同步：落地时把 system_design 四份前向入口小节并入对应子系统正文。

## 风险与未验证项

- **全上下文臂很强**：LoCoMo 上很可能无法超过，已将其降为“不劣化”守护；LongMemEval-S 是否能超过全上下文臂仍需 P0 基线实测。
- **chunk 层可能只追平 S_rag**：左脑 chunk 与 S_rag 的差只有类型化融合、授权与渲染，若 P0 基线显示 S_rag 已接近天花板，P1 的增益空间有限，需在 P0 后复评是否继续。
- **回答 token 上升**：靠 `chunk_byte_budget` 约束，敏感度需 P0 实测。
- **planner 重构风险**：类型化 Candidate 触及 fetch/fuse/rerank，必须由现有 planner 测试和 SocialMemBench 守护读数兜底。
- **既有缺陷**：右脑 mask 的子串匹配与 HISTORY 邻居跳过；前者本设计不修，后者 P0 修。
- **调研覆盖**：见“参考系统”末段。
- **judge 口径**：官方与社区口径双报；对外不引用 mem0 自报的 92.5/94.4。

## 评审记录（Codex，2026-10-17）

第三方评审结论为 RETHINK；其核心理由（P1 范围过大、混入多个未经验证的机制）经核实成立，其重排方案与本设计方案 A 同向，故按“收窄范围的 PROCEED WITH CHANGES”处置。完整输出存于本机 `build/dual_brain_20261017/codex_review/`（未入库）。

| Codex 发现 | 处置 |
|---|---|
| chunk 授权不安全（P1）| 成立；授权模型重写为话轮粒度，沿用 ObserverRetriever 的 speaker 校验，perspective 用类型化 join |
| 事件路径不保证运行（P1）| 部分成立；改为 checkpoint 扫描式订阅者加 `tick_all` 兜底，写明泵的真实调用点 |
| FTS5 迁移期失败（P1）| 成立；移至 P2，前置构建期检测 |
| 预算矛盾（P1）| 成立；统一记账口径，LongMemEval 开发期只用子集 |
| LoCoMo +5pp 不可达（P1）| 成立；LoCoMo 降为守护判据，进攻判据押 LongMemEval |
| 事实层重复抽取瓶颈（P1）| 采纳；用户确认后移到 P2 |
| planner 需类型化候选（P1）| 采纳；P1 内计入工作量 |
| HISTORY 邻居跳过 bug（P2）| 已核实为既有缺陷；纳入 P0 |
| RRF 不足以处理时序/更新（P2）| 采纳；P2 增查询改写与当前态/历史态策略 |
| 评测臂混淆、judge 纪律、弃答协议、trace（P2）| 采纳；评测一节补写 |
| `valid_to` 回填并发语义（P2）| 采纳；写入 P2 事实层前置项 |
| `episode_gist` 过早（P2）| 采纳；推迟 |
| `unicode61` 中文行为（P3）| 成立且更严重：已实测整句成一个 token；更正并将中文排除出本轮 |
| UTF-8 边界、chunk 策略、`volatile_penalty` 随意（P3）| UTF-8 边界入测试；`volatile_penalty` 随事实层后移而撤出 P1 |

Codex 未采纳的部分：其“共享 embedding 队列不可行”的判断正确，但 v1 写的是“复用协议”，v2 已改为明确抽出泛型队列接口，而非复用实现。

## 待实施前确认

1. P0 基线跑次的具体题数、seed 数与保留切分划定（实施计划阶段确定）。
2. 是否在本仓新开分支或 worktree 落地（当前文档在分支 `docs/dual-brain-general-memory-design`）。
3. P0 基线若显示 S_rag 已接近天花板，是否仍继续 P1（届时用数据决定）。
