<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.0 语义证据回链与事件邻域设计

日期：2026-09-24。状态：设计完成，下一步先写 RED 测试。延续 R4.9 的失败结论：主题词排序使来源集合发生变化，但不能识别“招募/推荐”“菜单接受度”“休息需求”等跨表达关系，也会把同主题的不同会话混为一个事件。

## 1. 目标与边界

本轮只解决一个已被代码路径直接证明的断点：statement 语义检索已有 qwen embedding 分数和 `semantic_claim_json.source_span`，但 `ObserverRetriever` 在选 source 时没有使用这条回链。目标是让 `evidence_profile_v7`：

1. 从当前 holder 过滤后的 `PlannerEntryOut` 中读取可验证的 source span；
2. 将 statement 的语义分数映射到同一 `engram_ref + clause_id` 的授权 source turn；
3. 对命中的 source turn 在同一 `session_id` 内扩展有限的相邻 `turn_index`，作为事件邻域候选；
4. 用语义回链分数优先选择直接证据，再用有界事件邻域补齐回应或前后状态；
5. 在诊断中明确区分直接语义证据、事件邻域证据和词汇回退。

本轮不做 source 独立 embedding，不增加 DashScope 请求，不改变 statement 检索公式，不修改 Python binding 的语义逻辑，不把相邻话轮自动解释为因果、同一观点或“早已知道”。邻域只是原文候选；最终答案仍必须依据渲染的原文和已有 statement。

## 2. 现状证据与根因假设

R4.9 真实复评中 57 个 statement ID 全部与 R4.8 相同，而 41/57 题的 source/block 改变。Q6 六个公开 source 锚点均在授权候选池中，但 `topic_relevance=0`；这说明仅提高词汇分数不能建立语义连接。R4.9 的 Q8 摄影题在选入包含 Fen 触发句的原文后两臂答对，Q5 则因丢失同一 session 的即时回应而发生原生回退。

代码检查显示：

- `RetrievalPlanner` 已返回经可见性、claim evidence 和 embedding 排序过滤后的 `PlannerEntryOut.score`；
- `StatementRow.semantic_claim_json` 含 `source_span.engram_ref` 和 `clause_id`，可与 source 行的同一身份键严格匹配；
- `profile_sources` 当前只消费 BM25、主题分数和 claim lane，不消费上述 semantic score；
- source 的 `session_id`、`turn_index` 已在授权、时间和完整性过滤后保留，可用于有界邻域。

假设 H50：把已有 statement 语义分数回链到同一 source turn，并在同一 session 的距离 1–2 内增加候选，可以恢复跨词表达的原文，减少同主题跨 session 替换。该假设必须先由不含 SocialMemBench 题号、金标或公开锚点的 C++ 合成反例验证，再执行离线消融。

## 3. C++ 设计

### 3.0 抽取与来源登记的身份不变量

语义回链的严格键要求抽取出来的 statement 与来源登记复用同一个 engram。真实评测的来源先由 `retain_source_turns` 以 `adapter_name=source_turns`、`source_prefix=source-<holder>-` 写入；按 speaker 隔离的抽取也必须使用这组身份参数，使相同 payload 命中幂等 engram。`adapter_name=ladder` 或其他前缀会产生内容相同但身份不同的第二个 engram，导致 v7 按合同拒绝回链，不能把这种拒绝误报为“没有语义证据”。

这一条是编排身份传递约束，不在 Python 重做语义排序：Python 只把来源登记时的 adapter/prefix 传入 C++ `memory_remember_holders`，engram 幂等、source span 生成和回链仍由 C++ 完成。测试必须验证输入身份参数与来源登记一致，并保留跨身份拒绝的 C++ 覆盖。

### 3.1 语义回链身份

新增内部函数从 `PlannerEntryOut` 提取 source key：

`source_span.engram_ref + "\\x1f" + claim.clause_id`（若实现版本把 clause_id 内嵌在 source_span，则读取内嵌字段）。

只接受以下条件：

- `semantic_claim_json` 可解析且 `source_span` 两个字段均为非空字符串；
- statement 已通过 planner 的 tenant、holder、状态、时间和 claim evidence 合同；
- source key 存在于本次 ObserverQuery 已授权且已通过 hash/retention/as-of 过滤的 source pool。

同一 source key 有多个 statement 时取最大非负语义分数；不匹配、解析失败或负分不产生 semantic link，并记录拒绝原因。禁止按文本、speaker 名称或 session 单独匹配，避免重复话轮和跨 holder 串证。

### 3.2 事件邻域

对每个直接 semantic link，在相同 `session_id` 且 `turn_index` 可用时生成距离 1–2 的邻域候选。邻域候选必须满足：

- 与直接 source 使用同一 speaker/session 身份域；
- turn index 的每一步都连续存在于授权 source pool；
- 不跨 session、不跨 holder、不补造缺失 turn；
- 直接证据优先于邻域，距离越远分数越低（内部衰减仅用于排序，不写回事实）。

邻域候选保留自身完整 `[SOURCE]` 原文和身份；诊断记录 `event_anchor_key`、`event_distance`、`event_score`。不输出“因果成立”“对方已知”等结论。

### 3.3 v7 选择顺序

`evidence_profile_v7` 继承 v6 的授权、时间、预算、claim 资格、source identity 和稳定顺序。source lane 顺序为：

1. 直接 semantic link：按 semantic score 降序；
2. 同事件邻域：按 event score 降序、距离升序；
3. v6 的 state/attribution/member 合同 lane；
4. topic score、完整 BM25 和时间顺序回退。

如果没有可回链 statement，v7 必须退化到 v6 的确定性选择，并在 profile 中报告 `semantic_links=0` 和 `semantic_fallback=true`。相同分数必须使用原有 chronological 稳定顺序。`source_limit`、整行 UTF-8 字节预算和输出去重合同不变。

### 3.4 诊断字段

v7 的 `selection_trace` 增加：

- `semantic_source_score`：直接回链分数，未命中为 0；
- `semantic_linked`：是否严格命中 source key；
- `event_anchor_key`、`event_distance`、`event_score`：仅邻域候选有值；
- `selected_by` 使用 `semantic`、`event`、既有 lane 名称或 `relevance`。

`evidence_profile` 增加：`semantic_links`、`semantic_link_rejections`、`event_candidates`、`event_selected`、`semantic_fallback`。这些字段只描述选择过程，不作为答案或金标输入。

## 4. 不变量与风险控制

- statement 语义分数只能提升已授权 source，不扩大 tenant、holder、as-of 或 retention 可见集；
- source span 严格使用 `engram_ref + clause_id`，不得按相同文本或相邻时间猜测身份；
- 事件邻域缺行时停止该方向，不能跳过缺口连接两个远端话轮；
- source embedding 不在本轮增加，保持真实预算和 qwen query embedding 次数可审计；
- Python 只传入 `ObserverQuery` 并读取 JSON 诊断，核心回链、衰减、排序全部在 C++；
- v2–v6、默认 `bm25` 和已封存实验源码行为不变；v7 不进入默认策略；
- 语义信号缺失、JSON 损坏或分数异常时 fail closed，保留 v6 回退并记录诊断，不抛出不可恢复的评测错误。

## 5. 测试与评测顺序

先在 `tests/cpp/test_source_retriever.cpp` 增加与基准无关的 RED：

1. 语义 source span 能压过词汇更相似但语义无回链的来源；
2. 同一 source key 的多条 statement 取最高分，错误 tenant、holder、clause 不得回链；
3. 直接证据之后选择同一 session 的连续邻域，跨 session 或缺 turn 不得进入 event lane；
4. 无 semantic link、负分、损坏 span、空 source pool 时稳定回退 v6，预算/去重/隔离不变。

RED 通过后只在 C++ 实现 v7，运行定向 GREEN、完整 CTest、HTTP 补跑和 Python 回归。然后用相同冻结库、相同 57 题和相同真实配置做 v7 对 v6 的零网络消融；只有 source/block 确实改变且合同不回归，才执行一次 DashScope 真实双臂复评。若为验证抽取与来源身份一致性而重新生成来源库，抽取请求必须单独计入总账本；本轮预注册总上界为 1000 次，覆盖新鲜抽取、来源嵌入、57 次共享检索、legacy 回答及 native 回答/裁判。最终候选在真实调用前预注册，不按离线锚点或 QA 分数择优。

真实复评继续报告 57 题检索/原生两臂、prompt 变更分层、network bootstrap、请求 ledger、锚点仅作事后诊断。若语义回链改变上下文但未提升 QA，封存并分析具体事件链，不扩充题目相关词表追分。

## 6. 晋升条件

R5.0 只有在以下条件同时满足时才可考虑晋升实验候选：完整测试和封存核验通过；v7 相对 v6 改变上下文且无权限、预算、身份或隔离回归；真实检索和原生结果均不低于 v6，且至少一臂净增不低于事前门槛；bootstrap 区间、裁判翻转和父库完整性限制均如实报告。任何一项不满足都保留 v7 为诊断实验，不修改默认策略。
