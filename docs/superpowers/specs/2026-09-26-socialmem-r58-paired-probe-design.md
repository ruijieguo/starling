<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.8 目标提示的配对原生验收

## 固定问题与授权

本阶段实现[R5.8核心设计](2026-09-26-socialmem-r58-target-units-design.md)的真实小规模验收。用户已授权自主迭代及DashScope请求；仍按文档、RED、编排实现、本地验证、审查、真实运行顺序执行。C++目标单元实现及完整回归未通过前，禁止启动真实请求。

本阶段只运行belief抽取、admission及原生commit，不调用general_fact、episodic、embedding、retrieve或QA。独立通道开关隔离由原生/绑定回归验证，此处不重跑无关模型通道。

## 输入身份与阶段

新增`scripts/run_socialmem_r58_paired_probe.py`和对应Python测试，提供prepare/run/check。输出存在即拒绝；不覆盖、不续跑。prepare/check零provider，run串行，不从CLI暴露模型、题目、批大小、臂或重试数。

来源只从两份固定历史seal读取：

- Mum：`build/socialmem_20260925_r56_expanded/build`，seal `6dcbd5a82172728cb2ae84f2b4811e94ced0c3552bd8598e4252130ab1fe762c`，scope `ae45ef45d7ff23aade9a9a29`的frozen.db，tenant=default、holder=Mum。预期15个原生来源单元、2批。
- Kwame：`build/socialmem_20260925_r56_kwame/run`，seal `30f33e4437f09eaf7b080b7bd630c11afb4f2e10b0767e6e083d95f170f716a7`，该目录frozen.db，tenant=default、holder=Kwame。预期33个单元、5批、12133个payload UTF-8字节。

先核对固定seal及全部文件。Mum用只读immutable SQL取holder唯一source_documents→engrams payload。Kwame的belief-only probe没有source_documents行：使用固定`remember-prepare.json`和`commit.json`绑定的engram_ref读取唯一engram的原始payload，再与固定`binding.json`的holder、payload hash及12133字节长度交叉核验。不能因缺少source_documents新造来源或切换输入。两者均记录原engram、payload hash、全部原生来源单元与原回执身份。失败Mum库仅提供不可变原始输入，不作为健康库；不调用要求live源码一致的历史check。

prepare显式接收已经验证的候选`--core-sha256`，要求当前唯一build模块的SHA完全一致且暴露新原生开关；冻结当前Python包/模块/实际helpers、源码、验证日志和两个输入副本。Starling核心和runtime后续统一从该prepare/frozen加载：run/check都使用prepare绑定的唯一路径，不能因.so内容相同而换到run副本导入。编排helpers仍由workspace审计程序导入，run在前后以完整source identity核验其与冻结副本一致；check使用当前审计程序及冻结核心，不要求后续workspace源码等于历史源码。最终checker及helpers源码和审查时SHA一并归档，历史结论绑定该版本，不能宣称任意更新后的checker必然给出逐字相同的审计结果。候选选择由本轮原生合同/质量审查及测试日志支持，不将prepare自行通过称为原生质量验证。

抽取与admission固定qwen3.8-27b、原DashScope endpoint、8192 tokens、120000 ms、thinking=false、temperature0、HTTP retry0、JSON Object、batch size8、protocol retry1，其余语义policy沿用R5.6 prepare。A仅claim_batch_target_units=false，B仅true；新core相同。原生计划必须对两臂产生相同来源清单/目标集合和2或5批，只有B的profile/提示不同。

## 调度、成本与提交

固定任务次序：Mum1-A、Mum1-B、Mum2-B、Mum2-A、Kwame1-A、Kwame1-B。6任务，原生预算上界分别6/6/6/6/15/15，总54；任务列表与预算从固定输入及原生planner重建，不接受重写plan后重新seal改变次序或数量。

每个任务新建临时SQLite，原生remember_prepare→memory_extract_llm→remember_commit。成功或失败的原生结果都提交到该任务库以保留审计；原生分批失败必须零semantic claim，但来源和费用仍保留。用SQLite backup形成无WAL/SHM的稳定快照，不复制运行中的数据库文件当冻结结果。

进入原生调用前持久预约该holder的上界，立即写开始记录。回执与commit尽早归档；逐raw HTTP重算次数、usage已知小计及unknown，按实际次数结算；无法确认实际次数时按上界扣账且保留unknown。进入原生前的确定性失败可记已知0，进入后无完整回执不得记0。模型输出截断或缺usage均不能通过技术健康门槛。

A臂在HTTP正常、usage完整、次数已知且原生回放确认的前提下，仅允许终末抽取阶段的`schema_failure`、`envelope_failure`或`batch_scope_failure`保留为对照并继续下个任务。必须同时记录失败阶段，终末attempt的admission不能已调用；不能把admission产生的同名schema错误当作抽取提示失败放行。本次只检验抽取目标索引，admission协议失败、其他scope/source错误，以及传输/身份/预算/持久化故障均停止整个阶段。B臂任何技术失败或最终admitted claim为0立即停止余下任务。已计划未执行项明确列出，不补跑、不用未消费余额启动新任务。

## 只读复验

check重验完整seal、来源/prepare链、core及schema/policy、任务次序、原生计划、逐请求raw HTTP、账本每笔预约/结算、DB输入payload与已提交声明。不能单凭自报summary、ok或token计数验收。

解析、语义与分批完整性尽量用冻结C++和FakeLLM回放实际响应复核：从实际请求哈希绑定原响应，按同一policy重跑原生抽取/提交到临时库，比较原生错误、目标、候选、拒收、retained、最终语义声明及来源证据。HTTP用量独立从真实原回执核算；FakeLLM没有真实HTTP，不能冒充新的模型验收。不能在Python实现第二份prompt、claim parser或范围校验。遇到不完整响应无法回放时明确保留失败/unknown，不能伪造本地通过。

异常终态也必须能够只读审计已有证据、保守账本、缺失与未执行任务；后续实际run仍拒绝该目录。check成功审计失败回执不代表候选通过。DB hash和全部输入前后不变。

## 判定与报告

候选通过要求三个B任务都完整、原生协议/提交/HTTP/usage健康，且每个至少1条admitted claim。对照不要求必须失败；A/B全通过时只报告固定输入都成功，不能宣称相对可靠性收益。比较技术终态、协议纠错次数、确定性及admission拒收、保留数量、触及来源与输入/输出token成本，不把数量当语义召回率。

全部候选通过才进入统一新核心8库重建的下一设计。6任务是开发来源技术验收，不是统计可靠性证明、全量baseline或QA提分。主报告及全部中文状态入口据实际终态更新。
