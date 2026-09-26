# SocialMemBench R5.9：统一目标索引核心的扩大 baseline

## 当前进展

R5.9 八库重建入口已完成本地实现，修复后最终 77 项回归全部通过，独立合同与质量审查均通过；本阶段真实建库已结束并被第二个 scope 的协议失败拦下，只有首库健康，后六库未执行；新增 133 题没有准确率结果。目标是先建立技术健康、身份一致的 baseline，再据错误分析改进 C++ 能力。设计、失败测试和实现按此顺序执行，不更换题目、模型或评分规则。

前置 R5.8 配对已完成：B 三个任务均技术通过，A 为 2/3，实际 37 次 HTTP、595505 tokens。文档同步后再次只读检查退出 0，原始记录与账本一致。该结果只放行统一八库重建，不代表语义覆盖或 QA 提升。Kwame B 保留 12 条、涉及 9 个来源；A 保留 15 条、涉及 11 个来源。完整诊断见[R5.8 报告](2026-09-26-socialmem-r58-target-units.md)。

R5.9 使用冻结 C++ 核心 `ead8046e4a28d257f3429d865523c1af1f6275fd0cb1ba98d8fa8023894d6fef`，开启严格布尔 `claim_batch_target_units=true`，保持批大小 8、一次原生协议纠错、抽取输出 8192 tokens、模型 `qwen3.8-27b`、thinking=false、temperature=0、HTTP retry=0。所有语义解析、来源分批、准入与提交仍由 C++ 完成；Python 仅编排和审计。

## 固定评测集及独立清点

本轮重新核验 R5.5 prepare 封印 `66b13d7e22b0794903467d9ea89f21b91379118d43866b4504b49fd9bd0178d0`，独立检查样本唯一性、分组完整性以及分组内记录与 sample 的逐字段一致性。结果为 133 题、6 网络、8 scopes，未使用模型请求。该集合属于已使用过的开发数据；旧 57 题和历史保留集不进入本轮分母。

| 网络 | 题数 |
|---|---:|
| grp_7a8b9c0d | 5 |
| grp_a5b6c7d8 | 34 |
| grp_b1c2d3e4 | 32 |
| grp_c2d3e4f5 | 27 |
| grp_d7e8f9a0 | 19 |
| grp_e6f7a8b9 | 16 |

自由回答共 106 题，其中 long_form 86、short_answer 20；选择题 27。题型计数为 Q1=25、Q2=10、Q3=1、Q4=10、Q5=12、Q6=8、Q7=24、Q8=40、Q9=3。网络和题型分布不均，报告须保留分项、固定全题分母及按网络分组的置信区间。Q3 和 Q9 样本很少，不能从少数题推断该能力的总体准确率。

清点证据见[cohort-independent-audit.json](../../build/socialmem_20260926_r59_work/cohort-independent-audit.json)。本地 prepare 已由新原生核心重新计算确认 65 holders、1322 来源单元、197 批次、belief 请求上界 591 和三通道抽取上界 851；这些是规划计数和费用上界，不是已完成的真实建库量。

## 本地验证证据

新增入口修复后最终回归为 77/77，通过耗时 280.49 秒。实现 SHA 为 `6da789332c267d04317fae1a48e3105ff562e4e82a9afd83a999c339c9de9336`，测试 SHA 为 `81f9f2420a0e8e6f7b9db22b16316602fb94f239b21d53ff06db565fa2707d1d`。初版 69 项通过后，主代理重新计算交接清单的 11 个文件指纹，全部一致，并在独立子进程对完整八库模拟产物执行正式 CLI check：8/8 健康、retrieval_ready=true、qa_ready=false，封印前后不变，报告实际 88 个审计程序文件指纹。

模拟运行使用真实候选 C++、本机 HTTP 服务与 Stub 向量，观测 327 次本机请求、3924 个合成 tokens；这不是 DashScope 请求、真实八库结果或 QA 分数。非空事件、belief 和 general_fact 共存、共享派生行、跨秒默认时间、数据库和费用证据篡改、异常中断都已有针对性覆盖。早期 RED 中存在被 fixture 初始化问题提前阻断的情况，交接清单明确限定，并通过从健康 fixture 出发的隔离防线失效验证补足，未混称有效 RED。

证据：[最终完整日志](../../build/socialmem_20260926_r59_work/expanded-full-green-quality-fixes.log)、[交接清单](../../build/socialmem_20260926_r59_work/expanded-implementation-handoff.json)、[主代理独立 check](../../build/socialmem_20260926_r59_work/expanded-parent-final-check.json)。最终 77 项源码的独立 CLI check 再次通过，8/8 模拟库完整且封印不变。独立合同与质量审查均通过，真实运行结果须另行补充，本地通过不替代真实建库验收。

独立合同审查发现初版允许缺少嵌套 structured_output 费用字段的回执通过；原始 HTTP 消费仍被正确统计，缺陷是副本完整性漏检。现按冻结 C++ 输出的 17 个必需字段及类型验证完整副本，新增四项 RED→GREEN。审查者复验 48 个删除/等值类型篡改变体、scope 及完整阶段重新封印场景，均被拒绝，正常八库模拟产物仍通过。主代理还对 R5.8 的 37 个真实历史响应作离线兼容审计，37/37 通过，原始封印不变，新增 provider 请求为 0。见[合同审查及修复闭环](../../build/socialmem_20260926_r59_work/expanded-final-spec-review.md)与[真实历史回执兼容证据](../../build/socialmem_20260926_r59_work/expanded-nested-real-compatibility.json)。

## 建库验收与失败处理

质量审查另复现并已修复两项边界：删除一个 holder 回执后，scope 会正确判失败，但费用把剩余 12 次请求、144 tokens 误报为完整量（原模拟数据为 16 次、192 tokens）；episodic 与 general_fact 同为 put/report/OCCURRED/POS 时，四字段匹配误将事件的固定来源时间视为 legacy 默认时钟，导致合法原生写入被拒绝。这些是审计层问题，未发出新的真实请求。先补中文合同，再完成四项 RED 与局部修复：scope 费用核对完整 holder 清单；默认时钟资格绑定原生回放行的 engram、非负整数 chunk_index 和精确 chunk-N 来源标记，再与 retained/commit 对应。相关 11 项 GREEN 及最终 77 项全套通过；合同审查独立重现两项修复后的预期结果，质量复验也已通过。证据见[质量审查复现](../../build/socialmem_20260926_r59_work/expanded-quality-probes.json)。

独立入口为 `scripts/run_socialmem_r59_expanded.py`，提供 prepare/build/check；历史 R5.6、R5.8 入口及封存目录保持原身份。R5.8 资格在独立子进程正式复查，R5.9 核心与 runtime 统一从自身 prepare/frozen 唯一路径加载，避免同一进程导入不同冻结路径的原生模块。

八个 scopes 按固定顺序串行构建，第一个不健康 scope 完成证据保全后停止后续 scopes。逐 holder 将真实响应通过冻结 C++ 回放，并核对实际数据库的 predicate、object、holder、modality、polarity 及来源字段；retained 与实际写入必须双向一致。不能仅凭回执中的成功字段或 semantic JSON 判定健康。

初始化、提交、写盘、快照、分析和结算中断均保存可复核的部分证据。缺响应或未知远端执行不记作零消费。抽取请求的保守扣账、已观测 chat HTTP 和 embedding 原生计数分别列出；当前 binding 未提供 embedding 完整 HTTP/usage，故 chat tokens 不能充作整个阶段的完整 token 消费。

全部 8/8 库技术健康后才放行检索。八库结果、逐项审查和费用将在真实运行后补入本报告，当前不得生成成功库数量或分数。

本地完整流程还发现了两项原生重放边界。其一，sleep 会由多 holder 的共有事实生成 `__common_ground__` 派生行，验证必须覆盖共享库中的原生派生及引用关系。其二，legacy JSON parser 直接把当前 UTC 时钟写为 observed_at，跨秒重放会产生不同的默认时间；冻结核心没有该时钟的注入入口。设计已限定仅对有原生来源证明、行/span 一致且处于各自调用窗口的默认时钟作比较归一，保存原始值，其余来源与语义时间继续严格检查。详见设计中的对应边界。这些是本地 fixture 和源码发现，不是已完成的真实八库结果。

legacy 默认采集时钟与固定 source_time 不同，也意味着后续跨次评测需要单独审计时间影响；本轮同库两臂共享实际时间，不在运行前临时修改核心。下一轮可在 C++ 中研究由原始来源或明确注入时钟统一默认时间，但尚未证明这个差异导致了任何 QA 错误。

最终质量审查独立重跑原两项复现，并确认删除可选 episodic 扩展行仍通过、把事件 observed_at 与 span 同时移入 legacy 时钟窗口仍被拒绝。最终审查见[质量报告](../../build/socialmem_20260926_r59_work/expanded-final-quality-review.md)。正式 prepare 与独立 check 已通过并已启动真实重建，尚未生成完整八库或准确率结果。

## 正式执行记录

正式 prepare 已在全新 `build/socialmem_20260926_r59_expanded/prepare` 完成，独立 check 退出 0，seal 为 `ca6c3e14db1172000dc12a553db14c5f012c0451d9fecbe9d7cf827ebade2ae4`。原生重新确认 133 题、8 scopes、65 holders、1322 units、197 batches，belief 上界 591、三通道抽取上界 851。prepare 与 check 的 provider 请求为 0。验证、审查和中文文档已复制到不可变 `real-evidence` 后再冻结，后续报告更新不改变运行证据。

真实 build 已按已有授权启动，输出目录 `build/socialmem_20260926_r59_expanded/build`。首 scope `ae45ef45d7ff23aade9a9a29` 于 `2026-09-25T19:16:49.100407Z` 进入原生调用，已持久化 40 次抽取上界预约；这是预算上界，不是已发生请求数。首 scope 已通过，主代理随后在独立进程复算 scope 审计并确认全部文件哈希不变；第二个 scope 随后因 Tomas 第二批协议失败停止（详情见下文）。首库包含 36 条声明，其中 21 条具有 semantic_claim，覆盖 8 种谓词；四个 holder 均无抽取失败。已观测 24 次聊天 HTTP、186358 个聊天 tokens，另有 5 次 embedding 原生请求；embedding token 尚不可见，不能把聊天用量说成全阶段总量。终态为 1/8 真实库通过、第二库技术失败、六库未执行，检索和 QA 均未执行。独立证据见[首库审计](../../build/socialmem_20260926_r59_work/expanded-real-scope1-audit.json)与[声明清点](../../build/socialmem_20260926_r59_work/expanded-real-scope1-inventory.json)。过程见[运行日志](../../build/socialmem_20260926_r59_work/expanded-real-build.log)、[启动记录](../../build/socialmem_20260926_r59_work/expanded-real-build-launch.json)及[prepare 独立复验](../../build/socialmem_20260926_r59_work/expanded-real-prepare-check.json)。

## 本次真实建库终态与失败定位

真实 build 退出码为 1，终态 incomplete。首库通过；第二库的八个 holder 完成 belief 批次，Tomas 在第二批（batch_index=1，target c8–c15）的初次输出和一次协议纠错均失败。两次 JSON 有效、HTTP 200、finish=stop，但声明顶层仅有 confidence 和 evidence，其余 holder、subject、predicate 等字段错放在 evidence 内，C++ 严格 schema 检查报告 `statements[0].holder: required string: holder`。这不是谓词目录不足或写数据库报错。第二库保存了 183 条声明及全部来源，但原生 belief 批次不完整，因此不能将其视为健康库，也不能用这个不完整库形成可比较 baseline。

独立进程正式 check 返回同样的 incomplete（退出 1），逐字段复算与原 summary 一致，34 个封印文件哈希全部匹配。build seal 为 `6c04f6161dcf1821972e939e8c0070104337e809cea7b68b00c76eb22acd90c7`。完整收尾证据见[运行核收](../../build/socialmem_20260926_r59_work/expanded-real-build-closure.json)和[独立检查](../../build/socialmem_20260926_r59_work/expanded-real-build-independent-check.json)。原始阶段保持封存，不原地续跑或覆盖。 Tomas 的独立冻结核心诊断确认：15 个生成示例的字段布局与输出模板不一致，两次失败输出呈现相同错层形态；这仍是待验证的生成因素。详情见[原始失败诊断](../../build/socialmem_20260926_r59_work/expanded-real-tomas-failure-diagnostic.md)，下一步先按[R6.0 中文布局设计](../superpowers/specs/2026-09-26-socialmem-r60-statement-layout-design.md)做最小 C++ 对照，不自动搬移字段。

本次两个已执行 scope 合计 111 次聊天 HTTP、1,305,003 个聊天 tokens，另有 28 次 embedding 原生请求。聊天用量完整且无未知执行；embedding 未暴露 token usage，故全阶段总 tokens 仍为未知。账本无未结算预约，抽取按预约上界保守扣费 184，另有 embedding 28，总扣费 212；这些预约扣费不能误报为实际 HTTP 数。后六库、检索和 QA 均未执行。

## 检索、QA 与分析合同

固定两臂为 baseline=`evidence_profile_v6/hybrid/k10` 和 source10=`evidence_profile_v9/sources/k10`，每臂 133 题，共 266 个检索终态。只有 266/266 检索健康且 context、数据库身份及账本审计通过，才进入 532 个 fresh QA 终态。检索预算 1336、answer/judge 预算 956；预算是计账上界，不是已发生请求。

两种回答政策为 legacy 和 grounded_memory_v1。沿用 answer512、thinking=false、judge64、judge thinking 未显式设置、HTTP retry=0 和最多 4 并发。grounded_memory_v1 全 133 题的 source10 准确率减 baseline 为主要终点，legacy 为次要终点；失败题计零，保留共同正常子集分析。继续扩大门槛仍为净增至少 7 题、按网络分组 bootstrap 的 95% 区间下界大于 0、共同正常增益同向，且每臂至少 127/133 正常。bootstrap 重复 100000 次、seed=20260925，只有 6 个网络，区间仅描述本次开发实验的不确定性。

本轮八库均使用目标索引，因此内部检索臂差异不能归因于 R5.8 抽取 A/B。该 133 题 cohort 之前没有健康旧分数，首次完整结果称为 baseline。后续诊断依次检查：来源是否进入库、所需语义是否被保留、检索是否选中并呈现证据、回答是否正确利用证据，以及相同实际 judge 输入下的评分波动。分别报告协议失败、语义遗漏、检索选取、回答和裁判问题，不能将所有错误归为谓词不足。

设计与实施计划见[统一八库设计](../superpowers/specs/2026-09-26-socialmem-r59-expanded-baseline-design.md)和[实施计划](../superpowers/plans/2026-09-26-socialmem-r59-expanded-baseline.md)。

## 并行完成的能力诊断

正式 R5.9 首库现已完成独立逐行诊断，主代理另用 `.venv/bin/python -B` 重跑诊断脚本，退出 0。belief 原始 49 行中，确定性合同拒收 19 行，其余 30 行进入 admission，再拒收 9 行，最终 21 行带 semantic_claim 写入；episodic 13 行、general_fact 2 行，共 36 行。八份原始 belief 响应经正式 prepare/frozen 的唯一 C++ 核心重解析后，与回执逐项一致；首库全部七个文件哈希不变，诊断新增 provider 请求为 0。证据见[首库中文诊断](../../build/socialmem_20260926_r59_work/expanded-real-scope1-extraction-diagnostic.md)。

首库的 49 条 belief 原始行均使用已有谓词，没有发生谓词目录拒收。确定性拒收包括 QUESTIONED 11 条、CONDITIONAL 1 条及时间或主题合同 7 条；admission 原有模型判定为 wrong_relation 5、not_asserted 2、wrong_scope 2。当前证据将后续研究重点指向局部陈述与来源范围的对齐，但这些计数不是语义误拒率。三个原文例子均存在尚需核查的完整候选语义；其中条件句例子还包含 topic 非逐字来源的后续合同阻碍，不能声称只改范围判断即可写入。

检索与 QA 入口的首轮完整本机回归为 105 项通过、1 项失败：266 次检索对应的 1336 次 embedding 请求正确，532 个 QA 终态中的 30 个回答在原生传输层报错，实际本机聊天请求为 896，未达到全部健康时的 956。随后资源观测定位预算账本连接未显式关闭：每 50 个 QA 任务约增加 100 个描述符。按中文补充设计扩充 SQL 异常路径的六项 RED 后，新入口使用显式关闭连接的预算账本；答案原生绑定修复后的完整回归为 115 项通过，四线程完成 1336 次 embedding、956 次本机聊天与 532 个健康 QA 终态，描述符保持约 24–25 个。另一路回归发现测试选中零消费预约而未实际篡改，修正后历史回归112项通过；加入原生 binding 和 failure audit 覆盖后，当前最终回归为115项通过。入口曾在合同审查中被联合篡改 normalized answer 阻断：Q6 伪造 raw_xml 与 response.raw_response 可被接受并改变分数；该问题已完成 RED、C++ binding 和 evaluator 修复，独立差量合同复审结论为 PASS；新的8/8 build与独立check完成前继续禁止真实评测。主代理复核17个交接文件指纹，并在独立进程check稳定模拟产物，确认532/532健康、956次本机聊天及11472个合成tokens。完整交接见[评测入口证据](../../build/socialmem_20260926_r59_work/evaluation-implementation-handoff.json)，差量合同复审已 PASS，差量质量复审已 PASS；新的8/8 build与独立check仍待完成。本机模拟结果不是 DashScope 真实评测分数。旧复用边界测试另有 120 项通过、8 项失败及 32 项 setup errors，已定位到历史冻结核心或源码指纹不匹配，仍需核查新调用路径的覆盖，不能按全套通过汇报。真实建库已因下述协议失败结束；两类失败属于不同进程和环节，当前冻结核心保持不变。

### 规范化答案绑定修复与验证

合同探针的真实反例是：Q6 的 HTTP `message.content` 和 `raw_completion` 保留错误选项 `0`，而 `raw_xml` 与 `response.raw_response` 被联合改写为金标准选项 `2`；若只依赖副本一致性，旧入口会把该题重新计分。修复把 `strip_reasoning_trace` 以只读纯函数暴露于 C++ binding，`raw_accounting`、QA verdict、终态校验和 failure audit 均通过该 native binding 重新生成 normalized `raw_xml`，Python 没有复制 reasoning 清理逻辑。合法 `<think>trace</think>answer` 可以通过；normalized answer 或 HTTP content 篡改均判技术失败，并保留已知 12 tokens。

正式 R5.9 frozen core `ead8046e4a28d257f3429d865523c1af1f6275fd0cb1ba98d8fa8023894d6fef` 和原有 1/8 build 封印未重标。为验证实际新 binding，单独 CMake 编译候选 core，路径为 `build/socialmem_20260926_r59_work/evaluator-native-binding-cmake/python/starling/_core.cpython-314-darwin.so`，SHA-256 为 `63853e2c8ee8b92db4ed8d88662382cf4752334da9ac602a8370e160b67f416a`；候选 fixture 仅用于独立验证，provider 请求为 0。候选检查证明 native 清理可用、合法回执 `healthy_http=true`、normalized 篡改和 HTTP content 篡改均为 `healthy_http=false`，联合篡改终态被 `validate_qa_terminal` 拒绝。证据见[修复前 corrected RED](../../build/socialmem_20260926_r59_work/evaluation-answer-binding-corrected-red.log)、[候选 smoke](../../build/socialmem_20260926_r59_work/evaluator-native-binding-smoke.log)、[候选 binding 检查](../../build/socialmem_20260926_r59_work/evaluator-native-binding-independent-check.json)和[候选构建记录](../../build/socialmem_20260926_r59_work/evaluator-native-binding-fixture/candidate-build.json)。

完整 R5.9 evaluator 本机回归为 115/115；旧 frozen core 没有新 binding，因此带 reasoning 的旧 fixture 会被 fail-closed，完整 localhost 回归使用无 reasoning 的稳定响应验证 1336 embedding、956 chat、532 健康 QA 和独立 check。该回归只证明评测入口合同和资源生命周期，不产生 SocialMemBench 分数。最终回归日志见[evaluation-answer-binding-regression-final.log](../../build/socialmem_20260926_r59_work/evaluation-answer-binding-regression-final.log)。交接清单见[evaluation-implementation-handoff.json](../../build/socialmem_20260926_r59_work/evaluation-implementation-handoff.json)，当前 SHA 为 `d53d15339037abd9ae6863c6e2d52efa194e17b22972c45b51a7eb1b17ad9ff3`；修复前无 native binding 的 corrected RED 见[evaluation-answer-binding-corrected-red.log](../../build/socialmem_20260926_r59_work/evaluation-answer-binding-corrected-red.log)；差量复审闭环见[evaluation-final-spec-review-closure.md](../../build/socialmem_20260926_r59_work/evaluation-final-spec-review-closure.md)，质量复审见[evaluation-final-quality-review-closure.md](../../build/socialmem_20260926_r59_work/evaluation-final-quality-review-closure.md)。新的8/8 build与独立check完成前，仍不得启动新的真实 retrieve/QA。

已用 R5.8 冻结 C++ 对三个 B 任务的九个成功终末响应重新解析，逐条拒收及范围诊断与原生回执完全一致，封存文件未改变，新增外部请求为 0。三个任务合计 28 条 QUESTIONED 拒收全部退回整来源单元判断：18 条因对象未逐字命中，8 条因边界不明确，2 条因候选不满足局部放行条件。这里含两次 Mum 重复，不能据此估计总体误拒率。

代码与原始来源共同指向一个值得独立改进的能力：声明与局部支持语句的对齐。当前 CONDITIONAL/显式时间约束直接检查整个话轮，QUESTIONED 的首句局部放行范围也很窄。例如 Kwame 的“我要买装备”会受到同话轮后段“如果需要，我可以帮忙”的条件词影响。部分来源本身确实是提问或带条件，不能把这些拒收一概当错，更不能删除守卫。详细反例、原生证据和未来必须覆盖的正反用例见[范围诊断](../../build/socialmem_20260926_r59_work/scope-rejection-audit.md)。当前 baseline 使用的核心保持冻结，后续能力修复另按文档、RED、C++ 实现与同口径 fresh 评测执行。
