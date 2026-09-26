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

# Extractor 真实抽取 prompt + JSON 解析器 Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 C++ Extractor 接真实 LLM 能真正抽出 Statement——落地真实抽取 prompt（复用 `eval_p1_extractor.py` 的成熟 prompt，单一源 `prompts.py` 注入 C++ Extractor），切 JSON 输出 + 重写解析器，使 `remember`（`starling.Memory` + dashboard 共用）端到端可用。

**Architecture:** prompt 住 `python/starling/extractor/prompts.py`（单一源），eval 改 import；`Extractor` 构造加 `prompt_template`，`run` 把 payload 文本插进模板调真实 LLM；新 `json_parser`（nlohmann/json）解析 LLM 的 JSON 数组 → `ExtractedStatement`（LLM 出语义、C++ 填簿记），替代退役的 `xml_parser`；`OpenAIAdapter` 加 `max_tokens`。

**Tech Stack:** C++20（改 extractor/parser/adapter/binding，需 cmake 重建）+ pybind11 + Python 3.14；ctest + pytest。

**Spec:** `docs/superpowers/specs/2026-06-06-extractor-real-prompt-design.md`（commit b6ab269）。

**执行位置：** 本里程碑**改 C++** → **worktree 隔离 + cmake 重建**。改 C++/绑定后刷新 `_core`：`cmake --build build && cmake --install build --prefix .venv/lib/python3.14/site-packages`（关键）。每 Task commit 本地；push/merge main 需显式 consent。

---

## 文件结构（决策锁定）

**新建**
- `python/starling/extractor/prompts.py` — `EXTRACTION_PROMPT`（权威 prompt 源）
- `src/extractor/json_parser.cpp` + `include/starling/extractor/json_parser.hpp` — `parse_extractor_json`
- `tests/cpp/test_json_parser.cpp` — JSON 解析单测
- `scripts/eval_extractor_smoke.py` — gated 真实 LLM 端到端烟测

**修改**
- `scripts/eval_p1_extractor.py` — 删内联 prompt，import prompts.py
- `include/starling/extractor/extractor.hpp` + `src/extractor/extractor.cpp` — Extractor 构造加 prompt_template；run 插 payload + 改调 json_parser；build_prompt_body_for_tests 退役为 fallback
- `include/starling/extractor/openai_adapter.hpp` + `src/extractor/openai_adapter.cpp` — Config 加 max_tokens；extract 带上
- `bindings/python/module.cpp` — Extractor 构造加第三参；OpenAIAdapterConfig 加 max_tokens
- `python/starling/memory.py` + `python/starling/dashboard/engine.py` — Extractor 传 EXTRACTION_PROMPT；make_stub_llm canned XML→JSON
- `CMakeLists.txt`（root line 72）+ `tests/cpp/CMakeLists.txt`（line 46）— xml_parser→json_parser
- 13 个 Python 测试的 canned XML→JSON（共享 stub）

**删除**
- `src/extractor/xml_parser.cpp` + `include/starling/extractor/xml_parser.hpp`
- `tests/cpp/test_xml_parser.cpp`

**共享常量（DRY，贯穿测试）— canned JSON stub**
```json
[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}]
```
（对应旧 canned XML 的 `<statement>` Bob/responsible_for/auth；解析后 subject_id="Bob"、predicate="responsible_for"、object_value="auth"、canonical_object_hash 由 C++ 计算。）

---

## Task 0: Baseline + worktree + 重建确认

**Files:** 无（环境校验）

- [ ] **Step 1: 建 worktree（using-git-worktrees）+ 基线**

Run（在主仓库 `/Users/jaredguo-mini/develop/memory/starling`）：
```bash
cd /Users/jaredguo-mini/develop/memory/starling
git worktree add .claude/worktrees/extractor-real-prompt -b worktree-extractor-real-prompt main
git -C .claude/worktrees/extractor-real-prompt status | head -2
```
Expected: worktree 建于 `.claude/worktrees/extractor-real-prompt`，含 spec（main HEAD b6ab269）。

- [ ] **Step 2: worktree 内建 venv + 全量编译 + baseline**

> ⚠ 本里程碑改 C++ → worktree 需独立 venv + 完整 cmake 构建（editable `_core` 指向主仓库；worktree 必须自建以免污染主仓库）。
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt
python -m venv .venv && source .venv/bin/activate
cmake -S . -B build -G Ninja
cmake --build build 2>&1 | tail -3
ctest --test-dir build 2>&1 | tail -3
pip install -e ".[dev]" 2>&1 | tail -2 || pip install -e ".[dev]" --config-settings cmake.define.FETCHCONTENT_SOURCE_DIR_JSON=$(pwd)/build/_deps/json-src 2>&1 | tail -2
python -m pytest -q 2>&1 | tail -2
```
Expected: cmake build 成功；ctest 全 passed（记下数，作 baseline）；pytest 536 passed + 13 skipped。**后续所有命令在此 worktree + 其 .venv 跑。**

无 commit。

---

## Task 1: prompts.py 单一源 + eval import

**Files:**
- Create: `python/starling/extractor/prompts.py`
- Modify: `scripts/eval_p1_extractor.py`

- [ ] **Step 1: 写 `python/starling/extractor/prompts.py`**

把 `scripts/eval_p1_extractor.py` 的 `_EXTRACT_PROMPT`（line 102 起的整个三引号字符串，含 `{convo}` 占位 + 全部规则 + worked examples，到其结束的 `"""`）**原样复制**为 `EXTRACTION_PROMPT`：
```python
"""Authoritative extraction prompt (single source).

Shared by scripts/eval_p1_extractor.py and the C++ Extractor (injected via
_core.Extractor(conn, llm, EXTRACTION_PROMPT)). The `{convo}` placeholder is
filled with the conversation/utterance text. Output is a JSON array of
statement objects: {holder, holder_perspective, subject, predicate, object,
modality, polarity, nesting_depth}.
"""
from __future__ import annotations

EXTRACTION_PROMPT = """<<< 把 eval_p1_extractor.py line 102-end 的 _EXTRACT_PROMPT 三引号内容原样粘到这里，保持 {convo} 占位 >>>"""
```
（实现者：用 Read 看 `scripts/eval_p1_extractor.py` 的 `_EXTRACT_PROMPT = """..."""` 完整区间，逐字搬运，勿改 prompt 文本。）

- [ ] **Step 2: eval 改 import**

Modify `scripts/eval_p1_extractor.py`：删掉 `_EXTRACT_PROMPT = """..."""` 整段；顶部 import 区加 `from starling.extractor.prompts import EXTRACTION_PROMPT`；把用到 `_EXTRACT_PROMPT.format(convo=convo_str)` 的地方（约 line 309）改成 `EXTRACTION_PROMPT.format(convo=convo_str)`。

- [ ] **Step 3: 校验 import 一致**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt && source .venv/bin/activate
python -c "from starling.extractor.prompts import EXTRACTION_PROMPT; assert '{convo}' in EXTRACTION_PROMPT; assert 'JSON' in EXTRACTION_PROMPT or 'json' in EXTRACTION_PROMPT; print('prompt len', len(EXTRACTION_PROMPT))"
python -c "import ast; ast.parse(open('scripts/eval_p1_extractor.py').read()); print('eval parse ok')"
python -c "import importlib.util as u; m=u.spec_from_file_location('e','scripts/eval_p1_extractor.py'); print('eval imports prompts ok')"
```
Expected: prompt len > 5000；`{convo}` 在；eval parse ok。

- [ ] **Step 4: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt
git add python/starling/extractor/prompts.py scripts/eval_p1_extractor.py
git commit -F - <<'EOF'
feat(P2.i): prompts.py 单一源抽取 prompt + eval import

python/starling/extractor/prompts.py 导出 EXTRACTION_PROMPT（eval_p1_extractor
的 _EXTRACT_PROMPT 原样移过来，含 {convo} 占位、JSON 数组输出 schema）。
eval_p1_extractor.py 删内联 prompt，改 import——单一源，C++ Extractor 也将注入它。

EOF
```

---

## Task 2: OpenAIAdapter 加 max_tokens（C++ + 绑定 + 重建）

**Files:**
- Modify: `include/starling/extractor/openai_adapter.hpp`、`src/extractor/openai_adapter.cpp`、`bindings/python/module.cpp`

- [ ] **Step 1: Config 加 max_tokens**

Modify `include/starling/extractor/openai_adapter.hpp` 的 `struct Config`：在 `int max_retries = 3;` 后加：
```cpp
    int         max_tokens = 4096;   // bound the response; reasoning models + JSON arrays
```

- [ ] **Step 2: extract 请求体带 max_tokens**

Modify `src/extractor/openai_adapter.cpp` 的 `extract`（约 line 66-71）的 body 构造：
```cpp
    nlohmann::json body = {
        {"model",       cfg_.model},
        {"messages",    nlohmann::json::array({
            {{"role", "user"}, {"content", std::string(prompt)}}})},
        {"temperature", 0},
        {"max_tokens",  cfg_.max_tokens}
    };
```
（`from_env` 无需改——`max_tokens` 用 struct 默认 4096。）

- [ ] **Step 3: 绑定暴露 max_tokens**

Modify `bindings/python/module.cpp` 的 `OpenAIAdapterConfig` 绑定（约 line 701-705）：在 `.def_readwrite("max_retries", ...)` 后加：
```cpp
            .def_readwrite("max_tokens",   &OpenAIAdapter::Config::max_tokens)
```

- [ ] **Step 4: 重建 + 校验**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt && source .venv/bin/activate
cmake --build build 2>&1 | tail -3
cmake --install build --prefix .venv/lib/python3.14/site-packages 2>&1 | tail -1
python -c "from starling import _core; c=_core.OpenAIAdapterConfig(); print('max_tokens default', c.max_tokens); c.max_tokens=2048; print('settable', c.max_tokens)"
```
Expected: build 成功；`max_tokens default 4096`；`settable 2048`。

- [ ] **Step 5: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt
git add include/starling/extractor/openai_adapter.hpp src/extractor/openai_adapter.cpp bindings/python/module.cpp
git commit -F - <<'EOF'
feat(P2.i): OpenAIAdapter 加 max_tokens（默认 4096）

Config 加 int max_tokens=4096，extract 请求体带上——JSON 多 Statement 输出 +
推理型模型（deepseek-v4-*）留余量，避免截断致解析失败。绑定 def_readwrite 暴露。

EOF
```

---

## Task 3: json_parser（替代 xml_parser）+ 测试 + CMake（C++ + 重建）

**Files:**
- Create: `include/starling/extractor/json_parser.hpp`、`src/extractor/json_parser.cpp`、`tests/cpp/test_json_parser.cpp`
- Modify: `CMakeLists.txt`、`tests/cpp/CMakeLists.txt`
- Delete: `src/extractor/xml_parser.cpp`、`include/starling/extractor/xml_parser.hpp`、`tests/cpp/test_xml_parser.cpp`

- [ ] **Step 1: 写 `include/starling/extractor/json_parser.hpp`**

```cpp
#pragma once

#include "starling/extractor/existing_ref_map.hpp"
#include "starling/extractor/extracted_statement.hpp"

#include <string>
#include <string_view>
#include <vector>

namespace starling::extractor {

struct ParseError {
    std::string kind;          // e.g. "not_json_array", "element_not_object"
    std::string detail;        // free text for human consumers
    std::size_t byte_offset;   // approximate; 0 if unknown
};

struct ParseResult {
    std::vector<ExtractedStatement> statements;
    std::vector<ParseError>         errors;
};

// Parses the LLM's JSON-array extraction output into ExtractedStatement list.
// LENIENT per-element: a malformed element (bad enum, missing field) is SKIPPED
// (not added to statements, not added to errors) so a mostly-valid response
// still yields its good statements. Only a non-array / non-JSON top level
// produces a ParseError (the orchestrator then retries the whole attempt).
// LLM supplies the semantic core (holder_perspective/subject/predicate/object/
// modality/polarity/nesting_depth); C++ fills bookkeeping (subject_kind=cognizer,
// object_kind=str or "statement" when nesting_depth>=2, canonical_object_hash
// computed, confidence=0.7, observed_at=now). The run() orchestrator fills
// holder_id/holder_tenant_id/chunk_index/source_hash.
ParseResult parse_extractor_json(
    std::string_view raw_json,
    const ExistingRefMap& existing_ref_map);

}  // namespace starling::extractor
```

- [ ] **Step 2: 写 `src/extractor/json_parser.cpp`**

```cpp
#include "starling/extractor/json_parser.hpp"

#include "starling/schema/canonicalize.hpp"
#include "starling/schema/statement_enums.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cctype>
#include <chrono>
#include <ctime>
#include <string>

namespace starling::extractor {
namespace {

std::string to_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return s;
}

// Map the prompt's modality vocabulary onto the C++ Modality enum strings.
// The eval prompt emits e.g. ENFORCES / OBSERVES which are not enum members;
// fold them onto the closest supported value. Unknown values fall through and
// modality_from_string throws (caught per-element).
std::string normalize_modality(std::string m) {
    m = to_lower(m);
    if (m == "enforces") return "norm_ought";
    if (m == "forbids")  return "norm_forbid";
    if (m == "observes") return "knows";
    return m;
}

std::string now_iso8601_utc() {
    const auto now = std::chrono::system_clock::now();
    const std::time_t t = std::chrono::system_clock::to_time_t(now);
    std::tm tm{};
#if defined(_WIN32)
    gmtime_s(&tm, &t);
#else
    gmtime_r(&t, &tm);
#endif
    char buf[32];
    std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm);
    return std::string(buf);
}

// Strip a leading ```json / ``` fence and locate the first '[' .. last ']'.
std::string_view extract_array(std::string_view raw) {
    const auto lb = raw.find('[');
    const auto rb = raw.rfind(']');
    if (lb == std::string_view::npos || rb == std::string_view::npos || rb < lb) {
        return {};
    }
    return raw.substr(lb, rb - lb + 1);
}

}  // namespace

ParseResult parse_extractor_json(
    std::string_view raw_json,
    const ExistingRefMap& /*existing_ref_map*/) {
    ParseResult result;

    const std::string_view arr_text = extract_array(raw_json);
    if (arr_text.empty()) {
        result.errors.push_back({"not_json_array", "no top-level JSON array found", 0});
        return result;
    }

    nlohmann::json arr;
    try {
        arr = nlohmann::json::parse(arr_text);
    } catch (const std::exception& e) {
        result.errors.push_back({"json_parse_error", e.what(), 0});
        return result;
    }
    if (!arr.is_array()) {
        result.errors.push_back({"not_json_array", "top level is not an array", 0});
        return result;
    }

    for (const auto& el : arr) {
        if (!el.is_object()) continue;  // lenient: skip non-objects
        try {
            ExtractedStatement s;
            // NOTE: holder_id is NOT set here — Extractor::run overrides it with
            // the run arg (the agent, e.g. "self"), matching the existing XML path.
            // The LLM "holder" field is advisory; multi-holder attribution is
            // deferred (spec §1 out-of-scope).
            s.holder_perspective = schema::perspective_from_string(
                to_lower(el.value("holder_perspective", std::string("inferred"))));
            s.subject_kind = "cognizer";
            s.subject_id   = el.value("subject", std::string());
            s.predicate    = el.value("predicate", std::string());
            s.object_value = el.value("object", std::string());
            // spec §4: nesting_depth>=2 -> object_kind="statement", else "str".
            const int nesting_depth = el.value("nesting_depth", 0);
            s.object_kind  = (nesting_depth >= 2) ? "statement" : "str";
            if (s.subject_id.empty() || s.predicate.empty() || s.object_value.empty()) {
                continue;  // lenient: skip incomplete element
            }
            // canonical_object_hash is COMPUTED C++-side (never trusted from LLM);
            // object_value stays the raw object text (matches the old XML path).
            const schema::CanonicalResult cr =
                schema::canonicalize_object(schema::CanonicalInput{s.object_value});
            s.canonical_object_hash = cr.sha256_hex;
            s.modality   = schema::modality_from_string(
                normalize_modality(el.value("modality", std::string("believes"))));
            s.polarity   = schema::polarity_from_string(
                to_lower(el.value("polarity", std::string("pos"))));
            s.confidence = 0.7;
            s.observed_at = now_iso8601_utc();
            result.statements.push_back(std::move(s));
        } catch (const std::exception&) {
            continue;  // lenient: bad enum / shape -> skip this element
        }
    }
    return result;
}

}  // namespace starling::extractor
```
（注意：`schema::CanonicalInput{s.object_value}` 用 string 变体 → `cr.sha256_hex` 作 canonical_object_hash；`object_value` 保留 LLM 原文（与旧 XML 路径一致，不覆写为 canonical 形）。`existing_ref_map` 本期未用——subject/object 名不做 ref 解析，minimal。若 `CanonicalInput{std::string}` 重载有歧义，显式写 `schema::CanonicalInput{std::string(s.object_value)}`。）

- [ ] **Step 3: 写 `tests/cpp/test_json_parser.cpp`**

镜像旧 `test_xml_parser.cpp` 的结构（用同一 test 框架；看其 include/TEST 宏写法）。核心用例：
```cpp
#include "starling/extractor/json_parser.hpp"
#include "starling/extractor/existing_ref_map.hpp"
// + 项目的测试框架头（同 test_xml_parser.cpp）

using namespace starling::extractor;

// 合法 JSON 数组 → 1 statement，字段映射 + C++ 簿记
TEST(JsonParser, ParsesSemanticCoreAndFillsBookkeeping) {
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob",)"
        R"("predicate":"responsible_for","object":"auth","modality":"BELIEVES",)"
        R"("polarity":"POS","nesting_depth":0}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_TRUE(r.errors.empty());
    ASSERT_EQ(r.statements.size(), 1u);
    const auto& s = r.statements[0];
    EXPECT_EQ(s.subject_kind, "cognizer");
    EXPECT_EQ(s.subject_id, "Bob");
    EXPECT_EQ(s.predicate, "responsible_for");
    EXPECT_EQ(s.object_kind, "str");
    EXPECT_FALSE(s.canonical_object_hash.empty());   // computed
    EXPECT_EQ(s.holder_perspective, schema::Perspective::FIRST_PERSON);
    EXPECT_EQ(s.modality, schema::Modality::BELIEVES);
    EXPECT_EQ(s.polarity, schema::Polarity::POS);
    EXPECT_DOUBLE_EQ(s.confidence, 0.7);
    EXPECT_FALSE(s.observed_at.empty());
}

// nesting_depth>=2 → object_kind="statement"（spec §4）
TEST(JsonParser, NestedBeliefMapsToStatementObjectKind) {
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"self","holder_perspective":"INFERRED","subject":"Alice",)"
        R"("predicate":"thinks","object":"Bob trusts Carol","modality":"BELIEVES",)"
        R"("polarity":"POS","nesting_depth":2}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_TRUE(r.errors.empty());
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].object_kind, "statement");
}

// 剥 ```json fence
TEST(JsonParser, StripsCodeFence) {
    ExistingRefMap refs;
    const std::string raw =
        "```json\n[{\"holder\":\"self\",\"holder_perspective\":\"INFERRED\","
        "\"subject\":\"X\",\"predicate\":\"knows\",\"object\":\"y\","
        "\"modality\":\"KNOWS\",\"polarity\":\"POS\",\"nesting_depth\":0}]\n```";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_TRUE(r.errors.empty());
    EXPECT_EQ(r.statements.size(), 1u);
}

// 非数组 → ParseError（让 orchestrator 重试）
TEST(JsonParser, NonArrayProducesError) {
    ExistingRefMap refs;
    ParseResult r = parse_extractor_json("not json at all", refs);
    EXPECT_FALSE(r.errors.empty());
    EXPECT_TRUE(r.statements.empty());
}

// 宽容：坏元素跳过，好元素保留，errors 仍空
TEST(JsonParser, SkipsMalformedElementLeniently) {
    ExistingRefMap refs;
    const std::string raw =
        R"([{"subject":"","predicate":"p","object":"o","modality":"BELIEVES","polarity":"POS","holder_perspective":"INFERRED"},)"
        R"({"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}])";
    ParseResult r = parse_extractor_json(raw, refs);
    EXPECT_TRUE(r.errors.empty());
    EXPECT_EQ(r.statements.size(), 1u);   // 空 subject 那条被跳过
}
```
（实现者：先 Read `tests/cpp/test_xml_parser.cpp` 确认 TEST 宏/include 的确切写法并对齐；用同一框架。）

- [ ] **Step 4: CMake 切换 + 删 xml_parser**

- `CMakeLists.txt` line 72：`src/extractor/xml_parser.cpp` → `src/extractor/json_parser.cpp`。
- `tests/cpp/CMakeLists.txt` line 46：`test_xml_parser.cpp` → `test_json_parser.cpp`。
- 删文件：
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt
git rm src/extractor/xml_parser.cpp include/starling/extractor/xml_parser.hpp tests/cpp/test_xml_parser.cpp
```
（注意：Task 4 才把 `Extractor::run` 从 `parse_extractor_xml` 改调 `parse_extractor_json`——本 Task 删 xml_parser 后 extractor.cpp 仍 include 它会编译失败。**所以 Task 3 与 Task 4 的编译验证合并在 Task 4**：本 Task 先写 json_parser + 测试 + CMake + git rm，**编译留到 Task 4** 改完 run 后一起。本 Task 的 Step 5 commit 不跑全量编译。）

- [ ] **Step 5: Commit（不单独编译，留 Task 4 一起绿）**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt
git add include/starling/extractor/json_parser.hpp src/extractor/json_parser.cpp tests/cpp/test_json_parser.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(P2.i): json_parser 替代 xml_parser（LLM 出语义，C++ 填簿记）

src/extractor/json_parser.cpp parse_extractor_json：nlohmann/json 解析 LLM 的
JSON 数组 → ExtractedStatement。LLM 出 holder_perspective/subject/predicate/
object/modality/polarity（枚举 to_lower + modality 词表归一 enforces→norm_ought
/observes→knows）；C++ 填 subject_kind=cognizer、object_kind=str、
canonical_object_hash 计算、confidence=0.7、observed_at=now。宽容解析（坏元素跳过，
非数组才报错让 orchestrator 重试）。删 xml_parser；CMake 切换。test_json_parser 4 用例。
（编译验证与 Task 4 改 run 一起。）

EOF
```

---

## Task 4: Extractor 注入 prompt_template + run 插 payload + 改调 json_parser（C++ + 绑定 + 重建）

**Files:**
- Modify: `include/starling/extractor/extractor.hpp`、`src/extractor/extractor.cpp`、`bindings/python/module.cpp`

- [ ] **Step 1: Extractor 构造 + 成员加 prompt_template**

Modify `include/starling/extractor/extractor.hpp`：
- 构造（约 line 28-29）改为：
```cpp
    Extractor(starling::persistence::Connection& conn, LLMAdapter& adapter,
              std::string prompt_template = "")
        : conn_(conn), adapter_(adapter), prompt_template_(std::move(prompt_template)) {}
```
- 成员（约 line 55-56 区）加：
```cpp
    std::string prompt_template_;
```
- 加一个私有/静态 helper 声明（替换占位）：
```cpp
    std::string build_prompt(std::string_view holder_id,
                             const std::vector<std::uint8_t>& payload_bytes) const;
```

- [ ] **Step 2: extractor.cpp 实现 build_prompt + run 改用它 + 改调 json_parser**

Modify `src/extractor/extractor.cpp`：
- include 改：`#include "starling/extractor/json_parser.hpp"`（替代 xml_parser）。
- 加 `build_prompt` 实现（payload 解码 UTF-8 填进模板 `{convo}`；模板空时退回旧占位）：
```cpp
std::string Extractor::build_prompt(std::string_view holder_id,
                                    const std::vector<std::uint8_t>& payload_bytes) const {
    if (prompt_template_.empty()) {
        // FakeLLM / tests ignore the prompt; keep a minimal deterministic body.
        return Extractor::build_prompt_body_for_tests(holder_id, payload_bytes, {});
    }
    const std::string convo(payload_bytes.begin(), payload_bytes.end());
    const std::string placeholder = "{convo}";
    std::string out = prompt_template_;
    const auto pos = out.find(placeholder);
    if (pos != std::string::npos) {
        out.replace(pos, placeholder.size(), convo);
    } else {
        out += "\n\nConversation:\n" + convo;  // template lacked {convo}: append
    }
    return out;
}
```
- `run`（约 line 170-172）prompt 构造改：
```cpp
    const std::string prompt_body = build_prompt(holder_id, payload_bytes);
    const std::string prompt_input_hash = compute_prompt_input_hash(prompt_body);
```
- `run`（约 line 193）parse 改：`ParseResult parsed = parse_extractor_json(resp.raw_xml, existing_ref_map);`
- `run` 写入循环里（约 line 216-220，已填 holder_id/tenant/chunk/source_hash 处）补一行填 perceived_by：
```cpp
        if (stmt.perceived_by.empty()) {
            stmt.perceived_by = {std::string(holder_id)};
        }
```

- [ ] **Step 3: 绑定 Extractor 加第三参**

Modify `bindings/python/module.cpp` 的 `Extractor` 绑定（约 line 731-735 的 init lambda）：
```cpp
    .def(py::init([](starling::persistence::Connection& conn,
                     starling::extractor::LLMAdapter& a,
                     const std::string& prompt_template) {
        return new starling::extractor::Extractor(conn, a, prompt_template);
    }), py::keep_alive<1, 2>(), py::keep_alive<1, 3>(),
       py::arg("connection"), py::arg("adapter"), py::arg("prompt_template") = "")
```

- [ ] **Step 4: 全量重建 + C++ 测试**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt && source .venv/bin/activate
cmake --build build 2>&1 | tail -4
ctest --test-dir build -R JsonParser 2>&1 | tail -4
ctest --test-dir build 2>&1 | tail -3
cmake --install build --prefix .venv/lib/python3.14/site-packages 2>&1 | tail -1
python -c "from starling import _core; print('Extractor 3-arg ok:', hasattr(_core, 'Extractor'))"
```
Expected: build 成功（xml_parser 已删、run 改调 json_parser → 编译通过）；JsonParser 4 用例 passed；ctest 全 passed（test_xml_parser 已换 test_json_parser；test_extractor_orchestrator 暂可能因 canned XML 失败——Task 4 Step 5 先迁它的 canned）。

- [ ] **Step 5: 迁 C++ orchestrator/fake_llm 测试的 canned XML→JSON**

Modify `tests/cpp/test_extractor_orchestrator.cpp` + `tests/cpp/test_fake_llm_adapter.cpp`：把 canned `LLMResponse.raw_xml` 的 `<extraction>...<statement>...</statement></extraction>` 改成 JSON 数组（用上方共享 stub 格式），并把断言里依赖 XML 特定值的地方对齐（subject_id/predicate/object_value 仍是 Bob/responsible_for/auth；canonical_object_hash 现由 C++ 计算，断言改 `!empty()` 而非具体 hash 值）。
Run:
```bash
cmake --build build 2>&1 | tail -2 && ctest --test-dir build 2>&1 | tail -3
```
Expected: ctest 全 passed。

- [ ] **Step 6: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt
git add include/starling/extractor/extractor.hpp src/extractor/extractor.cpp bindings/python/module.cpp tests/cpp/test_extractor_orchestrator.cpp tests/cpp/test_fake_llm_adapter.cpp
git commit -F - <<'EOF'
feat(P2.i): Extractor 注入 prompt_template + run 插 payload + 改调 json_parser

Extractor(conn, adapter, prompt_template="")；build_prompt 把 payload 解码填进
模板 {convo}（模板空则退回占位，FakeLLM 测试无视 prompt）。run 改调
parse_extractor_json，写入循环填 perceived_by={holder}。绑定加第三参（默认 ""）。
C++ orchestrator/fake_llm 测试 canned XML→JSON。ctest 全绿。

EOF
```

---

## Task 5: memory.py/engine.py 传 prompt + Python canned XML→JSON 全迁移（13 文件）

**Files:**
- Modify: `python/starling/memory.py`、`python/starling/dashboard/engine.py` + 11 个测试文件

- [ ] **Step 1: memory.py / engine.py 传 EXTRACTION_PROMPT**

Modify `python/starling/memory.py`：顶部 import 加 `from starling.extractor.prompts import EXTRACTION_PROMPT`；line 136 `ext = _core.Extractor(self._conn, self._llm)` → `ext = _core.Extractor(self._conn, self._llm, EXTRACTION_PROMPT)`。
Modify `python/starling/dashboard/engine.py`：顶部加同 import；line 140 `_core.Extractor(self._conn, self.llm)` → `_core.Extractor(self._conn, self.llm, EXTRACTION_PROMPT)`。

- [ ] **Step 2: 建共享 JSON stub 常量**

在测试里复用的 canned JSON（替代旧 canned XML）。**对每个用 make_stub_llm/FakeLLM canned XML 的测试文件**，把 `default_xml=`（或 set_default_response 的）`<extraction>...` 字面量替换成对应 JSON 数组。统一用：
```python
_STUB_JSON = '[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
```
（各文件原 canned XML 表达的语义不同的，按其原意改 JSON——保持该测试断言的 subject/predicate/object 值。）

- [ ] **Step 3: 逐文件迁移**

把以下文件里的 canned `<extraction>`/`<statements>` XML 字面量改成等价 JSON 数组（`make_stub_llm(default_xml=...)` 的值、`set_default_response`/`set_response` 的值、`memory.py` make_stub_llm 文档串示例）：
- `python/starling/memory.py`（make_stub_llm docstring 示例 XML→JSON）
- `tests/python/test_memory_facade.py`
- `tests/python/test_m0_4_acceptance.py`
- `tests/python/test_extractor_dead_letter.py`
- `tests/python/test_extractor_partial_success.py`
- `tests/python/test_extractor_idempotency.py`
- `tests/python/test_extractor_holder_perspective.py`
- `tests/python/test_extractor_chunk_duplicate.py`
- `tests/python/test_dashboard_engine.py`（`_STUB_XML`→JSON）
- `tests/python/test_dashboard_commands.py`（`_STUB_XML`→JSON）
- `tests/python/test_dashboard_config_routes.py`（若含 stub XML）
（实现者：逐文件 Read + grep `<extraction|<statements|<statement`，把 XML 字面量换 JSON；断言里若依赖具体 canonical_object_hash 值，改为不依赖具体 hash；perspective/modality/polarity 断言保持语义。）

- [ ] **Step 4: 跑全量 pytest**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt && source .venv/bin/activate
python -m pytest -q 2>&1 | tail -3
```
Expected: 全 passed（迁移后无 failed）。若某测试因旧 XML 断言失败，按 JSON 语义修断言（保持测试意图）。

- [ ] **Step 5: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt
git add python/starling/memory.py python/starling/dashboard/engine.py tests/python/
git commit -F - <<'EOF'
feat(P2.i): Memory/engine 注入 EXTRACTION_PROMPT + Python canned XML→JSON 迁移

memory.py + dashboard/engine.py 给 _core.Extractor 传 EXTRACTION_PROMPT（真实 prompt
进 run 路径）。13 个 Python 文件的 make_stub_llm/FakeLLM canned XML→JSON 数组
（共享 _STUB_JSON 格式）；断言对齐（canonical_object_hash 现 C++ 计算，不依赖具体值）。
pytest 全绿。

EOF
```

---

## Task 6: gated 真实 LLM 端到端烟测

**Files:**
- Create: `scripts/eval_extractor_smoke.py`

- [ ] **Step 1: 写 gated 烟测**

```python
#!/usr/bin/env python3
"""Gated real-LLM extraction smoke test (needs OPENAI_API_KEY; not in CI).

Builds a real Memory with a real OpenAI-compatible LLM and asserts remember()
extracts >=1 statement from real text — the end-to-end path the dashboard QA
found broken (stub-prompt extractor yielded 0). Run e.g.:

  OPENAI_BASE_URL=https://api.deepseek.com/v1 OPENAI_API_KEY=$DEEPSEEK_API_KEY \\
    python scripts/eval_extractor_smoke.py --model deepseek-chat
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="deepseek-chat")
    ap.add_argument("--text", default="Alice: I believe Bob is responsible for auth.")
    args = ap.parse_args()
    if not os.environ.get("OPENAI_API_KEY"):
        print("SKIP: OPENAI_API_KEY not set", file=sys.stderr)
        return 0
    from starling.memory import Memory, make_openai_llm
    db = tempfile.mktemp(suffix=".db")
    mem = Memory.open(db, agent="self", tenant_id="default",
                      llm=make_openai_llm(model=args.model))
    r = mem.remember(args.text)
    n = len(r.statement_ids)
    print(f"remember outcome={r.outcome} statements={n}")
    if n >= 1:
        print("PASS — real-LLM extraction produced statements")
        return 0
    print("BLOCKED — real-LLM extraction produced 0 statements")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 无 key 时 SKIP（CI 安全）**

Run（无 key）:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt && source .venv/bin/activate
env -u OPENAI_API_KEY python scripts/eval_extractor_smoke.py 2>&1 | tail -2
```
Expected: `SKIP: OPENAI_API_KEY not set`，exit 0。

- [ ] **Step 3: 真实 key 跑（手动 gated，验证核心目标）**

> ⚠ 需真实 key（DeepSeek）。这是本里程碑的核心验收——remember 接真实 LLM 抽出 >0。
```bash
source ~/.zshrc
OPENAI_BASE_URL=https://api.deepseek.com/v1 OPENAI_API_KEY=$DEEPSEEK_API_KEY \
  python scripts/eval_extractor_smoke.py --model deepseek-chat 2>&1 | tail -3
```
Expected: `PASS — real-LLM extraction produced statements`（statements >=1）。**若仍 0**：检查 build_prompt 是否真把 payload 插进 {convo}、parse_extractor_json 容错、max_tokens 是否生效——这是核心目标，必须真过。

- [ ] **Step 4: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt
git add scripts/eval_extractor_smoke.py
git commit -F - <<'EOF'
feat(P2.i): gated 真实 LLM 抽取端到端烟测

scripts/eval_extractor_smoke.py：真实 Memory + 真实 LLM remember → 断言抽出 >=1
statement（dashboard QA 暴露、从没验证过的端到端路径）。无 key SKIP（CI 安全）；
真实 key 下断言 PASS。

EOF
```

---

## Task 7: 回归 + roadmap 登记 + close

**Files:**
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md`

- [ ] **Step 1: 全量回归（worktree 重建后）**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt && source .venv/bin/activate
cmake --build build 2>&1 | tail -2
ctest --test-dir build 2>&1 | tail -3
python -m pytest -q 2>&1 | tail -2
ls migrations/ | tail -1
```
Expected: ctest 全 passed（test_json_parser 替代 test_xml_parser）；pytest 全 passed；migration 仍 0021（无新增）。

- [ ] **Step 2: 无密钥泄漏扫描**

Run:
```bash
grep -rnE "sk-[A-Za-z0-9]{16,}" python src scripts docs/superpowers/plans/2026-06-06-extractor-real-prompt.md 2>/dev/null || echo "OK 无真实密钥"
```
Expected: OK 无真实密钥。

- [ ] **Step 3: roadmap 登记**

在 `docs/superpowers/plans/2026-05-23-roadmap.md` 的 P2 收尾表后追加一行（或合适处）：
```markdown
| **P2.i Extractor 真实 prompt ✅** | C++ Extractor 接真实 LLM 能真正抽出 Statement（补 M0.4 占位 prompt 缺口） | dashboard QA 暴露：remember 接真 LLM 抽 0 statements（占位 prompt） | **[2026-06-06-extractor-real-prompt.md](2026-06-06-extractor-real-prompt.md)**：prompts.py 单一源（eval 共享）注入 C++ Extractor + json_parser 替代 xml_parser（LLM 出语义/C++ 填簿记）+ OpenAIAdapter max_tokens；改 C++（worktree+重建），无 migration；gated 真实 LLM 烟测 PASS |
```

- [ ] **Step 4: 提交 plan + roadmap（close）**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/extractor-real-prompt
git add docs/superpowers/plans/2026-06-06-extractor-real-prompt.md docs/superpowers/plans/2026-05-23-roadmap.md
git commit -F - <<'EOF'
docs(P2.i): land Extractor 真实 prompt 实施计划 + roadmap 登记

C++ Extractor 真实抽取闭环：prompts.py 单一源注入 + json_parser 替代 xml_parser +
OpenAIAdapter max_tokens；gated 真实 LLM 烟测验证 remember 抽出 >0。改 C++
（worktree+重建），无 migration；ctest（json_parser 替代 xml_parser）+ pytest 全绿。

EOF
```

- [ ] **Step 5: 合并回 main（需显式 consent + dangerouslyDisableSandbox）**

> ⚠ 合并前 `git -C /Users/jaredguo-mini/develop/memory/starling status` 检查清理 stray，再 `--no-ff` 合并 `worktree-extractor-real-prompt` 回 main；合并后主仓库需 `cmake --build build && cmake --install build`（C++ 改动）刷新主 `_core`。**需用户显式同意**后执行。

---

## 自检（writing-plans self-review）

**1. Spec 覆盖：** §2 单一源 prompt→Task 1；§3 注入→Task 4；§4 json_parser→Task 3（+Task 4 改 run 调用）——字段簿记齐：subject_kind=cognizer、`object_kind=str（nesting_depth>=2→statement，spec §4 明列）`、canonical_object_hash 计算、perceived_by=holder（run 填）、confidence=0.7、observed_at=now；holder_id 由 run 覆写（非 LLM holder，与旧 XML 路径一致，多 holder 归因 §1 范围外）；§5 max_tokens→Task 2；§6 测试迁移→Task 3(C++ parser 测试,含 nesting→statement 用例)/Task 4(orchestrator/fake)/Task 5(Python 13)/Task 6(gated)；§7 约束→各 Task（worktree+重建注入）；§8 验收→Task 6(核心 gated)+Task 7(回归)。无缺口。

**2. 占位扫描：** Task 1 Step 1 的 `<<< 把 eval ... 粘到这里 >>>` 是**明确的逐字搬运指令**（给了确切源行 + 约束「勿改文本」），非 TBD——prompt 是 201 行既有文本，搬运而非新写。其余代码步含完整 code block。Task 3/4 的"编译验证合并"是真实依赖说明（xml_parser 删除后 extractor.cpp 改 run 才编译通过）。

**3. 类型一致：** `parse_extractor_json(raw, ExistingRefMap)->ParseResult{statements,errors}`（Task 3 ↔ Task 4 run 调用）；`ParseError{kind,detail,byte_offset}`（与旧 xml_parser 同名同构，orchestrator 用法不变）；`ExtractedStatement` 字段（holder_perspective=Perspective enum、modality=Modality enum、polarity=Polarity enum、canonical_object_hash、confidence double、observed_at、perceived_by vector）经 `perspective_from_string`/`modality_from_string`/`polarity_from_string`（收小写）+ `canonicalize_object(CanonicalInput).sha256_hex` 填（Task 3）；`Extractor(conn, adapter, prompt_template="")`（Task 4 hpp/cpp/binding 一致）；`EXTRACTION_PROMPT`（Task 1 prompts.py ↔ Task 5 memory/engine import）；`OpenAIAdapter::Config::max_tokens`（Task 2 struct/extract/binding 一致）；`_STUB_JSON`（Task 5 共享）。一致。
