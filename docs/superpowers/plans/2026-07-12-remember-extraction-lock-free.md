# remember extraction 出锁(方案2 / option B)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `remember` 的 belief + general-fact 两条 extraction LLM 调用移出引擎锁 + DB 事务(照 #51 converse 三相),消除摄入/tick 期间的 dashboard 卡死;episodic 单体保留在锁内(option B 残留)。

**Architecture:** `Extractor::run` 拆 `extract_llm`(纯 LLM+parse,零 DB/无 txn)+ `persist`(txn 写),`run` 内联二者=单一语义源。`memoryops` 三相 `remember_prepare`/`extract_llm`/`remember_commit`,`remember` 内联。host `MemoryCore` 编排三管线:prepare(engram 一次)→ extract(belief+gf LLM,锁外)→ commit(belief persist → **episodic 单体**残留 → gf persist)。`engine.remember` 三段落锁(照 `_converse_phased`)。

**Tech Stack:** C++20 内核(`src/`+`include/`)、pybind11 绑定(`bindings/python/`)、Python host(`python/starling/`)、SQLite 单写者、gtest(ctest)、pytest。

## Global Constraints

- **架构边界(硬)**:核心语义(算法/事务边界/状态机/管线编排)在 C++ 内核;Python 只做适配转发/签名归一。`extract_llm`/`persist`/三相原语都是 C++;`MemoryCore` 的 belief/episodic/gf 编排是既有 host 层(不外扩)。
- **单写者 SQLite**:`extract_llm` 段**既不持引擎锁、也不在 DB 事务内**(只释放锁而不移事务 = BEGIN 套 BEGIN 隐患)。prepare/commit 短段持 `_lock`。episodic 单体仍在 commit 锁内(残留,option B)。
- **行为等价(带一处已知时戳位移)**:`Extractor::run` 与 `memoryops::remember` 单体保留并内联三相;既有全部 extractor / memory_ops / converse / facade 测试不改照跑 = 首道回归网。落库**行内容/status/statements/latency_ms**、幂等、FAILED 语义、statement_ids 顺序(belief+episodic+gf)全不变。**唯一例外(#8,已裁定接受+文档化):** DB 写**时戳列**(`pipeline_run.started_at`、`extraction_attempt.created_at`、events)从「与 LLM 交错」位移到「persist 时刻聚簇」——因所有 DB 写现在都跟在 extract_llm 之后。已核实**无消费方**依赖这些时戳的铺开(`governance_pipeline_run` 是另表;dashboard 抽取时间派生自 `extraction_attempt.created_at`,B 的 latency 端点用 `latency_ms`=真 LLM 往返,extract_llm 里测得、persist 原样落)。故 parity 测试的时戳列不入等值比较键。
- **写门**:`remember_prepare` 首行 `require_write_admission`(fail-fast);`remember_commit` persist 前再校验一次(捕锁外 extract 期间转 DRAINING 的中途翻转)。
- **provider 局部解析**:`engine.remember` 拆锁后不得换全局 adapter slot(并发轮会读到错模型);解析为局部引用传入 extract/commit(照 `_resolve_chat`)。
- **构建/测试**:canonical `python scripts/configure_build.py --build --test`;改 C++/绑定后必须 `--python-editable` 重装 `_core`;pytest 一律 `.venv/bin/python -m pytest tests/python`;PATH 需 `export PATH="$PWD/.venv/bin:$PATH"`,build 目录 `build-macos`。clang-tidy CI-only(本地跑不了,新 C++ 按 by-construction 干净写)。
- **git**:显式路径 `git add`(禁 `.`/`-A`);不用 `--no-verify`/`--amend`;commit 尾 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- **NEVER merge**:PR + CI 绿 + 用户明确「合并」。

---

### Task 1: Extractor 拆 extract_llm + persist(run 内联)

**Files:**
- Modify: `include/starling/extractor/extractor.hpp`(加 `ExtractionLlmAttempt`/`ExtractionLlmResult` 结构 + `extract_llm`/`persist` 方法声明;加 `#include "starling/extractor/json_parser.hpp"`)
- Modify: `src/extractor/extractor.cpp:185-448`(把 `run` 拆成 `extract_llm` + `persist`,`run` 内联二者)
- Create: `tests/cpp/test_extractor_phases.cpp`
- Modify: `tests/cpp/CMakeLists.txt`(注册新测试)

**Interfaces:**
- Consumes: `LLMResponse`(llm_adapter.hpp)、`ParseResult`/`parse_extractor_json`(json_parser.hpp)、`ExtractionRunResult`(现存)。
- Produces:
  - `struct ExtractionLlmResult { std::string prompt_body; std::string prompt_input_hash; std::vector<ExtractionLlmAttempt> attempts; };`
  - `struct ExtractionLlmAttempt { int attempt; LLMResponse resp; bool parsed; ParseResult parse; bool terminal; };`
  - `ExtractionLlmResult Extractor::extract_llm(const std::vector<std::uint8_t>& payload_bytes, std::string_view holder_id, const ExistingRefMap& existing_ref_map);`
  - `ExtractionRunResult Extractor::persist(std::string_view engram_ref_id, std::string_view holder_id, std::string_view holder_tenant_id, std::string_view interlocutor, const ExtractionLlmResult& llm_result);`

- [ ] **Step 1: 写失败测试 `tests/cpp/test_extractor_phases.cpp`**

```cpp
// test_extractor_phases.cpp — Extractor extract_llm/persist 拆分(方案2 option B)。
// 钉:extract_llm→persist ≡ 单体 run()(status + 落库逐行);extract_llm 零 DB、
// 返回后 autocommit==1(无开事务)。零网络(FakeLLM)。
#include "starling/extractor/extractor.hpp"

#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <memory>
#include <vector>

namespace starling::extractor {
namespace {

constexpr const char* kSuccessJson =
    R"JSON([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}])JSON";

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

LLMResponse ok_json() { return LLMResponse{.raw_xml = kSuccessJson, .ok = true}; }

// #7(review 加固):比行值不只比行数——转录 bug 可能保留计数却改坏值。
// 返回按稳定序排的 "col|col|..." 行串,供两库逐行等值比较。
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

TEST(ExtractorPhases, PhasedEqualsMonolithSuccess) {
    auto ma = make_adapter(); seed_engram(ma->connection());
    FakeLLMAdapter mllm; mllm.set_default_response(ok_json());
    Extractor mex(ma->connection(), mllm);
    const auto mono = mex.run("engram-1", {1,2,3}, "cog-self", "default", {});

    auto pa = make_adapter(); seed_engram(pa->connection());
    FakeLLMAdapter pllm; pllm.set_default_response(ok_json());
    Extractor pex(pa->connection(), pllm);
    const auto llm = pex.extract_llm({1,2,3}, "cog-self", {});
    EXPECT_EQ(sqlite3_get_autocommit(pa->connection().raw()), 1);   // extract_llm 无开事务
    EXPECT_EQ(row_count(pa->connection(), "statements"), 0);         // extract_llm 零写
    EXPECT_EQ(row_count(pa->connection(), "pipeline_run"), 0);
    const auto phased = pex.persist("engram-1", "cog-self", "default", "", llm);

    EXPECT_EQ(mono.status, phased.status);
    EXPECT_EQ(mono.accepted_statement_ids.size(), phased.accepted_statement_ids.size());
    EXPECT_EQ(row_count(ma->connection(), "statements"),
              row_count(pa->connection(), "statements"));
    EXPECT_EQ(row_count(ma->connection(), "extraction_attempt", "status='success'"),
              row_count(pa->connection(), "extraction_attempt", "status='success'"));
    EXPECT_EQ(row_count(ma->connection(), "pipeline_run", "status='finished'"),
              row_count(pa->connection(), "pipeline_run", "status='finished'"));
    EXPECT_EQ(row_count(ma->connection(), "bus_events", "event_type='statement.written'"),
              row_count(pa->connection(), "bus_events", "event_type='statement.written'"));
    // #7:行级值 parity——语句内容 + attempt 行(status/error/tokens)逐行等值,
    // 而非仅计数。时戳列(created_at/started_at)不入比较键(#8:聚簇到 persist 时刻,
    // 两库各自的 wall-clock 本就不同)。
    EXPECT_EQ(dump_rows(ma->connection(),
                  "SELECT subject_id,predicate,canonical_object_hash,holder_id "
                  "FROM statements ORDER BY predicate,canonical_object_hash"),
              dump_rows(pa->connection(),
                  "SELECT subject_id,predicate,canonical_object_hash,holder_id "
                  "FROM statements ORDER BY predicate,canonical_object_hash"));
    EXPECT_EQ(dump_rows(ma->connection(),
                  "SELECT attempt_number,status,error,total_tokens "
                  "FROM extraction_attempt ORDER BY extraction_span_key,attempt_number"),
              dump_rows(pa->connection(),
                  "SELECT attempt_number,status,error,total_tokens "
                  "FROM extraction_attempt ORDER BY extraction_span_key,attempt_number"));
}

TEST(ExtractorPhases, PhasedEqualsMonolithAllFail) {
    auto ma = make_adapter(); seed_engram(ma->connection());
    FakeLLMAdapter mllm;                       // no response → ok=false
    Extractor mex(ma->connection(), mllm);
    const auto mono = mex.run("engram-1", {1,2,3}, "cog-self", "default", {});

    auto pa = make_adapter(); seed_engram(pa->connection());
    FakeLLMAdapter pllm;
    Extractor pex(pa->connection(), pllm);
    const auto llm = pex.extract_llm({1,2,3}, "cog-self", {});
    EXPECT_EQ(llm.attempts.size(), 3u);        // 3 retries collected, no terminal
    const auto phased = pex.persist("engram-1", "cog-self", "default", "", llm);

    EXPECT_EQ(mono.status, ExtractionRunResult::Status::FAILED);
    EXPECT_EQ(phased.status, ExtractionRunResult::Status::FAILED);
    EXPECT_EQ(row_count(pa->connection(), "extraction_attempt", "status='failed'"), 3);
    EXPECT_EQ(row_count(ma->connection(), "extraction_attempt", "status='failed'"),
              row_count(pa->connection(), "extraction_attempt", "status='failed'"));
    EXPECT_EQ(row_count(ma->connection(), "bus_events", "event_type='extraction.failed'"),
              row_count(pa->connection(), "bus_events", "event_type='extraction.failed'"));
    // #7:失败 attempt 的 (number,status,error) 逐行等值(转录 bug 可能改坏 error 文本却保计数)。
    EXPECT_EQ(dump_rows(ma->connection(),
                  "SELECT attempt_number,status,error FROM extraction_attempt "
                  "ORDER BY attempt_number"),
              dump_rows(pa->connection(),
                  "SELECT attempt_number,status,error FROM extraction_attempt "
                  "ORDER BY attempt_number"));
}

TEST(ExtractorPhases, NoopShortCircuitOnReRun) {
    // 同 engram persist 两次(重忆):第二次 noop 短路,statements 不增。
    auto pa = make_adapter(); seed_engram(pa->connection());
    FakeLLMAdapter pllm; pllm.set_default_response(ok_json());
    Extractor pex(pa->connection(), pllm);
    const auto llm1 = pex.extract_llm({1,2,3}, "cog-self", {});
    pex.persist("engram-1", "cog-self", "default", "", llm1);
    const int after1 = row_count(pa->connection(), "statements");
    const auto llm2 = pex.extract_llm({1,2,3}, "cog-self", {});
    const auto r2 = pex.persist("engram-1", "cog-self", "default", "", llm2);
    EXPECT_EQ(row_count(pa->connection(), "statements"), after1);   // 无新增
    EXPECT_EQ(r2.status, ExtractionRunResult::Status::SUCCESS);
    EXPECT_GE(row_count(pa->connection(), "extraction_attempt", "status='noop'"), 1);
}

}  // namespace starling::extractor
```

- [ ] **Step 2: 注册测试到 `tests/cpp/CMakeLists.txt`**

在 `add_executable(starling_tests ...)` 列表中 `test_extractor_orchestrator.cpp`(现:62)那一行**后**加一行:

```cmake
    test_extractor_phases.cpp
```

- [ ] **Step 3: 运行测试,确认编译失败**

```bash
export PATH="$PWD/.venv/bin:$PATH"
python scripts/configure_build.py --build 2>&1 | tail -20
```
Expected: 编译失败(`Extractor` 无 `extract_llm`/`persist` 成员、无 `ExtractionLlmResult`)。

- [ ] **Step 4: `extractor.hpp` 加结构体 + 方法声明**

`#include` 块加(现:3-7 之后):
```cpp
#include "starling/extractor/json_parser.hpp"
```

在 `struct ExtractionRunResult { ... };`(现:16-22)**之后**加:
```cpp
// extract_llm 产出的逐 attempt 记录(LLM + parse 段);persist() 重放它们写
// ledger/attempt/statement 行。此处无任何 DB 状态——重试决策(!resp.ok 或
// parse 有错才重试、parse 成功即止)纯由 LLM 响应决定,故 attempt 序列可无 DB
// 完整确定,persist 忠实重放。
struct ExtractionLlmAttempt {
    int         attempt = 0;       // 1-based
    LLMResponse resp;              // 该 attempt 的原始 LLM 响应
    bool        parsed = false;    // resp.ok 且跑过 parser
    ParseResult parse;             // 仅 parsed==true 有效
    bool        terminal = false;  // parse 成功 → 该 attempt 结束重试循环
};

struct ExtractionLlmResult {
    std::string                       prompt_body;
    std::string                       prompt_input_hash;
    std::vector<ExtractionLlmAttempt> attempts;
};
```

在 `run(...)` 声明(现:49-55)**之后**加两个方法声明:
```cpp
    // 方案2 拆分:run() = extract_llm() → persist()(单一语义源内联)。
    // extract_llm:跑重试循环只做 adapter_.extract + parse_extractor_json,零 DB、
    // 无 TransactionGuard——LLM 只吃 payload + existing_ref_map,不需 engram 在库。
    ExtractionLlmResult extract_llm(
        const std::vector<std::uint8_t>&        payload_bytes,
        std::string_view                        holder_id,
        const ExistingRefMap&                   existing_ref_map);

    // persist:开 TransactionGuard,重放 llm_result.attempts 写 ledger/attempt/
    // events + terminal attempt 的 statements。FAILED 仍 COMMIT attempt 行。
    ExtractionRunResult persist(
        std::string_view                        engram_ref_id,
        std::string_view                        holder_id,
        std::string_view                        holder_tenant_id,
        std::string_view                        interlocutor,
        const ExtractionLlmResult&              llm_result);
```

- [ ] **Step 5: `extractor.cpp` 实现 extract_llm + persist,run 内联**

把现 `ExtractionRunResult Extractor::run(...) { ... }`(现:185-448 整个函数体)**替换**为下面三个函数(`extract_llm` 是循环的 LLM 段、`persist` 是循环的 DB 段逐字节移自原 run、`run` 内联):

```cpp
ExtractionLlmResult Extractor::extract_llm(
        const std::vector<std::uint8_t>&  payload_bytes,
        std::string_view                  holder_id,
        const ExistingRefMap&             existing_ref_map) {
    ExtractionLlmResult out;
    out.prompt_body       = build_prompt(holder_id, payload_bytes, existing_ref_map);
    out.prompt_input_hash = compute_prompt_input_hash(out.prompt_body);

    // 重试循环只做 LLM + parse(零 DB)。retry 决策与单体 run 完全一致:
    // !resp.ok 或 parse 有错 → 收录并 continue;parse 成功 → terminal 并 break。
    for (int attempt = 1; attempt <= kMaxRetries; ++attempt) {
        ExtractionLlmAttempt rec;
        rec.attempt = attempt;
        rec.resp    = adapter_.extract(out.prompt_body, out.prompt_input_hash);
        if (!rec.resp.ok) {
            out.attempts.push_back(std::move(rec));
            continue;
        }
        rec.parse  = parse_extractor_json(rec.resp.raw_xml, existing_ref_map);
        rec.parsed = true;
        if (!rec.parse.errors.empty()) {
            out.attempts.push_back(std::move(rec));
            continue;
        }
        rec.terminal = true;
        out.attempts.push_back(std::move(rec));
        break;
    }
    return out;
}

ExtractionRunResult Extractor::persist(
        std::string_view                  engram_ref_id,
        std::string_view                  holder_id,
        std::string_view                  holder_tenant_id,
        std::string_view                  interlocutor,
        const ExtractionLlmResult&        llm_result) {

    ExtractionRunResult result;

    // 单事务(移自原 run):FAILED 仍 COMMIT(attempt 行 + events 持久化),
    // 异常 ROLLBACK(TransactionGuard)。所有 DB 写集中在 LLM 之后。
    starling::persistence::TransactionGuard tx(conn_);

    std::optional<starling::cognizer::CognizerHub> cog_hub;
    if (store_adapter_ != nullptr) cog_hub.emplace(*store_adapter_);

    PipelineLedger ledger(conn_);
    const std::string run_id = ledger.start_run(holder_tenant_id, engram_ref_id, "{}");
    const std::string run_started_event_id = emit_pipeline_event(
        conn_, "pipeline.run_started", holder_tenant_id, run_id, std::nullopt);
    result.run_id = run_id;

    const std::int32_t chunk_index = 0;  // M0.4: 1 chunk per Engram
    const std::string chunk_span_key = compute_extraction_span_key(
        engram_ref_id, chunk_index, "__chunk__", "__chunk__");

    bool any_accepted   = false;
    bool all_failed     = true;
    bool result_partial = false;

    for (const auto& rec : llm_result.attempts) {
        const int attempt = rec.attempt;
        const std::string attempt_suffix = "attempt=" + std::to_string(attempt);
        // cost 归属:每 attempt 只算一次,落到本轮写的第一行(移自原 run)。
        bool attempt_cost_used = false;
        auto take_cost = [&]() -> AttemptCost {
            if (attempt_cost_used) {
                return {};
            }
            attempt_cost_used = true;
            return {rec.resp.prompt_tokens, rec.resp.completion_tokens,
                    rec.resp.total_tokens, rec.resp.latency_ms};
        };
        if (!rec.resp.ok) {
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  ExtractionStatus::Failed,
                                  /*raw_output=*/{},
                                  rec.resp.error,
                                  take_cost());
            emit_extraction_event(conn_, "extraction.failed",
                                  holder_tenant_id, run_id, chunk_span_key,
                                  run_started_event_id, attempt_suffix);
            if (attempt < kMaxRetries) {
                emit_extraction_event(conn_, "extraction.retry_scheduled",
                                      holder_tenant_id, run_id, chunk_span_key,
                                      run_started_event_id, attempt_suffix);
            }
            continue;
        }

        if (!rec.parse.errors.empty()) {
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  ExtractionStatus::Failed,
                                  rec.resp.raw_xml,
                                  rec.parse.errors.front().kind,
                                  take_cost());
            emit_extraction_event(conn_, "extraction.failed",
                                  holder_tenant_id, run_id, chunk_span_key,
                                  run_started_event_id, attempt_suffix);
            if (attempt < kMaxRetries) {
                emit_extraction_event(conn_, "extraction.retry_scheduled",
                                      holder_tenant_id, run_id, chunk_span_key,
                                      run_started_event_id, attempt_suffix);
            }
            continue;
        }

        // Parse 成功。逐语句校验 + 写(移自原 run:283-421,parsed 用本 attempt 的拷贝)。
        ParseResult parsed = rec.parse;   // 可变拷贝:下面会改 statements
        StatementWriter writer(conn_);
        bool any_rejected_this_attempt   = false;
        bool wrote_anything_this_attempt = false;
        bool noop_short_circuited        = false;
        std::set<std::string> written_span_keys;
        for (auto& stmt : parsed.statements) {
            stmt.holder_tenant_id = std::string(holder_tenant_id);
            stmt.chunk_index      = chunk_index;
            if (stmt.source_hash.empty()) {
                stmt.source_hash = "chunk-" + std::to_string(chunk_index);
            }
            if (cog_hub && stmt.subject_kind == "cognizer" && !stmt.subject_id.empty()) {
                stmt.subject_id = starling::cognizer::resolve_or_register_cognizer(
                    *cog_hub, holder_tenant_id, stmt.subject_id);
            }
            if (policy_.attribute_first_order_mental_to_holder
                    && stmt.llm_nesting_depth == 0
                    && is_first_order_desire(stmt.modality, stmt.predicate)
                    && !stmt.subject_id.empty()
                    && stmt.subject_id != std::string(holder_id)) {
                stmt.holder_id = stmt.subject_id;
            } else {
                stmt.holder_id = std::string(holder_id);
            }
            if (!interlocutor.empty()) {
                std::vector<std::string> pair{std::string(holder_id), std::string(interlocutor)};
                std::sort(pair.begin(), pair.end());
                stmt.scope_parties = pair;
                if (stmt.perceived_by.empty()) stmt.perceived_by = pair;
            } else if (stmt.perceived_by.empty()) {
                stmt.perceived_by = {std::string(holder_id)};
            }
            const ValidationOutcome v = validate_extracted_statement(stmt, policy_);
            if (!v.ok()) {
                any_rejected_this_attempt = true;
                continue;
            }
            if (v.review_status_override.has_value()) {
                stmt.review_status = *v.review_status_override;
            }

            const std::string span_key = compute_extraction_span_key(
                engram_ref_id, chunk_index, stmt.predicate, stmt.canonical_object_hash);
            if (written_span_keys.find(span_key) == written_span_keys.end()
                    && extraction_span_key_already_succeeded(conn_, span_key)) {
                if (ledger.record_attempt(run_id, span_key, attempt,
                                          ExtractionStatus::Noop,
                                          /*raw_output=*/{},
                                          /*error=*/"noop:extraction_span_key_hit",
                                          take_cost())) {
                    emit_extraction_event(conn_, "extraction.noop",
                                          holder_tenant_id, run_id, span_key,
                                          run_started_event_id);
                    noop_short_circuited = true;
                }
                continue;
            }

            const auto outcome = writer.write(stmt, engram_ref_id, span_key, run_started_event_id);
            if (std::holds_alternative<StatementWriteAccepted>(outcome)) {
                result.accepted_statement_ids.push_back(
                    std::get<StatementWriteAccepted>(outcome).stmt_id);
                written_span_keys.insert(span_key);
                ledger.record_attempt(run_id, span_key, attempt,
                                      ExtractionStatus::Success,
                                      /*raw_output=*/{},
                                      /*error=*/{},
                                      take_cost());
            } else {
                result.accepted_statement_ids.push_back(
                    std::get<StatementWriteChunkDuplicate>(outcome).stmt_id);
            }
            wrote_anything_this_attempt = true;
        }

        if (!wrote_anything_this_attempt && !noop_short_circuited) {
            const auto attempt_status =
                any_rejected_this_attempt ? ExtractionStatus::Failed
                                          : ExtractionStatus::Success;
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  attempt_status,
                                  rec.resp.raw_xml, /*error=*/{},
                                  take_cost());
        } else if (wrote_anything_this_attempt && any_rejected_this_attempt) {
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  ExtractionStatus::PartialSuccess,
                                  rec.resp.raw_xml, /*error=*/{},
                                  take_cost());
            result_partial = true;
        }
        if (wrote_anything_this_attempt) any_accepted = true;
        all_failed = false;
        break;
    }

    if (any_accepted) {
        result.status = result_partial
            ? ExtractionRunResult::Status::PARTIAL_SUCCESS
            : ExtractionRunResult::Status::SUCCESS;
        ledger.finish_run(run_id, PipelineStatus::Finished);
        emit_pipeline_event(conn_, "pipeline.run_completed",
                            holder_tenant_id, run_id, run_started_event_id);
    } else if (all_failed) {
        result.status = ExtractionRunResult::Status::FAILED;
        ledger.finish_run(run_id, PipelineStatus::Failed);
        emit_pipeline_event(conn_, "pipeline.run_failed",
                            holder_tenant_id, run_id, run_started_event_id);
    } else {
        result.status = ExtractionRunResult::Status::SUCCESS;
        ledger.finish_run(run_id, PipelineStatus::Finished);
        emit_pipeline_event(conn_, "pipeline.run_completed",
                            holder_tenant_id, run_id, run_started_event_id);
    }

    tx.commit();
    return result;
}

ExtractionRunResult Extractor::run(
        std::string_view                  engram_ref_id,
        const std::vector<std::uint8_t>&  payload_bytes,
        std::string_view                  holder_id,
        std::string_view                  holder_tenant_id,
        const ExistingRefMap&             existing_ref_map,
        std::string_view                  interlocutor) {
    // 单体 = 三相内联(单一语义源;host 分相调用与此逐字段等价,见 test_extractor_phases）。
    const ExtractionLlmResult llm = extract_llm(payload_bytes, holder_id, existing_ref_map);
    return persist(engram_ref_id, holder_id, holder_tenant_id, interlocutor, llm);
}
```

- [ ] **Step 6: 构建 + 跑 Extractor 相关测试**

```bash
export PATH="$PWD/.venv/bin:$PATH"
python scripts/configure_build.py --build 2>&1 | tail -5
ctest --test-dir build-macos -R "ExtractorPhases|ExtractorOrchestrator" --output-on-failure 2>&1 | tail -30
```
Expected: `ExtractorPhases`(3 新)+ `ExtractorOrchestrator`(既有,run 内联后不变)全 PASS。

- [ ] **Step 7: 全量 ctest(确认零回归)**

```bash
ctest --test-dir build-macos --output-on-failure 2>&1 | tail -15
```
Expected: 全绿。**#7 关键**:`test_extractor_orchestrator`(既有)对具体老行为下了绝对断言(如「3 条 failed attempt」「1 条 statement」「pipeline_run finished 计数」「特定 event 计数」)——**它才是老行为的权威回归网**(新 phases 测试的 run-vs-phased 因 run 内联 extract_llm→persist 而近乎恒真,只额外验 no-DB/autocommit + 行级值 parity)。orchestrator 测试必须保持绿,任何 persist 转录错误会在那里现形。

- [ ] **Step 8: 提交**

```bash
git add include/starling/extractor/extractor.hpp src/extractor/extractor.cpp tests/cpp/test_extractor_phases.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(extractor): split run into extract_llm (no-DB) + persist (txn), run inlines

方案2 option B 第一步:Extractor::run 拆成 extract_llm(重试循环只做
adapter_.extract + parse,零 DB、无 TransactionGuard)+ persist(开
事务重放 attempts 写 ledger/attempt/statements)。run 内联二者=单一
语义源。既有 extractor 测试驱动 run() 照跑;新 test_extractor_phases
钉 extract_llm→persist ≡ run + extract_llm 无开事务零写。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: memoryops remember 三相(remember 内联)+ C++ parity 测试

**Files:**
- Modify: `include/starling/memory/memory_ops.hpp`(加 `RememberPrepared` 结构 + 三方法声明;加 `#include "starling/extractor/extractor.hpp"`)
- Modify: `src/memory/memory_ops.cpp`(实现 `remember_prepare`/`extract_llm`/`remember_commit`,`remember` 内联)
- Create: `tests/cpp/test_remember_phases.cpp`
- Modify: `tests/cpp/CMakeLists.txt`(注册)

**Interfaces:**
- Consumes: Task 1 的 `Extractor::extract_llm`/`persist`/`ExtractionLlmResult`;现存 `RememberParams`/`RememberOutcome`。
- Produces:
  - `struct RememberPrepared { std::string engram_ref; std::string outcome; bool should_extract = false; std::string created_at_iso8601; };`(#6:created_at 权威时戳)
  - `RememberPrepared remember_prepare(persistence::SqliteAdapter&, const RememberParams&);`
  - `extractor::ExtractionLlmResult extract_llm(persistence::SqliteAdapter&, extractor::LLMAdapter&, std::string_view prompt_template, const RememberParams&, const extractor::ValidationPolicy& = {});`
  - `RememberOutcome remember_commit(persistence::SqliteAdapter&, extractor::LLMAdapter&, const RememberParams&, const RememberPrepared&, const extractor::ExtractionLlmResult&, const extractor::ValidationPolicy& = {});`

- [ ] **Step 1: 写失败测试 `tests/cpp/test_remember_phases.cpp`**

```cpp
// test_remember_phases.cpp — remember 三相拆分(方案2 option B)。
// 钉:prepare+extract+commit ≡ 单体 remember(落库 + outcome);should_extract
// =false 短路不 persist;FAILED 仍写 3 attempt;门中途关 → commit 抛。零网络。
#include "starling/memory/memory_ops.hpp"

#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/governance/write_gate.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <memory>
#include <string>

namespace starling::memoryops {
namespace {

constexpr const char* kJson =
    R"JSON([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}])JSON";

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
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

RememberParams rp(std::string_view text) {
    RememberParams p;
    p.tenant_id          = "default";
    p.holder_id          = "cog-self";
    p.interlocutor       = "";
    p.adapter_name       = "facade";
    p.source_prefix      = "mem-";
    p.created_at_iso8601 = "2026-07-12T10:00:00Z";
    p.payload.assign(text.begin(), text.end());
    return p;
}

extractor::LLMResponse ok_json() {
    return extractor::LLMResponse{.raw_xml = kJson, .ok = true};
}

}  // namespace

TEST(RememberPhases, PhasedEqualsMonolith) {
    auto ma = make_adapter();
    extractor::FakeLLMAdapter mllm; mllm.set_default_response(ok_json());
    const auto mono = remember(*ma, mllm, "", rp("hi bob"));

    auto pa = make_adapter();
    extractor::FakeLLMAdapter pllm; pllm.set_default_response(ok_json());
    const auto prepared = remember_prepare(*pa, rp("hi bob"));
    EXPECT_TRUE(prepared.should_extract);
    const auto llm = extract_llm(*pa, pllm, "", rp("hi bob"));
    EXPECT_EQ(sqlite3_get_autocommit(pa->connection().raw()), 1);   // extract 无开事务
    const auto phased = remember_commit(*pa, pllm, rp("hi bob"), prepared, llm);

    EXPECT_EQ(mono.outcome, phased.outcome);
    EXPECT_EQ(mono.statement_ids.size(), phased.statement_ids.size());
    EXPECT_EQ(mono.extraction_failed, phased.extraction_failed);
    EXPECT_EQ(row_count(ma->connection(), "statements"),
              row_count(pa->connection(), "statements"));
    EXPECT_EQ(row_count(ma->connection(), "engrams"),
              row_count(pa->connection(), "engrams"));
}

TEST(RememberPhases, CommitShortCircuitsWhenShouldNotExtract) {
    // 直接构造 should_extract=false 的 prepared(no_store 语义)→ commit 不 persist。
    auto pa = make_adapter();
    extractor::FakeLLMAdapter pllm;
    RememberPrepared no_store;
    no_store.outcome        = "no_store";
    no_store.should_extract = false;
    const extractor::ExtractionLlmResult empty;
    const int before = row_count(pa->connection(), "statements");
    const auto r = remember_commit(*pa, pllm, rp("x"), no_store, empty);
    EXPECT_EQ(r.outcome, "no_store");
    EXPECT_TRUE(r.statement_ids.empty());
    EXPECT_FALSE(r.extraction_failed);
    EXPECT_EQ(row_count(pa->connection(), "statements"), before);   // 零 persist
}

TEST(RememberPhases, FailedExtractionStillPersistsAttemptRows) {
    auto pa = make_adapter();
    extractor::FakeLLMAdapter pllm;                    // ok=false all
    const auto prepared = remember_prepare(*pa, rp("hi"));
    const auto llm = extract_llm(*pa, pllm, "", rp("hi"));
    EXPECT_EQ(llm.attempts.size(), 3u);
    const auto r = remember_commit(*pa, pllm, rp("hi"), prepared, llm);
    EXPECT_TRUE(r.extraction_failed);
    EXPECT_EQ(row_count(pa->connection(), "extraction_attempt", "status='failed'"), 3);
}

TEST(RememberPhases, CommitThrowsWhenGateClosesMidTurn) {
    auto pa = make_adapter();
    extractor::FakeLLMAdapter pllm; pllm.set_default_response(ok_json());
    const auto prepared = remember_prepare(*pa, rp("hi"));   // 门开
    const auto llm = extract_llm(*pa, pllm, "", rp("hi"));
    pa->set_write_admit([] { return false; });               // 生成期间关门
    EXPECT_THROW(remember_commit(*pa, pllm, rp("hi"), prepared, llm),
                 governance::WriteGateRejected);
}

}  // namespace starling::memoryops
```

- [ ] **Step 2: 注册测试到 `tests/cpp/CMakeLists.txt`**

在 `test_converse_phases.cpp`(现:146)那一行**后**加:
```cmake
    test_remember_phases.cpp
```

- [ ] **Step 3: 构建确认失败**

```bash
export PATH="$PWD/.venv/bin:$PATH"
python scripts/configure_build.py --build 2>&1 | tail -20
```
Expected: 编译失败(`remember_prepare`/`extract_llm`/`remember_commit`/`RememberPrepared` 未定义)。

- [ ] **Step 4: `memory_ops.hpp` 加结构体 + 声明**

`#include` 块加(现:15-22 附近,与其他 starling 头并列):
```cpp
#include "starling/extractor/extractor.hpp"
```

在 `struct RememberOutcome { ... };`(现:36-43)**之后**加:
```cpp
// 方案2 三相拆分(2026-07-12,remember extraction 出锁):prepare(engram 写)/
// extract_llm(纯 LLM,锁外无事务)/ commit(persist txn 写 + 写后泵)。host 在
// prepare/commit 段持引擎锁、extract 段释放——写事务不再跨 extraction 网络。
// remember() 本身内联三相(单一语义源:分调用与单体逐字段 parity,见
// test_remember_phases.cpp)。C++ 原语是单次 extraction;belief/episodic/gf 的
// 三管线编排在 host MemoryCore(option B:本 slice 只让 belief+gf 出锁)。
struct RememberPrepared {
    std::string engram_ref;         // 空 = 未入库(no_store/rejected)
    std::string outcome;            // accepted/idempotent/no_store/rejected
    bool        should_extract = false;  // accepted||idempotent → 继续 extract+commit
    // #6(review 加固):prepare 时刻快照;commit 以它为权威(而非另传 created_at),
    // 镜像 ConversePrepared.created_at_iso8601——即使 C++/绑定直呼者对 prepare/commit
    // 各传不同 now,落库时戳也不分叉。Python bundle 亦从此读(不再自持 created_iso)。
    std::string created_at_iso8601;
};

// 相位 1(锁内短):require_write_admission fail-fast + append_evidence(engram 写)。
RememberPrepared remember_prepare(persistence::SqliteAdapter& adapter,
                                  const RememberParams& params);

// 相位 2(锁外无事务):构 Extractor → extract_llm(纯 LLM + parse,零 DB)。
extractor::ExtractionLlmResult extract_llm(persistence::SqliteAdapter& adapter,
                                           extractor::LLMAdapter& llm,
                                           std::string_view prompt_template,
                                           const RememberParams& params,
                                           const extractor::ValidationPolicy& policy = {});

// 相位 3(锁内短):require_write_admission(捕中途转 DRAINING)+ Extractor::persist
// (txn 写 statements/attempt/events)+ 写后泵。should_extract=false 时直接回
// prepared 的 outcome/engram_ref(no_store/rejected 短路,不 persist、不泵)。
RememberOutcome remember_commit(persistence::SqliteAdapter& adapter,
                                extractor::LLMAdapter& llm,
                                const RememberParams& params,
                                const RememberPrepared& prepared,
                                const extractor::ExtractionLlmResult& llm_result,
                                const extractor::ValidationPolicy& policy = {});
```

- [ ] **Step 5: `memory_ops.cpp` 实现三相,remember 内联**

把现 `RememberOutcome remember(...) { ... }`(现:24-87 整个函数)**替换**为下面四个函数(EngramInput build 移自原 remember:30-48;单体 remember 末尾内联三相):

```cpp
RememberPrepared remember_prepare(persistence::SqliteAdapter& adapter,
                                  const RememberParams& p) {
    governance::require_write_admission(adapter);   // 门前抛 = 零 DB 写
    evidence::EngramInput in;
    in.tenant_id              = p.tenant_id;
    in.source.adapter_name    = p.adapter_name;
    in.source.adapter_version = "1";
    in.source.source_item_id = p.source_prefix + crypto::sha256_hex(std::string_view(
        reinterpret_cast<const char*>(p.payload.data()), p.payload.size())).substr(0, 16);
    in.source.source_version = "1";
    in.source.chunk_index    = 0;
    in.source_kind     = schema::SourceKind::USER_INPUT;
    in.ingest_mode     = schema::IngestMode::WHOLE_RECORD;
    in.privacy_class   = schema::PrivacyClass::INTERNAL;
    in.retention_mode  = schema::EngramRetentionMode::AUDIT_RETAIN;
    in.declared_transformations = {};
    in.byte_preserving = true;
    in.payload_bytes   = p.payload;
    in.redacted_content = std::nullopt;
    in.created_at_iso8601 = p.created_at_iso8601;

    bus::Bus bus(adapter);
    const auto out = bus.append_evidence(in, std::nullopt);

    RememberPrepared prep;
    prep.created_at_iso8601 = p.created_at_iso8601;   // #6:权威时戳快照
    if (const auto* acc = std::get_if<bus::AppendEvidenceAccepted>(&out)) {
        prep.outcome = "accepted";   prep.engram_ref = acc->ref.id;  prep.should_extract = true;
    } else if (const auto* idem = std::get_if<bus::AppendEvidenceIdempotent>(&out)) {
        prep.outcome = "idempotent"; prep.engram_ref = idem->ref.id; prep.should_extract = true;
    } else if (std::holds_alternative<bus::AppendEvidenceNoStore>(out)) {
        prep.outcome = "no_store";
    } else {
        prep.outcome = "rejected";
    }
    return prep;
}

extractor::ExtractionLlmResult extract_llm(persistence::SqliteAdapter& adapter,
                                           extractor::LLMAdapter& llm,
                                           std::string_view prompt_template,
                                           const RememberParams& p,
                                           const extractor::ValidationPolicy& policy) {
    // store_adapter ctor 保留(persist 段做 cognizer 名归一);extract_llm 段不碰 DB。
    extractor::Extractor ex(adapter.connection(), llm, adapter,
                            std::string(prompt_template), policy);
    return ex.extract_llm(p.payload, p.holder_id, /*existing_ref_map=*/{});
}

RememberOutcome remember_commit(persistence::SqliteAdapter& adapter,
                                extractor::LLMAdapter& llm,
                                const RememberParams& p,
                                const RememberPrepared& prepared,
                                const extractor::ExtractionLlmResult& llm_result,
                                const extractor::ValidationPolicy& policy) {
    RememberOutcome r;
    r.outcome    = prepared.outcome;
    r.engram_ref = prepared.engram_ref;
    if (!prepared.should_extract) {
        return r;   // no_store/rejected:未入库即不抽取、不泵(与单体早退等价)
    }
    governance::require_write_admission(adapter);   // 捕锁外 extract 期间转 DRAINING

    extractor::Extractor ex(adapter.connection(), llm, adapter,
                            /*prompt_template=*/"", policy);
    const auto run = ex.persist(prepared.engram_ref, p.holder_id, p.tenant_id,
                                p.interlocutor, llm_result);
    r.statement_ids     = run.accepted_statement_ids;
    r.extraction_failed = (run.status == extractor::ExtractionRunResult::Status::FAILED);

    // 写后泵(P2.o):生产语句写经 StatementWriter 不经 Bus::write,泵挂此处。
    // #6:用 prepared 的权威时戳(而非 params 另传的 created_at)——防 prepare/commit 漂移。
    bus::SubscriberPump::run_post_write(adapter, adapter.connection(),
                                        prepared.created_at_iso8601);
    return r;
}

RememberOutcome remember(persistence::SqliteAdapter& adapter,
                         extractor::LLMAdapter& llm,
                         std::string_view prompt_template,
                         const RememberParams& p,
                         const extractor::ValidationPolicy& policy) {
    // 单体 = 三相内联(单一语义源;host 分相调用与此逐字段 parity)。
    const RememberPrepared prepared = remember_prepare(adapter, p);
    if (!prepared.should_extract) {
        RememberOutcome r;
        r.outcome    = prepared.outcome;
        r.engram_ref = prepared.engram_ref;
        return r;
    }
    const auto llm_result = extract_llm(adapter, llm, prompt_template, p, policy);
    return remember_commit(adapter, llm, p, prepared, llm_result, policy);
}
```

- [ ] **Step 6: 构建 + 跑 remember/converse/extractor 测试**

```bash
export PATH="$PWD/.venv/bin:$PATH"
python scripts/configure_build.py --build 2>&1 | tail -5
ctest --test-dir build-macos -R "RememberPhases|ConversePhases|MemoryOps|ExtractorPhases" --output-on-failure 2>&1 | tail -30
```
Expected: `RememberPhases`(4 新)+ 既有 `ConversePhases`/`MemoryOps`(converse_commit→单体 remember 内联三相,行为不变)全 PASS。

- [ ] **Step 7: 全量 ctest**

```bash
ctest --test-dir build-macos --output-on-failure 2>&1 | tail -15
```
Expected: 全绿。

- [ ] **Step 8: 提交**

```bash
git add include/starling/memory/memory_ops.hpp src/memory/memory_ops.cpp tests/cpp/test_remember_phases.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(memory): remember three-phase (prepare/extract_llm/commit), remember inlines

方案2 option B 第二步:memoryops 三相原语——remember_prepare(写门+
append_evidence)/ extract_llm(构 Extractor→extract_llm,锁外无事务)/
remember_commit(写门再校验+persist+写后泵,should_extract=false 短路)。
remember 内联三者=单一语义源;converse_commit 仍调单体 remember。
test_remember_phases 钉 parity + 短路 + FAILED 持久化 + 门中途关抛。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: 绑定(bind_13:opaque 句柄 + 三 m.def)

**Files:**
- Modify: `bindings/python/bind_13_memory_ops.cpp`(加 2 opaque `py::class_` + 3 `m.def`;现 `memory_remember` 保留)

**Interfaces:**
- Consumes: Task 2 的 `RememberPrepared`/`remember_prepare`/`extract_llm`/`remember_commit`;Task 1 的 `extractor::ExtractionLlmResult`。
- Produces(Python `_core` 上):`RememberPrepared`(readonly engram_ref/outcome/should_extract)、`ExtractionLlmResult`(opaque)、`memory_remember_prepare`/`memory_extract_llm`/`memory_remember_commit`。

- [ ] **Step 1: 在 `bind_13_memory_ops.cpp` 加三相绑定**

在 `memory_converse_commit` 的 `m.def(...)`(现:216 起)**闭合之后**、`bind_13_memory_ops` 函数结束 `}` 之前,插入:

```cpp
    // 方案2 三相(2026-07-12 remember extraction 出锁):host 在 prepare/commit
    // 段持引擎锁、extract 段释放——写事务不再跨 extraction 网络。opaque 句柄只在
    // 三段间传递,Python 不解构(照 converse 三相绑定范式)。
    py::class_<starling::memoryops::RememberPrepared>(m, "RememberPrepared")
        .def_readonly("engram_ref",     &starling::memoryops::RememberPrepared::engram_ref)
        .def_readonly("outcome",        &starling::memoryops::RememberPrepared::outcome)
        .def_readonly("should_extract", &starling::memoryops::RememberPrepared::should_extract)
        .def_readonly("created_at_iso8601",   // #6:Python(episodic)从此读,不再自持 created_iso
                       &starling::memoryops::RememberPrepared::created_at_iso8601);

    // 纯句柄:extract→commit 之间传递,无成员导出。
    py::class_<starling::extractor::ExtractionLlmResult>(m, "ExtractionLlmResult");

    m.def("memory_remember_prepare",
          [](starling::persistence::SqliteAdapter& adapter,
             const std::string& tenant_id, const std::string& holder_id,
             const std::string& interlocutor, const std::string& adapter_name,
             const std::string& source_prefix, const std::string& created_at_iso8601,
             const py::bytes& payload) {
              starling::memoryops::RememberParams p;
              p.tenant_id          = tenant_id;
              p.holder_id          = holder_id;
              p.interlocutor       = interlocutor;
              p.adapter_name       = adapter_name;
              p.source_prefix      = source_prefix;
              p.created_at_iso8601 = created_at_iso8601;
              {   // bytes → vector 须持 GIL
                  const std::string raw = payload;
                  p.payload.assign(raw.begin(), raw.end());
              }
              starling::memoryops::RememberPrepared prep;
              {
                  py::gil_scoped_release release;
                  prep = starling::memoryops::remember_prepare(adapter, p);
              }
              return prep;
          },
          py::arg("adapter"), py::arg("tenant_id"), py::arg("holder_id"),
          py::arg("interlocutor"), py::arg("adapter_name"), py::arg("source_prefix"),
          py::arg("created_at_iso8601"), py::arg("payload"));

    m.def("memory_extract_llm",
          [](starling::persistence::SqliteAdapter& adapter,
             starling::extractor::LLMAdapter& llm,
             const std::string& prompt_template, const std::string& holder_id,
             const py::bytes& payload,
             starling::extractor::ValidationPolicy policy) {
              starling::memoryops::RememberParams p;
              p.holder_id = holder_id;
              {
                  const std::string raw = payload;
                  p.payload.assign(raw.begin(), raw.end());
              }
              starling::extractor::ExtractionLlmResult out;
              {
                  py::gil_scoped_release release;   // 纯 LLM 段
                  out = starling::memoryops::extract_llm(adapter, llm, prompt_template,
                                                         p, policy);
              }
              return out;
          },
          py::arg("adapter"), py::arg("llm"), py::arg("prompt_template"),
          py::arg("holder_id"), py::arg("payload"),
          py::arg("policy") = starling::extractor::ValidationPolicy{});

    m.def("memory_remember_commit",
          // #6:不收 created_at_iso8601——commit 以 prepared.created_at_iso8601 为权威
          // (防 prepare/commit 时戳漂移,镜像 converse_commit)。
          [](starling::persistence::SqliteAdapter& adapter,
             starling::extractor::LLMAdapter& llm,
             const std::string& tenant_id, const std::string& holder_id,
             const std::string& interlocutor,
             const starling::memoryops::RememberPrepared& prepared,
             const starling::extractor::ExtractionLlmResult& llm_result,
             starling::extractor::ValidationPolicy policy) {
              starling::memoryops::RememberParams p;
              p.tenant_id    = tenant_id;
              p.holder_id    = holder_id;
              p.interlocutor = interlocutor;
              // p.created_at_iso8601 留空:commit 用 prepared 的权威时戳。
              starling::memoryops::RememberOutcome r;
              {
                  py::gil_scoped_release release;   // 内含 persist txn 写 + 写后泵
                  r = starling::memoryops::remember_commit(adapter, llm, p, prepared,
                                                           llm_result, policy);
              }
              return py::dict("engram_ref"_a = r.engram_ref,
                              "statement_ids"_a = r.statement_ids,
                              "outcome"_a = r.outcome,
                              "extraction_failed"_a = r.extraction_failed);
          },
          py::arg("adapter"), py::arg("llm"), py::arg("tenant_id"), py::arg("holder_id"),
          py::arg("interlocutor"),
          py::arg("prepared"), py::arg("llm_result"),
          py::arg("policy") = starling::extractor::ValidationPolicy{});
```

- [ ] **Step 2: 重建 `_core` 并冒烟绑定可调**

```bash
export PATH="$PWD/.venv/bin:$PATH"
python scripts/configure_build.py --build --python-editable 2>&1 | tail -5
.venv/bin/python -c "
from starling import _core
assert hasattr(_core, 'memory_remember_prepare')
assert hasattr(_core, 'memory_extract_llm')
assert hasattr(_core, 'memory_remember_commit')
assert hasattr(_core, 'RememberPrepared')
assert hasattr(_core, 'ExtractionLlmResult')
print('bind ok')
"
```
Expected: `bind ok`。

- [ ] **Step 3: 提交**

```bash
git add bindings/python/bind_13_memory_ops.cpp
git commit -m "$(cat <<'EOF'
feat(bind): remember three-phase bindings (prepare/extract_llm/commit)

opaque RememberPrepared + ExtractionLlmResult 句柄 + 三 m.def(照 converse
三相绑定范式,各段 gil_scoped_release)。单体 memory_remember 保留。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: MemoryCore + engine 三相(host 落锁)+ Python 测试

**Files:**
- Modify: `python/starling/_memory_core.py`(加 `remember_prepare`/`remember_extract`/`remember_commit`;`remember` 改内联三相,belief/episodic/gf 编排移入)
- Modify: `python/starling/dashboard/engine.py`(`remember` 改三段落锁 + `_resolve_extraction`;移除已不再被用的 `_role_override`)
- Modify: `python/starling/dashboard/routes/commands.py`(#2:remember 路由 catch `_core.WriteGateRejected`→503)
- Create: `tests/python/test_remember_phases_binding.py`
- Create: `tests/python/test_remember_lock_release.py`

**Interfaces:**
- Consumes: Task 3 的 `_core.memory_remember_prepare`/`memory_extract_llm`/`memory_remember_commit`;现存 `_core.EpisodicExtractor`/`PerceptionReconstructor`。
- Produces:`MemoryCore.remember_prepare(text, *, holder, interlocutor, now) → bundle(dict)`、`MemoryCore.remember_extract(bundle, llm=None) → extracted(dict)`、`MemoryCore.remember_commit(bundle, extracted, llm=None) → dict`;`DashboardEngine._resolve_extraction(provider)`。

- [ ] **Step 1: 写失败测试 `tests/python/test_remember_phases_binding.py`**

```python
"""remember 三相绑定冒烟(MemoryCore 转发):remember_prepare → remember_extract
→ remember_commit 组合的 dict shape 须与单体 MemoryCore.remember 一致。
夹具抄 tests/python/test_converse_phases_binding.py(FakeLLMAdapter + DashboardEngine)。"""
from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _core_handles(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "rb.db"), token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB_JSON, True, "")
    eng.llm = fake
    return eng._core, fake


def test_phased_binding_matches_monolith_shape(tmp_path):
    core, _fake = _core_handles(tmp_path)
    now = "2026-07-12T10:00:00Z"

    mono = core.remember("Bob owns auth", holder=None, interlocutor=None, now=now)

    bundle = core.remember_prepare("Alice owns web", holder=None,
                                   interlocutor=None, now=now)
    extracted = core.remember_extract(bundle)
    phased = core.remember_commit(bundle, extracted)

    assert set(phased) == set(mono)            # dict 键一致
    assert mono["outcome"] == "accepted"
    assert phased["outcome"] == "accepted"     # 不同文本 → 都是首入 accepted
    assert phased["engram_ref"]


def test_no_store_re_remember_is_idempotent(tmp_path):
    # 同文本二次 remember(三相)→ idempotent,零新 engram。
    core, _fake = _core_handles(tmp_path)
    now = "2026-07-12T10:00:00Z"
    first = core.remember("Carol owns db", holder=None, interlocutor=None, now=now)
    assert first["outcome"] == "accepted"

    bundle = core.remember_prepare("Carol owns db", holder=None,
                                   interlocutor=None, now=now)
    assert bundle["prepared"].outcome == "idempotent"
    assert bundle["prepared"].should_extract is True
    extracted = core.remember_extract(bundle)
    second = core.remember_commit(bundle, extracted)
    assert second["outcome"] == "idempotent"


def test_engine_split_matches_core_inline(tmp_path):
    """#5(review 加固):三管线 host 编排 parity。engine.remember(真三相 split,
    带锁编排 + provider 局部解析 + bundle/llm 线程化)与 MemoryCore.remember(单体
    内联)在同一输入、独立库下产出相同 statement_ids 数量 + outcome——证 belief+
    episodic+gf 三条在 split 路径不丢不乱。非恒真:split 走 engine 分相调用,inline
    走 MemoryCore 顺序内联,二者编排代码不同。"""
    cfg_a = DashboardConfig(db_path=str(tmp_path / "split.db"), token="")
    eng_a = DashboardEngine(cfg_a)
    fa = _core.FakeLLMAdapter(); fa.set_default_response(_STUB_JSON, True, "")
    eng_a.llm = fa
    cfg_b = DashboardConfig(db_path=str(tmp_path / "inline.db"), token="")
    eng_b = DashboardEngine(cfg_b)
    fb = _core.FakeLLMAdapter(); fb.set_default_response(_STUB_JSON, True, "")
    eng_b.llm = fb

    text = "Bob owns auth and went to Paris"
    split = eng_a.remember(text, holder="cog-self")            # 三相 split(engine)
    inline = eng_b._core.remember(text, holder="cog-self")     # 单体内联(MemoryCore)
    assert split["outcome"] == inline["outcome"] == "accepted"
    assert len(split["statement_ids"]) == len(inline["statement_ids"])
    assert len(split["statement_ids"]) >= 1                     # belief(+gf)至少 1 条
```

- [ ] **Step 2: 写失败测试 `tests/python/test_remember_lock_release.py`**

```python
"""锁纪律:remember 的 belief+gf extraction 段不得持有 DashboardEngine._lock。
计时法(照 test_converse_lock_release.py):extraction adapter set_delay_ms 拉长
extract 段;并发 tick 必须在 extract 段拿到锁(<0.4s),拆锁前必阻塞 ≥0.7s。"""
import threading
import time

from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _engine(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "rl.db"), token="")
    eng = DashboardEngine(cfg)
    extraction = _core.FakeLLMAdapter()
    extraction.set_default_response(_STUB_JSON, True, "")
    extraction.set_delay_ms(700)     # #4:extract 段 = C++ 内睡 700ms(belief+gf 各一次,锁外)
    eng.llm = extraction
    return eng


def test_tick_interleaves_during_extract(tmp_path):
    """#4:照 test_converse_lock_release 的计时法(非 instrumentation——那会假通过:
    若全程持锁,被起线程会在 remember 返回后拿锁并在断言前 set event)。
    belief extraction 睡 700ms(锁外);并发 tick 必须在 extract 段 <0.4s 拿到锁;
    拆锁前 remember 全程持锁 → tick 阻塞 ≥0.7s。"""
    eng = _engine(tmp_path)
    turn = threading.Thread(
        target=lambda: eng.remember("hello bob", holder="cog-self"))
    turn.start()
    time.sleep(0.15)                       # prepare 毫秒级 → 已进 belief extract(锁外)
    start = time.monotonic()
    eng.tick("2026-07-12T00:00:00Z")       # 拆锁后:extract 段中锁可得(tick 不用抽取 adapter)
    elapsed = time.monotonic() - start
    turn.join(timeout=10)
    assert elapsed < 0.4, f"tick 等锁 {elapsed:.2f}s —— extract 段仍持锁,未拆"


def test_resolve_extraction_local_reference(tmp_path):
    import pytest
    from starling.dashboard.engine import _LLMNotConfigured
    eng = _engine(tmp_path)
    assert eng._resolve_extraction(None) is eng._core.llm     # None → role-bound
    with pytest.raises(_LLMNotConfigured):
        eng._resolve_extraction("no-such-provider")           # 未配 provider → 抛
```

- [ ] **Step 3: 跑测试确认失败**

```bash
export PATH="$PWD/.venv/bin:$PATH"
.venv/bin/python -m pytest tests/python/test_remember_phases_binding.py tests/python/test_remember_lock_release.py -q 2>&1 | tail -20
```
Expected: FAIL(`MemoryCore` 无 `remember_prepare`/`remember_extract`/`remember_commit`;`engine` 无 `_resolve_extraction`)。

- [ ] **Step 4: `_memory_core.py` 加三相方法 + remember 内联**

把现 `MemoryCore.remember(...)`(现:134-198 整个方法)**替换**为下面的单体内联 + 三方法:

```python
    def remember(self, text: str, *, holder=None, interlocutor=None, now=None) -> dict:
        """单体 = 三相内联(单一语义源)。facade 直接走本单体;DashboardEngine
        分相调用以在锁外跑 belief+gf extraction。belief/episodic/gf 顺序不变。"""
        if self.llm is None:   # #1:fail-fast(prepare 会写 engram,故在写前查;facade 路径的兜底)
            raise LLMNotConfigured(
                "remember requires an llm adapter "
                "(make_stub_llm / make_openai_llm / make_anthropic_llm)")
        bundle = self.remember_prepare(text, holder=holder,
                                       interlocutor=interlocutor, now=now)
        extracted = self.remember_extract(bundle)
        return self.remember_commit(bundle, extracted)

    def remember_prepare(self, text: str, *, holder=None, interlocutor=None,
                         now=None) -> dict:
        """三相之一(锁内短):engram 写(belief+gf 共用同一 idempotent engram)。
        #1:不查 self.llm——prepare 不用 llm;llm 缺失的 fail-fast 由调用方在写前做
        (facade monolith remember() 已查;engine.remember 经 _resolve_extraction 查)。
        #6:created_iso 不入 bundle——commit/episodic 从 prepared.created_at_iso8601 读。"""
        created_iso = parse_now(now).astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        holder_id = holder or self.agent
        prepared = _core.memory_remember_prepare(
            self.rt.adapter, tenant_id=self.tenant, holder_id=holder_id,
            interlocutor=interlocutor or "", adapter_name=self.adapter_name,
            source_prefix=self.source_prefix, created_at_iso8601=created_iso,
            payload=text.encode("utf-8"))
        return {"prepared": prepared, "holder_id": holder_id,
                "interlocutor": interlocutor or "", "text": text}

    def remember_extract(self, bundle: dict, llm=None) -> dict:
        """三相之二(锁外无事务):belief + general-fact 两条 LLM 抽取(纯网络)。
        should_extract=False(no_store/rejected)→ 空。llm 缺省 self.llm;
        DashboardEngine 传本轮解析出的局部 adapter(避拆锁后全局 slot 竞态)。"""
        prepared = bundle["prepared"]
        if not prepared.should_extract:
            return {"belief": None, "gf": None}
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
        return {"belief": belief, "gf": gf}

    def remember_commit(self, bundle: dict, extracted: dict, llm=None) -> dict:
        """三相之三(锁内短):belief persist → episodic 单体(option B 残留:
        其 LLM 仍在锁内)→ gf persist(复用同 engram)。statement_ids 顺序
        belief+episodic+gf 与单体一致。"""
        prepared = bundle["prepared"]
        if not prepared.should_extract:
            return {"engram_ref": prepared.engram_ref, "statement_ids": [],
                    "outcome": prepared.outcome, "extraction_failed": False}
        extraction_llm = llm or self.llm
        created_iso = prepared.created_at_iso8601   # #6:权威时戳从 prepared 读(不再自持)
        holder_id = bundle["holder_id"]
        interlocutor = bundle["interlocutor"]
        text = bundle["text"]
        policy = _build_policy(self._extraction)

        # 第一条:belief persist(#6:不传 created_at,C++ 用 prepared 的权威时戳)。
        out = _core.memory_remember_commit(
            self.rt.adapter, extraction_llm, tenant_id=self.tenant,
            holder_id=holder_id, interlocutor=interlocutor,
            prepared=prepared, llm_result=extracted["belief"], policy=policy)

        # 第二条:episodic(叙事事件)。单体,LLM+DB 仍在此锁内(option B 残留)。
        engram_ref = out.get("engram_ref") or ""
        if engram_ref:
            episodic = _core.EpisodicExtractor(
                self.conn, extraction_llm, self.rt.adapter,
                self._extraction.episodic_prompt)
            event_ids = episodic.extract(
                passage=text, engram_ref=engram_ref, tenant=self.tenant,
                agent_self=holder_id, now=created_iso)
            if event_ids:
                out["statement_ids"] = list(out.get("statement_ids", [])) + list(event_ids)
                try:
                    _core.PerceptionReconstructor(
                        self.conn, self.rt.adapter).reconstruct(tenant=self.tenant)
                except Exception:  # noqa: BLE001 — perception 是 best-effort;绝不失败 remember
                    pass

        # 第三条:general-fact persist(复用同 idempotent engram;#6:不传 created_at)。
        gf_out = _core.memory_remember_commit(
            self.rt.adapter, extraction_llm, tenant_id=self.tenant,
            holder_id=holder_id, interlocutor=interlocutor,
            prepared=prepared, llm_result=extracted["gf"], policy=policy)
        gf_ids = gf_out.get("statement_ids", []) if gf_out else []
        if gf_ids:
            out["statement_ids"] = list(out.get("statement_ids", [])) + list(gf_ids)
        return out
```

- [ ] **Step 5: `engine.py` — remember 三段落锁 + `_resolve_extraction`,移除 `_role_override`**

把现 `_role_override`(现:414-436)**替换**为 `_resolve_extraction`,并改写 `remember`(现:438-443):

```python
    def _resolve_extraction(self, provider: str | None):
        """锁内调用:解析本轮抽取 adapter 为局部引用(锁外 extract 段使用)。
        取代旧 _role_override('llm', …) 的全局 slot 换入换出——拆锁后换全局
        slot 会被并发轮/后台 tick 读到错误模型(同 _resolve_chat)。"""
        if provider:
            cfg = self._cfg.resolve_provider(provider)
            if not cfg or not cfg.get("api_key"):
                raise _LLMNotConfigured(
                    f"selected provider '{provider}' is not configured")
            return _build_chat_adapter(cfg)
        return self._core.llm

    def remember(self, text: str, *, holder=None, interlocutor=None, now=None,
                 provider: str | None = None) -> dict:
        """三相落锁(方案2):belief+gf extraction 段在锁外,prepare/commit 持锁。
        episodic 单体仍在 commit 锁内(option B 残留)。provider 解析为局部
        adapter 传入 extract/commit(避拆锁后全局 slot 竞态,同 _converse_phased)。"""
        now = now or datetime.now(timezone.utc)
        with self._lock:                                    # ① 短:写门 + engram
            extraction = self._resolve_extraction(provider)
            if extraction is None:   # #1:fail-fast 在写 engram 前(provider 未给且抽取角色未绑)
                raise _LLMNotConfigured(
                    "remember requires an llm adapter (bind the extraction role "
                    "or pass a configured provider)")
            bundle = self._core.remember_prepare(
                text, holder=holder, interlocutor=interlocutor, now=now)
        extracted = self._core.remember_extract(bundle, llm=extraction)  # ② 锁外 LLM
        with self._lock:                                    # ③ persist + episodic + 写
            return self._core.remember_commit(bundle, extracted, llm=extraction)
```

- [ ] **Step 5b(#2): `commands.py` remember 路由 catch `WriteGateRejected`→503**

三相锁外 extract 期间健康转 DRAINING → `remember_commit` 抛 `WriteGateRejected`;路由现只 catch `_LLMNotConfigured`,故它会冒泡成 500。加一个 except 回 503(`_core.WriteGateRejected` 已注册 bind_14:42,无需绑定改动;503 范式见 inspect.py:196)。改 `python/starling/dashboard/routes/commands.py:92-103`:

```python
    @router.post("/remember")
    async def remember(body: RememberBody, request: Request):
        from starling.dashboard.engine import _LLMNotConfigured
        from starling import _core
        eng = _engine(request)
        try:
            r = await to_thread.run_sync(partial(
                eng.remember, body.text, holder=body.holder,
                interlocutor=body.interlocutor, now=body.now, provider=body.provider))
        except _LLMNotConfigured:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="llm_not_configured")
        except _core.WriteGateRejected:
            # #2:三相锁外 extract 期间健康转 DRAINING → commit 抛;回 503 而非 500。
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="draining")
        await _broadcast(request, "statement_added", {"statement_ids": r["statement_ids"]})
        return r
```

测试断点(加进 `test_remember_lock_release.py` 或 `test_dashboard_drain.py` 风格):用 `eng._rt` 或 adapter 的 `set_write_admit([]{return False})` 关门后 POST `/api/remember` → 断言 503(非 500)。若 route 层难驱动,退而在 engine 级断言 `engine.remember` 关门时抛 `_core.WriteGateRejected`(commit 门),route 的 except 覆盖它。

- [ ] **Step 6: 确认 `_role_override` 已无调用方后删净**

```bash
grep -rn "_role_override" python/ tests/
```
Expected: 除了刚删除的定义无其它命中。若上一步已删定义、`grep` 只在别处出现,则一并处理;若零命中则已干净。

- [ ] **Step 7: 跑新 Python 测试 + 相关既有测试**

```bash
export PATH="$PWD/.venv/bin:$PATH"
.venv/bin/python -m pytest tests/python/test_remember_phases_binding.py tests/python/test_remember_lock_release.py tests/python/test_memory_facade.py tests/python/test_dashboard_engine.py tests/python/test_dashboard_ingest_worker.py tests/python/test_dashboard_converse.py tests/python/test_dashboard_drain.py tests/python/test_write_gate_memory_ops.py -q 2>&1 | tail -25
```
Expected: 全 PASS(facade Memory.remember 走单体内联三相不变;dashboard remember 三相释放锁;摄入 worker 用 engine.remember 不变)。

- [ ] **Step 8: 全量 pytest**

```bash
.venv/bin/python -m pytest tests/python -q 2>&1 | tail -15
```
Expected: 全绿。

- [ ] **Step 9: 提交**

```bash
git add python/starling/_memory_core.py python/starling/dashboard/engine.py python/starling/dashboard/routes/commands.py tests/python/test_remember_phases_binding.py tests/python/test_remember_lock_release.py
git commit -m "$(cat <<'EOF'
feat(dashboard): remember three-phase host wiring — belief+gf extraction lock-free

MemoryCore 三相编排三管线:prepare(engram 一次)→ extract(belief+gf LLM,
锁外)→ commit(belief persist → episodic 单体残留 → gf persist)。
engine.remember 三段落锁(照 _converse_phased),provider 解析为局部引用
传入(_resolve_extraction 取代 _role_override 全局 slot 换)。episodic
LLM 仍在 commit 锁内 = option B 残留(follow-up)。lock-release 测试钉
extract 段锁已释放。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 真机验证(手动,非 CI 门)

**Files:**
- 无(临时脚本写 `$CLAUDE_JOB_DIR/tmp` 或 scratchpad;结果进 PR body)

- [ ] **Step 1: 重装 `_core` + 重启 dashboard**

```bash
export PATH="$PWD/.venv/bin:$PATH"
python scripts/configure_build.py --build --python-editable 2>&1 | tail -3
launchctl kickstart -k gui/$(id -u)/io.starling.dashboard
sleep 3
tail -20 ~/.starling/dashboard.log
```
Expected: dashboard 正常起(无 traceback)。

- [ ] **Step 2: 摄入负载期间并发 tick 不卡(核心 payoff 验证)**

用 dashboard 触发一次 remember(经 `/api/converse` 或直接摄入一个会话 job),在其 extraction 期间并发打 `/api/tick`,测响应墙钟。对照拆锁前 A 实测的 37.8s——现应秒回(belief+gf 出锁;episodic 残留只在 commit 段短暂持锁)。

```bash
# 触发一次 remember(带真 provider),后台;同时循环打只读端点看是否阻塞
TOKEN=$(python -c "import json,os;print(json.load(open(os.path.expanduser('~/.starling/starling.json'))).get('dashboard_token',''))")
curl -s -X POST localhost:8765/api/converse -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"message":"记住:我在做方案2锁纪律验证"}' &
for i in $(seq 1 8); do
  /usr/bin/time -p curl -s localhost:8765/api/vitals -H "Authorization: Bearer $TOKEN" -o /dev/null 2>&1 | grep real
  sleep 1
done
wait
```
Expected: 8 次 `/api/vitals` 每次 real < ~1s(extraction 期间只读端点不被 remember 的锁长阻塞)。如实记录墙钟进 PR body;若 Clash TUN 黑洞导致 provider 超时,换 stub/换时刻重测(见记忆 clash-tun)。

- [ ] **Step 3: latency 端点确认 extraction 仍在跑(功能未退化)**

```bash
curl -s "localhost:8765/api/metrics/latency?bucket=3600" -H "Authorization: Bearer $TOKEN" | python -m json.tool | head -30
```
Expected: 有 extraction attempt 分桶数据(belief+gf 仍抽取,落 extraction_attempt);episodic 残留可作 follow-up 观测点。结果进 PR body。如实报「belief+gf 出锁生效;episodic 残留待 measure 决定是否再拆」。

---

## 评审 follow-up(plan-eng-review 记录,不在本 slice)

- **#3 belief/gf 跨管线非原子**(codex 抓):`remember_commit` 顺序跑 belief persist → episodic → gf persist,每个 C++ commit 重查门;若 drain 恰落在 belief 与 gf commit 之间,会 belief/episodic 已写、gf 前抛 = 部分写入 + 异常。**属既存**(单体 belief→gf 两次 memory_remember 也非原子,`begin_drain` 不持引擎锁),非本计划回归 → follow-up(让 commit 段门检查一次而非每 C++ commit 重查,或 begin_drain 与在途多管线写协调)。**已裁定不在本 slice 动**(保持只聚焦 belief+gf 出锁)。
- **`EpisodicExtractor` 三相化**:episodic LLM 仍在 commit 锁内(~15s 残留)——measure-first follow-up(option B 核心)。
- **已在本 PR 收**:#1 provider 回归、#2 路由 503、#4 锁测计时法、#5 三管线 parity、#6 created_at 权威、#7 行级值断言、#8 时戳位移接受+文档化。

## Self-Review

**1. Spec coverage(逐节对 spec):**
- Design ①(Extractor 拆 extract_llm+persist,run 内联)→ Task 1。✓
- Design ②(memoryops 三相,remember 内联)→ Task 2。✓
- Design ③(绑定 opaque + 三 m.def)→ Task 3。✓
- Design ④(MemoryCore 编排 belief+gf 出锁/episodic 残留 + engine 三段落锁 + provider 局部解析)→ Task 4。✓
- Design ⑤(单写者:extract 无锁无事务)→ Task 1 Step 1 autocommit 断言 + Task 4 lock-release 测试。✓
- Testing(Extractor parity / extract_llm 无事务 / remember 三相 parity+短路+FAILED+门中途关 / 锁纪律 / belief+episodic+gf 顺序)→ Task 1+2+4 测试。✓
- Blast Radius(单体保留、converse_commit 走单体、episodic 残留、run 签名不改)→ 全 Task 内联单体 + Task 2 converse_commit 不动。✓

**2. Placeholder scan:** 无 TBD/TODO/"similar to";每个改码步给完整代码或精确 verbatim-move + 源行号 + 替换规则。✓

**3. Type consistency:**
- `ExtractionLlmResult`/`ExtractionLlmAttempt`(Task 1 hpp)被 Task 2 memoryops::extract_llm 返回、Task 3 opaque 绑定、Task 4 传 commit——签名一致。✓
- `RememberPrepared{engram_ref,outcome,should_extract}`(Task 2)→ Task 3 readonly 三字段 → Task 4 `bundle["prepared"].should_extract`/`.outcome`/`.engram_ref`。✓
- `extract_llm`/`persist` 方法签名(Task 1 hpp Produces)与 Task 2 调用点一致(`ex.extract_llm(p.payload, p.holder_id, {})` / `ex.persist(engram_ref, holder, tenant, interlocutor, llm_result)`)。✓
- `memory_remember_prepare`/`memory_extract_llm`/`memory_remember_commit` 绑定 arg 名(Task 3)与 Task 4 关键字调用一致。✓
- `_resolve_extraction`(Task 4 engine)/ `remember_extract(bundle, llm=)`/`remember_commit(bundle, extracted, llm=)`(Task 4 MemoryCore)相互一致。✓

**下一步:** plan-eng-review 已过(加固折进)→ subagent-driven-development 执行。

## Failure modes(新 codepath;每条:有无测试 / 有无错误处理 / 用户可见性)

| codepath | 失败场景 | 测试 | 错误处理 | 用户可见 |
|---|---|---|---|---|
| `extract_llm`(锁外 LLM) | LLM transport error / parse fail | `PhasedEqualsMonolithAllFail` + `FailedExtractionStillPersistsAttemptRows` | 重试循环 → 收集 failed attempt → persist 写 failed 行 + FAILED 状态 | `extraction_failed=true`(摄入经 spool 重试;converse 显 remember_error)—— 非静默 |
| `persist`(txn 写) | DB error | 既有 extractor 测试 | `TransactionGuard` rollback + 抛 | 异常冒泡 —— 非静默 |
| `remember_commit` 门中途关 | 锁外 extract 期间转 DRAINING | `CommitThrowsWhenGateClosesMidTurn`(C++)+ 路由 503 断点 | `require_write_admission` 抛 `WriteGateRejected` → 路由 503(#2) | 503 draining —— 非静默(**修好**:原为 500) |
| `engine.remember` provider 未绑 | provider 未给且抽取角色未绑 | `test_resolve_extraction_local_reference` | `_resolve_extraction`/入口 `extraction is None` 抛 `_LLMNotConfigured` → 409 | 409 —— 非静默(**修好** #1 回归) |
| belief/gf 跨管线(#3) | drain 恰落 belief 与 gf commit 之间 | (既存行为,follow-up) | gf commit 前抛 → 部分写入 + 503 | 部分沉淀 + 503;幂等重试自愈 —— **既存非本计划回归**,follow-up |

**无 critical gap**(无「既无测试又无错误处理又静默」的路径)。

## Worktree parallelization

**Sequential implementation, no parallelization opportunity.** 5 任务是严格依赖链:Task 2(memoryops)消费 Task 1(`Extractor::extract_llm`/`persist`);Task 3(绑定)消费 Task 2;Task 4(host)消费 Task 3;Task 5(真机)在最后。同碰 extractor/memory_ops 核心,无独立可并行 lane。

## Implementation Tasks

评审全部发现已**折进任务**(非另立 backlog):#1/#4/#5/#6/#7 加固进 Task 1-4 的代码与测试;#2 路由 503 = Task 4 Step 5b;#8 = Global Constraints/spec 文档化。**无新增独立 task**——按 Task 1→5 顺序执行即含全部加固。deferred follow-up(不在本 slice):`EpisodicExtractor` 三相化、belief/gf 跨管线原子性(#3),记于 spec Out of Scope + 「评审 follow-up」节。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 8 findings, all adjudicated (5 folded + 1 accepted + 1 folded + 1 deferred) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 2 self-findings (both ⊆ codex); scope accepted as-is (option B) |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — (backend/host only, no UI) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **CODEX:** 8 findings — cleared the single-writer concern (span-key read correctly stays in persist); surfaced #1 provider regression, #4 lock-test false-pass, #5 three-pipeline parity gap, #6 created_at authority, #7 count-only parity, #8 started_at timing shift, #2 route 500, #3 pre-existing non-atomicity. #1/#4/#5/#6/#7 folded into plan; #2 route-503 folded; #8 accepted+documented; #3 deferred (pre-existing, not a regression).
- **CROSS-MODEL:** No tension. Codex agreed with + extended both self-findings (#5 parity gap = my Tests finding; #6 = my bundle/created_at finding). No disagreement to adjudicate.
- **VERDICT:** ENG CLEARED — plan hardened, ready to implement (option B scope accepted; subagent-driven next).

NO UNRESOLVED DECISIONS
