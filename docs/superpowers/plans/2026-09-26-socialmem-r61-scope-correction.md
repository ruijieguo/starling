# R6.1 来源纠错实施计划

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

**目标：** 修复目标批次越界后不使用已有纠错额度的问题，并用完整 holder 的真实对照验证。

**架构：** C++ 共用错误分类决定有界重新生成和原生回放；Python 仅隔离运行、封存和统计。

**规格：** [中文设计](../specs/2026-09-26-socialmem-r61-scope-correction-design.md)。按现有自主执行授权在本会话顺序实施，不启动新子代理。历史产物保持。

## 任务一：原生合同修复

- [x] 写入 R6.0 终态诊断和本设计，同步设计状态入口。
- [x] 在 `tests/cpp/test_claim_batch_target_units.cpp` 新增成功纠错、额度共享、后批耗尽、失败成本及防篡改用例。先运行旧实现并保存真实 RED 输出。
- [x] 在 `src/extractor/extractor.cpp` 添加私有 `retryable_claim_protocol_error(kind, policy)`，条件为 envelope/schema，或目标分批模式的 batch_scope_failure；抽取和完整性回放共用。
- [x] 在独立构建目录编译候选，运行聚焦和全量 C++。保存命令、退出码、发现/通过/跳过数及 core SHA；不覆盖现有 Python runtime。

## 任务二：完整 holder 探测

- [x] 为新入口先执行七项 RED；随后真实双核心 fixture 验证回放、篡改拒绝、usage缺失停止、失败封存和无请求check。预算固定30并有上界检查；未新增额度不足的专门fault fixture，不能称该项已覆盖。
- [x] 新建 `scripts/run_socialmem_r61_scope_probe.py` 及测试，复用已有原生回放/HTTP 解析工具，不复制抽取规则。固定四任务、两 runtime、完整来源、原生预算及失败封存。
- [x] 执行离线测试后冻结配置和源码，按设计运行 DashScope 四任务，再在独立进程 check。报告协议健康、非空准入、语义拒绝与消费，不报告 QA 提升。
- [ ] 更新本计划、设计、诊断报告及所有设计状态入口。两候选任务通过后进入统一八库新建库准入设计。

## 实际结果

原生36/36、完整C++1362/1362、Python binding9/9、探测10/10通过。第一轮1次空响应，远端执行和token未知；第二轮四任务健康、候选两任务非空，18HTTP/200561tokens，未触发纠错。详见[R6.1报告](../../eval/2026-09-26-socialmem-r61-scope-correction.md)。八库准入按独立设计与测试推进。
