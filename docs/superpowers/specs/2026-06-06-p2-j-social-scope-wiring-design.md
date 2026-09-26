<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# P2.j 社会域接线（CanonicalScope 七元组 + CommonGround grounding）设计
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **2026-09-11 契约补充**：证据链接沿用 tenant/perspective 可见性，不能扩大 scope。 当前扩展见 [已确认语义证据设计](2026-09-11-source-grounded-claim-contract-design.md)。下文保留本版本原有适用范围。


**里程碑**：P2.j（关闭 codex review 2026-06-06 的两条 High 缺口：CommonGround 真接线 + CanonicalScope 七元组）。
**日期**：2026-06-06
**状态**：设计已 user approved（brainstorming 逐节确认），待 writing-plans
**依赖**：main HEAD f7f57f2；ctest 493 / pytest 536(+13 skip) / `ci_static_scan` 绿；migration 最高 0021。本里程碑**改 C++** → worktree 隔离 + cmake 重建（记忆 worktree-cpp-editable-build-recipe）。

---

## 0. 背景与目标

codex review 指出两条 High：都是**明标的阶段占位**（非回归），但 roadmap 曾暗示已接线：

- **#2 CommonGround**：`src/tom/common_ground.cpp` 的 `query()` 仍 P2.a 占位（恒返回 `[]`）；`ToMEngine::perspective_take`（`src/tom/tom_engine.cpp:109`）拿到空 cg。零件齐全（`CommonGroundWriter` 5 act、`CommonGroundContainer.rebuild/read`、`common_ground`/`grounding_acts` 表 migration 0010/0014）但 **100% 测试隔离**——生产路径无 subscriber 触发 assert/rebuild。
- **#3 CanonicalScope**：`include/starling/bus/canonical_scope.hpp:48` 的 `scope_of()` 恒返回 `CanonicalScopeNull`；Norm/Commitment/CommonGround 三臂 `canonical_bytes()` 抛 `logic_error`（当前因 scope_of 恒 Null 而不可达）。`canonical_conflict_key` 七元组（`05_bus.md:205-218`）第 7 元缺真实 scope → 同形不同群体 Statement 进同一冲突键空间（潜在误去重）。

**目标一句话**：把社会域 scope（Commitment/Norm/CommonGround）接进冲突键七元组，并让 CommonGround grounding 协议在生产路径真实跑通（assert→acknowledge→grounded），使 `perspective_take` 返回真实 common ground。

**口径（user 选定）**：两个都全做；grounding 四规则全做（#1/#2/#3/#4）；scope 群体字段从**现有字段 + interlocutor 推导**（不改抽取 prompt）；interlocutor **显式串入** `remember`。

---

## 1. 范围

**范围内：**
- `statements.scope_parties_json`（migration 0022）+ `ExtractedStatement.scope_parties` + writer 持久化 + `Extractor.run` 收 interlocutor。
- `Memory.remember(interlocutor=)` + `DashboardEngine` 串 interlocutor → `scope_parties=sorted{self,interlocutor}`。
- `CanonicalScope`：`scope_of` 按 modality 分支 + 3 臂 `canonical_bytes` + backfill proxy 读 `scope_parties_json` + C++/Python 冲突键 parity。
- `CommonGroundSubscriber`：assert / acknowledge(#1+#3) / 共同在场推定(#2) / repair / 超时降级 + 容器 rebuild，接进 `SubscriberPump`。
- 人工确认(#4)：暴露带 audit actor 的人工 grounded 路径。
- `common_ground::query()` 真读 + `perspective_take` un-stub + Python 读路径（`render_working_set` 用 interlocutor 拼 cg_ref）。
- 测试迁移（un-stub 3 个 stub-locking 测试 + 新协议/scope 测试）。

**范围外（→ 后续/P3.a）：**
- 二阶 ToM 完整实现（nested belief 推理）——本期只把一阶 grounding 接通。
- 抽取 prompt 改动（scope 群体从现有字段推导，不让 LLM 出 principal/beneficiary/parties）。
- 多方（>2）grounding 的细则超出四规则之外的部分。
- `withdraw`/`supersede_ground` 的全自动触发（writer 已有方法，本期 supersede 走 `05_bus.md:222` 的 `statement.superseded` 消费即可，withdraw 走 RECANTED；非核心闭环，最小可用即可，复杂细则延后）。
- Norm `members` 的语义精确建模（本期 `sorted{holder,subject}` 的确定化近似，足够冲突键一致性）。

---

## 2. 数据模型（关键决策：scope_parties 独立于 perceived_by）

**核查结论**：复用 `perceived_by` 当 grounding/scope parties **不合适**。设计 `09_tom.md:80`「共同在场推定」规则要求 **`perceived_by` 覆盖（⊇）所有 parties** —— 是覆盖关系非相等：
- `perceived_by` = 信息可见性（认识论：谁见证；驱动 ToM frontier；群聊可 `[self,Bob,Alice]`，`system_design.md:1570`），**不可变**字段。
- `parties` = grounding 参与方（社会层；CommonGround 条目自有字段 `09_tom.md:237` + `common_ground.parties_json`）。
- 三方群聊 `perceived_by={self,Bob,Alice}` 但某两两 grounding `parties={self,Bob}` → 分叉。

故新增**独立字段**：

- **Migration 0022**：
  - `statements` 加 `scope_parties_json TEXT`（可空，default `NULL`；不可变——沿用 `perceived_by_json` 的 immutable trigger 模式，见 migrations 0006/0007）。仅对话语境填 `sorted{self,interlocutor}` 的 JSON 数组；私有信念为 `NULL`。
  - `common_ground` 加轮次支持（供 #2 共同在场推定 N=3）：优先**不加列、从事件序列/`created_at`+后续 statement.written 计数算**；若 planning 判定算法过重，则加 `rounds_since_assert INTEGER NOT NULL DEFAULT 0` 列。两案 planning 二选一，spec 不锁。
- **`ExtractedStatement`**（`include/starling/extractor/extracted_statement.hpp`）加 `std::vector<std::string> scope_parties;`（default 空）。`Extractor::run` 多收一个 parties/interlocutor 形参；有则填 `scope_parties = sorted{holder, interlocutor}` 并写入 `statements.scope_parties_json`。
- **`perceived_by` 在对话语境下也填 `{self, interlocutor}`**（现状 P2.i 是 `{holder}`）——这是规则 #2 共同在场推定要求的 `perceived_by ⊇ parties` 的前提（否则 #2 永不触发）。仍在写入时一次性设定（不可变性不破）。
- **为何两字段在 2 方时取值相同却要分列**：`perceived_by`（认识论：谁感知）与 `scope_parties`（社会层：grounding 参与方）是不同概念，2 方对话里恰好相等，但**多方会分叉**（群聊里 perceived_by 可含旁听的第三方，scope_parties 仍是两两 grounding 的双方）。故保持两列，即便简单场景值相同。

**该一个 `scope_parties_json` 字段喂三处**：CanonicalScope 的 CommonGround 臂、Commitment beneficiary、grounding 协议的 `common_ground.parties_json`。**本期假设 2 方对话**（`scope_parties` 恰 2 元）；多方 grounding 超四规则的细则属范围外。

---

## 3. CanonicalScope（bus 侧）

**`scope_of()`（`include/starling/bus/canonical_scope.hpp`，modality 优先）**：
```
modality == COMMITS                  → CanonicalScopeCommitment(principal=holder, beneficiary=interlocutor)
modality ∈ {NORM_OUGHT, NORM_FORBID} → CanonicalScopeNorm(kind, members=sorted{holder, subject})
else if scope_parties.size() >= 2    → CanonicalScopeCommonGround(parties=sorted scope_parties)
else                                 → CanonicalScopeNull{}
```
- Commitment `beneficiary` 取 interlocutor（即 `scope_parties` 里非 holder 的那方），**不是 subject**（subject 是被承诺的对象）。无 interlocutor 的 COMMITS（`scope_parties` 空）→ beneficiary 为空串，仍是合法确定的 Commitment scope（`principal + "\x1f" + ""`），与普通信念（Null）区分。
- Norm `kind` 由 modality 定（NORM_OUGHT→"obligation"，NORM_FORBID→"prohibition"）；`members` 用 `sorted{holder, subject}` 的确定化近似。
- CommonGround `parties` = `sorted(scope_parties)`。

**3 臂 `canonical_bytes()`（`src/bus/canonical_scope.cpp`，替换 throw）**：
- `CanonicalScopeNorm`：`kind + "\x1f" + join(members_sorted, "\x1f")`。
- `CanonicalScopeCommitment`：`principal + "\x1f" + beneficiary`。
- `CanonicalScopeCommonGround`：`join(parties_sorted, "\x1f")`。
（具体分隔符/编码与现有 conflict_key 的 `\x1f` US 风格一致；确保确定性 + C++/Python 一致。）

**backfill proxy**（`src/bus/conflict_key_backfill.cpp:141` 建 `ExtractedStatement stmt_proxy`）：SELECT 增读 `scope_parties_json`，填入 `stmt_proxy.scope_parties`，使 `canonical_conflict_key_hex` 算到真实 scope。

**C++/Python 冲突键 parity**：`canonical_conflict_key` 在 C++（`src/bus/conflict_key.cpp`）+ Python（镜像，`test_conflict_key.py` 校验 parity）两侧都要实现 scope 分支与 canonical_bytes，保证两侧 64-hex 一致。

**无回归保证**：旧数据 `scope_parties=NULL` + 非 COMMITS/NORM modality → scope=Null → bytes `""` → 七元组键不变。

---

## 4. CommonGround grounding 协议（tom 侧）

**新增 `CommonGroundSubscriber`**（`include/starling/tom/common_ground_subscriber.{hpp,cpp}`），接进 `SubscriberPump.run_post_write`（`src/bus/subscriber_pump.cpp`，沿用 belief_tracker 那种 checkpoint-consumer + SAVEPOINT 模式），消费 `statement.written`：

| 触发 | 条件（`09_tom.md` 规则） | 动作 |
|---|---|---|
| **Assert** | 新 Statement 带 `scope_parties`（≥2 方）且无同命题已开条目 | `CommonGroundWriter.assert_()` → `asserted_unack`，`parties_json`=scope_parties |
| **Acknowledge #1 显式确认** | 新 Statement 与某 `asserted_unack` **同命题**（同 subject/predicate/canonical_object_hash、同 polarity），holder 是该条目**另一方** | `acknowledge()` → `grounded` |
| **Acknowledge #3 重复确认** | 同命题被**不同 parties 成员独立提及 ≥ M=2 次** | `acknowledge()` → `grounded` |
| **Acknowledge #2 共同在场推定** | `perceived_by ⊇ parties` 且后续 **N=3 轮**内无 Repair/Withdraw/显式否认 | `acknowledge()` → `grounded`（tick/sweep 时判定，需轮次计数，见 §2） |
| **Acknowledge #4 人工确认** | human review / policy rule 显式设 grounded | `acknowledge(actor=human/policy)` → `grounded`，**保留 audit actor** |
| **Repair** | 同命题 **polarity 相反**，来自另一方 | `repair()` → `suspected_diverge` |
| **超时降级** | `asserted_unack` 超 **T=24h** 无 Ack/Repair | `sweep_timeout_downgrade()` → `suspected_diverge` |
| **rebuild** | 上述任一改了 common_ground 后 | `CommonGroundContainer.rebuild(tenant, cg_ref=f"{self}::{target}")` |

- **匹配逻辑**：`common_ground ⋈ statements`，按 `(subject, predicate, canonical_object_hash)` 同命题 + `parties_json` 重叠 + holder 异方。
- **常量**：N=3（共同在场轮数）、M=2（重复确认次数）、T=24h（超时），与 `09_tom.md:79-84` 一致。
- **#4 人工确认**：暴露一条带 audit actor 的人工 grounded API（Memory/dashboard 层方法或 policy hook，复用 `CommonGroundWriter.acknowledge` 的 audit 路径），`grounding_acts.actor_cognizer_id` 记人工/policy actor。
- writer 已实现全部 act，subscriber 只在对的时机调；全程经 outbox/CAS/审计（不绕过，`05_bus.md:227`）。

---

## 5. 读路径 + perspective_take

- **`common_ground::query(self_id, target_id, tenant, as_of)`**（`src/tom/common_ground.cpp` 替换 stub）：`SELECT … FROM common_ground WHERE tenant_id=? AND status IN ('grounded','asserted_unack','suspected_diverge') AND parties_json 同含 self_id 与 target_id AND as_of 过滤（grounded_at<=as_of 且未在 as_of 前 expired）` → `vector<CommonGroundEntry>`。
- **`ToMEngine::perspective_take`**（`src/tom/tom_engine.cpp:109`）已调 query()，现返回真实 cg。**un-stub `tests/cpp/test_tom_engine_perspective.cpp:142`**（原断言 cg 恒空 → 改为真实 grounding 后非空）。
- **Python 读路径**：`Memory.render_working_set`（`python/starling/memory.py:209`）+ dashboard 已读 `CommonGroundContainer.read()`，本期 subscriber 重建后其投影变真；`render_working_set` 需用 interlocutor 拼 `cg_ref=f"{self}::{interlocutor}"`（若 working set 渲染需指定对话方，planning 定参数传递）。

---

## 6. 测试

- **C++（ctest）**：
  - `test_canonical_scope`：un-stub（原锁 ExtractedStatement 恒 Null）→ 三种 scope 变体（Commitment/Norm/CommonGround）+ 仍 Null 的普通 Statement。
  - `test_conflict_key`（+ `test_conflict_key.py`）：**C++/Python parity 覆盖带 scope 的键**（同命题不同 parties → 不同键；无 scope → 旧键不变）。
  - 新 `test_common_ground_subscriber`：assert / ack #1 显式 / ack #3 重复 / ack #2 共同在场(N=3) / repair / 超时(T=24h) 六条路径 + rebuild。
  - `test_tom_engine_perspective`：un-stub，真实 grounding → query 非空。
- **Python（pytest）**：`remember(interlocutor=)` → grounding 端到端（self 断言→对方复述→grounded→`render_working_set` 出现 common ground）；现有 `test_grounding_acts` 不回归。
- **migration**：0022 干净应用（glob，最高 0021→0022）；旧数据 `scope_parties=NULL` → scope Null → 冲突键不回归。
- **红线回归**：M0.8/M0.9/P2.a–i 全绿；ctest（含新 scope/subscriber 用例，数会变）/ pytest 全绿；`ci_static_scan` 绿。

---

## 7. 实施约束（注入 writing-plans）

- **改 C++**（tom/ + bus/ + extractor 数据模型 + binding）→ **worktree 隔离 + cmake 重建**（记忆 worktree-cpp-editable-build-recipe：venv + pip cmake/ninja + `pip install -e --config-settings=build-dir=build`；改后 `cmake --build build && cmake --install build --prefix .venv/lib/python3.14/site-packages`）。
- **有 migration**：0022（glob-based，从 0021→0022，单一 `starling_tests`）。`scope_parties_json` 不可变 trigger 沿用 0006/0007 模式。
- **C++/Python 冲突键 parity 必须维持**（两侧 scope_of + canonical_bytes 一致）。
- subscriber 走既有 SubscriberPump checkpoint + SAVEPOINT，不绕 outbox/CAS/审计。
- 不改 Statement 写入/校验/dedup 的既有不变量（只加 scope_parties 字段 + scope 入键）；不改抽取 prompt。
- API key env-only；`ci_static_scan` 纳入收尾清单（每里程碑跑 ctest + pytest + ci_static_scan）。
- Co-Authored-By trailer 每 commit；无 `--no-verify`/`--amend`；plan untracked 直到 close；合并/push main 需 dangerouslyDisableSandbox + 显式 consent。

---

## 8. 验收

- `scope_of()` 按 modality + scope_parties 正确分支；3 臂 `canonical_bytes` 实现（不再 throw）；`canonical_conflict_key` 七元组真带 scope；C++/Python parity 绿。
- `scope_parties_json`（migration 0022）独立于 `perceived_by_json`，仅对话语境填；旧数据冲突键不回归。
- `CommonGroundSubscriber` 在生产路径触发 assert/acknowledge(#1/#2/#3/#4)/repair/超时 + 容器 rebuild；`common_ground::query` 真读；`perspective_take` 返回真实 cg。
- `Memory.remember(interlocutor=)` → grounding 端到端：self 断言→对方复述→`grounded`→`render_working_set` 出现 common ground。
- 3 个 stub-locking 测试 un-stub；新协议/scope 测试全绿；ctest/pytest/ci_static_scan 全绿；M0.8/M0.9/P2.a–i 不回归。
- roadmap「已知缺口」节把 #2/#3 从「未接线」更新为「已接线（P2.j）」。
