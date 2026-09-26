<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.8 原生目标单元提示实施计划

> 执行技能：superpowers:subagent-driven-development。已有自主优化授权；中文设计→RED→C++实现→GREEN→合同及质量审查→有界真实验收，不自动提交。

目标：保留完整上下文，减少当前批次可引用来源索引的混淆；以独立小规模配对验收判断是否值得重新建库。事实依据及边界见[设计](../specs/2026-09-26-socialmem-r58-target-units-design.md)。技术栈为C++20、原生nlohmann JSON与现有GTest；Python仅pybind字段、配置编排和统计。

## 任务一：原生政策与目标提示

- [x] 先确认R5.6 evaluator最后一轮冻结核心测试及审查已结束，再开始任何现有源码/CMake修改；否则旧测试的live-source身份门槛会被误触发。
- [x] 新增`tests/cpp/test_claim_batch_target_units.cpp`并在测试CMake注册；用feature-detection助手在旧policy缺字段时产生明确RED，而非编译错误：`if constexpr (requires { p.claim_batch_target_units; }) p.claim_batch_target_units=value; else ADD_FAILURE()<<"native target-unit policy missing";`。
- [x] RED覆盖false默认原提示与plan兼容、true只索引本批且保留全文、第二批保留c8等全局编号、UTF-8/SourceTurn元数据、空批、非法policy、每批纠错、批外/截断/后批失败零提交、policy/profile/prompt/plan篡改拒绝与合法多批持久化。记录`build/socialmem_20260926_r58_work/native-red.log`。
- [x] 在`include/starling/extractor/statement_validator.hpp`增加`bool claim_batch_target_units=false;`，在`src/extractor/statement_validator.cpp`统一检查true要求semantic与batch>0；不在Python复制判断。
- [x] 在`include/starling/extractor/claim_contract.hpp`声明原生分批提示函数，在`src/extractor/claim_contract.cpp`共享静态合同片段并实现true的数据布局。原文继续保留；目标单元从原生units清单按精确全局ID选择，未知/重复目标抛异常，禁止字符串替换成品prompt。
- [x] `src/extractor/extractor.cpp`生成及完整性重放统一使用该原生函数；原有false路径逐字保持。policy快照比较纳入新开关，true的plan/receipt标记`target_units_v1`；默认false的旧输出形状保持。实际声明比较和成本持久化沿用原逻辑。
- [x] `src/memory/memory_ops.cpp`的两处general_policy归零同时设置新开关false，保持独立通道语义。写对应多通道失败/正常用例后再实现。
- [x] 编译并执行`build/tests/cpp/starling_tests --gtest_filter='ClaimBatchTargetUnits.*:ClaimBatching.*'`，日志保存`native-green.log`。随后只按变更影响扩大到原生合同/抽取/记忆通道测试与完整CTest，不重复无关网络测试。

## 任务二：薄绑定与配置

- [x] 先新增`tests/python/test_claim_batch_target_units.py`的RED：binding默认false与显式true、dataclass到policy映射、非法组合由原生拒绝、baseline helper映射、真实原生FakeLLM批次调用。Python不得生成/过滤claim或复制prompt规则。
- [x] `bindings/python/bind_06_extractor.cpp`增加字段暴露；`python/starling/extractor/config.py`增加dataclass字段及`to_policy`赋值；`scripts/run_socialmem_baseline.py`仅增`claim_batch_target_units=bool(config.get("claim_batch_target_units",False))`。
- [x] 构建并安装同一native候选，运行新Python测试及相关claim_batching、binding、baseline测试。历史冻结core测试需独立进程，不混装；若旧实验check按设计拒live源码变化，保留历史证据并使用其封存runtime，不改旧实验常量。
- [x] 独立合同审查后质量审查，新增问题先RED再修复。确认false基线兼容后冻结候选core SHA、源码、配置、CMake及验证日志。

## 任务三：真实配对验收编排

- [x] 先为独立入口编写中文子设计、失败测试，再实现编排；输入仅来自R5.6两个已封存来源，原生拆分/计划/提示/抽取/提交为唯一实现。采用同一新core的false/true对照，不混用旧core健康声明。
- [x] 固定6个holder任务、54请求上界、次序及停止条件按设计执行，拒覆盖/续跑；每次调用前预约原生计划上界，HTTP原文/usage/unknown、费用及DB提交证据均冻结。实现与测试先审查后发请求。
- [x] 真实终态逐项独立核对schema/目标/global IDs、回执、原始HTTP、成本与持久化；候选失败立即按设计停止，不用部分样本宣称可靠性提升。
- [x] 报告配对协议成功、拒收/保留与token差异及小样本局限。只有全部候选验收通过才另立新核心8库重建；本次不产生133题QA结果。
- [x] 更新中文诊断报告和全部设计/计划、两技术报告状态入口，核验链接及`git diff --check`。
