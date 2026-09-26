<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.6扩大建库实施计划

> 执行技能：superpowers:subagent-driven-development，按文档、失败测试、实现、合同审查、质量审查、真实运行的顺序连续执行。用户已授权，无需重复确认，不自动提交。

目标：使用已验证的新C++分批能力，以相同模型和统一配置重建新增133题的全部8库，恢复后续对照评测。

架构：Python只映射配置、调用原生planner/流水线、冻结证据及统计成本；C++负责全部分批、解析、准入与持久化。复用现有纯编排helper，独立R5.6身份合同，旧R5.5历史封存不变。设计见[详细合同](../specs/2026-09-25-socialmem-r56-expanded-rebuild-design.md)。

## 任务1：入口与薄映射

- [x] 在`tests/python/test_socialmem_r56_expanded.py`先添加失败测试：`_build_extraction_config({}).claim_batch_size == 0`及显式8生效，固定原生预算65 holders/197批/851上界，拒覆盖和配置/身份篡改，RED日志保存到`build/socialmem_20260925_r56_work/`。
- [x] `scripts/run_socialmem_baseline.py`增加`claim_batch_size=int(config.get("claim_batch_size", 0))`。
- [x] 新增`scripts/run_socialmem_r56_expanded.py`的prepare/build/check，不提供未实现的retrieve/qa。prepare冻结新runtime和原生预算，build串行新库调用，check重算健康/账本/来源链，具体字段及边界遵循详细合同。
- [x] 添加真实core+FakeLLM的分批helper集成、失败快照、raw usage和重新封印后的篡改反例，分别执行`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/python/test_socialmem_r56_expanded.py`、`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/python/test_claim_batching.py`、`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/python/test_run_socialmem_baseline.py`；新增52/52、binding4/4、baseline19/19通过。历史baseline smoke与当前core测试必须独立进程，不能削弱frozen模块隔离；baseline中的本机HTTP测试需允许loopback监听，外部请求仍为0。真实native非空集成实际持久化2条声明，仍为Fake/Stub技术用例，不是模型评分。
- [x] 独立合同审查通过后独立质量审查，发现缺陷先补RED再修复；最终均通过，不修改C++或已封存probe。

## 任务2：真实建库

- [x] 运行新入口prepare至全新`build/socialmem_20260925_r56_expanded/prepare`并在独立进程check；0请求、源码/core对应和65个原生计划均通过，seal为`4aca92fe8eca1615fd7fe65a66d7cf28048f4ac789aa676367acc5ac4bda1577`。质量复核通过后才启动真实build。
- [x] 冻结源码/依赖后启动build至同父目录`build`；最多12000账本单位、抽取保守851，禁止自动重试和覆盖。运行已因Mum两次协议失败终止，0/8完整健康；该勾选表示执行终止，不代表建库通过。
- [x] 失败后保留全部回执和费用，独立离线check及审计终态：517个build文件、506个prepare文件前后哈希一致；23次chat/191907tokens及3次原生embedding计数，embedding tokens未知。保守账本43，实际本地请求计数26。审计见`build/socialmem_20260925_r56_work/expanded-real-audit.md`，无新增API调用。
- [x] 更新R5.6主报告、实施复选项及中文文档状态入口；健康8库、后续检索/QA仍未完成。严格模式兼容性诊断另见[R5.7计划](2026-09-25-socialmem-r57-strict-capability.md)。
