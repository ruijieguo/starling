<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.1 同库 v6/v7 检索对照设计

日期：2026-09-25

状态：已批准执行的诊断设计。R5.1 只生成冻结检索上下文和统计证据，不改变生产默认策略，不重新抽取来源，不发送回答或裁判请求。

## 1. 问题与目标

R5.0 在修复来源身份后重新抽取了 qwen3.8-27B 语料，并启用 `evidence_profile_v7`。R4.9 与 R5.0 的端到端分数差异同时混入了抽取产物、engram 身份、来源集合和排序策略变化，不能判断 v7 检索本身是否改善 QA。

R5.1 的目标是把变量收窄到检索策略：在 R5.0 retry4 的同一份冻结数据库、同一题目、同一观察者范围和同一配置上，分别生成 v6 与 v7 的上下文包，并对每题记录来源集合、渲染块、C++ 选择轨迹和诊断计数。R5.1 不回答质量问题；它为下一步共享回答/裁判双臂评测提供可审计输入。

## 2. 不变量与范围

1. 输入只能是 `build/socialmem_20260925_r50_semantic_real_retry4`，必须验证 `config.json`、`identity.json`、`scope-manifest.json`、`summary.json`、7 个 `runs/<group_id>/frozen.db` 数据库和冻结核心哈希。`source-databases/` 下的复用副本不作为本轮 QA 的来源。
2. 两臂共享题目、数据库快照、`query_time`、`k`、上下文预算、holder 列表、embedding 模型和请求协议；唯一策略变量是 `source_strategy`：v6 或 v7。
3. 每个题目使用临时数据库副本；脚本不得写回 retry4 目录，也不得改写 R5.0 评测结果。
4. Python 只负责加载冻结模块、注入 C++ `ObserverQuery`、写入回执和计算统计；source 回链、语义排序、事件邻域、权限和预算继续由 C++ 执行。
5. R5.1 不执行 qwen3.8-27B answer/judge 请求，不产生新的 QA 分数。任何后续分数必须引用本轮冻结上下文的哈希。
6. 任一身份、快照、请求、终态或文件哈希校验失败，脚本必须在模型调用前失败；不得静默降级到旧库或 Stub embedding。

## 3. 数据流

```text
retry4 identity/config/scope DB
        │
        ├─ v6 ObserverQuery(source_strategy=evidence_profile_v6)
        │       └─ C++ semantic/topic/holder selection → context + trace
        │
        └─ v7 ObserverQuery(source_strategy=evidence_profile_v7)
                └─ C++ semantic/event/topic/holder selection → context + trace
                         │
                         └─ R5.1 per-item receipt + seal + comparison.json
```

retry4 的 v7 回答回执已封存并且明确绑定 `runs/<group_id>/frozen.db`；R5.1 复用该回执作为 v7 arm，只重新在同一 `runs` 快照上生成 v6，避免重复发送相同 v7 embedding 请求。每个 arm 的回执至少包含 `item_id`、`group_id`、输入数据库 SHA-256、核心 SHA-256、embedding 模型、请求数、`source_refs`、`block` SHA-256、`selection_trace`、`diagnostics` 和终态状态。比较文件按规范化 JSON 计算 source/block 改变，并汇总 semantic/event/relevance lane 与拒绝原因。

## 4. 统计与解释边界

R5.1 报告 57 题的 source 集合改变数、block 改变数、三类选择车道计数、每题上下文字节和 embedding 请求数。它可以证明 v7 是否真实改变输入，以及改变发生在哪些 C++ 车道；它不能证明回答正确率提升。

只有后续在本轮上下文上使用相同 qwen3.8-27B answer/judge 协议完成双臂后，才计算共同技术正常子集的净增、按 network 聚类 bootstrap 和请求账本。预设晋升条件沿用 R5.0：两臂技术完整、无身份/权限/预算回归，至少一臂净增不低于 5 题且网络 bootstrap 95% 区间下界大于 0；否则保持实验开关关闭。

## 5. 验证顺序

执行顺序固定为：

1. 中文设计和实施计划；
2. Python 防漂移 RED 测试，验证输入目录、双臂策略、快照哈希、请求和终态合同；
3. 只读 Python 编排实现，核心选择不在 Python 重写；
4. RED→GREEN、离线 Stub 结构测试和真实 qwen embedding 上下文生成；
5. 独立统计、封存和中文评测报告；
6. 只有上下文封存完成后，才讨论是否执行共享回答/裁判评测。

## 6. 默认策略

R5.1 不修改 `evidence_profile_v6`、`evidence_profile_v7` 的 C++ 实现，不修改默认 `source_strategy`，不晋升 v7，不删除 R4.9/R5.0 目录。
