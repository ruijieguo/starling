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

# P2.l 配置·多适配器 Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

**Goal:** dashboard 支持多 provider 配置 + 可信配置体验:新 C++ `AnthropicAdapter`(原生 Messages API)+ Python provider 工厂 + 配置 v2(provider 字段 + 预设 + 向后兼容)+ `POST /api/config/test` 测连通 + 设置页 provider 预设/模型下拉/测试连接/降级可见。

**Architecture:** C++ 加一个 `AnthropicAdapter`(实现既有 `LLMAdapter::extract` 接口,libcurl→`/v1/messages`,`x-api-key`+`anthropic-version` 头,解析 `content[0].text`,key 从 `ANTHROPIC_API_KEY` env)+ pybind 绑定(镜像 OpenAIAdapter,api_key 不暴露)。Python `DashboardEngine` 的 `_build_chat_adapter` 按 `provider` 分发(anthropic→AnthropicAdapter via ANTHROPIC env-swap,余→OpenAIAdapter)。配置 v2 在 `~/.starling/starling.json` 加 `provider` 字段(文件级,**无 migration**),向后兼容旧文件。`POST /api/config/test` 用候选配置建临时适配器、真打一次最小调用、返回 `{ok, latency_ms, detail}` 不落盘不记 key。设置页加 provider 预设下拉 + 模型候选 + 测试连接按钮 + embedder 降级状态。

**Tech Stack:** C++20(libcurl + nlohmann/json,镜像 `openai_adapter.cpp`)· pybind11 · Python(FastAPI dashboard)· Svelte 5 前端。**无 migration**(配置文件级)。构建:`python scripts/configure_build.py --build`(C++/ctest)+ `--python-editable`(刷新 `_core`)。

**全局约束:** worktree `p2-l-config-multiadapter`(C++ 隔离)。改 C++/绑定后必 `--build` + `--python-editable`。API key 仅 env(`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`,env-swap 注入),绝不绑定 Python/记录/回传;`/api/config` 只回 `key_set`,`/api/config/test` 不记录请求体。explicit-path git add;无 --no-verify/--amend。C++/Python 现有不变量不破(Extractor 接口不变,只加新适配器)。ci_static_scan 纳入收尾。

---

## Task 0: worktree + baseline
venv + `pip install -r requirements-build.txt` + `python scripts/configure_build.py --build --test`(ctest 基线)+ `--python-editable` + `pip install pytest pytest-mock jsonschema fastapi uvicorn[standard] httpx` + `python -m pytest -q`(pytest 基线)。记录基线数,后续只增不减。

## Task 1: C++ AnthropicAdapter + 绑定 + Python 包装

**Create `include/starling/extractor/anthropic_adapter.hpp`:**
```cpp
#pragma once

#include "starling/extractor/llm_adapter.hpp"

#include <string>
#include <string_view>

namespace starling::extractor {

class AnthropicAdapter : public LLMAdapter {
public:
    struct Config {
        std::string base_url;                    // e.g. "https://api.anthropic.com"
        std::string api_key;                     // x-api-key
        std::string model = "claude-sonnet-4-5";
        std::string api_version = "2023-06-01";  // anthropic-version header
        int         timeout_ms = 60000;
        int         max_retries = 3;
        int         max_tokens = 4096;

        // Reads ANTHROPIC_BASE_URL and ANTHROPIC_API_KEY from env. Throws
        // std::runtime_error if api_key is unset.
        static Config from_env();
    };

    explicit AnthropicAdapter(Config cfg);

    LLMResponse extract(std::string_view prompt,
                        std::string_view prompt_input_hash) override;

private:
    Config cfg_;
};

}  // namespace starling::extractor
```

**Create `src/extractor/anthropic_adapter.cpp`** (mirror of `openai_adapter.cpp`; only URL / headers / body / parse differ):
```cpp
#include "starling/extractor/anthropic_adapter.hpp"

#include <chrono>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <thread>

#include <curl/curl.h>
#include <nlohmann/json.hpp>

namespace starling::extractor {

namespace {

std::size_t write_cb(char* ptr, std::size_t size, std::size_t nmemb, void* userdata) {
    auto* buf = static_cast<std::string*>(userdata);
    buf->append(ptr, size * nmemb);
    return size * nmemb;
}

bool is_retryable_status(long http_code) {
    return http_code == 429 || (http_code >= 500 && http_code < 600);
}

bool is_retryable_curl_code(CURLcode rc) {
    switch (rc) {
        case CURLE_OPERATION_TIMEDOUT:
        case CURLE_COULDNT_CONNECT:
        case CURLE_COULDNT_RESOLVE_HOST:
        case CURLE_COULDNT_RESOLVE_PROXY:
        case CURLE_SEND_ERROR:
        case CURLE_RECV_ERROR:
        case CURLE_GOT_NOTHING:
        case CURLE_PARTIAL_FILE:
            return true;
        default:
            return false;
    }
}

}  // namespace

AnthropicAdapter::Config AnthropicAdapter::Config::from_env() {
    Config c;
    const char* key = std::getenv("ANTHROPIC_API_KEY");
    if (!key || *key == '\0') {
        throw std::runtime_error("ANTHROPIC_API_KEY not set");
    }
    c.api_key = key;
    const char* base = std::getenv("ANTHROPIC_BASE_URL");
    c.base_url = (base && *base) ? base : "https://api.anthropic.com";
    return c;
}

AnthropicAdapter::AnthropicAdapter(Config cfg) : cfg_(std::move(cfg)) {}

LLMResponse AnthropicAdapter::extract(std::string_view prompt,
                                      std::string_view /*prompt_input_hash*/) {
    nlohmann::json body = {
        {"model",      cfg_.model},
        {"max_tokens", cfg_.max_tokens},
        {"messages",   nlohmann::json::array({
            {{"role", "user"}, {"content", std::string(prompt)}}})}
    };
    const std::string body_str = body.dump();
    const std::string url      = cfg_.base_url + "/v1/messages";
    const std::string key_hdr  = "x-api-key: " + cfg_.api_key;
    const std::string ver_hdr  = "anthropic-version: " + cfg_.api_version;

    int delay_ms = 1000;
    for (int attempt = 0; attempt <= cfg_.max_retries; ++attempt) {
        CURL* curl = curl_easy_init();
        if (!curl) return {.raw_xml = {}, .ok = false, .error = "curl_init_failed"};

        std::string resp_buf;
        curl_slist* headers = nullptr;
        headers = curl_slist_append(headers, "Content-Type: application/json");
        headers = curl_slist_append(headers, key_hdr.c_str());
        headers = curl_slist_append(headers, ver_hdr.c_str());

        curl_easy_setopt(curl, CURLOPT_URL,           url.c_str());
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER,    headers);
        curl_easy_setopt(curl, CURLOPT_POST,          1L);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS,    body_str.c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(body_str.size()));
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA,     &resp_buf);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS,    static_cast<long>(cfg_.timeout_ms));

        const CURLcode rc = curl_easy_perform(curl);
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        curl_slist_free_all(headers);
        curl_easy_cleanup(curl);

        if (rc != CURLE_OK) {
            if (is_retryable_curl_code(rc) && attempt < cfg_.max_retries) {
                std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms));
                delay_ms *= 2;
                continue;
            }
            return {.raw_xml = {}, .ok = false,
                    .error = std::string("transport_error:") + curl_easy_strerror(rc)};
        }

        if (is_retryable_status(http_code)) {
            if (attempt < cfg_.max_retries) {
                std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms));
                delay_ms *= 2;
                continue;
            }
            return {.raw_xml = {}, .ok = false, .error = "transient_after_retry"};
        }

        if (http_code >= 400) {
            return {.raw_xml = {}, .ok = false,
                    .error = "permanent_" + std::to_string(http_code)};
        }

        try {
            auto j = nlohmann::json::parse(resp_buf);
            const std::string content = j["content"][0]["text"].get<std::string>();
            return {.raw_xml = content, .ok = true, .error = {}};
        } catch (const std::exception&) {
            return {.raw_xml = {}, .ok = false, .error = "malformed_response"};
        }
    }
    return {.raw_xml = {}, .ok = false, .error = "transient_after_retry"};
}

}  // namespace starling::extractor
```

**Modify `CMakeLists.txt`** — add after `src/extractor/openai_adapter.cpp`:
```cmake
    src/extractor/anthropic_adapter.cpp
```

**Modify `bindings/python/module.cpp`** — after the OpenAIAdapter block, add (include the header at top: `#include "starling/extractor/anthropic_adapter.hpp"`):
```cpp
{
    using starling::extractor::AnthropicAdapter;
    py::class_<AnthropicAdapter::Config>(m, "AnthropicAdapterConfig")
        .def(py::init<>())
        .def_readwrite("base_url",    &AnthropicAdapter::Config::base_url)
        .def_readwrite("model",       &AnthropicAdapter::Config::model)
        .def_readwrite("api_version", &AnthropicAdapter::Config::api_version)
        .def_readwrite("timeout_ms",  &AnthropicAdapter::Config::timeout_ms)
        .def_readwrite("max_retries", &AnthropicAdapter::Config::max_retries)
        .def_readwrite("max_tokens",  &AnthropicAdapter::Config::max_tokens)
        .def_static("from_env",       &AnthropicAdapter::Config::from_env);
    py::class_<AnthropicAdapter, starling::extractor::LLMAdapter>(m, "AnthropicAdapter")
        .def(py::init<AnthropicAdapter::Config>());
}
```
(api_key 不 def_readwrite,镜像 OpenAI。)

**Modify `python/starling/extractor/__init__.py`** — re-export `AnthropicAdapterConfig` + `AnthropicAdapter`(镜像 OpenAI 行)。
**Modify `python/starling/memory.py`** — add `make_anthropic_llm(*, model="", base_url="", timeout_ms=0, max_retries=0)`(镜像 `make_openai_llm`,换 `AnthropicAdapterConfig`/`AnthropicAdapter`)。

**Build:** `python scripts/configure_build.py --build` + `--python-editable`。
**Test (C++):** 加 `tests/cpp/test_anthropic_adapter.cpp`——构造 + `from_env` 抛错(无 key)+ 注册进 CMake test。真实 HTTP 走 gated 烟测(`ANTHROPIC_API_KEY` 存在时)。
**Test (Python):** `from starling import _core; _core.AnthropicAdapter` 可导入 + `make_anthropic_llm` gated 真测。

## Task 2: 配置 v2 + provider 工厂

- **`config.py`**:`_default_llm` 加 `"provider": "openai"`;`_default_embedder` 加 `"provider": "openai"`。向后兼容:load 时旧文件无 provider → 推断(base_url 含 anthropic→anthropic,否则 openai)。
- **`engine.py`**:`_build_chat_adapter(llm_cfg)` 顶部读 `provider = llm_cfg.get("provider","openai")`;`anthropic` 分支用 ANTHROPIC env-swap(新 `_env_swap_anthropic` 或泛化 `_env_swap` 收 env 名)+ `_core.AnthropicAdapterConfig.from_env()` + `AnthropicAdapter`;余走原 OpenAI 路径。`_build_embed_adapter` 不加 anthropic(无 embedding API),provider 仅影响 base_url/model(仍 OpenAI 兼容)。
- **`routes/config.py`**:`ProviderBody` 加 `provider: str | None`;`_merge` 字段加 `"provider"`;`_mask` 回传 `provider`。
- **Test:** pytest——provider 工厂分发(monkeypatch `_core.AnthropicAdapter`/`OpenAIAdapter` 断言按 provider 选对);配置 v2 round-trip(存读 provider);旧文件无 provider 向后兼容。

## Task 3: POST /api/config/test 测连通

- **`routes/config.py`**:新 `@router.post("/config/test")`,收 `{kind: "llm"|"embedder", ...ProviderBody}`;从 `request.app.state.config` 拷贝对应 provider dict、应用 body(同 `_merge` 逻辑,**不落盘**);`_build_chat_adapter`/`_build_embed_adapter` 建临时适配器;打最小调用(chat:`extract("ping", "")`;embedder:embed 一条);返回 `{ok: bool, latency_ms: int, detail: str}`。**不持久化、不回传 key、不记录请求体**(确保该路由无 body 日志)。无 key 时 ok=false detail 明示。
- **Test:** pytest——monkeypatch 适配器返回成功/失败,断言 test 端点不落盘(config 不变)+ 不回 key + 形状正确。

## Task 4: 设置页 provider 预设 + 测试连接 + 降级可见(前端)

- **`dashboard/web/src/lib/providers.ts`**:provider 预设表常量(openai/azure/ollama/vllm/lmstudio/groq/deepseek/openrouter/anthropic/custom,每个含 default base_url + 常用模型候选 + needs_key);embedder 预设(openai/azure/ollama/voyage/custom,**不含 anthropic**)。
- **`settings/+page.svelte`**:LLM/Embedder 卡各加 provider `Select`(bits-ui,选了自动填 base_url + 模型 datalist/候选 + 标注是否需 key)+ **测试连接**按钮(POST /api/config/test + 内联绿勾/红叉 + 延迟)+ embedder 降级状态(无 key→「未启用 stub,召回不可用」)+ token 轮换按钮(可选)。引入 bits-ui Select 组件(`ui/Select.svelte`)。
- **Test:** vitest(providers 预设表 + 一个 Select 渲染)+ playwright(provider 选择填充 base_url)。

## Task 5: 回归 + 收尾
ctest + pytest + ci_static_scan(`python scripts/ci_static_scan.py`)+ vitest + playwright + svelte-check 全绿。真模型 QA(gated):Anthropic 原生 + 一个 OpenAI 兼容 provider 端到端(测试连接绿 + remember 抽出 statements)。roadmap 登记 P2.l。自审 + 修。合并 + push(显式授权一口气完成)。

## 非目标(留 P2.m / 未来)
Voyage embedder(标未来);重嵌完整后台任务(本期确认 + 简单进度);手动明暗开关(P2.m);面板深做(P2.m)。
