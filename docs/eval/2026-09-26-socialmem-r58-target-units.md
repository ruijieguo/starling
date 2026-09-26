# SocialMemBench R5.8：目标来源索引的配对诊断

## 当前结论

R5.8 已完成 C++ 实现、完整回归、合同/质量审查和六任务真实配对诊断。目标来源索引 B 的三个任务均技术通过，对照 A 为 2/3；达到进入下一轮统一八库重建的预定门槛。实际消费 37 次 HTTP、595505 tokens，无未知消费。它还没有证明 QA 提分：Kwame B 保留 12 条/9 个来源，A 为 15 条/11 个来源，存在具体语义遗漏。扩大开发集仍为 0/8 完整健康库，新增 133 题没有可报告的准确率。

本阶段沿用用户已授权的自主优化流程：中文设计先行，先运行失败测试，再实现和验证；真实模型保持 `qwen3.8-27b`。核心提示、来源分批、解析、语义校验、准入及提交均在 C++，Python 仅承担 binding、编排和审计。

## 诊断依据与改动

R5.6 扩大建库在 Mum 的首批失败：一次 schema 纠错后，响应仍引用本批之外的 c8。原提示同时呈现全部 c0—c14 来源索引，并要求检查每个来源单元，末端才限定本批 c0—c7。该现象支持检验“完整上下文与可引用目标未充分区分”的假设，尚不能据此确定唯一根因。

R5.7 的严格输出诊断也未能提供可靠替代方案：两次 HTTP 均成功，但正向 admission fixture 返回根数组，违反要求根对象的 schema，原生判定 `nonconformant` 后停止；总计 494 tokens。该结论仅适用于本次模型、服务及合同组合，不外推为模型整体不支持 strict。

新原生开关 `claim_batch_target_units` 默认关闭。开启时保留完整原文作为上下文，只把当前批的来源单元列入可引用索引，保留全局 clause ID、原始 UTF-8 span 和 SourceTurn 元数据。抽取与提交完整性重放共用同一 C++ 提示函数；默认关闭的既有提示、计划及回执保持兼容。仍只允许一次原生 schema/envelope 纠错，批外引用继续失败；没有放宽语义规则或从失败响应中回收声明。

设计及执行步骤见[原生设计](../superpowers/specs/2026-09-26-socialmem-r58-target-units-design.md)、[原生计划](../superpowers/plans/2026-09-26-socialmem-r58-target-units.md)、[配对设计](../superpowers/specs/2026-09-26-socialmem-r58-paired-probe-design.md)及[配对计划](../superpowers/plans/2026-09-26-socialmem-r58-paired-probe.md)。

## 本地证据

先有 10 项新原生用例 RED、17 项既有 batching 用例通过，另有 5 项新 Python 用例 RED。实现后又补充顶层 prompt 被改写的失败用例，并在原生完整性检查中修复。当前针对性原生 42/42、Python 19/19 通过；两组独立旧核/新核进程比较确认关闭开关时完整 plan、prompt、receipt 字节相同。测试覆盖目标索引、中文 UTF-8 与来源元数据、协议纠错、后批失败零语义写入、独立 general_fact 通道以及提交前篡改拒绝。

最终全量 CTest 为 1354/1354 通过；baseline 在独立进程中 19/19 通过。初次混合进程测试的四项失败分别来自旧/新 core 导入冲突及沙箱不能监听 localhost，已以相应隔离进程和允许回环的环境完成验证，没有削弱冻结模块身份检查。独立合同审查和质量审查均无新增阻断项，质量复核另运行 28 项原生测试通过。

冻结候选核心 SHA-256 为 `ead8046e4a28d257f3429d865523c1af1f6275fd0cb1ba98d8fa8023894d6fef`，构建目录和安装目录一致。主代理重新核验清单中 311 个互异文件，包括全部受影响源文件、原生构建输入、测试、核心和验证日志。验证清单及最终结论见[native-candidate-verification.json](../../build/socialmem_20260926_r58_work/native-candidate-verification.json)和[native-final-review.json](../../build/socialmem_20260926_r58_work/native-final-review.json)。这些证据不构成真实模型收益。

其他证据位于 `build/socialmem_20260926_r58_work/`：`native-red.log`、`python-red.log`、`top-prompt-red.log`、`native-green-final.log`、`python-green-final.log`、`ctest-full-final.log`、`baseline-isolated-final.log` 和 `false-byte-parity-summary.json`。

## 提示规模的离线实测

以同一候选 C++ 和 FakeLLM 对固定原始输入生成每批初始提示，完整原文逐字保持，测得：

| 固定来源 | 批数 | A 总提示字节 | B 总提示字节 | 减少比例 |
|---|---:|---:|---:|---:|
| Mum | 2 | 87,850 | 78,734 | 10.4% |
| Kwame | 5 | 359,688 | 245,136 | 31.8% |

统计单位为 UTF-8 字节，包含所有初始抽取提示，不含纠错或 admission；不能直接换算模型 tokens、费用或准确率。此结果只确认目标索引减少了重复呈现的来源条目，尚未验证对生成遵循度的效果。输入历史封印、payload 身份及逐批记录见[prompt-layout-audit.json](../../build/socialmem_20260926_r58_work/prompt-layout-audit.json)，新增外部请求为 0。

## 配对验收与后续门槛

独立入口 `scripts/run_socialmem_r58_paired_probe.py` 已实现 prepare/run/check。初版完整 46 项通过；合同终审复现任务预约 ID 未绑定账本实际行的问题，先写 RED 后补齐整数类型、ID、状态与上界比较。质量审查又复现 admission 嵌套费用副本未核同源的问题，同样先 RED 再修复。最终完整本地测试 52/52 通过（58.51 秒），最终差量合同独立 2 项、质量独立 15 项及原诊断重放均通过。旧 51 项独立全套与其他边界用例按旧源码版本保存，不混称最终版本全套。测试使用真实 C++、本机 HTTP fixture 和逐任务 FakeLLM 回放；该组请求只到 localhost。最终日志为 `build/socialmem_20260926_r58_work/probe-green-admission-final.log`，审查见同目录 `paired-contract-review.json` 与 `paired-quality-review.json`。

审查阶段先以失败测试复现并修复：A 批外引用被错误阻断、候选 object/null 被错误计数、嵌套 HTTP 元数据妨碍语义回放、实际声明列没有参与数据库复验，以及提交/快照/分析/结算中断后的失败封存。费用从原始 HTTP 独立重算，语义由冻结 C++ 回放；分析未完成的证据明确为 partial，不生成虚构的成功语义终态。

从已封存证据中固定取 Mum 15 单元和 Kwame 33 单元的原始 payload。在同一新核心上比较 A（完整来源索引）和 B（当前批目标索引），次序固定为 Mum1-A、Mum1-B、Mum2-B、Mum2-A、Kwame1-A、Kwame1-B，总请求上界 54。只运行 belief、admission 和原生提交，不运行其他抽取通道、embedding、检索或 QA。

A 仅允许终末抽取阶段的 schema/envelope/batch_scope 失败，在传输和消费已知、原生回放证实后保留为对照并继续；admission 协议失败或其他故障停止。B 的任何技术失败或零准入声明均立即停止后续任务。三个 B 任务都完整健康且各保留至少一条声明，才满足另立统一新核心八库重建方案的技术门槛。若 A/B 均成功，只能报告这些固定输入通过，不能声称相对可靠性收益。声明条数和触及来源数不等于语义召回率。

真实运行和独立审计已完成，结果见下文。旧 57 题历史成绩与本次新增 133 题继续分开报告；产品默认配置不自动推广。

长期复验边界：Starling 核心和 runtime 始终使用 prepare 绑定的唯一冻结路径。编排 helpers 由 workspace 程序执行，真实 run 前后核对其与冻结源码一致；只读 check 使用当前审计程序和冻结核心，源码及审查 SHA 随证据归档。本次审计结论绑定该检查程序版本，不保证未来修改后的 checker 产生逐字相同结果。

## 真实配对结果

| 任务（实际次序） | 技术终态 | 原生协议纠错 | HTTP 次数 | 实际写入 | 触及来源单元 | 总 tokens |
|---|---|---:|---:|---:|---:|---:|
| Mum1-A | 通过 | 1 | 4 | 4 | 4/15 | 52072 |
| Mum1-B | 通过 | 0 | 4 | 4 | 4/15 | 44175 |
| Mum2-B | 通过 | 0 | 4 | 4 | 4/15 | 44177 |
| Mum2-A | 抽取协议失败 | 1 | 4 | 0 | 0/15 | 52341 |
| Kwame1-A | 通过 | 1 | 10 | 15 | 11/33 | 218768 |
| Kwame1-B | 通过 | 1 | 11 | 12 | 9/33 | 183972 |

同 holder 的完整 payload、来源单元、分批目标及新核心一致，仅切换目标索引开关。独立审计还确认三个 A 任务的初始提示与对应历史原文提示逐字相同。不能将历史 Mum A 失败替代本次对照：本次 A 第一次通过、第二次失败。

Mum2-A 的第二批先把 holder/subject/predicate 等顶层字段误放入 evidence，触发 schema 错误；纠错后又引用本批之外的 c6，触发 `batch_scope_failure`。第一批已暂留的 3 条未进入最终库，实际 belief 语义写入为 0。该失败符合预注册 A 抽取协议继续条件，程序保留证据后继续 Kwame，不额外补跑。

两个 Mum B 均没有协议纠错，实际保留内容均为 c2/c6/c7/c13 的 4 条，逻辑字段与来源证据一致。原始 6 个候选并非完全一致：c14 的一处措辞不同，但都被 admission 以 `missing_context` 拒收。这支持继续检验目标索引降低批次混淆的假设；仅有两个来源及重复运行，不能估计总体成功率或宣布可靠性问题已解决。

Kwame 两臂都在最后一批出现 holder 等字段误放入 evidence 的 schema 错误，均由一次纠错恢复，说明新索引没有消除字段层级错误。B 的 token 消费比 A 少约 15.9%，但多一次 admission 请求；不能仅用请求次数代表 token 成本。全阶段输入 563682、输出 31823，合计 595505 tokens，37 个互异响应 ID；账本 committed=37、reserved=0、remaining=17，未消费余额没有触发额外请求。

## 语义短板与下一步

Kwame A 的成功终末输出为 48 行，30 行被确定性规则拒收，18 个候选进入 admission，3 个被拒，最终写入 15 条。B 对应为 46 行、28 行确定性拒收、18 个候选、6 个 admission 拒收，最终 12 条。两臂各有另 2 行来自 schema 失败的原响应，不能混入成功终末分母或直接做加减。

B 未保留 A 的 c4 和 c16 来源：c4 只生成 `promises: smash it this time`，被判 `wrong_relation`，A 的腿部状态知识行未出现在 B 输出；c16 在 B 输出中完全缺席，A 则保留相关情绪声明。B 新形成的 c8/c12/c13 候选均未通过准入；c22 的两行合成一行，c32 增加一行 belief。因此 15→12 同时涉及遗漏、关系选择、拒收和声明拆合，不能直接当作质量下降百分比，更不能当作准确率提升。

B 仍有明显的范围和限定词损失。Mum 每次 9 条确定性拒收中，7 条缺 QUESTIONED、1 条缺 CONDITIONAL、1 条丢失显式时间。Kwame B 的 28 条中，14 条缺 QUESTIONED、7 条缺 CONDITIONAL、4 条缺显式时间、2 条 object 丢失 topic、1 条 object 丢失时间限定。这些是后续 C++ 局部范围判定和生成合同简化的诊断方向；不能一概当成误拒，也不能直接取消约束。

下一阶段已先写[R5.9 统一八库设计](../superpowers/specs/2026-09-26-socialmem-r59-expanded-baseline-design.md)和[实施计划](../superpowers/plans/2026-09-26-socialmem-r59-expanded-baseline.md)，把已通过的目标索引候选应用于全部固定开发来源。先获得健康的 8 个库，再完成 133 题的固定检索与 fresh QA。该 cohort 尚无健康旧分数，首次完成的结果应称 baseline；内部 v6 hybrid10/v9 sources10 对照也不能解释为抽取 A/B 的 QA 增益。已观察到的 c4/c16 遗漏保留为后续诊断线索，不据此改题目或挑选分母。

## 封印与可复核证据

prepare 封印 `cf95c3412a32f22542f72b5b81d7d4d81b04377d4338a75891f8439dc1be73e0`，544 个封存文件；run 封印 `30d00e455388d6002b692080e0e7b60b13f56d76790245f1b3f8c57971b5735d`，45 个封存文件。真实 run 和独立正式 check 均退出 0，六任务无缺失，审计前后文件哈希不变。

- [真实 summary](../../build/socialmem_20260926_r58_paired/run/summary.json)及[正式只读 check 日志](../../build/socialmem_20260926_r58_work/paired-real-check.log)。
- [独立 HTTP、账本和数据库审计](../../build/socialmem_20260926_r58_work/paired-real-audit.json)，由不导入评测 runner 的只读脚本重算，新增 provider 请求为 0。
- [逐批中文语义诊断](../../build/socialmem_20260926_r58_work/paired-semantic-audit.md)及[逐行 JSON 证据](../../build/socialmem_20260926_r58_work/paired-semantic-audit.json)，区分失败响应、成功终末、候选、拒收和实际入库；原始响应未修补。
