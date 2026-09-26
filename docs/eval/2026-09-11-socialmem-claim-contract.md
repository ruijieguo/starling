> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：开发332/733=45.29%，对上一轮37.24%提升8.05百分点；60回答截断等74技术失败计零。本文历史结果保留原冻结身份；最新开发结论及限制见[当前报告](2026-09-17-socialmem-grounded-answer.md)，无本轮保留或全量成绩。

# SocialMemBench 来源语义证据契约诊断

状态（2026-09-12，Asia/Shanghai）：**实现、完整工程验证、独立审查、真实诊断和归档核验完成；真实运行 `complete_with_errors`，质量门槛未通过，默认关闭。**

核心结论：来源契约让错误可以沿 C++ 抽取、持久化、检索和回答链路追溯；目前不能证明整体准确率提升。对照 59/64，synthetic 严格计分 13/16 → 9/16；Q1 的链接原文组通过，但 Q9 的 linked/full 因传输失败未得到有效回答。

## 本次实现及边界

用户确认的[设计](../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md)按“先文档、再失败用例、最后实现”执行。生产逻辑统一在 C++：来源整行/整轮证据单元、UTF-8 字节区间与完整 payload 哈希、v2 JSON/单围栏信封、关系与范围校验、只允许保留/拒绝的模型准入、原生持久化和检索。Python binding 只映射类型/配置并转发；Python 评测脚本负责实验调度、归档核验和统计。

五个实验谓词为 `feels`、`uncertain_about`、`decided_on`、`indifferent_to`、`trusts`。新增 `semantic_claim_contract` 和 `claim_allow_code_fence` 均默认关闭；旧基线响应保持冻结。SQL migration 0034 新增 nullable `semantic_claim_json`，不重写旧行或哈希。

来源观察时间不等于事件发生时间；原文未提供可解析的绝对时间时保留 `time_text`，event_time 为 UNKNOWN，并记录 source-time fallback。所选原文摘录只能来自 C++ 已验证且在 tenant/holder 范围内的证据链接。图补全在激活/传播前拒绝失效证据；派生陈述保留父链，不继承直接来源证书。

## 审查与验证

独立审查指出三个 Important 问题，均补文档和失败用例后修复：直接 Bus 写入可能接受相互一致却非法的关系组合；查询 embedding 失败降级未记为技术失败；问答归档未从原生数据库行重建上下文。补充检查要求所选契约行有且只有一个证据链接。

- 原生修复复用 C++ parser，不在各调用端重复实现关系规则，也不增加模型调用。
- 查询降级保留 native fallback/receipt 供分析，但标记 context_error，对应回答不能作为有效成功。
- 离线验证通过 tenant-scoped native MetaStore getter 与原生 renderer 重建每个 scope 和 total-k 上下文；核对行字段、标签、评分、链接和实际回答输入。
- 完整构建及原生安装通过；Python **1,273 passed / 15 skipped**；C++ 全量 **1,024 passed / 1 skipped**，沙箱外补跑该本地 HTTP 测试 **1 passed**，合计 **1,025 项通过**。
- 完整 Fake 诊断与验证器通过：**140 次原生重放、144 个数据库、76 个抽取记录、64 个固定候选、8 个回答、120 次裁判记录**，所有技术错误计数为零。

日志：`build/claim_contract_final_pytest.log`、`build/claim_contract_review_ctest.log`、`build/claim_contract_review_http.log`、`build/claim_contract_final_smoke_verify.log`。

## 冻结协议与来源

HEAD：`8b6cc91b309aff4b6bcf02bb62393871dafa435f`，工作区包含前期未提交变更；评测源码清单与原生二进制哈希标识实际运行版本。构建前归档：`build/socialmem_claim_contract_before/`。当前原生 SHA256：`0617201108b6e79e5c9640f8432ca1f04ef6bfff0251ed53cc9c27a1e34d0ace`。

冻结父实验：`build/socialmem_20260910_supplement_run/`；64 个候选在首次真实调用前冻结，32 个沿用旧候选与标签，32 个新增候选在中英、正负之间平衡。固定候选注入不算新抽取调用。原生准入最多一次，不作内容质量重试；有界传输重试沿用适配器配置。

| 通道 | 固定数量 |
|---|---:|
| 新抽取：P1 / synthetic / speaker groups | 50 / 16 / 10，共 76 |
| 注入固定候选 | 64 |
| 准入 | 最多 140，按有效非空候选实际计数 |
| synthetic 裁判 | 2 组 × 16 题 × 3 票 = 96 |
| Q1/Q9 回答 | baseline / structured / linked / full，共 8 |
| QA 裁判 | 8 × 3 票 = 24 |

准入、抽取和作答只使用其授权来源字段；问题/金标不进入抽取与准入。裁判看到问题、参考答案和待判内容。三个投票来自同一模型的重复调用，不是独立裁判。Q9 只用 Sessions 1–5；两道已复核 QA 和开发对照不能代表全部 1,031 题。

真实运行目录：`build/socialmem_20260911_claim_contract_retry_run/`。首次启动在归档模型元数据时暴露缺少 `EmbeddingAdapter.model()` binding，尚未发出模型调用；该零调用失败记录保留在 `build/socialmem_20260911_claim_contract_run/startup_failure.json`。已先补失败用例，再把共同 C++ 虚接口直接暴露给 binding，完整测试与最终 smoke 均重跑通过。

## 真实结果与逐阶段分析

历史 strict admission 的 72/76 格式失败、13/16 → 3/16 synthetic 与离线围栏敏感性 25/32 为不同协议的历史诊断，不合并为本轮增益。本轮严格结果与失败归因如下，所有分母和协议保持冻结。

### 固定候选对照

64 个候选 **59/64 正确（92.19%）**。32 个正例：保留 31，误拒 1；32 个负例：拒绝 28，误收 1，技术失败 3。技术失败没有计作正确负例。旧 32 个候选本轮 31/32；新增 32 个 28/32；英文 29/32，中文 30/32。

| 类型 | 正确/总数 | 未通过原因 |
|---|---:|---|
| 条件 | 8/8 | — |
| 决定 | 8/8 | — |
| 未决 | 8/8 | — |
| 情绪 | 7/8 | 将 `I feel that the missing keys are in the kitchen` 错当情绪 `feels` 保留 |
| 归属 | 7/8 | 合法 reported + conditional + negative 候选被模型以 wrong_attribution 拒绝 |
| 信任 | 7/8 | 合法拒绝 JSON 后追加解释，信封技术失败 |
| 否定 | 7/8 | 合法拒绝 JSON 后追加解释，信封技术失败 |
| 时间 | 7/8 | 合法拒绝 JSON 后追加解释，信封技术失败 |

具体未通过 ID：`en_trust_no`、`new_en_emotion_no`、`new_en_attribution_yes`、`new_zh_negation_no`、`new_zh_time_no`。三个技术失败即使 raw JSON 内给出了拒绝，也不能替代完整协议成功。100% / 零技术失败门槛未通过。

### P1 兼容性与额外关系

50 个原标签和冻结基线保持不变，原 89 条基线语义全部保留；新增 21 条补充陈述。

| F1 | 冻结 base | 本轮 combined |
|---|---:|---:|
| holder | .7500 | .6630 |
| holder perspective | .7000 | .6188 |
| predicate / object | .7875 | .6961 |
| depth-1 | .5455 | .5455 |

旧标签没有覆盖五个新关系，因此不能把 21 个 unmatched rows 全部解释为语义错误；但逐条查原文确认仍存在实际误收。例如 `eval-015` 将 Bob 声明负责 auth 抽成 Bob `trusts auth`；`eval-020` 将职责交接笔记抽成 Alice `trusts Bob for auth`。`eval-024` 的“我确信这是正确归属”被当作 `feels`，仍混淆认知判断与情绪。`eval-002/008/017/032/034` 的决策对象还保留 him/他，依赖链接原文才能解析对象。保持旧行不变未能满足 combined 不下降门槛；也未证明额外关系具备足够精度。

### 真实调用、失败与复现

运行时间：2026-09-11 23:55:27 至 2026-09-12 00:21:48（Asia/Shanghai）；00:24:19 完成离线核验。

实际完成 **140 条记录**：76 次新抽取、64 个固定候选注入、**92 次准入**、8 次回答尝试和120 次裁判尝试。回答6/8获得有效响应；裁判119/120票有效。原生 embedding 统计为 **20 次实际 HTTP 尝试、16 次 embed 调用、2 次 batch 调用**；35 条新 QA 陈述完成 embedding，冻结基线向量复用。逻辑调用数与传输尝试数分开记录。

| 轨道 | 记录 | 新入库陈述 | 技术失败 | 确定性语义行拒绝 | 模型语义行拒绝 |
|---|---:|---:|---:|---:|---:|
| P1 | 50 | 21 | 3 | 49 | 7 |
| synthetic | 16 | 11 | 1 | 7 | 0 |
| scoped 对话 | 10 | 35 | 0 | 21 | 2 |
| 固定候选 | 64 | 32 | 3 | 15 | 14 |

记录数和陈述数不是同一分母。7 个原生管线技术失败均发生在准入：模型追加解释文字，违反一个完整 JSON 值或单一完整围栏的协议（7/92）；没有因此重试内容或事后修改评分。Q9 linked/full 的回答分别在共4次传输尝试失败后因 `SSL: UNEXPECTED_EOF_WHILE_READING` 失败，full 的第3张裁判票也因同类错误失败。其余来源/持久化证据错误、旧语义改写、检索/embedding失败均为0。

验证器核验 **140 次原生 ingestion 重放、144 个数据库、全部模型通道记录、来源/源码/二进制哈希、原生候选语义及问答上下文**。QA 验证不重新请求 embedding；通过归档原生 receipt、native MetaStore getter 和 C++ renderer 核验候选/标签/分数/选择/证据链接。证据验证通过不意味着模型语义正确。

```sh
.venv/bin/python scripts/eval_socialmem_claim_contract.py verify build/socialmem_20260911_claim_contract_retry_run
```

机器记录：[manifest](../../build/socialmem_20260911_claim_contract_retry_run/manifest.json)、[results](../../build/socialmem_20260911_claim_contract_retry_run/results.json)、[verification](../../build/socialmem_20260911_claim_contract_retry_run/verification.json)、[逐项分析](2026-09-12-socialmem-claim-contract-analysis.json)。

### Synthetic 配对退步与裁判稳定性

本轮用新裁判调用重新判定冻结旧候选：13/16；新契约严格合格9/16，没有配对收益，4项统计退步。

| 样本 | 冻结 / 契约赞成票 | 归因 |
|---|---:|---|
| emotion_positive | 2/3 → 0/3 | **候选和裁判 prompt 完全相同**；裁判不稳定，不是陈述丢失 |
| emotion_negative | 3/3 → 0/3 | 模型给出 NEG 但遗漏 NEGATED marker；整条否定情绪被确定性校验拒绝 |
| decision_change | 3/3 → 0/3 | 模型把 subject/actor 写成 I 而非 Elias，且对象未保留 Last week / Today；新通道未落库前后状态 |
| preference_qualifiers | 3/3 → 3/3 | 内容足以回答，但准入信封失败；原生失败使本轮不能计为合格成功 |

16个配对中有12个候选/prompt完全相同，其中 emotion_positive 的多数结论改变。三个投票均来自同一模型，无法作为独立裁判；不追加挑选有利投票，也不回写原结果。9/16必须连同“2处内容损失、1处技术失败、1处相同提示裁判不一致”解释。旧冻结候选也有错误关系（例如 preference_qualifiers 中把偏好写成 feels），旧组被裁判接受并不证明每个关系正确。

### Q1/Q9 回答与证据阶段

| 回答组 | Q1 | Q9 |
|---|---|---|
| 冻结基线 | 0/3 | 0/3 |
| 新契约 structured | 0/3 | 0/3 |
| 同一 structured + 所选原文链接 | 2/3 | **传输失败，无有效回答** |
| 完整来源对话 | 3/3 | **传输失败，无有效回答；另1张裁判票失败** |

每组仍以2次计划回答为分母。Q9两组失败不得解释为“全文也答错”，本轮不能得出Q9完整四组的语义比较。历史全文成功不填补本轮缺失结果。

| 来源 / 记忆组 | 存储行数 | sleep后 consolidated | 各holder原生返回条数之和 | 全局所选 / 契约链接 |
|---|---:|---:|---:|---:|
| Q1 baseline | 32 | 32 | 30 | 10 / 0 |
| Q1 structured | 48（新增16） | 48 | 38 | 10 / 6 |
| Q9 baseline | 80 | 80 | 30 | 10 / 0 |
| Q9 structured | 99（新增19） | 99 | 38 | 10 / 4 |

“各holder原生返回条数”是每个scope完成本地k选择后的候选之和，**不是完整可用记忆总数**。本次另在数据库副本上用 C++ BasicRetriever 核验两位关键主体的10条新陈述，10/10具备 basic 检索资格；其中Marcus的 c12 没进入 planner 的本次scope返回结果。该检查无模型调用，不替代实际向量排序。

| 问题所需线索 | 原始来源 | 存储 / 资格 / 本轮召回 | 回答影响与缺口归因 |
|---|---|---|---|
| Q1：反对增加建筑体量 | Claudette c0 | decided_on正确保存，原生可用且排首位 | 主体/主题覆盖改善；结构化组仍未整体通过 |
| Q1：development导致traffic的因果框架 | Claudette c4 | 简化成“害怕交通危险”，原文链接随所选行返回 | 因果关系在结构化对象中丢失；linked补回原句，有局部收益 |
| Q1：30年居民历史和联合规划信件 | Claudette c1 | 旧base有joint letter碎片，新契约无该完整论据，未选择对应来源 | 历史/主题背景覆盖不足；并非单纯排序遗漏 |
| Q1：停车方案试行/永久化 | Claudette c2/c3 | 情绪保存且被选中，c3对象没有停车主题 | 回答把停车政策永久化泛化到建筑开发；原文单行仍依赖相邻话题上下文 |
| Q9：早期考虑Swindon机会、尚未决定 | Marcus c12/c13 | c12可用但未进入scope结果；c13被选中但对象只剩“decided yet” | 同时存在局部检索遗漏与主题丢失 |
| Q9：接受工作、月底搬走 | Marcus c18 | 新候选因“said”触发REPORTED要求而被拒；旧base的promises原句仍被选中 | 新准入规则误拒言语行为；旧base提供部分信息但关系类型仍有噪声 |
| Q9：为改变现状而搬家、非主要为薪酬 | Marcus c20，前接Dev问better pay | 关键Marcus新陈述未覆盖，所选上下文缺该问答联系 | 跨说话者上下文丢失；按speaker分组无法单独确定指代/比较对象 |
| Q9：晚期紧张、停滞感 | Marcus c25 | 两条feels保存且被选中，资格正常 | 情绪已召回；缺少session/turn原始时间锚，source_time仅为诊断观察时间 |
| Q9：此前寡言与后来坦诚的变化 | Sessions1–3对比4–5 | 零散句子入库，互动模式及前后会话关系未表示 | 正确情绪陈述不等于完整社会记忆推理 |
| Q9：“either way / not my fight” | Marcus c6，原始Session2话题为停车空间咨询 | indifferent_to正确指向Marcus，但对象无主题，排第2 | structured回答把停车话题的无所谓错误用作搬家早期态度；需主题绑定及来源上下文 |

新选中的10个契约链接事件时间均为UNKNOWN，明确使用 source_time fallback，没有伪造发生时间。原始history保留session、turn、observed_at，但本轮speaker payload不携带这些结构化元数据；不能把统一诊断观察时间当作“最后已知情绪”的开始时间。

Q1 linked获得多数认可仍有停车/开发混用；结合相同prompt裁判不稳定现象，只能作为局部诊断收益。Q9 baseline/structured的有效回答没有恢复“寡言→坦诚”的完整对比，structured还使用了错误话题的indifference。当前证据不足以推进生产默认或1,031题代表性评测。

## 后续优化建议与验收边界

本轮已确认的实现与评测工作完成。下面是下一轮设计输入，尚未实施，不更改本轮冻结标签、源码和运行档案。

1. **原生关系和言语行为校验**：补充“said yes to the job”与第三方转述对照，减少整行关键词误判；保持 C++ 单一规则实现。对feels that/认知判断、职责/信任继续使用独立新对照，不能只依赖模型返回supported。
2. **原生来源上下文与主题/时间**：设计携带speaker、session、turn、原始时间和相邻话轮引用的SourceTurn输入；actor/主题指代在C++证据契约中验证，binding只传输数据。明确“原始话语时间”与“事件开始时间”，保留无法解析的相对时间。优先用Q9停车/搬家混淆和最后状态对比作回归。
3. **输出协议与服务稳定性**：评估供应商支持的结构化输出方式，由C++适配器提供能力与错误分类；保持单值解析和无内容重试。Q9失败两组若重跑，应另建、另冻结传输恢复诊断，引用本轮失败记录，不能覆写本轮结果。
4. **评价口径与基线噪声**：保留原P1不改，另增经审阅的subject/modality/polarity/scope/topic/time标签；明确base兼容与新增语义精度的双重门槛，协议调整需单独确认。本轮combined门槛仍按原方案判失败。相同候选的裁判一致性要作为评价工具自身的控制项；旧base错误陈述也需要在新的来源重建实验中处理。

## 2026-09-12 优化实现进展

已按上述建议完成第一批 C++ 优化：`feels` 的认知判断和 `trusts` 的职责陈述会在确定性校验阶段拒绝；第一人称“said yes”不会因关键词自动标为 `REPORTED`；整行来源单元可识别 `Session | speaker | turn` 元数据，证据保留 `topic` 与 `source_turn`，Context Pack 同步展示这些字段。Python schema 仅增加对应只读数据类，不包含语义规则。

新增的 C++ 回归用例和 Python 原生契约用例均已通过。结构化输出仍由 C++ 统一解析与记账，未在 Python 增加重试。下一步真实评测需重新冻结候选，单独报告扩展标签和裁判一致性；本报告上一轮真实结果保持不变。

本轮门槛：controls未通过、synthetic未通过、combined P1未通过、technical未通过；base语义保留通过。实验开关继续默认关闭，未执行1,031题全量评测。
