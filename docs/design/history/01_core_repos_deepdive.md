<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../../superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# 核心 4 仓库源码深度调研(EverOS / Letta / cognee / MemOS)

> 由调研 agent 产出,主报告员审阅。所有"行号"为 agent 在源码中读取到的位置,使用前应再次核对。

## EverOS

### 数据模型(`methods/EverCore/src/api_specs/`)

- **MemCell** `memory_types.py:132-207` —— 字段:`user_id_list / original_data(消息列表) / timestamp / event_id / group_id / participants / sender_ids / type`。设计意图:对话边界检测的承载,`conversation_data` 属性自动剥离中间 tool calls,`original_data` 保留原文。
- **EpisodicMemoryModel** `memory_models.py:242-268` —— 在 MemCell 之上增加 `subject / summary / start_time / end_time / keywords`,即"提升后"的情节单元。
- **AtomicFactModel** `memory_models.py:271-303` —— `parent_type(memcell|episode) / parent_id` 让原子事实指回上游;细粒度向量化的目标。
- **ForesightModel** `memory_models.py:306-341` —— 唯一的"前瞻"承载,字段含 `start_time / end_time / duration_days / evidence`。
- **ProfileModel** `memory_models.py:186-205` —— `profile_data(Dict) / scenario(solo|team) / confidence / cluster_ids / memcell_count`。implicit_traits 不是结构化字段,而是塞在 `profile_data` 里的自然语言。
- **AgentCaseModel / AgentSkillModel** `memory_models.py:344-395` —— Case 承载"任务意图+方案+质量分",Skill 由 Case 集群提升而来,带 `maturity_score`。

### 关键机制评注

- **Foresight 生效**:字段齐全,但未见运行时根据 `end_time` 主动失效或重排的循环 → **半纸老虎**。
- **检索融合**:`RetrieveMethod.HYBRID / AGENTIC` 枚举存在,具体融合算法未在本次抽样中验证。
- **多主体**:`group_id / sender_ids` 用作隔离 + 归因字段,但**没有任何"信念关于信念"的结构**(无二阶 ToM)。

### 可借用资产

1. MemCell→Episode→AtomicFact→Profile→Foresight→Case→Skill 七层提升管线作为"类脑分层"的工程参照;
2. Foresight 的 `start_time / end_time / duration_days` 三件套,是新系统建模"承诺有效期"的最小起点;
3. `group_id + sender_ids + participants` 是多主体最便宜的元数据组合。

### 纸老虎

- "implicit_traits 自适应更新":只是 LLM prompt 输出后写入 dict,无差分维护。
- "前瞻有效期触发":字段在,触发逻辑无。
- 无 CLS 机制,无重放、无再巩固。

---

## Letta(MemGPT 后继)

### 数据模型

- **Block** `letta/orm/block.py:20-116` + `letta/schemas/block.py` —— `value / limit / label(human|persona|system) / read_only / version(乐观锁) / metadata / hidden`。这就是工作记忆的"显式槽位"。
- **ArchivalPassage** `letta/orm/passage.py:76-104` —— `text / embedding / embedding_config / tags(JSON+junction 双写) / metadata_`。embedding 可空,允许纯文本搜索降级。
- **BlockHistory**(在 `block_history.py`)—— Block 每次修改写入一条 history,`current_history_entry_id` 指针决定"当前活跃版本",支持 rollback。**这就是 Letta 所谓的 "git-backed memory" 的本质**:**应用层模拟,不是真 git**。

### 关键机制

- **Sleeptime Agent 触发** `letta/services/group_manager.py:94-168`:配置 `ManagerType.sleeptime + sleeptime_agent_frequency = N`;`group.turns_counter = (turns_counter+1) % N`,归零时触发 consolidation。这是**最像睡眠巩固的工程化触发器**,但具体 LLM consolidation prompt 不在 group_manager 内,需要继续追到 agent 层。
- **Groups / Shared Blocks** `letta/orm/block.py:80-92`:Block 通过 `secondary="groups_blocks"` 多对多关联 Group,实现多 agent 共享同一块工作记忆。
- **Block 注入** 推测在 prompt builder 中按 `label` 拼接,本次未直接定位。

### 可借用资产

1. `version` 乐观锁 + history 表的双写,是"信念版本链"在关系库里的最简实现;
2. `tags JSON + junction 表`双写法;
3. sleeptime 计数触发器作为"低算量的离线巩固时机"。

### 纸老虎

- "Git-backed memory":数据库模拟而非 git。
- Sleeptime 真正"做了什么":在 group_manager 看不到 LLM 巩固提示和写回逻辑,需到 agent 层才能确认。

---

## cognee

### 数据模型(`cognee/infrastructure/engine/models/DataPoint.py:27-328`)

- **DataPoint** 是基类:`id(UUID) / created_at / updated_at / version / type / metadata(index_fields, identity_fields)`。
- **关键扩展机制**:用 `Annotated[..., _Embeddable / _Dedup]` 在子类字段上做声明式标记,基类 `__pydantic_init_subclass__` 自动收集进 `index_fields`,`_generate_identity_id` 用 UUID5 把"业务关键字段"映射成确定性 id —— **这是 4 个核心仓库里最适合作为"社会心智本体扩展点"的机制**。
- **MemoryEntry / FeedbackEntry**(`cognee/memory/entries.py`):V2 API 的输入封装,FeedbackEntry 带 1-5 分。

### V1 vs V2 API

| 维度 | V1 | V2 |
|---|---|---|
| 入口 | `add / cognify / search / delete / memify` | `remember / recall / forget / improve` |
| 粒度 | 数据集级 | 条目 + 反馈级 |
| 关键差异 | 顺序流水线 | 反馈驱动(feedback_score → improve) |

### 关键机制

- **forget()** `cognee/api/v1/forget/forget.py:15-204`:三级粒度(item / dataset / everything),同时清理关系库 / 图库 / 向量库,带权限校验。会话缓存清理标 TODO。
- **improve()**:框架在,**反馈如何更新权重的算法基本是 TODO**。
- **TEMPORAL / valid_from / valid_to**:CLAUDE.md 提到,本次抽样未在源码中确认到完整实现。

### 可借用资产

1. **DataPoint Annotated 扩展机制**——新系统应直接采纳同款模式定义 Belief / Intent / Norm / Commitment 等社会心智本体;
2. **UUID5 确定性 id**——同样适合"(holder, target, predicate, value) → id"的去重;
3. **三级删除粒度 + 权限**——直接复用;
4. **V2 反馈驱动 API 形状**——`remember / recall / forget / improve` 是值得保留的语义动词。

### 纸老虎

- improve 的"权重更新"基本是 TODO;
- TEMPORAL 在源码层未充分验证;
- "认知图谱主动巩固"在批处理之外没有实质循环。

---

## MemOS

### 数据模型

- **BaseMemCube** `src/memos/mem_cube/base.py:13-31`:四个域 —— `text_mem / act_mem / para_mem / pref_mem`。
- **GeneralMemCube** `src/memos/mem_cube/general.py:21-105`:工厂创建各域 backend,支持 selective load / dump。
- **KVCacheMemory(activation)** `src/memos/memories/activation/kv.py:16-138`:`kv_cache_memories: dict[id, KVCacheItem]`;`get_cache(ids) → DynamicCache`,通过 `_concat_caches` 合并多段 KV;直接交给 HF transformers 的 `past_key_values` 复用 —— **这是 4 个核心仓库里唯一接近"激活记忆"工程实现的代码**。

### 关键机制

- **激活记忆 KV 复用** `kv.py:63-81`:用 torch DynamicCache 拼接,跳过重新 prefill;
- **CompositeCube**:`memos/multi_mem_cube/composite.py` —— fan-out 检索框架,具体策略本次未深入;
- **Scheduler** `memos/mem_scheduler/base_scheduler.py:69-150`:`ScheduleTaskQueue(redis|in-memory) + SchedulerDispatcher(线程池) + Monitor`,任务种类(consolidation / eviction / scoring)在 `memory_manage_modules/` 下,**框架完整但任务实现很薄**。

### 可借用资产

1. 三层(textual / activation / parametric)+ pref 的内存域分类思路;
2. KV cache 拼接作为"工作记忆复用上下文窗"的真实手段;
3. 异步任务调度 + Redis/线程池二选一的工程基线。

### 纸老虎

- CompositeCube 的"多 Cube 智能融合"还是简单 fan-out;
- Scheduler 任务种类与触发条件不少处于占位阶段。

---

## 跨系统小结

**谁的睡眠巩固最接近 CLS?** 都不像。Letta 的 sleeptime 有触发计数器、MemOS 的 Scheduler 有任务队列,但**两者都缺少"高新颖/高情绪/高奖励优先重放"的采样器**。CLS 的核心不是"周期性触发 LLM 复述",而是"快慢两套表征 + 优先级重放 + 抗灾难性遗忘的混合训练",这一点 4 个核心仓库都没做。

**谁的本体扩展机制最适合社会心智 schema?** **cognee 的 DataPoint + Annotated**。其它三家要么是固定字段(Letta Block label、EverOS 七模型),要么没有本体(MemOS 内存域)。新系统的 Statement / Belief / Norm / Commitment 等,在 DataPoint 子类化下能以 ~30 行代码挂上去。

**看似不同实则同型的工程模式**

1. 版本控制:Letta `version` + `BlockHistory`,cognee `DataPoint.version`,MemOS `updated_at` —— 都是"版本号 + 历史表 + 时间戳"。
2. 多粒度删除:EverOS 七层、cognee 三级、Letta soft delete —— 都是权限校验 + 级联清理。
3. 异步巩固:MemOS Scheduler、Letta sleeptime、cognee improve —— 都是"采样 + 触发 + 改写",采样策略各家薄弱。
4. 混合检索:EverOS HYBRID(ES+Milvus)、Letta 向量+关键词、cognee KG+vector,**全部缺少"按对话主体视角过滤"这一维**。

**给新系统的具体启示**

- **本体层用 cognee DataPoint 风格**;**激活记忆用 MemOS KV cache 风格**;**版本与共享用 Letta Block 风格**;**事件分层用 EverOS 七模型风格**。这是"中间件而非新底座"路径下最经济的工程组合。
- **CLS / 二阶 ToM / 前瞻有效期触发**这三件事**所有核心仓库都没做**,是真正的设计空间。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
