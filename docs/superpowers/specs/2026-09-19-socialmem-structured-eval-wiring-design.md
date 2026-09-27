<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

# SocialMemBench 结构化检索评测接线设计

状态：已确认的结构化闭环下一阶段设计，实施顺序为本文档 → 失败测试 → Python 评测编排实现 → 固定模型对照。

## 1. 目标

将已通过离线门槛的 C++ 结构化抽取/证据路径接入 SocialMemBench 的受控开发评测。抽取、admission、持久化和来源证据仍由 C++ 执行；Python 只传递 `ExtractionConfig`、调用 binding、组织运行目录和汇总逐题结果。

本轮先使用已经有同口径来源快照的 57 题开发子集，比较：

- `sources`：当前来源观察者路径，作为同期对照；
- `statements`：同一来源、同一答案/裁判模型和预算下，使用结构化声明观察者路径。

两臂不修改题目、裁判、参考答案、历史归档或默认生产路径。模型固定为 `qwen3.8-27b`，DashScope 端点、零重试、thinking 配置、回答/裁判 token 上限与父实验一致。

## 2. 接线边界

`eval_ladder.make_real_extract_fn` 增加可选的 `ExtractionConfig` 参数。默认值保持旧行为；结构化实验显式传入 `semantic_claim_contract=true` 和 `preserve_text_objects=true`，并将同一 C++ `ValidationPolicy` 传给 `memory_remember_extract_all` 与 `memory_remember_commit_all`。SocialMemBench 来源运行器也只负责从配置构造该对象并透传到同一工厂；不得在 Python 中判断谓词、改写证据或补写声明。

检索臂只改变 `ObserverQuery.mode`：`sources` 或 `statements`。候选选择、租户和证据认证由 C++ `ObserverRetriever`/结构化检索核心执行。回答 prompt、裁判 prompt、语料、来源快照、embedding 模型和评分函数保持一致。

## 3. 运行与账本

每个臂使用独立目录和 manifest，冻结源码、构建扩展、语料、范围和配置哈希。`sources` 臂复用只读来源快照，不重新抽取；`statements` 臂在独立目录中运行 C++ 三相抽取、admission、持久化、embedding 和声明检索。两个臂的回答/裁判协议、问题分母和来源快照相同，抽取与 embedding 成本单独计入 `statements` 臂的请求账本。抽取、embedding、回答、裁判请求均预约上界；中断或未知终态按上界计费，不自动重试。运行结束后才读取分数，报告完整题目分母、成功分母、技术失败、抽取回执类别、结构化证据排除、tokens 和逐题差异。

运行入口为 `scripts/run_socialmem_structured_eval.py`：`prepare` 只创建新目录并复制来源臂的只读语料/快照，`check` 不构造 adapter、不发请求，`run --arm sources|statements` 才允许进入网络阶段。每个臂保存 `config.json`、`identity.json`、`execution-plan.json`、`request-ledger.sqlite` 和逐题结果；声明臂额外保存每个 scope 的 `extraction.completed.json` 与 C++ 回执。脚本拒绝覆盖已有目录，且在请求前校验源语料哈希、57 个唯一题目、7 个 scope、101 个来源臂问题请求上界、`qwen3.8-27b`、DashScope 端点和 `max_retries=0`。

首轮仅验证接线和同口径方向，不把 57 题结果外推到 733/1031 题。晋级条件为结构化臂相对来源臂净增至少 5 题，且网络 bootstrap 95% 区间下界大于 0；否则保持实验关闭，下一轮只针对唯一失败假设设计。

## 5. 首轮诊断后的唯一优化变量

首轮声明臂的 35 个技术失败来自 3 个 holder 的 `envelope_failure`：模型返回的结构化 JSON 被 ```json 围栏包裹，C++ 合同在 `claim_allow_code_fence=false` 下按协议失败处理。成功 scope 已完成 C++ admission、持久化和向量化，说明失败边界集中在输出封装而非谓词检索。下一轮只增加独立候选 arm `statements_fenced`，保持 `recall_mode=statements`、模型、题目、来源快照、回答/裁判协议、预算和零重试完全相同，显式将同一 C++ `ValidationPolicy.claim_allow_code_fence` 设为 true。该开关只允许原生合同去除围栏后继续校验，不在 Python 解析或改写声明；若技术失败仍存在，再进入单独的谓词/证据诊断。

`statements_fenced` 已把围栏导致的 scope 失败显著减少，但纯声明上下文仍可能丢失跨轮证据。因此下一轮候选 `hybrid_fenced` 复用该候选的冻结声明/来源数据库，只把 `ObserverQuery.mode` 改为 `hybrid`；`claim_allow_code_fence=true`、模型、回答/裁判、题目和零重试预算保持不变。该候选用于判断融合上下文是否恢复长答证据，不能与重新抽取或扩大题目分母混为一谈。

`hybrid_fenced` 已恢复完整覆盖并带来 1/57 的净增，但 bootstrap 区间跨过 0，不能晋级。下一候选 `hybrid_dialogue` 复用同一冻结数据库，只把 C++ `ObserverQuery.source_strategy` 从 `bm25` 改为 `focused_dialogue`，让检索在命中说话人的同时保留相邻对话上下文；不改变谓词目录、抽取、回答、裁判、题目或预算。

首轮 `hybrid_dialogue` 未产生模型请求：57 题均在查询阶段返回 `ValueError: invalid observer query`。根因是 `ObserverRetriever::run` 的旧校验将所有非 `bm25` 的来源策略限定为 `mode=sources`，这与 `hybrid` 同时合并来源和声明的语义冲突。优化范围限定为 C++ 查询合同：当 `mode=hybrid` 时允许 `focused`、`focused_window`、`focused_dialogue` 和 `focused_coverage`，来源选择仍先执行授权、租户、完整性和时间过滤，再按策略裁剪；随后继续执行声明检索并按既有上下文预算合并。`mode=statements` 仍只允许 `bm25`，避免在没有来源段的声明专用路径中引入未请求的对话读取。该改动不改变默认值、Python 语义或任何答案/裁判协议。

修复验收要求：C++ 测试必须证明 `hybrid + focused_dialogue` 能返回来源段并保留声明检索分支的结果字段；`statements + focused_dialogue` 仍拒绝；离线 C++/Python 回归通过后，复用同一冻结数据库重跑 57 题 `hybrid_dialogue`，单独记录技术失败、请求账本和相对 `hybrid_fenced` 的配对差异。若准确率提升仍未达到既定晋级门槛，候选继续保持实验状态。

修复后的真实重跑完成 57/57，技术失败 0，得分 17/57（29.82%）。来源对照为 15/57，`hybrid_fenced` 为 16/57；按仓库既有 5,000 次网络级 bootstrap，`hybrid_dialogue` 相对来源的 95% 区间为 `[-3.03%, +11.63%]`，相对 `hybrid_fenced` 为 `[-4.29%, +8.51%]`，均未满足净增至少 5 题且区间下界大于 0 的晋级条件。逐题 `source_diagnostics.dialogue_added_sources` 全部为 0，说明本轮只验证了 hybrid 与 focused 策略的合同兼容，尚未验证邻句扩展本身。

下一候选命名为 `hybrid_dialogue_expanded`，仅调整原生策略的预算参数：外层 `k=10`、`max_context_bytes=8000`、模型、题目、来源数据库、回答/裁判协议和零重试保持不变；显式传入 `source_seed_k=5`、`source_seed_max_context_bytes=4000`、`source_dialogue_radius=2`，为 C++ `focused_dialogue` 留出最多 5 条邻接来源的容量。该参数变化属于独立诊断，不能与上一轮 `hybrid_dialogue` 结果合并，也不能把来源数量或 `dialogue_added_sources` 直接当成 QA 提升。若候选完整运行仍未达到晋级门槛，保留 `hybrid_fenced` 作为当前结构化实验参考，不改变生产默认。

`hybrid_dialogue_expanded` 已完成 57/57，技术失败 0，得分 15/57（26.32%）。相对来源对照净增 0 题，网络 bootstrap 95% 区间为 `[-5.26%, +4.76%]`；相对 `hybrid_dialogue` 净减 2 题，区间为 `[-12.20%, +3.08%]`。57 题均产生 5 条邻句新增，证明 C++ 扩展确实被执行，但额外上下文没有带来稳定问答收益。该方向在当前固定预算下关闭，后续应转向结构化谓词覆盖与 admission 诊断。

## 4. 回滚与限制

评测接线的默认参数保持旧值，任何结构化臂必须显式声明。真实结果不能证明所有 SocialMemBench 谓词或社会推理能力；只能证明在冻结子集和协议下的端到端差异。历史 baseline、裁判和来源快照只读。

## 4.1 SourceTurn 与回执接线同步（2026-09-20）

真实抽取入口现按 holder 分组后调用 C++ `claim_source_turn_payload`，保留会话/话轮/观察时间元数据；C++ `memory_remember_bundle_receipt` 统一导出 belief、general-fact、episodic 三通道回执，Python 只归档外层 JSON。每个 scope 另存 `extraction.receipts.json`。本同步不改变题目、裁判、默认检索模式或历史实验；实现与验证详见 [SourceTurn 回执报告](../../eval/2026-09-20-socialmem-source-turn-receipt-implementation.md)。
