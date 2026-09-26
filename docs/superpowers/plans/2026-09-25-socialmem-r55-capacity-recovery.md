<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.5 抽取容量恢复实施计划

> 使用superpowers:subagent-driven-development与测试驱动流程；既有自主迭代授权持续有效，不自动提交。

目标：用严格绑定的单次原生抽取请求，确认Kwame的截断能否由合理输出容量解决。
架构：冻结R5.4 C++负责请求合同与claim解析；Python仅做来源身份、编排、预算和封存。
合同见[恢复设计](../specs/2026-09-25-socialmem-r55-capacity-recovery-design.md)。

## 任务一：独立容量预检

- [x] 新增 `tests/python/test_socialmem_r55_capacity_probe.py`：先测输入篡改零请求、绑定失败prompt/payload/core、16384/240000/重试0/单次上限、错误与截断终态、原生parse结果、拒覆盖，保存RED。
- [x] 新增 `scripts/run_socialmem_r55_capacity_probe.py`，复用原生StructuredOutputRequest(ClaimExtractionV2,JsonObject)、LLMAdapter.extract_with_contract及claim_parse_response。读取失败scope中Kwame的source engram payload，用C++重建原始prompt逐字核对。
- [x] 使用持久BudgetLedger上限1，返回原始响应与C++解析JSON；seal完整依赖与绑定输入。失败不删不覆盖，不把Python JSON修复当成功。
- [x] 跑同一测试GREEN，独立审查，并用真实冻结core做离线输入验证。

## 任务二：真实预检与结论

- [x] 按既有DashScope授权执行一次真实请求，保存原始usage和terminal状态；核对账本及封存。
- [x] 更新R5.5报告，分别报告首轮75次请求和本预检请求，不增加QA分数。
- [x] 若成功，另写统一16384抽取容量的完整8库恢复方案；若失败，停止继续加额度，转向C++有界分段设计。所有设计/计划与两技术报告同步中文状态入口。
