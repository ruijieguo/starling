# 辅助 4 仓库源码深度调研(memU / mem0 / mempalace / claude-mem)

> 由调研 agent 产出,主报告员审阅。"行号"以 agent 当时读取为准,使用前应再核对。

## memU

### 抽��流水线

`src/memu/prompts/memory_type/` 下 6 个独立 prompt 文件:`profile / event / knowledge / behavior / skill / tool`。每个 prompt 用 PROMPT_BLOCK_OBJECTIVE / WORKFLOW / RULES / OUTPUT / EXAMPLES / INPUT 拼成 XML。

**本质评估**:**"6 分类抽取"= 6 个 LLM prompt + 1 个 XML schema**,代码层没有交叉引用、关系建模或冲突检测。

### 增量摘要(Category Summary / Patch)

`category_patch/category.py:1-46` 的 LLM 输出 `need_update: bool` + 新摘要;`app/patch.py:37-144` 在 `propagate=True` 时同步触���下游摘要更新(无队列、无补偿)。

### Workflow Runner

`workflow/runner.py:28-81` 的 `LocalWorkflowRunner` 是线性 step 串行,有拦截器但无并行 / 分支 / 失败补偿。

### 可借用资产

1. PROMPT_BLOCK_* 拆分模式(可读、可单测、可复用);
2. XML 嵌套 schema(适合表达多维分类输出);
3. "need_update 先判 → 再生成"的两步增量摘要协议。

### 纸老虎

- `dedupe_merge` 不存在 —— 全靠 LLM 在 prompt 里"自觉去重";
- "propagate 触发下游更新"是同步 LLM 调用,堆叠后会拉爆延迟。

---

## mem0

### ADD/UPDATE/DELETE/NOOP 抽取

`configs/prompts.py:176-250` 是核心 prompt。运行时强制 entity 三维隔离:`user_id / agent_id / run_id`,通过 `filters={}` 而非顶级参数传入(`memory/main.py:103-110`)—— 这是干净的工程契约。

### 实体链接 / KG

`utils/entity_extraction.py:1-150` 用 spaCy NER + 4 类后缀(PROPER / QUOTED / COMPOUND / NOUN) + 黑名单(_GENERIC_HEADS / _GENERIC_ENDINGS / _NON_SPECIFIC_ADJ)。**结论**:有 NER,无 KG schema,无实体消歧。

### actor_id / role / scope

三维隔离:user_id(终端用户) / agent_id(AI 身份) / run_id(执行会话),全部可选但通常需 user_id;`_validate_and_trim_entity_id` 校验非空 / 无空格。

### 双写

LLM 提取 → 决定动作 → 同步写 SQL 元数据 + 写向量库。**无 WAL,故障可导致不一致**。

### 可借用资产

- `filters={}` 的统一隔离参数契约 —— 这是新系统多主体接口的最佳起点;
- 黑名单 + NER 后缀分类 —— 简单实用。

### 纸老虎

- "知识图":有 NER 而无图;
- 一致性:无事务,SQL ↔ 向量 写半截会污染状态。

---

## mempalace

### Drawer / Closet / AAAK

- **Drawer** `sources/base.py:108-122`:`DrawerRecord(content, source_file, chunk_index, metadata, route_hint)`,**严格 verbatim,不抽取不改写**。
- **Closet**:AAAK 压缩的"符号化摘要 + 指向 drawer 的索引"。Header 格式:`FILE_NUM | PRIMARY_ENTITY | DATE | TITLE`;Zettel 格式:`ZID:ENTITIES | keywords | "quote" | WEIGHT | EMOTIONS | FLAGS`。
- **AAAK** `dialect.py:1-170`:有损结构摘要,字段 entities / topics / key_quote / weight / emotions / flags / tunnels。**emotions 字段是 8 个被调研仓库里唯一把"情绪显著性"明确为一等字段的设计**。

### 时间 KG

`knowledge_graph.py:63-97` 用 SQLite 存 triples:`subject / predicate / object / valid_from / valid_to / confidence / source_closet`。`query_entity(entity, as_of=...)` 通过 `valid_from <= as_of < valid_to` 过滤。**这是 8 个仓库里唯一在 KG 层面把"双时间区间"做到查询路径的实现**。

### Sweep(巩固/清理)

`layers.py` 定义 L0-L3(Raw / Index / Archive / Recall),sweep() 把 L0 压向 L2、重生 closet、触发 KG 更新。**仍有部分占位**。

### 可借用资产

1. **Drawer = 100% verbatim 原档**:绝对不能让 LLM 抽取"覆盖"原始证据 —— 这是新系统**第一道防线**;
2. **AAAK 中的 emotions / weight / flags 字段**:情感与显著性的最小可行 schema;
3. **valid_from/valid_to + as_of 查询语义**:必须照搬。

### 纸老虎

- Sweep 实装不完整;
- "100% verbatim"成本高,长会话下需要分级冷热存储。

---

## claude-mem

### 5 个生命周期 Hook

1. SessionStart:注入历史上下文;
2. UserPromptSubmit:捕用户意图;
3. PostToolUse:捕工具执行;
4. Summary:压缩为摘要;
5. SessionEnd:最后持久化。

超时(`shared/hook-constants.ts`):DEFAULT 5min / HEALTH_CHECK 3s / POST_SPAWN_WAIT 15s / WINDOWS_MULTIPLIER 1.5x。

### 会话压缩

`sdk/prompts.ts:135-170` 的 `buildSummaryPrompt()`,要求模型输出严格的 `<summary>` XML,字段:`request / investigated / learned / completed / next_steps / notes`,**其它非 XML 文本一律丢弃**。

### Cynical Deletion

**搜索未找到显式实现**。看起来要么在 ObservationCompiler 的过滤阶段隐式存在,要么尚未实装。**应警惕将其作为既成机制引用**。

### Session Inject

`services/context/ContextBuilder.ts:80-150` 的 `buildContextOutput()`:Header(项目 + token 经济学) + Timeline(observations + summaries) + 最近摘要 + Previously + Footer。SessionStart 直接注入。

### 双存储

- SQLite(`~/.claude-mem/claude-mem.db`):session metadata / observations / summaries,SQL 时间窗 + project 过滤。
- Chroma(`~/.claude-mem/chroma/`):向量索���,用于语义检索。
- 协议:**先写 SQL 再写 Chroma;Chroma 故障时仍可降级到 SQL**。

### 可借用资产

1. **5 阶段 Hook 生命周期**:把"什么时候写、什么时候读"做成产品契约,不要藏在 framework 里;
2. **严格 XML 输出契约**(只取 `<summary>`,其余丢弃):降低自由文本的污染;
3. **SQL 主、向量副**的降级语义。

### 纸老虎

- "Cynical Deletion" 在源码中未确认 —— **不要在新设计文档中把它当成既有先例**;
- 摘要时机靠 hook 计数,**没有按"惊奇度切片"**(EM-LLM 的优势)。

---

## 跨系统小结

### "verbatim 原档"评分

| 系统 | 策略 | 100% Verbatim | 索引分离 |
|---|---|---|---|
| mempalace | Drawer + AAAK Closet | ✅ | ✅ |
| claude-mem | Observation 原始 JSON | ✅ | ✅ |
| mem0 | 抽取后事实 | ⚠️ | ⚠️ |
| memU | 分类摘要 | ⚠️ | ❌ |

**结论**:**mempalace + claude-mem 的"原档与索引分离"模式应作为新系统硬约束**。LLM 抽取错误是常态;无 verbatim,任何错误都会变成既成事实。

### 可作为新系统直接组件的工程片段

1. **mem0 的 `filters={user_id, agent_id, run_id}`** 隔离契约;
2. **mempalace 的 Drawer + AAAK + 时间 KG (`as_of`)** 三件套;
3. **claude-mem 的 Hook 生命周期 + 严格 XML 输出契约**;
4. **memU 的 PROMPT_BLOCK 模块化提示词组合**。

### 必须警惕的反模式

| 反模式 | 出处 | 后果 |
|---|---|---|
| 同步 LLM 调用嵌入 hook 主路径 | memU propagate | 长尾延迟爆炸 |
| 双写无事务 | mem0 SQL+向量 | 状态污染 |
| 把"prompt-only 的承诺"当作机制 | memU dedupe / cynical deletion | 设计文档失真 |
| KG 但无消歧 | mem0 NER | 同名实体污染图 |
| 摘要不分级冷热 | claude-mem | 长期会话存储成本超线性 |
