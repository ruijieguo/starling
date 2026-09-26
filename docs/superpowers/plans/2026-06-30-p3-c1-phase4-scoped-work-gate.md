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

# P3.c1 Phase 4 — ScopedWorkGate + RestartGuard Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the governance concurrency-control substrate — an in-memory reentrant `ScopedWorkGate` (critical/soft quota + leaked-lease sweep + soft-drop accounting) and a `RestartGuard` (dual-threshold crash-loop guard) — with the DEGRADED-emit coupling proven against the Phase-2 `RuntimeSupervisor`. Phase 4 of the Governance slice; 3a (the `governance_pipeline_run` ledger) + 3b (StageTimer) are merged.

**Architecture:** Two brand-new pure-C++ in-memory primitives in `src/governance/` + `include/starling/governance/` (no SQLite, process-lifetime, no existing code to mirror — designed from `05_governance.md`). The gate's quota/reentrancy/sweep logic is **correct-under-concurrency but trivially satisfied while single-threaded** (the c1 tick is one daemon thread under the engine RLock; real multi-lane concurrency is M0.9+/P3+, `replay_scheduler.cpp:397`). The DEGRADED coupling is a thin pure helper that maps a leaked-lease sweep / restart-guard trip to a `HealthDecision{DEGRADED}` for `RuntimeSupervisor::note_health` (Phase 2). **Live tick pump-routing is OQ-4.1 — recommended deferred to M0.9+** (see below).

**Tech Stack:** C++20 core (`include/starling/governance/`, `src/governance/`), GoogleTest (`tests/cpp/`). No migration (in-memory). No binding in c1 (D1-style defer). No Python/dashboard surface.

## Global Constraints

- **Architecture boundary (CLAUDE.md hard rule):** core semantics in C++. The gate + restart guard are pure core algorithms → C++.
- **CI clang-tidy (changed-LINES) gate** (`scripts/ci_clang_tidy_diff.py`): lints `.cpp` under `src/|bindings/` + included headers, WarningsAsErrors `*`, DISABLES `bugprone-easily-swappable-parameters`. New headers (`scoped_work_gate.hpp`, `restart_guard.hpp`) ARE gated once their `src/` TU includes them — write clean by construction: identifiers ≥3 chars, sized enums (`enum class Lane : std::uint8_t`), `[[nodiscard]]` on pure queries, braces on all bodies, designated initializers for multi-field aggregates, no `bugprone-branch-clone`. clang-tidy is **un-runnable locally** (macOS 26 SDK) — CI is the gate; the IDE's full-file lint surfaces header issues pre-push (it caught 3b's `ps`/`rs`). See `[[clang-tidy-ci-only-gate-gotchas]]`.
- **No std::mutex in c1 (OQ-4.5 — eng-review confirms):** the gate/guard are single-threaded-accessed in c1 (one daemon tick thread under the engine RLock; no concurrent caller). Mirror `PipelineRunStore`/`PerceptionStateStore` (no mutex) rather than `RuntimeSupervisor` (which added a mutex ONLY because Phase 2 has a concurrent dashboard reader). Document that real concurrency (M0.9+) adds locking.
- **Build:** `python scripts/configure_build.py --build --test` (C++ + ctest). Build tools live in `.venv/bin/{cmake,ninja}` (NOT system PATH); the `build-macos/` dir is pre-configured; the test binary is `build-macos/tests/cpp/starling_tests` (`--gtest_filter=...`). Pure-C++ tasks need NO `--python-editable`.
- **Commit gate:** full ctest + `pytest tests/python` green (pytest is a no-op regression check here — Phase 4 touches no Python).
- **git:** explicit-path `git add` only; no `--no-verify`/`--amend`. Commit footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## RESOLVED DECISIONS (LOCKED by /plan-eng-review + codex outside-voice, 2026-06-30)

The OQ analysis below is the rationale record. **The LOCKED block immediately after it is authoritative — implementers apply it OVER any conflicting task text.**

## OPEN DECISIONS — analysis (rationale record; superseded by the LOCKED block)

### OQ-4.1 (CENTRAL) — live tick pump-routing: defer to M0.9+, or wire now?

**The tension.** The master plan (governance-core.md:117) lists "route the existing background pumps through gate admission" + "gate-acquire wrapping in `src/memory/memory_ops.cpp` pump calls" as a Phase-4 c1 deliverable. BUT: (1) the c1 tick is **single-threaded** (one `starling-bg-tick` daemon under the engine RLock — seam map confirmed), so every `acquire` succeeds at depth 1 and **no quota/reentrancy/leak/soft-drop path ever trips** in the live tick; (2) the 8 pumps are **batch-level** (one call across all tenants), so a per-pump `GateKey` is synthetic, not per-aggregate; (3) `tick_all(adapter, worker, policy, now)` takes no gate, so a process-lifetime gate must be **threaded through the signature + the `memory_tick_all` binding + the Python `_memory_core.tick` plumbing** — a bound-surface change — for **zero c1 behavior**.

| # | Approach | Cost |
|---|---|---|
| **B (RECOMMENDED)** | Build `ScopedWorkGate` + `RestartGuard` as process-lifetime, fully **synthetic-unit-tested** primitives + the DEGRADED-coupling helper (Tasks 4.1-4.4). **Do NOT wire the live tick.** Pump-routing + run-claiming land at M0.9+ when concurrency makes them non-inert. | Deviates from the master plan's "route the pumps" c1 deliverable — reinterprets it as "the gate is built + proven; live routing is M0.9+" (same pattern as 3a's ledger with no live writer, 3b's deferred persistence). |
| **A** | B + thread a process-lifetime gate into `tick_all` (signature + `memory_tick_all` binding + `_memory_core.tick` + a `_core.ScopedWorkGate` owned by `Runtime`), wrapping each of the 8 pumps in `acquire`/`release`. | A bound-surface change + 8 inert `acquire`/`release` pairs in the hot tick for **zero single-threaded behavior**; the cross-tick `dropped_soft_work_count` is always 0 (no quota pressure single-threaded). Front-runs M0.9+. |
| **C** | B + a **per-tick local** `ScopedWorkGate` constructed inside `tick_all` (no signature change), wrapping the 8 pumps. | Structural-only; a per-tick gate is architecturally wrong (an admission controller is process-lifetime) → churn at M0.9+; cross-tick accounting resets (but is 0 anyway). |

**Recommendation: B.** The gate/guard are concurrency primitives; single-threaded they are inert by construction, and **synthetic unit tests (drive quota pressure / reentrancy / leaked leases / restart thresholds directly) fully validate every path** — the live tick adds no validation, only inert code + a bound-surface change. Build the substrate correctly + prove the DEGRADED coupling; defer live routing to M0.9+ (the phase that adds real lanes + claimed workers, which is also where 3b's deferred run-creation lands). **This deviates from the master-plan c1 deliverable, so eng-review must explicitly bless it** (cf. 3b's "wire into replay_scheduler.cpp" tension, resolved by timing from the orchestrator). The tasks below implement B; an A/C amendment would add a Task 4.5 wiring step.

### Sub-decisions (baselines folded; eng-review locks)

- **OQ-4.2 — Lane model.** `enum class Lane : std::uint8_t { Critical, Soft }`. Critical = a reserved quota that soft work cannot exhaust (Compliance erase / outbox delivery / commitment fire, 05_governance.md:59). Soft = rebuildable batch work (replay/projection/embed). Baseline: two lanes only (Critical/Soft); finer per-operation lanes are P3+.
- **OQ-4.3 — GateKey shape.** `struct GateKey { std::string tenant_id; std::string holder_scope; std::string aggregate_id; Lane lane; }` with value equality + a hash (for the slot map). Baseline: exactly the spec tuple (05_governance.md:158). Reentrancy = same GateKey (all 4 fields equal) → depth++; different aggregate_id → new slot.
- **OQ-4.4 — Quota config.** `struct GateConfig { int critical_quota; int soft_quota; }` injected at construction (no magic numbers). Critical-lane acquires draw from `critical_quota`; soft from `soft_quota`; **critical is never starved by soft** (separate pools). Soft over-quota → drop (return a sentinel) + `dropped_soft_work_count++` (invariant 5). Baseline: caller supplies quotas; tests use small values to force pressure.
- **OQ-4.5 — No mutex** (see Global Constraints). Single-threaded c1; M0.9+ adds locking.
- **OQ-4.6 — DEGRADED coupling shape.** The gate/guard are **pure data structures that return signals** (`sweep_leaked` → `std::vector<std::string>` leaked ids; `should_pause_lane` → `bool`); a free helper `degraded_decision(trigger) -> HealthDecision` builds the `{DEGRADED, trigger}` decision, and the CALLER invokes `supervisor.note_health(...)`. The gate/guard hold **no** supervisor reference (decoupled; mirrors Phase-2 "never call a callback under the lock"). Baseline locked.
- **OQ-4.7 — `sweep_leaked` lease model.** `acquire` stamps a lease deadline (`acquired_at` + a per-acquire `lease_until` iso8601 the caller supplies, mirroring 3a's `claim` lease contract). `sweep_leaked(now_iso)` force-releases slots whose `lease_until < now_iso` and returns their `task_id`s (the spec's "leaked run_id list", 05_governance.md:170). Single-threaded, acquire/release pair within a call so nothing leaks live — exercised synthetically.
- **OQ-4.8 — RestartGuard driver.** c1 has no real worker-restart loop, so `record_restart`/`record_no_success`/`record_success` are driven only by tests (the dual-threshold logic is the deliverable, validated synthetically). Baseline: build + unit-test; no live driver (M0.9+).
- **OQ-4.9 — Binding (D1-style).** DEFER the Python binding of ScopedWorkGate/RestartGuard — no c1 Python consumer (a dashboard read of `dropped_soft_work_count` is a Phase-5 read route). Core-only; ctest is the acceptance. Baseline: no `bind_14`/`bind_15` change.

### LOCKED eng-review decisions (2026-06-30) — AUTHORITATIVE; apply OVER task text

/plan-eng-review (FULL_REVIEW + codex outside-voice; 9 codex findings, 6 folded + 2 escalated-and-locked + 1 cross-model agreement). Where these conflict with the task code below, THESE win.

- **L1 — OQ-4.1 = B, RE-FRAMED HONESTLY (D4 + codex #1/#8).** Build `ScopedWorkGate` + `RestartGuard` + the coupling helper as **pure in-memory DATA STRUCTURES**, fully synthetic-unit-tested. **NO live runtime-governance guarantee in c1** — no tick routing, no worker run-claiming, no live DEGRADED observation. The plan must NOT claim "governance behavior"; acceptance = the data-structure contracts hold under synthetic tests. Live routing + run-claiming + health-observation land at **M0.9+** (which also owns 3b's deferred run-creation). c1 ships two ready-but-unused substrates (3a ledger + 4 gate) — the accepted cascade trade.
- **L2 — OQ-4.5 = NO mutex (D2).** Single-threaded c1; matches `PipelineRunStore`. Documented M0.9+ TODO: add locking with real concurrency.
- **L3 — `acquire` returns a TYPED `[[nodiscard]]` outcome, NOT int+throw (D5 + codex #4):**
  ```cpp
  enum class AdmitStatus : std::uint8_t { Admitted, SoftDropped, CriticalRejected };
  struct AcquireOutcome { AdmitStatus status = AdmitStatus::Admitted; int depth = 0; };
  [[nodiscard]] AcquireOutcome acquire(const GateKey& key, std::string_view task_id,
                                       std::string_view lease_until);
  ```
  Admitted → `{Admitted, depth>=1}`; soft over-quota → `{SoftDropped, 0}` + `dropped_soft_work_count++`; critical over-quota → `{CriticalRejected, 0}` (**NO throw**; `[[nodiscard]]` forces the caller to handle it — M0.9+ alarms + holds DEGRADED per invariant 4). Uniform 3-way outcome, no exception side-channel.
- **L4 — reentrancy keyed by `(GateKey, task_id)`, NOT GateKey alone (codex #2).** A slot is identified by `(GateKey, task_id)`. Same `(GateKey, task_id)` → `depth++` (reentrant, no new slot). Same `GateKey` + **different** `task_id` → a DISTINCT holder → consumes its own slot from the lane quota (NOT reentrant). Pin this exact distinction in a test (two task_ids on one GateKey = 2 slots, not depth 2).
- **L5 — `release` is FAIL-LOUD (codex #7).** `release(GateKey, task_id)` throws `std::runtime_error` on: a `(GateKey, task_id)` not currently held; a depth underflow; a wrong `task_id` for a held GateKey. Decrements depth; frees the slot + reclaims the lane quota at depth 0. Pin each failure mode in a test.
- **L6 — lease + sweep canonical contract (codex #5).** `lease_until` + the sweep `cutoff_iso` MUST be canonical iso8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`) — the SAME contract as 3a's claim/lease (CX-8) — so string-compare ordering is sound. Document it on `acquire`/`sweep_leaked`; tests construct canonical timestamps only. No validation/parsing in the gate (the contract is the caller's, mirroring 3a).
- **L7 — RestartGuard restart threshold is TIME-BASED (D3 + codex #6):**
  ```cpp
  void record_restart(std::string_view now_iso);   // store the canonical iso timestamp
  void record_no_success();                          // consecutive++
  void record_success();                             // consecutive = 0
  [[nodiscard]] bool should_pause_lane(std::string_view cutoff_iso) const;
  // true iff (count of stored restart ts >= cutoff_iso) > max_restarts_in_window
  //          OR consecutive_no_success > max_consecutive_no_success
  ```
  The caller computes `cutoff_iso = now - window_seconds` (it holds the clock; the guard does NO iso arithmetic, only string-compare). `RestartGuardConfig` drops `window_size`, keeps `max_restarts_in_window` + `max_consecutive_no_success`. Test in-window vs out-of-window restarts.
- **L8 — invariant-5 honesty (codex #3).** The gate delivers ONLY the soft-drop **ACCOUNTING** half of invariant 5 (`dropped_soft_work_count`). The "retain outbox/watermark rebuild basis" half is the PUMP's concern at routing time (M0.9+). The plan/self-review claims only the accounting half — no overclaim.
- **L9 — baselines hold:** Lane `{Critical, Soft}`; `GateKey` = the spec 4-tuple with `operator==(...) = default`, slots stored in a **small vector scanned linearly** (no hand-written `std::hash`); `GateConfig{critical_quota, soft_quota}` injected; coupling = pure `degraded_decision(trigger)` helper + caller drives `note_health`; binding DEFERRED.
- **L10 — path-ref fix (codex #9):** the `replay_scheduler.cpp` constructor deferral comment is at `:395` (not `:397`).

---

## What Phase 4 delivers (spec linkage)
- Spec: governance-core.md §461-469 (Phase 4) + `05_governance.md` ScopedWorkGate (流程 :55-61, 接口 :155-171, **invariant 5** :189) + RestartGuard (:34, :36).
- 3a (merged) provides the `governance_pipeline_run` ledger; 3b (merged) the StageTimer. Phase 4 adds the **in-memory admission/restart substrate**, distinct from both (no DB).
- Under OQ-4.1=B: **no `tick_all`/binding/Python change**; the live routing (pumps through admission + workers claiming runs) is M0.9+.

---

## File structure
- **Create** `include/starling/governance/scoped_work_gate.hpp` + `src/governance/scoped_work_gate.cpp` — `Lane` enum, `GateKey`, `GateConfig`, `ScopedWorkGate` (acquire/release/sweep_leaked/dropped_soft_work_count + depth/quota state).
- **Create** `include/starling/governance/restart_guard.hpp` + `src/governance/restart_guard.cpp` — `RestartGuard` (dual-threshold) + `RestartGuardConfig`.
- **Create** `include/starling/governance/health_coupling.hpp` (header-only) — free helper `degraded_decision(std::string trigger) -> HealthDecision`.
- **Modify** `CMakeLists.txt` (add the 2 `src/governance/*.cpp` to `starling_core`), `tests/cpp/CMakeLists.txt` (add the test files).
- **Create** `tests/cpp/test_scoped_work_gate.cpp`, `tests/cpp/test_restart_guard.cpp`, `tests/cpp/test_health_coupling.cpp`.

---

## Task 4.1: `ScopedWorkGate` core — acquire/release/reentrancy + critical/soft quota + soft-drop

**Files:** Create `include/starling/governance/scoped_work_gate.hpp` + `src/governance/scoped_work_gate.cpp` + `tests/cpp/test_scoped_work_gate.cpp`; Modify `CMakeLists.txt` + `tests/cpp/CMakeLists.txt`.

**Interfaces (Produces):**
```cpp
namespace starling::governance {

enum class Lane : std::uint8_t { Critical, Soft };

struct GateKey {
  std::string tenant_id;
  std::string holder_scope;
  std::string aggregate_id;
  Lane lane = Lane::Soft;
  bool operator==(const GateKey&) const = default;   // value equality (reentrancy key)
};

struct GateConfig {
  int critical_quota = 0;   // reserved slots for Lane::Critical (never starved by soft)
  int soft_quota = 0;       // slots for Lane::Soft; over-quota soft work is dropped
};

// AcquireResult: depth>0 = admitted at that reentrancy depth; depth==0 = soft-dropped
// (over-quota rebuildable work; dropped_soft_work_count was incremented). Critical-lane
// over-quota THROWS (invariant 2: critical work is never silently dropped).
class ScopedWorkGate {
 public:
  explicit ScopedWorkGate(GateConfig config);
  // Reentrant: same GateKey (all 4 fields equal) + same task_id -> depth++ (no new slot).
  // New GateKey consumes a slot from its lane's quota. lease_until = canonical iso8601 UTC.
  [[nodiscard]] int acquire(const GateKey& key, std::string_view task_id,
                            std::string_view lease_until);
  void release(const GateKey& key, std::string_view task_id);   // depth--; frees slot at depth 0
  [[nodiscard]] long long dropped_soft_work_count() const;
  [[nodiscard]] int active_slot_count() const;                  // distinct held GateKeys (test introspection)
 private:
  // ... slot table keyed by GateKey: {depth, task_id, lease_until}; per-lane in-use counts ...
};

}  // namespace starling::governance
```

- [ ] **Step 1: Write the failing tests** — `tests/cpp/test_scoped_work_gate.cpp` (tests/cpp is NOT clang-tidy-linted). Cover: reentrant depth (same key → 1,2,3; release → 2,1,0); cross-aggregate new slot; soft over-quota → `acquire` returns 0 + `dropped_soft_work_count`++ + the slot is NOT held; critical quota is reserved (fill soft to its quota, a critical acquire still succeeds); critical over-quota THROWS (`EXPECT_THROW`); release frees the slot (a re-acquire then succeeds). [Full test bodies written here at implementation time — pin each behavior with explicit `EXPECT_EQ`/`EXPECT_THROW`.]
- [ ] **Step 2: Register + run to verify fail** — add the 2 src files to `CMakeLists.txt` `target_sources(starling_core ...)` after `pipeline_run_store.cpp`; add `test_scoped_work_gate.cpp` to `tests/cpp/CMakeLists.txt`. Run: `python scripts/configure_build.py --build` then `build-macos/tests/cpp/starling_tests --gtest_filter='ScopedWorkGate*'`; Expected: FAIL (header missing).
- [ ] **Step 3: Implement** the header + cpp per the interface: an `unordered_map`/`vector` slot table keyed by `GateKey` (provide a hash or use a `std::map` with a `<` ordering / a vector-scan for c1 — small N); per-lane in-use counters; `acquire` = find existing key (reentrant depth++) else check the lane's quota (critical: throw on over-quota; soft: return 0 + increment dropped counter on over-quota) else insert a slot (depth 1, store task_id + lease_until); `release` = depth-- and erase at 0. NO mutex (OQ-4.5). `enum class Lane : std::uint8_t`; `[[nodiscard]]`; braces; ≥3-char identifiers (clang-tidy header gating).
- [ ] **Step 4: Run to verify pass** — `build-macos/tests/cpp/starling_tests --gtest_filter='ScopedWorkGate*'`; Expected: PASS.
- [ ] **Step 5: Full gate + commit** — `python scripts/configure_build.py --build --test`; commit `feat(P3.c1/4): ScopedWorkGate — reentrant admission + critical/soft quota + soft-drop`.

## Task 4.2: `ScopedWorkGate::sweep_leaked` — lease-expiry leak detection

**Files:** Modify `scoped_work_gate.{hpp,cpp}` (add `sweep_leaked`); Modify `test_scoped_work_gate.cpp` (add cases).

**Interfaces (Produces):** `[[nodiscard]] std::vector<std::string> sweep_leaked(std::string_view now_iso);` — force-releases every held slot whose stored `lease_until < now_iso` (string compare is valid for canonical `YYYY-MM-DDTHH:MM:SSZ`, mirroring 3a's lease contract) and returns their `task_id`s. A swept slot's quota is reclaimed.

- [ ] **Step 1: Write failing tests** — acquire two slots with `lease_until` in the past + one in the future at `now`; `sweep_leaked(now)` returns exactly the 2 past `task_id`s, frees their slots (`active_slot_count` drops by 2, a re-acquire of a swept lane succeeds), leaves the future slot held. Empty gate → empty vector. [Full bodies at impl time.]
- [ ] **Step 2: Run to verify fail** — `--gtest_filter='ScopedWorkGate*'`; Expected: FAIL (`sweep_leaked` undefined).
- [ ] **Step 3: Implement** — iterate the slot table, collect `task_id`s where `lease_until < now_iso`, erase those slots + decrement their lane counters, return the collected ids. `[[nodiscard]]`, braces, ≥3-char.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `feat(P3.c1/4): ScopedWorkGate::sweep_leaked — lease-expiry leak detection`.

## Task 4.3: `RestartGuard` — dual-threshold crash-loop guard

**Files:** Create `include/starling/governance/restart_guard.hpp` + `src/governance/restart_guard.cpp` + `tests/cpp/test_restart_guard.cpp`; Modify `CMakeLists.txt` + `tests/cpp/CMakeLists.txt`.

**Interfaces (Produces):**
```cpp
namespace starling::governance {
struct RestartGuardConfig {
  int max_restarts_in_window = 0;        // sliding-window restart-count threshold
  int window_size = 0;                   // # of record_restart events the window spans
  int max_consecutive_no_success = 0;    // consecutive no-success threshold
};
class RestartGuard {
 public:
  explicit RestartGuard(RestartGuardConfig config);
  void record_restart();        // push into the sliding window
  void record_no_success();     // consecutive-no-success++
  void record_success();        // resets consecutive-no-success to 0
  [[nodiscard]] bool should_pause_lane() const;  // true if EITHER threshold exceeded
 private:
  // ... ring of recent restart marks (size window_size) + consecutive_no_success_ count ...
};
}  // namespace starling::governance
```

- [ ] **Step 1: Write failing tests** — restart-window: `record_restart` × (max+1) within the window → `should_pause_lane()` true; spread beyond the window → false. no-success: `record_no_success` × (max+1) → true; a `record_success` mid-streak resets → false. Either threshold alone trips. [Full bodies at impl time.]
- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement** — a fixed-capacity ring (or count within the last `window_size` marks) for restarts + a `consecutive_no_success_` counter; `should_pause_lane` = `(restarts_in_window > max_restarts_in_window) || (consecutive_no_success_ > max_consecutive_no_success)`. NO mutex. `[[nodiscard]]`, braces, ≥3-char, sized members.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `feat(P3.c1/4): RestartGuard — dual-threshold (restart-window + no-success) lane pause`.

## Task 4.4: DEGRADED-emit coupling — sweep/restart-trip → `RuntimeSupervisor::note_health`

**Files:** Create `include/starling/governance/health_coupling.hpp` (header-only) + `tests/cpp/test_health_coupling.cpp`; Modify `tests/cpp/CMakeLists.txt`.

**Interfaces (Produces):** `[[nodiscard]] inline HealthDecision degraded_decision(std::string trigger) { return HealthDecision{.target_status = RuntimeHealth::DEGRADED, .trigger = std::move(trigger), .metrics_snapshot = {}}; }` — pure builder. The gate/guard hold NO supervisor ref (OQ-4.6); the caller does `if (!gate.sweep_leaked(now).empty()) supervisor.note_health(degraded_decision("leaked_lease_sweep"));` and `if (guard.should_pause_lane()) supervisor.note_health(degraded_decision("restart_guard_pause"));`.

- [ ] **Step 1: Write failing test** — construct a real `RuntimeSupervisor` (all-caps + idx-present → start READY, mirror `test_runtime_supervisor.cpp`); apply `supervisor.note_health(degraded_decision("leaked_lease_sweep"))`; assert `supervisor.health() == RuntimeHealth::DEGRADED` and `supervisor.last_event()->trigger == "leaked_lease_sweep"` and `current_status == DEGRADED`. A second helper test: a leaked-sweep result drives the decision end-to-end (acquire a past-lease slot on a `ScopedWorkGate`, `sweep_leaked` non-empty → build the decision → note_health → DEGRADED). [Full bodies at impl time; mirror `test_runtime_supervisor_transitions.cpp` setup.]
- [ ] **Step 2: Run to verify fail** — `--gtest_filter='HealthCoupling*'`; Expected: FAIL (`health_coupling.hpp` missing).
- [ ] **Step 3: Implement** the header-only `degraded_decision`. (No tick wiring — OQ-4.1=B.)
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Full gate + commit** — `python scripts/configure_build.py --build --test` then `.venv/bin/python -m pytest tests/python` (regression — should be untouched-green); commit `feat(P3.c1/4): DEGRADED-emit coupling — sweep/restart trip → supervisor.note_health`.

**Phase 4 acceptance (L1 — PURE DATA STRUCTURES, NO live runtime-governance guarantee):** the `ScopedWorkGate` + `RestartGuard` DATA-STRUCTURE CONTRACTS hold under synthetic unit tests — reentrant depth keyed by `(GateKey, task_id)` [L4], cross-(GateKey,task_id) slots, critical-quota protection via the typed `AcquireOutcome` [L3], soft-drop ACCOUNTING [L8: the accounting half of invariant 5 only], fail-loud `release` [L5], lease-expiry `sweep_leaked` [L6 canonical contract], RestartGuard time-based restart window + no-success thresholds [L7]; the `degraded_decision` helper drives a real `RuntimeSupervisor` to DEGRADED in a test. **NO live tick routing / run-claiming / health-observation — those are M0.9+ (which also owns 3b's deferred run-creation).** full ctest + pytest (regression) green; clang-tidy CI green. core-only; no migration / binding / Python / dashboard.

---

## Self-review

**Spec coverage** (governance-core.md §461-469 + 05_governance.md) — all DATA-STRUCTURE contracts (L1: no live governance guarantee):
- ScopedWorkGate acquire (typed `AcquireOutcome` [L3]) / fail-loud release [L5] / reentrant depth by `(GateKey, task_id)` [L4] + critical/soft quota → Task 4.1. ✅
- `sweep_leaked(cutoff_iso) -> vector<task_id>` (canonical-iso contract [L6]) → Task 4.2. ✅
- `dropped_soft_work_count` = the **accounting half of invariant 5 only** [L8]; the rebuild-basis-retention half is the pump's (M0.9+). ✅
- RestartGuard **time-based** restart window + consecutive-no-success [L7] → Task 4.3. ✅
- `degraded_decision` helper → real `RuntimeSupervisor` DEGRADED (test only; live observation = M0.9+) → Task 4.4. ✅
- "route the existing background pumps through gate admission" → **OQ-4.1=B: deferred to M0.9+** (the live tick is single-threaded so routing is inert; synthetic tests fully validate the data structures). Locked deviation from the master-plan deliverable, re-framed honestly [L1].
- invariant 2 (critical failure_policy never overridable) → critical over-quota returns `CriticalRejected` (typed, `[[nodiscard]]`, never silently dropped) [L3]; alarm + DEGRADED-hold is the M0.9+ caller's (deferred).

**Placeholder scan:** Tasks 4.1-4.4 give complete interfaces + behavior contracts + exact test scenarios. The gate/guard are brand-new algorithms (no existing code to mirror), so the per-test bodies + impl are written at implementation time against the pinned contracts here — NOT "fill in later": each test scenario names exact inputs → exact assertions, and the impl behavior is fully specified. (This is the one place the plan specifies behavior + test scenarios rather than transcribable code, because there is no source to transcribe — flagged honestly for eng-review.)

**Type consistency:** `Lane`/`GateKey`/`GateConfig` (4.1) consumed by `sweep_leaked` (4.2); `HealthDecision`/`RuntimeHealth`/`note_health` reused unchanged from Phase 2 (seam-map verified: `runtime_health_event.hpp:36`, `runtime_supervisor.cpp:64`); `degraded_decision` (4.4) returns the Phase-2 `HealthDecision`. No mutex anywhere (OQ-4.5). iso8601 `lease_until` string-compare matches 3a's canonical contract.

**clang-tidy pre-flight:** new headers gated once their src/ TU includes them — `enum class Lane : std::uint8_t` + `enum class AdmitStatus : std::uint8_t`, `[[nodiscard]]` on `acquire`/queries, ≥3-char identifiers (`key`/`config`/`gate`/`guard`/`now_iso`/`task_id`/`lease_until`/`cutoff_iso`), braces, designated initializers, `operator==(...) = default`. tests/cpp not linted.

---

## Implementation Tasks
Synthesized from this review's findings (all FOLDED into the LOCKED block + tasks).

- [ ] **T1 (P1, human: ~2h / CC: ~20min)** — ScopedWorkGate — apply the codex-caught interface fixes
  - Surfaced by: codex #2 (reentrancy keyed by `(GateKey, task_id)` not GateKey [L4]), #4 (typed `AcquireOutcome`, no throw [L3]), #7 (fail-loud `release` on unheld/underflow/wrong-task [L5]), #5 (canonical-iso lease contract [L6])
  - Files: `include/starling/governance/scoped_work_gate.{hpp,cpp}`, `tests/cpp/test_scoped_work_gate.cpp`
  - Verify: `build-macos/tests/cpp/starling_tests --gtest_filter='ScopedWorkGate*'` (incl. two-task-ids-one-GateKey = 2 slots; release fail-loud cases)
- [ ] **T2 (P2, human: ~45min / CC: ~10min)** — RestartGuard — time-based restart window
  - Surfaced by: D3 + codex #6 — `record_restart(now_iso)` + `should_pause_lane(cutoff_iso)` [L7], not count-based
  - Files: `include/starling/governance/restart_guard.{hpp,cpp}`, `tests/cpp/test_restart_guard.cpp`
  - Verify: `--gtest_filter='RestartGuard*'` (in-window vs out-of-window restarts)
- [ ] **T3 (P3, done in review)** — honest re-framing (codex #1b/#3/#8) — plan/self-review state "pure data structures, no runtime guarantee"; invariant-5 accounting-half only. Already folded.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 9 findings; 6 folded + 2 escalated→locked + 1 cross-model agreement |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 5 decisions locked; 0 critical gaps; codex caught 1 real plan bug + 2 real gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

Step 0 scope: ACCEPTED, re-framed — 10 files is test-driven (2 primitives × hpp+cpp+test + a header-only helper + 2 CMake); 2 new classes (at threshold). 5 decisions locked: **OQ-4.1=B** (build substrate, defer live routing to M0.9+) **re-framed honestly** as pure data structures with no runtime-governance guarantee (D4); **OQ-4.5=no-mutex** (D2); **RestartGuard time-based window** (D3); **critical over-quota = typed `[[nodiscard]]` `AcquireOutcome`** not throw (D5). Architecture 1 finding (RestartGuard time-window, D3); Code Quality 1 minor (GateKey vector-scan storage, locked); Tests strong (every data-structure path has a synthetic test); Performance 0 (in-memory, tiny N).

- **CODEX (outside voice):** 9 findings. **#2** (reentrancy keyed by GateKey-only = a real correctness bug — a different task wrongly admitted as reentrant) + **#7** (release failure-modes undefined) + **#5** (sweep canonical-iso contract) were real gaps the C++ review missed → folded (L4/L5/L6). **#1** (B overbuilds inert dead code) + **#4** (critical-throw bad policy) escalated to the user → locked (D4 hold-B-re-framed, D5 typed result). **#3/#8** (invariant-5 overclaim / coupling-weak) → honest re-framing (L1/L8). **#6** (restart not a time window) = cross-model agreement with D3. **#9** path-ref → L10.
- **CROSS-MODEL:** codex's core thesis — "B is only defensible if re-scoped as pure data structures, no runtime guarantee" — was accepted (D4 holds B with exactly that honest re-framing). Codex's reentrancy-key bug (#2) is the highest-value catch: a C++-only inspection read the interface line and missed that the impl sketch keyed by GateKey alone.
- **VERDICT:** ENG CLEARED — Phase 4 ready to implement subagent-driven, as a pure-data-structure substrate (no live runtime governance until M0.9+). All 5 decisions + 6 codex folds in the LOCKED block; canonical interfaces (typed AcquireOutcome, (GateKey,task_id) reentrancy, fail-loud release, time-based RestartGuard) locked there.

NO UNRESOLVED DECISIONS
