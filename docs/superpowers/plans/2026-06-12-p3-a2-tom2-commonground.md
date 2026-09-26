<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# P3.a2 二阶 ToM + CommonGround 补完 Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> 状态:**已完成**(2026-06-12,inline)。ctest 563 / pytest 594 全绿;真模型
> gated 评测命令记 admission report §6。执行中追加发现:tom_inferred 采样
> 因子 0.25 × 中性 salience 0.0144 < w_min——嵌套行永不巩固,修为 salience
> 继承(源 ×0.8);嵌入式 cognizers 表为空(self 行只在 demo 种子里),
> 自动二阶触发面=多 holder 写入,e2e 程序化种行验证。
>
> 原计划状态行:执行中(2026-06-12,inline)。前置探查实测,起点比 spec 字面好:
> perspective_take / ToMDepthEstimator.estimate(缓存+TTL)/ 4 of 7 mentalizing /
> CG 五幕(assert/ack/repair/withdraw/supersede)+ N=3 共同在场 + 24h sweep
> **均已实现**。本里程碑只补真缺口并接线。

**Goal:** 二阶信念的程序化生产-治理-查询闭环(估计器调制 + 双限流 + META_BELIEF 数据底座)+ CommonGround 七幕齐全且事件联动 + 二阶 ToM 准入评测(precision > 0.70,fixture 离线 + 真模型 gated)。

**实测缺口清单(全部有 file:line 锚点):**
1. CG 缺两幕:`expire_ground` / `unground`(writer 五幕已在,含 supersede/sweep)。
2. `sweep_timeout_downgrade` 已实现已绑定**但生产零调用**(订阅者不跑)。
3. `statement.superseded` 在 belief_tracker 是 no-op、CG 订阅者不消费——spec「ConflictProbe superseding → SupersedeGround(主触发器)」断线。payload=`{old_stmt_id,new_stmt_id}`(arbitration.cpp:488,event primary=new_id)。
4. `CommonGroundContainer::rebuild` 不按 parties 过滤(container.cpp:70 SELECT 无 parties 谓词)——P2.j 遗留,单 pair 假设下全租户镜像。
5. 双限流缺链长半边:rate_limiter 只有 10min 窗口;`derived_depth>=3`/链长检查无实现。
6. 估计器无 driver:`estimate()` 没有任何消费者,不调制持久化深度。
7. **depth>=1 语句生产端缺位**:LLM 抽取一律 object_kind="str"(2026-06-11 裁定),NestingDepthWriter 的程序化路径无生产调用者——META_BELIEF intent(P3.a1)查的是永远为空的集合。
8. mentalizing 缺 3:`what_does_X_think_Y_believes` / `predict_X_would` / `who_committed`。
9. 人工确认(grounded 规则#4):acknowledge 有 actor 参数但 audit_actor 列语义未明确(实现时核对补齐)。
10. 二阶准入评测:eval_tom_bench.py 只有 FIRST_ORDER_ABILITIES 子集(阈 0.55);二阶子集+阈 0.70 待加。

**判读(不补的):** grounded 规则#3(M=2 重复确认)已被订阅者「同命题异方 → acknowledge」路径覆盖(subscriber.cpp:119-121,#1/#3 同路),文档注记而非重复造计数器。

**裁剪登记:** dashboard ToM/CG 面板 API(/api/tom/*)不在本期(roadmap a2 出货项未列 UI;归 backlog);`predict_X_would` v1 返回**预测依据**(beliefs/prefs/commitments 结构化集合)而非编造性预测文本(LLM 模拟归 P3+);depth=2(三阶视角链)持久化仅在估计器 order=2 时放行,本期生产路径产 depth=1(self 给 partner 信念建模),depth=2 留显式 API。

---

## Tasks

1. **CG 两幕补全**:writer `expire_ground`(grounded→expired,expired_at=now)+ `unground`(grounded→suspected_diverge)+ grounding_acts 审计行;`acknowledge` 人工确认核对(audit_actor 列落值)。测试扩 test_common_ground_writer.cpp。
2. **订阅者接线**:tick_one_batch ①末尾跑 `sweep_timeout_downgrade`;②事件 SELECT 扩 `statement.superseded`,对 old_stmt 的 grounded 条目逐个 `supersede_ground`(新建 cg 条目交由 new_stmt 的 statement.written 既有路径)。测试扩 test_common_ground_subscriber.cpp。
3. **rebuild parties 过滤**:`cg_ref` 含 `::` 时解析 sorted-pair,SELECT 加 `parties_json LIKE '%"a"%' AND parties_json LIKE '%"b"%'`;不含 `::` 保持旧全租户行为(向后兼容,旧钉测不动)。测试扩 test_common_ground_container.cpp。
4. **双限流 limiting**:`tom/limiting.hpp/cpp` `should_persist_tom_statement(conn, tenant, holder, subject, predicate, canonical_hash, derived_depth, causation_chain_len, as_of)`:链长(derived_depth>=3 ‖ chain_len>=3,对齐 Bus 深度帽)→ 窗口(复用 rate_limiter)。新测试 test_tom_limiting.cpp。
5. **二阶程序化写入**:`tom/second_order_writer.hpp/cpp` `maybe_persist_second_order(adapter, conn, ev_tenant, stmt_id, now)`:读源语句(holder=X);X==self/源已是 tom_inferred/depth>0 → 跳过;self=cognizers.kind='self';估计器 gate(estimate(X)>=1 允许 depth1;depth2 仅显式 API)+ 双限流 → `StatementWriter` 写 holder=self/subject=X/predicate='believes'/object_kind='statement'/object=stmt_id/provenance=tom_inferred(NestingDepthWriter 自动算 depth=1)。挂 belief_tracker 的 statement.written handler(泵内,自产事件因 holder=self 收敛)。新测试 test_second_order_writer.cpp。
6. **mentalizing 三 API**:`what_does_X_think_Y_believes`(嵌套行 JOIN 内层)/ `predict_X_would`(PredictionBasis{beliefs,preferences,commitments},LIKE 关键词)/ `who_committed`(commitments JOIN statements,object LIKE)。测试扩/新建。
7. **绑定 + Python 面**:bind_08 扩(expire/unground/limiting/second_order/三 API);`python/starling/tom/__init__.py` re-export;pytest e2e(remember 双 holder → 泵产 depth1 → `Memory.query(intent="META_BELIEF")` 命中——a1×a2 闭环钉)。
8. **二阶准入评测**:eval_tom_bench.py `--order second`(SECOND_ORDER_ABILITIES + threshold 0.70)+ fixture 测试;admission report 补 gated 行。
9. **文档 + roadmap + 全量门**(09_tom 实现补记/附录 H/roadmap a2 行;ctest+pytest+scan+前端不动)。

**验收:** 双 holder 对话写入后,无人工干预产生 depth=1 二阶语句(估计器+双限流过闸);`META_BELIEF` 检索返回它们;CG 七幕审计齐全、超时降级与 superseding 联动自动运行;二阶评测 fixture PASS(阈 0.70)。
