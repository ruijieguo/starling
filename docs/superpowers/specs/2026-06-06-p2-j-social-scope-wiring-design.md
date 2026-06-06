# P2.j 社会域接线（CanonicalScope 七元组 + CommonGround grounding）设计

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
