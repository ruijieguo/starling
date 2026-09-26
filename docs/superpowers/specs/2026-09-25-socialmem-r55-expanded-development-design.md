<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.5：扩大开发验证设计

日期：2026-09-25。状态：执行前冻结；遵循用户既有自主迭代与 DashScope 数据/请求授权。先中文文档，再失败测试，最后实现和真实评测。不自动提交。

## 目标与选择

R5.4 在 57 题、6 个开发网络中，legacy 为 18→23，grounded_memory_v1 为 18→25，达到预先规定的扩大验证门槛。本轮验证该组合方案能否迁移到更多开发网络，不修改 C++ 策略、抽取提示、回答提示或裁判协议。

备选一是重跑原 57 题，只能测重复性；备选二是直接运行全部 733 题，需新增 32 个结构化范围且成本大。本轮采用固定的新增 6 网络、133 题开发 cohort，先验证迁移，再决定后续能力优化。历史开发数据已被使用，不能称为未见集；298 题历史保留集本轮不查询、不评测。

## 样本与身份

输入为 `build/socialmem_20260917_source_focus/corpus.jsonl`（1031 条，SHA-256 `ba9d11578f6ebdad5bf3a0e443cf44a0d002fd400e11b243890f3fcc06ec607c`）及同目录 `network-split.json`（SHA-256 `e9c76953955892c18d433d2efadf8532b7909d420853c085d992f912cd80f266`）。剔除 R5.4 的 6 个网络，在剩余 development_networks 中按 network ID 的 SHA-256 升序取前 6 个，选入网络的全部题目，不读答案分数进行选样。

固定顺序：`grp_c2d3e4f5`、`grp_7a8b9c0d`、`grp_e6f7a8b9`、`grp_d7e8f9a0`、`grp_b1c2d3e4`、`grp_a5b6c7d8`。共 133 题、8 scopes、65 个 holder-scope、1322 个 scope 内话轮、106 道自由回答题。按 network/scope/history_hash 分组，sample 与 groups 完整记录必须逐字一致，题 ID 唯一，历史一致。答案和锚点仅作评测，不能进入抽取或检索决策。

## 冻结核心与建库

固定 R5.4 核心 `02a2a3d8c653d331c700cdf652c59fefe2b812ff99845271bd5137bebf81dd3d`。R5.4 seal、frozen runtime、当前与核心对应的 implementation 源码均核验归档；不能把继承的 R5.0 源码树称为新核心完整源码。新评测另存当前源码快照与清单，并核验关键实现文件与 R5.4 一致。移除本项目 editable finder，拒绝加载非冻结 `_core`。

历史 8 库均为零 statements 的纯来源库，不能作为健康 hybrid 对照。从新库导入相同历史，复用现有原生 retain_history_sources、holder_isolation 抽取、sleep 生命周期及 embed_seeded。核心抽取、来源回链、排序、渲染和提示生成仅 C++；Python 仅数据选择、协议编排、账本及统计。不得在 binding 重写核心逻辑。

抽取沿用 qwen3.8-27b、8192 tokens、thinking=false、json_object、semantic_claim_contract、preserve_text_objects、code fence 兼容及原生协议重试上限 1。HTTP 重试为 0，timeout 120000ms。embedding 为 qwen3.7-text-embedding、1024 维、每批 10。created_at 为 2026-06-01T00:00:00Z，query_time 为 2026-12-08T00:00:00Z。

每个 scope 串行建库，避免既有临时 monkeypatch 和环境变量构造的并发冲突。冻结helper在独立临时scope目录内运行；仍可能持有连接的network.db及WAL/SHM属于瞬态工作状态，不能直接纳入正式seal。成功后归档已完成的权威frozen.db及全部原始回执；失败则以SQLite backup生成一致的诊断数据库快照，保留回执、异常及账本。正式阶段验收必须在子进程退出后再次通过，以证明数据库生命周期不会破坏封存。必须保存完整原始抽取回执、holder 成功/失败清单、声明/向量/来源计数、嵌入计数、DB 哈希。任何 holder 缺失/重复/抽取失败、零声明、向量不完整或嵌入失败都阻断后续检索和 QA；不能删题或丢弃失败 scope 来形成完整成绩。构建函数现有 partial 行为由外层严格验收，不把 partial 当健康。逐holder还须核验belief、general_fact和episodic各被调用响应的原生成功/错误、finish_reason及HTTP回执；episodic失败不传播到holder状态，故其HTTP失败、截断或缺失回执必须额外阻断。冻结episodic的ok=false同时表示合法空数组或解析失败，Python不得自行补解析；将传输正常但ok=false逐条标为“空结果或未解析，原生回执无法区分”，单列数量，不宣称事件语义完整率100%。本轮健康门槛证明传输及声明/向量对照可用，不证明事件抽取语义完整。失败不覆盖，不自动重建；在独立失败报告中分析后，另行记录恢复方案。

## 预算与执行阶段

建库持久账本上限 12000 请求单位；抽取每 holder 预留 9 并按既有 helper 上界计账（总 585），必须区分保守计账与原始实际请求。嵌入按已有 `_embedding_reservation` 预留、实际请求结算。超预算停止，不偷偷扩额。

检索同库同核心双臂：baseline=`evidence_profile_v6/hybrid/k10`，source10=`evidence_profile_v9/sources/k10`。每题 8000 UTF-8 bytes、min_source_items=7、radius=1，其他参数沿用 R5.4。baseline 查询嵌入上限 1336；source10 不运行 planner/embedding，零嵌入。共 266 条检索回执，复制库后查询，前后核验原库哈希。所有 holder 的正常 embedding receipt 必须完整，degraded_paths 必须显式空列表。保存来源、声明、上下文、native trace 及实际请求。

QA 在建库、身份和全部检索健康通过后执行，不按新增 cohort 的锚点/质量增益筛选是否运行，避免扩大验证的幸存偏差。双臂×legacy/grounded_memory_v1=532 个 fresh 终态，最多 956 次 answer/judge 请求。每臂均新生成答案，不复用 R5.4 成绩。qwen3.8-27b，回答512、裁判64、回答thinking=false；裁判沿用原协议，enable_thinking 未显式设置。不能把64参数当成观测总推理 token 上限。HTTP 重试0，并发最多4；异常上界收费、终态计零、保存原响应与 usage。进程崩溃保留未知 reservation，不静默重放。

三个阶段独立输出和 seal，禁止覆盖已存在结果。实际依赖、配置、输入、DB、逐题回执及持久账本全量封存；执行前后验证。冻结数据库先拒绝既有WAL/SHM副文件，再以mode=ro&immutable=1读取并显式关闭连接；仅mode=ro仍可能创建副文件，必须用真实WAL格式反例验证检查前后目录不变。总阶段预算上限14292个计账单位（12000+1336+956），不等于实际请求或 token 数。

## 统计与决策

主要终点：grounded_memory_v1 的全题 source10 准确率减 baseline；技术失败计零，固定 133 题分母。legacy 为预先指定次要终点。另报共同正常子集、配对四格表、按题型/网络分解、锚点变化、完全相同实际 judge 输入的翻转、成本、token 缺失比例。翻转审计按judge_prompt精确字节及固定judge配置分组，不把不同answer prompt当作不同judge输入；另保留严格相同回答提示/答案分组诊断。

沿用 100000 次 network cluster bootstrap，seed=20260925，区间95%。仅6个新增网络，区间只表述本次开发验证不确定性。复用R5.4统计计算时必须覆盖旧 eligible_for_expanded_development 字段，不能沿用旧的共同正常净增5题门槛；本轮5个百分点对应133题至少净增7题。达到继续扩大验证的标准：主要终点全题增益至少5个百分点且区间下界>0，共同正常增益方向一致，grounded 两臂各自 status=ok 的比例≥95%（每臂至少127/133题；终态完整率另计，不把失败终态当正常）；不得因legacy更好改为主要终点。任一未达标则诊断失败题并设计下一轮能力修正，不调整分母、提示、预算或裁判后混报本轮结果。不自动推广产品默认。

新增133题与旧57题分别汇报，不将旧成绩相加冒充190题fresh结果。结果属于增加来源且删除声明的组合效果，不能独立归因于来源预算。source-only仍读取合格claim metadata，不等于完全不依赖结构化记忆。

## 交付与验收

先失败测试覆盖样本泄漏/漂移、holder不完整、纯来源库冒充健康、配置或core篡改、拒覆盖、请求预算、异常终态及阶段封存，再实现。复用 R5.4 逐题检索与 QA helpers，新增 cohort 编排独立文件。阶段报告即使失败也明确写出已完成边界和未执行请求。同步所有设计、计划与两技术报告的中文当前状态入口，保留历史正文。
