<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench R3.4 结构化抽取协议有限重试实施计划

> 顺序固定：中文设计 → RED 测试 → C++ 实现 → 回归 → 独立评测；Python 只做 binding 和配置透传。

## 任务 1：文档与配置边界

- [x] 写入 [R3.4 中文设计](../specs/2026-09-21-socialmem-r34-protocol-retry-design.md)。
- [x] 在系统设计、claim contract、Neocortex、Cognizer、Retrieval 入口追加 R3.4 状态，保持生产默认说明。
- [x] 为 R3.4 建立独立评测身份、配置哈希和请求预算记录，不覆盖 R3.3 产物。

## 任务 2：C++ RED 测试

- [x] 为 `ValidationPolicy.claim_protocol_retry_budget` 增加默认值、上限和非法值测试。
- [x] 用 FakeLLM 模拟重复 JSON key 首轮失败、第二轮合法响应，断言第二次请求和最终成功。
- [x] 用目录外谓词首轮 schema 失败、第二轮合法谓词，断言第二次请求和最终成功。
- [x] 断言两次协议失败后停止、scope 语义拒绝不重试、attempt prompt/hash/raw response 全量回执。
- [x] 先运行专项测试形成 RED 证据，再实现（C++ 编译失败、Python 4 项失败，见 `build/socialmem_20260921_r34_red_{cpp,python}.log`）。

## 任务 3：C++ 最小实现

- [x] 在 `ValidationPolicy` 和 `ExtractionLlmAttempt` 增加原生字段，并绑定到 Python。
- [x] 增加 C++ retry prompt 构造函数；不带入模型原文，不做 JSON 修补或谓词改写。
- [x] 在 `Extractor::extract_llm` 的结构化路径中只对 envelope/schema 错误执行有界重试。
- [x] 更新 C++ receipt，使每个 attempt 使用实际 prompt/hash，同时保持首轮顶层字段兼容。

## 任务 4：Python binding 与门禁测试

- [x] `ExtractionConfig` 增加 `claim_protocol_retry_budget`，只映射到原生 policy。
- [x] R3.4 runner 固定预算为 1；旧 arms 和生产默认保持 0。
- [x] 补充 binding、配置、请求上限和结构化 scope 归档测试，确认 Python 没有重试或解析逻辑。

## 任务 5：回归与独立评测

- [x] 构建 C++ 专项并运行相关 Python pytest；运行完整 CTest，单列既有 loopback listener 环境失败。专项 C++ 为 4/4，R3.4 Python 相关门禁为 53/53；完整 CTest 归档为 1207 通过、22 跳过、1 个既有 loopback listener 失败。
- [x] 对固定离线夹具做零请求协议回放，核验默认 0 与 R3.4 1 的尝试计数和 receipt hash。`ClaimContract.ProtocolRetry*` 4/4 通过，覆盖零预算、一次重试、停止条件以及每次 prompt/hash 原样回执。
- [x] 通过所有门禁后，在独立网络环境运行 57 题；不复用或覆盖 R3.3 目录。R3.4 目录为 `build/socialmem_20260921_structured_eval_hybrid_protocol_retry_r34_protocol_retry`。
- [x] 分析 scope/holder 完成率、失败类别、请求实际数、全题准确率、成功子集准确率和共同正常题 bootstrap；配对诊断见 `build/socialmem_20260921_r34_pairwise_diagnostics.json`。

## 任务 6：报告与晋升判断

- [x] 新建中文 R3.4 评测报告，明确技术完成率与 QA 分母。
- [ ] 同步五份现行设计入口和检索边界，保留历史 R3.3 结论。
- [x] 只有预注册配对门槛满足才讨论晋升；本轮未满足，保持生产默认并记录下一项短板。
