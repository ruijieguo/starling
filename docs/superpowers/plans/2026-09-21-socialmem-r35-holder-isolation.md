<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench R3.5 Holder 级故障隔离实施计划

> 顺序固定：中文设计 → RED 测试 → C++ 实现 → binding/评测回归 → 离线回放 → 独立真实评测。Python 只做 binding、字段映射和归档。

## 任务 1：设计文档同步

- [x] 写入 [R3.5 中文设计](../specs/2026-09-21-socialmem-r35-holder-isolation-design.md)。
- [x] 在 `docs/design/system_design.md`、`docs/design/claim_contract_sync.md`、`docs/design/subsystems_design/07_neocortex.md`、`docs/design/subsystems_design/08_cognizer.md`、`docs/design/subsystems_design/13_retrieval.md` 追加 R3.5 边界、partial scope 统计和生产默认说明。
- [x] 写入 R3.5 独立评测 arm、目录身份和预注册统计，不覆盖 R3.4。

## 任务 2：C++ RED 测试

- [x] 为 `ParseError.field_path` 和 receipt 的 `errors[].field_path` 增加缺失字段、目录外谓词、重复 key 的断言。
- [x] 为带错误摘要的 retry prompt 增加“包含 kind/path、不包含原始响应”的断言。
- [x] 为 `remember_holders` 增加两个 holder 夹具：首个 holder 协议失败，第二个 holder 成功；断言两者均有结果且第二个成功提交。
- [x] 为失败 holder 的三通道 receipt、失败 attempt 原文/hash、prepare/commit failure 阶段增加回放断言。
- [x] 先运行新增专项测试并保存 RED 日志；确认失败原因来自缺失接口，而不是测试错误。

## 任务 3：C++ 最小实现

- [x] 扩展 `ParseError`、claim parser 错误路径推导和 `errors_json`；保持既有初始化与历史 receipt 字段兼容。
- [x] 实现原生字段级 retry prompt，并在 `Extractor::extract_llm` 中把当前 attempt 的错误摘要传入下一次 prompt。
- [x] 在 `include/starling/memory/memory_ops.hpp` / `src/memory/memory_ops.cpp` 增加 holder DTO 和批量管线；每 holder 独立 prepare、extract、commit，捕获并记录失败后继续。
- [x] 仅由 C++ 生成 holder receipt、failure category、failure detail 和 partial 状态；不把解析或重试逻辑放入 Python。

## 任务 4：Python binding 与 runner 门禁

- [x] 绑定 holder DTO/批量函数，Python 只把 holder/payload 列表映射为 native 对象并归档结果。
- [x] 新增 R3.5 arm：固定 qwen3.8-27b、57 题、1200 请求预算、retry=1；旧 arm/default 保持原值。
- [x] 将 `eval_ladder.py` 的逐 holder 循环改为一次 native 批量调用；保留稳定 holder 顺序和 source payload 生成。
- [x] 更新 scope gate 允许带完整 holder 结果的 partial snapshot，并强制输出 `holder_failures`、`scope_state` 和分层 QA 分母。
- [x] 添加 Python RED 门禁，验证无 Python 重试、无谓词目录、无 JSON 清洗和无伪造成功 holder。

## 任务 5：回归与独立评测

- [ ] C++ 专项、相关 Python pytest、完整 CTest；记录既有 loopback listener 环境失败。
- [x] 对固定 FakeLLM/SQLite 夹具做零请求批量回放，验证第二个 holder 仍写入、失败 attempt 可重放、frozen snapshot 完整。
- [x] 在独立 R3.5 目录执行 57 题真实评测，保存请求账本、每 holder receipt、partial scope 与逐题回执。
- [x] 生成配对诊断、网络 bootstrap 和分层 QA 统计，校验请求预算与目录哈希。

## 任务 6：报告与晋升判断

- [x] 新建中文 R3.5 评测报告，明确完整/partial holder 分母、技术失败和 QA 分数。
- [x] 复核五份现行设计入口与报告链接，确认生产默认仍为 `semantic_claim_contract=false`、`claim_protocol_retry_budget=0`。
- [x] 仅在预注册门槛全部满足时讨论晋升；否则记录下一项能力短板并关闭 R3.5 arm。
