<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench SourceTurn 输入与三通道抽取回执设计

## 背景与目标

当前 SocialMemBench 的真实抽取入口在按说话人分组后，把每组话轮重新拼成普通文本。这个转换丢失了 `session_id`、`turn_id`、`turn_index` 和 `observed_at`，使 C++ 结构化声明无法把声明绑定回原始话轮。现有 C++ 已经具备 SourceTurn 规范化能力，也已经能为 belief 抽取保留 extraction/admission 回执，但评测编排没有使用这些能力，且 general-fact 与 episodic 回执没有统一归档。

本阶段只修复评测闭环的输入与可观测性，目标是：

1. 每个 holder 的真实抽取 payload 都由 C++ `claim_source_turn_payload` 生成，并保留来源话轮元数据。
2. 每个 holder 的三个抽取通道都能从 C++ 导出完整、可重放的回执。
3. scope 归档单独保存每个 holder 的回执，能区分 extraction、admission、episodic 三类结果。
4. 不改变题目、参考答案、裁判协议、历史归档或 Python 中的谓词语义。

## 设计原则

- C++ 是 SourceTurn、校验、回执字段和通道语义的唯一事实来源。
- Python 只做数据集字段映射、binding 调用、评测编排和 JSON 归档。
- holder 归属显式传入 C++，不会从 payload 中自动猜测或跨 holder 合并。
- 原始模型响应、prompt 哈希、错误、token/延迟和 admission 决策保留在回执中；回执不参与评分。
- 既有 legacy 路径保持兼容；新回执只附加在真实三相抽取路径上。

## C++ 接口

### SourceTurn payload

`claim_source_turn_payload(turns_json, preserve_invalid_time)` 接受只含以下字段的数组：

`speaker`、`text`、`session_id`、`turn_id`、`turn_index`、`observed_at`。

函数负责字段白名单、UTF-8、时间和索引校验，并渲染 `@starling/source-turn-v1`（非法时间时为 tolerant v2）行。`claim_source_units` 再从 payload 生成带 `clause_id`、字节区间、payload 哈希及 SourceTurn 元数据的来源单元。Python 不复制这些规则。

### 三通道 bundle 回执

新增 `memory_remember_bundle_receipt(const RememberLlmBundle&) -> string`。返回 JSON：

```json
{
  "schema_version": 1,
  "channels": {
    "belief": {"...": "claim_extraction_receipt"},
    "general_fact": {"...": "claim_extraction_receipt"},
    "episodic": {
      "prompt": "...",
      "prompt_input_hash": "sha256...",
      "response": {
        "raw_xml": "...",
        "ok": true,
        "error": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_ms": 0
      },
      "ok": true,
      "event_count": 0
    }
  }
}
```

belief 与 general-fact 复用 C++ `claim_extraction_receipt`，因而完整保留每次 extraction attempt、原始响应、解析错误、candidate、admission prompt/响应、admission 拒绝计数和 retained 结果。episodic 新增同等层级的 prompt/响应信息和解析后的事件数量；episodic 没有 admission 阶段，因此显式标记为独立通道而不伪造 admission 字段。

## 数据流

1. `run_socialmem_baseline.py` 先把数据集话轮映射为白名单 SourceTurn JSON，用 `retain_source_turns` 保存原始来源。
2. `eval_ladder.make_real_extract_fn` 按 speaker 分组，仍以该 speaker 为 holder；每组调用 C++ SourceTurn renderer 得到 payload。
3. C++ `memory_remember_prepare -> memory_remember_extract_all -> memory_remember_bundle_receipt -> memory_remember_commit_all` 完成抽取、回执和持久化。
4. Python 将 holder、结果和 native bundle 回执写入 `extraction.completed.json`，并将所有 holder 回执复制到独立的 `extraction.receipts.json`。
5. 覆盖分析器读取这些归档，分别统计 payload 元数据覆盖率、belief/general-fact admission 结果和 episodic 事件结果；这些统计不直接充当 QA/F1 分数。

## 错误与兼容性

- SourceTurn 字段或时间非法时，C++ 在网络调用前抛出；评测题记录为 ingestion/extraction 技术失败，不消耗模型请求。
- 某一通道响应失败时，回执保留失败响应和错误，其他通道照常归档；现有 commit 失败语义不变。
- scope 已存在的历史归档不重写；新字段只写入本阶段新生成的 scope 目录。
- 不在 Python 重建 predicate、admission 或 episodic 解析逻辑。

## 验证标准

- C++：SourceTurn payload 元数据、bundle 三通道回执和 episodic 原始响应测试先 RED 后 GREEN。
- Python：真实抽取入口的 payload 必须含 `session_id`、`turn_id`、`turn_index`、`observed_at`；scope 归档必须覆盖每个 holder 且包含三个通道。
- 运行相关 C++/Python 回归和本地 HTTP 回归；本阶段不追加 DashScope 请求。
