# SocialMemBench SourceTurn 输入与三通道回执实现报告

日期：2026-09-20。范围：Starling 当前工作区的离线输入接线、C++ native 回执和本地回归。未发起新的 DashScope 请求，未重写历史评测目录。

## 实现

1. `scripts/eval_ladder.py` 按 speaker 显式分组，将允许的 SourceTurn 字段交给 C++ renderer；`preserve_invalid_time` 只作为配置透传。
2. `EpisodicLlmResult` 在 C++ 保存 prompt、prompt hash 和原始 `LLMResponse`；`episodic_extraction_receipt` 与 `memory_remember_bundle_receipt` 统一序列化三通道证据。
3. `scripts/run_socialmem_baseline.py` 写入独立 `extraction.receipts.json`，校验 holder 唯一性和三个通道完整性。
4. claim extraction receipt 补充根级 prompt/hash，并合并 provider 的原始 HTTP/token/延迟证据；既有 extraction/admission 字段保持兼容。

对冻结的历史 `socialmem_20260919_structured_eval_dialogue_v3` 运行离线覆盖分析，得到 423 个来源话轮、36 个预期 holder、31 个已抽取 holder、14 条结构化声明、7 个 scope 中 6 个完整结构化 scope；该结果是修复前比较基线，不是本阶段的新 QA 结果。产物为 [coverage-analysis.json](../../build/socialmem_20260920_source_turn_receipt/coverage-analysis.json)。

## RED/GREEN 证据

新增测试先在实现前失败：Python 由于没有 SourceTurn 调用、bundle binding 和 scope 归档函数而失败；C++ 因 `EpisodicLlmResult` 缺少回执字段及 bundle 接口而无法编译。实现后以下专项全部通过：

- Python：SourceTurn/receipt、来源管线、真实抽取离线、claim channel boundary 等 73 项通过。
- C++：SourceTurnReceipt、ClaimContract、StructuredMemoryClosure、EpisodicExtractor、RememberPhases 共 81 项通过。
- 本地 HTTP：既有 OpenAI/structured/capability/HTTP 30 项在允许 loopback 后全部通过。

新构建和当前虚拟环境 `_core` 的 SHA-256 均为：

`60dafea16e0670212e1080c2a9bc2b80274b6b01e88f9ee6882739facb0b9ddc`

完整 C++ 执行了 1208 项：1185 通过、22 跳过、1 项因沙箱不能创建 loopback listener 失败；同一 HTTP 范围在允许本地回环后为 30/30 通过。全量 Python 收集 1871 项，1796 通过、23 跳过、52 失败；失败原因主要是工作区原有 Python facade 与当前 native `RememberOutcome` 字段漂移（`RememberResult` 未接收 `failure_category`）、冻结模块导入污染和 Python loopback 权限。新增 SourceTurn/receipt 相关测试和 SocialMemBench 评测编排专项没有失败。

## 评测结论

本阶段证明了输入元数据和抽取失败证据可以在 C++/binding/评测归档之间闭环，不能证明 QA/F1 提升，也没有建立新的真实 baseline。历史 hybrid_dialogue 的 17/57 仍按原报告保留，且仍受 6/7 scope 结构化覆盖限制。下一阶段必须在新接线下重新运行完整 7/7 scope、36/36 holder baseline，再将谓词扩展、admission 规则作为独立变量评估。

相关文件：

- 设计：[SourceTurn 与三通道回执设计](../superpowers/specs/2026-09-20-socialmem-source-turn-receipt-design.md)
- 计划：[SourceTurn 与三通道回执实施计划](../superpowers/plans/2026-09-20-socialmem-source-turn-receipt.md)
- 诊断：[结构化覆盖诊断](2026-09-20-socialmem-structured-coverage-diagnosis.md)
