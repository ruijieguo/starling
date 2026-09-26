<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench 结构化评测接线实施计划

目标：在不复制 C++ 语义的前提下，把版本化结构化抽取和声明检索接入一个 57 题受控开发对照。

- [x] 中文设计文档完成并冻结边界。
- [x] 先写并运行 RED 测试：默认抽取行为保持；显式结构化配置必须传入原生 policy；sources/statements 只改变 C++ ObserverQuery mode。
- [x] 实现 `eval_ladder.make_real_extract_fn` 的可选 `ExtractionConfig` 透传。
- [x] 将来源运行器的结构化策略配置透传到同一 C++ 三相抽取入口。
- [ ] 创建 `scripts/run_socialmem_structured_eval.py` 的双臂 prepare/check/run 入口和独立 manifest。
- [ ] 运行离线编排 guard 和 binding 回归。
- [ ] 生成两臂独立 manifest，执行固定 `qwen3.8-27b` 对照。
- [x] 分析完整分母、失败类别、tokens、逐题差异和 bootstrap；首轮未达晋级门槛，保留诊断状态。
- [ ] 按唯一失败假设新增 `statements_fenced` 候选 arm，只打开 C++ `claim_allow_code_fence`，完成同口径复测。
- [ ] 若 fenced 诊断确认纯声明上下文不足，复用其冻结数据库新增 `hybrid_fenced`，只改变 C++ `ObserverQuery.mode` 并分析跨轮证据恢复。
- [ ] 对 `hybrid_fenced` 未晋级结果继续做 `hybrid_dialogue` 单变量检验，只改变 C++ `source_strategy`。
- [x] 诊断 `hybrid_dialogue` 的 57 个查询失败：确认均为 `ValueError: invalid observer query`，定位到非 `bm25` 来源策略被旧校验限定为 `mode=sources`。
- [ ] 更新 C++ 查询合同：允许 `mode=hybrid` 搭配聚焦来源策略，保持 `mode=statements` 的拒绝边界；先补 RED 测试，再实现。
- [ ] 复用 `hybrid_fenced` 冻结数据库重跑 `hybrid_dialogue`，核对技术失败、账本和配对 bootstrap，决定是否进入下一轮谓词覆盖优化。
- [x] 完成 C++ 合同修复后的 `hybrid_dialogue` 重跑：57/57、17 正确、技术失败 0；`dialogue_added_sources` 全部为 0，确认默认 `source_seed_k=10` 与外层 `k=10` 没有留下扩展容量。
- [ ] 新增独立 `hybrid_dialogue_expanded` 配置（seed_k=5、seed_bytes=4000、radius=2），先写守门 RED，再透传到 C++ `ObserverQuery`，复用同一冻结 scope 数据库完成 57 题回答/裁判。
- [ ] 对 expanded 候选单独报告邻句新增分布、技术失败、格式/网络分层和配对 bootstrap；不与 `hybrid_dialogue` 或 `hybrid_fenced` 合并晋级。
- [x] `hybrid_dialogue_expanded` 完成：57/57、15 正确、技术失败 0；57 题均新增 5 条邻句，但相对来源净增 0，bootstrap 95% 区间 `[-5.26%, +4.76%]`，关闭该参数方向。
- [ ] 下一阶段转向结构化谓词覆盖诊断：按 scope 统计原生 extraction/admission 失败类别、结构化声明谓词分布与查询命中率，先更新中文设计与 RED 测试，再决定是否扩展 C++ 目录或 admission 规则。

## 2026-09-20 后继诊断

按 scope 的离线诊断已完成，发现一个 source_only scope 混入结构化实验及14条声明全部缺会话时间元数据。相关中文设计、原生拒绝分类与评测门禁已按 RED→GREEN 补齐；见[诊断报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。旧未勾选项保持原执行记录，不以本次诊断替代真实完整 baseline。
