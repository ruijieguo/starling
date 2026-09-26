> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](2026-09-17-socialmem-grounded-answer.md)。

> **本轮优化已验收（2026-09-17）**：相同冻结C++候选完成开发及保留集，全量392/1031=38.02%（原baseline20.47%），保留集119/298=39.93%；模型/评分保持，核心逻辑由C++统一实现。当前设计与结论见[最新报告](2026-09-17-socialmem-source-focus.md)；下文保留原阶段历史事实。

# SocialMemoryBench 谓词覆盖 R1/B 实施与真实探测报告
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](2026-09-16-socialmem-scope-schema.md)。


**状态（2026-09-16）：原生模块身份已修正，本轮真实评测在能力门槛停止。** 实际 16 次 HTTP 请求、零重试；四来源的 16 次抽取及最多 16 次准入均未执行。没有新的覆盖率、F1 或问答质量结论，生产默认继续关闭。

## 本轮实现与模块纠正

C++ 抽取提示增加逐话轮检查明确状态/状态变化的指导；共享关系目录补充 trusts 和 indifferent_to 边界；无可恢复主题的裸 `indifferent_to(either way)` 由 C++ 拒绝。共享目录同时改变抽取与准入提示，候选数据、wire schema、来源 proof 和默认值保持。Python 只负责绑定、请求编排、归档和统计。

上轮仅构建 C++ 测试目标，Python 仍加载旧 L/R0 模块。因此旧 Python 91/91、1387/15 和所谓“R1/B 的 S/T 52 条重放”撤回为 R1/B 证据，旧封存本身不变。本轮补充 binding 行为 RED，重建、安装后验证 GREEN。

| 实验臂 | 模块 | SHA-256 |
|---|---|---|
| D0 | L/R0 最终封存，已含此前 B/C/S 开发树改动，不能称为历史 A | `23f77718fb13ec9ffc9c12bbd88d1bde7337a8caeb99b94c8ccfb5d05249a642` |
| D1 | 当前重建安装的 R1/B | `94749a715ae19ea57bdce350b00cf382f45fef2a520fe7bcb88d57c6df201cfe` |

D0 原件位于 `build/socialmem_20260915_claim_scope_final/modules/current/`；D1 来自 `.venv/lib/python3.14/site-packages/starling/`。本轮隔离副本分别在 `build/socialmem_20260916_r1b_work/stages/D0/` 与 `stages/D1/`，使用 `python -S` 加载并逐一核对实际路径和 hash。

## 回归与历史派生重解析

- 状态覆盖指导、裸短语拒绝、关系目录三项 C++ RED→GREEN；binding 的旧模块 RED→新模块 GREEN。
- 重建后完整 C++ 1106/1106；Python 1397 通过、15 跳过。初次沙箱回环监听失败单独保存，完整计数来自允许本机 HTTP 的复跑。
- 新增 R1/B 编排测试覆盖预算、双臂门槛、C++ 准入重放、请求前保存准入预览及失败分类；`.venv/bin/python -m pytest tests/python/test_eval_socialmem_r1b.py -q` 为 9/9，通过日志保存在 `build/socialmem_20260916_r1b_work/worker_guard_green.log`；综合核验见 `build/socialmem_20260916_r1b_work/validation.json`。
- 新 D1 对历史 S/T 52 条回执派生重解析：42 条完整响应、10 条未知；与 D0 的解析结果无差异。Marcus 的三类状态在旧回执中仍未生成，Femi 的既有解析修复仍有效。
- 历史 A+L 的 140 条整链路重放只作为历史基线证据，不证明新 R1/B 的生成、准入或存储效果。

原设计中的通用参考例、复杂关系、存储/检索及覆盖诊断大部分沿用既有实现，本轮没有新增相应全套 RED。实施计划已撤回过度勾选；objecting 只是旧 feels 候选的对象文本，本轮未新增事件谓词或事件通道。

## 本轮真实请求及停止原因

沿用已冻结模型 `qwen3.7-plus`、原 DashScope 兼容端点、温度 0、4096 tokens、120 秒、零重试。四个拟评测来源为 T-20 Marcus、T-17 Femi、S-20 Alice、S-26 Claudette，每臂每来源两次；来源内容和模型输入预览已冻结，问题/答案/人工目标不进入提示。

| 项目 | D0 | D1 |
|---|---:|---:|
| 原生 HTTP 尝试 | 8 | 8 |
| HTTP 200 完整响应 | 8 | 8 |
| 通过原生探测契约的响应 | 8/8 | 7/8 |
| json_object 抽取/准入探测 | 通过/通过 | 通过/通过 |
| json_schema_strict 抽取/准入探测 | 通过/通过 | **失败**/通过 |
| SocialMemoryBench 来源抽取/准入 | 未执行/未执行 | 未执行/未执行 |

D1 严格抽取的逆格式探测生成 `assertion_scope="ASSERTED"`、`scope_markers=[]`；原生错误为 `schema_failure:primary scope absent from scope_markers evidence`。同一响应已在 D0 与 D1 中离线重放，两者拒绝结果一致。

当前 wire schema 只约束 scope_markers 为枚举数组，未约束非空及唯一性，所以该响应 wire 校验通过，但更严格的 C++ 声明契约失败。不能将它说成 HTTP/超时失败、SocialMemoryBench 样本失败、单纯谓词不足或提供商违反已发送的 schema。两臂各一个固定小组，也不足以归因新提示导致退化。

编排审查补充：`run_socialmem_r1b.py` 生成的停止计划已正确消费 16 次探测预算并返回空样本计划；`eval_socialmem_r1b.py` 的 worker 通过 `extract_once` 校验零重试/严格模式，但全局 48 次预算和能力报告身份仍由 supervisor 负责，worker 单独调用不会替代 supervisor。下一轮若恢复样本，必须先增加身份、schema、端点、来源 proof 和硬预算的失败测试与守卫。

按任一臂能力门槛失败即停止的设计，本轮状态为 `stopped_capability_gate`。16/48 次预算已使用；剩余 32 次不自动续用。请求逐条身份、原始响应、模块/schema hash、用量和预算已归档。实际返回的 token 总数为 45279（prompt 32544、completion 12735），不是费用估算。

## 结论与后续方案

已证明：新模块确实加载 R1/B；完整回归通过；历史响应解析兼容；失败响应由两臂相同契约拒绝；停止条件得到执行。尚未证明：Marcus 未决/决定/紧张的生成召回、Femi 新输出稳定性、Alice 认知误标改善、Claudette 反对目标完整性。上述四项新结果一律记为未执行，不写成零召回。

优先对齐 C++ wire schema 与声明契约的数组约束，再做独立能力探测，之后恢复候选覆盖对照。具体顺序、测试和兼容边界见[范围字段对齐方案](../superpowers/specs/2026-09-16-scope-schema-alignment-design.md)。该新 schema 方案尚未实施，不混入已冻结实验。生产默认保持 `semantic_claim_contract=false`、`claim_output_mode=Legacy`；本轮探测专用配置是 `semantic_claim_contract=true`、`json_schema_strict`。无存储、检索、QA、裁判、1031 题全量、提交或推送。

本轮实施、请求和核验证据封存位置：`build/socialmem_20260916_r1b_work/`。主要入口为 `real-summary.json`、`stopped-plan.json`、`request-ledger.jsonl`、`failure-native-replay.json` 和 `native_boundary_parity.json`。评测方案见[真实评测设计](../superpowers/specs/2026-09-16-r1b-real-evaluation-design.md)。
