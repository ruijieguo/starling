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

# P2.o 运行时闭环(写→读真正闭合)实现计划
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> 状态:**已完成**(2026-06-12)。ctest 536(+3)/ pytest 587(+5) 全绿;e2e 钉测
> `tests/python/test_runtime_loop.py`。执行中追加发现**根因之二**(见 §1-1.5):
> 出生 salience 硬编码 0.0 使重放采样权重恒 0——即使泵接通,巩固也永不发生;
> 修为中性 affect 公式值 ≈0.0144(`affect::salience(AffectVector{})`,单源)。

**Goal:** 让「界面记住一段内容 → 一个维护周期内 recall 能召回它」无人工干预地成立;出箱积压收敛;投影/信念/再巩固/在线回放在生产写路径上真正运行。

## 1. 根因(实测,2026-06-12)

1. **写后泵生产零调用。** 五订阅者泵(conflict_key / belief_tracker / reconsolidation / projection / replay_online,`src/bus/subscriber_pump.cpp`)唯一生产挂点是 `Bus::write` 尾部(`src/bus/bus.cpp:642`),而 `Bus::write` 在生产代码无调用者——remember 路径 = `append_evidence`(无泵)+ `Extractor`→`StatementWriter`(无泵)。后果:真实写入时投影滞后、信念/再巩固/在线回放静默缺席。
2. **出生 salience 锁死巩固(执行中发现)。** `StatementWriter` 硬编码 `salience=0.0, affect_json='{}'`,而 `sample_weight` 直接乘 salience → 生产语句采样权重恒 0(< w_min 0.01),Replay 永远采不到——泵接通了也不巩固。活库 17 条 volatile 全部 salience=0 实证。spec §3.9「写入打分」意图是 affect 公式打分,中性向量应得 0.4·0.4·0.3·0.3·1.0 ≈ 0.0144(刚过门槛:中性记忆排队最末,但不是永不巩固)。
3. **周期维护缺位。** `memoryops::tick_all` 只跑 embed + policy + common_ground;`ReplayScheduler::run_idle` / `sweep_volatile_ttl` / `enforce_oscillation_guard`、`ProjectionMaintainer` 兜底、`OutboxDispatcher` 在应用层零接线(仅 `__init__.py` re-export)。
4. **dashboard 无自动 tick**,全靠手动按钮。

直接用户可见后果:remember 的语句永滞 volatile ⇒ recall 永不可见(演示数据全靠 seed 手工置 consolidated);`bus_events` pending 单调增长(实测 174);认知体/承诺投影需手工 drain。

## 2. 关键决策

- **D1 泵宿主归位 `memoryops::remember`**:extractor 跑完后(accepted/idempotent 分支)调一次 `SubscriberPump::run_post_write(adapter, conn, now_utc)`,now 用调用方参数(确定性、可测)。`Bus::write` 尾部泵保留,直调 API 语义不变。
- **D2 `tick_all` 扩展(组合逻辑居 C++,per §2.0 边界规范)**:embed → policy → CG(现有)之后追加 replay 维护(oscillation guard → volatile TTL sweep → `run_idle`)→ PM 兜底批 → OutboxDispatcher。
- **D3 嵌入式 dispatch 语义**:单进程无外部消费者;五个进程内消费者全部按 `consumer_checkpoints` 推进且 SELECT 不过滤 `dispatch_status`(实测核验),故 Accept-all 消费者(`consumer_id="in_process"`)把 pending 收敛为 delivered=「进程内交付完成」是安全且诚实的。语义记入 05_bus。
- **D4 dashboard 后台调度线程**:`DashboardConfig.tick_interval_s`(默认 30.0,0=禁用);engine 起 daemon 线程,持引擎锁调 tick,结果非零时 WS 广播;app lifespan 启停。
- **D5 `TickOutcome` 扩展**:原 {embedded, fired, broken, auto_withdrawn} + {replay_sampled, consolidated, ttl_archived, projected, dispatched}。dashboard commands 的钉键测试同步更新。

## 3. 任务

1. C++:`memory_ops.cpp` remember 尾接泵;`tick_all` 扩展 + `TickOutcome` 新字段;`test_memory_ops.cpp` 扩(泵生效:1 次 remember 后 online counter=1、3 次后窗口触发且有语句巩固;tick_all:volatile→consolidated、pending→delivered、投影兜底)。
2. 绑定:`bind_13_memory_ops.cpp` 返回 dict 加新键。
3. Python:dashboard config 字段 + engine 后台线程 + app lifespan 接线;commands 钉键测试更新;新增 e2e `test_runtime_loop.py`(remember→tick→recall 命中,全栈钉)+ 调度线程测试。
4. 前端:queues/tick 反馈兼容新键(尽量零改)。
5. 文档:05_bus(泵宿主 + in_process dispatch 语义)、system_design 附录 H、roadmap 登记 P2.o。
6. 全量门(ctest + pytest + 前端四件套)+ dashboard 实测闭环 QA。

## 4. 验收

UI remember 新内容 → ≤1 个调度周期 → recall 命中(无手动 tick);queues pending 收敛;面板投影自动跟上;C++/Python/前端测试全绿。
