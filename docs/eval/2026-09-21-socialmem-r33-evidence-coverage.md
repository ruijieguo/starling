# SocialMemBench R3.3 证据覆盖评测报告

日期：2026-09-21

## 1. 评测边界

R3.3 只改变 C++ `ObserverRetriever` 的来源候选覆盖和 hybrid 来源配额，未改变抽取谓词目录、JSON 合同、admission、裁判、题目、模型、回答预算或重试协议。Python 仅透传 `ObserverQuery.min_source_items` 和已有来源参数。

固定配置为 `qwen3.8-27b`、57 题、7 个 scope、零重试、`mode=hybrid`、`source_strategy=focused_coverage`、`source_seed_k=5`、`source_seed_max_context_bytes=4000`、`source_dialogue_radius=1`、`min_source_items=7`、回答上限 512。独立实验目录为 `build/socialmem_20260921_structured_eval_hybrid_coverage_r33_evidence_coverage_net`。

## 2. 实施与离线验证

C++ 新增了以下行为：

- 题目含 `each member`、`all members`、`everyone`、`each person`、`all four` 及对应中文表达时，按 `allowed_holders` 的稳定顺序覆盖全部允许人物；没有全体成员标记时不扩大人物范围。
- `focused_coverage` 对变化、早晚和历程问题按 session 首尾交替补充来源，并继续执行 tenant、holder、时间、擦除、哈希、重复话轮和 UTF-8 字节预算过滤。
- hybrid 的 `min_source_items` 在 C++ 校验并先填 SOURCE 行；实际来源数、声明数、预算拒绝、配额是否达成和选择 trace 写入回执。默认值 0 保持旧交替顺序。

测试先于实现。C++ 来源专项 24/24 通过，Python binding/结构化评测门禁 24/24 通过。完整 CTest 为 1226 项，其中 1203 通过、22 跳过、1 项失败；失败是当前沙箱禁止 loopback listener 的既有 `OpenAIAdapterHttpTest.LegacyAndGenerationRejectIncompleteOrRefusedCompletions`，与 R3.3 代码路径无关。

零请求回放使用 R3.2 固定数据库和 56 道技术正常题，按来源模式、`k=10`、8000 字节、`seed=5`、4000 字节 seed、radius=1 对比：BM25 至少命中一个金标话轮 24/56，R3.3 focused coverage 为 45/56，超过设计门槛 42/56。该结果是来源召回诊断，不是 QA 或 F1。

## 3. 真实结果

R3.3 完成 57/57 题，但 19 题技术失败，38 题进入回答和裁判。最终正确 11/57（19.30%），成功子集 11/38（28.95%）。技术失败由两个 scope 失败造成：一个 scope 的抽取出现重复 JSON key 的 `envelope_failure`，另一个 scope 在 holder 抽取阶段重试后失败；因此仅 5/7 scope 完成、23/36 holder 完成。该失败是技术可用性结果，不能作为来源策略的语义质量结论。

38 道技术正常题的 hybrid 回执全部达到 `source_count=7`，`source_quota_satisfied=true`。R3.3 正常题来源锚点命中为 25/38 题；这是实际上下文诊断，不能单独解释答案正确性。

与 R3.2 的同题配对如下：

| 指标 | R3.2 | R3.3 |
|---|---:|---:|
| 总题数 | 57 | 57 |
| 正确题数 | 13 | 11 |
| 技术失败 | 1 | 19 |
| 成功子集 | 13/56（23.21%） | 11/38（28.95%） |
| 完成 scope | 6/7 | 5/7 |
| 完成 holder | 32/36 | 23/36 |

两轮共同技术正常题为 38 题，R3.2 正确 9 题、R3.3 正确 11 题，净增 2 题（+5.26 个百分点）。按网络重采样 5000 次的 95% 区间为 [-2.63, +2.63] 个百分点，下界不大于 0，且净增未达到预注册的至少 5 题。因此 R3.3 不晋升，也不改变生产默认。

## 4. 诊断结论与后续

R3.3 证明 C++ 来源覆盖和 hybrid SOURCE 配额按合同工作，并显著提高了离线金标话轮候选覆盖；真实正常题的配对结果出现方向性改善，但统计证据不足，且抽取技术失败从 1 题增加到 19 题，导致整体可用性下降。当前主要瓶颈由“候选没进上下文”转为“抽取协议/批级 scope 稳定性”和“已有证据上的主体、关系、时间推理”。

后续优先级为：先单独修复重复 key 与 scope 级抽取失败并以独立目录复测 7/7 scope、36/36 holder，再在技术完成率稳定后评估来源配额对 Q7/Q8 关系和跨 session 题的净收益。来源覆盖、声明数量和离线回放均不能替代同协议 QA 晋升门槛。

## 5. 证据文件

- C++ 专项日志：`build/socialmem_20260921_r33_green_cpp.log`
- 完整 CTest 日志：`build/socialmem_20260921_r33_ctest.log`
- 零请求覆盖：`build/socialmem_20260921_r33_offline_coverage.json`
- 结构化覆盖诊断：`build/socialmem_20260921_r33_structured_coverage.json`
- 真实运行摘要：`build/socialmem_20260921_structured_eval_hybrid_coverage_r33_evidence_coverage_net/selected-summary.json`
- 真实逐题和原始回执：同一独立评测目录下的 `summary.json`、`runs/*/questions/*.json`、`runs/*/scope*.json` 和 `request-ledger.sqlite`
