<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R6.0：目标批次的声明输出布局一致化

## 目标与真实触发

本设计是用户已授权的“先取得健康 baseline，再改进并循环评测”的故障修复步骤。沿用先中文文档、再失败用例、最后 C++ 实现与真实验证。当前 R5.9 只有 1/8 健康库，133 题尚无分数；本设计不宣称准确率提升。

R5.9 的第二库 Tomas 在 batch_index=1 的初次生成与一次纠错中均返回三个格式错误的声明。顶层仅包含 confidence 和 evidence，其余声明字段嵌套在 evidence 内；原始 HTTP 200、finish=stop、JSON 有效，C++ 报缺少顶层 holder。失败原始回执保存在 `build/socialmem_20260926_r59_expanded/build/runs/1c2838ef51b9983207436fc9/`，保持不可变。

当前原生提示的 15 个参考示例经默认 JSON 序列化后以 confidence、evidence 开始，随后才是 holder 等字段；文字输出模板与末端骨架却要求 holder 等字段在前、evidence 在末。失败返回的字段顺序与参考示例相近。这证明提示布局存在不一致，不足以证明它是模型生成错误的唯一原因。把字段移回也不等于语义正确：诊断中的三条失败候选仍有 modality 或 QUESTIONED 等合同问题，不能自动写入。

## 方案取舍

1. **采用：统一目标批次参考示例的字段顺序。** 仅改变 C++ 生成的目标批次提示中参考示例的声明键顺序，使十个声明标量字段先出现，evidence 最后出现；所有字段值、示例数量、来源、模板及语义规则保持。通过受控真实请求验证协议稳定性。这个最小对照能单独检验布局假设。
2. **暂缓：纠错提示增加全部错层路径。** 可能比首个缺字段错误更清晰，但与布局同时修改会难以区分收益来源；当前一次原生纠错与错误摘要仍保留。
3. **暂缓：显式扁平 wire 新协议。** 可消除这类嵌套要求，但涉及新的请求 schema、转换、回执及兼容面，当前先测试较小方案。禁止在 v2 解析器中静默搬移、补全或猜测字段。

## C++ 边界与身份

- 产品修改只涉及 `src/extractor/claim_contract.cpp` 的目标批次提示与原生 profile 元数据。Python binding 不新增核心逻辑或参数；沿用已有 `claim_batch_target_units=true`。
- `claim_batch_target_units=false` 的抽取、纠错、plan 和回执保持逐字兼容；已存在的历史 prompt SHA 用例继续验证。普通未分批接口也保持不变。
- 开启目标索引时，仅将 `REFERENCE_EXAMPLES_JSON` 中每个 `response.statements[*]` 的顶层顺序改为：holder、holder_perspective、subject、subject_kind、predicate、object、modality、polarity、nesting_depth、confidence、evidence。evidence 内部的现有键顺序不变；目标是将整个证据对象放到声明尾部，不同时改变内部布局。
- 使用 C++ 有序 JSON 序列化构造私有输出副本。以原示例为唯一值来源，逐个指定字段复制，验证字段集合完整；不把 JSON 对象的顺序当作解析语义，也不修改原始候选或回执。输出后用严格 JSON 解析比较，新旧示例的值必须完全相同。
- SOURCE_DATA_JSON、批次目标索引、完整上下文、谓词目录、关系边界、准入提示、输出模板与末端骨架保持逐字一致。首次和纠错提示均复用同一个目标批次参考示例序列化入口，禁止替换任意来源字符串中的同名字段。
- 目标批次 native plan 和 receipt 使用新 profile `target_units_statement_first_v1`。新 core SHA、源码、profile、prompt/hash 必须形成新的冻结身份，不能把 R5.9 的 target_units_v1 产物重新标记为新结果。
- 继续严格 schema v2、JSON Object、8192 输出 tokens、thinking=false、temperature=0、一次协议纠错及 HTTP retry=0；不修改 admission、范围/时间、实体或谓词语义，不删除失败候选的诊断。

## 文档之后必须新增的失败测试

1. 在现有目标批次测试中解析实际 C++ 提示：15 个参考示例每个声明的顶层键序都符合上述顺序；解析后的所有值与未开启目标索引的历史示例逐项一致。
2. 首次与纠错提示的参考示例完全相同；批目标、SOURCE_DATA_JSON 和除参考示例外的文本与同输入的历史目标提示一致。保存改动前冻结核心的离线参考证据，不通过手写模拟完整提示冒充原生行为。
3. plan/receipt 的新 profile 一致；改变 profile、来源、目标或 prompt 并重算 hash 仍无法通过已有原生持久化完整性验证。
4. 以合成候选复现真实错误形状：声明字段移入 evidence，或同时出现在两个层级，仍由 schema v2 拒绝，不进入 admission、不写 semantic_claim；失败后的原始回执与费用仍保留。
5. 合法声明、后批失败、general_fact/episodic 独立行为保持已有回归；false 模式的历史提示 SHA 不变。
6. Python 仅验证已有 binding 能反映新 profile 并调用 C++，不编写字段重排或语义修复。

## 验证与真实执行的先后

先完成 R5.9 evaluator 的账本修复、完整本机回归与合同/质量审查，避免修改核心源码影响其正在运行的指纹检查。本设计随后经独立合同预审，写实施计划，再进入上述 RED 与最小 C++ 实现。编译的新库与历史 R5.9 冻结库分开保存。通过相关 C++/Python、全 CTest、原生原始响应兼容检查及独立质量审查后，才冻结真实探测配置。

真实探测先使用 Tomas、Mum、Kwame 的既有完整来源，按固定任务清单比较旧 R5.9 profile 与候选新 profile；每个任务都执行完整 holder 的 C++ 分批和 admission，不直接只请求有利批次，不复用旧答案充当 fresh 对照。具体任务次数、交错顺序、预算及放行门槛在实现完成后的独立探测设计中冻结，再调用 provider。阶段结果必须区分协议健康、语义保留和消费；不能把空数组的技术成功等同于语义能力恢复。

只有候选完整任务全部健康并保留有来源的 admitted claim，才设计统一新核心的八库 fresh 重建。旧 R5.9 失败目录不续跑、不覆盖；新八库全部通过后，继续既定 133 题、两检索臂、两回答政策和评分合同。首次完整分数仍称 baseline。若布局修改没有改善稳定性，报告阴性结果，再独立研究字段路径纠错或新 wire 协议，不叠加无界重试。

## 状态

C++ 已实施，候选两库探测2/2，八库建库3/8。实际执行偏离交错对照及隔离构建要求，测试覆盖也有缺口；不得视为原计划完整验收。详见 [R6.0 诊断与执行偏差](../../eval/2026-09-26-socialmem-r60-build-diagnosis.md)。
