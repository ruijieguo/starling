# Extraction Configurability — Design

**Date:** 2026-06-19
**Status:** Approved (design); pending implementation plan.
**Context:** Third and final stage of the extraction-grounding sequence (resolution ✅ → completeness ✅ → **configurability**). The first two stages hard-wired *better* extraction behaviour into the single source-of-truth prompt constants and the C++ reconstructor. This stage makes the extraction policy **injectable per deployment/domain** without forking those constants or recompiling: a caller can supply custom belief/episodic prompts, extra domain predicates the validator treats as core, and tuned confidence thresholds. The prompt-injection seam already exists end-to-end in C++/bindings (`Extractor`/`EpisodicExtractor` ctor `prompt_template`, `memory_remember`'s `prompt_template` param) but is plumbed to **no** Python public surface — the constants are hardcoded at exactly one point (`_memory_core.py:125` belief + `:138` episodic). The vocabulary (`predicate_registry.hpp` `constexpr`) and the two confidence thresholds (`statement_validator.cpp` literals `0.3`/`0.5`) are compile-time and need a real C++ change to become injectable.

---

## 1. Goal & scope

Expose one cohesive, construction-time **`ExtractionConfig`** carrier on the embedded `Memory` facade that lets a caller override, per `Memory` instance:

1. **`belief_prompt`** — the conversation/belief extraction prompt (default = `EXTRACTION_PROMPT`).
2. **`episodic_prompt`** — the narrative/episodic extraction prompt (default = `EPISODIC_EXTRACTION_PROMPT`).
3. **`extra_core_predicates`** — domain predicates the validator treats as core (**additive** to the built-in `constexpr` set), so custom-domain belief predicates are auto-accepted instead of downgraded to `REVIEW_REQUESTED`.
4. **`confidence_drop_floor`** (default `0.30`) + **`weak_inference_floor`** (default `0.50`) — the two tunable validator thresholds.

Plus a small model-ergonomics rider: widen `make_openai_llm` / `make_anthropic_llm` to expose `max_tokens` (today only settable by hand-building `OpenAIAdapterConfig` — the gap the eval harness hit). **Model selection itself stays in the `llm` adapter** the caller already passes to `Memory.open` (clean separation; `ExtractionConfig` does NOT carry a model, to avoid a second source of truth that conflicts with `llm`).

**The load-bearing invariant: a default-constructed `ExtractionConfig` (and default C++ `ValidationPolicy`) reproduces today's behaviour byte-for-byte** — same prompts, same `constexpr` predicate set, same `0.3`/`0.5`. Back-compat + every existing pin (ctest 644 / pytest 626) stays green.

**Decisions locked (brainstorming):**
1. **Scope = full** (prompts + model ergonomics + vocab + thresholds), including the C++ validator change for vocab/thresholds.
2. **Carrier = `Memory.open(extraction=…)` + a `MemoryCore` field** (embedded facade, the programmatic surface). NOT `DashboardConfig` — dashboard persistence/wiring is a deferred follow-on.
3. **Granularity = construction-time** (set once at `Memory.open`, applies to all `remember()` calls). No per-call override (YAGNI — a domain is per-deployment).

**Out of scope (deferred):**
- **Dashboard wiring / `starling.json` persistence** of the extraction config (carrier decision A is embedded-only). A later change can serialize `ExtractionConfig` onto `DashboardConfig` and thread it through `DashboardEngine`.
- **Per-`remember()` override** (granularity A).
- **Full predicate-set *replacement*** — `extra_core_predicates` is additive only (the built-in belief/action/perception classes always stay core). Replacing the base set is unnecessary and would silently break B/A behaviour.
- **Model in `ExtractionConfig`** — stays in the `llm` adapter.

## 2. Current state (file:line)

- **Hardcoded prompt constants (single source):** `python/starling/extractor/prompts.py:17` `EXTRACTION_PROMPT`; `python/starling/extractor/episodic_prompt.py:23` `EPISODIC_EXTRACTION_PROMPT`. Consumed at exactly one place: `python/starling/_memory_core.py:125` (belief, positional arg 3 to `_core.memory_remember`) + `:138` (episodic, arg 4 to `_core.EpisodicExtractor`). Empty `prompt_template` is a FakeLLM test stub, not a production prompt (`extractor.cpp:147` `build_prompt_body_for_tests`) — so the constants are load-bearing.
- **Prompt seam exists, unplumbed:** `Extractor` ctor `prompt_template` (`include/starling/extractor/extractor.hpp:29`/`:42`); `EpisodicExtractor` ctor `prompt_template`; `memory_remember`'s `prompt_template` binding param (`bind_13_memory_ops.cpp`) → threaded to `memoryops::remember` → `extractor::Extractor` (`memory_ops.cpp:65`). No Python public knob — `Memory.open` (`memory.py:124-126`: `db_path, agent, tenant_id, llm`) and `MemoryCore.__init__` (`_memory_core.py:73-75`) take no prompt/config param.
- **Validator (pure free function, no config):** `src/extractor/statement_validator.cpp:26` `validate_extracted_statement(const ExtractedStatement& s)`. Tunable literals: `is_weak_inference` `s.confidence < 0.5` (`:21`); drop `s.confidence < 0.3` (`:58`). Vocab gate: `if (!is_core_predicate(s.predicate) && s.modality != schema::Modality::OCCURRED)` → `REVIEW_REQUESTED` (`:81-82`). `validate_for_write` calls the base validator at `:93`. Header `statement_validator.hpp:25`/`:38`.
- **Vocabulary (compile-time):** `include/starling/extractor/predicate_registry.hpp:16-50` — three `inline constexpr std::array` (`kCoreBeliefPredicates` 10, `kActionPredicates` 10, `kPerceptionPredicates` 4) + `is_core_predicate(std::string_view)` linear scan.
- **Model ergonomics gap:** `make_openai_llm` (`memory.py:48-67`) / `make_anthropic_llm` (`:70-88`) expose `model/base_url/timeout_ms/max_retries` but **not** `max_tokens` (bound on `OpenAIAdapterConfig`, `bind_06_extractor.cpp:164`, default 4096). Reasoning models truncate at 4096 → empty extraction; today you must hand-build the config.
- **`MemoryCore` already holds config-like state** (`_memory_core.py:80-81`: `adapter_name`, `source_prefix`) — the natural sibling slot for `self._extraction`.

## 3. Architecture

### 3.1 The Python carrier — `ExtractionConfig` (new, `python/starling/extractor/config.py`)

A frozen dataclass (immutable + hashable; tuple not list):

```python
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

`ExtractionConfig()` (all defaults) == today. Re-exported from `starling` (`__init__.py`) so callers do `starling.ExtractionConfig(...)`.

### 3.2 The C++ policy — `ValidationPolicy` (new, vocab + thresholds)

The validator becomes policy-aware via a small struct (placed in `include/starling/extractor/statement_validator.hpp`, bound like `OpenAIAdapterConfig`):

```cpp
struct ValidationPolicy {
    std::vector<std::string> extra_core_predicates;   // ADD to the constexpr core set
    double confidence_drop_floor = 0.30;
    double weak_inference_floor  = 0.50;
};
```

Changes in `src/extractor/statement_validator.cpp` (default-constructed `ValidationPolicy{}` ⇒ identical to today):
- `validate_extracted_statement` gains a defaulted trailing param: `validate_extracted_statement(const ExtractedStatement& s, const ValidationPolicy& policy = {})`.
- `validate_for_write` gains the same defaulted param and forwards it to its inner `validate_extracted_statement(s, policy)` call (`:93`).
- The drop literal `0.3` (`:58`) → `policy.confidence_drop_floor`.
- `is_weak_inference` takes the floor: its `s.confidence < 0.5` (`:21`) → `s.confidence < weak_inference_floor`; the `HEARSAY`/`INFERRED`/`TOM_INFERRED` perspective/provenance clauses are unchanged (only the numeric floor is tunable).
- The vocab gate (`:81`): `!is_core_predicate(s.predicate)` → `!is_core_predicate(s.predicate) && !contains(policy.extra_core_predicates, s.predicate)` (a small local `contains` helper or `std::find`). The `&& s.modality != OCCURRED` clause is **unchanged** — OCCURRED rows are still never downgraded, so `extra_core_predicates` only affects **belief-tier (non-OCCURRED)** statements (episodic events are exempt by construction). Thresholds apply wherever the validator runs.

### 3.3 Threading the policy (mirror the existing `prompt_template` seam)

- `Extractor` gains an optional `ValidationPolicy policy_` member set via a new defaulted ctor param (both ctors), passed to the validator inside `run()` (the plan greps the exact `validate_extracted_statement`/`validate_for_write` call site). Default `ValidationPolicy{}` = pre-change behaviour.
- `memoryops::remember` (`memory_ops.cpp`) gains a `const ValidationPolicy& policy = {}` param forwarded to the `Extractor` ctor it builds (`:65`).
- **Bindings (`bindings/python/`):** bind the `ValidationPolicy` struct (`def_readwrite` on the three fields + default ctor, like `OpenAIAdapterConfig` in `bind_06_extractor.cpp`, with `<pybind11/stl.h>` for the `vector<string>` ↔ `list[str]` field); add a defaulted `policy` kwarg to the `memory_remember` binding (`bind_13_memory_ops.cpp`). **Binding order:** the `py::arg("policy") = ValidationPolicy{}` default materializes the type at definition time, so `ValidationPolicy` must be bound in an earlier-numbered bind file (06 < 13 — bind it in `bind_06_extractor.cpp`).
- **Episodic path:** the episodic prompt threads through the existing `EpisodicExtractor` `prompt_template` ctor arg (no policy needed there — episodic events are OCCURRED, exempt from the vocab gate; whether `EpisodicExtractor` runs the threshold checks is confirmed in the plan and the policy threads there only if it does).

### 3.4 Wiring `ExtractionConfig` → the call path

- `make_openai_llm` / `make_anthropic_llm` (`memory.py`): add `max_tokens: int = 0` param → `if max_tokens: cfg.max_tokens = max_tokens` (mirrors the existing `timeout_ms`/`max_retries` override pattern exactly).
- `Memory.open(db_path, *, agent="self", tenant_id="default", llm=None, extraction: "ExtractionConfig | None" = None)` → forwards `extraction` to `Memory.__init__` → `MemoryCore(...)`.
- `MemoryCore.__init__(..., extraction=None)` stores `self._extraction = extraction or ExtractionConfig()` (sibling of `adapter_name`/`source_prefix`).
- `MemoryCore.remember`:
  - belief: `_core.memory_remember(self.rt.adapter, self.llm, self._extraction.belief_prompt, …, policy=_build_policy(self._extraction))` where `_build_policy` constructs a `_core.ValidationPolicy` from the three policy fields.
  - episodic: `_core.EpisodicExtractor(self.conn, self.llm, self.rt.adapter, self._extraction.episodic_prompt)`.

## 4. Data flow

```
caller: Memory.open(db, llm=make_openai_llm(model="…", max_tokens=32768),
                     extraction=ExtractionConfig(belief_prompt=MY_PROMPT,
                                                 extra_core_predicates=("annotates","cites"),
                                                 confidence_drop_floor=0.15))
→ MemoryCore stores self._extraction
→ remember(text):
    belief  → memory_remember(adapter, llm, MY_PROMPT, …, policy=ValidationPolicy{extra=[annotates,cites], drop=0.15, weak=0.5})
              → Extractor(…, MY_PROMPT, policy) → validate_extracted_statement(s, policy)
                  · predicate "annotates" → in policy.extra → NOT REVIEW_REQUESTED
                  · confidence 0.2 → ≥ policy.confidence_drop_floor(0.15) → kept (default 0.3 would drop)
    episodic → EpisodicExtractor(conn, llm, adapter, EPISODIC_EXTRACTION_PROMPT default)
```
Default path (`Memory.open(db, llm=…)` with no `extraction=`): `ExtractionConfig()` → today's constants + `ValidationPolicy{}` → byte-identical to current behaviour.

## 5. Error handling

- Unknown/empty fields default to today's constants/thresholds (`extraction or ExtractionConfig()`; `belief_prompt` defaults to `EXTRACTION_PROMPT`). A caller passing an empty `belief_prompt=""` would hit the FakeLLM test-stub path — documented as caller error, not a crash.
- `extra_core_predicates` is purely additive; an entry already in the `constexpr` set is a harmless no-op.
- Thresholds are not range-validated by the policy (the existing `[0.0,1.0]` confidence *validity* check at `:52` is independent and unchanged); a nonsensical floor (e.g. `> 1.0`) just drops everything / nothing — caller's responsibility, never crashes.
- Best-effort parity: any code path not passing a policy gets `ValidationPolicy{}` = today.

## 6. Testing (two tracks + regression)

1. **C++ ctest** (`tests/cpp/`, new validator-policy test): with a custom `ValidationPolicy{extra_core_predicates={"annotates"}, confidence_drop_floor=0.15, weak_inference_floor=0.7}` — (a) a belief statement with predicate `"annotates"` (non-OCCURRED) is accepted with **no** `REVIEW_REQUESTED`; (b) a `0.2`-confidence statement is **kept** (default `0.3` would drop); (c) a `0.6`-confidence statement **with a core predicate** (e.g. `believes`, so the vocab gate does not overwrite the flag) is flagged `INFERRED_UNREVIEWED` (raised weak floor `0.7`). And **default-policy reproduces today**: an out-of-vocab non-OCCURRED predicate → `REVIEW_REQUESTED`; `0.25` confidence → dropped; an OCCURRED out-of-vocab verb → kept verbatim.
2. **Python e2e** (`tests/python/`, stub-LLM): inject a custom `ExtractionConfig(belief_prompt=SENTINEL_PROMPT, extra_core_predicates=("annotates",), confidence_drop_floor=0.15)` into `Memory.open` and verify end-to-end that (a) the injected **policy** changes the validation outcome — a belief statement with predicate `"annotates"` lands **approved** (not `REVIEW_REQUESTED`), confirming the `ExtractionConfig`→`ValidationPolicy`→validator path is plumbed; (b) the injected `belief_prompt`/`episodic_prompt` are the strings **forwarded to the extractors** — asserted by spying on the `_core.memory_remember` / `EpisodicExtractor` boundary (the prompt arg equals `SENTINEL_PROMPT`), since `make_stub_llm` does not expose the received prompt for direct byte-capture. Plus a **default-path test**: `Memory.open` with no `extraction=` → the spy shows `EXTRACTION_PROMPT`/`EPISODIC_EXTRACTION_PROMPT` forwarded and a default `ValidationPolicy`, behaviour unchanged. (The plan picks the exact spy mechanism — `pytest-mock` is available.)
3. **`max_tokens` factory:** a focused test that `make_openai_llm(max_tokens=N)` sets the config field (env-gated like the eval, or asserted on the built adapter's config) — low-risk, mirrors `timeout_ms`/`max_retries`.
4. **Regression:** ctest 644 → +new policy tests; pytest 626 → +new config tests. The default path is byte-identical (default policy/prompts), so belief / multi-order-ToM / six-state / conflict / A-episodic / B-perception / grounding / completeness pins all stay green.

## 7. Constraints

Core logic (the `ValidationPolicy` decision — vocab membership + thresholds) is **C++** (`src/extractor/statement_validator.cpp`, `include/starling/extractor/`); Python is only the carrier (`ExtractionConfig`) + forwarding (`_memory_core.py`, `memory.py`) + bindings. **A default-constructed `ValidationPolicy` / `ExtractionConfig` must reproduce today exactly** (the parity + 644-ctest guarantee). Do NOT touch `canonicalize_object`/`canonicalize_string`, the reconstructor, the prompt *content* (only its injectability), or `validate_for_write`'s cross-tenant logic (only thread the policy through). `extra_core_predicates` is additive (never replaces the base set). `perceived_by_json` immutable. The API key is never a parameter / never logged (`max_tokens` widening keeps `from_env()` reading `OPENAI_API_KEY`). TDD: failing test → red → minimal impl → green → commit. Build from repo root `/Users/jaredguo-mini/develop/memory/starling`; after C++/binding changes rebuild with `--python-editable`; C++ tests via `.venv/bin/ctest --test-dir build`. explicit-path `git add` (never `.`/`-A`); commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`; no `--no-verify`/`--amend`. Design phase burns no API.

**Phasing (for the plan):** ① Python `ExtractionConfig` carrier + prompt injection wiring + `max_tokens` factory widening (pure Python — the prompt seam already exists) → ② C++ `ValidationPolicy` + validator change + thread through `Extractor`/`memoryops::remember` + bindings → ③ `MemoryCore` builds the policy from `ExtractionConfig` + the end-to-end stub-LLM e2e. Each phase keeps ctest/pytest green.
