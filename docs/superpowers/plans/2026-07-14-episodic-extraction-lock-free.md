# EpisodicExtractor 三相化(方案2 option B 收尾)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 照方案2 option A(`src/extractor/extractor.cpp` 的 `extract_llm`/`persist` 拆分)把 `EpisodicExtractor::extract` 拆成 `extract_llm`(纯 LLM+parse,锁外无 txn)+ `persist`(事件落库,锁内),让 episodic 的 ~20-50s LLM 调用从 remember commit 写锁内移到锁外 extract 相。

**Architecture:** `EpisodicExtractor::extract` 现为「LLM + DB 写」单体(`episodic_extractor.cpp:77-216`)。拆成 `extract_llm(passage) → EpisodicLlmResult`(build_prompt + `adapter_.extract` + 解析数组 + 逐事件抽 raw 字段 + 完整性过滤 + 密集 seq + 纯计算 `normalize_theme`/`canonicalize_object`;零 DB 无 `TransactionGuard`)与 `persist(engram_ref, tenant, agent_self, now, const EpisodicLlmResult&) → EpisodicExtractionResult`(`TransactionGuard` + `resolve_name` + `writer.write` + `ep_store.upsert` + commit)。`extract(...)` 保留为内联 `persist(…, extract_llm(passage))`(单一语义源)。Host `remember_extract`(锁外)加 episodic `extract_llm`;`remember_commit`(锁内)把 episodic 从 `.extract` 改 `.persist`(纯 DB)。

**Tech Stack:** C++20 内核(`src/` + `include/starling/`)、pybind11 绑定(`bindings/python/`)、Python host(`python/starling/`)、SQLite 单写者、gtest(ctest)、pytest。

## Global Constraints

- 核心一律 C++ 内核(`src/` + `include/starling/`);Python 层只适配;prompt 等配置数据单一源在 C++/host,绑定层禁算法/状态机。
- 行为中立:statement_ids 顺序 belief+episodic+gf 不变;`created_at` 取 `prepared.created_at_iso8601`;best-effort(LLM 失败/空数组零写入不抛);`span_key`/`chunk_index`(=seq)/`source_hash` 计算不变。
- 写后/订阅者路径用 SAVEPOINT 不用 BEGIN;单写者 SQLite。
- clang-tidy CI-only(本地跑不了):新绑定 opaque py::class_ 需 `// NOLINTNEXTLINE(bugprone-unused-raii)`;新方法/lambda 参数避 by-value(用 `const T&`);标识符 ≥3 字符;aggregate 用 designated init;restructure 触碰的 terse 名会被重新 lint。见记忆 `clang-tidy-ci-only-gate-gotchas`。
- 构建:`export PATH="$PWD/.venv/bin:$PATH"` 后 `python scripts/configure_build.py --build --python-editable`(build dir `build-macos`);改 C++/绑定后**必须** `--python-editable` 重装 `_core`。pytest 一律 `.venv/bin/python -m pytest tests/python`。提交门:全量 ctest + pytest 绿。
- git 显式路径 `git add`(禁 `.` / `-A`);不用 `--no-verify`/`--amend`;commit 尾 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- NEVER merge:PR + CI 绿 + 用户明确合并。

---

## File Structure

| 文件 | 责任 | 改动 |
|---|---|---|
| `include/starling/extractor/episodic_extractor.hpp` | EpisodicExtractor 接口 | 加 `ParsedEpisodicEvent` + `EpisodicLlmResult` 结构;加 `extract_llm`/`persist` 方法声明(保留 `extract`) |
| `src/extractor/episodic_extractor.cpp` | 实现 | `extract` 拆成 `extract_llm`(锁外)+ `persist`(锁内),`extract` 内联为二者 |
| `tests/cpp/test_episodic_phases.cpp` | C++ parity 测试(新) | 分相 ≡ 单体逐字段;`extract_llm` 零 DB |
| `tests/cpp/CMakeLists.txt` | ctest 注册 | 加 `test_episodic_phases` 条目(照 `test_extractor_phases`) |
| `bindings/python/bind_06_extractor.cpp` | pybind | 加 `EpisodicLlmResult` opaque handle + `extract_llm`/`persist` 方法绑定 |
| `python/starling/_memory_core.py` | host 三相编排 | `remember_extract` 加 episodic `extract_llm`(锁外);`remember_commit` episodic 改 `.persist`(锁内) |
| `tests/python/test_remember_lock_release.py` | 锁纪律测试 | 加回归守卫:高频探测 tick 全程无锁内 LLM 窗口 |
| `tests/python/test_extraction_config_wiring.py` | prompt/policy wiring spy | **必修(外部视角 P1)**:`FakeEpisodic` spy 加 `extract_llm`/`persist`(host 不再调 `.extract`),否则 5 个 wiring 测试经 `remember()` → `FakeEpisodic.extract_llm` → AttributeError |

依赖序线性:Task 1(C++)→ Task 2(绑定,依赖 Task 1 的结构/方法)→ Task 3(host,依赖 Task 2 的绑定)。

---

## Task 1: C++ 拆分 EpisodicExtractor.extract → extract_llm + persist

**Files:**
- Modify: `include/starling/extractor/episodic_extractor.hpp`
- Modify: `src/extractor/episodic_extractor.cpp`
- Create: `tests/cpp/test_episodic_phases.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Interfaces:**
- Consumes: 既有 `EpisodicExtractor` 私有成员 `conn_` / `adapter_` / `store_adapter_` / `prompt_template_`;`ExtractedStatement`、`StatementWriter`、`store::EpisodicEventStore`、`schema::normalize_theme`/`canonicalize_object`、`cognizer::resolve_or_register_cognizer`、`compute_extraction_span_key`(均已 include)。
- Produces:
  - `struct ParsedEpisodicEvent { long long seq; std::string actor, action, object_value, canonical_object_hash, location, event_time; std::vector<std::string> participants; };`
  - `struct EpisodicLlmResult { bool ok = false; std::vector<ParsedEpisodicEvent> events; };`
  - `EpisodicLlmResult EpisodicExtractor::extract_llm(std::string_view passage);`
  - `EpisodicExtractionResult EpisodicExtractor::persist(std::string_view engram_ref, std::string_view tenant, std::string_view agent_self, std::string_view now, const EpisodicLlmResult& llm_result);`
  - `extract(...)` 签名不变,内联为 `persist(engram_ref, tenant, agent_self, now, extract_llm(passage))`。

- [ ] **Step 1: 写 C++ parity 测试(先失败)**

Create `tests/cpp/test_episodic_phases.cpp`(镜像 `tests/cpp/test_extractor_phases.cpp` 的骨架):

```cpp
// test_episodic_phases.cpp — EpisodicExtractor extract_llm/persist 拆分(option B 收尾)。
// 钉:extract_llm→persist ≡ 单体 extract()(event_statement_ids + statements/
// episodic_events 逐行);extract_llm 零 DB(autocommit==1、零写)。零网络(FakeLLM)。
#include "starling/extractor/episodic_extractor.hpp"

#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <memory>
#include <string>
#include <vector>

namespace starling::extractor {
namespace {

// 两事件叙事:actor/action/theme 齐全 + location/time/participants。
constexpr const char* kEpisodicJson =
    R"JSON([{"actor":"Sally","action":"put","theme":"ball","location":"basket","time":"2026-05-23T10:00:00Z","participants":["Anne"]},)JSON"
    R"JSON({"actor":"Anne","action":"move","theme":"ball","location":"box","participants":[]}])JSON";

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

void seed_engram(persistence::Connection& conn) {
    sqlite3_exec(conn.raw(),
        "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
        "ingest_mode,privacy_class,retention_mode,refcount,payload_inline,created_at)"
        " VALUES('engram-1','default','hash-1','user_input','store','whole_record',"
        "'internal','audit_retain',0,X'','2026-05-23T10:00:00Z')",
        nullptr, nullptr, nullptr);
}

int row_count(persistence::Connection& conn, const std::string& table,
              const std::string& where = "1=1") {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(conn.raw(),
        ("SELECT COUNT(*) FROM " + table + " WHERE " + where).c_str(),
        -1, &raw, nullptr), SQLITE_OK);
    persistence::StmtHandle h(raw);
    sqlite3_step(h.get());
    return sqlite3_column_int(h.get(), 0);
}

std::vector<std::string> dump_rows(persistence::Connection& conn, const std::string& sql) {
    std::vector<std::string> out;
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr), SQLITE_OK);
    persistence::StmtHandle h(raw);
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        std::string row;
        for (int c = 0; c < sqlite3_column_count(h.get()); ++c) {
            if (c) row.push_back('|');
            const unsigned char* t = sqlite3_column_text(h.get(), c);
            row += t ? reinterpret_cast<const char*>(t) : "<null>";
        }
        out.push_back(row);
    }
    return out;
}

}  // namespace

TEST(EpisodicPhases, PhasedEqualsMonolith) {
    auto ma = make_adapter(); seed_engram(ma->connection());
    FakeLLMAdapter mllm; mllm.set_default_response(LLMResponse{.raw_xml = kEpisodicJson, .ok = true});
    EpisodicExtractor mex(ma->connection(), mllm);
    const auto mono = mex.extract("passage", "engram-1", "default", "cog-self",
                                  "2026-05-23T10:00:00Z");

    auto pa = make_adapter(); seed_engram(pa->connection());
    FakeLLMAdapter pllm; pllm.set_default_response(LLMResponse{.raw_xml = kEpisodicJson, .ok = true});
    EpisodicExtractor pex(pa->connection(), pllm);
    const auto llm = pex.extract_llm("passage");
    EXPECT_TRUE(llm.ok);
    EXPECT_EQ(llm.events.size(), 2u);
    EXPECT_EQ(sqlite3_get_autocommit(pa->connection().raw()), 1);   // extract_llm 无开事务
    EXPECT_EQ(row_count(pa->connection(), "statements"), 0);         // extract_llm 零写
    const auto phased = pex.persist("engram-1", "default", "cog-self",
                                    "2026-05-23T10:00:00Z", llm);

    EXPECT_EQ(mono.event_statement_ids.size(), phased.event_statement_ids.size());
    EXPECT_EQ(row_count(ma->connection(), "statements"),
              row_count(pa->connection(), "statements"));
    EXPECT_EQ(row_count(ma->connection(), "episodic_events"),
              row_count(pa->connection(), "episodic_events"));
    // 行级值 parity:语句内容(subject/predicate/object/holder)+ episodic_events
    // 扩展行(seq/location/participants/action)逐行等值,而非仅计数。
    EXPECT_EQ(dump_rows(ma->connection(),
                  "SELECT subject_id,predicate,canonical_object_hash,holder_id,modality "
                  "FROM statements ORDER BY predicate,canonical_object_hash"),
              dump_rows(pa->connection(),
                  "SELECT subject_id,predicate,canonical_object_hash,holder_id,modality "
                  "FROM statements ORDER BY predicate,canonical_object_hash"));
    EXPECT_EQ(dump_rows(ma->connection(),
                  "SELECT seq,location,participants_json,action_raw "
                  "FROM episodic_events ORDER BY seq"),
              dump_rows(pa->connection(),
                  "SELECT seq,location,participants_json,action_raw "
                  "FROM episodic_events ORDER BY seq"));
}

TEST(EpisodicPhases, LlmFailNoTxNoWrite) {
    // 适配器无响应 → ok=false、events 空;persist 不开事务、零写(镜像单体 early-return)。
    auto pa = make_adapter(); seed_engram(pa->connection());
    FakeLLMAdapter pllm;                        // no response → resp.ok=false
    EpisodicExtractor pex(pa->connection(), pllm);
    const auto llm = pex.extract_llm("passage");
    EXPECT_FALSE(llm.ok);
    EXPECT_TRUE(llm.events.empty());
    const auto phased = pex.persist("engram-1", "default", "cog-self",
                                    "2026-05-23T10:00:00Z", llm);
    EXPECT_TRUE(phased.event_statement_ids.empty());
    EXPECT_EQ(sqlite3_get_autocommit(pa->connection().raw()), 1);   // persist 未开事务
    EXPECT_EQ(row_count(pa->connection(), "statements"), 0);
}

TEST(EpisodicPhases, LlmEmptyEventsOkOpensEmptyTx) {
    // 加固(codex P2):非空合法数组、但每个元素 incomplete(缺 actor/action/theme)
    // → extract_llm 置 ok=true、events 空。persist 镜像单体:仍开 TransactionGuard、
    // 提交空事务、零写。钉死 ok 语义开关(防未来给 persist 加 `if events.empty(): return`
    // 绕过空 tx)。行为无可观测差异,但 ok 是本次拆分唯一新增语义,一个钉测锁死它。
    auto pa = make_adapter(); seed_engram(pa->connection());
    FakeLLMAdapter pllm;
    // 合法 JSON 数组,元素缺 action/theme → 完整性过滤全 skip → events 空但 ok=true。
    pllm.set_default_response(LLMResponse{
        .raw_xml = R"JSON([{"actor":"Sally"}])JSON", .ok = true});
    EpisodicExtractor pex(pa->connection(), pllm);
    const auto llm = pex.extract_llm("passage");
    EXPECT_TRUE(llm.ok);                            // 非空合法数组 → ok=true
    EXPECT_TRUE(llm.events.empty());                // 全 incomplete → 零事件
    const auto phased = pex.persist("engram-1", "default", "cog-self",
                                    "2026-05-23T10:00:00Z", llm);
    EXPECT_TRUE(phased.event_statement_ids.empty());
    EXPECT_EQ(sqlite3_get_autocommit(pa->connection().raw()), 1);   // 空 tx 已 commit(不悬开)
    EXPECT_EQ(row_count(pa->connection(), "statements"), 0);        // 零写
    EXPECT_EQ(row_count(pa->connection(), "episodic_events"), 0);
}

}  // namespace starling::extractor
```

- [ ] **Step 2: 注册 ctest 条目**

在 `tests/cpp/CMakeLists.txt` 里找 `test_extractor_phases` 的注册方式(`grep -n test_extractor_phases tests/cpp/CMakeLists.txt`),照同样方式加 `test_episodic_phases`(同一 add_executable/target_link_libraries/gtest_discover_tests 或 list 模式)。若是 glob 模式则无需手动加。

- [ ] **Step 3: 构建 → 确认失败(方法未定义)**

Run: `export PATH="$PWD/.venv/bin:$PATH" && python scripts/configure_build.py --build 2>&1 | tail -20`
Expected: 编译失败——`extract_llm` / `persist` / `EpisodicLlmResult` 未声明。这是 RED。

- [ ] **Step 4: 改头文件——加结构 + 方法声明**

在 `include/starling/extractor/episodic_extractor.hpp`,把 `EpisodicExtractionResult` 结构之后、`class EpisodicExtractor` 之前插入两个结构:

```cpp
// 相①(extract_llm)产物:解析好、待落库的单个事件。actor/participants 仍是 raw
// surface —— cognizer 名解析(resolve_name)会写库,留到 persist(锁内)。
struct ParsedEpisodicEvent {
    long long seq = 0;                       // 1-based,密集于完整事件
    std::string actor;                       // raw surface(persist 里 resolve_name)
    std::string action;
    std::string object_value;                // normalize_theme(theme)(M8 entity-kind)
    std::string canonical_object_hash;       // canonicalize_object(object_value)
    std::string location;                    // "" → episodic_events NULL
    std::string event_time;                  // "" → NULL
    std::vector<std::string> participants;   // raw surfaces(persist 里逐个 resolve_name)
};

// 相① LLM+parse 输出容器,零 DB。ok = 适配器 ok 且解析出非空合法数组
// (决定 persist 是否开事务:与单体一致——非空合法数组即使全 incomplete 也开事务)。
struct EpisodicLlmResult {
    bool ok = false;
    std::vector<ParsedEpisodicEvent> events;
};
```

在 `class EpisodicExtractor` 的 `public:` 段,`extract(...)` 声明之后加两方法声明:

```cpp
    // 相①(锁外,零 DB 无 TransactionGuard):build_prompt + LLM + 解析数组 + 逐事件
    // 抽 raw 字段 + 完整性过滤 + 密集 seq + 纯计算 normalize_theme/canonicalize_object。
    // resp 失败 / 无数组 / 空数组 → ok=false、events 空。
    EpisodicLlmResult extract_llm(std::string_view passage);

    // 相②(锁内):!llm_result.ok → 零写返回(不开事务,镜像单体 early-return)。否则开
    // TransactionGuard,逐事件 resolve_name(actor+participants) → writer.write →
    // ep_store.upsert(best-effort),commit。返回 event_statement_ids(seq 升序)。
    EpisodicExtractionResult persist(
        std::string_view engram_ref,
        std::string_view tenant,
        std::string_view agent_self,
        std::string_view now,
        const EpisodicLlmResult& llm_result);
```

- [ ] **Step 5: 改实现——`extract` 拆成 `extract_llm` + `persist` + 内联 `extract`**

在 `src/extractor/episodic_extractor.cpp`,把现有 `EpisodicExtractor::extract`(整个 77-216 行的函数体)替换为下面三个函数(`build_prompt` 与匿名命名空间 helper `extract_array`/`participants_json` 不动):

```cpp
EpisodicLlmResult EpisodicExtractor::extract_llm(std::string_view passage) {
    EpisodicLlmResult out;

    const std::string prompt_body = build_prompt(passage);
    const std::string prompt_input_hash = crypto::sha256_hex(prompt_body);
    const LLMResponse resp = adapter_.extract(prompt_body, prompt_input_hash);
    if (!resp.ok) return out;  // best-effort：适配器失败即 ok=false、零事件。

    const std::string_view arr_text = extract_array(resp.raw_xml);
    if (arr_text.empty()) return out;
    nlohmann::json arr;
    try {
        arr = nlohmann::json::parse(arr_text);
    } catch (const std::exception&) {
        return out;  // 解析失败。
    }
    if (!arr.is_array() || arr.empty()) return out;

    out.ok = true;  // 非空合法数组:persist 将开事务(即使下面全 incomplete)。

    long long seq = 0;
    for (const auto& el : arr) {
        if (!el.is_object()) continue;  // lenient: skip non-objects.
        std::string actor;
        if (el.contains("actor") && el["actor"].is_string()) actor = el["actor"].get<std::string>();
        std::string action;
        if (el.contains("action") && el["action"].is_string()) action = el["action"].get<std::string>();
        std::string theme;
        if (el.contains("theme") && el["theme"].is_string()) theme = el["theme"].get<std::string>();
        if (actor.empty() || action.empty() || theme.empty()) {
            continue;  // lenient: skip incomplete event(保持 seq 密集于写入)。
        }
        ++seq;

        ParsedEpisodicEvent event;
        event.seq    = seq;
        event.actor  = actor;   // raw surface —— resolve_name 在 persist(要写库)。
        event.action = action;
        event.object_value = schema::normalize_theme(theme);  // M8: entity-kind theme
        const schema::CanonicalResult cr =
            schema::canonicalize_object(schema::CanonicalInput{event.object_value});
        event.canonical_object_hash = cr.sha256_hex;
        if (el.contains("location") && el["location"].is_string()) {
            event.location = el["location"].get<std::string>();
        }
        if (el.contains("time") && el["time"].is_string()) {
            event.event_time = el["time"].get<std::string>();
        }
        if (el.contains("participants") && el["participants"].is_array()) {
            for (const auto& part : el["participants"]) {
                if (part.is_string()) event.participants.push_back(part.get<std::string>());  // raw
            }
        }
        out.events.push_back(std::move(event));
    }
    return out;
}

EpisodicExtractionResult EpisodicExtractor::persist(
        std::string_view engram_ref,
        std::string_view tenant,
        std::string_view agent_self,
        std::string_view now,
        const EpisodicLlmResult& llm_result) {

    EpisodicExtractionResult result;
    if (!llm_result.ok) {
        return result;  // 镜像单体 early-return:无合法数组 → 不开事务、零写。
    }

    persistence::TransactionGuard tx(conn_);
    StatementWriter writer(conn_);
    store::EpisodicEventStore ep_store(conn_);

    std::optional<cognizer::CognizerHub> hub;
    if (store_adapter_ != nullptr) hub.emplace(*store_adapter_);
    const auto resolve_name = [&](const std::string& surface) -> std::string {
        if (!hub) return surface;
        return cognizer::resolve_or_register_cognizer(*hub, tenant, surface);
    };

    for (const auto& event : llm_result.events) {
        // resolve actor + 每个 participant(CognizerHub register-on-miss 写本事务)。
        const std::string actor = resolve_name(event.actor);
        std::vector<std::string> participants;
        participants.reserve(event.participants.size());
        for (const auto& part : event.participants) participants.push_back(resolve_name(part));

        ExtractedStatement stmt;
        stmt.holder_id          = std::string(agent_self);
        stmt.holder_tenant_id   = std::string(tenant);
        stmt.holder_perspective = schema::Perspective::FIRST_PERSON;
        stmt.subject_kind       = "cognizer";
        stmt.subject_id         = actor;
        stmt.predicate          = event.action;
        stmt.object_kind        = "entity";
        stmt.object_value       = event.object_value;            // 相①已 normalize
        stmt.canonical_object_hash = event.canonical_object_hash; // 相①已算
        stmt.modality    = schema::Modality::OCCURRED;
        stmt.polarity    = schema::Polarity::POS;
        stmt.confidence  = 0.9;  // 用户输入的直接事件叙述,过 validator 的 [0.3,1.0]。
        stmt.observed_at = std::string(now);
        if (!event.event_time.empty()) stmt.event_time_start = event.event_time;
        stmt.provenance    = schema::StatementProvenance::USER_INPUT;
        stmt.review_status = schema::ReviewStatus::APPROVED;
        // chunk_index = seq:让每个事件的 extraction_span_key 互不相同。
        stmt.chunk_index = static_cast<std::int32_t>(event.seq);
        stmt.source_hash = "episodic-" + std::to_string(event.seq);
        stmt.perceived_by = {std::string(agent_self)};

        const std::string span_key = compute_extraction_span_key(
            engram_ref, stmt.chunk_index, stmt.predicate, stmt.canonical_object_hash);
        const auto outcome = writer.write(stmt, engram_ref, span_key,
                                          /*causation_parent_event_id=*/std::nullopt);
        std::string stmt_id;
        if (std::holds_alternative<StatementWriteAccepted>(outcome)) {
            stmt_id = std::get<StatementWriteAccepted>(outcome).stmt_id;
        } else {
            stmt_id = std::get<StatementWriteChunkDuplicate>(outcome).stmt_id;
        }
        result.event_statement_ids.push_back(stmt_id);

        // Best-effort episodic_events 扩展行:写在同一事务内,失败不回滚语句。
        try {
            store::EpisodicEventRow row;
            row.statement_id      = stmt_id;
            row.tenant_id         = std::string(tenant);
            row.seq               = event.seq;
            row.event_time        = event.event_time;   // "" → NULL
            row.location          = event.location;      // "" → NULL
            row.participants_json = participants_json(participants);
            row.action_raw        = event.action;
            ep_store.upsert(row);
        } catch (const std::exception&) {
            // 扩展行失败容忍:语句已写入本事务,不应因扩展失败而整体回滚。
        }
    }

    tx.commit();
    return result;
}

EpisodicExtractionResult EpisodicExtractor::extract(
        std::string_view passage,
        std::string_view engram_ref,
        std::string_view tenant,
        std::string_view agent_self,
        std::string_view now) {
    // 单体 = 两相内联(单一语义源;host 分相调用与此逐字段等价,见 test_episodic_phases）。
    return persist(engram_ref, tenant, agent_self, now, extract_llm(passage));
}
```

- [ ] **Step 6: 构建 + 跑 parity 测试 → 绿**

Run:
```bash
export PATH="$PWD/.venv/bin:$PATH"
python scripts/configure_build.py --build 2>&1 | tail -5
ctest --test-dir build-macos -R EpisodicPhases --output-on-failure 2>&1 | tail -20
```
Expected: `PhasedEqualsMonolith` + `LlmFailNoTxNoWrite` PASS。

- [ ] **Step 7: 全量 ctest 无回归**

Run: `ctest --test-dir build-macos --output-on-failure 2>&1 | tail -15`
Expected: 全绿(既有 episodic/remember 测试不回归——`extract` 行为逐字段不变)。

- [ ] **Step 8: Commit**

```bash
git add include/starling/extractor/episodic_extractor.hpp src/extractor/episodic_extractor.cpp tests/cpp/test_episodic_phases.cpp tests/cpp/CMakeLists.txt
git commit -m "feat(episodic): split extract into extract_llm(lock-free)+persist(lock-held)

方案2 option B 收尾第一步(C++)。EpisodicExtractor.extract 拆成 extract_llm
(纯 LLM+parse,零 DB 无 TransactionGuard)+ persist(事件落库,锁内);extract
内联为二者。parity 测试钉分相 ≡ 单体逐字段 + extract_llm 零 DB。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: pybind 绑定 extract_llm / persist + EpisodicLlmResult

**Files:**
- Modify: `bindings/python/bind_06_extractor.cpp`

**Interfaces:**
- Consumes: Task 1 的 `EpisodicLlmResult`、`EpisodicExtractor::extract_llm`/`persist`。
- Produces: Python `_core.EpisodicLlmResult`(opaque handle);`EpisodicExtractor.extract_llm(passage) -> EpisodicLlmResult`;`EpisodicExtractor.persist(engram_ref, tenant, agent_self, now, llm_result) -> list[str]`。

- [ ] **Step 1: 注册 EpisodicLlmResult opaque handle**

在 `bind_06_extractor.cpp` 的 `// ----- sub-project A phase 5: EpisodicExtractor` 注释(现 266 行)**之前**插入(须在 EpisodicExtractor 的 `.def("persist")` 用到该类型之前注册):

```cpp
    // ----- option B 收尾:EpisodicLlmResult(相① extract_llm 产物,opaque handle) -----
    // 无方法 opaque py::class_(Python 只持有、原样回传给 persist)→ 触 bugprone-unused-raii,
    // 照 belief ExtractionLlmResult 加 NOLINT。
    // NOLINTNEXTLINE(bugprone-unused-raii)
    py::class_<starling::extractor::EpisodicLlmResult>(m, "EpisodicLlmResult");
```

- [ ] **Step 2: 加 extract_llm / persist 方法绑定**

在 `bind_06_extractor.cpp` 的 `EpisodicExtractor` py::class_ 链上(现有 `.def("extract", …)` 之后、分号之前)追加两个 `.def`:

```cpp
        .def("extract_llm",
             [](starling::extractor::EpisodicExtractor& self, const std::string& passage) {
                 // 相①:LLM 网络调用期间释放 GIL(照 .extract / Extractor.run)。
                 py::gil_scoped_release release;
                 return self.extract_llm(passage);
             },
             py::arg("passage"))
        .def("persist",
             [](starling::extractor::EpisodicExtractor& self,
                const std::string& engram_ref, const std::string& tenant,
                const std::string& agent_self, const std::string& now,
                const starling::extractor::EpisodicLlmResult& llm_result) {
                 // 相②:纯 DB(快),返回本次写入的 OCCURRED 语句 id 列表。
                 // DB 写期间释放 GIL(对齐 belief memory_remember_commit / .extract 范式:
                 // 让无关只读 Python 线程在这几 ms 内不被阻塞;persist 短、无并发 conn 访问)。
                 py::gil_scoped_release release;
                 const auto r = self.persist(engram_ref, tenant, agent_self, now, llm_result);
                 return r.event_statement_ids;
             },
             py::arg("engram_ref"), py::arg("tenant"), py::arg("agent_self"),
             py::arg("now"), py::arg("llm_result"))
```

注意:`persist` 的 lambda 参数 `llm_result` 用 `const EpisodicLlmResult&`(非 by-value),避 `performance-unnecessary-value-param`。

- [ ] **Step 3: 重装 _core**

Run: `export PATH="$PWD/.venv/bin:$PATH" && python scripts/configure_build.py --build --python-editable 2>&1 | tail -5`
Expected: 构建 + 重装 `_core` 成功。

- [ ] **Step 4: 绑定 callability 冒烟**

Run:
```bash
export PATH="$PWD/.venv/bin:$PATH"
.venv/bin/python -c "
from starling import _core
assert hasattr(_core, 'EpisodicLlmResult'), 'EpisodicLlmResult 未注册'
e = _core.EpisodicExtractor
assert 'extract_llm' in dir(e) and 'persist' in dir(e), 'extract_llm/persist 未绑定'
llm = _core.FakeLLMAdapter(); llm.set_default_response('[]', True, '')
print('OK: EpisodicLlmResult + extract_llm + persist 绑定就绪')
"
```
Expected: 打印 OK(类型注册 + 方法存在)。

- [ ] **Step 5: 全量 pytest 无回归**

Run: `.venv/bin/python -m pytest tests/python -q 2>&1 | tail -5`
Expected: 全绿(新绑定不破坏既有;host 仍走 `.extract`,行为不变)。

- [ ] **Step 6: Commit**

```bash
git add bindings/python/bind_06_extractor.cpp
git commit -m "feat(episodic): bind extract_llm/persist + EpisodicLlmResult handle

option B 收尾第二步(绑定)。EpisodicLlmResult opaque handle(NOLINT unused-raii);
extract_llm 绑定 GIL 释放(LLM 网络),persist 绑定纯 DB、const-ref llm_result。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: host 三相编排 —— episodic LLM 出锁 + 锁纪律回归守卫

**Files:**
- Modify: `python/starling/_memory_core.py`(`remember_extract` + `remember_commit`)
- Modify: `tests/python/test_remember_lock_release.py`(加回归守卫)

**Interfaces:**
- Consumes: Task 2 的 `_core.EpisodicExtractor(...).extract_llm(text)` / `.persist(engram_ref=…, tenant=…, agent_self=…, now=…, llm_result=…)`;既有 `self.conn`、`self.rt.adapter`、`self._extraction.episodic_prompt`、`self.tenant`。
- Produces: `remember_extract` 返回 dict 增 `"episodic_llm"` 键;`remember_commit` 用 `.persist` 落 episodic(纯 DB)。`MemoryCore.remember`(单体)与 `Memory.remember` 复用二者,自动覆盖。

- [ ] **Step 0: 更新 `test_extraction_config_wiring.py` 的 `FakeEpisodic` spy(P1 必修——否则 Step 6 必 RED)**

`tests/python/test_extraction_config_wiring.py` 的 `FakeEpisodic` spy(现 30-35 行)只实现 `.extract`;Task 3 把 host 改成调 `.extract_llm`/`.persist` 后,5 个经 `mem._core.remember("hi")` 的测试会撞 `AttributeError`(host 调 `FakeEpisodic(...).extract_llm(...)`)。先把 spy 的 `.extract` 换成新两相方法,并更新 docstring 那句「EpisodicExtractor spy unchanged」。

把 `class FakeEpisodic` 块(现 30-35 行)替换为:

```python
    class FakeEpisodic:
        def __init__(self, conn, llm, adapter, prompt):
            captured["episodic"] = prompt

        def extract_llm(self, passage):
            return object()   # opaque placeholder; only re-forwarded to persist below

        def persist(self, **kw):
            return []
```

并把 `_install_spies` docstring 末句 `EpisodicExtractor spy unchanged.` 改为 `EpisodicExtractor spy now exposes extract_llm/persist (option B: episodic LLM out of lock).`

排序说明:spy 删掉 `.extract`、换成 `.extract_llm`/`.persist`,与 Step 3/4 的 host 改动是**同一逻辑单元**(旧 host 调 `.extract`、新 host 调新两相——两者不能中间态共存),故同一提交落、wiring 测试并进 Step 6 全量 pytest 一起验绿。本 Step 只是先把 spy 编辑做掉,不单独跑。

- [ ] **Step 1: 写锁纪律回归守卫(先失败)**

在 `tests/python/test_remember_lock_release.py` 末尾追加(顶部已 `import threading, time`):

```python
def test_tick_never_blocks_during_remember(tmp_path):
    """option B 收尾回归守卫:episodic LLM 出锁后,remember 全程无锁内 LLM 窗口。
    高频探测并发 tick,最大阻塞必 <0.4s。拆锁前 episodic 的 ~D LLM 在 commit 锁内 →
    某次 tick 会阻塞 ≈D(此测在旧 host 上 RED)。"""
    eng = _engine(tmp_path)                       # FakeLLM set_delay_ms(700)
    done = threading.Event()

    def run():
        eng.remember("Sally put the ball in the basket", holder="cog-self")
        done.set()

    turn = threading.Thread(target=run)
    turn.start()
    time.sleep(0.05)                              # 让 remember 进入 extract 段
    max_block = 0.0
    now_iso = "2026-07-14T00:00:00Z"
    while not done.is_set():
        b0 = time.monotonic()
        eng.tick(now_iso)                         # 取同一 self._lock
        max_block = max(max_block, time.monotonic() - b0)
        time.sleep(0.01)
    turn.join(timeout=30)
    assert max_block < 0.4, (
        f"某次 tick 阻塞 {max_block:.2f}s —— 仍有锁内 LLM 窗口(episodic 未出锁)")
```

> **测法余量说明(eng-review P3):** `max_block` 括住整个 `eng.tick()`(取锁 +
> tick 自身 embed/pump/reconstruct 工作),非纯等锁计时。判别信号是 0.4s 阈值 vs
> 拆锁前 0.7s(`set_delay_ms(700)`)锁内窗口 → 0.3s 余量;拆锁后 tick 自身在此
> FakeLLM/stub-embedder 路径远 <0.4s。照既有 `test_tick_interleaves_during_extract`
> 同范式同阈值(稳定)。若重载 CI 出现假 RED(tick 自身某次 >0.4s),把
> `set_delay_ms(700)` 调到 `1500` 并阈值调到 `0.6` 拉大余量——信号(拆锁前锁内睡
> 满 delay)与阈值同比放大,判别力不变。

- [ ] **Step 2: 跑测试 → 确认失败(旧 host 仍锁内跑 episodic LLM)**

Run: `.venv/bin/python -m pytest tests/python/test_remember_lock_release.py::test_tick_never_blocks_during_remember -v 2>&1 | tail -15`
Expected: FAIL——`某次 tick 阻塞 0.7x s`(当前 `remember_commit` 在锁内跑 `episodic.extract` 的 700ms LLM)。这是 RED。

- [ ] **Step 3: 改 `remember_extract`——加 episodic extract_llm(锁外)**

在 `python/starling/_memory_core.py` 的 `remember_extract`(现 163-184 行),把 `should_extract=False` 的返回加 `episodic_llm` 键,并在 `return {"belief": belief, "gf": gf}` 前加 episodic 相①:

替换现有 `remember_extract` 函数体为:

```python
    def remember_extract(self, bundle: dict, llm=None) -> dict:
        """三相之二(锁外无事务):belief + general-fact + episodic 三条 LLM 抽取(纯网络)。
        should_extract=False(no_store/rejected)→ 空。llm 缺省 self.llm;DashboardEngine
        传本轮解析出的局部 adapter(避拆锁后全局 slot 竞态)。episodic LLM 就此出锁。"""
        prepared = bundle["prepared"]
        if not prepared.should_extract:
            return {"belief": None, "gf": None, "episodic_llm": None}
        extraction_llm = llm or self.llm
        if extraction_llm is None:   # #1:extract 真正用 llm 处兜底(直呼 extract 时)
            raise LLMNotConfigured("remember requires an llm adapter")
        holder_id = bundle["holder_id"]
        payload = bundle["text"].encode("utf-8")
        policy = _build_policy(self._extraction)
        belief = _core.memory_extract_llm(
            self.rt.adapter, extraction_llm, self._extraction.belief_prompt,
            holder_id=holder_id, payload=payload, policy=policy)
        # {self} 由 holder_id 填充,使事实 holder=self → 默认 recall 命中。
        gf_prompt = self._extraction.general_fact_prompt.replace("{self}", holder_id)
        gf = _core.memory_extract_llm(
            self.rt.adapter, extraction_llm, gf_prompt,
            holder_id=holder_id, payload=payload, policy=policy)
        # episodic 相①(锁外,option B 收尾):~20-50s LLM 出锁,与 belief+gf 并列。
        episodic = _core.EpisodicExtractor(
            self.conn, extraction_llm, self.rt.adapter,
            self._extraction.episodic_prompt)
        episodic_llm = episodic.extract_llm(bundle["text"])
        return {"belief": belief, "gf": gf, "episodic_llm": episodic_llm}
```

- [ ] **Step 4: 改 `remember_commit`——episodic 由 `.extract` 改 `.persist`(锁内纯 DB)**

在 `python/starling/_memory_core.py` 的 `remember_commit`,把「第二条:episodic」块(现 207-222 行)替换为:

```python
        # 第二条:episodic(叙事事件)。相② persist:LLM 已在锁外 extract_llm 跑完,
        # 此处纯 DB 落库(option B 收尾:episodic LLM 出锁)。次序 belief→episodic→
        # reconstruct→gf 不变;reconstruct 读 episodic_events 故须在 persist 之后。
        engram_ref = out.get("engram_ref") or ""
        if engram_ref:
            episodic = _core.EpisodicExtractor(
                self.conn, extraction_llm, self.rt.adapter,
                self._extraction.episodic_prompt)
            event_ids = episodic.persist(
                engram_ref=engram_ref, tenant=self.tenant,
                agent_self=holder_id, now=created_iso,
                llm_result=extracted["episodic_llm"])
            if event_ids:
                out["statement_ids"] = list(out.get("statement_ids", [])) + list(event_ids)
                try:
                    _core.PerceptionReconstructor(
                        self.conn, self.rt.adapter).reconstruct(tenant=self.tenant)
                except Exception:  # noqa: BLE001 — perception 是 best-effort;绝不失败 remember
                    pass
```

- [ ] **Step 5: 跑回归守卫 → 绿**

Run: `.venv/bin/python -m pytest tests/python/test_remember_lock_release.py -v 2>&1 | tail -15`
Expected: `test_tick_never_blocks_during_remember` PASS(episodic LLM 出锁,全程 tick <0.4s);既有 `test_tick_interleaves_during_extract` 等仍 PASS。

- [ ] **Step 6: 全量 pytest + ctest 无回归**

Run:
```bash
export PATH="$PWD/.venv/bin:$PATH"
.venv/bin/python -m pytest tests/python -q 2>&1 | tail -5
ctest --test-dir build-macos --output-on-failure 2>&1 | tail -8
```
Expected: 全绿(remember 端到端 belief+episodic+gf 逐字段不变;statement_ids 顺序不变)。

- [ ] **Step 7: Commit**

```bash
git add python/starling/_memory_core.py tests/python/test_remember_lock_release.py tests/python/test_extraction_config_wiring.py
git commit -m "feat(episodic): move episodic LLM out of the commit write-lock (option B done)

remember_extract 加 episodic extract_llm(锁外);remember_commit episodic 改
.persist(纯 DB,锁内)。episodic 的 ~20-50s LLM 出锁 → remember 写锁持有纯 DB。
锁纪律回归守卫:高频探测 tick 全程 <0.4s(拆锁前 RED)。次序 belief→episodic→
reconstruct→gf 不变。MemoryCore.remember 单体 + Memory.remember 自动覆盖。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage(逐 spec 节核):**
- spec ① 范围边界(只拆 episodic LLM;perception/pump/belief·gf persist 纯 DB 留锁内)→ Task 1 只改 EpisodicExtractor;Task 3 `remember_commit` 保留 reconstruct + gf persist 在锁内。✓
- spec ② C++ 拆分(extract_llm 锁外零 DB + persist 锁内 + 内联 extract + EpisodicLlmResult)→ Task 1 Step 4/5 + parity 测试断言 `autocommit==1`/零写。✓
- spec ③ host 编排(remember_extract 加 episodic LLM;remember_commit 改 persist;次序 belief→episodic→reconstruct→gf)→ Task 3 Step 3/4。✓
- spec ④ 行为中立(statement_ids 顺序;created_at=prepared;best-effort;span_key/chunk_index/source_hash 不变)→ persist 逐字段照搬原 extract 写路径;parity 测试逐行等值。✓
- spec 测试(C++ parity `test_episodic_phases` + 锁纪律回归 + before/after)→ Task 1 + Task 3。`max_block/D` before/after 佐证进 PR body。✓

**2. Placeholder scan:** 无 TBD/TODO;每步含完整代码 + 确切命令 + 期望。✓

**3. Type consistency:**
- `EpisodicLlmResult`(`bool ok` + `vector<ParsedEpisodicEvent> events`)在 Task 1 定义,Task 2 绑定,Task 3 通过 `extracted["episodic_llm"]` 传回 `persist`。✓
- `persist` 签名 `(engram_ref, tenant, agent_self, now, const EpisodicLlmResult&)` 三处一致(hpp 声明 / cpp 实现 / 绑定 py::arg / host 调用 kwargs)。✓
- `extract_llm(passage)` 单参一致(hpp / cpp / 绑定 / host `episodic.extract_llm(bundle["text"])`)。✓
- host `remember_extract` 返回三键 `{belief, gf, episodic_llm}`;`remember_commit` 读 `extracted["episodic_llm"]`——键名一致;`should_extract=False` 分支也回三键(shape 一致)。✓

**4. Eng-review 加固(外部视角 4 项,全折进):**
- [P1 必修] `test_extraction_config_wiring.py` 的 `FakeEpisodic` spy 只有 `.extract`,Task 3 改用 `.extract_llm`/`.persist` 后 5 个测试必 AttributeError → Task 3 Step 0b 更新 spy(加 `extract_llm`/`persist`、更新 docstring),同提交落、并进 Step 6 全量 pytest;File Structure 表 + Step 7 git add 已含该文件。✓
- [P2] 缺「非空数组、全 incomplete → ok=true、events 空、persist 开+提交空 tx」钉测 → Task 1 加 `LlmEmptyEventsOkOpensEmptyTx`(锁死 `ok` 语义,防未来给 persist 加 `if events.empty(): return` 绕过空 tx)。✓
- [P3] persist 绑定原未释 GIL,与 belief `memory_remember_commit` / `.extract` 范式不一致 → Task 2 Step 2 persist lambda 加 `py::gil_scoped_release`(DB 写期间不白占 GIL)。✓
- [P3] 锁测 `max_block` 括整个 tick 非纯等锁、0.4s 对 0.7s 仅 0.3s 余量 → Task 3 Step 1 加测法余量说明 + CI 假 RED 的放大调法(delay 700→1500、阈值 0.4→0.6)。✓

无遗漏。

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_found | 4 issues (1 P1 + 1 P2 + 2 P3), 0 critical gaps, all folded |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**Step 0 scope:** accepted as-is(7 文件、0 新类,方案2 忠实镜像;低于 8 文件/2 类阈值)。
**Architecture:** 无 issue(拆分范式镜像已发布 PR #54 的 `Extractor::extract_llm`/`persist`;锁内次序 belief→episodic→reconstruct→gf 保证 reconstruct 读 episodic_events 在其落库后)。
**Code Quality / Tests / Performance:** 外部视角(codex 超时→Claude 子代理亲读实现验)4 findings,全折进:P1 FakeEpisodic spy 漏更新(必 RED)、P2 空-tx 钉测、P3 persist GIL、P3 锁测余量。

**CODEX:** codex exec 5min 超时零输出(Clash TUN 掐 API 网络),照 skill 回退 Claude 子代理外部视角(fresh context、repo 读权,逐条亲验 parity)。
**VERDICT:** ENG CLEARED — ready to implement(4 findings 全折进计划,0 未决)。

NO UNRESOLVED DECISIONS
