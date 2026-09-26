# SocialMemBench R4.9 主题相关性、成员排序消融与真实评测

日期：2026-09-24。状态：中文设计、RED、C++ 实现、回归、A/B 离线消融和真实双臂复评均完成。**本轮未证明准确率提升，不晋升默认策略。** 检索回答 17/57（29.82%）、原生回答 16/57（28.07%），相对 R4.8 两臂各净减 1 题；来源锚点 48→51/104，覆盖增长未转化为总体 QA 收益。所有结果均为 57 题开发诊断，不是全量或保留集成绩。

## 0. 真实结果与结论

| 轮次 | 检索回答 | 原生回答 | 来源锚点 |
|---|---:|---:|---:|
| R3.5 固定父基线 | 16/57（28.07%） | 无独立原生臂 | 53/104 |
| R4.7 | 19/57（33.33%） | 17/57（29.82%） | 48/104 |
| R4.8 | 18/57（31.58%） | 17/57（29.82%） | 48/104 |
| R4.9 | **17/57（29.82%）** | **16/57（28.07%）** | **51/104** |

本轮 114/114 回答正常终结，技术失败 0，重试 0；547/600 次 HTTP 请求由 345 次 query embedding、114 次 answer、88 次 judge 构成。ledger 已结清，无预留或不确定计费，余量 53。回答与裁判合计 token：检索臂 112474、原生臂 178944，不含 embedding token。

| 配对比较 | 净增正确题 | 准确率差（百分点） | network bootstrap 95% 区间（百分点） |
|---|---:|---:|---:|
| R4.9 检索 − R4.8 检索 | −1（4 得、5 失） | −1.75 | [−8.06, 4.76] |
| R4.9 原生 − R4.8 原生 | −1（4 得、5 失） | −1.75 | [−9.52, 2.99] |
| R4.9 检索 − R3.5 父基线 | +1 | +1.75 | [−8.16, 9.23] |
| R4.9 原生 − R3.5 父基线 | 0 | 0.00 | [−9.09, 6.67] |
| R4.9 原生 − 同轮检索 | −1 | −1.75 | [−6.82, 0.00] |

按 6 个 network 聚类重采样 100000 次，seed=20260921。区间不包含生成和裁判重复运行方差，小样本及多轮开发迭代也限制泛化推断。相对 R3.5 净增至少 5 题且区间下界大于 0 的事前门槛未达到；来源库完整性限制也仍存在。不能把本轮净减 1 题断言为稳定退化，也不能把局部收益或锚点增加宣称为总体改进。

## 1. 修复与实验边界

R4.8 检索 18/57、原生回答 17/57，来源锚点 48/104。此前已证明同一 claim 的状态资格修复没有改变来源上下文，而 Q6 的 6 个关键锚点均在授权候选池中却未被选入。本轮选择两项可由独立合成反例验证的排序问题：

1. 人物匹配后按未加权的词重合数排序，使多个常见问句词压过稀有主题词。
2. 成员队列无条件优先有 claim 的来源，使有结构化元数据的异主题来源压过同一人物的直接原文证据。

按中文设计、RED、C++ 实现顺序完成。所有行为改变均限于 `evidence_profile_v6` 实验策略，Python 没有增加生产语义逻辑；默认策略未晋升。公开锚点、金标和题号只用于事后诊断，未输入排序规则。

## 2. C++ 实现与测试

完整 query 和主题 query 复用一个内部 BM25 实现，保留原公式与参数。v6 从问题中去掉关注人物姓名和事先固定的英文功能词/疑问词，用同一授权来源池计算主题 BM25；否定词和其他语言 token 保留。全局排序与会话代表选择优先使用主题分数，成员队列依次比较主题分数、完整相关性、有效 claim、稳定时间顺序。claim 只在相关性相同时决胜。

原始 `topic_overlap` 保留用于诊断，trace 新增 `topic_relevance`，profile 新增 `topic_terms`。这些分数仍是词汇相关性，不是语义正确率；没有把 claim 文本或额外推理注入原文上下文。状态/归属合同、来源授权、整行 UTF-8 预算和去重规则不变。

| 验证 | 实际结果 |
|---|---|
| A 主题排序初始 RED | 4 项中 3 项按预期失败，1 项空主题/隔离控制通过 |
| A 定向 GREEN | 65/65 |
| B 成员排序初始 RED | 4 项中 2 项按预期失败，2 项同分/预算控制通过 |
| B 最终定向 GREEN | 69/69 |
| 完整 CTest | 1291 项：1268 通过、23 沙箱跳过、0 失败 |
| localhost HTTP 补跑 | 30/30，覆盖全部跳过项 |
| 相关 Python 回归 | 65/65 |

新增测试使用陶窑、陶器等独立主题和人物，验证直接主题来源、稀有词、会话代表、每个真实 speaker、同分 claim 优先、SQL 反向读取、空主题与字节拒绝。没有使用基准题号或答案作为测试输入。

最终构建、安装、离线 B 和真实封存核心 SHA256：

`bc3d34327ef7ae2edaf298a7960ad805453f4ed857873caac852a387eb9d613f`

## 3. 固定 A/B 离线消融

A 仅改变主题排序，成员仍无条件优先 claim；B 在 A 上把 claim 改为同分决胜。最终候选事先固定为 B，没有根据锚点或真实分数在 A/B 中择优。A 没有执行真实回答，不能为它报告 QA 成绩。

三个离线目录都使用相同冻结数据库和替身 embedding，每题 10 source、0 statement。A、B 各完成 57 recalls、114 terminals、0 请求及封存核验。替身答案只用于验证流程，不作为分数。

| 比较 | 来源/block 改变题数 | 两臂 prompt 改变题数 | 锚点命中变化 |
|---|---:|---:|---:|
| R4.8 → A | 41/57 | 各 41/57 | 67→67/104 |
| R4.8 → B | 41/57 | 各 41/57 | 67→67/104 |
| A → B | 6/57 | 各 6/57 | 67→67/104 |

A/B 相对 R4.8 的锚点得失相同：`Q4_ph9s1c2`、`Q7_ph9s5c1` 各增加 1，`Q3_c0s3c2`、`Q5_ph9s2c1` 各减少 1。B 相对 A 虽改变了 6 道题的来源，但公开锚点没有增减。Q6 仍为 0/6。

成员车道逐题累计选入含 claim 的来源从 20 降至 7，普通来源成功回退从 7 增至 20；这是排序改变后的来源类型构成，不能解释为语义退化或成功。状态车道仍为 36，归属车道仍为 17，claim 加载累计 1142、拒绝 0。所有计数均按题累计，不是独立知识数量。

## 4. 真实检索对照

真实检索 57/57 成功，每题仍为 7 source、3 statement、8000 bytes 以内。相对 R4.8，41/57 题来源集合及 block 改变，statement ID 全不变，两臂各 41 个 prompt 改变。

来源锚点为 **48→51/104**，具体为：

| 题目 | R4.8 | R4.9 |
|---|---:|---:|
| `Q4_v4s1c2` | 1 | 2 |
| `Q8_v4s2c1` | 2 | 3 |
| `Q8_a3b4c607` | 1 | 2 |
| `Q8_a3b4c616` | 0 | 1 |
| `Q5_ph9s2c1` | 1 | 0 |

其余题锚点命中不变。Q8 合计 20→23/37，Q4 为 3→4/9，Q5 为 4→3/10，Q6 仍 0/6。离线与真实名额构成不同，不能用离线 67/104 与真实 51/104 直接计算退化。

## 5. 答案变化、裁判波动与事件混淆

两臂各有 41 题 prompt 改变、16 题完全不变。分层结果如下：

| 回答臂 | 分层 | R4.8 正确数 | R4.9 正确数 | 得失 |
|---|---|---:|---:|---|
| 检索 | 不变的 16 题 | 3 | 2 | 1 得、2 失，净 −1 |
| 检索 | 改变的 41 题 | 15 | 15 | 3 得、3 失，净 0 |
| 原生 | 不变的 16 题 | 2 | 2 | 1 得、1 失，净 0 |
| 原生 | 改变的 41 题 | 15 | 14 | 3 得、4 失，净 −1 |

同 prompt 的差值不能归因于本轮检索代码。原生臂在改变 prompt 的子集也净减 1，不能把全部退化归因于生成/裁判波动；该子集同时改变了上下文和一次随机生成，仍不足以建立因果量化结论。

发现一条**答案文本和 judge prompt 均完全相同**但判分翻转的记录：`Q1_c0s3c1` 原生回答在 R4.8 判 YES、R4.9 判 NO。答案均描述 Josh 用幽默、自嘲回避职业话题并转向 Priya 或聚会；judge prompt SHA256 为 `231bd2a22865da7c5f9b8b1e492afd646052a75f3e8fb9dd0b0a2daa17c23940`。这是裁判不稳定的直接证据，保留两次原始分数，不重判择优。

三个代表案例说明上下文变化的作用和边界：

1. **补齐明确因果句，双臂答对：`Q8_a3b4c616`。** R4.8 只选到 Priya 拍了不同于以往的一卷照片，缺少改变原因。R4.9 选入“figures as compositional interruptions / The work Fen showed last session changed that / structural elements”，两臂都正确回答旧观点、Fen 的触发作用和新观点。该题来源锚点 0→1、答案由错转对，支持“明确原因原文有用”的案例判断；不能外推为整类题改善。
2. **同主题跨会话替换，原生臂回退：`Q5_ph9s2c1`。** R4.8 保留 session 2 中 Luca 的即时确认“That's exactly what happens”及 Karachi 建议；R4.9 丢失该锚点，新增 session 3 关于合同的“Then let it pay for the quiet months”。新答案仍理解商业工作与个人创作的冲突，却用后一次会话解释“Luca 早已知道”。锚点 1→0、原生由对转错，暴露出主题匹配不能替代对话事件和先后关系约束；检索臂两轮都未答对。
3. **选择题变正确，关键证据仍缺：`Q6_c0s5c1`。** 两臂都从选项 2 改为金标选项 1。新上下文增加 Leon 的职业近况询问，但仍未选入明确索要投资推荐的原文。回答只有选项编号，没有推理轨迹，不能据此证明已恢复规范例外证据；公开锚点也不是完整答案要点。

| 题型 | R4.9 检索正确 | R4.9 原生正确 |
|---|---:|---:|
| Q1 | 3/11 | 3/11 |
| Q2 | 2/4 | 2/4 |
| Q3 | 0/2 | 0/2 |
| Q4 | 4/6 | 4/6 |
| Q5 | 1/7 | 0/7 |
| Q6 | 2/3 | 2/3 |
| Q7 | 1/8 | 1/8 |
| Q8 | 4/16 | 4/16 |

Q6 两臂均从 R4.8 的 1/3 增至 2/3，但公开来源锚点仍为 0/6，必须同时呈现这两个事实。按回答格式，长文本为 8/36、7/36，简答均为 1/8，选择题均为 8/13；选择题局部改善没有消除开放回答的证据缺口。

## 6. Q6 暴露出的词汇方法边界

六条公开锚点的 `topic_relevance` 全部为 0。它们仍在授权候选池中，没有字节预算拒绝，却输给同一 speaker 的其他来源。原文与问题的语义关系超出了同词匹配：

| 问题关注的行为 | 未选入的关键原文 | 被选入同人来源的信号 |
|---|---|---|
| 群聊是否有人招募或索要推荐 | Leon：“if you know anyone who'd want to invest let me know” | “what's everyone else up to professionally” 匹配 everyone 等词 |
| 所有人是否接受同一圣诞菜单 | Adaora 请求 beans、moi moi、akara，并延后解释变化 | “that's so much food…all of that” 匹配问题中的通用词 |
| 所有人是否喜欢不停下的徒步 | Bev 多次要求 cafe/tea stop | 其他话轮匹配 group/everyone 等群体表述 |

移除 metadata 的无条件优先是可验证的修复，但不能自动识别投资推荐、饮食限制或休息需求。“stopping”与“stop”等词形差异也是当前限制；本轮未按失败题追加词干规则或同义词表。

当前 source 选择仍是词汇排序，真实 embedding 主要用于 statement 检索。本轮 57 题 statement 集合全部相同，新增主题分数没有建立来源话轮的语义相似度或事件关系。因此后续优先方向是原生的语义证据连接与事件阶段约束，而不是不断扩充基准相关关键词。

## 7. 协议、身份与封存

真实实验为 `build/socialmem_20260924_r49_topic_member_real`，沿用已冻结运行器。历史 `arm=r44_claim_attribution` 和 coverage 的 `r40` 字段不改名；实际轮次由目录、核心哈希和本文确定。模型 `qwen3.8-27b`、embedding `qwen3.7-text-embedding`、answer512、judge64、k10、至少7 sources、8000 bytes、4 workers、零重试、整轮600 HTTP上限。两臂共享一次检索，原评分口径保持。

R4.8、A、B、真实候选的 7 个来源库 SHA256 均相同，仍由 R3.5 固定父库复制，没有重新抽取/写库。父库 35/36 holder 完整性限制未消除；本轮仅 57 题、7 scopes、6 networks 的开发诊断，不是全量或保留集验证。

补充诊断只写 `build/socialmem_20260924_r49_diagnostics/`。封存核验读取 SQLite 时使用 `mode=ro&immutable=1`，拒绝忽略非空 WAL。历史实验、回答及裁判分数不覆盖。

## 8. 下一轮能力改进方向

本轮停止追加词表和重跑择优。保留 R4.9 为独立实验结果，以 R4.8 和 R4.9 封存记录作为下一轮对照。下一轮应先写独立中文设计和合成反例，再实现、消融与真实复评，优先验证以下能力：

1. **来源话轮的语义证据连接。** 在 C++ 内为授权原文建立可追踪的语义相关性信号，处理无共同词的请求、偏好和行为表达；沿用真实 source 身份、租户/holder 可见性和原文引用，不把模型推断升级为事实。设计需明确 embedding 的来源、缓存身份、计算预算与失败行为，Python 仅编排和诊断。
2. **同一事件内的证据组合。** 将问题涉及的人物、同一对话事件、前态/触发/后态或回应关系联合约束；先用独立人物和领域验证“同主题但不同会话”反例。相邻话轮只是候选线索，不能自动视为同一事件；不凭时间顺序伪造因果或“早已知道”。
3. **分别验证机制与答案。** 固定语义相关性、事件约束两个消融步骤，事先确定最终候选；离线同时记录增加和丢失的原文，确认真实上下文改变且合同无回归后再调用 DashScope。真实评分继续保存首次结果、同 prompt 分层和裁判一致性诊断；待开发改进稳定后，再完成父库缺失 holder 和独立保留集验证。

这些是本轮证据支持的下一轮设计方向，尚未实现或评测，不计入当前能力和成绩。

## 9. 可复核材料

- [中文设计](../superpowers/specs/2026-09-24-socialmem-r49-topic-ranking-design.md)、[实施计划](../superpowers/plans/2026-09-24-socialmem-r49-topic-ranking.md)、[C++ 补丁](../../build/socialmem_20260924_r49_diagnostics/r48_to_r49_core.patch)。
- [A 初始 RED](../../build/socialmem_20260924_r49_diagnostics/r49_a_red.log)、[B 初始 RED](../../build/socialmem_20260924_r49_diagnostics/r49_b_red.log)、[69 项 GREEN](../../build/socialmem_20260924_r49_diagnostics/r49_b_green.log)。
- [完整 CTest](../../build/socialmem_20260924_r49_diagnostics/r49_ctest.log)、[HTTP 补跑](../../build/socialmem_20260924_r49_diagnostics/r49_http_ctest.log)、[Python 回归](../../build/socialmem_20260924_r49_diagnostics/r49_python.log)。
- [R4.8→A](../../build/socialmem_20260924_r49_diagnostics/r48_vs_a_comparison.json)、[R4.8→B](../../build/socialmem_20260924_r49_diagnostics/r48_vs_b_comparison.json)、[A→B](../../build/socialmem_20260924_r49_diagnostics/a_vs_b_comparison.json)。
- [真实上下文对照](../../build/socialmem_20260924_r49_diagnostics/real_context_comparison.json)、[Q6 原文和词汇缺口](../../build/socialmem_20260924_r49_diagnostics/q6_lexical_gap.json)、[核心/数据库身份](../../build/socialmem_20260924_r49_diagnostics/identity_comparison.json)。
- [真实分析](../../build/socialmem_20260924_r49_topic_member_real/analysis.json)、[完成封存](../../build/socialmem_20260924_r49_topic_member_real/completion-seal.json)、[配对与 prompt 分层](../../build/socialmem_20260924_r49_diagnostics/paired_comparison.json)。
- [全部正误变化及原始答案](../../build/socialmem_20260924_r49_diagnostics/changed_answers.json)、[代表题原文上下文](../../build/socialmem_20260924_r49_diagnostics/representative_cases.json)、[相同裁判输入翻转](../../build/socialmem_20260924_r49_diagnostics/identical_judge_input_flips.json)。
- [五个实验只读封存核验](../../build/socialmem_20260924_r49_diagnostics/verification.json)、[全部设计入口同步清单](../../build/socialmem_20260924_r49_diagnostics/document_sync.json)、[最终校验](../../build/socialmem_20260924_r49_diagnostics/final_validation.json)、[诊断产物哈希清单](../../build/socialmem_20260924_r49_diagnostics/artifact_manifest.json)。
