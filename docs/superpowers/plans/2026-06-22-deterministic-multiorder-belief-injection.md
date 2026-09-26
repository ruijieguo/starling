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

# Deterministic Multi-Order Belief Query Injection — Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Starling compute HiToM order 3-4 nested beliefs deterministically and inject the answer into the in-loop dump, so deepseek-v4-pro reads instead of reasons (stops the 32768-token exhaustion: measured fallback 39%/68% at order 3/4).

**Architecture:** Three components across the C++/Python boundary. ① extraction: the episodic prompt captures the scene-initial "X is in Y" stative as a location event; the *unchanged* reconstructor's present-cast witness logic assigns the initial location to every present agent (fills the perception gap). ② core: `what_does_X_think_chain` generalizes the existing order-2 observer-intersection to arbitrary N (additive; `what_does_X_think` untouched). ③ eval: the in-loop server (renamed `starling_tomeval_server.py`) parses the HiToM cognizer-chain + theme, calls the chain query, and injects the computed answer definitively.

**Tech Stack:** C++20 (`src/tom/`, gtest), pybind11 (`bindings/python/`), Python (`python/starling/`, pytest), FastAPI eval server, SQLite perception_state.

**Spec:** `docs/superpowers/specs/2026-06-22-deterministic-multiorder-belief-injection-design.md` (commit `184794f`).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `python/starling/extractor/episodic_prompt.py` | episodic extraction prompt (config data) | Modify — add bare-stative rule + Worked Example 6 |
| `src/tom/mentalizing_chain.cpp` | `what_does_X_think_chain` (core N-order query) | Create |
| `include/starling/tom/mentalizing.hpp` | declare the new query | Modify — add declaration after `what_does_X_think` |
| `CMakeLists.txt` | build sources | Modify — add `src/tom/mentalizing_chain.cpp` to `starling_core` |
| `tests/cpp/test_mentalizing_chain.cpp` | ctests for the chain query | Create |
| `tests/cpp/CMakeLists.txt` | test sources | Modify — add the new test to `starling_tests` |
| `bindings/python/bind_08_tom.cpp` | pybind for the chain query | Modify — add `.def` after `what_does_X_think` |
| `python/starling/tom/primitives.py` | thin Python wrapper | Modify — add `what_does_X_think_chain` |
| `tests/python/test_chain_belief_roundtrip.py` | stub-LLM round-trip | Create |
| `scripts/starling_tombench_server.py` → `scripts/starling_tomeval_server.py` | in-loop server | `git mv` + add chain parse/query/inject |
| `tests/python/test_tomeval_server_chain.py` | server parser + injection unit tests | Create |

---

## Task 0: Confirm green baseline (controller)

**Files:** none (verification only)

- [ ] **Step 1: Build + run the full suite**

Run (from repo root `/Users/jaredguo-mini/develop/memory/starling`):
```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build
.venv/bin/ctest --test-dir build --output-on-failure
.venv/bin/python -m pytest tests/python -q
```
Expected: all ctest pass, all pytest pass. Record the exact counts (baseline ~ctest 644 / pytest 625; confirm actual). If anything is red BEFORE any change, stop and report — do not start on a red baseline.

---

## Task 1: #2 — capture the scene-initial stative as a location event (extraction-side)

**Files:**
- Modify: `python/starling/extractor/episodic_prompt.py` (the `location` RULE ~line 35; add Worked Example 6 after line 99)
- Test: `tests/python/test_chain_belief_roundtrip.py` (created here; extended in Task 4)

**Why:** HiToM's "The watermelon is in the green_bucket" names no person, so the current prompt does not emit it as an event → `perception_state` never gets the initial location → an agent who only saw the initial location has `has_belief=false`. The reconstructor *already* witnesses a located event by `present ∪ participants`, and `present` defaults to the whole entered cast (see `perception_reconstructor.cpp` cast/present logic) — so we only need the event to EXIST with a non-empty actor (required by `episodic_extractor.cpp:132`, which skips events with empty actor) and `participants=[]`; the reconstructor assigns the initial location to everyone present.

- [ ] **Step 1: Write the failing stub-LLM e2e test**

Find the stub-LLM pattern first: `grep -n "class .*Adapter\|def extract\|StubLLM\|stub" tests/python/test_completeness_e2e.py tests/python/test_perception_e2e.py` — mirror how those build a deterministic-event stub adapter and open a Memory with it.

Create `tests/python/test_chain_belief_roundtrip.py`:
```python
"""Round-trip: a HiToM-style story whose scene-initial location is a bare stative.
The leaver (saw only the initial location) must end with a belief at the initial
location — i.e. perception_state must contain the initial location for ALL agents
present at the scene-initial fact, established from a participant-less location event."""
import json

import starling
from starling.tom import what_does_X_think

# The episodic JSON the new prompt is designed to elicit for a BARE scene-initial
# stative "The watermelon is in the green_bucket" (NO person named): a `find` with
# participants=[] (no one is NAMED in the fact) and a present actor. The reconstructor's
# present-cast (present defaults to the whole cast) witnesses it, so every present agent
# perceives the initial location. Cast here = {Noah, Emma} (Noah's leave + Emma's move
# register them); both are present at the find (seq 1) -> both perceive green_bucket.
# This is the bare-stative sibling of test_completeness_e2e.py (which lists explicit
# finders); here NO one is named, so participants=[] and present-cast does the witnessing.
_CANNED = json.dumps([
    {"actor": "Noah", "action": "find", "theme": "watermelon", "location": "green_bucket",
     "participants": [], "time": None},
    {"actor": "Noah", "action": "leave", "theme": "hall", "location": None,
     "participants": ["Noah"], "time": None},
    {"actor": "Emma", "action": "move", "theme": "watermelon", "location": "blue_chest",
     "participants": ["Emma"], "time": None},
])


def test_bare_stative_perceived_by_all_present_then_leaver_keeps_it(tmp_path):
    # make_stub_llm wraps the C++ FakeLLMAdapter (Memory.open requires a real adapter, not
    # a Python object). default_response is returned for EVERY pass; only the episodic pass
    # turns it into events -> perception_state. Pattern: tests/python/test_completeness_e2e.py:34-56.
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), agent="narrator",
        llm=starling.make_stub_llm(default_response=_CANNED))
    mem.remember(
        "Noah and Emma entered the hall. The watermelon is in the green_bucket. "
        "Noah exited the hall. Emma moved the watermelon to the blue_chest.")
    frontier = starling._core.KnowledgeFrontier(mem._rt.adapter)
    tenant = mem._core.tenant
    # Leaver Noah: saw only the bare-stative initial location, absent for the move.
    noah = what_does_X_think(mem._rt.adapter, frontier, x="Noah", theme="watermelon", tenant_id=tenant)
    assert noah.has_belief, "the bare stative must give the leaver an initial-location belief"
    assert noah.state_value == "green_bucket"
    # Mover Emma: present through the move -> fresh blue_chest.
    emma = what_does_X_think(mem._rt.adapter, frontier, x="Emma", theme="watermelon", tenant_id=tenant)
    assert emma.has_belief
    assert emma.state_value == "blue_chest"
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python -m pytest tests/python/test_chain_belief_roundtrip.py -v`
Expected: this likely PASSES already (the reconstructor's present-cast witnesses the participant-less find — the completeness machinery is in place). It is a contract/regression pin: it locks that a bare-stative location event (participants=[]) gives the leaver the initial-location belief.

- [ ] **Step 3: Interpret the result**

If it PASSES: #2's downstream machinery is correct for a participant-less located event; the remaining deliverable is the PROMPT so the real LLM emits the bare stative — proceed to Step 4. If `noah.has_belief` is False: the participant-less find is NOT being witnessed via present-cast; STOP and report (the design depends on `present` defaulting to the whole cast — recheck `perception_reconstructor.cpp` present/cast init).

- [ ] **Step 4: Add the prompt rule + worked example (the real deliverable)**

In `python/starling/extractor/episodic_prompt.py`, the `location` RULE already mentions "the hat is in the suitcase". Strengthen it for the NO-PERSON bare stative. Replace the sentence starting `For "they find the hat in the suitcase"` (line ~35) — read the file and match the exact current text — appending:
```
 Even when NO person is named — a bare scene-setting "The X is in the Y" right after people enter a place — STILL emit it: action = "find", theme = "X", location = "Y", participants = [] (no one is NAMED in the fact itself), and actor = any person currently present (e.g. the first who just entered) so the event is non-empty. Everyone present when the scene opens perceives this initial location; the memory system assigns it to all of them.
```

Add after Worked Example 5 (line 99), before the `Passage:` footer (line 101):
```
WORKED EXAMPLE 6 (bare scene-initial stative, no person named):

Passage:
  Noah, Emma and Liam entered the hall. The watermelon is in the green_bucket. Noah exited the hall. Emma moved the watermelon to the blue_chest.
JSON array:
[
  {"actor":"Noah","action":"enter","theme":"hall","location":null,"participants":["Noah","Emma","Liam"],"time":null},
  {"actor":"Noah","action":"find","theme":"watermelon","location":"green_bucket","participants":[],"time":null},
  {"actor":"Noah","action":"leave","theme":"hall","location":null,"participants":["Noah"],"time":null},
  {"actor":"Emma","action":"move","theme":"watermelon","location":"blue_chest","participants":["Emma"],"time":null}
]
(The bare "The watermelon is in the green_bucket" names no one, but it is the INITIAL location everyone present sees. Emit it as a "find" with participants=[] and actor set to a present person (Noah). Noah leaves before Emma's move, so Noah keeps believing green_bucket; Emma sees the move to blue_chest.)
```

- [ ] **Step 5: Verify no regression in existing episodic extraction**

Run the episodic/perception/completeness suites that exercise this prompt:
```bash
.venv/bin/python -m pytest tests/python/test_completeness_e2e.py tests/python/test_perception_e2e.py tests/python/test_chain_belief_roundtrip.py -v
```
Expected: PASS (the new example is additive; the "do NOT infer presence" rule for specific later actions is unchanged — the bare-stative exception is narrow). If a real-LLM e2e test drifts, it is gated/skipped without a key; do not chase it here.

- [ ] **Step 6: Commit**
```bash
git add python/starling/extractor/episodic_prompt.py tests/python/test_chain_belief_roundtrip.py
git commit -m "$(cat <<'EOF'
feat(P3/#3): capture scene-initial bare stative as a location event (#2 perception completeness)

HiToM's "The X is in the Y" names no person, so the episodic pass never emitted it ->
perception_state lacked the initial location -> an agent who only saw the initial
location had has_belief=false. Add a prompt rule + Worked Example 6: a bare scene-initial
stative becomes a "find" event with participants=[] and a present actor; the reconstructor's
present-cast witness logic (unchanged) assigns the initial location to everyone present.
Stub-LLM round-trip pins it: the early leaver keeps the initial location, the mover updates.

EOF
)"
```

---

## Task 2: `what_does_X_think_chain` — arbitrary N-order perception query (C++ core)

**Files:**
- Create: `src/tom/mentalizing_chain.cpp`
- Modify: `include/starling/tom/mentalizing.hpp` (declare after `what_does_X_think`, line ~173)
- Modify: `CMakeLists.txt` (add the new `.cpp` to `starling_core`)
- Create: `tests/cpp/test_mentalizing_chain.cpp`
- Modify: `tests/cpp/CMakeLists.txt` (add the new test to `starling_tests`)

**Semantics (generalize `mentalizing_think.cpp:42-53`):** `chain=[c1..cN]`, holder = `cN` (deepest), observers = `c1..c_{N-1}`. Return holder's highest-position perceived state among events in EVERY observer's perceived-event set. N=1 → `last_known`. N=2 → existing observer logic.

- [ ] **Step 1: Declare the function**

In `include/starling/tom/mentalizing.hpp`, immediately after the `what_does_X_think` declaration (ends ~line 173), add:
```cpp
// 9. 任意多阶感知 ToM:chain=[c1..cN],"c1 think c2 think … cN think theme is where"。
//    holder=cN,observers=c1..c_{N-1}。返回 holder 在「所有链成员都感知过的事件」中
//    position 最高的状态。N=1 等价一阶;N=2 等价 what_does_X_think 的 observer 分支。
//    空链 / dim 不可定 / 无交集行 → has_belief=false。
StateBelief what_does_X_think_chain(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    const std::vector<std::string>& chain,
    std::string_view theme,
    std::string_view tenant,
    std::string_view as_of);
```
Confirm `#include <vector>` is present at the top of the header (it is — other returns use `std::vector`).

- [ ] **Step 2: Write the failing ctests**

Create `tests/cpp/test_mentalizing_chain.cpp` (mirror `test_mentalizing_think.cpp`'s `open_migrated` + `seed_event` helpers — copy them into this file's anonymous namespace verbatim from `tests/cpp/test_mentalizing_think.cpp:22-62`):
```cpp
// what_does_X_think_chain: arbitrary multi-order perception ToM (generalizes the
// order-2 observer intersection in test_mentalizing_think.cpp).
#include "starling/tom/mentalizing.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/cognizer/perception_reconstructor.hpp"
#include "starling/store/episodic_event_store.hpp"
#include "starling/store/perception_state_store.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
#include <memory>
#include <string>
#include <vector>

namespace {
// COPY open_migrated() and seed_event() verbatim from tests/cpp/test_mentalizing_think.cpp:22-62.
// (Keep them local; they are test fixtures, not shared production code.)
}  // namespace

using starling::tom::mentalizing::what_does_X_think;
using starling::tom::mentalizing::what_does_X_think_chain;

// Build the standard 3-cognizer scene: all enter (cast={c1,c2,c3}); initial find ball@A
// (participants=[] -> witnessed by all present); c3 leaves; c2 moves ball->B.
static std::unique_ptr<starling::persistence::SqliteAdapter> scene_early_leave(const char* T) {
    auto a = open_migrated();
    seed_event(*a, T, "h0", "c1", "find",  "ball", "A", R"([])",        1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "h1", "c3", "leave", "room", "",  R"(["c3"])",    2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "h2", "c2", "move",  "ball", "B", R"(["c2"])",    3, "2026-01-01T00:00:03Z");
    // c1 needs to be in the cast; give c1 a presence event so the cast includes it.
    seed_event(*a, T, "h3", "c1", "leave", "room", "",  R"(["c1"])",    4, "2026-01-01T00:00:04Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);
    return a;
}

TEST(WhatDoesXThinkChain, OrderOneEqualsFirstOrder) {
    auto a = scene_early_leave("tc1");
    starling::cognizer::KnowledgeFrontier f(*a);
    const char* AS = "2026-01-02T00:00:00Z";
    auto chain = what_does_X_think_chain(*a, f, {"c2"}, "ball", "tc1", AS);
    auto first = what_does_X_think(*a, f, "c2", "ball", "tc1", AS, "");
    EXPECT_EQ(chain.has_belief, first.has_belief);
    EXPECT_EQ(chain.state_value, first.state_value);  // c2 saw A then moved to B -> B
    EXPECT_EQ(chain.state_value, "B");
}

TEST(WhatDoesXThinkChain, OrderTwoEqualsObserverBranch) {
    auto a = scene_early_leave("tc2");
    starling::cognizer::KnowledgeFrontier f(*a);
    const char* AS = "2026-01-02T00:00:00Z";
    // c1 think c2 think ball: == what_does_X_think(c2, observer=c1)
    auto chain = what_does_X_think_chain(*a, f, {"c1", "c2"}, "ball", "tc2", AS);
    auto obs = what_does_X_think(*a, f, "c2", "ball", "tc2", AS, "c1");
    EXPECT_EQ(chain.has_belief, obs.has_belief);
    EXPECT_EQ(chain.state_value, obs.state_value);
}

TEST(WhatDoesXThinkChain, OrderThreeEarlyLeaverReturnsInitial) {
    auto a = scene_early_leave("tc3");
    starling::cognizer::KnowledgeFrontier f(*a);
    const char* AS = "2026-01-02T00:00:00Z";
    // c1 think c2 think c3 think ball: c3 (deepest) saw only A (left before the move);
    // all three co-saw the initial find@A -> A.
    auto r = what_does_X_think_chain(*a, f, {"c1", "c2", "c3"}, "ball", "tc3", AS);
    EXPECT_TRUE(r.has_belief);
    EXPECT_EQ(r.state_value, "A") << "c3 only ever saw the initial A; all co-saw it";
}

TEST(WhatDoesXThinkChain, OrderThreeAllPresentReturnsMoved) {
    auto a = open_migrated();
    const char* T = "tc3b";
    // No one leaves before the move -> all three witness ball->B.
    seed_event(*a, T, "j0", "c1", "find", "ball", "A", R"([])",     1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "j1", "c2", "move", "ball", "B", R"(["c2"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "j2", "c3", "leave", "room", "", R"(["c3"])", 3, "2026-01-01T00:00:03Z");
    seed_event(*a, T, "j3", "c1", "leave", "room", "", R"(["c1"])", 4, "2026-01-01T00:00:04Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);
    starling::cognizer::KnowledgeFrontier f(*a);
    const char* AS = "2026-01-02T00:00:00Z";
    auto r = what_does_X_think_chain(*a, f, {"c1", "c2", "c3"}, "ball", T, AS);
    EXPECT_TRUE(r.has_belief);
    EXPECT_EQ(r.state_value, "B") << "all three present through the move -> B";
}

TEST(WhatDoesXThinkChain, OrderFour) {
    auto a = open_migrated();
    const char* T = "tc4";
    // 4 cognizers all see initial A; c4 leaves first, then move -> chain[c1..c4] = A.
    seed_event(*a, T, "k0", "c1", "find",  "ball", "A", R"([])",     1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "k1", "c4", "leave", "room", "", R"(["c4"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "k2", "c2", "move",  "ball", "B", R"(["c2"])", 3, "2026-01-01T00:00:03Z");
    seed_event(*a, T, "k3", "c3", "leave", "room", "", R"(["c3"])", 4, "2026-01-01T00:00:04Z");
    seed_event(*a, T, "k4", "c1", "leave", "room", "", R"(["c1"])", 5, "2026-01-01T00:00:05Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);
    starling::cognizer::KnowledgeFrontier f(*a);
    const char* AS = "2026-01-02T00:00:00Z";
    auto r = what_does_X_think_chain(*a, f, {"c1", "c2", "c3", "c4"}, "ball", T, AS);
    EXPECT_TRUE(r.has_belief);
    EXPECT_EQ(r.state_value, "A") << "c4 left first; common-witnessed event is the initial A";
}

TEST(WhatDoesXThinkChain, EmptyChainAndUnknownCognizer) {
    auto a = scene_early_leave("tc5");
    starling::cognizer::KnowledgeFrontier f(*a);
    const char* AS = "2026-01-02T00:00:00Z";
    auto empty = what_does_X_think_chain(*a, f, {}, "ball", "tc5", AS);
    EXPECT_FALSE(empty.has_belief);
    auto unknown = what_does_X_think_chain(*a, f, {"c1", "nobody"}, "ball", "tc5", AS);
    EXPECT_FALSE(unknown.has_belief) << "deepest cognizer never perceived the theme";
}
```
Add `tests/cpp/test_mentalizing_chain.cpp` to the `add_executable(starling_tests ...)` source list in `tests/cpp/CMakeLists.txt` (grep for `test_mentalizing_think.cpp` there and add the new file next to it).

- [ ] **Step 3: Run to verify it fails to link**

Run:
```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build
```
Expected: FAIL — link error `undefined reference to what_does_X_think_chain` (declared, not defined).

- [ ] **Step 4: Implement the chain query**

Create `src/tom/mentalizing_chain.cpp`:
```cpp
// what_does_X_think_chain — arbitrary multi-order perception ToM. Generalizes the
// order-2 observer intersection in mentalizing_think.cpp:42-53: holder = chain.back(),
// observers = the rest; the answer is the holder's highest-position perceived state
// among events that EVERY observer also perceived. N=1 -> first-order last_known.
#include "starling/tom/mentalizing.hpp"
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/name_resolver.hpp"
#include "starling/schema/normalize_theme.hpp"
#include "starling/store/perception_state_store.hpp"

#include <optional>
#include <string>
#include <unordered_set>
#include <vector>

namespace starling::tom::mentalizing {

StateBelief what_does_X_think_chain(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    const std::vector<std::string>& chain,
    std::string_view theme,
    std::string_view tenant,
    std::string_view as_of) {
    (void)frontier;  // parity with what_does_X_think (reserved for access checks)
    StateBelief out;
    if (chain.empty()) return out;

    auto& conn = adapter.connection();
    const std::string theme_n = schema::normalize_theme(theme);  // match the write side
    cognizer::CognizerHub hub(adapter);                          // query-side lookup-only
    std::vector<std::string> chain_n;
    chain_n.reserve(chain.size());
    for (const auto& c : chain) chain_n.push_back(cognizer::resolve_cognizer(hub, tenant, c));

    store::PerceptionStateStore ps(conn);
    const std::string dim = ps.dim_for_theme(tenant, theme_n, as_of);
    if (dim.empty()) return out;  // theme never perceived

    const std::string& holder = chain_n.back();
    std::optional<store::PerceptionStateRow> row;
    if (chain_n.size() == 1) {
        row = ps.last_known(tenant, holder, theme_n, dim, as_of);   // first-order
    } else {
        // Each observer's perceived-event-id set for the theme.
        std::vector<std::unordered_set<std::string>> obs_sets;
        obs_sets.reserve(chain_n.size() - 1);
        for (std::size_t i = 0; i + 1 < chain_n.size(); ++i) {
            auto rows = ps.perceived_for_theme(tenant, chain_n[i], theme_n, as_of);
            std::unordered_set<std::string> s;
            for (const auto& r : rows) s.insert(r.source_event_id);
            obs_sets.push_back(std::move(s));
        }
        // Holder's highest-position row whose event every observer also perceived.
        auto h_rows = ps.perceived_for_theme(tenant, holder, theme_n, as_of);
        for (auto it = h_rows.rbegin(); it != h_rows.rend(); ++it) {
            if (it->state_dim != dim) continue;
            bool in_all = true;
            for (const auto& s : obs_sets) {
                if (!s.count(it->source_event_id)) { in_all = false; break; }
            }
            if (in_all) { row = *it; break; }
        }
    }
    if (!row) return out;
    out.has_belief = true;
    out.state_dim = row->state_dim;
    out.state_value = row->state_value;
    out.source_event_id = row->source_event_id;
    const std::string truth = ps.latest_actual(tenant, theme_n, dim, as_of);
    out.is_stale = (!truth.empty() && truth != out.state_value);
    return out;
}

}  // namespace starling::tom::mentalizing
```
Add `src/tom/mentalizing_chain.cpp` to the `starling_core` library sources in the root `CMakeLists.txt` (grep for `mentalizing_think.cpp` and add the new file beside it).

- [ ] **Step 5: Build + run the chain ctests**
```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build
.venv/bin/ctest --test-dir build -R WhatDoesXThinkChain --output-on-failure
```
Expected: all 6 `WhatDoesXThinkChain.*` PASS.

- [ ] **Step 6: Confirm no regression in order-1/2**
```bash
.venv/bin/ctest --test-dir build -R "WhatDoesXThink\b|Mentalizing|SecondOrder" --output-on-failure
```
Expected: the existing `WhatDoesXThink.*` tests still PASS (the new function is additive).

- [ ] **Step 7: Commit**
```bash
git add src/tom/mentalizing_chain.cpp include/starling/tom/mentalizing.hpp CMakeLists.txt tests/cpp/test_mentalizing_chain.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P3/#3): what_does_X_think_chain — arbitrary multi-order perception ToM

Generalizes the order-2 observer intersection (mentalizing_think.cpp) to a chain
[c1..cN]: holder=cN, observers=the rest; returns the holder's highest-position
perceived state among events EVERY observer also perceived. N=1 delegates to
last_known. Additive — what_does_X_think is untouched; order-1/2 tests stay green.
Six ctests cover order-1 parity, order-2 equivalence, order-3 early-leave (initial)
and full-presence (moved), order-4, and empty/unknown -> has_belief=false.

EOF
)"
```

---

## Task 3: Bind + wrap the chain query for Python

**Files:**
- Modify: `bindings/python/bind_08_tom.cpp` (add `.def` after `what_does_X_think`, line ~191)
- Modify: `python/starling/tom/primitives.py` (add wrapper after `what_does_X_think`, line ~173)
- Test: `tests/python/test_chain_belief_roundtrip.py` (add a pybind smoke assertion)

- [ ] **Step 1: Add the failing pybind smoke test**

Append to `tests/python/test_chain_belief_roundtrip.py`:
```python
def test_chain_query_is_bound_and_callable():
    from starling import _core
    assert hasattr(_core, "what_does_X_think_chain")
    from starling.tom.primitives import what_does_X_think_chain  # wrapper exists
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/python/test_chain_belief_roundtrip.py::test_chain_query_is_bound_and_callable -v`
Expected: FAIL — `AttributeError: ... has no attribute 'what_does_X_think_chain'`.

- [ ] **Step 3: Add the pybind `.def`**

In `bindings/python/bind_08_tom.cpp`, immediately after the `what_does_X_think` `.def` block (ends line ~191), add (confirm `#include <pybind11/stl.h>` is present near the top so `list[str] <-> std::vector<std::string>` auto-converts; grep — it must be, since `shared_with`/`perceived` use vectors):
```cpp
    m.def("what_does_X_think_chain",
        [](starling::persistence::SqliteAdapter& adapter,
           starling::cognizer::KnowledgeFrontier& frontier,
           const std::vector<std::string>& chain, const std::string& theme,
           const std::string& tenant, const std::string& as_of) {
            return starling::tom::mentalizing::what_does_X_think_chain(
                adapter, frontier, chain, theme, tenant, as_of);
        },
        py::arg("adapter"), py::arg("frontier"), py::arg("chain"), py::arg("theme"),
        py::arg("tenant"), py::arg("as_of"),
        "Arbitrary multi-order: holder cN's last-perceived state among events all "
        "chain members perceived (chain=[c1..cN]). Returns a StateBelief.");
```

- [ ] **Step 4: Add the Python wrapper**

In `python/starling/tom/primitives.py`, after `what_does_X_think` (ends line ~173), add:
```python
def what_does_X_think_chain(
    adapter,
    frontier,
    *,
    chain: list[str],
    theme: str,
    tenant_id: str = "default",
    as_of: Optional[datetime] = None,
):
    """Arbitrary multi-order belief: "chain[0] thinks chain[1] thinks … chain[-1] thinks
    the theme is where". holder = chain[-1]; observers = the rest. Returns StateBelief.

    Parameters
    ----------
    adapter   : SqliteAdapter
    frontier  : KnowledgeFrontier
    chain     : cognizer ids, outermost first, belief-holder (deepest) last.
    theme     : theme id (statements.object_value, e.g. 'watermelon')
    tenant_id : tenant scope
    as_of     : time anchor; defaults to now (UTC). Must be tz-aware.
    """
    as_of_iso = _iso_now_or_convert(as_of)
    return _core.what_does_X_think_chain(adapter, frontier, chain, theme, tenant_id, as_of_iso)
```

- [ ] **Step 5: Rebuild the editable extension + run the smoke test**
```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --python-editable --build-dir build
.venv/bin/python -m pytest tests/python/test_chain_belief_roundtrip.py::test_chain_query_is_bound_and_callable -v
```
Expected: PASS. (If the editable `_core.so` is stale, also run `cmake --install build --prefix "$(.venv/bin/python -c 'import site;print(site.getsitepackages()[0])')"`.)

- [ ] **Step 6: Commit**
```bash
git add bindings/python/bind_08_tom.cpp python/starling/tom/primitives.py tests/python/test_chain_belief_roundtrip.py
git commit -m "$(cat <<'EOF'
feat(P3/#3): bind + wrap what_does_X_think_chain for Python

Thin pybind .def mirroring what_does_X_think (chain as list[str] via pybind11/stl)
plus a Pythonic wrapper in starling.tom.primitives (as_of defaults to now). No logic
in the binding layer.

EOF
)"
```

---

## Task 4: Round-trip — HiToM story → remember → chain query

**Files:**
- Test: `tests/python/test_chain_belief_roundtrip.py` (add the end-to-end chain assertion)

- [ ] **Step 1: Add the failing round-trip test**

Append to `tests/python/test_chain_belief_roundtrip.py` (same `make_stub_llm` pattern as Task 1, but a 3-cognizer scene so a real order-3 chain resolves; the `enter` event is REQUIRED here — Aiden is the outermost observer who never leaves/moves, so without it he is absent from the cast → no perception → the chain query returns empty):
```python
_CANNED_O3 = json.dumps([
    {"actor": "Aiden", "action": "enter", "theme": "hall", "location": None,
     "participants": ["Aiden", "Avery", "Carter"], "time": None},
    {"actor": "Aiden", "action": "find", "theme": "cabbage", "location": "blue_bathtub",
     "participants": [], "time": None},
    {"actor": "Carter", "action": "leave", "theme": "hall", "location": None,
     "participants": ["Carter"], "time": None},
    {"actor": "Avery", "action": "move", "theme": "cabbage", "location": "red_box",
     "participants": ["Avery"], "time": None},
])


def test_order3_chain_resolves_to_initial_for_early_leaver(tmp_path):
    from starling.tom.primitives import what_does_X_think_chain
    from datetime import datetime, timezone
    # enter seats the cast {Aiden, Avery, Carter}; all present at the find -> all perceive
    # blue_bathtub. Carter leaves before Avery's move, so Carter still believes blue_bathtub.
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), agent="narrator",
        llm=starling.make_stub_llm(default_response=_CANNED_O3))
    mem.remember("Aiden, Avery and Carter entered the hall. The cabbage is in the blue_bathtub. "
                 "Carter exited the hall. Avery moved the cabbage to the red_box.")
    frontier = starling._core.KnowledgeFrontier(mem._rt.adapter)
    # "Aiden think Avery think Carter think the cabbage is": Carter (deepest) left before the
    # move; all three co-saw the initial blue_bathtub -> blue_bathtub.
    sb = what_does_X_think_chain(
        mem._rt.adapter, frontier, chain=["Aiden", "Avery", "Carter"], theme="cabbage",
        tenant_id=mem._core.tenant, as_of=datetime(9999, 1, 1, tzinfo=timezone.utc))
    assert sb.has_belief
    assert sb.state_value == "blue_bathtub"
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python -m pytest tests/python/test_chain_belief_roundtrip.py::test_order3_chain_resolves_to_initial_for_early_leaver -v`
Expected: PASS (Tasks 1-3 already provide the behavior; this is the integration lock). If it fails on `has_belief`, the find event's initial location is not reaching all three — recheck Task 1's reconstructor behavior. If `state_value` is wrong, recheck the chain semantics (Task 2).

- [ ] **Step 3: Commit**
```bash
git add tests/python/test_chain_belief_roundtrip.py
git commit -m "$(cat <<'EOF'
test(P3/#3): round-trip — HiToM story remember -> order-3 chain query

End-to-end lock over Tasks 1-3: a scripted 3-cognizer story (bare initial stative +
early leaver + move) feeds remember, and what_does_X_think_chain(["Aiden","Avery",
"Carter"], "cabbage") returns the initial blue_bathtub (Carter left before the move).

EOF
)"
```

---

## Task 5: Rename the in-loop server to `starling_tomeval_server.py`

**Files:**
- Rename: `scripts/starling_tombench_server.py` → `scripts/starling_tomeval_server.py`
- Modify: the file's module docstring (run command lines ~22-26) + any in-repo references

- [ ] **Step 1: git mv**
```bash
git mv scripts/starling_tombench_server.py scripts/starling_tomeval_server.py
```

- [ ] **Step 2: Update in-file references**

In `scripts/starling_tomeval_server.py`, update the docstring run command (lines ~25-26) from `scripts.starling_tombench_server:app` to `scripts.starling_tomeval_server:app`. Update the opening docstring sentence to read that it serves the ToMEval harness (ToMBench + HiToM), not "ToMBench" specifically. Grep the repo for any other reference: `grep -rn "starling_tombench_server" . --exclude-dir=build --exclude-dir=.git` and fix each (docs, comments).

- [ ] **Step 3: Verify the server still imports**
```bash
.venv/bin/python -c "import importlib.util, pathlib; \
spec = importlib.util.spec_from_file_location('s', 'scripts/starling_tomeval_server.py'); \
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('app' , hasattr(m, 'app'))"
```
Expected: `app True`.

- [ ] **Step 4: Commit**
```bash
git add scripts/starling_tomeval_server.py
git commit -m "$(cat <<'EOF'
refactor(eval): rename starling_tombench_server.py -> starling_tomeval_server.py

The in-loop server is the Starling endpoint for the ToMEval harness (serves ToMBench
AND HiToM, and others) — the tombench name was inaccurate once HiToM became the active
benchmark. Pure rename + docstring/run-command update; cfg files reference only the
port, so nothing else changes.

EOF
)"
```
Note: also update the memory note `~/.claude/projects/.../memory/starling-in-the-loop-tomeval.md` filename reference (not under git; edit directly).

---

## Task 6: Parse the HiToM cognizer-chain question (server)

**Files:**
- Modify: `scripts/starling_tomeval_server.py` (add `_parse_chain_question`)
- Create: `tests/python/test_tomeval_server_chain.py`

- [ ] **Step 1: Write the failing parser tests**

Create `tests/python/test_tomeval_server_chain.py`:
```python
"""Unit tests for the in-loop server's HiToM chain-question parser."""
import importlib.util

_spec = importlib.util.spec_from_file_location("tomeval_server", "scripts/starling_tomeval_server.py")
srv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(srv)


def test_order3_chain_parsed():
    q = "Where does Aiden think Avery thinks Carter thinks the cabbage is?"
    assert srv._parse_chain_question(q) == (["Aiden", "Avery", "Carter"], "cabbage")


def test_order4_chain_parsed():
    q = "Where does Amelia think Nathan thinks Jackson thinks Sophia thinks the tomato is?"
    assert srv._parse_chain_question(q) == (["Amelia", "Nathan", "Jackson", "Sophia"], "tomato")


def test_order1_really_think_not_a_chain():
    # single cognizer -> not a nested-belief chain -> skip injection (use existing dump).
    assert srv._parse_chain_question("Where does Isla really think the cabbage is?") is None


def test_first_order_simple_think_not_a_chain():
    assert srv._parse_chain_question("Where does Isla think the cabbage is?") is None


def test_non_hitom_question_ignored():
    assert srv._parse_chain_question("[Question] Which of the following best describes X? [Candidate Answers]") is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/python/test_tomeval_server_chain.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_parse_chain_question'`.

- [ ] **Step 3: Implement the parser**

In `scripts/starling_tomeval_server.py` (near `_extract_story`, ~line 108), add:
```python
# HiToM nested-belief question: "Where does A think B thinks … the THEME is?".
# The `\s+thinks?\s+the\s+` REQUIRES a think/thinks immediately before "the THEME" — that
# consumes the FINAL verb so it does not cling to the last cognizer (without it,
# "Carter thinks" would survive the split and fail the single-token guard). `re` is the
# module-level import at the top of the server file.
_CHAIN_RX = re.compile(r"\bdoes\s+(.+?)\s+thinks?\s+the\s+([A-Za-z][\w ]*?)\s+is\b", re.I)
_THINK_SPLIT = re.compile(r"\s+thinks?\s+", re.I)


def _parse_chain_question(question: str):
    """Return (chain, theme) for an order>=2 HiToM nested-belief question, else None.
    chain is outermost-first; the deepest (belief-holder) is last. Single-cognizer
    ("really think" / plain "think") and non-HiToM questions return None (the caller
    falls back to the existing dump scaffold)."""
    m = _CHAIN_RX.search(question or "")
    if not m:
        return None
    span, theme = m.group(1).strip(), m.group(2).strip()
    parts = [p.strip() for p in _THINK_SPLIT.split(span) if p.strip()]
    if len(parts) < 2:
        return None  # one cognizer (e.g. "Isla" / "Isla really") -> not a nested chain
    # Each part must be a single name token (HiToM uses single first names); a multi-word
    # part is a parse artifact -> skip and fall back to the plain dump.
    if any(len(p.split()) != 1 for p in parts):
        return None
    return parts, theme
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/python/test_tomeval_server_chain.py -v`
Expected: all 5 PASS. Trace: the regex consumes the final `thinks` before `the`, so order-3 captures `"Aiden think Avery thinks Carter"` → splits to `["Aiden","Avery","Carter"]` (3 ≥ 2, all single-token → returns the chain); order-1 `"Isla"` and `"Isla really"` capture a single span → `len(parts) < 2` → None; the ToMBench/`[Question]` string never matches `does … thinks the … is` → None.

- [ ] **Step 5: Commit**
```bash
git add scripts/starling_tomeval_server.py tests/python/test_tomeval_server_chain.py
git commit -m "$(cat <<'EOF'
feat(P3/#3): parse HiToM nested-belief chain questions (in-loop server)

_parse_chain_question extracts the cognizer chain (outermost-first, deepest last) and
theme from "Where does A think B thinks … the THEME is?". Returns None for order-1
("really think" / plain "think") and non-HiToM questions so the caller falls back to
the existing dump. Exact pattern pinned by 5 unit tests.

EOF
)"
```

---

## Task 7: Inject the computed answer into the dump (server)

**Files:**
- Modify: `scripts/starling_tomeval_server.py` (`_starling_memory_for` / `chat_completions` to compute + inject the chain answer)
- Test: `tests/python/test_tomeval_server_chain.py` (add an injection-format test)

**Why:** The chain query needs the live Memory's adapter + frontier (`mem._rt.adapter`), so the query must run while `mem` is open (inside `_starling_memory_for`), and the question must be threaded in. The injection is definitive (spec §7.3) so deepseek reads, not reasons.

- [ ] **Step 1: Add the failing injection-format test**

Append to `tests/python/test_tomeval_server_chain.py`:
```python
def test_chain_injection_format():
    txt = srv._format_chain_injection(["Aiden", "Avery", "Carter"], "cabbage", "blue_bathtub")
    assert "blue_bathtub" in txt
    assert "Aiden thinks Avery thinks Carter thinks" in txt
    assert "deterministic" in txt.lower()
    # the lie hedge must be present so deepseek can override on explicit deception
    assert "lied" in txt.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/python/test_tomeval_server_chain.py::test_chain_injection_format -v`
Expected: FAIL — no `_format_chain_injection`.

- [ ] **Step 3: Implement the injection formatter + wire the query**

In `scripts/starling_tomeval_server.py`:

(a) Add the formatter near `_memory_dump`:
```python
def _format_chain_injection(chain: list[str], theme: str, location: str) -> str:
    nested = " thinks ".join(chain) + " thinks"
    return (
        "Starling's deterministic ToM engine computed the answer to this exact "
        "nested-belief question:\n"
        f"  {nested} the {theme} is in: {location}\n"
        "Use this as the primary answer (match it to the lettered choice). If the story "
        "explicitly shows a character LIED about the location, adjust accordingly."
    )
```

(b) Add a helper that runs the chain query against a live Memory (uses `mem._rt.adapter`, `mem._core.tenant` — confirm both accessors by grepping the `Memory` class in `python/starling/memory.py`):
```python
def _chain_injection_for(mem, user_content: str) -> str:
    """If the question is an order>=2 HiToM chain, compute the nested belief via Starling
    and return a definitive injection string; else "" (caller keeps the plain dump)."""
    parsed = _parse_chain_question(user_content)
    if not parsed:
        return ""
    chain, theme = parsed
    try:
        frontier = _core.KnowledgeFrontier(mem._rt.adapter)
        sb = _core.what_does_X_think_chain(
            mem._rt.adapter, frontier, chain, theme, mem._core.tenant,
            "9999-12-31T23:59:59Z")
    except Exception:
        print("[CHAIN-EXC]\n" + traceback.format_exc(), file=sys.stderr, flush=True)
        return ""
    if not sb.has_belief or not sb.state_value:
        return ""  # incomplete perception -> fall back to the plain dump
    return _format_chain_injection(chain, theme, sb.state_value)
```

(c) Thread the question into `_starling_memory_for` and append the injection. Change its signature to `_starling_memory_for(story: str, user_content: str = "") -> str` and, before `mem.close()` in the `try`, build:
```python
        dump = _memory_dump(db_path, mem._core.tenant)
        inject = _chain_injection_for(mem, user_content)
        return (dump + "\n\n" + inject) if inject else dump
```
(Keep the `finally` close/unlink unchanged.) In `chat_completions`, change the call to pass the question:
```python
    memdump = _starling_memory_for(_extract_story(user), user)
```

- [ ] **Step 4: Run the injection test + the full server-chain suite**
```bash
.venv/bin/python -m pytest tests/python/test_tomeval_server_chain.py -v
```
Expected: all PASS (parser + injection format).

- [ ] **Step 5: Full regression**
```bash
.venv/bin/ctest --test-dir build --output-on-failure
.venv/bin/python -m pytest tests/python -q
```
Expected: all green, counts >= the Task 0 baseline (only additions).

- [ ] **Step 6: Commit**
```bash
git add scripts/starling_tomeval_server.py tests/python/test_tomeval_server_chain.py
git commit -m "$(cat <<'EOF'
feat(P3/#3): inject Starling's computed nested belief into the in-loop dump

When the HiToM question is an order>=2 chain, run what_does_X_think_chain against the
live Memory's adapter and inject the computed location definitively ("Starling computed:
A thinks B thinks C thinks the cabbage is in: blue_bathtub"), with a lie hedge so
deepseek can override on explicit deception. has_belief=false / non-chain questions fall
back to the existing dump. This lets deepseek READ order 3-4 instead of reasoning it
(the 32768-token exhaustion that drove the 39%/68% fallback).

EOF
)"
```

---

## Final: dispatch a whole-implementation code review

After Task 7, dispatch a final code-reviewer over the full diff (Tasks 1-7) against the spec, then STOP before any push / merge / roadmap edit / eval re-run (those need explicit user consent; the eval re-run also burns API). Report: ctest/pytest counts, the diff summary, and the measurement command for the user to run when ready:
```bash
# (server up with the bounded-budget env from the hang-fix), then:
cd /Users/jaredguo-mini/develop/ToMEval && .venv/bin/python tasks/HiToM/run.py --experiment-config cfg_starling_HiToM.yaml
```

---

## Hard Constraints (apply to every task)

- Core ToM logic = C++ (`src/tom/`); bindings/wrappers = thin forwarding; question-parse + injection = Python eval harness; #2 = prompt data + the **unchanged** reconstructor.
- Do NOT modify `canonicalize_*`, `what_does_X_think` itself, or `perceived_by_json`.
- `normalize_theme` only for entity/str-kind themes; cognizer resolution query-side is lookup-only, best-effort pass-through.
- The chain query is additive → order-1/2 and all existing ToM / B-perception / A-episodic / six-state / conflict / grounding ctests stay green.
- TDD: failing test → red → minimal implementation → green → commit, each task.
- Build from repo root: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`; after C++/binding changes add `--python-editable` (and `cmake --install` if the editable `_core.so` is stale); ctest via `.venv/bin/ctest`.
- Explicit-path `git add` (never `.` / `-A`); no `--no-verify` / `--amend`.
- Do NOT push, merge to main, register the roadmap, or re-run the API-burning eval without explicit user consent.
