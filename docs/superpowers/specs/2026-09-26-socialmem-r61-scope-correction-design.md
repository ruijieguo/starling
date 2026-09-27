<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

# SocialMemBench R6.1：目标批次来源越界的有界纠错

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

## 目标和授权边界

这是用户已授权的建库故障修复和自主评测迭代。R6.0 第四库 Lionel、Miriam 出现批外引用且未触发纠错，详见 [诊断报告](../../eval/2026-09-26-socialmem-r60-build-diagnosis.md)。本阶段先完成 C++ 有界纠错及完整 holder 探测，不将开发探测称为 baseline。

## 方案与取舍

采用现有协议预算内的重新生成：仅 `claim_batch_target_units=true` 且启用分批时，把 `batch_scope_failure` 与 schema/envelope 错误共享 `claim_protocol_retry_budget`。当前配置为 1，因此每批最多两次抽取及一次成功候选 admission，原生请求上界不增加。预算耗尽仍失败并保留全部费用。

不采用删除越界行、修正 clause id 或放宽来源范围：这些做法会改变证据且掩盖遗漏。不增加无限重试或新的 Python 抽取规则。暂不缩减完整上下文，避免影响跨轮指代且混淆此次机制验证。

## C++ 合同

在 `src/extractor/extractor.cpp` 内提取私有的可纠错错误判断，由真实抽取和持久化完整性回放共用。false/未分批路径对批外引用仍立即失败。schema/envelope 行为不变，HTTP、截断、来源结构和 admission 错误不增加重试。

首次提示、profile `target_units_statement_first_v1`、参考示例和 parser 均不改变。现有纠错提示已带错误路径、目标索引和不得重编号规则；先验证原提示下的纠错机制。新候选以独立 core SHA 和源码快照区分，不重标 R6.0 产物。纠错前错误行不进入 admission、不写语义声明；成功纠错必须再次经过完整解析和 admission。后批最终失败时整个 holder belief 不写入，所有调用费用仍记账。通道隔离保持。

## 验收测试（实现前运行 RED）

1. 首批批外引用→合法新响应→admission→后续批完成：原生完整性回放通过，原错误回执保留，仅新响应写入，费用含失败请求。
2. 先成功后越界→再次越界：恰好一次纠错，无后续批请求，无该 holder belief 写入，费用全部保留。
3. schema→越界和越界→schema：共享一次额度，不能分别领取一次。
4. 零预算和 false 模式保持立即失败；HTTP/截断/admission 仍使用已有严格失败行为。
5. 篡改纠错提示、目标列表、预算或失败回执不能通过原生持久化完整性验证。
6. 补齐 R6.0 的 evidence 内部顺序、还原旧顺序后整段 SHA 比较，以及错层/两层重复字段拒绝的集成证据。

## 真实探测与晋级

固定使用已封存 R6.0 第四库的 Lionel、Miriam 完整 payload，各运行旧 core 与候选 core 一次，交错顺序固定为 Lionel 旧→新、Miriam 新→旧。每个任务执行完整 holder 的所有 belief 批次、admission、commit，不仅重发有利批次；不复用旧回答。模型为 DashScope qwen3.8-27b，配置继承固定 8192、thinking=false、HTTP retry=0、每批协议预算 1。候选与旧 core 使用独立进程和冻结 Python runtime；不覆盖常规 build/venv。

运行器只编排原生调用和费用统计；需要 prepare/run/check 三阶段、输入/源码/core/原始响应/账本摘要绑定、失败封存与原生回放。候选两任务均完整健康且各有至少一个 admitted claim 才能推进新八库设计；空结果单独报告，不能作为能力恢复。对照失败仍保留并继续既定候选任务；传输/账本不确定时停止。四任务最大额度按原生 plan 累加，非预算金额。独立完整性检查通过不代表 QA 提升。

R6.0 的旧探测资格不作为 R6.1 准入证据。新八库和后续评测入口在通过此探测后单独形成中文执行设计与失败测试，不能放宽 R5.9/R6.0 的历史 SHA 或把部分建库拼成 baseline。

## 首轮外部故障与一次独立重启（执行后记录）

第一轮四任务在首个 Lionel 旧核心请求遇到 curl 52 / HTTP 0 空响应，execution_certainty=unknown，已封存为 incomplete。只观察到一次本地原生 HTTP 尝试，不能确认远端生成、不能把缺失 usage 当成零消费。候选未执行，本轮不提供修复效果证据。原单轮30额度保持。独立检查后先做不带密钥的端点连通性检查；确认端点可达时允许一个全新目录的完整四任务重启，总计最多两轮、60额度单位，绝不续跑或覆盖首轮。第二轮若再次传输失败则停止真实重启，保留已知与未知消费分别报告。这是外部故障后的明确执行调整，不追认为原预注册内容。
