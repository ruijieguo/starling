# SocialMemBench R3.4 结构化抽取协议有限重试评测报告

日期：2026-09-21

## 1. 评测边界与实验身份

R3.4 只在 C++ `semantic_claim_contract` 抽取路径增加最多一次原生协议纠错重试。重试条件限定为 `envelope_failure` 或 `schema_failure`；scope 语义拒绝、admission 失败、来源证明失败和持久化失败不重试。Python 只把 `claim_protocol_retry_budget` 映射到原生 `ValidationPolicy`，没有复制解析、JSON 修补、谓词目录或重试循环。

本轮固定使用 `qwen3.8-27b`、57 道题、7 个 scope、`mode=hybrid`、`source_strategy=focused_coverage`、`min_source_items=7`、回答上限 512、裁判上限 64、HTTP 预算 1200。R3.4 预算为 `claim_protocol_retry_budget=1`，R3.3 对照为 0。两轮使用相同题目、回答/裁判协议和来源快照，实验目录与请求账本独立。

R3.4 目录：`build/socialmem_20260921_structured_eval_hybrid_protocol_retry_r34_protocol_retry`。

## 2. 实现和离线验证

C++ 为重试的唯一实现层。每次 attempt 保存实际 prompt、prompt hash、原始响应、解析错误、admission 回执和终态；只有终态协议成功 attempt 的声明进入最终统计。默认预算仍为 0，生产 `semantic_claim_contract=false` 不受影响。

当前工作区的新鲜验证结果如下：

- C++ `ClaimContract.ProtocolRetry*`：4/4 通过，覆盖默认零预算、一次重试、重复 JSON key、目录外谓词、重试上限、scope 语义拒绝不重试，以及每次 prompt/hash/原始响应回执。
- R3.4 相关 Python 门禁：53/53 通过。
- 离线原生 smoke：1/1 通过，冻结快照保持不变。
- 完整 CTest 归档：1207 通过、22 跳过、1 个失败。唯一失败是既有沙箱禁止 loopback listener 的 `OpenAIAdapterHttpTest.LegacyAndGenerationRejectIncompleteOrRefusedCompletions`，与 R3.4 逻辑无关。

离线回放日志：`build/socialmem_20260921_r34_offline_protocol_replay.log`、`build/socialmem_20260921_r34_python_verification.log`、`build/socialmem_20260921_r34_offline_smoke.log`。既有 RED 日志仍保留在 `build/socialmem_20260921_r34_red_cpp.log` 和 `build/socialmem_20260921_r34_red_python.log`。

## 3. 真实评测结果

R3.4 执行 57/57 题，覆盖率 1.0。9 题技术失败，48 题进入回答和裁判；最终正确 12/57（21.05%），技术正常子集为 12/48（25.00%）。R3.3 为 11/57（19.30%），19 题技术失败，正常子集为 11/38（28.95%）。

| 指标 | R3.3 | R3.4 | 变化 |
|---|---:|---:|---:|
| 总题数 | 57 | 57 | 0 |
| 执行题数 | 57 | 57 | 0 |
| 正确题数 | 11 | 12 | +1 |
| 全题准确率 | 19.30% | 21.05% | +1.75 个百分点 |
| 技术失败 | 19 | 9 | -10 |
| 技术正常题 | 38 | 48 | +10 |
| 技术正常子集准确率 | 28.95%（11/38） | 25.00%（12/48） | -3.95 个百分点 |
| 完成 scope | 5/7 | 5/7 | 0 |
| 完成 holder | 23/36 | 27/36 | +4 |
| 请求账本 committed | 590 | 738 | +148 |

R3.4 的技术失败集中在两个 scope：

| scope | holder | 归档失败分类 | 证据与判断 |
|---|---|---|---|
| `3c2b930eaabb88e5f3da20b4` | Josh | `envelope_failure`，连续两次 | 两次原始 V2 响应都包含重复 `time_text` key；第二次仍失败，达到预算上限。 |
| `e0851b27363bcbedab64e5cb` | Yusuf | `schema_failure`，记录一次 | prompt token 为 19,996，原始响应是 V2 structured-claim object，因而可确认属于 belief 结构化通道；scope.failure 未保留逐字段错误和完整 receipt，具体触发字段仍不能从归档单独还原。 |

Preet 的回执记录了首轮 `schema_failure`（缺少 `holder`）和第二轮成功，证明 R3.4 的原生纠错链路在真实 DashScope 请求中确实生效。真实运行中共发现 4 个失败 attempt 行：Josh 两次、Yusuf 一次、Preet 首轮一次；第二轮成功的 Preet 不计入技术失败。

R3.3 的 19 个技术失败来自 Josh scope 和 Margot 所在 scope；R3.4 修复了 Margot scope 的可用性，但 Yusuf scope 仍失败，因此 scope 完成率没有上升。

## 4. 配对 QA 与统计判断

两轮 57 道题逐题配对，技术失败按 0 分计入全题分母：

- 18 题由 `ingestion_failure` 恢复为正常，8 题由正常退化为 `ingestion_failure`，1 题两轮均失败，30 题两轮均正常。
- 7 题从错误变正确，6 题从正确变错误，5 题两轮均正确，39 题两轮均错误。
- 全题净增 1 题（+1.75 个百分点）。以 6 个 network 为重采样单位、固定随机种子 20260921、100,000 次网络 bootstrap，95% 区间为 **[-22.22, +22.37] 个百分点**。
- 两轮共同技术正常题只有 30 题：R3.3 正确 8 题，R3.4 正确 6 题，净减 2 题（-6.67 个百分点）；网络 bootstrap 95% 区间为 **[-17.24, +12.50] 个百分点**。

因此 R3.4 没有满足预注册晋升条件“净增至少 5 题且网络 bootstrap 区间下界大于 0”。协议重试显著改善了技术可用性，却没有证明回答质量提升；生产默认继续保持 `semantic_claim_contract=false` 和 `claim_protocol_retry_budget=0`。

完整逐题配对、scope/holder、失败 attempt 和 bootstrap 数据见 `build/socialmem_20260921_r34_pairwise_diagnostics.json`；R3.4 原始摘要、逐题回执、scope 数据库和请求账本均保留在独立目录中。

## 5. 能力短板诊断

第一，重试只解决输出协议的偶发不稳定，不能修复声明内容的主体、关系、时间和跨会话归因。共同正常子集反而下降，说明当前主要瓶颈已从“是否能写入”转为“写入后的证据选择和答案推理”。

第二，holder scope 仍是全有或全无。单个 holder 的协议失败会使整个 scope 不生成 frozen snapshot；R3.4 的 Yusuf 失败使该网络的 8 道题全部归零。Josh 失败 scope 也继续保留为 1 道技术失败。这种批级放大效应仍是整体分数的主要可用性风险。

第三，Yusuf 的失败虽然可定位到 belief 结构化通道，但当前 scope.failure 没有完整保留失败 attempt 的 prompt、解析错误位置和通道 receipt，导致无法判断是模型字段缺失、字段类型错误还是目录/证据边界触发。诊断证据链还需要补齐。

第四，R3.4 增加了 148 个账本 committed 请求，却没有带来正常题质量净增。继续扩大重试预算或回答 token 上限没有充分依据，下一轮应先隔离 holder 失败传播和字段级 schema 诊断，再测语义改进。

## 6. 下一轮优化建议（待确认后编码）

建议进入 R3.5 诊断性优化，仍遵守“中文设计 → RED 测试 → C++ 实现 → 离线回归 → 独立真实评测”：

1. **C++ 失败证据完整化**：在失败 scope 也持久化每个 channel、每个 attempt 的 output contract、prompt hash、解析错误 kind/detail、原始响应 hash 和终态；不把模型原文重新拼进纠错 prompt。
2. **holder 级故障隔离**：将单个 holder 的失败记录为可审计的 holder result，继续处理后续 holder；只有没有任何可用 holder 或写入边界被破坏时才终止 scope。Python 只负责遍历和展示结果，解析、重试、状态机和提交边界留在 C++。
3. **字段级 schema 纠错**：针对 `schema_failure` 生成包含确定性错误类别和字段路径的原生纠错提示，保持最多一次预算；不修补原 JSON、不改写谓词和证据。
4. **评测门禁**：新增固定离线夹具，分别验证预算 0/1、holder 失败后继续、失败 receipt 完整性；真实复测仍固定 57 题、qwen3.8-27b、1200 请求上限。只有技术失败继续下降且共同正常题配对净增达到预注册条件，才讨论晋升。

R3.5 未获确认前不改变生产默认，也不把 R3.4 的技术完成率改善写成端到端质量提升。

## 7. 证据索引

- R3.4 摘要：`build/socialmem_20260921_structured_eval_hybrid_protocol_retry_r34_protocol_retry/selected-summary.json`
- R3.4 完整摘要：同目录 `summary.json`
- R3.4 配对诊断：`build/socialmem_20260921_r34_pairwise_diagnostics.json`
- R3.4 请求账本：同目录 `request-ledger.sqlite`
- R3.4 scope/holder 回执：同目录 `runs/*/scope*.json`、`runs/*/extraction.receipts.json`、`runs/*/network.db`
- R3.4 专项和离线回放：`build/socialmem_20260921_r34_offline_protocol_replay.log`、`build/socialmem_20260921_r34_python_verification.log`、`build/socialmem_20260921_r34_offline_smoke.log`
- R3.4 CTest 归档：`build/socialmem_20260921_r34_ctest.log`
- R3.3 对照摘要：`build/socialmem_20260921_structured_eval_hybrid_coverage_r33_evidence_coverage_net/selected-summary.json`
