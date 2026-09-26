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

# M0.7 Acceptance Milestone — Design Spec
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

**Status**: Draft for review
**Author**: Auto Mode (Subagent-Driven Development)
**Date**: 2026-05-24
**Spec source**: `docs/design/system_design.md` §15.3.1 / §15.3.2 / §15.3.3 / §15.3.4

---

## 1. Goal

Close P1 by satisfying the four acceptance gates declared in `system_design.md` §15.3.1–§15.3.3:

1. **13 P1 CRITICAL** test cases all green (8 already exist; 5 to add)
2. **14 non-CRITICAL** test cases passing (regression coverage)
3. **2 E2E** scenarios passing (one already exists in M0.6 smoke; second to add)
4. **TC-EVAL**: 50 manually-annotated corpus samples ≥ 5 F1 thresholds across 3 EVAL rounds

A fifth requirement falls out of the EVAL gate even though it is not in the milestone overview row: a real LLM adapter must exist before EVAL can run, and M0.4 only shipped `FakeLLMAdapter`. This milestone therefore also delivers an OpenAI-compatible C++ adapter as a **P2-pull-forward**.

P1 closes when all four gates are green AND the OpenAI adapter is in `production roots` (no `starling::testing` references) AND ci_static_scan stays clean.

---

## 2. Non-Goals

- Replay Scheduler / Reconsolidation Engine / Prospective Loop integrations (all P2/P3)
- Anthropic / local-LLM adapters (only OpenAI-compatible covered here)
- ToMBench / FANToM datasets (P2 acceptance per §16.3-10; this milestone uses the 50-sample manual corpus only)
- Schema migrations beyond what existing migrations 0001–0005 provide; no new columns
- TC-A8-001 async arbitration variant (P2 per §15.3.6); P1 ships the synchronous severe-conflict path only
- ToM 2nd-order runtime; only schema-level nesting_depth=1 in EVAL corpus

---

## 3. Architecture

### 3.1 Component layout

```
                                                         ┌──────────────────────────────┐
                                                         │ scripts/eval_p1_extractor.py │
                                                         │  (CLI EVAL harness, Python)  │
                                                         └──────────────┬───────────────┘
                                                                        │
                                                                        ▼ uses
┌──────────────────────────────┐                          ┌──────────────────────────────┐
│ scripts/generate_eval_corpus │ ─── one-shot writes ───▶ │ tests/data/eval_p1_corpus    │
│   .py (Python, GPT-5.5 gen)  │                          │   .jsonl (50 records, in-tree)│
└──────────────────────────────┘                          └──────────────────────────────┘
                                                                        │
                                                                        ▼ feeds
                                       ┌──────────────────────────────────────────────┐
                                       │ Extractor (C++) ─ pluggable ─ LLMAdapter     │
                                       │                                              │
                                       │   ┌──────────────────────────────────────┐  │
                                       │   │ OpenAIAdapter (NEW, this milestone)  │  │
                                       │   │   src/extractor/openai_adapter.cpp   │  │
                                       │   │   - libcurl HTTPS POST               │  │
                                       │   │   - reads OPENAI_BASE_URL / KEY env  │  │
                                       │   │   - retry w/ exp backoff (max 3)     │  │
                                       │   │   - returns LLMResponse              │  │
                                       │   └──────────────────────────────────────┘  │
                                       └──────────────────────────────────────────────┘

                                       ┌──────────────────────────────────────────────┐
                                       │ Validator (M0.4, EXTENDED)                   │
                                       │   - cross-tenant derivation rejection (NEW)  │
                                       │   - immutable-field UPDATE rejection (NEW)   │
                                       │   - existing rules unchanged                 │
                                       └──────────────────────────────────────────────┘
```

### 3.2 Execution order (risk-front)

1. **OpenAI adapter** (highest unknown risk: C++ + libcurl + JSON + auth + retry)
2. **EVAL harness skeleton + 50-sample corpus generation + 1 baseline F1 round** (early signal on prompt quality before final gate)
3. **5 missing CRITICAL** tests + Validator extensions
4. **14 non-CRITICAL** regression tests
5. **E2E #2 (severe-conflict)**
6. **3 EVAL rounds** (final gate; F1 must hit thresholds)
7. **Milestone close** (roadmap flip + final review + merge)

Rationale: F1 baseline at step 2 surfaces prompt issues early. If F1 is 0.40 at baseline, there's still time to iterate prompts before the final 3-round gate. If left to the end, BLOCKED at gate = no slack to recover.

### 3.3 OpenAI adapter — wire-level contract

**Class**:
```cpp
namespace starling::extractor {
class OpenAIAdapter : public LLMAdapter {
public:
    struct Config {
        std::string base_url;     // OPENAI_BASE_URL or default
        std::string api_key;      // OPENAI_API_KEY (never log)
        std::string model;        // "gpt-5.5"
        int         timeout_ms = 60000;
        int         max_retries = 3;
    };
    explicit OpenAIAdapter(Config cfg);
    LLMResponse extract(std::string_view prompt,
                        std::string_view prompt_input_hash) override;
};
}  // namespace
```

**Wire shape** (OpenAI-compatible chat completions):
```
POST {base_url}/chat/completions
Authorization: Bearer {api_key}
Content-Type: application/json

{
  "model": "gpt-5.5",
  "messages": [{"role": "user", "content": "<prompt>"}],
  "temperature": 0
}
```

**Failure handling**:
- HTTP 429 / 5xx → exponential backoff retry (1s, 2s, 4s) up to `max_retries`, then return `LLMResponse{ok=false, error="transient_after_retry"}`
- HTTP 4xx (other) → no retry, `LLMResponse{ok=false, error="permanent_<code>"}`
- Network timeout → counts as 5xx for retry purposes
- Malformed JSON in body → `LLMResponse{ok=false, error="malformed_response"}`
- Successful response → extract `choices[0].message.content` as `raw_xml`, return `{ok=true}`

**Secret handling**: api_key is read from env at adapter construction, stored in the `Config`, used only in the `Authorization` header. Never logged. Never written to receipts/audit. Never bound to Python (Python EVAL harness reads env directly).

### 3.4 EVAL harness contract

**File**: `scripts/eval_p1_extractor.py` (Python CLI, runs from venv)

**Usage**:
```bash
python scripts/eval_p1_extractor.py \
  --corpus tests/data/eval_p1_corpus.jsonl \
  --model gpt-5.5 \
  --rounds 3 \
  --report build/eval_p1_report.md
```

**Per-round flow**:
1. Read each record from corpus (conversation + ground-truth Statements list)
2. Call extractor (via Python pybind binding) with `OpenAIAdapter`
3. For each ground-truth Statement, compute prediction match on:
   - `holder` (cognizer attribution)
   - `holder_perspective` (4-value categorical)
   - `predicate` (controlled core set)
   - `object` (exact OR canonical_object_hash match)
   - 2nd-order ToM (`nesting_depth=1` subset, ~10 records)
4. Aggregate to per-field F1 across all 50 records (each round produces 1 F1 vector)
5. After 3 rounds, take last round's F1 as final per spec §15.3.3

**Pass condition** (last round only):
| Field | F1 ≥ |
|---|---|
| holder | 0.85 |
| holder_perspective | 0.80 |
| predicate | 0.75 |
| object (exact / canonical_object_hash) | 0.70 |
| nesting_depth=1 (2nd-order ToM, ~10 records) | 0.60 |

**Failure mode**: if any threshold fails after round 3, the harness exits non-zero and the milestone close is BLOCKED — the controller reports the gap to the user without merging. No auto-retry, no threshold-tuning, no corpus rewriting.

**Report**: written as Markdown to `build/eval_p1_report.md` with per-round F1 table + per-record diff (predicted vs ground-truth) for the last round only.

### 3.5 Corpus generation contract

**File**: `scripts/generate_eval_corpus.py` (one-shot, output committed)

Generates 50 records to `tests/data/eval_p1_corpus.jsonl`. Each record:

```json
{
  "id": "eval-001",
  "conversation": [{"speaker": "Alice", "text": "...", "observed_at": "2026-..."}, ...],
  "ground_truth_statements": [
    {"holder": "Alice", "holder_perspective": "FIRST_PERSON",
     "subject": "Bob", "predicate": "responsible_for", "object": "auth",
     "modality": "BELIEVES", "polarity": "POS",
     "nesting_depth": 0, ...}
  ],
  "tags": ["bilingual", "first_person"]
}
```

**Coverage matrix** (spec §15.3.3 wording — bilingual, perspective × commitment × norm × 2nd-order ToM):
- ~12 records each: FIRST_PERSON / QUOTED / HEARSAY / INFERRED (= 48)
- 10 records: nesting_depth=1 (subset of the 48 — overlap allowed)
- ~5 each: COMMITMENT / NORM (overlap allowed)
- 50% Chinese, 50% English

**One-shot policy**: corpus generation is run once during this milestone; the resulting JSONL is committed. EVAL rounds re-use the same corpus across all 3 rounds — only extractor output varies.

**Self-eval bias acknowledgment**: §16.2-10 already documents that 50 samples have weak statistical power and the EVAL is engineering-empirical, not academic-grade. Spec gates apply as written; if F1 fails, BLOCKED.

### 3.6 Validator extensions (TC-NEG-CROSSTENANT, TC-NEG-IMMUTABLE)

**Cross-tenant derivation rejection** (TC-NEG-CROSSTENANT):
- New rule in Validator: if `derived_from` references a Statement whose `tenant_id != self.tenant_id`, reject with code `cross_tenant_derivation_forbidden` UNLESS the new Statement carries `provenance.protocol_id` (explicit cross-tenant agreement).
- With `protocol_id`: do not reject, but mark `review_status=REVIEW_REQUESTED` (do not silent-write).

**Immutable-field UPDATE rejection** (TC-NEG-IMMUTABLE):
- Bus.write must reject any path that calls a SQL UPDATE on `holder_id`, `source_speaker`, `perceived_by`, `tenant_id`, or `provenance` columns of an existing row.
- The correct mutation path is `statement.corrected + supersedes` (insert a new row + supersedes edge). This is what M0.5 already does for severe conflicts; the test verifies that direct UPDATE attempts are denied.
- Implementation: add a Validator guard that intercepts any Bus.write whose target row already exists with the same `id` AND whose payload changes any of the 5 immutable fields. The test exercises this guard by directly attempting `Bus.write` with a payload that mutates `holder_id` on an existing row, then asserts `PERMISSION_DENIED` (or equivalent semantic error code). This is an active behavioral test, not a structural one.

**Time-anchor regression** (TC-NEG-TIMEANCHOR):
- Already structurally enforced by M0.4's TemporalAnchor parsing rules. M0.7 adds the explicit acceptance test: import an Engram with "last week" relative phrasing → assert `valid_from` falls in the original observed window, not today.

### 3.7 E2E #2 — severe-conflict end-to-end

**File**: `tests/python/test_e2e_severe_conflict.py`

**Flow** (single test):
1. Seed: `mark_consolidated(S_old)` where S_old: holder=self, subject=Bob, predicate=responsible_for, object="auth", polarity=POS
2. Drive M0.4 Extractor with a conversation: "Alice told me Bob is no longer responsible for auth — Carol owns it now"
3. Validator + ConflictProbe + Bus.write: assert single SQLite transaction commits S_new (POL=NEG) + SUPERSEDES edge + S_old → ARCHIVED + 3 outbox events
4. `basic_retrieve(holder=self, subject=Bob, predicate=responsible_for, as_of=now())`: assert returns only S_new
5. RetrievalReceipt: assert `sufficiency_status=SUFFICIENT`, `evidence_erased_count=0`, `candidate_counts.fetched=1`

This is the only test that exercises M0.4 + M0.5 + M0.6 in a single transaction.

---

## 4. File Structure

### Created

| Path | Responsibility |
|---|---|
| `include/starling/extractor/openai_adapter.hpp` | Public class declaration, Config struct |
| `src/extractor/openai_adapter.cpp` | libcurl wire impl + retry loop + JSON parse |
| `tests/cpp/test_openai_adapter.cpp` | Adapter unit tests (uses local mock HTTP server fixture) |
| `bindings/python/module.cpp` (extended) | Bind OpenAIAdapter so EVAL harness can construct one |
| `python/starling/extractor/__init__.py` (extended) | Re-export `OpenAIAdapter` Python wrapper |
| `scripts/generate_eval_corpus.py` | One-shot 50-sample corpus generator (commits output) |
| `scripts/eval_p1_extractor.py` | EVAL harness CLI |
| `tests/data/eval_p1_corpus.jsonl` | 50 records, generated and committed once |
| `tests/python/test_eval_harness.py` | Lightweight harness self-test (mocked LLM, F1 calc verified) |
| `tests/python/test_tc_q3a_001.py` | TC-Q3a-001 mild correction provenance unchanged |
| `tests/python/test_tc_q3b_001.py` | TC-Q3b-001 2nd-order Statement object distinction |
| `tests/python/test_tc_neg_crosstenant.py` | TC-NEG-CROSSTENANT cross-tenant derivation reject |
| `tests/python/test_tc_neg_timeanchor.py` | TC-NEG-TIMEANCHOR last-week relative time anchor |
| `tests/python/test_tc_neg_immutable.py` | TC-NEG-IMMUTABLE direct UPDATE rejection |
| `tests/python/test_e2e_severe_conflict.py` | E2E #2 |
| `tests/python/test_p1_non_critical.py` | All 14 non-CRITICAL tests in one file (or split if it grows) |
| `docs/superpowers/specs/2026-05-24-m0-7-acceptance-design.md` | This document |
| `docs/superpowers/plans/2026-05-24-m0-7-acceptance.md` | Implementation plan (next step after spec approval) |

### Modified

| Path | Change |
|---|---|
| `CMakeLists.txt` | Add `find_package(CURL REQUIRED)` + link to extractor target |
| `src/validator/<existing>.cpp` | Add cross-tenant derivation rejection rule |
| `src/validator/<existing>.cpp` | Add immutable-field UPDATE guard (defensive) |
| `docs/superpowers/plans/2026-05-23-roadmap.md` | M0.7 row flip at milestone close |

---

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| OpenAI API quota / rate-limit during EVAL | Adapter retry w/ backoff + EVAL harness 1s sleep between records; total cost bounded (50 × 3 = 150 calls) |
| modelservice.top proxy instability | Adapter retry covers transient; if persistent, BLOCKED report identifies proxy as cause |
| GPT-5.5 self-eval bias inflates F1 | Acknowledged per §16.2-10; spec gates as written; BLOCKED if fails |
| GPT-5.5 self-eval bias deflates F1 (more likely if generator and extractor disagree on edge cases) | If round 1 baseline is far from threshold, prompt-engineer extractor before round 2 — corpus is frozen |
| libcurl + C++ HTTP is new for this codebase | Adapter is small (~200 LoC); unit-tested with local fixture; if blocked, fall back to a separate Python micro-service is NOT in scope (would be a new design decision) |
| 14 non-CRITICAL spread across many subsystems | Each test file is self-contained; failures isolate cleanly; if a subsystem can't satisfy a non-CRITICAL, document as P2 follow-up but P1 closes only if CRITICAL + EVAL pass |
| EVAL F1 BLOCKS at end | Risk-front execution puts a baseline F1 round at step 2; gives 3-5 days slack to iterate prompts before final gate |

---

## 6. Acceptance criteria for milestone close

1. ctest 251 + new C++ tests = all PASS
2. pytest 296 + new Python tests + EVAL harness self-test = all PASS
3. ci_static_scan = clean
4. `python scripts/eval_p1_extractor.py --rounds 3` last-round F1 vector = all 5 thresholds met
5. `OPENAI_API_KEY` is never written to a committed file or stdout
6. Whole-branch reviewer: no CRITICAL or IMPORTANT findings
7. Roadmap row M0.7 pinned at last-work commit (not merge commit)
8. Plan-doc commits to main only after merge (per project policy)
9. Worktree torn down

P1 is closed when all 8 are met.

---

## 7. Open questions

None at spec-write time. All scope decisions have been resolved in brainstorming:
- 50-sample corpus generated by GPT-5.5 once and committed
- OpenAI adapter in C++ (P2 pull-forward)
- F1 BLOCKS milestone close per spec §15.3.3
- Severe-conflict picked as E2E #2
- TC-NEG-CROSSTENANT lands in Validator
- Single plan, single worktree, risk-front execution order
