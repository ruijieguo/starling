<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.4：来源预算与声明干扰消融设计

日期：2026-09-25。状态：在用户“继续”及自主迭代授权范围内执行；先文档、再失败测试、最后实现。产品默认 bm25 保持，当前开发对照 v6，不自动提交前序工作。

## 背景与选择

R5.3 健康对照为 v6 51/104 来源锚点、v8 45/104；v8 独立来源预算有效，但同时把 86.3% 的选择交给词面相关路径，压缩时间链与成员覆盖。68 次声明渲染的代理审阅仅 18 次对当前题目有实质帮助。直接继续扩充谓词或重新调高词法分无法隔离退化原因。

本轮选用方案 A：新增实验策略 v9，完全复用 v6 来源选择顺序，仅采用独立来源预算及 v8 的严格 sidecar 准入。来源容量、声明追加分别比较。方案 B 是同时修改人物/事件相关性过滤，混入新变量，留到消融后；方案 C 是简单扩大原 hybrid 的 k，会同时改变检索候选及声明名额，不采用。

## C++ 合同

1. `source_strategy=evidence_profile_v9` 只支持 sources/hybrid。v9 的来源选择与同 k、同 byte budget 的 v6 sources 一致；保持 v6 的主体、主题、状态、归属、成员、时间和互动车道。不能进入 v8 的直接命中优先分支，也不能使用 v7/v8 semantic/event 来源排序。
2. v9 的 k 只限制来源，独立 sidecar 最多三条；共享总 UTF-8 byte budget，先来源后声明。分项字节严格求和，声明不能挤掉来源。
3. v9 hybrid 使用既有 planner 获取候选；sidecar 完全复用 v8 的合法 span、标识一致、当前 tenant/holder/as-of、已选来源、问题词项相关性和字节准入。此次不修改词表、抽取或相关性政策。
4. v9 sources 无需 planner/embedding：来源排序不消费语义向量，不渲染声明，无 embedding 请求、receipts 为空；这不称为语义检索健康，而是原生来源路径。其来源与 v9 hybrid 一致。
5. 共享 sidecar 渲染与计数逻辑，不复制 C++ 实现，不在 Python binding 增加决策。v6/v7/v8 和 bm25 的既有行为不变。

## 预注册评测

固定 R5.0 的 7 个 runs/frozen.db、57 题/6 networks、同一新 core，问题时间/模型/提示/评分沿用 R5.3。四组：

| 组名 | 策略/模式 | k | 作用 | 嵌入请求上限 |
|---|---|---:|---|---:|
| baseline | v6 hybrid | 10 | 当前健康开发对照 | 345 |
| source7 | v6 sources | 7 | 与对照的来源部分核对 | 0 |
| source10 | v9 sources | 10 | 预先指定的 QA 候选 | 0 |
| sidecar | v9 hybrid | 10 | 与 source10 同来源、额外声明的诊断组 | 345 |

四组 228 条检索回执，最多 690 次 DashScope 查询嵌入、零重试。sources 组仅构造不会被调用的 Stub adapter 以满足构造接口，不用伪向量参与任何排序；通过 receipts 为空及实际调用为零验证。禁止覆盖历史产物，源码/core/配置/逐题回执全量封存，原库复制后查询并前后重验。金标仅用于检索后统计。

来源消融需核对 baseline 来源与 source7 是否一致，并比较 source7→source10 的锚点得失；声明消融需核对 sidecar 与 source10 的来源引用、来源文本和来源字节完全一致。来源扩容不预设集合单调性，如发生替换须逐题记录，不能只报告总数。

## QA 门槛及归因

在看到本轮结果前，将 **source10** 指定为唯一 QA 候选：无 sidecar、所有身份/时间/预算及封存检查通过、来源锚点不少于 baseline、至少一题上下文确实变化、baseline 全部 embedding 健康。满足后执行 baseline/source10 两臂×legacy/grounded_memory_v1，固定 qwen3.8-27B、回答512、裁判64、thinking=false、零重试、500次请求预算。失败计零，保存请求账本及逐次回执，不能复用历史 QA 得分。

source10 不产生声明，声明相关性指标应为“不适用”，不能记作100%或拿空分母满足 R5.3 的0.8门槛。sidecar 组仍是诊断臂，本轮不进入 QA、不因来源门槛通过自动晋升；其原人工相关性门槛不放宽。baseline/source10 的 QA 差值是“增加来源并去掉声明”的组合效果，不能归因于单独预算或声明因素。source7/sidecar 检索消融只能提供机制线索，不是各因素的 QA 因果效应。

QA 若执行，报告共同正常子集、四格转移、network bootstrap 95%区间、技术失败、相同提示/回答的裁判翻转和成本。至少一policy共同正常净增≥5题且网络区间下界>0，才允许讨论扩大开发验证；不自动改变产品默认，不外推全量/保留集。若门槛失败，报告停止点及未执行的请求。

QA 实现前明确既有协议：上述 thinking=false 指 `answer_enable_thinking=false`；裁判沿用冻结 `_make_native_adapters`，未显式设置 enable_thinking，不在本轮修改该行为。`judge_max_tokens=64` 是原请求参数，不能据此断言供应商实际推理/总 completion token 上限为64。只调用 answer/judge 方法；未使用的 extract/embed adapter 构造不产生请求。所有实际 usage 以原始响应为准。

## 测试与文档

- 先写 v9 未注册导致的 RED：v6 sources 等价、真实声明正向追加、来源不被sidecar占位、source-only不运行planner、byte边界、非法span/身份/时间/擦除继承、旧策略不变。
- Python只验证策略透传；runner先测四组固定参数、无降级伪健康、完整manifest/哈希/终态、拒覆盖、失败请求落盘、source7/source10/sidecar正确配对及QA门槛。
- QA编排若门槛通过才实现；先失败测试覆盖配置/上下文漂移、重复/缺失题、拒覆盖、异常收费和候选减对照的统计方向。
- 最终同步全部中文设计文档及技术报告，新增本轮报告，历史分数不改写。

## 实施前置修正：声明有效期一致性

RED阶段发现既有planner语义支路未对声明valid_from/valid_to执行as-of过滤，而statement_main已有 valid_from<=as_of、valid_to>as_of 合同。仅来源话轮时间合法不能证明声明当前有效。本轮先修复该遗漏：semantic候选按与结构化路径相同的声明有效期合同过滤，来源profile的claim metadata也使用相同边界，空边界保持无界。此为核心安全过滤，不把observed_at来源时间当作valid_from，不引入新的事件时间推断。

因此“旧策略行为不变”限定为既有合法时间数据；未来/过期声明属于被修复的错误行为。先补未来生效、过期/结束边界、当前有效和空界对照RED，再做C++修复，比较各策略同一新核心。baseline必须新生成，不能混用修复前上下文。

## 首轮预检恢复记录

首轮预检已发送8次嵌入，其中sidecar一名holder发生embedder_unavailable，按门槛封存incomplete并停止批量任务。另建`_retry1`目录重建完整四组，不把旧降级回执混入质量统计；本次仍最多690次，本轮累计上限698次。每次HTTP无自动重试，评测启动重试单列一次。


## 实施与评测最终状态

本轮已完成文档→RED→C++实现→GREEN→独立审查→真实检索→fresh QA→独立验封。四臂228条检索回执全部健康，baseline/source7为51/104锚点，source10/sidecar为67/104；两个来源控制一致，source10通过事前QA门槛。C++全量1,312/1,312、相关Python140/140（QA合同31项）通过。

fresh QA的legacy为18/57→23/57，grounded_memory_v1为18/57→25/57；共同正常子集分别净增5题和6题，network bootstrap 95%区间下界分别1.41和4.76个百分点，两policy都通过扩大开发验证门槛。228条QA终态中222正常、6次grounded回答截断；398次answer/judge，账本零悬挂、零重试。source10无声明的相关性仍“不适用”；sidecar仍仅诊断。

这些结果仅属于57题开发cohort、“增加来源并去掉声明”的组合效果。发现一组相同judge输入翻转，主评分不改写；完整成本、误差和归因边界见本轮中文评测报告。下一步冻结v9扩大开发验证，尚未执行，不自动修改默认、不自动提交。全部设计/计划及技术报告345份同步当前中文状态入口。
