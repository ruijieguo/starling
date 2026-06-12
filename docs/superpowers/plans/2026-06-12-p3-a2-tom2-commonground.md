# P3.a2 二阶 ToM + CommonGround 补完 Implementation Plan

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
