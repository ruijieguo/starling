# P2.o 运行时闭环(写→读真正闭合)实现计划

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
