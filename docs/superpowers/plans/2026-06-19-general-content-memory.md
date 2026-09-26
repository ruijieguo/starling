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

# General-Content Memory (Sub-Project C) Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third "general fact" extraction pass so arbitrary declarative content (definitions, statives, relationships, quantities) becomes recallable self-held `BELIEVES` statements — reusing the existing belief `Extractor`, with one C++ predicate-class addition.

**Architecture:** A new `general_fact_prompt` (Python data) emits the belief claim-JSON schema with `holder={self}`-filled, `modality=BELIEVES`, a general predicate. `MemoryCore.remember` runs it as a third `memory_remember` call on the idempotent engram. A 4th `kGeneralFactPredicates` class makes general predicates core/approved. Recall is unchanged (self-held facts hit the default `recall(holder=self)`).

**Tech Stack:** C++20 (predicate registry), Python adaptation (prompt data, config, wiring), pytest + gtest/ctest.

**Spec:** `docs/superpowers/specs/2026-06-19-general-content-memory-design.md` (commit b7e4c56).

**Baseline:** ctest 650 / pytest 638 (15 skipped). The third pass is additive; a passage with no declarative fact yields `[]` → no behaviour change for belief/episodic content.

**Build/test commands (repo root `/Users/jaredguo-mini/develop/memory/starling`, cwd resets each Bash call → prefix `cd … &&`):**
- Build (after C++): `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`
- C++ test: `.venv/bin/ctest --test-dir build -R <Name> --output-on-failure`
- Editable rebuild (after C++/binding): add `--python-editable`
- pytest: `.venv/bin/python -m pytest <file> -v`

**Hard constraints (every task):** reuse the belief `Extractor` (NO new C++ extractor); the only C++ is the predicate class. Do NOT touch `canonicalize_*`, the reconstructor, `validate_*` logic, or the belief/episodic prompt content. No new modality, no migration. General facts are self-held `BELIEVES`, recallable via the default `recall`. Third pass best-effort (never fails `remember`). TDD: failing test → red → minimal impl → green → commit. explicit-path `git add` (never `.`/`-A`); no `--no-verify`/`--amend`; do NOT push / merge / touch roadmap.

---

## Task 0: Baseline (controller — do directly)
- [ ] Confirm ctest 650 / pytest 638 green: `.venv/bin/ctest --test-dir build --output-on-failure 2>&1 | tail -3` ; `.venv/bin/python -m pytest -q 2>&1 | tail -3`. If not, reconcile before Task 1.1.

---

## Phase 1 — `kGeneralFactPredicates` (C++)

### Task 1.1: 4th predicate class + `is_core_predicate` scan + ctest

**Files:**
- Modify: `include/starling/extractor/predicate_registry.hpp`
- Test: `tests/cpp/test_validation_policy.cpp` (extend) or a predicate-registry test — register in `tests/cpp/CMakeLists.txt` if new

**Context:** `predicate_registry.hpp:16-50` has 3 `inline constexpr std::array` + `is_core_predicate` scanning them. Out-of-set non-OCCURRED predicates → `REVIEW_REQUESTED` (`statement_validator.cpp:88`). Add a 4th class (general facts) so general predicates are approved. No overlap with `kCoreBeliefPredicates` (`located_at`/`member_of`/`knows` already core).

- [ ] **Step 1: Write the failing ctest.** Grep for an existing `is_core_predicate` test: `grep -rln "is_core_predicate\|kActionPredicates" tests/cpp`. Extend it (or add to `tests/cpp/test_validation_policy.cpp`) with:
```cpp
TEST(GeneralFactPredicates, AreCorePredicates) {
    using namespace starling::extractor;
    EXPECT_TRUE(is_core_predicate("is_a"));
    EXPECT_TRUE(is_core_predicate("has_value"));
    EXPECT_TRUE(is_core_predicate("part_of"));
    EXPECT_TRUE(is_core_predicate("reports_to"));
    EXPECT_TRUE(is_core_predicate("depends_on"));
    EXPECT_FALSE(is_core_predicate("frobnicates"));  // unregistered → still not core
}
TEST(GeneralFactPredicates, GeneralPredicateNotReviewedUnderDefaultPolicy) {
    // a non-OCCURRED belief statement with predicate "is_a" must NOT be REVIEW_REQUESTED
    // (reuse make_valid_belief from this file)
    auto s = make_valid_belief("is_a");
    auto out = validate_extracted_statement(s);  // default policy
    EXPECT_TRUE(out.accepted);
    EXPECT_FALSE(out.review_status_override.has_value());
}
```
(If `make_valid_belief` isn't in the chosen file, reuse/replicate the helper as Task 2.1 of the configurability milestone did.)

- [ ] **Step 2: Build, verify FAIL.** `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build` then `.venv/bin/ctest --test-dir build -R GeneralFactPredicates --output-on-failure` → expect FAIL (`is_a` not core → `is_core_predicate` false / the statement IS `REVIEW_REQUESTED`).

- [ ] **Step 3: Add the 4th class + scan.** In `include/starling/extractor/predicate_registry.hpp`, after `kPerceptionPredicates` (`:35-37`):
```cpp
// General-fact predicate class (sub-project C): attributive + relational
// predicates for arbitrary declarative world-facts ("X is a Y", quantities,
// relationships). In-vocab so general facts are approved, not REVIEW_REQUESTED.
// No overlap with kCoreBeliefPredicates (located_at/member_of/knows already core).
inline constexpr std::array<std::string_view, 8> kGeneralFactPredicates = {
    "is_a", "instance_of", "has_property", "has_value",
    "part_of", "related_to", "depends_on", "reports_to",
};
```
and add a scan loop in `is_core_predicate` (after the `kPerceptionPredicates` loop, `:46-48`):
```cpp
    for (const auto p : kGeneralFactPredicates) {
        if (p == predicate) return true;
    }
```

- [ ] **Step 4: Build + run, verify PASS.** Rebuild; `.venv/bin/ctest --test-dir build -R GeneralFactPredicates --output-on-failure` → expect PASS.

- [ ] **Step 5: Full ctest — no regression.** `.venv/bin/ctest --test-dir build --output-on-failure 2>&1 | tail -4` → expect 652 (650 + 2 new), 0 failed.

- [ ] **Step 6: Commit.**
```bash
cd /Users/jaredguo-mini/develop/memory/starling && git add include/starling/extractor/predicate_registry.hpp tests/cpp/test_validation_policy.cpp tests/cpp/CMakeLists.txt && git commit -F - <<'EOF'
feat(general-content): kGeneralFactPredicates — general facts are core/approved

A 4th curated predicate class (is_a/instance_of/has_property/has_value/part_of/
related_to/depends_on/reports_to) scanned by is_core_predicate, mirroring A's
kActionPredicates + B's kPerceptionPredicates. General-fact predicates are now
approved (not REVIEW_REQUESTED). No overlap with the existing core set.

EOF
```
(Drop `tests/cpp/CMakeLists.txt` from the add if no new test file was created.)

---

## Phase 2 — `general_fact_prompt` + config field (Python)

### Task 2.1: The general-fact extraction prompt

**Files:**
- Create: `python/starling/extractor/general_fact_prompt.py`

- [ ] **Step 1: Create the prompt module** (no test of its own — it's prompt data, exercised by Phase 3). It carries TWO placeholders: `{self}` (filled by `MemoryCore` with the agent name) and `{convo}` (filled by the C++ `Extractor`). Both are literal `str.replace`, so the JSON examples' single braces are untouched:
```python
"""Authoritative general-fact extraction prompt (single source) — sub-project C.

remember()'s THIRD pass. Captures standalone DECLARATIVE world-facts (definitions,
properties, quantities, relationships) that the belief pass (focal-speaker mental
states) and episodic pass (physical events) skip, as self-held BELIEVES claims.

Reuses the belief Extractor: this emits the SAME claim-JSON schema as
prompts.py (EXTRACTION_PROMPT). TWO placeholders, both filled by LITERAL
str.replace (NOT str.format): {self} (MemoryCore fills it with the agent name so
holder=self.agent → recallable by the default recall) and {convo} (the C++
Extractor fills it with the passage). Keep the predicate vocabulary in sync with
kGeneralFactPredicates in include/starling/extractor/predicate_registry.hpp.
"""
from __future__ import annotations

GENERAL_FACT_EXTRACTION_PROMPT = """You are a general-fact extractor for a Statement-based memory system.

Given a passage, extract ALL standalone DECLARATIVE FACTS about the world — definitions, properties, quantities, and relationships stated as true. Output ONLY a JSON array.

Each Statement: {"holder": str, "holder_perspective": "FIRST_PERSON", "subject": str, "predicate": str, "object": str, "modality": "BELIEVES", "polarity": "POS"|"NEG", "nesting_depth": 0}

For EVERY fact: holder is "{self}" (the memory's own agent, which records the fact), holder_perspective is "FIRST_PERSON", modality is "BELIEVES", nesting_depth is 0.

predicate must be one of: is_a, instance_of, has_property, has_value, part_of, related_to, depends_on, reports_to, located_at, member_of. Pick the closest underscore form — never free-form English. Guidance:
- is_a / instance_of — definitions/types: "Postgres is a relational database" -> is_a(Postgres, relational database)
- has_property — attributes: "the server is rack-mounted" -> has_property(server, rack-mounted)
- has_value — quantities/measurements: "the budget is $40k" -> has_value(budget, $40k)
- part_of — composition: "the API is part of the platform" -> part_of(API, platform)
- depends_on — dependencies: "auth depends on the token service" -> depends_on(auth, token service)
- reports_to — org relations: "Alice reports to Bob" -> reports_to(Alice, Bob)
- located_at — location of a thing: "the server room is on floor 3" -> located_at(server room, floor 3)
- member_of — membership: "Alice is on the platform team" -> member_of(Alice, platform team)

subject = the entity the fact is about (canonical short noun). object = the value/type/target (canonical short noun, or a number/string for quantities). Drop hedges and modifiers ("the", "service", "system").

DO NOT extract (output nothing for these — other passes own them):
- A person's voiced opinion / belief / commitment / preference / promise in conversation ("I think...", "I'll do X", "Alice prefers Python"). Those are mental-state claims, NOT general facts.
- A physical event or action ("Sally put the ball in the basket", "Tom left the room"). Those are events, NOT general facts.
- If the passage has only conversational claims or physical events with no standalone declarative fact, output [].

WORKED EXAMPLE 1:
Passage:
  Postgres is a relational database. The deploy budget is $40k. Alice reports to Bob.
JSON array:
[
  {"holder":"{self}","holder_perspective":"FIRST_PERSON","subject":"Postgres","predicate":"is_a","object":"relational database","modality":"BELIEVES","polarity":"POS","nesting_depth":0},
  {"holder":"{self}","holder_perspective":"FIRST_PERSON","subject":"deploy budget","predicate":"has_value","object":"$40k","modality":"BELIEVES","polarity":"POS","nesting_depth":0},
  {"holder":"{self}","holder_perspective":"FIRST_PERSON","subject":"Alice","predicate":"reports_to","object":"Bob","modality":"BELIEVES","polarity":"POS","nesting_depth":0}
]

WORKED EXAMPLE 2 (no general facts):
Passage:
  Alice: I think Bob should handle auth. Then she put the report on the desk.
JSON array:
[]
(A voiced opinion ("I think...") belongs to the belief pass; "put the report on the desk" is a physical event for the episodic pass. Neither is a standalone declarative world-fact, so output [].)

Passage:
{convo}

JSON array:"""
```

- [ ] **Step 2: Sanity-check it imports + has both placeholders.**
```bash
cd /Users/jaredguo-mini/develop/memory/starling && .venv/bin/python -c "from starling.extractor.general_fact_prompt import GENERAL_FACT_EXTRACTION_PROMPT as P; assert '{self}' in P and '{convo}' in P; print('ok', len(P))"
```
Expected: `ok <len>`.

- [ ] **Step 3: Commit.**
```bash
cd /Users/jaredguo-mini/develop/memory/starling && git add python/starling/extractor/general_fact_prompt.py && git commit -F - <<'EOF'
feat(general-content): GENERAL_FACT_EXTRACTION_PROMPT (declarative-fact pass)

The third-pass prompt: extracts standalone declarative world-facts (definitions/
properties/quantities/relationships) as self-held BELIEVES claims in the belief
Extractor's JSON schema. Two literal placeholders: {self} (MemoryCore fills the
agent name) + {convo} (C++ fills the passage). Anti-overlap guidance skips
mental-state claims + physical events. Predicate vocab synced with
kGeneralFactPredicates.

EOF
```

### Task 2.2: `ExtractionConfig.general_fact_prompt` field

**Files:**
- Modify: `python/starling/extractor/config.py`
- Test: `tests/python/test_extraction_config.py` (extend)

- [ ] **Step 1: Add the failing assertion** to `tests/python/test_extraction_config.py`'s `test_defaults_match_module_constants` (and import): add
```python
from starling.extractor.general_fact_prompt import GENERAL_FACT_EXTRACTION_PROMPT
```
and inside the test:
```python
    assert c.general_fact_prompt == GENERAL_FACT_EXTRACTION_PROMPT
```

- [ ] **Step 2: Run, verify FAIL.** `.venv/bin/python -m pytest tests/python/test_extraction_config.py -v` → FAIL (`ExtractionConfig` has no `general_fact_prompt`).

- [ ] **Step 3: Add the field** to `python/starling/extractor/config.py`: add the import
```python
from .general_fact_prompt import GENERAL_FACT_EXTRACTION_PROMPT
```
and the field (after `episodic_prompt`):
```python
    general_fact_prompt: str = GENERAL_FACT_EXTRACTION_PROMPT
```

- [ ] **Step 4: Run, verify PASS.** `.venv/bin/python -m pytest tests/python/test_extraction_config.py -v` → PASS.

- [ ] **Step 5: Commit.**
```bash
cd /Users/jaredguo-mini/develop/memory/starling && git add python/starling/extractor/config.py tests/python/test_extraction_config.py && git commit -F - <<'EOF'
feat(general-content): ExtractionConfig.general_fact_prompt (default-on)

4th carrier field defaulting to GENERAL_FACT_EXTRACTION_PROMPT, so the third pass
is on by default and per-deployment overridable via the existing #3 seam.

EOF
```

---

## Phase 3 — third-pass wiring + e2e

### Task 3.1: Wire the third pass in `MemoryCore.remember` ({self} fill + merge) + spy test

**Files:**
- Modify: `python/starling/_memory_core.py`
- Test: `tests/python/test_extraction_config_wiring.py` (extend)

**Context:** `remember` currently runs belief (`memory_remember` #1, creates engram) then episodic (`EpisodicExtractor` on `engram_ref`). Add a third pass: a second `memory_remember` with the `{self}`-filled `general_fact_prompt` (idempotent engram → re-extracts, confirmed `memory_ops.cpp:48-69`). `holder_id = holder or self.agent` is already computed in `remember`.

- [ ] **Step 1: Write the failing spy test** (append to `tests/python/test_extraction_config_wiring.py`):
```python
def test_third_general_pass_runs_with_self_filled_prompt(tmp_path, monkeypatch):
    import starling._memory_core as mc
    from starling.extractor.config import ExtractionConfig
    prompts = []

    def spy(adapter, llm, prompt, **kw):
        prompts.append(prompt)
        return {"engram_ref": "eng-1", "statement_ids": [], "outcome": "stub"}

    class FakeEpisodic:
        def __init__(self, *a):
            pass

        def extract(self, **kw):
            return []

    monkeypatch.setattr(mc._core, "memory_remember", spy)
    monkeypatch.setattr(mc._core, "EpisodicExtractor", FakeEpisodic)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), agent="self",
        llm=starling.make_stub_llm(default_response="[]"))
    mem._core.remember("Postgres is a relational database.")

    # exactly two memory_remember calls: belief (#1) then general (#2)
    assert len(prompts) == 2
    assert prompts[0] == ExtractionConfig().belief_prompt
    expected_general = ExtractionConfig().general_fact_prompt.replace("{self}", "self")
    assert prompts[1] == expected_general
    assert "{self}" not in prompts[1]
```

- [ ] **Step 2: Run, verify FAIL.** `.venv/bin/python -m pytest tests/python/test_extraction_config_wiring.py -k third_general -v` → FAIL (`len(prompts) == 1`; only the belief pass calls `memory_remember`).

- [ ] **Step 3: Wire the third pass.** In `python/starling/_memory_core.py` `MemoryCore.remember`, AFTER the episodic block (after the `event_ids` merge), add:
```python
        # 第三条:general-fact 抽取(陈述性世界事实)。复用 belief Extractor:
        # 同一(idempotent)engram 上再跑一次 memory_remember,用 general prompt。
        # {self} 由 holder_id(=self.agent)填充,使事实 holder=self.agent → 默认
        # recall(holder=self) 命中。best-effort 第三条,空集正常。
        gf_prompt = self._extraction.general_fact_prompt.replace("{self}", holder_id)
        gf = _core.memory_remember(
            self.rt.adapter, self.llm, gf_prompt,
            tenant_id=self.tenant, holder_id=holder_id,
            interlocutor=interlocutor or "",
            adapter_name=self.adapter_name, source_prefix=self.source_prefix,
            created_at_iso8601=created_iso, payload=text.encode("utf-8"),
            policy=_build_policy(self._extraction))
        gf_ids = gf.get("statement_ids", []) if gf else []
        if gf_ids:
            out["statement_ids"] = list(out.get("statement_ids", [])) + list(gf_ids)
```
(Place it so `out` is the dict already returned/merged by the belief+episodic passes, before `remember` returns. Confirm `out` is still in scope and is the return value.)

- [ ] **Step 4: Reconcile the prior #3 wiring spies (known interaction).** The third pass adds a SECOND `memory_remember` call, so `_install_spies`'s `captured["belief"] = prompt` (in `tests/python/test_extraction_config_wiring.py`) now gets OVERWRITTEN by the general call → `test_custom_prompts_forwarded` / `test_default_prompts_forwarded` break (they'd see the general prompt, not the belief prompt). **Fix:** change that one line in `_install_spies` from `captured["belief"] = prompt` to `captured.setdefault("belief", prompt)` — `setdefault` keeps the FIRST (belief) call's prompt, so those tests pass unchanged. (`captured["episodic"]` comes from `FakeEpisodic` — unaffected. `test_policy_built_from_config` / `test_default_policy_built` capture `policy`, which is the SAME `_build_policy` result on both calls — unaffected.) Then run `.venv/bin/python -m pytest tests/python/test_extraction_config_wiring.py -v` → all pass (prior tests + the new third-pass test).

- [ ] **Step 5: Full regression.** `.venv/bin/python -m pytest -q 2>&1 | tail -3` → 0 failures. If any test elsewhere asserted "remember makes exactly one memory_remember call" or counted statements in a way the third pass perturbs, reconcile (the third pass on real/stub content that returns `[]` adds nothing; only stubs returning non-empty for ALL prompts add general statements).

- [ ] **Step 6: Commit.**
```bash
cd /Users/jaredguo-mini/develop/memory/starling && git add python/starling/_memory_core.py tests/python/test_extraction_config_wiring.py && git commit -F - <<'EOF'
feat(general-content): third general-fact pass in MemoryCore.remember

After belief + episodic, remember runs a third memory_remember with the {self}-
filled general_fact_prompt on the idempotent engram -> self-held BELIEVES general
facts, statement-ids merged. {self} is filled with holder_id (=self.agent) so the
facts land under the recall-default holder. Best-effort (empty general extraction
is a no-op). Spy test pins the two-call sequence + the {self} fill.

EOF
```

### Task 3.2: Roundtrip e2e — declarative text → stored, approved, self-held, recallable

**Files:**
- Test: `tests/python/test_general_content_e2e.py`

**Context:** Phase 1 proved general predicates are approved; Task 3.1 proved the third pass runs with the general prompt. This proves end-to-end: declarative text → a general fact stored as an approved, FIRST_PERSON, `holder=self` BELIEVES statement (the recall-default scope). Reads back via SQLite (reliable; the embedded facade's stub embedder makes *semantic* recall non-deterministic, so assert the stored row + holder/status, mirroring the configurability milestone's e2e which read `review_status` via `sqlite3`).

- [ ] **Step 1: Find the read pattern.** Grep `tests/python/test_extraction_config_e2e.py` (the #3 milestone e2e) for its `sqlite3.connect` + `SELECT review_status FROM statements WHERE ...` pattern; reuse it.

- [ ] **Step 2: Write the e2e.** A `make_stub_llm(default_response=<canned general-fact JSON>)` where the canned JSON is a one-element array: `{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Alice","predicate":"reports_to","object":"Bob","modality":"BELIEVES","polarity":"POS","nesting_depth":0}` (confidence defaults / set ≥0.5 if the schema needs it). `Memory.open(db, agent="self", llm=...)`; `mem.remember("Alice reports to Bob.")`. Then read back via `sqlite3`:
```python
import sqlite3
con = sqlite3.connect(db)
rows = con.execute(
    "SELECT holder_id, holder_perspective, review_status FROM statements "
    "WHERE predicate='reports_to'").fetchall()
con.close()
assert rows, "general fact not stored"
holder, persp, review = rows[0]
assert holder == "self"                       # holder=self.agent -> recall-default scope
assert review != "review_requested"           # general predicate is core -> approved
```
(Verify the exact column names — `holder_id` vs `holder`, `holder_perspective` casing — against the schema / the #3 e2e; adapt. If `holder_perspective` is stored, assert it is the first-person value.) Then assert recallability via a STRUCTURED path if one is reliable with the stub embedder (e.g. `mem.query(...)` by subject, or a tom primitive for `self`); if only semantic `recall` exists and is stub-embedder-dependent, the stored-row assertion (holder=self + approved) IS the recall-eligibility proof — keep the SQL assertion as load-bearing and add a structured-query assertion only if it's deterministic.

**Attribution note (per spec §6.2):** with `default_response`, the belief pass also accepts this JSON (stub ignores the prompt; the real belief prompt skips declarative facts). That's a harmless stub artifact — Task 3.1's spy is the general-pass-specific proof. This e2e proves the end-to-end storage+holder+approval.

- [ ] **Step 3: Run, verify PASS.** `.venv/bin/python -m pytest tests/python/test_general_content_e2e.py -v` → PASS. Debug the canned JSON / column names until the row is stored with holder=self and an approved status.

- [ ] **Step 4: Full regression (ctest + pytest).**
```
.venv/bin/ctest --test-dir build --output-on-failure 2>&1 | tail -4
.venv/bin/python -m pytest -q 2>&1 | tail -3
```
Expect ctest 652, pytest baseline + new, 0 failures.

- [ ] **Step 5: Commit.**
```bash
cd /Users/jaredguo-mini/develop/memory/starling && git add tests/python/test_general_content_e2e.py && git commit -F - <<'EOF'
test(general-content): e2e — declarative text -> approved self-held general fact

Drives remember with a stub emitting a declarative-fact claim; asserts the fact is
stored as an approved (not review_requested), holder=self, FIRST_PERSON BELIEVES
statement -> in the default recall(holder=self) scope. Closes the
text -> recallable general fact loop.

EOF
```

---

## Final review (controller, after all tasks)
- [ ] Dispatch a final reviewer over `git diff b7e4c56..HEAD`: spec compliance (third pass reuses belief Extractor; kGeneralFactPredicates core/approved; holder=self.agent via {self}; default-on; recall unchanged), no new extractor, no canonicalize/reconstructor/prompt-content touch, best-effort.
- [ ] Confirm ctest 652 / pytest (baseline + new) green.
- [ ] Report: changes list, test counts, a worked snippet (`mem.remember("Postgres is a relational database. Alice reports to Bob.")` → recallable `is_a`/`reports_to` self-facts). STOP before push/merge/roadmap.

## Self-review (plan author)
- **Spec coverage:** general_fact_prompt → Task 2.1; ExtractionConfig.general_fact_prompt (default-on) → Task 2.2; third-pass wiring + {self} fill → Task 3.1; kGeneralFactPredicates (core/approved) → Task 1.1; holder=self.agent recallable → Task 3.2; reuse belief Extractor (no new extractor) → Task 3.1 (memory_remember reuse). All covered.
- **Type/name consistency:** `GENERAL_FACT_EXTRACTION_PROMPT` (constant) / `general_fact_prompt` (field + local) / `kGeneralFactPredicates` / `{self}`+`{convo}` placeholders consistent across 1.1/2.1/2.2/3.1. `_build_policy` reused from #3. `holder_id` is the `{self}` fill source.
- **No placeholders:** the full prompt is in Task 2.1; grep anchors (existing `is_core_predicate` test fixture in 1.1; the #3 e2e SQL pattern + exact column names in 3.2) are verbatim-lookups.
- **Ordering:** Phase 1 C++ (rebuild) so general predicates are core BEFORE the pass emits them; Phase 2 pure Python prompt+field; Phase 3 wiring (pure Python, no rebuild) + e2e. Task 3.1 Step 4/5 flags that prior `memory_remember`-spy tests may now see two calls — reconcile.
