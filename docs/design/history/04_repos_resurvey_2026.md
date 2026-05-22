# 04 — 9-Repo Re-Survey (2026-05)

> 产出日期: 2026-05-05
> 方法: general-purpose subagent 逐仓库深读源码 (436s, 58 tool uses)
> 对照基线: `04_anima_design_v3.md`

---

## graphiti

### v3 已吸收且正确
- §16.2 "valid_from/valid_to 双时间区间直接复用" — 概念正确, Graphiti 确实做了双时间 (`graphiti_core/edges.py:271-282` 的 `valid_at / invalid_at / expired_at / reference_time`)
- §4 cloud-graphiti profile 的定位准确 (Postgres + Neo4j/Graphiti + Qdrant)

### v3 误读或过时
- **字段名错误**: `graphiti_core/edges.py:274,277` —— Graphiti 字段是 `valid_at` / `invalid_at` / `expired_at` (三时间, 非两时间); v3 §16.2 说"valid_from/valid_to 直接复用"会迁移失败。`expired_at` 是被新事实推翻的时刻 (`edge_operations.py:569`), `invalid_at` 是事实本身停止为真的时刻 —— **三者语义不同**, v3 把 mempalace 的 `valid_from/valid_to` 与 Graphiti 混为一谈。
- **节点类型不全**: `graphiti_core/nodes.py:867` —— 2025 新增 `SagaNode` (增量摘要节点, 带 `last_summarized_at`), v3 §16.2 仅提 "Episode 中心"。Saga 是 episode 之上的"故事单元", Starling 的 EpisodicEvent 与之不是 1:1。
- **Edge 上还有 `reference_time` 和 `episodes` 列表字段** (`edges.py:267,280`), v3 完全没提 —— 这是 Graphiti 把 episode 作为"事实证据来源"显式建模的关键。

### v3 未吸收的关键细节
- `graphiti_core/utils/maintenance/dedup_helpers.py:31-36` —— 实体名去重用 **MinHash + Shannon entropy + Jaccard ≥ 0.9**, short/低熵名延迟到 LLM 仲裁。Starling Cognizer Hub 的 alias 归一 (§3.1) 目前无算法, 可直接采纳此 hybrid 策略。
- `graphiti_core/search/search_filters.py:62-65,242-266` —— `DateFilter` 支持 **valid_at/invalid_at/expired_at 各自的 OR-list of AND-list 组合**, 即 CNF 时间过滤。Starling §13 Retrieval Planner 时间锚点查询缺这种表达力。
- `graphiti_core/graphiti.py:433-525` `summarize_saga()` —— 增量摘要只读取 `created_at > last_summarized_at` 的新 episode, 把已有摘要塞进 prompt 续写。这是真正的"在线巩固", 可直接做 Starling Replay Scheduler `compress` 动作的参考实现。
- `graphiti_core/utils/maintenance/edge_operations.py:562-572` `resolve_edge_contradictions` —— 新边设 `expired_at = utc_now()` 把旧边作废, 但旧边节点保留 (就地不删) —— 与 Starling reconsolidation supersedes 链同型, 可直接复用 cypher。

### 2025-2026 新增机制
- **SagaNode + HasEpisodeEdge + NextEpisodeEdge** 三件套 (`nodes.py:867`, `graphiti.py:346-525`) —— 一阶情节链 + 增量摘要;
- **Cross-encoder rerank** (`cross_encoder/bge_reranker_client.py`) —— BGE/OpenAI/Gemini 三家 reranker;
- **Kuzu / Neptune driver** 加入 (原仅 Neo4j/FalkorDB);
- **OpenTelemetry tracing** (`telemetry/`);
- **Namespace 重构** (`spec/driver-operations-redesign.md`) `graphiti.nodes.entity.save()` 风格 API 取代旧的"模型类自带 save"。

### 该仓库的"已知缺陷"
- 无 holder/perspective —— 全局事实图, 不区分"谁相信"; Starling 加 holder 维度后, 需要在 group_id 之外再叠 holder 标签, 否则跨 holder 子图族查询代价高;
- `expired_at` 设置时刻无版本号, 只能查"当前活/失效", 无法查"在 T 时刻 X 是否被认为有效" (伪 bi-temporal —— 无 transaction time)。Starling `observed_at / inferred_at / valid_from / valid_to` 才是真 bi-temporal。

---

## letta

### v3 已吸收且正确
- §16.2 `Block.label / version / BlockHistory / shared_blocks / sleeptime` 的概念引用正确。

### v3 误读或过时
- **"sleeptime agent" 现已迭代到 v4**: `letta/groups/sleeptime_multi_agent_v4.py` 是当前实现, 旧 `sleeptime_multi_agent.py` 与 v2/v3 都还在并存。v3 §16.2 把 sleeptime 当成单实体引用, 实际上 letta 还分出了 `voice_sleeptime_agent.py` (`letta/agents/voice_sleeptime_agent.py`) + `ManagerType.voice_sleeptime` (`group_manager.py:100`)。
- **"BlockHistory" 已不再是版本主路径**: `letta/services/block_manager_git.py:1-50` —— 2025 引入 `GitEnabledBlockManager`, 标签 `GIT_MEMORY_ENABLED_TAG = "git-memory-enabled"` 的 agent 用 **真实 git CLI + GCS/S3 对象存储** 写版本, Postgres 仅作 cache。v2 调研说"git-backed memory 是数据库模拟, 不是真 git" —— **2025 后已变成真 git** (`letta/services/memory_repo/git_operations.py:_run_git`)。v3 §11.3 "Letta Block version 历史在, 但不区分是否被回忆触发" 描述仍准确, 但把"git-backed"当成"伪 git"已过时。

### v3 未吸收的关键细节
- `letta/orm/identity.py:18-50` `Identity` model + `identifier_key + identity_type + properties` —— **letta 已经有 Cognizer 等价物** (Identity ORM), 通过 `identities_agents / identities_blocks` 多对多绑定。v3 §3.1 Cognizer 设计时未对照 Letta Identity, 迁移路径漏写。
- `letta/orm/archive.py:23-30` `Archive` —— ArchivalPassage 现在归属于 `Archive` (可跨 agent 共享), 通过 `ArchivesAgents` 关联。Starling §3.8 Drawer 可参考此 share 模型 (多 agent 共享同一原档池)。
- `letta/services/memory_repo/git_operations.py` —— 真 git CLI 的 commit/diff/log, 可作 Starling supersedes 链的物理底座参考 (用 git tree 记录 Statement 版本)。

### 2025-2026 新增机制
- `letta/agents/letta_agent_v3.py` —— 当前 agent 主版本;
- `letta/services/lettuce/` (新目录, 功能名 "lettuce");
- `letta/services/llm_router/` —— LLM 路由层;
- `letta/services/conversation_manager.py` + `letta/orm/conversation.py` + `conversation_messages.py` —— 新增 Conversation 顶层抽象 (原仅 message/agent);
- `voice_sleeptime` ManagerType + `voice_sleeptime_agent` —— 语音对话场景的睡眠巩固;
- `letta/services/file_processor/` —— 文件处理子系统。

### 该仓库的"已知缺陷"
- Block label 仍硬编码 `human / persona / system` (无 `interlocutor_persona / common_ground / pending_commitments` —— v3 §6.5 的差异点依然成立);
- Identity 无 `aliases / canonical_name` (v3 §3.1 Cognizer 加的);
- sleeptime 触发仍是简单 turns_counter 取模 (`group_manager.py:264`), 无 salience/conflict 优先级 —— Starling §10.2 优先级采样器是真差异点。

---

## cognee

### v3 已吸收且正确
- §16.2 `DataPoint 子类机制 / forget() 三级 / improve()` 引用准确。

### v3 误读或过时
- **"improve() 权重更新算法 TODO" 已不成立**: `cognee/api/v1/improve/improve.py:36-100` + `cognee/memify_pipelines/apply_feedback_weights.py:1-60` + 顶层 `cognee/tasks/memify/apply_feedback_weights.py` —— **流式 feedback alpha (`alpha ∈ (0,1]`) 已实装**, session_ids 驱动节点/边的 `feedback_weight` 更新 (高分 boost、低分降权), 按 `batch_size` 流式更新 + 全成功才标 applied。v3 §11.3 与 §16.2 仍说"improve 框架在, 反馈如何更新权重的算法 TODO" —— 过时 6 个月以上。
- **TEMPORAL 已经不是 cognee 自实现, 而是直接调用 graphiti**: `cognee/tasks/temporal_awareness/build_graph_with_temporal_awareness.py:1-40` —— `from graphiti_core import Graphiti`, cognee 把时间 KG 任务**完全外包给 graphiti**。v3 §16.2 "TEMPORAL 边 → valid_from/valid_to 双时间区间" 实际等价于"用 graphiti 的 valid_at/invalid_at"。

### v3 未吸收的关键细节
- `cognee/modules/retrieval/temporal_retriever.py:1-50` —— 检索时显式抽取 `QueryInterval` (用 `extract_query_time.txt` prompt), 再用 `triplet_distance_penalty` (默认 6.5) 在距离查询时间窗的 triplet 上加惩罚。Starling §13.5 Reranker 没有"时间距离惩罚"项, 可直接采纳。
- `cognee/memify_pipelines/persist_sessions_in_knowledge_graph.py` + `consolidate_entity_descriptions.py` —— **session 反馈驱动的图持久化** 是 cognee 2025 的核心新能力, 把 Q&A 文本带 `node_set="user_sessions_from_cache"` 标签写回主图。这个"feedback → 图改写"循环是 Starling §11 reconsolidation 的工程化先例, v3 完全没提。
- `cognee/api/v1/improve/improve.py:46-65` —— `improve()` 现在是四阶段: apply_feedback_weights → persist_session_QA → enrichment → sync_to_session_cache。这是比 v3 §10.3 7 项原子操作更细的真实工业流水线。

### 2025-2026 新增机制
- `cognee/memory/entries.py` 的 `MemoryEntry / FeedbackEntry` (1-5 分);
- V2 API 完整化: `remember / recall / forget / improve` 四动词;
- `cognee/modules/observability/` —— 新增可观测性模块 (spans / trace 元数据);
- `cognee/skill.md` —— 模型可调用的"技能"声明文件;
- `memify_pipelines/` (11 个子流水线)。

### 该仓库的"已知缺陷"
- improve 仍是离线批量 (无在线增量 reconsolidation);
- DataPoint 无 holder / perspective 字段;
- temporal awareness 把脏活外包给 graphiti, 意味着 cognee 自己**不再独立维护 bi-temporal**, 采用 cognee-bridge profile 的 Starling 实际是吃 graphiti 的时间能力。

---

## MemOS

### v3 已吸收且正确
- §20 "MemCube (activation memory) / Memory-Brain 概念" 仍准确;
- KV cache 拼接 (`activation/kv.py`) 仍是该项目的核心差异点。

### v3 误读或过时
- **"Scheduler 任务种类与触发条件不少处于占位"** 已大幅推进: `src/memos/mem_scheduler/memory_manage_modules/` 现在包含 `activation_memory_manager.py / enhancement_pipeline.py / filter_pipeline.py / memory_filter.py / post_processor.py / rerank_pipeline.py / retriever.py / search_pipeline.py / search_service.py` —— 9 个真实模块, 不再是空壳。
- **MemCube 4 域 (text/act/para/pref) 定义未变**, 但 `pref_mem` 现有独立子系统 `memories/textual/prefer_text_memory/` + `simple_preference.py / preference.py`, Starling §7.4 Persona vs Belief 的"偏好通道"实际可借这个落地。

### v3 未吸收的关键细节
- `src/memos/memories/textual/tree.py` + `tree_text_memory/` —— **TreeTextMemory** 是 MemOS 2025 的核心, 把文本记忆组织成树 (parent/child), 与 Starling Hippocampus/Neocortex 双层并不同型。v3 §6/§7 完全没对照。
- `src/memos/mem_scheduler/optimized_scheduler.py:1-40` `OptimizedScheduler(GeneralScheduler)` —— 带 API 的 working memory 优化版, `format_textual_memory_item` + `group_messages_by_user_and_mem_cube` 是 Starling §6.5 Working Set 多用户分组的现成参照。
- `src/memos/mem_feedback/simple_feedback.py` —— 反馈一等公民, 与 cognee feedback 形成对照 (MemOS 偏存储, cognee 偏图改写)。
- `src/memos/mem_agent/deepsearch_agent.py` —— 多步深度检索 agent, 可对照 Starling §13 Retrieval Planner 7 步规划。

### 2025-2026 新增机制
- `mem_chat / mem_user / mem_agent` 三个新顶层目录;
- `optimized_scheduler.py` + `general_scheduler.py` 双轨;
- `memos_tools/` + `mem_os/core.py` —— 把 OS 概念落地为 core class;
- `chunkers/` —— 显式 chunking 子系统;
- `apps/memos-local-plugin/` 独立 CHANGELOG —— 出现"MemOS as a service"分支。

### 该仓库的"已知缺陷"
- 仍无 holder / perspective;
- TreeTextMemory 的 tree 结构是按主题/层级, 不是按主体;
- KVCache 仍只对 HF transformers 生效, 不能用于闭源 API 模型 —— Starling §4 Substrate Adapter "Cache (KV-cache)" 行需注明此约束。

---

## EverOS

### v3 已吸收且正确
- §20 "MemCell→Episode→AtomicFact→Profile→Foresight→Case→Skill 七层" 引用准确 (EverCore 部分);
- Foresight 的 trigger 字段确实未实装运行时调度。

### v3 误读或过时
- v3 把 EverOS 当作"七模型层级"单一项目, **实际上 EverOS 已分裂成两个独立子项目**: `methods/EverCore/` (原七层) 与 `methods/HyperMem/` (2026 ACL 新论文, 完全不同架构)。v3 整章未提 HyperMem 的存在, **这是最大的遗漏**。

### v3 未吸收的关键细节
- `methods/HyperMem/README.md:1-50` —— HyperMem 是 **三级 hypergraph (Topic L3 → Episode L2 → Fact L1)** + 加权 hyperedge $w \in [0,1]$, 通过 attention $\alpha_{e,v}$ 做嵌入传播, **LoCoMo 92.73% 超越 MemOS 16.93 个点**。Starling §3.7 是"边类型表" (社会图谱), 完全没考虑 hyperedge 表达"多事实共属同一 episode"这种 N 元关系。
- HyperMem 的 **Coarse-to-fine retrieval (Stage1 Topic→Stage2 Episode→Stage3 Fact)** 用 RRF $\sum 1/(k+\mathrm{rank}_m)$ 融合 BM25+dense, 可直接替换 Starling §13.5 简单加权 reranker。
- `methods/EverCore/src/memory_layer/` + `agentic_layer/` + `biz_layer/` + `infra_layer/` —— 4 层架构, 比 v2 调研描述的"七模型"更接近工业产品形态; v3 §20 仍只提 7 模型, 漏掉 layer 划分。

### 2025-2026 新增机制
- **HyperMem 整套** (超图 + 三级检索 + LoCoMo SOTA);
- EverCore 的 `migrations/` + `application_startup.py` —— 工程化加固;
- `agentic_layer/` —— agent 与 memory 的分层。

### 该仓库的"已知缺陷"
- HyperMem 与 EverCore 之间无统一接口 (两个独立代码库);
- HyperMem 仅做 LoCoMo benchmark, 无生产部署形态;
- 仍无 holder / 二阶 ToM (EverOS 全家都缺)。

---

## memU

### v3 已吸收且正确
- §20 "Category summary 增量维护 / PROMPT_BLOCK 模块化" 仍准确;
- 6 个 prompt 文件 (profile/event/knowledge/behavior/skill/tool) 仍在 `src/memu/prompts/memory_type/`。

### v3 误读或过时
- v3 仍把 memU 当 Python 项目, **实际上 v1.4+ 已转为 Rust core + Python binding**: 仓库根有 `Cargo.toml / Cargo.lock`, 源码有 `src/lib.rs` 与 `src/memu/_core.pyi` (stub)。Python 侧 `src/memu/` 是 wrapper, 核心 patch/embedding/blob 在 Rust。v3 §20 与 §16 共存策略未反映这一架构变化。

### v3 未吸收的关键细节
- `CHANGELOG.md` v1.5.0 (#386) "**non-propagate option for memory patch**" —— 之前 propagate=True 时同步触发下游摘要更新会拉爆延迟 (02_aux 已警告), memU 现在加了 non-propagate 开关, 等价于"异步增量"。Starling §10.3 `compress` 动作可直接采纳此开关语义 (默认 non-propagate, 显式触发时传 True)。
- `src/memu/blob/` —— Rust 实现的 blob 存储层 (verbatim 原档), 与 Starling §3.8 Drawer 的"append-only 物理介质"对应, 可作底座候选。
- `src/memu/database/` + `src/memu/integrations/` —— integrations 子系统是新加的 connector 抽象层。

### 2025-2026 新增机制
- Rust core 重写;
- `mem0-plugin/` 与 `vercel-ai-sdk/` 等多 SDK 适配 (在 mem0 仓库; memU 自己也有 `integrations/`);
- `non-propagate` patch 开关。

### 该仓库的"已知缺陷"
- "6 分类抽取"本质未变 (仍是 6 个独立 LLM prompt + XML), 无交叉关系建模;
- Rust 化未带来抽取语义升级, 只是性能;
- 仍无 holder。

---

## mem0

### v3 已吸收且正确
- §16.2 "ADD/UPDATE/DELETE/NOOP → Statement.modality + supersedes 链" 概念正确。

### v3 误读或过时
- **filters 维度漏一项**: `mem0/memory/main.py:99-100` —— `ENTITY_PARAMS = frozenset({"user_id", "agent_id", "run_id"})`, 但 `_build_filters_and_metadata` (第 233-260 行) 还接受第 4 维 `actor_id` (查询时过滤, 优先级: 显式 actor_id arg → `filters["actor_id"]` → null)。v3 §16.2 仅提 `{user_id, agent_id, run_id}` 三维, **漏 actor_id**。Cognizer 三维隔离 → 实际应为四维。
- **API 已 1.0.0**: `MIGRATION_GUIDE_v1.0.md` —— 移除 `version` / `output_format` 参数, 统一返回 `{"results": [...]}`, top-level entity params 现在 **抛错拒绝** (`main.py:104-110`)。v3 §16.2 写"既有向量库保留为 Substrate.vector"没问题, 但若按旧 mem0 API 写迁移脚本会全部 break。

### v3 未吸收的关键细节
- `mem0/memory/main.py:248-252` —— `actor_id` 是 **query-time only** 字段 (写入是 `user_id/agent_id/run_id` 三维元数据, 但查询可按 actor 切片), 这是 holder 思想的雏形 (actor ≈ holder)。Starling 设计 Cognizer Hub 时, 可用 mem0 actor_id 做反向兼容入口。
- `mem0/reranker/` —— mem0 现在有独立 reranker 子模块, v2 调研未提;
- `mem0-ts / vercel-ai-sdk / mem0-plugin / openmemory` —— 多 runtime/SDK 适配。

### 2025-2026 新增机制
- v1.0.0 breaking API change (filters 强制);
- `actor_id` 查询维度;
- `openmemory/` 子项目 (可能与 OpenMemory MCP 相关);
- TS SDK + Vercel AI SDK 适配。

### 该仓库的"已知缺陷"
- 仍是双写无事务 (SQL+vector 写半截);
- "知识图": 有 NER 而无图 (mem0 graph_memory 是 Neo4j 直接写, 无 schema);
- actor_id 仅查询时生效, 写入仍按 user/agent/run 分桶 —— holder 维度污染问题 (02_aux 警告) 未根治。

---

## mempalace

### v3 已吸收且正确
- §16.2 "Drawer 不变; triples 升级为带 holder 的 Statement; emotions 升级为 AffectVector" 仍准确;
- KG 字段 `subject/predicate/object/valid_from/valid_to/confidence/source_closet` (`knowledge_graph.py:63-97`) 依然保持。

### v3 误读或过时
- mempalace v3.3.0+ 引入 **Hall detection** (CHANGELOG 2026-04-13 v3.3.0): 路由 drawer 到 `emotions / technical / family / memory / identity / consciousness / creative` 7 个 hall —— 与 Starling §7.1 Neocortex "5 子区"是另一种维度 (基于内容情感/主题), v3 完全没提。这是 mempalace 把 emotions 字段进一步**外化为存储分区**的 2026 演进。
- v3.3.4 引入 **corpus origin 检测** (CHANGELOG): 识别"对话型语料 vs 文档型语料", 自动把 AI persona 名 (Echo/Sparrow/Cipher 等) 与人类名分开 —— 这是 Starling §3.1 Cognizer.kind=`agent` vs `human` 的现成分类器, v3 没引用。
- v3.3.0 "Cross-wing tunnels" (显式跨项目链接) —— 与 Starling §3.7 边类型 `MAY_OVERLAP_WITH` 同构但 mempalace 是显式存储边, v3 未对照。

### v3 未吸收的关键细节
- `mempalace/searcher.py` 的 hybrid 检索 (BM25 + cosine, CHANGELOG #1180): **closets 仅 boost ranking, 从不 gate result** (原档不可被索引层挡住) —— 这是 verbatim 原则的检索层落地, Starling §13 Retrieval Planner 应吸收"index 不准 gate verbatim"约束。
- `mempalace/layers.py` L0-L3 + sweep —— 02_aux 称"sweep 实装不完整", CHANGELOG 显示 `mempalace sweep` CLI 已成正式命令 (v3.3.2 #998 加入), 不再是占位。
- AAAK Zettel 字段 `ZID:ENTITIES | keywords | "quote" | WEIGHT | EMOTIONS | FLAGS` —— `WEIGHT` 与 `FLAGS` 字段语义 v3 没接, 只接了 `EMOTIONS`。WEIGHT 等价于 Starling salience, FLAGS 等价于 v3 §13.6 8 标签, 可直接对应。

### 2025-2026 新增机制
- **Hall detection** (7 hall, 内容情感分区);
- **Corpus origin 自动检测 + agent_persona 识别**;
- **Cross-wing topic tunnels** (语义 + 显式拓扑);
- 多语种 entity detector (8+ 语言);
- v4 planning prep (ROADMAP) 已开始。

### 该仓库的"已知缺陷"
- 100% verbatim 成本仍高, 长会话需冷热分级 —— mempalace 仍未解 (无 archive 层);
- KG 仍为 SQLite 单机, 无图 DB;
- emotions 字段是 AAAK 自然语言串, 非结构化 vector (Starling 五维 vector 仍是真升级)。

---

## claude-mem

### v3 已吸收且正确
- §20 "5 阶段 Hook 生命周期 / SQL 主 + 向量副 / 严格 XML 输出契约" 仍准确 (已存活到 v12.4)。

### v3 误读或过时
- **"Cynical deletion 未找到实装"是误读对象的范畴错误**: `ANTI-PATTERN-TODO.md:1-7` (301 issues / 289 fixed) + `CHANGELOG.md` v12.4.7 (2026-04-26) "Cynical deletion + review fixes" + 仓库根 `cursor-hooks/` 与 `ISSUE-BLOWOUT-TODO.md` —— **"Cynical deletion" 不是数据删除策略, 而是代码风格运动**: 删除 "defenders" (orphan cleanup / 多余 liveness probe / 端口窃取重启) 与 "tolerators" (silent JSON drops / drift 过滤器 / passthrough Zod schemas), 用 **fail-fast 与 strict boundary 替代防御性 try/catch**。02_aux 警告"不要在新设计文档中把它当成既有先例"是对的, 但理由要改为"它根本不是数据删除"。v3 §10.4 "claude-mem 的 cynical deletion 真删, Starling 永远可审计" —— **完全反了**, 需要从 v3 中删除该对照。
- §5.3 "claude-mem 的 5 阶段 hook 是 session 级, Starling 是 statement 级" 仍正确, 但 v12.4.4 (2026-04-26) **移除了 SessionEnd hook** (改为 worker 自完成), 5 阶段实际已变成 4 阶段 (SessionStart / UserPromptSubmit / PostToolUse / Summary)。

### v3 未吸收的关键细节
- v12.4.7 (#2141) "**Defenders/Tolerators**" 二分类 —— 这是绝佳的 Starling §5 Validator + §13.7 Abstention Gate 的设计准绳: Validator 应当"拒收非合规 Statement" (strict boundary, 非 silent drop), Abstention 应当 fail-fast 不编造。可作 §19 风险章节的工程纪律引用。
- v12.4.3 `CleanupV12_4_3.ts` —— 一次性 marker-file 门控的清理迁移, 带 `VACUUM INTO` + WAL 备份。Starling §10.3 `purge_compliance` 动作的工业级模板。
- `src/utils/tag-stripping.ts` (CHANGELOG v12.4.3 + v12.4.9 #2204) —— `<private>...</private>` 隐私 tag 在 hook 边缘剥离, **先于到达 worker/database**。Starling §3.2 `visibility / retention_policy` 的边缘剥离实现可参考。
- v12.4.7 多账户隔离 `CLAUDE_MEM_DATA_DIR` + `CLAUDE_MEM_WORKER_PORT = 37700 + uid % 100` —— 多 Cognizer 共存场景的进程级隔离方案。

### 2025-2026 新增机制
- v12.4 系列 (2026-04) 的 cynical deletion sweep (289/301 anti-patterns 修复);
- 多账户/多 UID 隔离;
- Codex transcript ingestion + Gemini CLI 适配;
- pro feature gating (license validation, 核心仍开源);
- migration 30 (`observations.metadata` 列加入)。

### 该仓库的"已知缺陷"
- 摘要时机仍按 hook 计数, 无 EM-LLM 惊奇度切片 (02_aux 已指出, 未变);
- `ISSUE-BLOWOUT-TODO.md` 表明仓库长期 issue 爆炸 (可作 Starling "issue 防爆"的反向案例);
- Chroma 仍是单机文件, 无分布式; `backfillAllProjects` 重建向量是离线操作, 无在线增量。

---

## 跨仓库总结 (优先级修复给 v4)

1. **graphiti 字段名**: `valid_at/invalid_at/expired_at` (三时间) ≠ `valid_from/valid_to` (两时间); v3 §16.2 + §3.2 需修。
2. **graphiti SagaNode**: v3 缺增量摘要节点抽象。
3. **EverOS HyperMem (2026 ACL)**: v3 整章遗漏 —— hypergraph + 三级 coarse-to-fine + RRF, 影响 §13 检索规划与 §3.7 边类型设计。
4. **mem0 actor_id**: Cognizer 应 4 维 (user/agent/run/actor), 非 3 维。
5. **cognee improve() feedback alpha**: 已实装, v3 §11.3 + §16.2 需更新。
6. **letta 真 git memory + Identity ORM**: v3 §16.2 仍按"伪 git + Block-only" 写迁移, 缺 Identity / Archive / git_operations。
7. **claude-mem cynical deletion 是代码风格, 非数据删除**: v3 §10.4 对照表完全反向, 必须删除或反向改写。
8. **mempalace Hall detection + corpus origin**: v3 §3.1 Cognizer.kind 与 §7.1 Neocortex 子区分类有现成参照未吸收。
9. **MemOS TreeTextMemory + 9 个 scheduler 模块**: v3 §10 Replay Scheduler 与 §7 Neocortex 缺对照, 2025 后已不再"占位"。
10. **memU Rust core + non-propagate**: v3 §20 与 §10.3 compress 动作可直接采纳 non-propagate 开关。
