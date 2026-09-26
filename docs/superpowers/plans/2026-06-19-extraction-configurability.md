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

# Extraction Configurability Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose a construction-time `ExtractionConfig` on `Memory.open` that injects per-domain belief/episodic prompts, additive core predicates, and tuned confidence thresholds — without forking the prompt constants or recompiling for vocab/threshold changes.

**Architecture:** A frozen Python `ExtractionConfig` (defaults == today's constants) threads through `Memory.open` → `MemoryCore` → the existing `memory_remember`/`EpisodicExtractor` prompt seam (already wired in C++/bindings, just unplumbed). Vocab + thresholds become a C++ `ValidationPolicy` struct threaded through `validate_extracted_statement`/`validate_for_write`/`Extractor`/`memoryops::remember` + bindings; a default-constructed policy reproduces today byte-for-byte. Three phases: ① Python carrier + prompt wiring + `max_tokens` factory rider, ② C++ `ValidationPolicy`, ③ wire config→policy + e2e.

**Tech Stack:** C++20 (validator, extractor), pybind11 bindings, Python adaptation layer, pytest + gtest/ctest.

**Spec:** `docs/superpowers/specs/2026-06-19-extraction-configurability-design.md` (commit 7ece500).

**Baseline:** ctest 644 / pytest 626 (15 skipped). The load-bearing invariant: a default-constructed `ExtractionConfig` / `ValidationPolicy` reproduces today exactly — every existing pin stays green.

**Build/test commands (repo root `/Users/jaredguo-mini/develop/memory/starling`, cwd resets each Bash call → absolute paths):**
- Build (after C++/binding change): `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`
- C++ test: `.venv/bin/ctest --test-dir build -R <Name> --output-on-failure` (`.venv/bin/ctest`, not bare `ctest`)
- Editable rebuild (after C++/binding change, before pytest sees it): add `--python-editable` to the configure_build invocation
- pytest: `.venv/bin/python -m pytest <file> -v`

**Hard constraints (every task):** core logic (the `ValidationPolicy` decision) is C++; Python is carrier + forwarding + bindings only. Default policy/config == today (parity + 644 ctest). Do NOT touch `canonicalize_*`, the reconstructor, the prompt *content*, or `validate_for_write`'s cross-tenant logic (only thread the policy). `extra_core_predicates` is additive. `perceived_by_json` immutable. API key never a param/never logged. TDD: failing test → red → minimal impl → green → commit. explicit-path `git add` (never `.`/`-A`); no `--no-verify`/`--amend`. Do NOT push / merge / touch roadmap (accumulates with #2/#4).

---

## Task 0: Baseline confirmation (controller — do directly)

- [ ] Confirm ctest 644 / pytest 626 green before starting (the spec's invariant baseline). Run:
  - `.venv/bin/ctest --test-dir build --output-on-failure 2>&1 | tail -3`
  - `.venv/bin/python -m pytest -q 2>&1 | tail -3`
  Expected: 644 ctest pass, 626 pass / 15 skipped. If not, stop and reconcile before dispatching Task 1.1.

---

## Phase 1 — Python carrier + prompt wiring + max_tokens rider (pure Python, no rebuild)

### Task 1.1: `ExtractionConfig` dataclass

**Files:**
- Create: `python/starling/extractor/config.py`
- Modify: `python/starling/__init__.py` (re-export)
- Test: `tests/python/test_extraction_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/python/test_extraction_config.py
import dataclasses

import pytest

import starling
from starling.extractor.config import ExtractionConfig
from starling.extractor.prompts import EXTRACTION_PROMPT
from starling.extractor.episodic_prompt import EPISODIC_EXTRACTION_PROMPT


def test_defaults_match_module_constants():
    c = ExtractionConfig()
    assert c.belief_prompt == EXTRACTION_PROMPT
    assert c.episodic_prompt == EPISODIC_EXTRACTION_PROMPT
    assert c.extra_core_predicates == ()
    assert c.confidence_drop_floor == 0.30
    assert c.weak_inference_floor == 0.50


def test_frozen_immutable():
    c = ExtractionConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.belief_prompt = "x"


def test_reexported_from_starling():
    assert starling.ExtractionConfig is ExtractionConfig
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/python/test_extraction_config.py -v`
Expected: FAIL (ModuleNotFoundError: `starling.extractor.config`).

- [ ] **Step 3: Create the dataclass**

```python
# python/starling/extractor/config.py
"""Per-deployment extraction configuration carrier (single construction-time object).

Injected at Memory.open(extraction=...); a default-constructed ExtractionConfig
reproduces today's behaviour exactly (the prompt constants + the validator's
built-in core predicate set + the 0.3/0.5 thresholds). belief_prompt/episodic_prompt
plumb the prompt seam that already exists in C++/bindings; extra_core_predicates +
the two floors become a C++ ValidationPolicy at the write boundary (see
MemoryCore._build_policy / statement_validator.cpp). extra_core_predicates is
ADDITIVE to the built-in constexpr core set and (because the vocab gate exempts
modality=OCCURRED) only affects belief-tier statements.
"""
from __future__ import annotations

from dataclasses import dataclass

from .prompts import EXTRACTION_PROMPT
from .episodic_prompt import EPISODIC_EXTRACTION_PROMPT


@dataclass(frozen=True)
class ExtractionConfig:
    belief_prompt: str = EXTRACTION_PROMPT
    episodic_prompt: str = EPISODIC_EXTRACTION_PROMPT
    extra_core_predicates: tuple[str, ...] = ()
    confidence_drop_floor: float = 0.30
    weak_inference_floor: float = 0.50
```

- [ ] **Step 4: Re-export from the package root**

Grep `python/starling/__init__.py` for the existing public re-exports (e.g. the line exporting `Memory` / `make_stub_llm`). Add alongside them:
```python
from .extractor.config import ExtractionConfig
```
and add `"ExtractionConfig"` to `__all__` if an `__all__` list is present.

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/python/test_extraction_config.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add python/starling/extractor/config.py python/starling/__init__.py tests/python/test_extraction_config.py
git commit -F - <<'EOF'
feat(configurability): ExtractionConfig carrier (defaults == today)

Frozen dataclass holding belief_prompt/episodic_prompt + extra_core_predicates +
confidence_drop_floor/weak_inference_floor, all defaulting to today's constants/
thresholds. Re-exported as starling.ExtractionConfig. Not yet consumed (Task 1.2
wires the prompts; Task 3.1 the policy).

EOF
```

### Task 1.2: Thread `ExtractionConfig` prompts through `Memory.open` → `MemoryCore.remember`

**Files:**
- Modify: `python/starling/memory.py` (`Memory.__init__`, `Memory.open`)
- Modify: `python/starling/_memory_core.py` (`MemoryCore.__init__`, `MemoryCore.remember`)
- Test: `tests/python/test_extraction_config_wiring.py`

- [ ] **Step 1: Write the failing test** (spy on the C++ boundary — `make_stub_llm` does not expose the received prompt, so assert the prompt string forwarded into `_core.memory_remember` / `_core.EpisodicExtractor`)

```python
# tests/python/test_extraction_config_wiring.py
import starling
import starling._memory_core as mc
from starling.extractor.prompts import EXTRACTION_PROMPT
from starling.extractor.episodic_prompt import EPISODIC_EXTRACTION_PROMPT


def _install_spies(monkeypatch, captured):
    def fake_remember(adapter, llm, prompt, **kw):
        captured["belief"] = prompt
        # engram_ref non-empty so MemoryCore runs the episodic pass too.
        return {"engram_ref": "eng-1", "statement_ids": [], "outcome": "stub"}

    class FakeEpisodic:
        def __init__(self, conn, llm, adapter, prompt):
            captured["episodic"] = prompt

        def extract(self, **kw):
            return []

    monkeypatch.setattr(mc._core, "memory_remember", fake_remember)
    monkeypatch.setattr(mc._core, "EpisodicExtractor", FakeEpisodic)


def test_custom_prompts_forwarded(tmp_path, monkeypatch):
    captured = {}
    _install_spies(monkeypatch, captured)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"),
        extraction=starling.ExtractionConfig(belief_prompt="SENTINEL-BELIEF",
                                             episodic_prompt="SENTINEL-EPISODIC"))
    mem._core.remember("hi")
    assert captured["belief"] == "SENTINEL-BELIEF"
    assert captured["episodic"] == "SENTINEL-EPISODIC"


def test_default_prompts_forwarded(tmp_path, monkeypatch):
    captured = {}
    _install_spies(monkeypatch, captured)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"))
    mem._core.remember("hi")
    assert captured["belief"] == EXTRACTION_PROMPT
    assert captured["episodic"] == EPISODIC_EXTRACTION_PROMPT
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/python/test_extraction_config_wiring.py -v`
Expected: FAIL — `Memory.open()` got an unexpected keyword argument `extraction` (and the default-path test fails because the spy sees the hardcoded constant, which currently happens to equal EXTRACTION_PROMPT, so that one may pass; the custom-prompt test is the red one).

- [ ] **Step 3: Wire `MemoryCore`**

In `python/starling/_memory_core.py`:
- Add the import near the other extractor imports (`:22-23` region, where `EXTRACTION_PROMPT` / `EPISODIC_EXTRACTION_PROMPT` are imported):
```python
from .extractor.config import ExtractionConfig
```
- `MemoryCore.__init__` (`:73-75`) — add a keyword param and store it (sibling of `adapter_name`/`source_prefix` at `:80-81`):
```python
    def __init__(self, rt, *, agent: str, tenant_id: str, llm=None,
                 adapter_name: str, source_prefix: str,
                 vector_backend: str = "sqlite", vector_store_path=None,
                 extraction: "ExtractionConfig | None" = None):
```
and in the body:
```python
        self._extraction = extraction or ExtractionConfig()
```
- `MemoryCore.remember` — replace the hardcoded constants:
  - belief call (`:125`): `EXTRACTION_PROMPT` → `self._extraction.belief_prompt`
  - episodic ctor (`:138`): `EPISODIC_EXTRACTION_PROMPT` → `self._extraction.episodic_prompt`

- [ ] **Step 4: Wire `Memory`**

In `python/starling/memory.py`:
- `Memory.__init__` (`:115`) — add `extraction=None` and forward into `MemoryCore`:
```python
    def __init__(self, rt, *, agent: str, tenant_id: str, llm, extraction=None):
        self._rt = rt
        self._core = MemoryCore(rt, agent=agent, tenant_id=tenant_id, llm=llm,
                                adapter_name="facade", source_prefix="mem-",
                                extraction=extraction)
        self._core.set_embedder(_core.StubEmbeddingAdapter(8))
```
- `Memory.open` (`:124-126`) — add `extraction=None` and pass through:
```python
    @classmethod
    def open(cls, db_path, *, agent: str = "self", tenant_id: str = "default",
             llm=None, extraction=None) -> "Memory":
        _runtime.relax_preflight_for_embedded()
        rt = _runtime._build_local_store_sqlite_runtime(Path(db_path))
        rt.start()
        return cls(rt, agent=agent, tenant_id=tenant_id, llm=llm, extraction=extraction)
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/python/test_extraction_config_wiring.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Regression — full pytest (no rebuild; pure Python)**

Run: `.venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: 628 passed (626 + 2 new wiring; Task 1.1's 3 are also counted) / 15 skipped. (Exact total = baseline + new tests; the point is zero failures.)

- [ ] **Step 7: Commit**

```bash
git add python/starling/memory.py python/starling/_memory_core.py tests/python/test_extraction_config_wiring.py
git commit -F - <<'EOF'
feat(configurability): inject ExtractionConfig prompts through Memory.open

MemoryCore.remember now uses self._extraction.belief_prompt / .episodic_prompt
instead of the hardcoded module constants; Memory.open(extraction=...) threads the
carrier (default ExtractionConfig() == today). Spy tests assert the injected (and
default) prompt strings reach the _core.memory_remember / EpisodicExtractor
boundary. Pure Python; the prompt seam already existed in C++/bindings.

EOF
```

### Task 1.3: `max_tokens` rider on the LLM factories

**Files:**
- Modify: `python/starling/memory.py` (`make_openai_llm`, `make_anthropic_llm`)
- Test: `tests/python/test_llm_factory_max_tokens.py`

- [ ] **Step 1: Write the failing test** (env-gated; `from_env()` requires the key. Assert the factory constructs without error when `max_tokens` is passed — mirrors the untested `timeout_ms`/`max_retries` params; the config field itself is already bound + covered by `OpenAIAdapterConfig`)

```python
# tests/python/test_llm_factory_max_tokens.py
import inspect

import starling


def test_make_openai_llm_accepts_max_tokens(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid")
    llm = starling.make_openai_llm(model="m", max_tokens=32768)
    assert llm is not None


def test_max_tokens_in_signature():
    assert "max_tokens" in inspect.signature(starling.make_openai_llm).parameters
    assert "max_tokens" in inspect.signature(starling.make_anthropic_llm).parameters
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/python/test_llm_factory_max_tokens.py -v`
Expected: FAIL (`max_tokens` not a parameter / unexpected keyword argument).

- [ ] **Step 3: Add the param to both factories**

In `python/starling/memory.py`, `make_openai_llm` (`:48-67`) — add `max_tokens: int = 0` to the signature and, after the `max_retries` override (`:65-66`):
```python
    if max_tokens:
        cfg.max_tokens = max_tokens
```
Do the same in `make_anthropic_llm` (`:70-88`).

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/python/test_llm_factory_max_tokens.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add python/starling/memory.py tests/python/test_llm_factory_max_tokens.py
git commit -F - <<'EOF'
feat(configurability): expose max_tokens on make_openai_llm/make_anthropic_llm

Mirrors the existing timeout_ms/max_retries override pattern (from_env() then
override explicit fields). Closes the gap where reasoning models truncate at the
4096 default and callers had to hand-build OpenAIAdapterConfig. API key still
env-only.

EOF
```

---

## Phase 2 — C++ `ValidationPolicy` (vocab + thresholds)

### Task 2.1: `ValidationPolicy` struct + policy-aware validator + ctest

**Files:**
- Modify: `include/starling/extractor/statement_validator.hpp` (add struct + defaulted param on both fns)
- Modify: `src/extractor/statement_validator.cpp` (thread the policy)
- Test: `tests/cpp/test_validation_policy.cpp` (new) — register in `tests/cpp/CMakeLists.txt`

**Context:** `validate_extracted_statement` (`statement_validator.cpp:26`) is a pure free function. Tunables: `is_weak_inference` `s.confidence < 0.5` (`:21`); drop `s.confidence < 0.3` (`:58`); vocab gate `!is_core_predicate(s.predicate) && s.modality != OCCURRED` → REVIEW_REQUESTED (`:81-82`). `validate_for_write` calls the base at `:93`. A default `ValidationPolicy{}` must reproduce all three exactly.

- [ ] **Step 1: Write the failing ctest**

Grep `tests/cpp/` for the existing validator test (e.g. `grep -rl validate_extracted_statement tests/cpp`) and reuse its helper that builds a fully-populated valid `ExtractedStatement` (all required non-empty fields: holder_id, holder_tenant_id, subject_kind, subject_id, predicate, object_kind ∈ {bool,int,float,str,...}, object_value, canonical_object_hash, observed_at, source_hash, confidence, modality). If none is reusable, add a local `make_valid_belief(predicate)` helper in the new test file. Then:

```cpp
// tests/cpp/test_validation_policy.cpp
#include <gtest/gtest.h>
#include "starling/extractor/statement_validator.hpp"
#include "starling/schema/statement_enums.hpp"

using namespace starling::extractor;
using starling::schema::ReviewStatus;
using starling::schema::Modality;

// make_valid_belief(pred): a fully-populated, non-OCCURRED, confidence=0.9
// ExtractedStatement with predicate=pred (reuse the existing fixture if present).
// ... helper here ...

TEST(ValidationPolicy, ExtraPredicateNotReviewed) {
    auto s = make_valid_belief("annotates");
    ValidationPolicy pol; pol.extra_core_predicates = {"annotates"};
    auto out = validate_extracted_statement(s, pol);
    EXPECT_TRUE(out.accepted);
    EXPECT_FALSE(out.review_status_override.has_value());
}
TEST(ValidationPolicy, DefaultFlagsUnknownPredicate) {
    auto s = make_valid_belief("annotates");
    auto out = validate_extracted_statement(s);  // default policy
    EXPECT_TRUE(out.accepted);
    ASSERT_TRUE(out.review_status_override.has_value());
    EXPECT_EQ(*out.review_status_override, ReviewStatus::REVIEW_REQUESTED);
}
TEST(ValidationPolicy, LoweredDropFloorKeepsLowConfidence) {
    auto s = make_valid_belief("believes"); s.confidence = 0.2;
    ValidationPolicy pol; pol.confidence_drop_floor = 0.15;
    auto out = validate_extracted_statement(s, pol);
    EXPECT_TRUE(out.accepted);
}
TEST(ValidationPolicy, DefaultDropFloorDropsLowConfidence) {
    auto s = make_valid_belief("believes"); s.confidence = 0.25;
    auto out = validate_extracted_statement(s);  // default policy
    EXPECT_FALSE(out.accepted);
    EXPECT_EQ(out.error_kind, "below_minimum_confidence");
}
TEST(ValidationPolicy, RaisedWeakFloorFlagsModerateConfidence) {
    auto s = make_valid_belief("believes"); s.confidence = 0.6;  // core predicate so the vocab gate doesn't overwrite the flag
    ValidationPolicy pol; pol.weak_inference_floor = 0.7;
    auto out = validate_extracted_statement(s, pol);
    EXPECT_TRUE(out.accepted);
    ASSERT_TRUE(out.review_status_override.has_value());
    EXPECT_EQ(*out.review_status_override, ReviewStatus::INFERRED_UNREVIEWED);
}
TEST(ValidationPolicy, OccurredUnknownPredicateKeptVerbatim) {
    auto s = make_valid_belief("teleported"); s.modality = Modality::OCCURRED;
    auto out = validate_extracted_statement(s);  // default policy
    EXPECT_TRUE(out.accepted);
    EXPECT_FALSE(out.review_status_override.has_value());
}
```
Register in `tests/cpp/CMakeLists.txt`: add `test_validation_policy.cpp` to the `add_executable(starling_tests ...)` source list (gtest_discover_tests auto-registers).

- [ ] **Step 2: Build + run to verify it fails**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`
Expected: COMPILE ERROR — `validate_extracted_statement` takes 1 arg / `ValidationPolicy` undeclared.

- [ ] **Step 3: Add the struct + defaulted params to the header**

In `include/starling/extractor/statement_validator.hpp` — add `#include <vector>` and, before the function declarations:
```cpp
struct ValidationPolicy {
    std::vector<std::string> extra_core_predicates;   // ADDITIVE to the constexpr core set
    double confidence_drop_floor = 0.30;
    double weak_inference_floor  = 0.50;
};
```
Change the two declarations to:
```cpp
ValidationOutcome validate_extracted_statement(const ExtractedStatement& s,
                                               const ValidationPolicy& policy = {});

ValidationOutcome validate_for_write(
    const ExtractedStatement& s,
    const std::function<std::string(const std::string&)>& resolve_parent_tenant,
    const ValidationPolicy& policy = {});
```

- [ ] **Step 4: Thread the policy in the `.cpp`**

In `src/extractor/statement_validator.cpp`:
- `is_weak_inference` — add a floor param; only the numeric clause changes:
```cpp
bool is_weak_inference(const ExtractedStatement& s, double weak_floor) {
    return s.holder_perspective == schema::Perspective::HEARSAY
        || s.holder_perspective == schema::Perspective::INFERRED
        || s.provenance == schema::StatementProvenance::TOM_INFERRED
        || s.confidence < weak_floor;
}
```
- add a local helper in the anonymous namespace:
```cpp
bool in_extra_set(const std::vector<std::string>& extra, const std::string& pred) {
    for (const auto& p : extra) { if (p == pred) return true; }
    return false;
}
```
- `validate_extracted_statement(const ExtractedStatement& s, const ValidationPolicy& policy)`:
  - drop gate (`:58`): `if (s.confidence < 0.3)` → `if (s.confidence < policy.confidence_drop_floor)`. **Keep the detail string literal `"confidence < 0.3 — extractor drops per §15.3.2"` unchanged** (existing tests may assert it; the floor staleness in the message when tuned is cosmetic and acceptable).
  - weak flag: `if (is_weak_inference(s))` → `if (is_weak_inference(s, policy.weak_inference_floor))`.
  - vocab gate (`:81`): `if (!is_core_predicate(s.predicate) && s.modality != schema::Modality::OCCURRED)` → `if (!is_core_predicate(s.predicate) && !in_extra_set(policy.extra_core_predicates, s.predicate) && s.modality != schema::Modality::OCCURRED)`.
- `validate_for_write(..., const ValidationPolicy& policy)` — forward to the base: `auto base = validate_extracted_statement(s, policy);` (`:93`).

- [ ] **Step 5: Build + run to verify it passes**

Run:
```
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build
.venv/bin/ctest --test-dir build -R ValidationPolicy --output-on-failure
```
Expected: 6 ValidationPolicy tests PASS.

- [ ] **Step 6: Full ctest — no regression**

Run: `.venv/bin/ctest --test-dir build --output-on-failure 2>&1 | tail -5`
Expected: 650 pass (644 + 6 new). Zero failures — the default-policy path is unchanged.

- [ ] **Step 7: Commit**

```bash
git add include/starling/extractor/statement_validator.hpp src/extractor/statement_validator.cpp tests/cpp/test_validation_policy.cpp tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(configurability): ValidationPolicy makes vocab + thresholds injectable

validate_extracted_statement / validate_for_write gain a defaulted ValidationPolicy
(extra_core_predicates additive to the constexpr core set; confidence_drop_floor /
weak_inference_floor replacing the 0.3 / 0.5 literals). A default-constructed policy
reproduces today exactly (extra_core_predicates only bites non-OCCURRED belief rows;
the OCCURRED exemption is unchanged). 6 ctests pin both the custom and default paths.

EOF
```

### Task 2.2: Thread the policy through `Extractor` + `memoryops::remember`

**Files:**
- Modify: `include/starling/extractor/extractor.hpp` (both ctors + `policy_` member)
- Modify: `src/extractor/extractor.cpp` (pass `policy_` to the validate call site)
- Modify: `include/starling/memory/memory_ops.hpp` + `src/memory/memory_ops.cpp` (`remember` policy param → Extractor ctor)

**Context:** No new behaviour — a defaulted policy keeps every path at today's defaults; the e2e in Phase 3 proves the thread carries a custom policy. Acceptance = builds + full ctest still green.

- [ ] **Step 1: Add `policy_` to `Extractor`**

In `include/starling/extractor/extractor.hpp` — `#include "starling/extractor/statement_validator.hpp"`; add a defaulted trailing `ValidationPolicy policy = {}` to BOTH ctors (`:29-32` conn-only, `:42-46` store-adapter), store `policy_(std::move(policy))`; add member `ValidationPolicy policy_;` near `prompt_template_` (`:86`).

- [ ] **Step 2: Pass `policy_` at the validate call site**

In `src/extractor/extractor.cpp` — grep for `validate_extracted_statement(` / `validate_for_write(` inside `run()`; pass `policy_` as the trailing arg (e.g. `validate_for_write(stmt, resolve_parent_tenant, policy_)`).

- [ ] **Step 3: Add the policy param to `memoryops::remember`**

In `include/starling/memory/memory_ops.hpp` (`:45-47`) — add `const extractor::ValidationPolicy& policy = {}` to the `remember` signature (after `prompt_template`, include the validator header). In `src/memory/memory_ops.cpp` (`:65`) — pass `policy` into the `extractor::Extractor` ctor it constructs.

- [ ] **Step 4: Build + full ctest (no regression)**

Run:
```
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build
.venv/bin/ctest --test-dir build --output-on-failure 2>&1 | tail -5
```
Expected: 650 pass (unchanged — defaulted policy). If any signature-mismatch compile error in other callers of `remember`/the `Extractor` ctor, they get the default policy automatically (no edit needed); fix only genuine breaks.

- [ ] **Step 5: Commit**

```bash
git add include/starling/extractor/extractor.hpp src/extractor/extractor.cpp include/starling/memory/memory_ops.hpp src/memory/memory_ops.cpp
git commit -F - <<'EOF'
feat(configurability): thread ValidationPolicy through Extractor + memoryops::remember

Both Extractor ctors and memoryops::remember gain a defaulted ValidationPolicy
forwarded to the validate call site. Defaulted everywhere → 650 ctest unchanged;
Phase 3's e2e exercises a custom policy end-to-end.

EOF
```

### Task 2.3: Bind `ValidationPolicy` + the `memory_remember` policy kwarg

**Files:**
- Modify: `bindings/python/bind_06_extractor.cpp` (bind the struct)
- Modify: `bindings/python/bind_13_memory_ops.cpp` (policy kwarg on `memory_remember`)
- Test: `tests/python/test_validation_policy_binding.py`

**Context:** `py::arg("policy") = ValidationPolicy{}` materializes the type at binding-definition time → `ValidationPolicy` MUST be bound in the earlier-numbered file (06 < 13). Bind in `bind_06_extractor.cpp` (which already binds `OpenAIAdapterConfig`); ensure `<pybind11/stl.h>` is included for `vector<string>` ↔ `list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/python/test_validation_policy_binding.py
import starling


def test_validation_policy_fields():
    pol = starling._core.ValidationPolicy()
    assert pol.confidence_drop_floor == 0.30
    assert pol.weak_inference_floor == 0.50
    assert list(pol.extra_core_predicates) == []
    pol.extra_core_predicates = ["annotates", "cites"]
    pol.confidence_drop_floor = 0.15
    pol.weak_inference_floor = 0.70
    assert list(pol.extra_core_predicates) == ["annotates", "cites"]
    assert pol.confidence_drop_floor == 0.15
    assert pol.weak_inference_floor == 0.70
```

- [ ] **Step 2: Build editable + run to verify it fails**

Run:
```
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build --python-editable
.venv/bin/python -m pytest tests/python/test_validation_policy_binding.py -v
```
Expected: FAIL (`_core` has no attribute `ValidationPolicy`).

- [ ] **Step 3: Bind the struct** (in `bindings/python/bind_06_extractor.cpp`, mirroring the `OpenAIAdapterConfig` binding `:158-165`; add `#include <pybind11/stl.h>` if absent)

```cpp
py::class_<starling::extractor::ValidationPolicy>(m, "ValidationPolicy")
    .def(py::init<>())
    .def_readwrite("extra_core_predicates", &starling::extractor::ValidationPolicy::extra_core_predicates)
    .def_readwrite("confidence_drop_floor", &starling::extractor::ValidationPolicy::confidence_drop_floor)
    .def_readwrite("weak_inference_floor", &starling::extractor::ValidationPolicy::weak_inference_floor);
```
(Include `starling/extractor/statement_validator.hpp`.)

- [ ] **Step 4: Add the policy kwarg to `memory_remember`** (in `bindings/python/bind_13_memory_ops.cpp`)

Grep the `memory_remember` binding (the `m.def("memory_remember", ...)` lambda + its `py::arg` list, `:26`/`:45`/`:51` region). Add a `ValidationPolicy policy` lambda param forwarded to `memoryops::remember(..., policy)`, and `py::arg("policy") = starling::extractor::ValidationPolicy{}` to the arg list. (Include the validator header.)

- [ ] **Step 5: Build editable + run to verify it passes**

Run:
```
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build --python-editable
.venv/bin/python -m pytest tests/python/test_validation_policy_binding.py -v
```
Expected: PASS.

- [ ] **Step 6: Regression — full pytest**

Run: `.venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: baseline + new tests, zero failures.

- [ ] **Step 7: Commit**

```bash
git add bindings/python/bind_06_extractor.cpp bindings/python/bind_13_memory_ops.cpp tests/python/test_validation_policy_binding.py
git commit -F - <<'EOF'
feat(configurability): bind ValidationPolicy + memory_remember policy kwarg

ValidationPolicy bound in bind_06 (before bind_13, so the py::arg default
materializes); memory_remember gains a defaulted policy kwarg. Default-constructed
policy keeps every existing caller at today's behaviour.

EOF
```

---

## Phase 3 — Wire config → policy + end-to-end

### Task 3.1: `MemoryCore` builds the policy from `ExtractionConfig`

**Files:**
- Modify: `python/starling/_memory_core.py` (`_build_policy` helper + pass `policy=` in `remember`)
- Test: extend `tests/python/test_extraction_config_wiring.py`

- [ ] **Step 1: Write the failing test** (spy captures the real `_core.ValidationPolicy` built from the config)

```python
# append to tests/python/test_extraction_config_wiring.py
def test_policy_built_from_config(tmp_path, monkeypatch):
    captured = {}

    def fake_remember(adapter, llm, prompt, *, policy=None, **kw):
        captured["policy"] = policy
        return {"engram_ref": "", "statement_ids": [], "outcome": "stub"}

    monkeypatch.setattr(mc._core, "memory_remember", fake_remember)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"),
        extraction=starling.ExtractionConfig(extra_core_predicates=("annotates",),
                                             confidence_drop_floor=0.15,
                                             weak_inference_floor=0.7))
    mem._core.remember("hi")
    pol = captured["policy"]
    assert list(pol.extra_core_predicates) == ["annotates"]
    assert pol.confidence_drop_floor == 0.15
    assert pol.weak_inference_floor == 0.7


def test_default_policy_built(tmp_path, monkeypatch):
    captured = {}

    def fake_remember(adapter, llm, prompt, *, policy=None, **kw):
        captured["policy"] = policy
        return {"engram_ref": "", "statement_ids": [], "outcome": "stub"}

    monkeypatch.setattr(mc._core, "memory_remember", fake_remember)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"))
    mem._core.remember("hi")
    pol = captured["policy"]
    assert list(pol.extra_core_predicates) == []
    assert pol.confidence_drop_floor == 0.30
    assert pol.weak_inference_floor == 0.50
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/python/test_extraction_config_wiring.py -k policy -v`
Expected: FAIL — `fake_remember` is called without a `policy` kwarg (TypeError on missing, or `captured["policy"]` is None) because `remember` doesn't pass it yet.

- [ ] **Step 3: Build the policy + pass it**

In `python/starling/_memory_core.py` — add a module-level helper:
```python
def _build_policy(extraction):
    pol = _core.ValidationPolicy()
    pol.extra_core_predicates = list(extraction.extra_core_predicates)
    pol.confidence_drop_floor = extraction.confidence_drop_floor
    pol.weak_inference_floor = extraction.weak_inference_floor
    return pol
```
In `MemoryCore.remember`, add `policy=_build_policy(self._extraction)` to the `_core.memory_remember(...)` call (`:124-129`).

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/python/test_extraction_config_wiring.py -v`
Expected: PASS (all wiring tests, including the 2 new policy ones).

- [ ] **Step 5: Commit**

```bash
git add python/starling/_memory_core.py tests/python/test_extraction_config_wiring.py
git commit -F - <<'EOF'
feat(configurability): MemoryCore builds ValidationPolicy from ExtractionConfig

remember() now passes policy=_build_policy(self._extraction) into memory_remember;
default ExtractionConfig() yields a default ValidationPolicy (==today). Spy tests
pin both the custom and default policy.

EOF
```

### Task 3.2: End-to-end behavioral test (real stub-LLM through the C++ validator)

**Files:**
- Test: `tests/python/test_extraction_config_e2e.py`

**Context:** Phase-1/3.1 spies prove the config→prompt and config→policy *plumbing*; Task 2.1's ctest proves the validator *honours* a policy. This task proves the two meet end-to-end: a custom `extra_core_predicates` makes a custom-predicate belief statement land approved (not REVIEW_REQUESTED) through the real write path.

- [ ] **Step 1: Find the belief-path stub template**

Grep `tests/python/` for an existing test that drives the belief extractor with `make_stub_llm` returning belief-claim JSON and then reads a statement's `review_status` (e.g. `grep -rl review_status tests/python` / look for the canned JSON shape the belief parser expects: the `EXTRACTION_PROMPT` output format — claims with subject/predicate/object/confidence). Copy that canned-JSON shape.

- [ ] **Step 2: Write the e2e test**

Using the template's canned-belief-JSON shape, write a statement whose `predicate` is a custom domain verb (e.g. `"annotates"`), driven by `make_stub_llm(default_response=<that JSON>)`. Two cases:
- with `extraction=ExtractionConfig(extra_core_predicates=("annotates",))` → after `mem.remember(...)`, the resulting statement's `review_status` is the approved/default status (NOT `REVIEW_REQUESTED`).
- with default `extraction` (no config) → the same custom-predicate statement IS `REVIEW_REQUESTED`.
Read the statement back via the same query the template uses (the adapter / a `_core` read by statement id from the `remember` result's `statement_ids`). If the template reads `review_status` through a specific accessor, reuse it verbatim.

- [ ] **Step 3: Run to verify both cases**

Run: `.venv/bin/python -m pytest tests/python/test_extraction_config_e2e.py -v`
Expected: PASS (custom predicate approved under policy; flagged without it).

- [ ] **Step 4: Full regression — ctest + pytest**

Run:
```
.venv/bin/ctest --test-dir build --output-on-failure 2>&1 | tail -5
.venv/bin/python -m pytest -q 2>&1 | tail -3
```
Expected: ctest 650, pytest baseline + all new config tests, zero failures.

- [ ] **Step 5: Commit**

```bash
git add tests/python/test_extraction_config_e2e.py
git commit -F - <<'EOF'
test(configurability): e2e — extra_core_predicates approves a custom belief predicate

Drives the real belief write path with a stub LLM emitting a custom-predicate
statement: with ExtractionConfig(extra_core_predicates=("annotates",)) it lands
approved; without it, REVIEW_REQUESTED. Closes the config→policy→validator loop.

EOF
```

---

## Final review (controller, after all tasks)

- [ ] Dispatch a final code reviewer over the whole diff (`git diff main...HEAD` for the configurability commits): spec compliance (all four knobs injectable; default == today), no `canonicalize_*`/reconstructor/prompt-content touch, additive-only predicates, API key never logged.
- [ ] Confirm ctest 650 / pytest (baseline 626 + new) green.
- [ ] Report to user: changes list, test counts, a worked snippet (`Memory.open(db, llm=make_openai_llm(model=…, max_tokens=32768), extraction=ExtractionConfig(belief_prompt=…, extra_core_predicates=(…,), confidence_drop_floor=0.15))`). STOP before push/merge/roadmap (accumulates with #2/#4 per "先 2、3、4").

## Self-review (plan author)

- **Spec coverage:** belief_prompt/episodic_prompt → Task 1.2; extra_core_predicates → Task 2.1 (validator) + 2.3 (bind) + 3.1 (wire) + 3.2 (e2e); confidence_drop_floor/weak_inference_floor → Task 2.1 + 3.1; max_tokens rider → Task 1.3; carrier/Memory.open → Task 1.1/1.2; default==today invariant → Task 2.1 default-path ctests + 3.1 default-policy spy. All covered.
- **Type consistency:** `ExtractionConfig` fields (belief_prompt/episodic_prompt/extra_core_predicates/confidence_drop_floor/weak_inference_floor) 1:1 with C++ `ValidationPolicy` (extra_core_predicates/confidence_drop_floor/weak_inference_floor); `_build_policy` maps tuple→list. `validate_extracted_statement(s, policy={})` / `validate_for_write(s, resolve, policy={})` consistent across 2.1/2.2. `make_openai_llm(..., max_tokens=0)` matches the timeout_ms/max_retries override idiom.
- **No placeholders:** every code step has concrete code; the two grep anchors (existing validator fixture in 2.1; belief stub template in 3.2) are verbatim-lookups, not undefined behaviour.
- **Ordering:** Phase 1 pure-Python (no rebuild); Phase 2 rebuilds (2.1/2.2 C++, 2.3 editable); Phase 3 pure-Python wiring + e2e. Binding-order gotcha (06<13) called out in 2.3.
