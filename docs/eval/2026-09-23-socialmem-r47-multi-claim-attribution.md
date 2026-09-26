# SocialMemBench R4.7 多声明保留、第一人称归属与真实复评诊断

日期：2026-09-23。状态：C++ 修复、回归、离线闭环、真实双臂评测、归因分析及封存核验完成。**本轮补齐了两项可复现的核心能力，但没有证明稳定的准确率提升，不晋升生产。**

## 1. 结论与适用范围

R4.7 检索臂为 **19/57（33.33%）**，原生回答臂为 **17/57（29.82%）**，分别比 R4.6 多答对 4 题和 2 题。114 个回答任务全部正常，实际使用 547/600 次 HTTP 请求。来源锚点仍为 48/104。

涨分需要谨慎归因：检索臂净增的 4 题全部来自回答 prompt 未变化的子集；prompt 改变的 7 题合计没有净增。另发现 3 个跨轮完全相同的答案，在完全相同的裁判 prompt 下发生判分翻转。单次跨轮差值混合了回答生成、裁判和运行时间变化，不能全部算作代码修复的收益。

工程结论更明确：一个 source 现在保留全部有效 claim；无效 sibling 不能遮蔽有效 claim；第一人称知识/信念在满足人物边界时可以进入归属车道。新规则只作用于 `evidence_profile_v6` 实验策略，核心实现位于 C++，Python 只承担绑定、评测编排和只读诊断。

本报告对应固定的 57 题开发诊断队列、7 个 scope、6 个 network。它不是 SocialMemBench 全量或保留集成绩，也不能与历史 733/1031 题分数直接相减。父库仍只有 35/36 个完整 holder。

## 2. 基线、协议与身份

| 同一 57 题开发队列 | 检索臂 | 原生回答臂 | 来源锚点命中 | 技术失败 |
|---|---:|---:|---:|---:|
| R3.5 冻结父基线 | 16/57，28.07% | 无独立臂 | 53/104 | 0 |
| R4.5 | 14/57，24.56% | 18/57，31.58% | 48/104 | 0 |
| R4.6 | 15/57，26.32% | 15/57，26.32% | 48/104 | 检索臂 1、原生臂 0 |
| **R4.7** | **19/57，33.33%** | **17/57，29.82%** | **48/104** | **0** |

真实目录为 `build/socialmem_20260923_r47_multi_claim_real`。沿用冻结的 `run_socialmem_r44.py`，其 `arm=r44_claim_attribution` 和 coverage 的 `r40` 是历史字段名，实际轮次由目录、核心哈希及本报告确定。来源库由运行器固定的 R3.5 父实验复制；已逐库核实，R4.6、R4.7 真实与 R4.7 离线的 7 个数据库 SHA256 完全相同。没有重新抽取或写入语料。

模型为 `qwen3.8-27b`，embedding 为 `qwen3.7-text-embedding`；两臂共享每题同一次检索结果，按冻结任务顺序交替提交。配置为 k=10、至少 7 条 source、8000 UTF-8 字节、answer 512 token、judge 64 token、4 workers、零重试、600 HTTP 上限。真实检索最终每题均渲染 7 条 source 和 3 条 statement。

R4.7 构建、安装及真实封存 `_core` 的 SHA256 一致：

`bc0831fc9263aa7f6fa2c709f7fcf8bbcaffe77b853057f0d2ce7239a17594fb`

当前 `source_retriever.cpp`、R4.7 封存源码与补充 RED 前备份字节相同。补充顺序测试后恢复构建没有改变实际受评核心。旧 R4.6 核心为 `b86cbac787d697e2847e6bb64074292b4d4e1269f4583e6a527006b7ecaf0261`。

## 3. 修复内容及证据强度

### 3.1 保留同源多条声明

R4.6 的来源索引每个键只存一个 claim，SQLite 后读行会覆盖先读行。同一话轮同时表达知识、偏好或决策时，所需语义可能丢失。

R4.7 将 `Source.claim` 改为 `claims` 集合，`ClaimView` 分别收集有效 evidence 与拒绝原因。每条声明独立通过原生证据合同与来源回连；一个无效 sibling 只贡献拒绝诊断，不能删除同源有效声明。车道以集合资格判断选择来源，来源仍只占一个上下文名额。

两种写入顺序和 `PRAGMA reverse_unordered_selects=ON` 的测试均核对最终上下文与诊断一致。补充无效 sibling 用例保留正确 source 索引，仅把 `prefers` 的 `relation_modality` 破坏为 `INTENDS`，从而确实覆盖“已回连但合同拒绝的 sibling 遮蔽有效 claim”路径；不能只靠空 JSON 的早期拒绝用例证明这一点。

### 3.2 有人物边界的第一人称归属

对 belief、knowledge、uncertainty 等合格 claim，第三方转述沿用 `attributed_to == speaker` 的路径；无归属字段的自述要求 `actor == speaker`、perspective 为 `FIRST_PERSON`，且问题只关注该 speaker，或 claim 的 topic/object 明确提及另一位关注人物。可空 topic 安全读取，人物提及沿用现有姓名边界匹配。

这恢复了合法自述的资格，但不代表自动恢复二阶心智、代词指代或完整人物关系推理。原始 source 行仍是回答证据，claim 元数据不替换或扩写原文。

### 3.3 回归与流程记录

| 验证 | 结果 | 含义 |
|---|---|---|
| 初始 RED | 4 项中 3 项预期失败、1 项边界负例通过 | 先写设计与测试，再实现主要修复 |
| 补充顺序及单人物测试 | 旧 R4.6 核心 5/5 失败，恢复 R4.7 后 5/5 通过 | 实评后补验，未再改生产代码 |
| 最终定向 C++ | 54/54 通过 | 来源检索、覆盖、回连、多 claim 与顺序边界 |
| 最终完整 CTest | 1276 项：1253 通过、23 环境跳过、0 失败 | 不能写成 1276 项全部实际执行 |
| 本机 HTTP 补跑 | 30/30 通过 | 覆盖上述 23 个沙箱跳过项 |
| 新核心 Python 回归 | 71/71 通过 | 绑定及评测协议边界 |
| 离线闭环 | 57 recalls、114 terminals、0 请求，封存通过 | 仅证明流程与合同，无 QA 质量含义 |

完整顺序测试属于真实评测后的补充验证，应如实记录，不能改写成所有用例都在第一次实现前写完。早期 1271 项 CTest 的准确口径为 1248 通过、23 跳过；最终新增 5 项后如上表。

## 4. 分数差值与归因

### 4.1 配对统计

| 对照 | 候选臂 | 净增正确题 | 差值（百分点） | 95% network bootstrap 区间（百分点） |
|---|---|---:|---:|---:|
| R4.6 同臂 | retrieval | +4（6 得、2 失） | +7.02 | [2.00, 10.53] |
| R4.6 同臂 | native_answer | +2（2 得、0 失） | +3.51 | [0.00, 9.52] |
| R3.5 父基线 | retrieval | +3 | +5.26 | [-5.88, 15.79] |
| R3.5 父基线 | native_answer | +1 | +1.75 | [-4.26, 6.67] |
| R4.7 retrieval | R4.7 native_answer | -2（3 得、5 失） | -3.51 | [-12.73, 4.55] |

沿用冻结统计：以 6 个 network 为重采样单位，100000 次 bootstrap，seed=20260921。这些区间只描述已观测结果的网络抽样差异，不包含重复生成与重复裁判的方差。检索臂相对 R4.6 区间虽为正，仍不能作代码因果收益的证明。

相对 R3.5 的两个臂均未达到事前“净增至少 5 题且区间下界大于 0”的扩大验证门槛；父库完整性限制也仍存在。`promoted=false`。

### 4.2 按实际回答 prompt 是否改变分层

| 臂 | 分层 | 题数 | R4.6 正确 | R4.7 正确 | 净变化 |
|---|---|---:|---:|---:|---:|
| retrieval | prompt 完全相同 | 50 | 13 | 17 | +4 |
| retrieval | prompt 改变 | 7 | 2 | 2 | 0（1 得、1 失） |
| native_answer | prompt 完全相同 | 42 | 12 | 13 | +1 |
| native_answer | prompt 改变 | 15 | 3 | 4 | +1 |

相对 R4.6，只有 7/57 题的 source 集合和渲染 block 改变，57 题 statement ID 集合全部相同。原生臂有 15 个 prompt 改变，是因为其 prompt 还包含 coverage 诊断；prompt 变动不一定意味着新增证据。相对 R4.5，source/block 改变 13 题，retrieval/native prompt 分别改变 13/22 题，锚点总数仍为 48/104。

### 4.3 已直接确认的裁判不稳定

下列三题在 R4.6/R4.7 的答案文本和裁判 prompt 均完全相同，却得到相反判分。原始答案、prompt 哈希与裁判结果已保存至独立诊断文件。

| 题目 | 臂 | R4.6 → R4.7 | 答案讨论的内容 |
|---|---|---|---|
| `Q7_a3b4c601` | retrieval | NO → YES | Bex 通过 Nora 在艺术中心主持的公开工作坊加入集体 |
| `Q8_a3b4c612` | retrieval | NO → YES | Nora 看到 Sol 作品的创作意图后改变对 lo-fi 摄影的看法 |
| `Q7_r3a7b8c9` | retrieval | YES → NO | Bev 留意 Marcus 的膝伤，并在路线选择中照顾他的偏好 |

这三次翻转对观测净变化的代数贡献为 +1，但不应把剩余 +3 直接算作代码效果；其余题仍可能有生成和裁判波动。本次审计不修改原裁判、原分数或历史基线，也没有追加裁判请求。

### 4.4 原生臂新增正确题的边界

`Q1_r3a1b2c3` 从错误变为正确，但 source、statement 与 block 完全相同；唯一的 coverage 差异是 `belief_attribution_missing` 从 `["speaker_or_belief_holder"]` 变为空。新回答补出了 deer rutting ground 与 lapwing breeding windows 的生态细节，因此不能称为“新增检索证据带来的收益”。

该题 `belief_attribution_selected` 仍为 0：此字段计数归属车道实际新选入的来源，不包含已被状态等前序车道选择的合格来源。空 missing 与 selected=0 可以同时出现，不应据此虚增归属选中数。

## 5. 仍然缺失的能力

### 5.1 元数据覆盖与谓词使用面仍窄

7 个 scope 合计 102 条 claim，覆盖 90 个来源话轮，其中 11 个话轮有多条 claim，单源最大 3 条。当前库实际只使用 7 种谓词：`believes` 56、`prefers` 20、`decided_on` 12、`feels` 6、`uncertain_about` 4、`knows` 3、`owns` 1；102 条均为第一人称，`attributed_to` 为空。

这是冻结语料中实际存储的谓词分布，不能解释为 Starling 仅支持 7 种谓词，也不能仅凭分布区分“抽取没抽到、合同拒绝、库不完整、原文没有该语义”。本轮复用数据库，因此没有扩充结构化抽取覆盖；新增谓词、事件角色或第三方归属抽取应作为独立写入实验验证。

真实检索逐题累计加载、尝试回连、成功回连均为 1142，拒绝为 0；1142 不是独立知识条数。47/57 题候选中存在多 claim 来源，多来源计数逐题累计 115，底层独立来源仍是 11 个。`claims_per_source_max` 应取最大值 3，不能把逐题数值相加解释成最大值。

状态链实际新选入含状态 claim 的来源累计 38，归属车道 16（涉及 13 道题），成员车道 20，成员普通来源成功回退 7 次。26 道题触发归属需求。57 题均满足车道选中数等于最终渲染数、上下文字节数等于实际 UTF-8 长度。

### 5.2 人物、话题与事件阶段尚未联合约束

| 题型 | 题数 | retrieval 正确 | native_answer 正确 | R4.7 锚点命中 |
|---|---:|---:|---:|---:|
| Q1 | 11 | 2 | 2 | 13/17 |
| Q2 | 4 | 2 | 2 | 1/5 |
| Q3 | 2 | 0 | 0 | 1/7 |
| Q4 | 6 | 5 | 5 | 3/9 |
| Q5 | 7 | 2 | 3 | 4/10 |
| Q6 | 3 | 1 | 1 | 0/6 |
| Q7 | 8 | 1 | 1 | 6/13 |
| Q8 | 16 | 6 | 3 | 20/37 |

Q3 多人物回答仍全部计错，Q6 来源锚点仍全部缺失，Q8 初态—触发—变化信号—后态仍不完整。姓名出现、会话首尾覆盖和更多 claim 不保证取到“这个人物在这个事件阶段”的有效证据。公开锚点也不是完整答案要点，更不是独立的语义判分器。

静态复核还发现一项待 RED 验证的风险：状态链的 family 判断与 actor 判断分别对 claim 集合做 `any_of`，可能由两个 sibling 分别满足条件，造成跨声明拼接资格。当前测试尚未证明这一候选问题的影响；本轮不能宣称所有角色和时序组合均已正确处理。下一轮应先构造隔离反例，再决定是否将条件绑定到同一条 claim。

### 5.3 回答仍可能丢失否定和关键细节

`Q1_a3b4c609` 两轮检索臂都引用了 “themed shoots are really my thing”，同时在括注中解释为实际不喜欢。截取引语缺少否定语境，即使整体结论接近，也不是可靠的原文引用。旧答案被判正确、新答案被判错误，进一步说明原裁判结果与人工阅读诊断应分别呈现。

按回答格式，选择题两臂均 8/13，短回答均 1/8，长回答为 10/36 和 8/36。扩大回答容量不是本轮首选：当前零截断，但长回答仍缺少必要证据和细节。原生臂 answer+judge token 比检索臂高约 67.8%，本轮反而少答对 2 题，没有显示成本收益优势。

## 6. 下一轮优化顺序与验收条件

| 优先级 | 具体工作 | 测试先行与评估条件 |
|---|---|---|
| P0 | 建立固定答案的裁判一致性诊断 | 先冻结问题、金标、答案和 judge prompt，以哈希关联同一裁判输入；如增加重复裁判，独立预注册协议与预算，报告原分和一致性，不覆盖基线 |
| P0 | 检验同一 claim 内的资格约束 | 先写“另一人物的状态 claim + speaker 的非状态 claim”负例及反向写入顺序测试；若复现，再在 C++ 联合检查 family、actor、source_turn 与来源边界 |
| P1 | 人物—话题—事件阶段联合检索 | 按初态、触发、明确变化信号、后态建立有来源的候选链；先覆盖同名异话题、同人异事件、事件前后阶段冲突、缺失证据及预算挤占反例，禁止使用答案/公开锚点选择来源 |
| P1 | 保留完整否定与关系证据 | 为否定、转折、第三方转述与缺失成员写原生测试；引用保留原句语境，诊断明确“未检索到”，不由 binding 补写推论 |
| P2 | 扩充实际写入的结构化能力 | 独立评估事件角色、承诺/拒绝、信念承载者等语义的抽取—合同—存储—检索链；把抽取缺失和合同拒绝分开，先补 holder 完整性，再做新写入库比较 |

执行仍按中文设计 → RED → C++ 实现 → 回归 → 固定库离线验证 → 独立真实配对评测。一次改变一个可检验的机制，保留相同题目、模型和评分口径；先检查实际上下文变化，再解释 QA 差值。若修改裁判或统计协议，建立新实验身份；在未参与优化的数据上验证后才能讨论更广泛收益。当前 R4.7 的结论是关闭本轮实验，不是高分目标已经完成。

## 7. 请求、封存与复核

- 57/57 recalls 正常，114/114 回答终态正常；实际 HTTP 为 345 query embedding + 114 answer + 88 judge = 547，reserved=0、charged_upper=0，剩余 53 次未使用。
- answer+judge 观测 token：retrieval 112118，native_answer 188150。embedding token 不包含在这两项中。
- 离线使用替身 embedding，每题为 10 source、0 statement；真实每题为 7 source、3 statement。因此离线与真实车道计数一致不等于完整上下文相同，离线替身答案无质量含义。
- R4.6 真实、R4.7 真实和 R4.7 离线均重新调用冻结运行器核验，通过后再次核对完成封存与请求账本 SHA256。SQLite 连接限制为 `mode=ro&immutable=1`，拒绝忽略非空 WAL。
- 封存后的补充诊断统一保存在独立目录 `build/socialmem_20260923_r47_diagnostics/`，附文件哈希清单；不写入已封存实验目录，不重新运行 `analyze`。
- 当前系统/子系统、历史设计入口、技术报告及设计规格/实施计划统一同步 R4.7 中文入口；历史正文和原始评测分数保留当时口径。

可复核材料：

1. [中文设计](../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)、[实施计划与完成记录](../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。
2. [真实评测汇总](../../build/socialmem_20260923_r47_multi_claim_real/analysis.json)、[完成封存](../../build/socialmem_20260923_r47_multi_claim_real/completion-seal.json)。
3. [跨轮配对与 prompt 分层](../../build/socialmem_20260923_r47_diagnostics/paired_comparison.json)、[来源集合比较](../../build/socialmem_20260923_r47_diagnostics/source_comparison.json)、[相同裁判输入的判分翻转](../../build/socialmem_20260923_r47_diagnostics/judge_instability.json)。
4. [真实车道诊断](../../build/socialmem_20260923_r47_diagnostics/real_lane_diagnostics.json)、[存储 claim 基数](../../build/socialmem_20260923_r47_diagnostics/stored_claim_diagnostics.json)、[数据库一致性](../../build/socialmem_20260923_r47_diagnostics/database_identity.json)。
5. [初始 RED](../../build/socialmem_20260923_r47_diagnostics/initial_red.log)、[顺序补验 RED](../../build/socialmem_20260923_r47_diagnostics/order_red.log)、[顺序补验 GREEN](../../build/socialmem_20260923_r47_diagnostics/order_green.log)、[最终 54 项定向回归](../../build/socialmem_20260923_r47_diagnostics/focused_tests.log)。
6. [完整 CTest](../../build/socialmem_20260923_r47_diagnostics/ctest.log)、[HTTP 补跑](../../build/socialmem_20260923_r47_diagnostics/http_ctest.log)、[Python 回归](../../build/socialmem_20260923_r47_diagnostics/python_tests.log)。
7. [最终封存核验](../../build/socialmem_20260923_r47_diagnostics/frozen_verification.json)、[核心身份](../../build/socialmem_20260923_r47_diagnostics/core_identity.json)、[外置诊断哈希清单](../../build/socialmem_20260923_r47_diagnostics/artifact_manifest.json)。
