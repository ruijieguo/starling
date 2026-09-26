<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.0 语义证据回链与事件邻域实施计划

设计：[中文设计文档](../specs/2026-09-24-socialmem-r50-semantic-event-evidence-design.md)。执行顺序固定为中文设计 → RED → C++ → 回归 → 离线消融 → 真实复评 → 分析；核心逻辑只在 C++。

- [x] 完成现状诊断：statement 语义分数和 source span 已存在，但 v6 source profile 未消费。
- [x] 写中文设计，固定 source key、同 session 连续邻域、v7 lane 顺序、回退与晋升条件。
- [x] 补充来源登记与抽取复用 engram 身份的约束，避免同 payload 的 `ladder` 副本使严格回链全部失配。
- [x] 在 C++ 测试中写语义回链、最高分、身份隔离、事件邻域和缺失回退 RED。
- [x] 实现 `evidence_profile_v7` 的 source span 回链与同 session 有界 event lane。
- [x] 在 Python 编排测试中锁定 source-turn 登记与 holder 抽取的 adapter/prefix 身份一致性。
- [x] 运行定向 GREEN、完整 CTest、HTTP 补跑和 Python 回归。
- [x] 使用相同冻结库和替身 embedding 完成 v7 对 v6 的零网络 source/block 消融；另以真实 qwen embedding 完成可用语义信号消融。
- [x] 离线上下文已改变且合同无回归，已预注册 v7 并完成一次 DashScope 真实双臂复评。
- [x] 新鲜来源身份验证需要重新抽取时，使用独立 2000 请求上界；抽取、嵌入、共享检索、legacy/native 回答和裁判分别记账。
- [x] 生成中文评测报告，分析语义回链收益、事件混淆、裁判稳定性及未达门槛原因。
- [x] 同步设计入口、规格、计划和技术报告顶部当前契约，并保留评测目录、provenance 与产物哈希。

## 预期不变量

- 默认策略、v2–v6 行为和已封存目录不改写；
- source key 只接受严格 `engram_ref + clause_id`，不按文本或 session 猜测；
- 事件邻域不跨 session/holder，不跳过缺失 turn；
- 不新增 source embedding 请求，Python 不包含排序或语义回链实现；
- 所有真实分数、锚点、裁判输出和原始回答保留首次结果，不能用诊断结果覆盖。
