# 形态 S：带日期的原文通道进入生产召回（完整设计 v4）

日期 2026-10-20（v1→v2 经 Codex 首轮 14 条，v2→v3 经二轮 12 条，v3→v4 经三轮 9 条与用户的多智能体场景裁定）。状态：**设计稿，未实现**。

**v4 相对 v3 的实质变化：授权模型从"说话人 + 会话作用域"改为"基于感知"。** 用户 2026-10-20 给出目标场景：Starling 作为**社会情境模拟器**的记忆系统，多个 agent 各有记忆，系统模拟多个情境。在这个场景下 v3 的授权规则是错的——它只允许 agent 召回**自己说的**原话，而 B 在场听 A 说话，B 理应记得。v4 改为：**一句原话能被某个 agent 召回，当且仅当该 agent 感知到了它**，判据由 Starling 已有的 `KnowledgeFrontier::visible_engrams_at` 给出。因此 v3 的 `Session`/`Project` 两种作用域模式与 `project_key` **全部移除**。

**分层（用户 2026-10-20 裁定）**：

| 层 | 映射 | 性质 |
|---|---|---|
| 世界 | **租户** | 安全边界：平行世界之间硬隔离 |
| 场景 | **会话**（`session_id`，即对话 session 在多智能体下的推广）| **元数据**：排序、渲染、管理、将来的回滚；**不是召回边界** |
| agent | **感知**（逐句听众 + `visible_engrams_at`）| 认知边界：每个 agent 只能回忆它感知到的话 |

**产品定位**：原文通道的产品面是**通用摄入 API**，由可信后端（如模拟器）调用。Claude Code transcript 只是测试数据。

**范围（用户 2026-10-20 裁定）**：世界/场景的**管理能力**（多世界 Dashboard、场景快照、回滚、分叉）**另起任务**，不在本设计内。本设计只做三件为它铺路、且现在做几乎零成本的事：感知授权、场景元数据、原话可重放（§3.5）。

## 0. 结论

左脑 = 一条原文召回 lane：原始话轮存 `source_documents` + engram，按**向量**检索，以 `[SOURCE]` 标签渲染，与右脑语句候选在同一 `Candidate` variant 上 RRF 融合。**召回授权基于感知**：只返回查询主体感知过的话。

**能力边界**：同一世界内**跨场景**召回是默认行为（agent 记得它参与过的所有场景），这与评测证据的会话结构一致。§1 的读数仍是"在互相隔离的基准库里观察到的跨会话检索证据"，**不是**感知授权或多智能体场景的验证——那需要多智能体数据，本轮没有。

## 1. 证据及其正确边界

| 事实 | 读数 |
|---|---|
| 真实检索，带日期原文 vs 带日期三元组 | 84.1% vs 17.9%（+66.4pp）|
| 日期边际贡献 | +29.2pp（k=20），k=6 时 +25.7pp |
| 生产 source 腿 BM25 vs 评测用向量 | 55.4% vs 84.1%（**判劣**）|
| BM25 证据召回@20 | 55.1%（向量 89.4%），34 题零证据 |
| 抽取对个人事件的保留率 | 11.1% |

**这些实验实际是什么**（v2 的 §7.5 说错了，这里更正）：

- LongMemEval 113 道时序题：每题 haystack 有 **41 到 58 个会话，中位 47，只有 14 道题正好 47**（v2 写"每题 47 个会话"是错的）。
- LoCoMo：**10 个对话组，每组 19 到 32 个会话**（v2 写"每组 10 个会话"是错的）。
- 评测实现是**每题/每组一个独立库**，把话轮平铺成 statement 行后直接调 `SemanticRetriever`（`spike_run.py:78,113`、`locomo_l1.py:115`）。它**没有**经过感知授权、没有跨库隔离、没有 planner 融合。

**因此准确的表述是**：这是"在互相隔离的基准库里观察到的跨会话检索证据"。它说明**同一主体跨会话召回原话有价值**，而 v4 的默认行为正是同一世界内跨场景召回，二者方向一致。

**但它验证不了感知授权**：基准里每题只有一个"用户"和一个"助手"，没有第三方，不存在"谁在场、谁不在场"的问题。感知授权在多智能体下是否正确，必须用多智能体数据单独验证（§9 的感知用例；更大规模的评测属于世界/场景任务）。

## 2. 接入点与生效范围

| 入口 | 经过 planner | 位置 |
|---|---|---|
| `/api/converse`、`/ws/converse` | 是 | `engine.py:495-514` → `_memory_core.py:254-263` → `memory_ops.cpp:376`（planner 在 `:395`）|
| `/api/recall` 带 intent | 是 | `commands.py:114-129` → `engine.py:598` → `_memory_core.py:220-241` → `retrieval_planner.cpp:86` |
| `/api/recall` 不带 intent | 否 | `commands.py:130-137` → `_memory_core.py:196-218`；completion 模式走 `PatternCompletor` |
| OpenClaw recall / workingSet | 否 | `runtime.ts:123`、`index.ts:112-114` |

左脑只接 planner 内部。这是范围限制，不是缺陷。

**intent 限制照搬父 spec**（`2026-10-17-...md:102-118`）：FACT_LOOKUP、HISTORY、PREFERENCE、ABSTAIN_CHECK 开；BELIEF_OF_OTHER、META_BELIEF、COMMON_GROUND、COMMITMENT_DUE、NORM_LOOKUP 不开。

## 3. 授权：信任边界与认知边界

### 3.1 两种边界必须分开（v4 新增，回应 Codex 三轮 #7）

| 边界 | 回答的问题 | 由谁保证 |
|---|---|---|
| **信任边界** | 谁有权调用 Starling | **部署**：租户（世界）由服务端配置或服务端注册表决定，**通用摄入 API 与查询 API 都不接受请求里的租户** |
| **认知边界** | 每个 agent 能回忆什么 | **Starling 核心**（C++）：感知授权，见 §3.2 |

**信任模型取方案 A（可信应用边界）**，用户 2026-10-20 裁定。含义：

- 租户是**唯一的安全边界**。现状正是这样实现的：Dashboard 的租户来自进程配置（`config.py:49,103`、`engine.py:182`），请求体里没有租户字段；C++ 的 `scope()`（`source_retriever.cpp:70-74`）只检查非空，不做授权，它信任调用方。
- 通用摄入 API 是**可信后端 API**，调用方是该租户自己的服务端代码（如模拟器）。调用方声明的 `speaker`、`audience`、`session_id`、`observed_at` 是**它对世界发生了什么的断言**，Starling 不验证其真伪。恶意调用方可以把某个 agent 伪造进听众列表——这在 A 下是被接受的，因为调用方本身就是可信的。
- **v3 的"签发 + 交叉校验"并不建立所有权**（Codex 三轮 #7 指出得对：知道一个标识不等于有权使用它；payload 与索引一致只证明一致性）。v4 不再把它称为授权；交叉校验保留，作用改为**数据完整性检查**（防索引行与 payload 不一致导致的错配）。
- **不适用 A 的部署形态**：一个进程服务多个租户、或一个租户内有多个互不信任的终端用户共用一个 token。这两种情形需要请求级认证（token → tenant 映射，或完整的主体授权），不在本设计内，属于世界/场景任务（多世界 Dashboard 需要管理面与查询面分离）。

### 3.2 感知授权（v4 核心）

**规则**：查询主体 P（`perspective`，未设则为 `querier`）能召回一个原话单元 u，当且仅当 u 所在的 engram 属于 `KnowledgeFrontier::visible_engrams_at(tenant, P, as_of)`。

`visible_engrams_at` 已实现并在用（`knowledge_frontier.cpp`；调用方：`tom_engine.cpp:30`、`mentalizing_know.cpp:139`、`retrieval_planner.cpp:125`）。它的 SQL 写成"在场记录 ∪ 被明确告知 ∪ 可访问来源 ∪ 群体成员 − 明确未被告知"。左脑直接复用，不自造授权逻辑。

**v4.1 更正（Codex 四轮，已逐条核对代码）——这套机制的实际语义比 SQL 的写法窄，左脑必须按实际语义设计：**

| 事实 | 依据 | 对左脑的影响 |
|---|---|---|
| **群体成员这一路现在不工作，用户 2026-10-20 裁定"修"** | `record_group_membership` 以 `source_engram_id = nullopt` 写入；可见性查询的 membership 分支要求 `source_engram_id IS NOT NULL`。另外 `insert_frontier_fact` 在两个 id 都为空时用 `random_hex_32()` 合成主键，所以**重复调用会插入重复行**（不是幂等） | 见 §3.2b 的修法 |
| **在场记录先写入的时间赢** | 主键合成为 `cognizer:engram`，`INSERT OR IGNORE`（`insert_presence`）| 事后用更早时间补写会被**静默忽略**；首次写入若用了偏晚的时间，该 engram 在这之前的 as-of 查询里不可见。因此 presence 必须在**原话写入的同一事务里、用世界时刻**一次写对，不能依赖事后回填 |
| **"明确未被告知"按 engram 整体扣除，且不看时间先后** | `EXCEPT` 按 `source_engram_id` 扣，不比较 `asserted_at` 的先后 | 对一句话标"X 未被告知"会把**整个 engram**（同组所有原话）对 X 扣掉；之后再标"已告知"也恢复不了。按 `(场景, 听众)` 分组后一个 engram 可能含多句话，粒度变粗。v4.1 规定：左脑**不使用** `explicit_not_told` 表达可见性，"谁没听到"由不把他写进听众来表达 |

**与右脑的关键差异（必须写明）**：planner 现在只在 `perspective ≠ querier` 时才套 frontier 遮罩（`retrieval_planner.cpp:121`：`need_mask = perspective != q.querier`）。agent 查**自己**的记忆时不做感知过滤——对右脑这是对的，因为语句本身按 `holder_id` 归属，查自己的信念不需要遮罩。**左脑不能沿用**：原话不按 holder 归属，自查时若不过滤，agent X 就能召回它从未听到的话。因此 **source lane 无条件按 P 套 `visible_engrams_at`**，不论 `perspective` 是否等于 `querier`。

**写入侧**：每次写入一组原话，对其 `audience` 中的每个 agent 调用 `KnowledgeFrontier::record_presence_from_statement(tenant, audience, engram_id, observed_at, conn)` 记录在场。presence 的 `observed_at` 取该 engram 内最早一句的时间（frontier 只在 engram 粒度判可见；engram 内各句的时间由 §4.2 的 unit 级 `observed_at <= as_of` 再过滤，两层一致）。

**粒度要求**：`visible_engrams_at` 按 engram 判可见。若一个 engram 混入不同听众的话（A 先对 B 说一句、再对 C 说一句），engram 级判断就会错。因此 **写入必须按 `(session_id, 听众集合)` 分组成 engram**，一个 engram 内所有原话的听众相同、场景相同。见 §5.1。

**说话人与听众的关系**：说话人默认属于听众（说的人当然知道自己说了什么）；写入时若 `audience` 不含 `speaker`，自动补上。听众为空的单元拒收（`empty_audience`）。

### 3.2b 修群体成员这条路（用户 2026-10-20 裁定"修"）

**现状是坏的，有两处缺陷**：
1. `record_group_membership` 写入时 `statement_id` 与 `source_engram_id` 都为空（`knowledge_frontier.cpp` 的该函数），而 `visible_engrams_at` 的 membership 分支要求 `source_engram_id IS NOT NULL` ——**这条路永远贡献 0 条可见 engram**。
2. `insert_frontier_fact` 在两个 id 都为空时用 `random_hex_32()` 合成主键，`INSERT OR IGNORE` 形同虚设，**重复调用会插入重复行**。

**修法取"写入时展开"，不取"查询时按组成员关系扩展"**：

| 方案 | 做法 | 判断 |
|---|---|---|
| **写入时展开（采用）** | 调用方给出听众时可以直接写 `audience = ["alice","bob","group:team"]`。C++ 在写入事务内把 `group:*` 展开成**当时**的成员列表，再按 §5.1 分组、逐 agent 写在场记录 | 语义正确：感知是**当时**发生的事实，后来加入组的人不该凭空获得之前的记忆。且不新增可见性分支，不改 `visible_engrams_at` |
| 查询时扩展（不采用） | 让 membership 分支返回组成员能看到的 engram | 需要 engram→group 的关联与成员有效期，且"后来入组能看到历史上所有组内对话"在模拟器里是错的 |

**随之要修的两处底层缺陷**（都属于 C++ 核心，须带测试）：

1. **成员关系必须有时间维度，不能只按 `(cognizer, group_id)` 去重**（Codex 五轮 #5 指出 v4.2 的错）。按 `(cognizer, group_id)` 单行会丢掉加入/离开的时间；而按时刻解析"当时谁在组里"正需要它。因此**新建一张有历史的成员表**，不复用 `cognizer_frontier_facts`（它的 `metadata_json` 只存 `group_id`，无法可靠做时间查询，Codex 五轮 #6），也不放进 `cognizers`（那是认知体本身）：

```sql
CREATE TABLE cognizer_group_membership (
  tenant_id    TEXT NOT NULL,
  group_id     TEXT NOT NULL,
  cognizer_id  TEXT NOT NULL,
  joined_at    TEXT NOT NULL,        -- 生效时刻（世界时刻/事件时间，不是写入时刻）
  left_at      TEXT,                 -- NULL = 仍在组内
  recorded_at  TEXT NOT NULL,        -- 写入时刻，供审计
  PRIMARY KEY (tenant_id, group_id, cognizer_id, joined_at)
);
CREATE INDEX idx_cgm_asof ON cognizer_group_membership(tenant_id, group_id, joined_at);
```

   - **幂等**：主键含 `joined_at`，同一 (组, 成员, 生效时刻) 重复写入被 `INSERT OR IGNORE` 吸收；同一成员在不同时刻的多次加入是不同行，历史完整保留。
   - **as-of 查询**：`WHERE group_id=? AND joined_at <= ? AND (left_at IS NULL OR left_at > ?)`。
   - **离开**：`UPDATE ... SET left_at=?`，只影响之后的 as-of 查询，不改写历史。
   - 旧 `record_group_membership` 的写入改为写这张表（`asserted_at` 作为 `joined_at`），`cognizer_frontier_facts` 里原有的 membership 行保留不动但不参与可见性。

2. **`visible_engrams_at` 的实际语义写清**：membership 分支在修好之前永远为空。文档不再宣称"五路并集"，改为"三路有效 + 成员关系仅经写入时展开生效"。

**右脑影响**：新建成员表本身不改变任何现有可见性（该分支此前恒为空，v4.3 也不扩展 `visible_engrams_at`）。真正的行为变化来自 §3.4b 的在场权威统一。两项可分开评审：先做 §3.4b + 成员表，再启用写入时展开。

**组本身怎么存**：`record_group_membership` 已有 `metadata_json={"group_id":...}` 的写法，但它只记录"某 cognizer 属于某组"，**没有"组在某时刻有哪些成员"的可查询视图**。写入时展开需要一个按 `group_id` 查成员的查询，实现上就是 `SELECT cognizer_id FROM cognizer_frontier_facts WHERE fact_kind='membership' AND json_extract(metadata_json,'$.group_id')=? AND asserted_at <= ?`。这条查询要加到 `KnowledgeFrontier`，并由它负责展开，**不由 Python 展开**（边界裁定：授权语义在 C++）。

**右脑影响**：修好 membership 幂等本身不改变任何现有可见性（因为该分支此前恒为空，且现在仍不参与 `visible_engrams_at`）。真正的行为变化来自 §3.4b 的在场权威统一。因此这两项可以分开评审、分阶段落地：
- 先做 §3.4b（统一在场权威）+ 幂等修复，这两项都不改 `visible_engrams_at` 的语义；
- 写入时展开是左脑 lane 新增的能力，只影响左脑新写入的数据。

**测试要求**：同一组重复写同一批原话不产生重复在场行；组在 T1 有成员 {a,b}、T2 加入 c，T1 的原话对 c 不可见、T2 之后的可见；空组拒收（`empty_group`）；组内成员不在 `allowed` 租户范围内时拒绝。

### 3.3 场景是元数据，不是召回边界

- 场景复用 unit 已有的 `session_id` 字段，不新增字段：**场景就是对话 session 在多智能体下的推广**，同一个概念用同一个字段。
- **召回不按场景过滤**：agent 默认能回忆它参与过的所有场景。v3 的 Session 模式（只召回当前会话）在这个场景下是错的——agent 每换一个场景就会失忆。
- 场景的用途：排序与渲染（同一场景内按 `turn_index`）、管理端按场景查看与删除、将来的场景回滚（§3.5）。
- 场景过滤作为**可选的相关性参数**留到世界/场景任务，本设计不实现。它不承担授权作用。

### 3.4 移除的内容

v3 的 `SourceScope{Off|Session|Project}`、`project_key`、Session/Project 两套授权规则**全部移除**。理由：感知授权已经给出了正确的认知边界，作用域模式与之重复且在多智能体下是错的；`project_key` 的身份稳定性问题（Codex 二轮 #2、三轮 #7）随之消失。`ConverseParams`/`PlannerQuery` 不再需要新增作用域字段——查询主体已经由现有的 `querier`/`perspective` 表达。

### 3.4b 左脑写在场记录会改变右脑的结果（v4.1；v4.3 补顺序与冲突规则）

**这不是假设，是代码事实**：
- 严格语义来源链接下，右脑抽取**刻意复用** `retain_source_turns` 注册的同一个 engram（`eval_ladder.py:588-591`、`:661-664`：`adapter_name="source_turns"`、同一 `source_prefix`，注释写明"否则严格语义来源链接会失败"）。所以右脑语句的 `evidence_json` 引用的正是左脑的原话 engram。
- planner 的遮罩是"语句的任一证据 engram 可见，则语句可见"（`retrieval_planner.cpp:345-356`，按子串匹配 `evidence_json`）。
- `does_X_know`：语句的任一证据 engram 对 X 可见，结果就从 `Unknowable` 变为 `NotKnown`（`mentalizing_know.cpp:142-145`）。

**因此**：左脑给某个 engram 的听众写在场记录，从这个 engram 抽出的右脑语句就对这些听众可见，ToM 的"X 知道吗"结果也随之改变。**只含原话、没有被抽取的 engram 不产生信念**——影响只发生在左右脑共用的 engram 上。

**这是想要的行为，不是泄漏**：B 在场听 A 说话，B 理应能看到"A 相信什么"，ToM 推理"B 是否知道"也理应改变。但它必须有唯一的权威。

**v4.3 的规则（回应 Codex 五轮 #1、#2、#3）**：

1. **听众先于抽取落库，抽取只读不写。** 顺序固定为：① 写原话 engram（`retain_source_turns`）→ ② 在同一事务内写 `source_unit_meta`（含 `audience`）与逐 agent 的在场记录 → ③ 抽取在同一事务内读该 engram 的 `audience` 作为 `perceived_by`，**不得自行推断，也不得再写在场记录**。
2. **对来源 engram，抽取不得覆盖冲突值。** 现状只在 `perceived_by` 为空时填默认值（`extractor.cpp:872-874`），所以预填值会存活——这正是 v4.2 方案不成立的原因。v4.3 改为：若 engram 有 `source_unit_meta` 记录，`perceived_by` **强制取自**该记录的 `audience`；抽取若给出不同集合，视为合同错误并拒绝（`perceived_by_conflict`），不静默合并。
3. **竞态规则**：在场记录是 `INSERT OR IGNORE` 且按 `cognizer:engram` 合成主键（`knowledge_frontier.cpp:39-45`），**后写的收窄不掉先写的**。因此顺序不能反过来：必须先写声明听众，再抽取。同一事务内完成，用同一个连接（Codex 五轮 #7 也要求同一连接，否则有快照竞态）。
4. **无听众来源的兼容规则**：普通 `remember`（非原话路径）没有 `audience`，保持现有 `{holder, interlocutor}` 回退不变，历史行为逐字节兼容。**空听众不等于"所有人可见"**；对来源 engram 而言空听众直接拒收（`empty_audience`）。

**回归要求（Codex 五轮 #4）**：只有当声明听众恰好等于旧的推断两人对时，行为才不变；任何不一致都会同时改变 planner 可见性与 ToM 结果。因此测试必须覆盖：预填冲突的 `perceived_by`、抽取在前与在后的两种顺序、多智能体听众的精确性、普通 remember 的回退、planner 遮罩、`does_X_know`，然后跑 SocialMemBench（0.7825）与 HiToM 的回归。

### 3.5 为世界/场景任务铺路（本设计内做，零成本）

用户 2026-10-20 裁定世界/场景管理另起任务（见 §14）。但以下三件事现在不做、以后就要重灌全部历史数据，因此在本设计内完成：

1. **感知授权**（§3.2）——它本身就是左脑 lane 的正确性要求，不是额外功能。
2. **场景元数据写入即固定**：`session_id`（场景）、世界时刻（`observed_at`，模拟时钟）、`audience`、`provenance` 都作为原话 payload 的一部分写入，不可变。
3. **原话可重放不变量**：原话 payload 只追加、不改写，保留到 engram 被擦除为止（`retention_mode='audit_retain'`）；payload 必须自足，包含重新摄入所需的全部字段（说话人、文本、场景、句序、时间、听众、来源）。将来"保留后续场景"的回滚要靠它：从快照分叉后，把要保留的场景的原话重新摄入。**已知限制**：重新摄入会重新调 LLM 抽取，右脑重建出的信念不保证与原来逐字一致；这是语义重建，不是精确恢复。

## 4. 检索与融合

### 4.1 类型化候选

采用父 spec 的 `std::variant<StatementCandidate, SourceCandidate>`。`SourceCandidate` 字段：`tenant_id`、`engram_ref`、`clause_id`、`speaker`（渲染归属用，**不再作授权依据**）、`audience`（写入时的听众集合，供诊断）、`session_id`（场景，元数据）、`turn_index`、`observed_at`（**unit 级**，见 §5.3）、`provenance`、`text`、`score`、`rrf_rank`。

**去重身份（Codex 二轮 #8）**：v2 只写 `(tenant, engram_ref, clause_id)`，但增长的 transcript 快照会得到新 engram_ref，导致同一话轮重复出现、白白占上下文。v3 改为与现有 observer 一致的元组去重：`(speaker, session_id, turn_id 或 turn_index, observed_at, text)`（参照 `source_retriever.cpp:1423` 的 `seen_turns` 构造；v4 把 `holder` 换成 `speaker`，因为原话不再按 holder 归属）。

### 4.2 fetch

1. 问题嵌入（与语句腿同 embedder/model/dim；不匹配的行不参与）。
2. `SourceVectorIndex::search`，**所有条件在 SQL 下推、排序之前**：
   - `tenant_id` 精确匹配；
   - **感知**（§3.2）：命中的 engram 必须属于 `visible_engrams_at(tenant, P, as_of)`，其中 `P = perspective`（未设则 `querier`）。**无条件套用**，`perspective == querier` 时也要套——这是与右脑 planner 遮罩（`retrieval_planner.cpp:121` 只在 `perspective != querier` 时遮罩）的关键差异。实现上把可见 engram 集作为 `IN (...)` 下推（集合过大时改为 join 临时表），发生在排序之前；
   - `status='embedded'`；
   - **时间三重界**：`registered_at <= as_of` 且 `engram.created_at <= as_of` 且 **`observed_at IS NOT NULL AND observed_at <= as_of`**。
     - v2 写 `(observed_at IS NULL OR ...)` 与"无时间不可见"自相矛盾（Codex 二轮 #9 指出）。v3 明确：**source lane 只召回有可信时间的 unit**，`observed_at IS NULL` 的一律不进候选。
     - 理由：`observed_at` 是渲染日期与 as-of 语义的唯一依据；缺失时既不能排序也不能截断。这类 unit 仍存在于库中（可审计），只是不进召回。这要在 receipt 里计数 `source_no_time`。
   - `erased_at IS NULL`、`retention_mode='audit_retain'`（对齐 `source_retriever.cpp:1377`）。
3. **回填（Codex 二轮 #8）**：v2 的"取 k×3"不保证 k 条——若前 3k 全被去重或复核拒绝，后面还有合法行也拿不到。v3 改为**迭代回填**：以倍增批量取（k、2k、4k…，上限 `k_max=200`），直到凑够 k 条或遍历完符合条件的集合；若遍历完仍不足，返回实际条数并在 receipt 标 `source_truncated=true`（截断），**不**标成"语料不足"。
4. **payload 交叉校验（数据完整性，不是授权）**：解析 unit → `unit.session_id == 索引行 session_id` → 内容哈希与 `engrams.content_hash` 一致 → `erased_at IS NULL`。任一不符丢弃并计数 `source_unit_rejected`。**注意**：这一层只防索引与 payload 错配，不建立所有权（§3.1）；真正的认知边界是第 2 步的感知过滤。
   - **v4.1 更正（Codex 四轮）**：v4 在这里还有一步 `P ∈ unit.audience`，**这与感知规则自相矛盾**——通过 `explicit_told` 获得可见性的 agent 不在听众列表里，会被它错误拒绝。v4.1 删除该步。授权**只**由第 2 步的 `visible_engrams_at` 决定；`audience` 只作诊断与重建用，不参与授权。
5. **与 `global_holder_filter` 的交互**：左脑不受它约束（它是语句侧的 holder 过滤），但若查询同时设置了 `global_holder_filter` 且其值不在感知主体内，照现有 `invalid_scope_filter_mix`（`retrieval_planner.cpp:204-212`）拒绝整次查询，不静默降级。

### 4.3 融合：RRF

两路各自按名次，`score = Σ 1/(60 + rank)`，`k=60`（RRF 用名次，不需要分数同分布——v1 的相反说法是错的）。融合后按 score 降序、同分按 identity 稳定排序，每行带 `lane` 与 `rrf_rank` 进 `score_breakdown`。统一字节预算（`chunk_byte_budget`，默认 8000），按整行截断，计数 `budget_skipped`。不引入 `min_source_items`（父 spec 已放弃该参数）。

### 4.4 abstain（Codex 二轮 #6，v2 的判据是错的）

v2 用 `best_source_rank <= k` 判"有证据"——**这等于取消低分保护**：只有 source 候选时，最不相关的那条也是 rank 1，自动通过。

v3 改为**分数判据 + 预算后判定**：

- source 候选的相似度分数与语句的 `final_score` 不可直接比，所以**分别设阈值**：`tau_source`（新配置项，默认待实测确定，初始取与 `tau_recall=0.25` 同量级但必须由一次标定实验给出，不拍脑袋）；
- `AbstentionInput` 增加 `best_source_score`（无 source 为 `-inf`）；
- 判据：`any_candidates || best_source_score >= tau_source`；
- **预算之后判定**：只有当该 source 行**实际进入了渲染后的 context pack** 才算证据（被字节预算截掉的不能用来宣称"有证据"）；
- 语句侧三个否决条件（frontier/recanted/conflict）对 source 不适用，但成立时仍拒答，理由里带 `source_available` 供诊断（保守，见 §14）。

`tau_source` 未标定前，**lane 默认关闭**——这一步是硬约束，不允许用未经标定的阈值上线。

### 4.5 渲染

**payload 的真实结构（v2 已更正，此处确认）**：带版本前缀的行（`turn_prefix="@starling/source-turn-v1 "`，`claim_contract.cpp:120`；容错 `v2` 在 `:121`）。`units()` 产出的 unit 里 `text` 是整行原文，解析后的说话内容在 `utterance`（`claim_contract.cpp:194`）。

**时间来源（Codex 二轮 #9；用户 2026-10-20 澄清后进一步修正）**：v2 说"按 `adapter_name` 区分 `source_turn` 与 `ingest_clock`"——**不成立**，因为 `retain_source_turns` 对所有调用都写死 `adapter_name="source_turns"`（`source_retriever.cpp:1297`）。

v3 原以为"本轮只有一个写入路径，一律 `source_turn`"，但 §6.3 的裁定（通用摄入 API，transcript 只是测试数据）使 `ingest_clock` 成为真实用例。因此：

- **provenance 显式存储**：写入 API 增加必填参数 `provenance ∈ {source_time, ingest_clock}`，落 `source_unit_vectors.provenance` 列（§5.3）。
- `source_time` → 渲染日期；`ingest_clock` → **不渲染日期**（行仍出现，日期位留空）。
- 检索侧不因 provenance 过滤：两种来源都可召回，只是显示不同。as-of 截断对 `ingest_clock` 用 `observed_at`（= 摄入时刻）判断，语义正确。

**多行注入（Codex 首轮 #11）**：原文换行 JSON 转义为单行，续行不产生标签前缀；`neutralize_recall_fence`（`memory_ops.cpp:360`，在 `:408` 调用）继续作用于 SOURCE 行。

**标签**：`ContextPackLabel` **追加** `SOURCE` 在末尾（`context_pack.hpp:15`），现有值编号不变；Python 镜像同步（`bind_05_retrieval.cpp:274-282`）。枚举自省会变，需审计所有遍历/长度断言。

### 4.6 计数、receipt、Python 返回

- `PlannerResult` 增加 `source_entries`；**计数与充分性以融合后的 `entries` 为准**；
- `RetrievalReceipt` 增加 `source_candidates`、`source_selected`、`source_rejected`、`source_no_time`、`source_truncated`、`source_partial`、`source_degraded_reason`、`source_audience_mismatch`、`frontier_visible_engrams`（感知过滤后的可见集大小，供诊断）；
- Python 侧**两处返回结构不同，v2 说错了**（Codex 二轮 #12）：
  - `memory.py:189-190` 返回 `{"row": e.row, ...}`——整个 row 对象，不是扁平字段；
  - `engine.py:613-617` 是扁平化 `subject/predicate/object`。
  - 两处都要改：source 条目带 `kind:"source"` 与 `engram_ref/clause_id/speaker/session_id/observed_at/text`；statement 条目补 `kind:"statement"` 保持向后兼容。

## 5. 存储

### 5.1 写入侧不是"不变"（Codex 二轮 #7；v4 因感知授权再改分组键）

v3 写"写入路径不变"。**不成立**。v4 在此基础上又改了一处**分组键**，这是感知授权的直接要求：

1. **分组键从 speaker 改为 `(session_id, audience 集合)`**。现状 `source_retriever.cpp:1279-1283` 用 `std::map<speaker, turns>` 按说话人分组，同一说话人的话跨会话、跨听众会被并成一个 engram；而 `visible_engrams_at` 按 engram 判可见（§3.2），一个 engram 混了不同听众就会错判。**一个 engram 必须是"一个场景 + 一组固定听众"**，组内可以有多位说话人（`speaker` 仍逐句保留，用于渲染归属，不再用于授权）。
2. **写入时必须记录在场，且顺序固定**（v4.3 补，Codex 五轮 #2、#7）：对 `audience` 中每个 agent 调 `KnowledgeFrontier::record_presence_from_statement(tenant, audience, engram_id, observed_at, conn)`。**必须在抽取之前、同一事务、同一连接**——在场记录是 `INSERT OR IGNORE` 且按 `cognizer:engram` 合成主键（`knowledge_frontier.cpp:39-45`），先写入的收窄不掉，所以抽取先写会把声明的听众永久并进可见集。组名（`group:*`）在此步展开成当时的成员（§3.2b）。
3. **原文、`source_unit_meta`、pending 向量行、presence、抽取必须同一事务完成**，否则会出现"原文写成功、但召不到"或"索引有了、感知没记"的静默不一致。**v4.1 更正（Codex 四轮）**：v4 说"`retain_source_turns` 内部自行提交、无法原子"是错的——`TransactionGuard` 支持嵌套（`connection.hpp:44`：最外层守卫持有 `BEGIN IMMEDIATE`，内层用 SAVEPOINT），外层开一个事务包住即可，**不需要改它的提交方式**。
4. **删除 `project_key` 相关写入**（§3.4 已移除该概念）。

这四处是 v4 的主要实现面，工作量不小，不能按"复用现有原语"估算。**grouping 变化还会改变幂等键**：engram 的幂等键是 `sha256(payload)` 前 16 hex（`memory_ops.cpp:65`），分组键变化会改变 payload 内容，因此**历史数据的分组与新版不一致**，需要迁移策略：旧 engram 保留原样（其听众按 `speaker` 回填为单元素听众集），新写入按新键分组。这一点必须写进迁移。

### 5.2 向量索引：新后端

`VectorIndex` 硬绑 `statement_vectors`（`sqlite_blob_vector_index.cpp:27`）、`SearchScope` 单 holder、返回 `ScoredId` 只有 id+分数、planner 拿不到 `SemanticRetriever` 的私有 embedder。因此新增：

```cpp
struct SourceVectorHit { std::string engram_ref, clause_id, speaker, session_id; double score; };
class SourceVectorIndex {
public:
    virtual void upsert(persistence::Connection&, const SourceUnitKey&, const SourceUnitMeta&,
                        const std::vector<float>&, std::string_view model, int dim) = 0;
    virtual std::vector<SourceVectorHit> search(persistence::Connection&, const std::vector<float>&,
                                                int k, const SourceSearchScope&) = 0;
    virtual void erase(persistence::Connection&, std::string_view tenant, std::string_view engram_ref) = 0;
};
```

`SourceSearchScope` = `{tenant_id, visible_engrams（感知过滤后的可见集合）, as_of, include_unknown_time}`。**注意它不持有 holder 列表**：授权不再按 holder，而在 SQL 里按可见 engram 集合过滤（§4.2 第 2 步）。

SQLite 实现是**全量扫描 + 排序**，与现有实现同构。这是已知扩展性上限，必须进验收指标（延迟随 unit 数曲线）。依赖注入：给 `RetrievalPlanner` 增加可选 `SourceLaneDeps{SourceVectorIndex*, EmbeddingAdapter*, int dim, std::string model}`，为空即关闭。两个 planner 构造点都要接线。

### 5.3 表：元数据与派生索引分离（v4.3 重构）

**v4.3 的结构变化（回应 Codex 五轮 #9）**：v4.2 把 `audience`、`session_id`、`provenance` 都存在 `source_unit_vectors` 里——那是**派生索引**，删掉重建会丢数据。而这三项是**权威元数据**（重建要用、授权要查、审计要留）。因此拆成两张表：

```sql
-- 权威元数据：写入即固定，只追加，重建的来源
CREATE TABLE source_unit_meta (
  tenant_id     TEXT NOT NULL,
  engram_ref    TEXT NOT NULL,
  clause_id     TEXT NOT NULL,
  speaker       TEXT NOT NULL,      -- 渲染归属
  session_id    TEXT NOT NULL,      -- 场景
  audience_json TEXT NOT NULL,      -- 展开后的听众（组已在写入时展开，§3.2b）
  turn_index    INTEGER,
  observed_at   TEXT,               -- NULL = 无可信时间，不参与召回
  provenance    TEXT NOT NULL CHECK (provenance IN ('source_time','ingest_clock')),
  PRIMARY KEY (tenant_id, engram_ref, clause_id)
);
CREATE INDEX idx_sum_session ON source_unit_meta(tenant_id, session_id);

-- 派生索引：可整表重建，删了不丢信息
CREATE TABLE source_unit_vectors (
  tenant_id      TEXT NOT NULL,
  engram_ref     TEXT NOT NULL,
  clause_id      TEXT NOT NULL,
  dim            INTEGER NOT NULL CHECK (dim > 0),
  model          TEXT NOT NULL,
  index_vector   BLOB,
  raw_embedding  BLOB,
  status         TEXT NOT NULL CHECK (status IN ('pending','embedded','failed')),
  retry_count    INTEGER NOT NULL DEFAULT 0,
  last_attempt_at TEXT,
  embedded_at    TEXT,
  PRIMARY KEY (tenant_id, engram_ref, clause_id)
);
CREATE INDEX idx_suv_scan ON source_unit_vectors(tenant_id, status);
```

**要点**：
- 检索时 `observed_at`/`session_id` 从 `source_unit_meta` 取，向量表只存向量与索引状态。`search` 的实现因此是一次 `JOIN source_unit_meta`，而不是从单表取。
- **重建只依赖 `source_unit_meta` + payload**，不依赖向量表。这同时修好了 Codex 三轮 #9（provenance 无法重建）。
- 旧数据的回填：`source_unit_meta` 从既有 payload 解析生成；解析不出的 unit 不入表（不可召回），计入迁移报告。
- `source_unit_meta` 加入 `clear_tenant` 的删除列表（与 `source_documents` 同列），异步清理按 `erased_at` 删。

**授权仍然不出现在这两张表里**：可见性是 `cognizer_presence_log` 经 `visible_engrams_at` 算出来的（§3.2）。`audience_json` 是诊断与重建用的记录，不是授权依据（§4.2 第 4 步已删除 `P ∈ audience` 检查）。

### 5.4 擦除

- **读侧立即生效**：查询条件含 `erased_at IS NULL`，被擦除 engram 的 unit 立刻不可见，不依赖清理任务；
- 异步清理：tick 删除 `engrams.erased_at IS NOT NULL` 的向量行，滞后进 Vitals；
- `clear_tenant` 的删除列表加入 `source_unit_vectors`（`memory_ops.cpp:642` 附近）；
- 测试必须有：擦除后同一事务外立刻查询，该 unit 不出现。

### 5.5 嵌入生命周期

| 环节 | 做法 |
|---|---|
| 产生 | `retain_source_turns` 内为每个 unit 插 `pending` 行（与原文写入同一事务，§5.1 第 2 点） |
| 驱动 | 现有 `EmbeddingWorker` tick 按 kind 分支；source 分支扫 `status IN ('pending','failed') AND retry_count < 3` |
| 背填 | 首次启用时一次性把已有 `source_documents` 入队（迁移的一部分，非运行时） |
| 重试 | 沿用现有语义：`retry_count+1`、`last_attempt_at` 更新、`>=3` 永久 failed。**注意**：现有 worker **只按 retry_count 判定，没时间退避**（`embedding_worker.cpp:223` 的 SQL），v2 写"退避"是错的 |
| 模型/维度变更 | 必须同时清空 source 向量并把 `retry_count` **重置为 0**、状态置 `pending`；否则永久 failed 的行会带着 `retry_count>=3` 永远不被处理（Codex 二轮 #10） |
| 原子发布 | 单行 UPSERT 原子；批量 tick 用 SAVEPOINT |
| 重建 | source 专用重建：从 `source_documents` + payload 重新枚举；repair guard 的计数与分支是 statement 专用，需各自的验证（重建后 unit 数 == payload 有效行数） |

### 5.6 降级可见性（Codex 二轮 #10）

`source_partial` 必须有**明确的触发规则**，不是只加个字段：

| 情形 | 标记 | 外部表现 |
|---|---|---|
| 查询嵌入失败 | `source_partial=true`, `reason=query_embed_failed` | 只有语句结果；receipt 明示 |
| 存在 pending/未嵌入 unit | `source_partial=true`, `reason=index_pending`, 附带 `index_pending_count` | 同上 |
| payload 复核拒绝 | `source_rejected>0`，不单独置 partial | 计数可见 |
| 依赖未注入（lane 关闭） | `source_off` | 与"没检索到"区分 |
| 重试耗尽 | `source_partial=true`, `reason=index_failed`, 附带 `index_failed_count` | 同上 |

Vitals 聚合积压与永久失败数。**要求**：任何"没检索到"的查询，receipt 必须能区分"语料里没有"与"索引没建好"。

## 6. 写入侧与 Python 适配

### 6.1 写入入口（两条，都是同一个 API）

**产品入口：通用摄入 API。** 任何可信后端（如模拟器）提供逐话轮数组即可写入左脑。v4 的合同升到 **v3**：

| 字段 | 必填 | 说明 |
|---|---|---|
| `speaker` | 是 | 渲染归属；若不在 `audience` 中会被自动补入 |
| `text` | 是 | 原话正文 |
| `audience` | **是（新增）** | 听众 cognizer id 数组，非空；空则拒收 `empty_audience` |
| `session_id` | **是（新增必填）** | 场景；同一调用内必须一致，见下 |
| `turn_index` | 是 | 场景内句序，用于排序 |
| `observed_at` | 视 provenance | `source_time` 时必填；`ingest_clock` 时由**受信摄入代码**写入当前时刻，调用方传值被忽略 |
| `provenance` | **是（新增）** | `source_time` \| `ingest_clock` |
| `turn_id` | 否 | 可空 |

**批次规则**：一次调用可以混多个场景与多组听众，C++ 内部按 `(session_id, audience)` 分组（§5.1）；同一 unit 内出现冲突的 `session_id` 或 `audience` 视为合同错误；分组顺序是确定性的（`session_id` 升序 → 听众排序后字典序 → `turn_index`），保证同样的输入产生同样的 payload，从而幂等键稳定。

**与旧合同的关系**：现有 `@starling/source-turn-v1`（`claim_contract.cpp:120`）只有 6 个字段且 `session_id`/`observed_at` 可为空（`claim_contract.cpp:132`），v4 的合同是 `@starling/source-turn-v3`，由 C++ 按前缀分派。**旧数据（v1/v2）无 `audience`**：迁移时把 `audience` 回填为 `{speaker}`，即只有说话人本人可召回——这是保守的，不会泄漏，但会让旧数据在感知授权下几乎不可检索。这条限制必须在迁移说明里写清。

底层实现是 `retain_source_turns`（`source_retriever.cpp:1267`）加 §5.1 的四处改动。**这是产品面，不绑定前端。**

**测试入口：Dashboard transcript worker**（`engine.py:892`）。它是本轮唯一的端到端消费者，用来验证真实数据上的行为，不是设计依据。接它时必须在现有锁与 generation 检查下：generation 在 `engine.py:871` 捕获、`:470` 检查，新调用放在同一 try 块内，`source_missing` 与 `_TenantCleared` 语义照现有 remember 路径。`retain_source_turns` 继承写入门禁（`memory_ops.cpp:56`），但门禁不等于 generation 检查。

### 6.2 时间与清洗

- **毫秒截断**：`valid_observation_time` 只接受秒级（`claim_contract.cpp:124`），transcript 是毫秒（`2026-10-17T10:17:33.385Z`）。在 Python 适配层截断到秒，不改 C++ 合同。
- **新增 `clean_turns_ts()`**：返回 `(role, text, event_time, turn_index)`；不动 `clean_turns()`，避免破坏 `chunk_dialogue` 的两元解包（`ingest_filter.py:84`）。
- **已知损失**：`clean_turns` 剥掉代码块与超长行，source lane 拿到的是清洗后文本，不是逐字节原文。写明，不掩盖。

### 6.3 来源范围（用户 2026-10-20 裁定：transcript 只是测试数据）

**这条改变了设计的重心。** Claude Code transcript 只是**测试数据**，不是产品的摄入主路径。因此：

- 原文通道的入口必须是**通用的摄入 API**：任何可信后端提供符合 v3 合同（§6.1 字段表）的逐话轮数组，即可写入左脑。这条 API 就是现有的 `retain_source_turns`（`source_retriever.cpp:1267`）加上 §5.1 的改动，**不绑定任何特定前端**。
- Dashboard transcript 摄入（`engine.py:892`）只是**第一个消费者**，也是本轮唯一的消费者，因为它是现成的、可用于端到端验证的数据源。
- **不作为设计依据的**：transcript 的字段形状（`clean_turns` 的清洗损失、毫秒时间戳、SessionEnd 作业的会话关联）。这些是实现第一个消费者时要处理的细节，不是原文通道的普遍约束。v3 的 §6.2 保留为"transcript 消费者的适配说明"，不再当作核心设计的组成部分。
- **`ingest_clock` 不再是空转**：通用 API 的调用方若无法提供事件时间，就填摄入时刻，来源标 `ingest_clock`，渲染时不显示日期。这条来源语义因此有了真实用例（§4.5 需要它能被区分，见下）。

**对 §4.5 的连带影响**：既然通用 API 会有 `ingest_clock` 来源，v3 原来说"本轮只有一个写入路径，一律 `source_turn`"不再成立。因此 **provenance 必须显式存储**，不能推迟到"将来"：写入 API 增加一个必填的来源参数（`source_time` | `ingest_clock`），存进 `source_unit_vectors.provenance` 列。这是把 v2 标记为技术债的东西提到了本轮。

**对授权的连带影响（v4）**：`session_id` 与 `audience` 由可信后端提供（§3.1 方案 A），不是从 transcript 作业推断。v3 担心的"网页端拿不到会话"在 v4 下不再是问题：召回不按会话过滤（§3.3），查询主体由现有的 `querier`/`perspective` 表达，网页端无需知道会话。transcript 作为测试数据时，`audience` 填 `{user, assistant}`，`session_id` 用 job 里已有的会话 id（`ingest_session.py:66`）。

## 7. 开关

| 开关 | 默认 | 说明 |
|---|---|---|
| `source_lane.enabled` | `false` | 关闭即不检索、不渲染 |
| `source_lane.render_time` | `false` | 从属于 enabled |
| `current_date_in_prompt` | `false` | 独立 |

**上线额外门槛**：`tau_source` 未标定前 lane 不得开启（§4.4）。

## 8. 与右脑及不变量

不改右脑三通道的**抽取逻辑与输出形状**、不改六态机、§0.1、Bus 单入口。source unit 无状态，不参与六态机。事实权威在 Statement 图，`[SOURCE]` 靠转义与 fence 保证不冒充。检索/融合/渲染全在 C++，Python 只做信封适配与三元组构造。

**唯一例外（v4.1，§3.4b）**：右脑抽取写入的 `perceived_by` 必须改为取自该 engram 的 `audience`，否则左脑的在场记录与右脑的两人对推断会产生不一致的可见性。这是本设计**唯一**触碰右脑的改动，需要明确批准，并带"两人场景逐字节不变 + SocialMemBench/HiToM 不下降"的回归测试。

## 9. 测试矩阵（Codex 二轮 #11）

| 组 | 用例 |
|---|---|
| **感知（v4 核心）** | A 对 B 说的话：B 能召回，C 不能；A 先后对 B、对 C 各说一句：B 只召回前一句、C 只召回后一句（证明按听众分组正确）；**自查也过滤**：`perspective == querier` 时 X 仍召回不到自己不在场的话；`explicit_told` 使未在场的 agent 可见；`explicit_not_told` 使在场的 agent 不可见；说话人不在 `audience` 时被自动补入；空 `audience` 拒收；as-of 前不在场的话在 as-of 时不可见 |
| 租户（世界） | 跨租户不可召回；请求里不接受租户字段 |
| 场景元数据 | 召回**不按**场景过滤（跨场景可召回）；同场景内按 `turn_index` 排序；`session_id` 写入后不可改 |
| 分组与幂等 | 同一输入重复写入不产生新 engram（确定性分组顺序）；同一调用混多个场景与听众时正确拆分；旧 v1 数据迁移后 `audience={speaker}` |
| 事务原子性 | 原文、pending 向量行、presence 三者同时成功或同时失败（注入故障测试） |
| 时间 | 无 `observed_at` 不召回且计 `source_no_time`；as-of 三重界；未来时间不泄漏 |
| 去重与回填 | 重叠 transcript 不重复占上下文；拒绝数 > 3k 时仍能取到后续合法行或明确 `source_truncated` |
| abstain | 只有 source 且全低分时**拒答**；入选但被预算截掉不算证据；`tau_source` 标定前后行为 |
| 渲染 | 多行原文转义后不产生 `[FACT]`；fence 生效；`render_time=false` 无日期；枚举追加不自省破坏（审计所有遍历） |
| 生命周期 | pending→embedded；重试耗尽；模型变更重置 retry_count；重建后 unit 数一致；查询嵌入失败时 `source_partial` |
| Python | `Memory.query`（row 对象）与 Dashboard（扁平）两条返回都带 source 条目 |
| parity | `enabled=false` 时 planner 输出与现状逐字节相同（固定行集） |

## 10. 验收与预算

- 守护：SocialMemBench 0.7825 不下降（固定行集比对）；
- 不劣化：LoCoMo 全量，非时序不劣化（基线 +3.1pp）；
- 进攻：父 spec 原式 `S_dual − max(S_full, S_rag) ≥ max(5pp, α_judge)`（`2026-10-17-...md:158`）；
- 预算：父 spec 给的是**两个基准各约 3e7**（`2026-10-17-...md:171`），不是合计；
- **单主体基准不覆盖感知授权**：LongMemEval 与 LoCoMo 都是单一主体与对话方，没有第三方在场的问题。在这两个基准上，`audience` 恒为 `{user, assistant}`，感知授权退化为"全部可见"，因此上述判据测的是检索与渲染，**不测**感知授权的正确性。感知授权由 §9 的确定性测试覆盖；多智能体规模的评测属于世界/场景任务（§14）。

### 10.1 `tau_source` 标定实验（2026-10-20 预注册；v4 按 Codex 三轮改为两阶段）

**v4 的定性变化（Codex 三轮 #1、#4、#6）**：本节原方案只能当**试点**，不能当上线门槛。三个原因叠加：
1. **样本太小**：在验收线上刚好达标（TPR 37/46、FPR 4/46）时，Wilson 95% 区间为 TPR [66.8%, 89.3%]（宽 22.5pp）、FPR [3.4%, 20.3%]（宽 16.9pp），区分不了达标与不达标（已独立复算）。
2. **测的不是生产里的东西**：原方案只测"检索出来没有"，生产里命中还要经过 RRF 竞争、字节预算截断、abstain 否决，合格命中可能在渲染前消失。
3. **没有时序题**：92 题里一道时序题都没有，而原方案的验收线允许仅凭非时序结果开启 lane，这与本节自己"时序须单独验证"的要求矛盾。

**因此改为两阶段，上线门槛只看第二阶段：**

| 阶段 | 数据 | 测量 | 用途 |
|---|---|---|---|
| **A 试点** | 92 道单会话、未用过的 LongMemEval 题（下文）| 检索层 TPR/FPR，加难负例 | 选 `tau_source` 的候选值；**不授权上线** |
| **B 验收** | **BEAM-100K**（从未使用，含时序类）| **走完整 planner**：语句候选 + RRF + 预算 + abstain，测"**支持答案的证据实际被渲染**"的比例 | **上线门槛** |

**阶段 A 的修订**：
- **负例分两类分别计分**（Codex 三轮 #2）：随机非证据会话保留为基线；另取**难负例**——与问题共享实体或话题、但人工确认不含答案的会话（按检索相似度挖掘再人工复核）。两类 FPR 分别报告，**以难负例 FPR 为准**。原文"同题同分布"的表述有误：配对只控制了题目，没控制会话相关性。
- **证据充分性审计**（Codex 三轮 #3）：6 道题证据跨多个话轮（如 `35a27287` 有 3 个），"标注话轮全在一个会话"只是筛选规则。阳性命中必须是**支持答案的话轮**，命中证据会话里的无关高分话轮不算真阳性。
- **目标函数**（Codex 三轮 #5）：改为"**在 FPR ≤ 给定上界的约束下最大化 TPR**"，不用 Youden。理由：错答（用无关原文作答）与拒答的代价不对称，前者更糟。

**阶段 B 的预注册判据（跑前另行冻结）**：以置信下界而非点估计判定——证据渲染率的 95% 下界 ≥ 预设值、错误作答率的 95% 上界 ≤ 预设值，样本量按区间宽度反推。具体数值在阶段 A 结束后、阶段 B 开始前冻结。**时序类必须单独达标**，否则 lane 不对时序意图开启。

**阶段 B 依赖**：BEAM 从"P2 复核用"提前为左脑上线门槛。**评测预算已由用户于 2026-10-21 批准：约 1 到 2e7 tokens，单轮内使用。**

下面保留阶段 A 的数据与构造说明。

**数据（可行性检查实测）**：LongMemEval-S cleaned 全量 500 题中，证据话轮恰好落在一个会话、且**从未进入确认集或探索集**的题，去掉弃答题后共 **92 题**：

| 题型 | 题数 |
|---|---|
| single-session-user | 46 |
| single-session-assistant | 36 |
| single-session-preference | 10 |

每题 haystack 有 41 个以上会话（中位 49），证据会话的话轮数中位 12（2 到 32）。

**已知分布偏移（必报）**：**没有一道时序题**。全部 133 道 temporal-reasoning 题都已在确认集或探索集中用过，单会话时序题也全在其中。`tau_source` 是检索层阈值（判"这条原文的向量相似度是否构成证据"），不针对题型，所以在事实/偏好类上标定在原理上可迁移；但时序题的问句形态（"How many days between…"）与证据的词面重合度更低，相似度分布可能整体偏低。因此：**标定出的阈值在时序题上的效果必须单独验证**，不能直接假设成立。

**阶段 A 的正负例构造**（v4：感知授权下，"只给 agent 一个会话可见"由 `audience` 实现，不再靠作用域模式）。每题建一个库，把证据会话与一个负例会话写入，**两个会话的听众不同**：
- **正例**：查询主体是证据会话的听众。lane 应当返回支持答案的证据话轮并判为有证据。
- **随机负例**：查询主体只是一个随机**非证据**会话的听众（种子固定 20261020），看不到证据会话。lane 应当判为无证据（拒答）。
- **难负例**：查询主体只是一个**与问题共享实体或话题、经人工确认不含答案**的会话的听众。判据同上。

**切分**：92 题按题型分层，固定种子对半——**标定半 46 题、留出半 46 题**。阈值只在标定半上选；留出半只报一次数字。

**选阈值（跑前固定）**：在标定半上，在**难负例 FPR ≤ 10%** 的约束下取 TPR 最大的阈值；无阈值满足约束则阶段 A 记为失败，lane 保持关闭。同时报告随机负例下的 FPR 作对照。

**阶段 A 的结论只是候选阈值**：留出半的 TPR/FPR 连同 Wilson 区间一起报告，**不构成上线授权**（样本量不足，见本节开头）。上线由阶段 B 决定。

**成本**：只检索与嵌入，不调 LLM 作答。92 题 × 3 次检索（正例、随机负例、难负例），embedding 约数千次请求，不消耗 deepseek 预算；难负例的人工复核约 92 题。

**依赖**：阶段 A 测的是仓内实现，需要感知过滤 + 向量检索 + 分数输出先存在；阶段 B 需要完整 planner 接线。顺序：实现 → 阶段 A → 冻结阶段 B 判据 → 阶段 B → 达标才开启 lane。

## 11. 剩余风险

1. 上下文体积：S 臂中位 14,743 字符，约语句路径 5.8 倍；默认 k=10 是折中，延迟未实测。
2. SQLite 向量后端全量扫描，扩展性上限已知。
3. 三条入口不覆盖（不带 intent 的 recall、OpenClaw、Working Set）。
4. 清洗后文本不是逐字节原文。
5. **信任模型只在方案 A 的部署形态下成立**（§3.1）：调用方是可信后端，`audience` 由调用方断言、Starling 不核实。一个进程服务多租户、或租户内多个互不信任的用户共用 token 时不成立。
6. `tau_source` 未经阶段 B 验收，lane 不能上线；阶段 B 的 BEAM 评测预算已批准（约 1 到 2e7）。
7. **旧数据在感知授权下几乎不可检索**：v1/v2 原话迁移后 `audience={speaker}`，只有说话人本人可召回（保守、不泄漏，但召回面大幅收窄）。
8. **感知授权没有被任何基准验证**：LongMemEval/LoCoMo 都是单主体，感知授权在其上退化为全部可见。正确性只由 §9 的确定性测试保证。
7. 未实测：`[SOURCE]` 前缀与评测臂格式差异对模型的影响。

## 12. 二轮 12 条处置

> **v4 注**：#1、#2、#4、#5、#11 中关于 `SourceScope`、`project_key`、Session/Project 模式的处置，已被 v4 的感知授权**整体取代**（§3.4），保留本表作为审计记录。#1 的"交叉校验"保留，但定性改为数据完整性检查（§3.1）。

| # | 级别 | 处置 |
|---|---|---|
| 1 | P1 | 采纳：§3.1 改为"签发 + 交叉校验"双层；补 `unit.session_id == 索引 session_id` 校验；承认 auth 只有 bearer token |
| 2 | P1 | 采纳并更正：§3.3 project_key 用 remote 哈希（移动不改 key），重试冻结，bootstrap 不签发；撤回"移动必然改 key" |
| 3 | P1 | 采纳：§1 更正会话数（41-58/中位 47/14 题正好 47；LoCoMo 10 组各 19-32 会话）与"这是隔离基准库里的跨会话证据" |
| 4 | P1 | 采纳：§3.3 撤回"同轮实现 Project 分支"；只签发并存储 project_key，不实现检索分支 |
| 5 | P1 | 采纳：§3.2 明确四个消费者与"必须显式传 session_id"，并写明 Dashboard 网页端不具备该能力 |
| 6 | P1 | 采纳：§4.4 改为分数判据 `tau_source` + 预算后判定；未标定前 lane 不得开启 |
| 7 | P1 | 采纳：§5.1 更正"写入不变"；unit 级元数据、事务原子性、project_key 写入三处都要改；§5.3 表补 `observed_at` |
| 8 | P2 | 采纳：§4.1 去重改为 `(holder, session_id, turn, observed_at, text)`；§4.2 改迭代回填 + `source_truncated` |
| 9 | P1 | 采纳并更正：§4.5 撤回"按 adapter_name 判来源"；用户澄清后进一步改为**写入 API 必填 provenance 并落库**（`source_time` / `ingest_clock`），因为通用摄入 API 使 `ingest_clock` 成为真实用例；§4.2 无时间 unit 不召回 |
| 10 | P2 | 采纳：§5.6 给出 `source_partial` 的触发规则表；§5.5 模型变更同时重置 `retry_count`；更正"无退避" |
| 11 | P2 | 采纳：§9 扩为测试矩阵；§3.4 统一缺省语义（缺省 Off / 非法拒绝 / 关闭模式拒绝） |
| 12 | P2 | 采纳：§4.6 更正 `memory.py` 返回 row 对象；§4.5 引用改 `:132`/`:194`；§6.1 generation 在 `:871` 捕获、`:470` 检查；§5.5 更正无退避；§10 预算引用改 `:171` |

## 12.5 三轮 9 条处置（v4）

| # | 级别 | 处置 |
|---|---|---|
| 1 | P1 | 采纳：§10.1 改两阶段，上线门槛改为**阶段 B 走完整 planner**、测"支持答案的证据实际被渲染"的比例 |
| 2 | P1 | 采纳并更正：撤回"同题同分布"；增加人工复核的难负例，以难负例 FPR 为准，随机负例作对照 |
| 3 | P2 | 采纳：证据充分性审计；阳性须为支持答案的话轮，6 道多话轮证据题单独核对 |
| 4 | P1 | 采纳：46 题 Wilson 区间（已独立复算）不足以判定；阶段 A 降为试点，阶段 B 以置信界判定并按区间宽度反推样本量 |
| 5 | P2 | 采纳：改为"FPR 上界约束下最大化 TPR"，不用 Youden；理由是错答比拒答代价更高 |
| 6 | P1 | 采纳：时序验收改用**从未使用的 BEAM-100K**，时序类须单独达标，否则 lane 不对时序意图开启 |
| 7 | P1 | 采纳：§3.1 拆分信任边界与认知边界，信任模型取方案 A（可信后端），明确其不适用的部署形态；交叉校验改称数据完整性检查 |
| 8 | P2 | 采纳：§6.1 给出 v3 合同字段表（必填/可空、批次规则、确定性分组顺序、旧数据回填）；`ingest_clock` 由受信摄入代码写入；更正"仅 speaker/text 必填"的现状 |
| 9 | P1 | 采纳：provenance 写进**原话 payload（合同 v3）**，不再只存在派生表；重建可复现；§3.5 的可重放不变量要求 payload 自足 |

## 12.6 五轮 7 条处置（v4.3）

| # | 级别 | 处置 |
|---|---|---|
| 1 | P1 | 采纳：`perceived_by` 只在为空时填默认（`extractor.cpp:872-874`），所以只改默认值不够。v4.3 改为**对有 `source_unit_meta` 的 engram 强制取自 `audience`**，抽取给出不同集合即拒绝（`perceived_by_conflict`） |
| 2 | P1 | 采纳：写明顺序与竞态规则——**听众先写、抽取后读**，同一事务同一连接；因为在场是 `INSERT OR IGNORE`，反序会把声明听众永久并进可见集 |
| 3 | P2 | 采纳：来源 engram 必须提供非空听众，空即拒收；普通 `remember` 保持 `{holder, interlocutor}` 回退，历史行为不变；空听众**不等于**所有人可见 |
| 4 | P2 | 采纳：撤回 v4.2"两人场景不变"的宽泛说法——只有声明听众恰等于旧推断两人对时才不变；给出六项回归清单 + SocialMemBench/HiToM 回归 |
| 5 | P1 | 采纳并更正：`(cognizer, group_id)` 单行会丢掉加入/离开时间。改为**新建带历史的 `cognizer_group_membership`**（`joined_at` / `left_at` / `recorded_at`），主键含 `joined_at` 以保幂等与历史 |
| 6 | P2 | 采纳：不复用 `cognizer_frontier_facts`（`metadata_json` 只存 group_id，无法可靠做时间查询），也不放 `cognizers`；定义加入/离开语义与 as-of 查询 |
| 7 | P2 | 采纳：写入时展开的追溯语义正确且符合 C++ 边界，但**必须在同一事务、同一连接内**执行，否则有快照竞态；不扩展 `visible_engrams_at`，另加 as-of 成员查询 |

**v4.3 的结构性变化**：新增 `source_unit_meta` 作为**权威元数据表**，`source_unit_vectors` 降为可整表重建的派生索引（§5.3）。这一处同时修好了五轮 #1（抽取读权威听众）、五轮 #5/#6（成员表独立）与三轮 #9（provenance 可重建）。

## 13. 待确认（用户 2026-10-20 已裁定：按建议执行）

> **v4 注**：以下三条中的第 2、3 条已因 v4 的感知授权失去对象（不再有 Session/Project 模式）；第 1 条的标定方案已在 §10.1 改为两阶段。保留作为裁定记录。

1. **`tau_source` 标定** —— 裁定：**用单会话切片标定，且与验收题分离**；不得在同一半上既调阈值又报数字；切不出足够样本则 lane 保持关闭——**不允许用拍脑袋的阈值上线**。
   - **可行性检查已做（2026-10-20）**：原计划"从确认集切"**不可行**——确认集 171 题里证据落在单会话的只有 37 题，且都已用作开发数据。改从 **LongMemEval-S 全量 500 题中未被确认集/探索集用过的题**取样：单会话可答且未用过的共 **95 题**，去掉 3 道弃答题后 **92 题**。完整方案见 §10.1。
2. **Session 模式的消费者** —— 裁定：**不做 Claude Code hook**。用户 2026-10-20 明确 transcript 只是测试数据，不是重点。产品面是通用摄入 API（§6.3）；Dashboard transcript 摄入只作为端到端测试消费者。因此不投入集成工作，§3.2 的"网页端不具备会话关联"从风险降为**已知范围**。
3. **Project 模式** —— 裁定：**立为独立项目**，含它自己的评测（把每个基准库映射成显式 project、并测混合库隔离）与安全复核（助手转述跨会话、共享目录、时间无界三条残余风险）。本轮只签发并存储 `project_key`，不实现检索分支。

## 14. 世界/场景管理：另起任务（用户 2026-10-20 裁定）

**不在本设计范围内**，但它的需求已经确定，记在这里，避免本设计做出与之冲突的选择。

### 14.1 已确定的需求

| 需求 | 用户答复 |
|---|---|
| 一个 Dashboard 管多个世界 | 是，有一个默认世界，大多数情况下只有一个世界 |
| 删除场景 | 要能彻底回滚 |
| 并发场景 | 会有：同一时刻多个地点同时发生 |
| 回滚语义 | **两种都要**：丢掉该场景之后的所有场景；或只回滚该场景、保留后续场景 |
| 快照保留 | 只保留最近 N 份，N 可配置 |

### 14.2 已知的设计约束（供该任务参考，不在此裁定）

- **世界状态散布在 32 张表**（`memory_ops.cpp` 中 `clear_tenant` 的清单），且**没有一张带场景列**。逐表按场景删除会漏表、且 LLM 抽出的语句无法确定性重放。倾向**场景边界快照**：完整性由构造保证，并顺带支持分叉。SQLite backup API 已在评测脚本中使用（如 `run_socialmem_r58_paired_probe.py:403`），生产代码中尚无。
- **并发场景使"按场景快照"失效**：S 与 S' 并发时，恢复 S 之前的快照会连 S' 一起抹掉。因此：
  - **丢掉后续所有场景** = 恢复世界时刻快照，简单、完整、确定；
  - **只回滚 S、保留其余** = 从 S 之前的快照**分叉**，再把要保留的场景的原话**重新摄入**。它依赖本设计 §3.5 的可重放不变量，且是语义重建而非精确恢复（重新抽取会产生不同的右脑信念、消耗 token）。
- **快照只保留 N 份**意味着"保留后续"的回滚起点必须落在保留范围内；更早的场景只能走"丢掉后续"。
- **多世界 Dashboard 要求管理面与 agent 查询面分离**：管理员可选世界，agent 查询固定在自己的世界里；世界只能从服务端注册表里选，不接受客户端传文件路径。
- 两个例外需单独处理：zvec 向量后端（默认关闭）存在 SQLite 之外；摄入 spool 是文件目录（模拟器走 API，不受影响）。
- **依赖本设计先落地**：重建靠左脑存的原话，所以该任务排在左脑 lane 实现之后。

### 14.3 本设计为它做了什么

见 §3.5：感知授权、场景与世界时刻写入即固定、原话可重放不变量。这三件事本设计不做，该任务就需要重灌全部历史数据。
