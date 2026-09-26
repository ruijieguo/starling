<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.9：目标索引核心的统一八库 baseline

## 前置证据与目标

R5.8 的同核心配对已达到预先规定的技术门槛：三个 B 任务全部通过，六任务共 37 次真实 HTTP、595505 tokens，无未知消费。run seal 为 `30d00e455388d6002b692080e0e7b60b13f56d76790245f1b3f8c57971b5735d`，prepare seal 为 `cf95c3412a32f22542f72b5b81d7d4d81b04377d4338a75891f8439dc1be73e0`。正式 check、独立 HTTP/账本/数据库审计均通过。A 为 2/3 技术通过，B 为 3/3；两个来源及少量重复不能证明总体可靠性。

语义覆盖仍有风险：Kwame B 保留 12 条/9 个来源，A 为 15 条/11 个来源；B 未保留 A 的 c4 知识行和 c16 情绪行，部分新增候选被 admission 拒收。因此本阶段只据技术门槛启动完整开发评测，不宣称 B 语义更优，也不更改产品默认配置。

目标是用同一候选核心与固定配置重新建立 8 个库，再承接固定新增 133 题的检索和 fresh QA。既有用户自主迭代及 DashScope 授权有效，按中文设计、RED、实现、回归、合同/质量审查、真实执行顺序推进，不重复请求批准。先完成八库入口；QA 接入可独立实施，但必须等待 8/8 健康库才发请求。

## 固定身份及隔离

候选核心固定为 `ead8046e4a28d257f3429d865523c1af1f6275fd0cb1ba98d8fa8023894d6fef`。抽取配置沿用 R5.6，唯一能力变化是严格布尔 `claim_batch_target_units=true`；`claim_batch_size=8`、一次原生协议纠错、8192 输出 tokens、thinking=false、temperature=0、HTTP retry=0、模型 `qwen3.8-27b` 保持。embedding、lifecycle、检索及回答配置沿用预注册开发实验，不以本次输出选择题目或预算。

固定 cohort 继续来自 `build/socialmem_20260925_r55_expanded/prepare`，seal `66b13d7e22b0794903467d9ea89f21b91379118d43866b4504b49fd9bd0178d0`：新增开发 133 题、6 个网络、8 个 scopes；旧 57 题和保留集不进入本次分母。逐文件核验历史封印，再从 corpus/split 重建 sample/groups/manifest。历史旧核心只作为历史身份保存，不能与候选 core 常量混用。

R5.8 成功资格由固定 run/prepare 封印、三个 B 的完整原生终态，以及独立 check 的归档证据支持。每次资格验证在独立子进程执行正式 R5.8 check，归档命令、退出码、输出摘要/哈希及检查程序/helpers 源码指纹；既有日志可作附加证据，不能只信日志代替复核。资格检查与 R5.9 新 runtime 加载使用独立进程：同一进程不能先加载 R5.8 prepare/frozen，再加载另一目录的同 SHA `.so`。新阶段统一从自身 prepare/frozen 导入 core/runtime；build/evaluate 不切换为各阶段复制目录加载。

## 实现边界与复用

新增独立入口 `scripts/run_socialmem_r59_expanded.py` 及测试，不改旧 R5.6/R5.8 入口常量、不覆盖历史产物，不通过给旧模块全局变量赋值来伪装新实验。

可直接复用已验证且没有旧实验身份副作用的函数：历史封印清点、固定 cohort 重建、来源保留、原生 plan、scope 构建 worker、稳定快照、原始 HTTP 统计、数据库证明及 ledger 基础设施。新的代码负责固定身份、配置、阶段依赖和健康门槛；不复制 C++ prompt、来源分批、语义解析或提交规则。若旧阶段函数闭包绑定历史 SHA/递归 check，则新入口显式编排，不调用该旧阶段函数并临时篡改其 globals。

只读 check 使用当前审计程序及冻结核心重放，报告实际检查程序/helpers 的源码指纹，并保留本阶段已审查版本的完整源码；不要求所有历史 Python checker 从 frozen 目录重新导入。核心/runtime 的唯一冻结路径要求仍严格执行。真实 run 前后核验 workspace 编排源码与冻结副本一致。冻结实际 helpers、baseline、运行依赖、源码、验证证据与历史输入身份；不宣称任意后续 checker 版本产生逐字相同的结论。源码漂移、加载路径漂移和核心不符均在 provider 前拒绝。

## 八库阶段合同

提供 prepare/build/check，已有输出目录拒绝，不续跑。prepare/check 不调用 provider。prepare 由新核心重新生成全部 holder 的 SourceTurn payload 与分批 plan，逐条要求 profile 为 `target_units_v1`；两处 general_fact 开关清零由现有 C++ 保证。预期 65 holders、1322 units、197 batches、belief 上界 591、三通道抽取上界 851，须重新计算验证，不能直接抄历史计数。

build 固定 scopes 次序串行，每个 scope 使用新库，先持久化预约与开始记录，再进入原生构建；第一处不健康即停止余下 scopes。总账本上限沿用 12000 请求，抽取逐 scope 上界来自新原生 plan。保守扣账、已观测 chat 请求数和 embedding 原生请求数分别报告：上界扣账不是实际请求数。现有 binding 不提供完整 embedding token/HTTP 明细时明确未知，不把 chat tokens 说成全阶段完整用量。

每个健康 scope 必须满足完整 holder/来源清单、全部 belief 批次完成、原生 schema/目标/profile/原始 payload 一致、独立通道回执有效、实际声明与 retained 对应、SourceTurn/来源证据一致及向量数/维度正确。空合法来源结果不等于语义全召回；不能把每个 holder 必须有 claim 当成新增隐性筛选条件。

成功或失败均保存回执和 SQLite 稳定 backup；分批失败只能保证该 holder 的 belief 语义写入为零，不抹去独立 general_fact/episodic 的合法写入。检查 actual persisted predicate/object/holder/modality/polarity/source 逻辑字段，不只检查 semantic JSON。belief 原始 HTTP 与顶层、嵌套 structured_output 的费用/模式/schema 信息须同源；可复用 R5.8 `raw_cost`。其他通道沿原合同审计，不能把旧通道响应当作 claim JSON Object 检查。

对 belief 回执，以冻结 C++ + 每 holder 独立 Fake 响应映射回放实际响应，核对 prompt、目标、错误、候选、拒收、retained；费用始终来自真实 HTTP，不要求 Fake 产生真实 usage。原生抽取回放与持久化证据可以分层比较，不能借助 Python 再实现解析器；重放结果与实际库使用稳定逻辑字段及已经绑定的 source 身份比较，不按随机 UUID 判差异。

多 holder 的持久化验证保留同一 scope 的共享状态：按当前 C++ 实际顺序先登记全部来源，再逐 holder 执行 prepare → extract_all → commit_all，最后调用冻结的原生 lifecycle。每 holder 的 Fake 响应映射独立，不等于每 holder 在隔离数据库中提交。合法零 belief、跨调用幂等和原生去重遵循 C++ 结果，不能要求 retained 数、commit ID 数与物理行数简单相等。

本地八库 fixture 已展示原生 sleep 会根据四个 holder 的合法 general_fact 产生 `holder=__common_ground__`、`provenance=consolidation_abstract` 的第五条派生声明。它是原生 lifecycle 行为，不得新增“全部 DB holder 必须在输入 holder 清单”或“全部 DB ID 必须在原始 commit IDs”硬门槛。应通过共享库原生回放对整个数据库的逻辑行多重集作双向比较，并核验 derived_from 等引用关系。随机 source/statement UUID 仅在对应的来源或稳定逻辑身份已验证后归一；派生 owner、条数、语义和引用必须由原生实际重现，不能在 Python 生成、折叠或补齐。任意多写、漏写、未知 holder 或派生引用篡改仍由全库差集和关系核验拒绝。允许变动的运行时间和随机批次字段须显式列出，confidence、规范 object hash、原生语义时间、治理状态和来源证明不能笼统排除。

另一个已由跨秒 fixture 与代码共同确认的例外是 legacy 默认采集时钟：`src/extractor/json_parser.cpp` 当前无条件以 `now_iso8601_utc()` 生成 legacy `observed_at`，原生持久化还将它写入对应来源 span；现有 binding 没有该时钟的固定入口。本阶段不为离线重放修改冻结核心。真实 scope 原生调用前后分别持久化 UTC 窗口；仅在原生 legacy retained 及其来源已核对、行 `observed_at` 与该行所有对应 legacy span 的时间一致、且落入真实调用窗口时，才可在逻辑比较中把该默认时钟位置替换为明确标记。回放侧须独立满足其自身窗口。原始数据库/回执保留实际时间，不改写证据；缺窗口、超窗或行/span 不一致均不得通过健康验收。

该窗口仅证明默认运行时钟的可审计合理性，不宣称逐秒重现原运行时间。belief 的 observed_at、source created_at/source_time、event_time、SourceTurn 的 observed_at/raw_observed_at/time_status 以及任何原生语义时间仍严格按冻结来源和配置检查。不能以 NULL semantic 一项就将任意 legacy/派生行的全部时间排除；归一范围必须绑定原生确实生成的默认字段。源 UUID 与默认时钟归一均属于证据比较，不在 Python 重建抽取或派生语义。

默认时钟资格也不能仅由 predicate、object、modality、polarity 四字段相同判定。原生 episodic 与 general_fact 可以合法写出语义字段相同而来源类别、语义时间不同的两行；应由原生回放的通道来源和持久化来源 span 等证据区分。episodic 的时间必须严格比较，general_fact 的合法 OCCURRED 仍可具有运行时默认时钟。不能根据“当前值恰好落在窗口内”倒推来源类别，不能依赖可选的 episodic_events 扩展行来建立必要证明。新增同四字段共存用例应通过，事件时间篡改仍须拒绝。

逐条预约绑定实际 SQLite 行，包含整数 ID、scope、stage、上界和结算状态。初始化、提交、快照、分析、写盘及结算中断要能区分有效终态、部分证据、未知消费和未执行 scope；缺回执/不可读账本不能推断零消费。不完整阶段不得产生分数或进入 QA，重新 seal 自报 summary 不得绕过原始证据复算。

scope 费用完整性还必须与冻结输入的预期 holder 回执清单绑定。进入原生后缺少任一 holder 回执，即使剩余响应均有合法 usage，也只能给出可见请求与 token 小计；完整总量为空，缺失部分的本地请求计数及远端执行均保持未知，不能因数据库健康检查已经拒绝而忽略费用层的误报。未进入原生且有明确未调用证据的情况仍可记录已知零。健康与费用完整性分别判断，失败 scope 也须保留准确的已知/未知边界。

## 评测接入及结论边界

8/8 技术健康后才接入 R5.6 已预注册的固定 133 题：266 个检索终态、532 个 fresh QA 终态。两检索臂精确保持 `baseline=evidence_profile_v6 + hybrid + k10` 与 `source10=evidence_profile_v9 + sources + k10`；回答政策、主要终点、固定分母及网络分组分析均保持。8/8 库只放行 retrieve，另须 266/266 检索健康且 context/ledger 审计通过才允许发 answer/judge 请求。检索请求上界 1336、answer/judge 上界 956 沿原生/现有任务重建确认。新增评测入口另做身份适配和对应 RED，不把旧 R5.6 的冻结核心测试当成新阶段验收。

R5.8 A/B 抽取探测与 R5.9 的 v6 hybrid10/v9 sources10 QA 对照是不同实验。新八库均使用目标索引能力，因此其内部检索臂差异不能归因于抽取 A/B；R5.6 八库未健康也没有可比较的 133 题旧分数。首次完成的新 133 题结果就是该 cohort 的健康 baseline，此后才做同口径迭代。

## 必须先失败的用例

- 固定历史/成功 probe seal、core、严格 true 开关及 profile 漂移，在 provider 前拒绝；不能载入另一冻结根目录或复用旧健康库。
- 新原生全 cohort 规划与计数；配置到 C++ 薄映射；原始 SourceTurn 字节与元数据不变。
- 真实 native + Fake/本机 HTTP/Stub 向量的非空持久化与完整 scope；后批越界/截断/缺 usage/准入失败停止及 belief 零写入。
- 嵌套费用副本、actual predicate/object/source 时间和来源证明篡改、started 预约 ID/类型/上界篡改，即使重新 seal 也拒绝。
- 阶段初始化/写盘/快照/分析/结算异常后可只读审计；进入 native 后缺回执保持 unknown，入口异常已知未调用可记零。
- 共享原生 sleep 合法生成 common-ground 派生行时通过；额外插入 legacy/派生行、改变派生来源引用、删除 retained 的实际结果或伪造逻辑列均拒绝；保留原生去重，不用条数强等式替代证明。
- legacy 默认 observed_at 在不同真实秒回放时可在独立调用窗口内比较；超出窗口、行/span 时间不一致、缺调用窗口或篡改 belief/source/event 时间仍拒绝。
- 八库不全、健康自报造假或题目/任务分母更改不能进入评测，不生成新分数。
