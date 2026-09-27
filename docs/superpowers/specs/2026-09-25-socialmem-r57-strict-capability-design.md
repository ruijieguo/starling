<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.7 严格输出兼容性诊断设计

## 问题与目标

R5.6 的八库重建在首个 scope 停止：Mum 首次响应含非法嵌套字段，一次纠错后引用本批 c0–c7 之外的 c8。两次均 HTTP 200、正常 stop，原提示已有精确来源白名单。旧 core `4c5a7c39` 正确拒绝写入；当前不存在新增 133 题的健康 baseline。

本阶段只回答指定 DashScope endpoint、`qwen3.8-27b` 与现有原生 strict schema 是否兼容。沿用用户对自主诊断与 DashScope 请求的授权，最多 4 次 HTTP，无自动续跑。所有合同生成、请求、解析和能力分类由现有 C++ 完成；Python 仅编排、冻结、计账和审计。

## 方案比较与选择

1. 先运行现有原生严格能力探测（本阶段采用）。改动小，可先取得指定模式与schema组合的实测响应；服务端若明确拒绝该模型的strict模式，则避免先实现无法使用的provider profile。
2. 分离本地完整合同与提供商 wire schema，并按批次生成 clause_id enum。若 strict 能力成立但特定关键字被拒绝，再单独设计这一 C++ 改进；不在本轮静默移除关键字。
3. 保留 JSON Object，缩小生成目标与上下文暴露范围。若服务端明确拒绝指定模型的strict模式，则围绕原失败来源设计原生批次提示修正及固定小规模对照；泛化schema错误不能直接触发此判断。本轮不直接改提示、放宽合同或增加重试。

最新官方页面明确 JSON Object 不保证字段稳定；JSON Schema 支持列表列出 Max、Plus、Flash 系列，未列出 qwen3.8-27b。历史 qwen3.7-plus 曾拒绝 `uniqueItems`，不能外推到当前模型。官方快照为 `build/socialmem_20260925_r56_work/provider-structured-output-current.md`；Context7 本问题三次命令已用尽（无关返回及不支持 research 选项），随后取得阿里云官方网页快照。

## 固定输入与执行

新增独立入口 `scripts/run_socialmem_r57_strict_probe.py`，提供 `run/check`。固定引用 R5.6 expanded prepare，seal SHA-256 为 `4aca92fe8eca1615fd7fe65a66d7cf28048f4ac789aa676367acc5ac4bda1577`；先核验全部文件哈希，再从该 prepare/frozen 唯一加载原生模块与原配置。不加载 partial build、不操作数据库。

固定 core SHA-256 为 `4c5a7c39ae708a13d10065a0816a5c97a994929479cb0898f504c21e12b422f9`。模型、endpoint、8192 tokens、120000 ms、thinking=false 沿用 prepare 抽取配置；max_retries=0、json_object_output=false。不从 CLI 暴露模型、模式、重试或任意 schema 覆盖。

第一阶段调用一次原生 `probe_structured_output(ClaimAdmissionV1, JsonSchemaStrict)`，其内部执行固定正向和反指令两个 fixture。此schema不含`uniqueItems`，但仍含`minimum`等关键字；它不是最小模式探针。成功可证明该组合的协议fixture通过，失败仍须依据服务端原始错误区分模型模式拒绝与schema关键字拒绝。仅当原生 state 为 observed_conformant、两次 HTTP 均正常且 usage 完整，才调用同样包含两个 fixture 的 ClaimExtractionV2 探测。任一阶段失败立即在该原生调用结束后停止；最多 2+2 次、零 HTTP retry、零模型切换。原生调用内部遇到第一次失败仍会完成第二个 fixture，此行为保留并纳入预算。

## 证据与验收

输出目录必须不存在，创建后即封存输入身份、两种原生 schema 与哈希、配置、入口/测试副本及预算预约。每个合同调用前持久预约 2 次；异常且实际数量未知按 2 次扣账，明确 remote/token unknown；不能因异常将消费写零。每次回执立即保存，最后封存成功或失败终态。拒覆盖、拒自动恢复、check 零 provider。

check 核验固定 prepare 链、当前加载 core 身份和封存文件集；用 C++ `validate_capability_evidence_json` 重验原生状态，再从原始 HTTP 重算 request_count、finish、usage、known subtotal、缺失 usage、未知执行和逐预约结算。验收需显式 HTTP200/curl0/response_received/stop，不接受只有 FakeLLM 逻辑成功但没有 HTTP 的证据。不能单凭自报 summary、state、token 或重新计算 seal 通过审计。入口/test 副本与执行时 manifest 绑定，不要求历史运行永远等于后来修改的工作区。

成功仅表示固定模型/endpoint/schema 的四个协议 fixture 通过，不代表动态批次 enum 支持、不代表自然语言语义召回、建库可靠性或 QA 提分。HTTP400 缺失 usage 记 unknown；请求被拒绝不推定计费零。原生返回 unknown 时保留原分类，另报告服务端原始错误，不能擅自改成 unsupported。现有C++对含格式名和unsupported关键词的HTTP400/422会分类unsupported；这也可能是特定schema拒绝，不能仅凭该state宣称整个模型不支持strict。模式级结论要求服务端明确指向指定模型和该模式，泛化错误继续保留wire兼容性未定。

## 测试与后续门槛

先写测试并记录 RED，再实现：固定身份漂移在 provider 构造前拒绝；输出覆盖拒绝；admission 不通过时只两次且不调用 extraction；成功路径四次；usage 缺失保留 unknown；异常保守结算；篡改 raw completion、summary、schema、config 或 ledger 后即使重 seal 也拒绝。用冻结 C++ 与本地 HTTP fixture 验证真实 response_format、max_retries=0、正反两个 fixture 和原生分类。

合同/质量审查通过后执行一次真实探测，封存并独立只读复验，随后选择有证据支持的 C++ 修正方案。全量重建仍需新核心的失败来源验收和独立中文设计，不从本次 fixture 直接跳转到八库或 QA。
