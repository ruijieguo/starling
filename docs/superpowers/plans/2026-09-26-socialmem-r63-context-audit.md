# R6.3 上下文核验实施计划

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

按既有自主迭代授权执行；C++核心语义保持，修复Python到binding的参数类型。设计见[核验恢复设计](../specs/2026-09-26-socialmem-r63-context-audit-design.md)。

- [x] 定位R6.2失败：266个已完成检索、1336次embedding、字符串与枚举不匹配。
- [x] 先加入真实原生结构声明核验及缺行/篡改测试，保存RED。
- [x] 最小修复共享核验参数转换，保存GREEN。
- [x] 先编写恢复/零provider/篡改测试，再实现新入口和恢复证明。
- [x] 对真实封存产物离线恢复并独立检查，不重发检索。
- [x] 执行532个fresh答案并独立重算，分析配对成绩和失败。
- [x] 同步中文报告及全部设计文档状态。
