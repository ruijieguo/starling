<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.8 同一声明状态资格实施计划

设计：[中文设计](../specs/2026-09-23-socialmem-r48-state-claim-identity-design.md)。延续既有授权；核心只在 C++，先文档、再测试、最后实现。

- [x] 编写中文设计，明确相同声明条件、非状态关键词边界与评估停止条件。
- [x] 同步所有设计/规格/计划与技术报告的当前入口。
- [x] 增加交叉 sibling、词语绕过、无效 sibling 和正向控制测试；在未改生产代码时记录 RED，7 项中 4 项按预期失败，3 项控制通过。
- [x] 在 v6 合并状态资格条件，保持 v2-v5 和其他车道行为。
- [x] 定向 C++ 61/61；完整 CTest 1283 项（1260 通过、23 沙箱跳过）、HTTP 补跑 30/30；相关 Python 65/65。构建/安装核心哈希一致。
- [x] 独立 57 题零网络闭环（114 个终态），与 R4.7 同替身 embedding 比较：来源、statement、block 全不变，2 个原生 prompt 的 coverage 字段改变。
- [x] 按 2 个原生 prompt 变化触发真实复评：retrieval 18/57、native_answer 17/57，0 技术失败、547 请求；没有准确率收益，不晋升。
- [x] 写[中文诊断报告](../../eval/2026-09-24-socialmem-r48-state-claim-identity.md)、同步最终文档状态、核验 R4.7 与新目录封存。

## 当前验证记录

- 核心 SHA256：`4c5c964bf55df68f9997a38a16235ae414cd4ab84cf4d368d5361b00466e6593`。
- RED/GREEN：`build/r48_state_red.log`、`build/r48_state_green.log`。
- CTest/HTTP/Python：`build/r48_ctest.log`、`build/r48_http_ctest.log`、`build/r48_python.log`。
- 离线目录：`build/socialmem_20260923_r48_state_claim_offline`，已封存。
- 真实目录：`build/socialmem_20260923_r48_state_claim_real`。2026-09-24 完成 57/57 检索、114/114 正常回答；来源/block 全部不变，2 个原生 prompt 的 coverage 变化但判分不变。初次自动审批超时未执行，工具允许的一次重试通过；没有重复检索请求。
- 相对 R4.7，检索 -1 题、原生净差 0，所有正误互换发生在同 prompt 子集；3 轮自然重复裁判输入 31 组中 4 组不一致，不重写原分数。
- 事后 Q6 诊断：6 个公开锚点全部在候选池中，但全部未渲染且没有预算拒绝。只用于定位排序问题，不把锚点写入选择规则。
