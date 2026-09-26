<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.9：新核心 baseline 的检索与 fresh QA 接入

## 目标与前置合同

本文件细化[统一八库设计](2026-09-26-socialmem-r59-expanded-baseline-design.md)中已经批准的评测阶段。先完成本文档，再新增失败测试及编排实现。八库入口已通过本地验证并开始真实重建；检索和 QA 入口正在本机验证。本设计不构成八库全部通过或真实检索、QA 已执行的证据，实际进展与发现见[执行报告](../../eval/2026-09-26-socialmem-r59-expanded-baseline.md)。

本阶段继续使用固定 133 道开发题、6 网络、8 scopes。唯一可接受核心为 `ead8046e4a28d257f3429d865523c1af1f6275fd0cb1ba98d8fa8023894d6fef`，全部库由 R5.9 的 `claim_batch_target_units=true` 同一配置生成。评分合同沿用[R5.6 评测设计](2026-09-25-socialmem-r56-expanded-evaluation-design.md)。用户对自主迭代和 DashScope 请求的授权持续有效；不用新授权替代实现、验证或审查。

## 接入边界与方案选择

新增 `scripts/run_socialmem_r59_evaluate.py` 及 `tests/python/test_socialmem_r59_evaluate.py`，提供 retrieve/qa/check。复用已验证的原生检索、上下文渲染、回答任务、选项/裁判解析和统计，不修改产品算法、旧阶段脚本常量或其 globals。

直接替换 R5.6 evaluator 的 builder 全局变量会使身份、异常路径及预算函数隐含依赖混杂，故不用该方式。复制整套旧实现又会携带已复现的消费审计缺陷，故新增入口只显式编排新阶段身份、门槛、任务调度及审计，把稳定的功能通过参数调用。R5.6 的函数只有在其完整依赖链不绑定旧核心、旧 builder 或待修费用逻辑时才能直接复用。

现有 `raw_accounting` 在 `choices=[]`、`choices=[null]` 时会丢弃原始 HTTP 中仍然有效的 usage；`message=null` 还会触发未捕获异常。新入口须先独立读取完整 raw 的合法 usage，再判断输出格式、拒答与内容绑定；格式失败、副本冲突不抹去原始费用证据。QA 的 accounting/verdict/terminal/failure 路径不得通过复用旧 wrapper 闭包绕过该修正。这里只处理评测统计，不在 Python 实现声明语义或模型输出的产品解析。

legacy 回答绑定保留原生清理 reasoning 的行为：原始 HTTP 的 `message.content` 对应 `raw_completion`，原生 `response.raw_response` 对应任务 `payload.raw_xml`；不要求 `raw_xml` 或 `raw_response` 与 `raw_completion` 相同。回答判分与 judge prompt 继续使用原生 `raw_xml`。不能直接套用 R5.8 claim JSON Object、schema 或抽取响应相等合同。

### 规范化答案的原生绑定

合同审查在稳定 fixture 中发现：若同时篡改 answer 的 `raw_xml` 和 `response.raw_response`，而保留 `raw_completion`、原始 HTTP body 与 usage 不变，旧的费用检查仍可能接受伪造的选择题答案并重新计分。QA 终态必须同时证明规范化答案来自原生 C++ 回执：

- 原始 HTTP `choices[0].message.content` 必须等于 `response.raw_completion`；`response.raw_response` 必须等于记录的 `raw_xml`，并且 `raw_xml` 必须是同一冻结 C++ adapter 对 `raw_completion` 产生的 reasoning 清理结果。
- 清理函数只在 C++ 中实现；Python binding 仅暴露现有 C++ helper 供评测审计调用，不在 Python 复制 `<think>` 语义。绑定函数必须是纯函数，不能发请求或改变全局状态。
- QA accounting/verdict/terminal/check 在原始 raw HTTP usage 审计后调用此原生绑定；normalized raw_xml 或 response.raw_response 联合篡改、raw completion/message content 篡改、raw HTTP body 篡改都必须拒绝。合法 reasoning 清理仍可通过。
- 选择题的 prediction 和正确率只能来自通过上述绑定的 raw_xml；失败题计零并保留已知 usage，不能用伪造 normalized 文本修复分数。

先在已保存的联合篡改反例上补充 RED，再在 C++ binding 暴露 helper、R59 evaluator 接入最小验证；不改回答模型、提示、重试或产品解析逻辑。完成后须重跑 115 项、隔离候选 core 独立 check 和旧 raw compatibility；真实 provider 仍受 8/8 build gate 约束。

本轮修复的隔离验证固定两条身份边界：正式 R5.9 frozen core `ead8046e4a28d257f3429d865523c1af1f6275fd0cb1ba98d8fa8023894d6fef` 保持不变，缺少该 binding 时遇到 reasoning-normalized 回执必须判技术失败；带 binding 的候选 core 只在 `build/socialmem_20260926_r59_work/evaluator-native-binding-cmake` 编译，SHA 为 `63853e2c8ee8b92db4ed8d88662382cf4752334da9ac602a8370e160b67f416a`，独立 fixture 不得重标正式 R5.9 身份。候选独立检查必须证明合法清理通过、normalized answer 与 HTTP content 篡改均拒绝、provider 请求为 0。

## 身份、冻结和生命周期

`validated_build` 调用 R5.9 正式 check，要求 state=complete、8/8 健康、固定题目及分组完整、八个 frozen.db 哈希一致、无 WAL/SHM、账本可审计，并验证 core、严格 true 开关与 target_units_v1 计划。在任何 provider 构造之前拒绝不完整库、自报健康、旧核心、缺库、题目漂移或冻结依赖漂移。

原生 runtime 始终从该 build 所绑定的 prepare/frozen 加载。retrieve/qa 可保存运行源码副本，但不从阶段副本再次导入另一根目录的同 SHA 原生模块。逐题检索使用原库副本，原八库在阶段前后及独立 check 后哈希不变。所有阶段拒绝已有输出目录，不续跑、不静默重放。

评测冻结新入口/测试、实际 helpers、当前审计程序指纹、验证与审查证据，以及 config/sample/groups/build seal/prepare seal/八库 hash。真实阶段前后检查 workspace 执行源码与冻结副本一致。只读 check 记录当前审计程序的实际指纹，保留阶段审查源码，不要求任意未来 checker 产生逐字一致结果，也不为本轮引入通用 Python 冻结模块加载器。

## 检索合同

两臂精确为 baseline=`evidence_profile_v6/hybrid/k10`，source10=`evidence_profile_v9/sources/k10`；上下文上限 8000 UTF-8 bytes、min_source_items=7、radius=1。每臂 133 题，共 266 个唯一终态。通过显式新 core SHA 调用既有逐题检索和行校验，不复用绑定旧 core 的总体验收。

预算 1336：baseline 逐题预约对应 history holders 数，source10 预约 0、使用 StubEmbeddingAdapter。将原生请求计数与持久账本逐预约绑定；完整正常时 baseline 合计 1336，source10 必须为 0。缺失 native 计数不推断零。embedding 未暴露完整 raw HTTP/usage，明确报告此边界及未知 token，不伪造全阶段 HTTP 明细。

用 C++ 的 grounded packet 解析及 context renderer，核对所选来源原文、speaker/session/turn/time、engram、clause ID，以及实际 SQLite 中的声明。保留来源选择、实际上下文和 trace。全部 266/266 终态技术正常、逐 holder embedding 健康、degraded_paths 显式为空、context/ledger 验收通过，才允许 QA。锚点分数或候选数量不是 QA 放行条件。

## QA、异常消费与统计

双臂乘 legacy/grounded_memory_v1 两种回答政策乘 133 题，共 532 个 fresh 终态，请求上界 956。沿用 `qwen3.8-27b`、answer512、answer thinking=false、judge64、judge thinking 未显式设置、HTTP retry=0、timeout=120000ms、最多 4 并发。每题绑定 item/arm/policy/native answer prompt/context；裁判提示由冻结问题、gold 与原始回答经既有 helper 重建，不能仅比较自报哈希。

请求前持久化逐任务预约及 started；调用后保存原始 answer/judge HTTP、原生回执、usage、终态与结算。异常格式响应也保留已观测请求及有效 raw usage。`choices` 或 `message` 结构不合法、顶层或嵌套副本矛盾、finish/refusal 异常都判技术不健康；未知执行确定性或缺回执明确记录 unknown，禁止记作已知零。

adapter 构造失败且有明确未调用证据可结算零；进入 native 后缺终态、结算失败、写盘/汇总/封印中断须保留 partial 证据、预约和未执行任务清单。正式 check 独立复算 raw 已知费用、未知边界、逐条整数预约 ID、类型、上界和实际 SQLite 状态。ID、upper_bound、actual、charged_requests 和所有请求/token 计数在非空时均用严格整数校验，排除 bool、float 和字符串，不能依赖 `True == 1` 的值相等。空值须与实际状态一致：未结算或 charged_upper 的 ledger.actual 为 None，完整用量不可知时 total_tokens 为 None；不能为了满足类型检查而替换为 0。重新 seal 一个修改后的 summary 不能绕过复算。

### 预算账本连接生命周期补充

首轮完整本机评测出现后 30 个回答的 `CURLE_BAD_FUNCTION_ARGUMENT`。带文件描述符观测的复现表明，每 50 个 QA 任务约增加 100 个打开的描述符，预约 500 附近达到进程资源边界；阶段末垃圾回收后下降。既有 `BudgetLedger` 在预约和结算中仅使用 SQLite 连接的事务上下文，未显式关闭连接。新评测入口改用本阶段专用预算账本：沿用原表结构、预算计算、持久预约、结算、上界扣费和线程同步合同，每次连接均以显式关闭覆盖正常及异常退出，不依赖垃圾回收。该逻辑属于评测编排；不改旧 baseline helper、原生核心、重试策略或四线程并发上限。

先为构造、reserve、settle、charge_upper、snapshot 的成功及异常路径新增连接生命周期失败测试，再实现最小修复。随后重跑完整本机检索和 QA，要求全部 1336 次 embedding、956 次聊天及 532 个健康 QA 终态，并在同样的描述符观测下确认增长问题消除。保留首次失败、原始回执和资源诊断，不用重试或降低并发掩盖本次故障。

已按仓库要求通过 Context7 查询 [Python 3.14 SQLite 官方说明](https://docs.python.org/zh-cn/3.14/library/sqlite3.html)：连接上下文管理器不会自动关闭连接；[contextlib.closing](https://docs.python.org/zh-cn/3.14/library/contextlib.html) 在正常或异常退出时调用 close。该文档结论与本次描述符实测一致。最早的连接泄漏诊断测试早于本小节补充；正式扩充 SQL 异常路径的六项 RED 在补充后运行，再进行实现，交接保留这一先后区别。

每个技术失败、无效选项、回答或裁判失败均按固定 133 分母计零。完整实验终态不等于全部正常，二者分开报告。主要终点为 grounded_memory_v1 的 source10 全题准确率减 baseline，legacy 为次要。继续扩大标准保持净增至少 7 题、network cluster bootstrap 的 95% CI 下界大于 0、共同正常同向、两臂各至少 127 正常；重复 100000 次、seed=20260925。报告题型、网络、配对四格表、共同正常、成本、缺失 usage，以及完全相同实际 judge 输入和配置下的翻转。产品默认不自动推广。

## 必须先 RED 的用例及验收

- provider 构造前拒绝旧/partial/伪健康库、错误 core/profile/布尔开关、样本或分组重复/缺失、源库 hash 或冻结根目录漂移。
- 固定 133 题与两臂 266 检索、四组合 532 QA、1336/956 上界不变；source10 零 embedding；锚点低但全部检索健康仍放行 QA。
- 实际 native+Stub/Fake 或 localhost fixture 覆盖新核心身份、上下文重建、独立进程加载与源库不变；只用 mock 不能证明这些边界。
- 修改 context、来源、策略、数据库声明，或一起改 prompt 与 hash 后重新 seal，必须被实际输入重建拒绝。
- 正常原始 usage 搭配空 choices、null choice/message、拒答、长度截断、顶层副本矛盾时，已知费用不得消失；malformed JSON、缺 usage、未知 certainty 不得冒充已知零。
- started 与账本整数 ID/类型/上界/状态篡改必须拒绝；入口构造失败、进入 native 后缺回执、写盘/结算/汇总中断必须有可读的失败审计。
- 失败题计零、正常比例与终态完整率分开、主要终点和聚类 bootstrap 固定；不能复用旧题或旧答案填补 fresh 终态。

依次完成新增 RED、最小实现、针对性回归、合同审查、质量审查和独立入口复验。只有八库真实验收通过才启动 retrieve，只有检索验收通过才启动 QA。真实阶段结束后在独立进程 check 并补充中文报告、统一所有设计状态入口。
