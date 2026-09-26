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

# Extraction Completeness — Design
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **2026-09-11 契约补充**：补充抽取保留 topic/时间/归属，不从问答金标生成输入。 当前扩展见 [已确认语义证据设计](2026-09-11-source-grounded-claim-contract-design.md)。下文保留本版本原有适用范围。


**Date:** 2026-06-19
**Status:** Approved (design); pending implementation plan.
**Context:** Second of the extraction-grounding sequence (resolution ✅ → **completeness** → configurability). Grounding-resolution lifted the ToMBench location-FB end-to-end from 0.39 to ~0.78; the dominant remaining no-ground is the **leaver-find-gap**: in a Sally-Anne scene the character who *leaves* before the object is moved must have perceived the **initial location** to hold a (now-stale) false belief, but that initial location comes from a "they **find** the X in the Y" clause the episodic extractor does not reliably capture **with a location**. Real failing item (`tests/data/eval_tom_bench/full.jsonl:353-357`, qids `tb-false-belief-task-012..016`): *"Xiao Li and Youyou … they see a suitcase, a backpack, and a storage locker, they find a hat in the suitcase, Youyou leaves the basement, Xiao Li moves the hat to the storage locker."* — asked "where does Youyou look for the hat?", gold = "Suitcase" (the initial location).

---

## 1. Goal & scope

Make the episodic extractor capture **state-establishing initial locations** ("they find X in Y" → X is located at Y) so the leaver — already a present witness — forms the correct stale belief. **This is a pure prompt change (Python config data); no C++.**

**Why the prompt is the whole fix (C0).** The leaver (Youyou) is named in her own *"Youyou leaves"* clause, so she is in the reconstructor's **cast** (every named cognizer) and **default-present from the scene start** (`perception_reconstructor.cpp` presence model). She is therefore a witness of the *find* event (seq-before her leave) **regardless of how the find names its actor** — so she grounds **iff the find event carries a non-empty `location`** (the reconstructor's physical-location branch is gated on `!ev.location.empty()`). Today the prompt's `location` rule is "the **resulting** place after the action", so "find X in Y" emits `location=null` → the reconstructor writes nothing → the leaver has no initial perception → `[name-drift]` miss (the *move* event exists for the theme, so the M5 tag reads name-drift, but the real cause is the missing find-location). **Capturing the find with a location is the whole fix for ToMBench, and it needs no code change** — a `find` with a location already routes to `state_dim="location"` in the reconstructor (`find` is in no special-set).

**No compound-cognizer split (dropped — YAGNI).** "Xiao Li and Youyou find …" yields a compound `actor` surface, but it does **not** block the leaver (she is in the cast via her own *leave* clause, C0). A deterministic read-time split was considered and **dropped**: it added zero functional value for ToMBench (the leaver grounds without it), its only-in-compound robustness was partial anyway (the read-time split outputs raw, un-re-resolved sub-surfaces that drift on casing — P1), and it added a C++ touch point. The prompt still asks the model to resolve conjoined/pronoun subjects to individuals (§3.1) — a cheap, cosmetic extraction-cleanliness ask, not a grounding requirement. If a *only-in-compound* participant ever needs robust grounding (open narratives, not ToMBench), the future path is a **write-time** split (before name resolution), a separate change.

**Out of scope (deferred):**
- **`see X in Y` as a physical initial location.** `see`/`look` already route to `state_dim="content"` (the unexpected-contents channel, `is_see` → content branch). Reusing `see` for a physical location would collide with that semantics. The prompt uses **`find`/`discover`** for physical initial location (which routes to the location branch); `see` stays content. No reconstructor routing change.
- **Stative "X is in Y" / "there is an X in Y" capture** is best-effort only (C5): the extractor is action-oriented, so it reliably emits the *action* "find/discover" but may drop a pure stative clause. The prompt instructs the stative forms too, but the design does not depend on them — ToMBench uses "find".
- **Configurability** (prompt/vocab injection) — the next spec (#3).

## 2. Current state (file:line)

- **Episodic prompt** `python/starling/extractor/episodic_prompt.py`: `location` rule (:35) = "the object's **RESULTING place after the action**" — no state-establishing/initial-location instruction; PREFER verb list (:33) = {put, place, move, take, give, remove, transfer, leave, open, close, tell, inform} — **`find` absent**; `actor` (:32) / `participants` (:36) rules — **no conjoined-subject instruction**; 4 worked examples (:43-87) — none show a "find X in Y" initial location or a conjoined subject.
- **Reconstructor** `src/cognizer/perception_reconstructor.cpp` (unchanged by this spec): presence cast = every cognizer named in any non-tell event; **default-present from scene start**, a `leave` removes the leaver only *after* its own event; physical-location branch gated on `!ev.location.empty()` (~:193) writes `perception_state(witness, theme, state_dim="location", value=location)`. A non-tell/non-presence/non-content/non-close predicate with a location (e.g. `find`) routes to this location branch **today, zero code change**. `is_see` (~:55) routes `see`/`look` to the **content** branch (~:174).
- **Schema — no blocker:** `episodic_events.location` (migration 0025) is nullable TEXT; `perception_state.state_dim='location'` (migration 0026) is ready. An initial-location find is just an `OCCURRED` statement with `location` set.

## 3. Architecture

### 3.0 Decisions locked (brainstorming)

1. **Pure prompt change.** No C++ (no split, no registry change, no reconstructor routing change); `canonicalize` untouched.
2. **Initial physical location uses `find`/`discover` in the prompt** (routes to the location branch); `see` stays content.
3. **Two-track measurement** — a deterministic machinery pin (a find-with-location grounds the leaver) + a real-model grounding-recall re-run.

### 3.1 Episodic prompt changes (the only change — Python config data)

`python/starling/extractor/episodic_prompt.py` (purely additive; existing put/move/leave/tell/see-content rules unchanged):
- **Extend the `location` rule** to cover **state-establishing initial location**: for "they **find/discover** X in Y" → `action="find"`, `theme=X`, `location=Y` (the container/place where X is found). The existing "resulting place" wording stays for action verbs; this adds the find/initial case. **(This is the load-bearing change.)**
- **Add `find` (and `discover`) to the PREFER verb list.** (Prompt-only — NOT the C++ `kActionPredicates` registry: `OCCURRED` rows accept out-of-vocab verbs verbatim, and `find` is not in any reconstructor special-set, so a `find` with a location routes to `state_dim="location"` with zero code change.)
- **Add a conjoined-subject / pronoun-coreference instruction** to the `actor`/`participants` rules: "If a clause has a conjoined subject ('X and Y …') or a plural pronoun back-reference ('they …' / 'them' referring to people named earlier), **resolve it to the individual names** and list each in `participants`; pick a single individual or omit `actor` for a group action. Do not emit a single 'X and Y' string, or a bare 'they', as a person." **This is cosmetic, not load-bearing (C0):** the find event's `actor`/`participants` are irrelevant to the leaver grounding (she witnesses via default-presence from her own *leave* clause). It exists only to keep extraction clean (no junk compound cognizer) and is cheap to include in the prompt.
- **Add a worked example** of the leaver-find 5-clause shape: the Xiao-Li/Youyou narrative → ordered events `find(hat, location=suitcase, participants=[Xiao Li, Youyou])`, `leave(Youyou)`, `move(hat → storage locker, Xiao Li)`. This is the primary lever — the prompt's effect is an **LLM-behaviour bet measurable only by the real-model eval** (C1); the worked example is how we steer it, and it may need real-model iteration.
- **`see`/`look` unchanged** — reserved for labelled-container apparent content; physical initial location uses `find` (avoids the see=content routing collision).

### 3.2 No code change

No C++ at all: no `split_compound_cognizers`, no `kActionPredicates`/registry change, no reconstructor routing change. `canonicalize_object`/`canonicalize_string` untouched (parity intact). The find-with-location event already grounds the leaver through the existing reconstructor + `what_does_X_think` (the find routes to the location branch; the leaver is a default-present witness).

## 4. Data flow

```
"they find a hat in the suitcase, Youyou leaves, Xiao Li moves the hat to the storage locker"
→ EpisodicExtractor (new prompt): find(hat, loc=suitcase, …) + leave(Youyou) + move(hat → locker, Xiao Li)
→ PerceptionReconstructor (UNCHANGED): cast includes Youyou (named in her leave clause), default-present at find(seq1)
   → find@suitcase writes perception_state(Youyou, hat, location, suitcase) (+ Xiao Li); Youyou leaves(seq2) → absent at move(seq3)
→ what_does_X_think(Youyou, hat) = suitcase (stale; ground truth=locker) ✓
```
The leaver grounds because the find now carries a location and she is a present witness via her own *leave* clause — independent of how the find's actor is phrased.

## 5. Error handling

- If the LLM still emits the find with `location=null` (the prompt is a bet, C1), the reconstructor writes nothing and the leaver misses — degrades to today's behaviour, never crashes. The real-model eval is how we detect + iterate this.
- A conjoined actor the model fails to split is harmless (a junk extra cast member; the leaver still grounds via her own clause).
- Single-scene / tenant assumption inherited from B.

## 6. Testing (two tracks — decision 3)

1. **Deterministic machinery pin** (no real LLM): a **stub-LLM leaver-find e2e** (`tests/python/`): canned episodic JSON for the Xiao-Li/Youyou scene (`find(hat, location="suitcase", …)` + `leave(Youyou)` + `move(hat→"storage locker", Xiao Li)`) → `what_does_X_think(Youyou, "hat")` = `"suitcase"`, `is_stale=true`; `(Xiao Li, "hat")` = `"storage locker"`. This **pins the machinery** (a find-with-location grounds the leaver) and documents the target behaviour. NOTE: it passes against the *current* reconstructor (no code change) — it is a regression pin, not a TDD red→green; the actual gap is whether the *real model* emits the find with a location, which only the real-model eval exercises (C1).
2. **Real-model grounding-recall re-run** (`STARLING_RUN_LLM_E2E` gate; on-demand, **after the tokenkey.dev budget window recovers — this spec burns no API**): re-run `scripts/eval_perception_starling.py`; expect the leaver-find probes to ground and the M5 `[name-drift]` tag to shrink (fewer leaver misses). **No fixed lift is promised** (C1) — the real run measures whether the prompt elicits find-with-location.
3. **Regression:** ctest 644 / pytest 625 stay green — there is no code change; the prompt additions are additive (the deterministic B/grounding tests drive stub LLMs and are prompt-independent; the gated real-LLM Sally-Anne e2e has no find/conjoined clauses, so the new rules don't fire).

## 7. Constraints

The only change is **Python prompt config data** (`python/starling/extractor/episodic_prompt.py`) + one stub-LLM e2e test. **No C++**, no migration, no binding change. Do not touch `canonicalize_object`/`canonicalize_string` or the reconstructor; reuse the existing find→location routing. Do not break belief / multi-order-ToM / six-state / conflict / A-episodic / B-perception / grounding pins. `perceived_by_json` immutable. TDD where applicable; explicit-path `git add` (never `.`/`-A`); no `--no-verify`/`--amend`; an editable rebuild is not needed (no C++/binding change), but run the full pytest to confirm no regression; build from repo root `/Users/jaredguo-mini/develop/memory/starling`.


## 生成契约完整性同步（2026-09-12）

按 [中文生成契约设计](2026-09-12-claim-generation-design.md)，C++ 在抽取提示中明确对象、逐字主题、原始时间限定和字段类型约束，并提供与本次来源隔离的通用中英文参考示例。模型输出校验、准入、存储/检索与默认开关保持既有约束，Python 仅绑定和评测编排；参考示例不作为当前证据。本轮 C++ 实现、完整回归、离线核验及历史响应 140/140 一致性重放已完成；真实诊断于北京时间 2026-09-13 完成核验，为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、独立对象 12/14、主题/联合各 1/14，原生技术失败 5；主题字面匹配分数不能解释为字段缺失。P1 兼容与逐例不退步门槛仍失败，Q1/Q9 结构化及链接组仍为 0/3，默认关闭。详见 [生成契约评测报告](../../eval/2026-09-12-socialmem-generation.md)。其他专项职责沿用设计同步清单，历史快照保持。

## 输出协议与偏好边界同步（2026-09-13）

按 [中文修复设计](2026-09-13-claim-protocol-boundary-design.md) 继续已批准优化：C++ 提示强调键唯一、时间原文及同话轮引用，准入与解析共用合法原因目录，窄范围拒绝把明确偏好对象写成 feels。真情绪不因同源其他偏好句被拒；Bus/回读复用共享契约，Python 仅绑定与编排。当前已完成 RED、C++ 实现与复审修复后的完整回归（C++ 1,062 项，Python 1,319 项通过/15 项跳过）；旧响应重解析 137/140 一致，3 条偏好误标候选提前拒绝。复合/因果情绪及被动 preferred 感受保留准入，句尾标点边界有正反例覆盖。独立复审发现均已关闭，最终离线 140 条/144 数据库核验通过；真实诊断已完成并由原生验证器核验为 `verified / complete_with_errors`：140 条重放、144 个数据库；固定候选 56/64（TP 30、TN 26、误收 0、误拒 1、技术失败 7），synthetic 冻结 11/16、契约 11/16（有效分母 15/16），P1 combined F1 为 holder 0.7317、holder/perspective 0.6829、predicate/object 0.7683；扩展标签 object/topic/scope/time/joint 为 12/14、2/14、12/14、12/14、2/14（有效目标 13）；Q1/Q9 的 baseline、structured、linked 均为 0/3，full 均为 3/3；实际证据链仍受入库与证据聚合限制。原生技术失败共 10 条，主要为重复 JSON 键和准入 JSON 后追加文本；无效裁判票 0。`promotion_ready=false`，生产默认保持关闭，不运行 1,031 题全量。默认、原标签、检索与历史归档保持。

## 声明范围与覆盖诊断职责（2026-09-15）

后继 R0 以人工来源状态注释加原生行索引定位阶段缺口；Python 只汇总，不重建谓词或文本语义。输出未知、整批结构拒绝和未执行必须分开。L 的句首误拒修复只改变解析候选，不补抽取、不追问、不伪造状态序列。

详见[声明范围定位与生成覆盖诊断设计](2026-09-15-claim-scope-localization-design.md)。
