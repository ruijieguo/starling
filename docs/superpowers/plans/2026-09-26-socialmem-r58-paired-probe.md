<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.8 配对原生验收实施计划

> 使用superpowers:subagent-driven-development，先文档再RED与编排实现，合同/质量审查后仅启动一次有界真实run，不自动提交。

目标及精确边界见[子设计](../specs/2026-09-26-socialmem-r58-paired-probe-design.md)。核心prompt、planner、抽取、准入与持久化已有独立C++任务负责，本任务仅编排。

## 任务一：固定输入、调度与离线复核

- [x] 新增`tests/python/test_socialmem_r58_paired_probe.py`，先因缺少独立入口RED，再分组新增固定seal/payload/core漂移、现有目录、6任务54上界、A协议失败可继续而B失败停止、unknown上界结算、partial终态只读check、重新seal改任务/summary/ledger拒绝用例。日志写`build/socialmem_20260926_r58_work/`。
- [x] 新增`scripts/run_socialmem_r58_paired_probe.py`的prepare/run/check。固定两来源与调度在代码中，不复用历史runner内硬编码Kwame或旧core的整体验证，也不修改旧模块常量。可复用seal/inventory、frozen runtime、BudgetLedger及真实响应统计等纯编排helpers；实际依赖一并冻结。
- [x] prepare要求调用者显式传入已审查candidate SHA，原生生成A/B计划；Python只核对实验规模、选择开关并冻结，不计算来源分批或生成提示。
- [x] run按任务新建临时库、预约预算、调用现有原生memory_*、保存回执和commit、SQLite backup、按raw HTTP结算，保存正常/失败/未执行状态。无外部模型重试或自动续跑。
- [x] check从固定来源和冻结core重建task/plan，FakeLLM回放原生语义与commit，用原始HTTP重算费用，逐预约对账；不发provider请求，不改变原DB或封存文件。
- [x] 等新核心GREEN后补真实native/Fake/Stub或本机HTTP集成测试：两臂profile差异、非空声明持久化、批外失败0semantic、缺usage不得通过。所有本地模拟证据明确不算真实模型支持。
- [x] 独立合同审查后质量审查，发现缺口先RED后修正。不得让编排测试修改仍在验证的C++或旧builder源码。

## 任务二：一次真实运行与解释

- [x] 核验候选C++/binding测试和独立审查通过，记录core SHA、源码与实际验证日志；在全新目录prepare/check。
- [x] 运行固定6任务、总上界54的串行run，按照设计停止条件执行；全程不启动8库或QA。
- [x] 终态独立check及HTTP/DB/费用审计，保留未执行项、partial/unknown边界；不将CLI失败退出码误认为审计异常。
- [x] 更新中文R5.8诊断报告及全部状态入口，明确是否满足3个候选验收门槛、A/B差异与下一步；没有QA时不报提分。
