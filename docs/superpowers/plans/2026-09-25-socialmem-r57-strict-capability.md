<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.7 严格输出兼容性诊断实施计划

> 执行技能：superpowers:subagent-driven-development。遵循中文文档→失败测试→实现→合同审查→质量审查→一次真实诊断；已有自主迭代授权，不重复请求确认，不自动提交。

目标：用现有 C++ 原生能力探测，以最多 4 次 HTTP 核实指定模型 strict 合同兼容性。详细固定输入、停止条件与证据边界见[设计](../specs/2026-09-25-socialmem-r57-strict-capability-design.md)。

## 任务一：有界编排与失败证据

- [x] 新增 `tests/python/test_socialmem_r57_strict_probe.py`，先观察缺少入口时 RED，再分组加入调度、身份、成本与篡改反例。命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/python/test_socialmem_r57_strict_probe.py`；日志保存 `build/socialmem_20260925_r57_work/`。
- [x] 新增 `scripts/run_socialmem_r57_strict_probe.py`。实现 `run(out)` 与 `check(out)`，固定 prepare/core/model，复用历史 seal、冻结加载和持久预算工具；不修改冻结 builder 或核心。
- [x] 编排骨架为：`reserve(2) -> native.probe(admission) -> save -> settle -> verify`；仅通过后执行 `reserve(2) -> native.probe(extraction) -> save -> settle -> verify`；任意异常封存诊断并终止。成功与失败均允许只读 check 重算。
- [x] 补冻结 core 的本地 HTTP fixture：实际请求严格 schema、反指令 fixture、四请求成功与两请求停止、HTTP400 usage unknown、无 HTTP 的伪成功拒绝。外部模型请求为零。
- [x] 合同审查通过后再质量审查；发现阻断项先新增 RED，再最小修正、重跑对应测试。

## 任务二：真实能力结论

- [x] 在全新 `build/socialmem_20260925_r57_strict_probe/run` 执行一次 `run`，最多 4 次 HTTP；不得因能力失败重复调用或切换模型。
- [x] 独立 `check` 核验原生 evidence 与原始 HTTP/token/账本，保留完整错误与 unknown。
- [x] 新增中文 `docs/eval/2026-09-25-socialmem-r57-strict-capability.md`，记录兼容性结论及下一 C++ 修正选择，明确不是新增 QA 结果。
- [x] 同步所有设计/计划与两技术报告的中文状态入口，保留历史正文；运行 `git diff --check`。

完成记录（2026-09-26）：22项本机HTTP测试和独立合同/质量审查通过。真实2HTTP/494tokens，正向fixture根数组违反object schema，原生nonconformant；抽取探测未执行。独立只读审计与check一致，封存未变。详见[实测报告](../../eval/2026-09-25-socialmem-r57-strict-capability.md)。勾选代表计划执行及失败诊断完成，不代表strict能力通过。
