> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](2026-09-17-socialmem-grounded-answer.md)。

> **本轮优化已验收（2026-09-17）**：相同冻结C++候选完成开发及保留集，全量392/1031=38.02%（原baseline20.47%），保留集119/298=39.93%；模型/评分保持，核心逻辑由C++统一实现。当前设计与结论见[最新报告](2026-09-17-socialmem-source-focus.md)；下文保留原阶段历史事实。

# SocialMemBench 协议恢复实现与本地验证报告
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](2026-09-16-socialmem-scope-schema.md)。


> 以下正文保留本地交付时点。后续已明确授权并启动 A 真实诊断，最新状态、报告刷新和额外 DNS 失败计数见[A 阶段报告](2026-09-14-socialmem-protocol-recovery-a.md)。本地封存不改写。

**本轮本地修复、完整回归及独立 A/B 离线验证已完成；真实实验被自动审批阻断，新增外部模型请求为 0，质量分数为空。** 这不是 Qwen 的能力失败观测。工程结果不能证明关系覆盖或答题质量提升。

设计依据为[结构化协议恢复与模型对照设计](../superpowers/specs/2026-09-14-protocol-recovery-design.md)，执行顺序和未完成步骤见[实施计划](../superpowers/plans/2026-09-14-protocol-recovery.md)。此前[调查报告](2026-09-14-socialmem-protocol-recovery.md)保留调查时的文档阶段状态。

## 修复及职责边界

- C++ 共享抽取提示的六个示例和输出形状补齐 `confidence:null`，指导明确未知置信度使用 null。原生 schema、必填约束及 null/缺省解析为 0.7 的兼容行为保持原样。
- 评测构造入口与探测、claim CLI 增加显式 `--model`；默认仍为 `deepseek-v3`。空白或首尾含空白的名称在请求前拒绝。
- cohort 启动前，使用实际配置构造原生 adapter，再将其端点、模型与能力报告核对。不能以报告提供的模型与报告自己比较来替代实际配置检查。
- 新 manifest 的 `base_memory_provenance` 保存基础输入 manifest、核心和原抽取配置；旧基础记忆仍为 DeepSeek 来源，不能被新补充抽取的 Qwen 名称覆盖。验证器拒绝篡改，并兼容没有新增字段的历史档案。

请求构造、schema、能力状态、原始回执、语义判断和重试仍唯一实现在 C++。Python 只负责配置、编排和归档身份核验。相对上一轮最终源码清单，本轮变更 8 个源码/测试文件；未增加谓词或更改关系、时间规则。

## 测试与工程证据

先同步中文设计，再记录 RED，最后实现并运行 GREEN、完整回归。日志封存在 `build/socialmem_20260914_protocol_recovery_final/logs/`，原日志保持在 build 根和实验工作目录。

| 检查 | 结果及范围 |
|---|---|
| 原生新增测试 RED | 从实际 C++ prompt 读取参考响应，以同一 C++ schema 校验；六个示例均报 missing_field |
| Python RED | 六个配置/CLI 测试因缺少 model 参数失败；随后来源身份测试因缺少 helper 失败 |
| 聚焦 GREEN | C++ 47/47；Python 50 passed |
| 当前版本完整构建与安装 | 完成；确认实际加载的已安装原生模块 |
| 当前版本 C++ 全套 | 1,090/1,090，无跳过 |
| 当前版本 Python 全套 | 1,362 passed / 15 skipped；跳过包括既有真实模型 E2E，不能算作已完成真实验证 |
| A/B 独立构建与 C++ 聚焦测试 | 各 34/34；只覆盖协议、schema 和 HTTP，不冒充历史完整测试树 |
| 模块与能力报告交叉核验 | 三个版本各自报告通过离线身份核验，跨核心报告全部拒绝；此检查不刷新 TTL，不授权真实评测 |

旧 archive 没有完整测试树；A/B 补入的公共构建文件、协议测试及来源哈希分别登记在 `a_preparation.json`、`b_preparation.json`。当前源码的全套回归与 A/B 的阶段聚焦验证分别计数。

## 独立副本与离线结果

| 版本 | 核心 SHA-256 | 离线结果 |
|---|---|---|
| A：冻结协议阶段加共同修复 | `79a0c3873ab68348797ae84c75c0ffed7dfcbc3f9a0903c3fe74455d1eca7e2e` | 140 条旧原文重放零差异；smoke 原生核验 verified / complete |
| B：冻结关系阶段加共同修复 | `d4f2379fd9d86e29ee9fa438fc5b9136b6d7b919f5cdc8270d164974b0b68b8a` | 140 条旧原文重放零差异；smoke 原生核验 verified / complete |
| 当前开发版本 | `af1b769fa5a83e19209461d0d944b8047cde6332c3f87590ff35c53e53e9d876` | 140 条旧原文重放零差异；smoke 原生核验 verified / complete |

三份有效档案分别位于 `build/socialmem_20260914_protocol_recovery_{a,b,current}_offline`。每份 smoke 包含 140 次原生持久化重放、144 个数据库、76 次 Fake 抽取、64 次固定注入、45 次 Fake 准入、8 次 Fake 回答及 120 次 Fake 裁判；另有 8 次真实本机 HTTP 能力回环、零重试。它们只验证工程链路，外部模型调用均为 0。

A/B 的共同补丁新增/删除行哈希完全一致，关系提示仍各自冻结，A 未混入 B 关系边界或 C 时间实现。三版本 schema 与上一轮冻结内容一致。

首次尝试通过 PYTHONPATH 选择 A/B 时，venv 的 editable `.pth` 导入钩子仍加载了当前开发模块。这两份结果移至后缀 `_offline_invalid_editable` 的目录并写入 `INVALID.json`，明确排除。有效运行使用 `python -S` 和 `run_stage.py`，显式加载阶段模块并断言实际路径与哈希。阶段副本根下保留的旧 `.so` 仅是复制来源遗留文件，实际加载路径为阶段 `python/starling/`。离线加载器只存在于实验目录。

## 真实执行阻断与后续边界

自动审批拒绝了向 `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions` 的 `qwen3.7-plus` 发送 A 阶段八条请求。理由是它认为用户的“继续”不足以明确授权把内部提示词、结构化协议及相关载荷发送到该外部目的地。该命令没有执行，未生成新真实能力报告。

准确状态是 `approval_review_blocked`，Qwen 能力为 `not_observed`；A/B cohort、回答、裁判、嵌入及条件时间 QA 均未启动。不能伪造 `nonconformant` 或把审批阻断登记为服务拒绝、网络失败、新能力回执。

A 的八条完整请求预览为 [request_preview.json](../../build/socialmem_20260914_protocol_recovery_a_offline/request_preview.json)。其中含通用 Nora/picnic 来源、共享抽取/准入指导、参考示例及 schema；不含评测问答金标或凭证。每请求温度 0、最多 4,096 输出 token；八条探测零重试。预览用于确认正文，不是已发送证明；预览中早期的 approved 描述不能替代自动审批放行。

本地工作和结果已具备复核条件。只有明确外部发送授权后才重试 A 探测；严格抽取和准入同时通过且报告未满十分钟，才进入 A 的 140 条固定诊断。B 必须用自身核心再探测，A 失败不启动 B。后续材料、端点及总预算按设计表执行；本轮没有产生新模型费用或新评测分母。

## 对整体评测的结论

最近真实质量仍来自[协议与偏好边界诊断](2026-09-13-socialmem-protocol-boundary.md)：`verified / complete_with_errors`，固定控制 56/64，10 条技术失败；P1 combined F1 为 0.7317/0.6829/0.7683，Q1/Q9 的 baseline、structured、linked 均 0/3，full 为 3/3。最近真实协议观测仍是旧 DeepSeek 的[八条探测四组 nonconformant](2026-09-14-socialmem-capability-probe.md)。两者均不得改名为本轮 Qwen 结果。

谓词丰富度问题尚未获得完整语料的覆盖率结论。已建 1,031 题结构矩阵，但除 Q1/Q9 外的 1,029 题尚未逐题复核；B 的关系边界和当前时间视图只有本地工程证据。本轮先消除了可复现的提示/schema 矛盾，并保证后续 A/B 的配置、基础记忆及模块身份可区分；其语义收益仍待真实对照。

生产默认保持 `semantic_claim_contract=false`、`claim_output_mode=Legacy`、`temporal_evidence=None`。未跑 1,031 题全量，未提交或推送。现行设计入口同步本轮本地完成/审批阻断状态；104 份历史设计、原标签和旧评测归档以哈希核验保留。

机器可读结果见 [分析记录](2026-09-14-socialmem-protocol-recovery-implementation-analysis.json)，最终源码、模块、schema、日志及归档索引见 `build/socialmem_20260914_protocol_recovery_final/manifest.json`，文档/历史/归档核验见同目录 `validation.json`。
