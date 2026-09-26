<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.6 分批声明抽取实施计划

日期：2026-09-25。使用superpowers:subagent-driven-development；中文文档→失败测试→实现→独立合同/质量审查→评测。已授权范围内连续执行，不自动提交。

设计见[原生分批设计](../specs/2026-09-25-socialmem-r56-bounded-claim-design.md)。

## 一、原生能力与binding

- [x] 先新增C++失败用例，覆盖设计验收矩阵，记录编译或行为RED。
- [x] 实现原生batch planner、目标prompt/parser、分批执行、完整性验收、全批写入和成本回执。
- [x] 增加ValidationPolicy及Python配置的薄映射，general_fact清零分批配置；无Python分段算法。
- [x] 聚焦C++/binding测试GREEN，再跑必要完整C++回归和相关Python通道/证据测试，独立合同与质量审查。

## 二、同输入真实验收

- [x] 新目录冻结当前核心、源码、模型与参数，用原生planner计算Kwame5批、belief最多15请求；先实现入口失败测试，再编排。
- [x] 已授权DashScope真实抽取；固定8192、120000ms、batch_size=8、HTTP retry0；5批完成、15条入库、10HTTP/219586tokens，无截断，正式离线check通过。
- [x] 独立核验输入、计划、账本、全部终态、证据跨度和持久化；10条原始响应在冻结C++核心离线回放逐字段一致，新增HTTP0；只得出可靠性诊断结论。

## 三、扩大开发评测

- [ ] 单holder验收通过后，另冻结8库重建方案与入口测试；[设计](../specs/2026-09-25-socialmem-r56-expanded-rebuild-design.md)及[实施计划](2026-09-25-socialmem-r56-expanded-rebuild.md)已写，正在先测试后实现；原生65 holders上界851，不混用旧健康scope。
- [ ] 完整8库技术门槛→266检索终态→532fresh QA；按R5.5预注册统计对照和技术失败，旧57题分开。
- [ ] 同步所有设计文档与技术报告中文状态；详细记录真实请求、用量缺失与未执行阶段。
