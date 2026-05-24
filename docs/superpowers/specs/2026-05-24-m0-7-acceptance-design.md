# M0.7 Acceptance Milestone — Design Spec

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
