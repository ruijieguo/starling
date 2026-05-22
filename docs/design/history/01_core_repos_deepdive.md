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
