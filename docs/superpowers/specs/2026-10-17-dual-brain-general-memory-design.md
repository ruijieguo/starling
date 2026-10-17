# 双脑记忆：在 Starling 上增设左脑（通用记忆）通道

日期 2026-10-17。状态：设计已逐节获用户确认，待用户审阅本文后进入实施计划。

## 目标与口径

补齐 Starling 的通用记忆能力，在国际记忆评测上取得有说服力的成绩；架构上从单脑扩到双脑：**左脑**擅长通用记忆（原文、事实、时间、更新），**右脑**即现有社会心智通道（归属、嵌套信念、共同基础、感知、再巩固）。双脑是一个系统，不对现有架构做颠覆性改动。

用户已裁定：
- **SOTA 口径 = 同 backbone 相对胜出**：同一回答模型（deepseek-v4-pro）、同一 embedder 下，超过自建的强基线臂与全上下文臂，按官方 judge 口径分项报告。不追厂商自报的绝对榜单值。
- **评测预算 = 开发级**：每轮 ≤ 5e7 tokens（LoCoMo 六台阶全量 + LongMemEval 分层子集 + BEAM-100K 子集）；LongMemEval-S 全量（S_star 约 2e8 tokens）和更大跑次需另行批准。
- 资金路径沿用 tokenkey.dev 的 deepseek-v4-pro 与 dashscope embedding。

## 评测目标

| 基准 | 角色 | 规模（本机实测） | 官方口径 | 注意 |
|---|---|---|---|---|
| LongMemEval-S cleaned | 主基准 | 500 题，每题约 12.2 万 tokens，500 套独立 haystack，不可摊薄建库 | 按题型 5 套 yes/no judge 模板，30 题 abstention | MIT；开发用每题型 20 题的分层子集 |
| LoCoMo | 开发主战场与对照 | 10 组共约 19 万 tokens，1540 非对抗题，10 库覆盖全部 | 官方 token-F1；社区 mem0 判分松 | CC BY-NC，只作评测；标注错约 6.4%；同时报 F1 与 judge |
| BEAM-100K | 分项能力与规模 | 20 会话 × 20 题，10 能力各 40 题 | rubric nugget judge | CC BY-SA；probing_questions 是 Python repr 字符串，需 `ast.literal_eval` |

不选：LongMemEval-M（每题 150 万 tokens）、MemoryAgentBench（事实列表与 ICL，非对话记忆，其冲突消解多跳全行业不超过 7%）、SocialMemBench（保留为右脑守护基准）。

对标线（子代理转述，**未独立核实**）：LongMemEval-S 上 Zep 71.2%（gpt-4o）、全上下文约 60%；LoCoMo 上 Zep 自跑 75.14、Memobase 75.78（gpt-4o-mini），mem0 论文里全上下文 72.9 高于其测的所有记忆系统。换 backbone 后不可直接比，必须自跑同 backbone 的 RAG 与全上下文臂。

## 现状诊断：六个漏斗

均已用代码或既有实测核对。

1. **抽取过窄且有损**：三条抽取 prompt 把文本压成受控谓词加短名词（OBJECT BREVITY），时间短语、数量、列表、长描述被削或不抽。free31 有 16/31 题库内无被支持语句。
2. **出生 VOLATILE，检索只看 consolidated**：statement_writer 写 volatile，planner 与向量检索只取 consolidated/archived，巩固靠低频采样。实测 31 库只有 13.5% 语句可见。
3. **检索信号单一**：只有 `subject predicate object` 文本的 cosine 与结构化精确匹配；无词法通道、无时间过滤。
4. **渲染丢原文与时间**：Context Pack 只渲染三元组、置信度、holder。
5. **巩固不产生抽象**：`op_compress` 只翻状态位；#38-C gist 在真实数据上惰性。
6. **单一 holder 语义**：通用事实被归于叙述者，多说话人被抹平，或按 speaker 拆库成本随人数线性增长。

结果：SocialMemBench free31 上 S_star 0/31 < S_rag 3/31 < S_full 10/31；现得分来源是 sources 模式（原文检索），结构层增益区间含零（WP2.B）。

## 参考系统

VoiceMem（xzf-thu/VoiceMem，Apache-2.0，2026-08 发布）是同构的“流式双脑”：左脑用 Schema 与 Entity 管事实（底层依赖 mem0ai），右脑管情绪、人格、跨实体关系；自报 LoCoMo 91.2%（Top-5）、每轮 430 记忆 token。其右脑只到情绪与人格，没有信念归属、嵌套 ToM、共同基础、感知可见性，而这些正是 Starling 右脑已有的部分。自报数字未复现，本设计不引用为对标线。

借鉴的机制均映射到 system_design §0.1 允许的原语：混合检索（BM25 + 稠密 + RRF）、原文一等召回（mempalace “索引不 gate 原档”）、三时间事实更新（graphiti）、增量会话摘要（graphiti SagaNode）、粗到细多粒度（EverOS HyperMem）。

覆盖说明：前沿系统与 GitHub 动量两路调研因网关中断未产出报告，该部分依赖仓内 2026-05 的历史调研（`docs/design/history/01–05`）和本机对 VoiceMem、mem0 benchmarks 的直接核实；MemOS、EverMemOS、LightMem、MIRIX 等 2026 年新进展未复核，实施前若需要再补。

## 架构

```
              Application (Memory.query / converse / dashboard)
                              │
                  RetrievalPlanner（扩展）
   parse → mask → plan → fetch ─┬─ statement_main / semantic_index / graph_index   右脑 lane（不变）
                                ├─ engram_chunks   （chunk 稠密）                  左脑 lane（新）
                                └─ lexical_index   （FTS5 BM25）                   左脑 lane（新）
                → fuse（跨 lane RRF）→ ground → abstain
                              │
              Context Pack：右脑 8 标签行 + 左脑 [SOURCE] 原文行（带时间）

   Statement Bus（单入口，不变）
     append_evidence → Engram ─┬─ Extractor（右脑三通道，不变）
                               ├─ chunk_projector（左脑）→ engram_chunks + FTS5 + chunk 向量
                               └─ general_fact_projector（左脑，可开关）→ 事实 Statement
   Replay：右脑 op 不变；左脑新增 episode_gist（P2）
```

左脑 = **Engram 的投影加一层可选事实 Statement**。chunk 层是 Projection Index 第 8 类（可由 engrams 全量重建，走 repair guard），不是事实源；事实 Statement 仍是 Statement 图的一部分。

### 不变量

1. Bus 单入口：两个新订阅者挂在写后泵（SAVEPOINT 隔离），不开旁路。
2. 事实权威只在 Statement 图：chunk 在 Context Pack 里标 `[SOURCE]`，不混入 `[FACT]`。
3. 六态机不变：chunk 无状态；左脑 lane 的 `visible_only=false`，对 volatile 事实 Statement 在 rerank 乘 `volatile_penalty`（默认 0.8，可配）；右脑 lane 保持 `visible_only=true`。
4. perspective filter 先于排序：chunk 命中按 `engram_ref ∈ visible_engrams_at(perspective)` 过滤，发生在 RRF 之前；holder 过滤与 frontier 过滤正交，两者都生效。
5. C++ 与 Python 边界：切块、索引、RRF、渲染、预算全在 C++；Python 只透传 `PlannerQuery.lanes` 和 prompt 配置数据。
6. 无新一等实体（§0.1）：chunk 是 Engram 的投影。

### chunk 带 holder（用户裁定）

`engram_chunks.holder_id` = 话轮 speaker 经 `resolve_or_register_cognizer` 归一后的 canonical name，与右脑 Extractor 同一套别名归一。仅对带显式 speaker 字段的话轮注册 cognizer；自由文本不做说话人猜测，holder = agent（self），以避免重现 7 月修过的认知体过度注册。左脑 lane 的范围由 `PlannerQuery.querier`、`perspective` 和显式 `allowed_holders` 决定，沿用 ObserverRetriever 的 allowlist 契约，不自动扩到租户全部。

## 写入路径

### chunk_projector（P1）

- 触发：`SubscriberPump::run_post_write` 新增订阅者，消费 `evidence.appended`，SAVEPOINT 隔离；失败只回滚该 engram，checkpoint 保留，下次 tick 重试。
- 切块（C++，确定性）：payload 符合 `claim_source_turn_payload` 合同时**一轮一块**，不跨话轮合并，超过 1200 字节的话轮按句边界再切；自由文本按段落或句群切到约 800–1200 字节，observed_at 取 created_at。
- 表 `engram_chunks(tenant_id, engram_ref, chunk_index, holder_id, speaker_surface, session_id, turn_index, observed_at, text, byte_start, byte_end)`，主键 `(tenant_id, engram_ref, chunk_index)`。
- 词法：`engram_chunks_fts` 为 FTS5 外部内容表，tokenizer `unicode61 remove_diacritics 2`，BM25 用内置 `bm25()`。
- 向量：新表 `chunk_vectors`，协议同 `statement_vectors`（缺行即待嵌入，failed 带 retry_count），由现有 EmbeddingWorker 在 `tick_all` 的 embed 阶段统一处理；`VectorIndex` 增 chunk 命名空间，主键前缀 `starling:chunk:v1:` 与 statement 命名空间隔离。
- 幂等与重建：engram 幂等命中不重切；`projection_rebuild_state` 登记 `engram_chunks`，`rebuild_projection("engram_chunks")` 从 engrams 重建并走 repair guard（rebuilt < ground_truth 则 `truncation_suspected`，不替换 active）。
- 能力：`ProfileCapability` 增 `lexical_fts5`，preflight 登记该名称；缺失时词法 lane 降级并写 `degraded_paths`，不阻断启动。
- 成本：写入零 LLM 调用，每 chunk 一次 embedding。

### general_fact_projector（P1，`ExtractionConfig.left_brain_facts` 开关）

- 对每个 engram 的全部 chunk **一次**单通道 LLM 抽取，输出 `{subject, predicate, object, event_time?, valid_from?}`；prompt 为配置数据，谓词归一为 `snake_case`，object 保留原文短语。
- 落库：`holder=agent`、`modality=BELIEVES`、`provenance=user_input`、evidence 指向 chunk 所在 engram，`observed_at=chunk.observed_at`。
- `ValidationPolicy` 增 `open_predicates`：为真时集外谓词不降 REVIEW_REQUESTED，并要求 `preserve_text_objects=true`；右脑三通道的受控核心集规则不变。
- 幂等沿用 `extraction_span_key`。
- **事实更新**走现有 ConflictProbe：同 `(holder, modality, subject, predicate)` 不同 object 且更晚，判 Superseding，沿用 supersedes 链与旧版 ARCHIVED；唯一补充是在同一事务内回填旧版 `valid_to = 新版 observed_at`。HISTORY 沿 supersedes 链取全链，FACT_LOOKUP 的时间过滤自动只留当前版。
- 不做 ADD/UPDATE/DELETE 式覆盖，不做 LLM 去重。

## 检索路径

`PlannerQuery` 增 `lanes`（`auto | right | left | both`，默认 `auto`）、`chunk_k`、`chunk_byte_budget`（默认 8000）、`volatile_penalty`。

| Intent | 右脑 lanes（不变） | 左脑 lanes（新，`auto`） |
|---|---|---|
| FACT_LOOKUP | statement_main + semantic_index | engram_chunks + lexical_index |
| HISTORY | statement_main（时间序）+ graph_index | engram_chunks + lexical_index，按 observed_at 排序 |
| PREFERENCE | statement_main（PREFERS） | engram_chunks + lexical_index |
| ABSTAIN_CHECK | 全部（exhaustive） | 全部 |
| BELIEF_OF_OTHER、META_BELIEF、COMMON_GROUND、COMMITMENT_DUE、NORM_LOOKUP | 现状 | 不开 |

- 两个新 scope 都在 SQL 下推 `holder_scope` 与 `observed_at ≤ as_of`。词法查询由 C++ 处理：去停用词，保留数字、日期、专名原形，中文按字。
- **fuse**：各 lane 内部先排序（右脑沿用 Affect-aware rerank，chunk 稠密用 cosine，词法用归一 bm25），再跨 lane **RRF（k=60）**；同一 engram 的 chunk 与 Statement 不去重，渲染时同一 chunk 只出现一次。`score_breakdown` 每行增 `lane` 与 `rrf_rank`，`candidate_counts` 增 `chunks_fetched / chunks_returned`。
- **abstain**：四条件不变，`max_score` 取 RRF 后最高分，左脑命中足够时不再因右脑 low_score 而弃答。
- **Context Pack**：新增第 9 个标签 `[SOURCE]`，格式 `[SOURCE] (holder, observed_at, session s / turn t) "原文…"`，按 observed_at 升序排在右脑 8 标签行之后，总字节受 `chunk_byte_budget` 约束，按整块截断；`neutralize_recall_fence` 同样作用于 SOURCE 行。
- `converse_prepare` 默认 `lanes=auto`，`recall_k` 语义保持。
- 评测专用的 ObserverRetriever（sources/hybrid）不动，历史回放依赖它；新 lane 不复用它的 lane 启发式（代码自注为 EXPERIMENTAL，由 SocialMemBench 开发集调出）。

## 巩固（P2，默认关）

`episode_gist` 为 Replay `run_idle/run_sleep` 的新 op：对同 `(holder, session_id)` 的新 chunk 增量续写摘要（只喂 `created_at > last_summarized_at` 的 chunk 加旧摘要），落为 Statement `provenance=replay_derived, predicate=session_gist`，`derived_from` 指向对应事实 Statement，并作为粗粒度 chunk 进稠密索引，形成粗到细两级召回。复用 `write_gist_proposals` 的 Bus::write 与门控骨架，不复用 #38-C 的跨 holder 规范归纳语义。

## 评测与验收

- **适配器**：`longmemeval_official`（cleaned JSON，session 按 haystack_dates 排序，role→speaker，user→`user`、assistant→agent）、`locomo_official`（每组一库，speaker_a/b 为 holder，`session_N_date_time` 解析为 observed_at，cat5 排除但保留字段）、`beam`（10 能力作 subset）。
- **judge 注册表**：`eval_official_protocol` 按基准注册 `official` 与 `community` 两套模板（LongMemEval 官方 5 模板加 mem0 松模板；LoCoMo 官方 F1 加 mem0 judge；BEAM nugget rubric），同一回答双裁，α_judge 对抗审计照跑。
- **阶梯新增两臂**：`S_left`（`lanes=left`）、`S_dual`（`lanes=both`）；`S_star` 保持“仅右脑”。
- **预注册判据**：
  - 防守：LoCoMo 全量 `S_dual ≥ S_rag − α_judge` 且 `S_dual ≥ S_star`。
  - 进攻：LoCoMo 全量与 LongMemEval 分层子集上 `S_dual − max(S_full, S_rag) ≥ max(5pp, α_judge)`，网络级重采样区间不跨零；knowledge-update、temporal 子集单列；abstention 正确率单列，不混入总分。
  - 成本必报：写入 token、每题检索字节、p50/p95 延迟。
- **守护**：SocialMemBench 1031 题来源路径读数（0.7825）不得下降；ctest 与 pytest 全绿；新增 parity 钉测（RRF 顺序、切块确定性、FTS5 缺失降级、chunk 命名空间隔离）。
- 纪律沿用既有规则：同 backbone、预注册读法、开发/保留切分、不对同一批题反复调参、不晋升则如实降级。

## 路线

| 阶段 | 内容 | 主要落点 |
|---|---|---|
| P0 评测地基（约 1 周） | 三基准适配器、双 judge、S_left/S_dual 臂；跑 S0 / S_rand / S_full / S_rag / S_star 基线，量化“现在差多少” | `scripts/eval_adapters.py`、`eval_official_protocol.py`、`eval_ladder.py`、`eval_ladder_pipeline.py` |
| P1 左脑通道（约 3 周） | migration `0037_engram_chunks`（表、FTS5、chunk_vectors、projection 注册）；`chunk_projector`；稠密与词法检索器；planner 的 fetch/fuse/render；`VectorIndex` chunk 命名空间；EmbeddingWorker 读 chunk 队列；`lexical_fts5` capability；`general_fact_projector`、`open_predicates`、supersede 回填 valid_to、事实 prompt；绑定透传；dashboard brain_map 增“左脑原文”区 | `include/starling/{projection,retrieval,vector}/`、`src/…`、`bindings/python/bind_05_retrieval.cpp`、`bind_06_extractor.cpp`、`migrations/0037` |
| P2 巩固与规模（约 2 周） | `episode_gist` op、粗粒度 chunk 入索引、弃答校准、BEAM 子集与规模曲线、写入成本报告 | `src/replay/episode_gist.cpp`、`replay_scheduler.cpp` |

每阶段：中文设计 → RED 测试 → C++ 实现 → `python scripts/configure_build.py --build --test`，再 `--python-editable` → pytest → 预注册评测。文档同步：`system_design.md` §2.4 增“左脑 General Memory”行，`13_retrieval.md` 增 lanes/RRF/`[SOURCE]`，`04_substrate.md` 增第 8 类投影，`06_hippocampus.md` 注明 chunk 投影。

## 风险与未验证项

- **回答 token 上升**：`[SOURCE]` 原文进上下文，靠 `chunk_byte_budget` 约束；预算对分数的敏感度需 P0 基线实测。
- **全上下文臂很强**：LoCoMo 每组仅约 2 万 tokens，整段可塞，“打败 S_full”可能在 LoCoMo 上不成立而只在 LongMemEval 成立，预注册判据按基准分别判定，不合并。
- **事实层可能无增益**：WP2.B 显示结构层对 QA 增益区间含零；P1 内事实层可开关，且 S_left（仅 chunk）与加事实层两臂分开归因，若无增益则默认关闭并如实记录。
- **LongMemEval 成本**：500 套独立 haystack，建库无法摊薄；开发期只用分层子集。
- **holder 注册压力**：多说话人输入会注册 cognizer，仅限显式 speaker 字段。
- **FTS5 中文**：`unicode61` 对中文按字切，召回精度有限；基准均为英文，中文留待后续换 trigram。
- **judge 口径**：官方口径与社区松口径必须双报；对外不引用 mem0 自报的 92.5/94.4。
- **调研覆盖**：见“参考系统”末段。

## 待实施前确认

无阻塞问题；实施计划阶段需再确认两点：(1) P0 基线跑次的具体题数与 seed 数；(2) 是否在本仓新开分支或 worktree 落地（现位于 main）。
