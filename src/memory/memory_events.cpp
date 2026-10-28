#include "starling/memory/memory_events.hpp"

#include <sqlite3.h>

#include <cstdio>
#include <ctime>
#include <format>
#include <utility>

#include <nlohmann/json.hpp>

#include "starling/crypto/sha256.hpp"
#include "starling/evidence/engram.hpp"
#include "starling/governance/write_gate.hpp"
#include "starling/persistence/stmt.hpp"

namespace starling::memoryops {

namespace {

// 读一列 TEXT;NULL 当空串(events 的这几列都是 NOT NULL,这里只是防御)。
std::string column_string(sqlite3_stmt* stmt, int col) {
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    const auto* text = reinterpret_cast<const char*>(sqlite3_column_text(stmt, col));
    return text != nullptr ? std::string(text) : std::string();
}

// events 表里一条行的全部字段(写侧用)。found=false 表示这个 key 还没有行。
struct EventRow {
    bool found = false;
    std::string state;
    std::string text;
    std::string text_sha256;
    std::string engram_ref;              // 列可空,NULL 读成空串
    std::string statement_ids_json = "[]";
    std::int64_t seq = 0;
};

EventRow read_event(persistence::Connection& conn, std::string_view tenant,
                    std::string_view key) {
    persistence::Stmt q(conn.raw(),
                        "SELECT state, text, text_sha256, COALESCE(engram_ref,''), "
                        "statement_ids_json, seq FROM events WHERE tenant_id=?1 AND key=?2");
    q.bind(tenant, key);
    EventRow row;
    if (!q.step_row()) return row;
    row.found              = true;
    row.state              = column_string(q.raw(), 0);
    row.text               = column_string(q.raw(), 1);
    row.text_sha256        = column_string(q.raw(), 2);
    row.engram_ref         = column_string(q.raw(), 3);
    row.statement_ids_json = column_string(q.raw(), 4);
    row.seq                = sqlite3_column_int64(q.raw(), 5);
    return row;
}

std::vector<std::string> parse_statement_ids(const std::string& json_text) {
    std::vector<std::string> ids;
    const auto parsed = nlohmann::json::parse(json_text, nullptr, /*allow_exceptions=*/false);
    if (!parsed.is_array()) return ids;   // 列被外部写坏时当空,不崩
    for (const auto& item : parsed) {
        if (item.is_string()) ids.push_back(item.get<std::string>());
    }
    return ids;
}

// 事件时钟:epoch_iso 加 seq 秒(设计源 4.3——时刻由事件行的 seq 推出,
// 所以同一 key 重试时时戳不漂移)。解析不出来就原样返回,坏时戳不致崩。
std::string add_seconds_to_iso(std::string_view epoch_iso, std::int64_t seconds) {
    const std::string iso(epoch_iso);
    int y = 0, mo = 0, d = 0, h = 0, mi = 0, s = 0;
    // NOLINTNEXTLINE(cert-err34-c)
    if (std::sscanf(iso.c_str(), "%d-%d-%dT%d:%d:%dZ", &y, &mo, &d, &h, &mi, &s) != 6) {
        return iso;
    }
    std::tm tm{};
    tm.tm_year = y - 1900; tm.tm_mon = mo - 1; tm.tm_mday = d;
    tm.tm_hour = h;        tm.tm_min = mi;     tm.tm_sec = s;
    const std::time_t epoch = timegm(&tm) + static_cast<std::time_t>(seconds);
    std::tm out{};
    gmtime_r(&epoch, &out);
    return std::format("{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
                       out.tm_year + 1900, out.tm_mon + 1, out.tm_mday,
                       out.tm_hour, out.tm_min, out.tm_sec);
}

// 本租户 content_hash 相同的 engram id(payload 决定 content_hash,S7)。按 rowid
// 升序,补齐分支逐个找挂在它上面的语句。
std::vector<std::string> engrams_with_content_hash(persistence::Connection& conn,
                                                   std::string_view tenant,
                                                   std::string_view content_hash) {
    persistence::Stmt q(conn.raw(),
                        "SELECT id FROM engrams WHERE tenant_id=?1 AND content_hash=?2 "
                        "ORDER BY rowid ASC");
    q.bind(tenant, content_hash);
    std::vector<std::string> ids;
    while (q.step_row()) ids.push_back(column_string(q.raw(), 0));
    return ids;
}

// evidence_json 指向 engram_id、holder 相同的语句 id,按 rowid 升序。匹配写法与
// src/bus/statement_writer.cpp 的 find_existing_in_chunk 一致(LIKE 扫 "engram_ref":"<id>")。
std::vector<std::string> statements_for_engram(persistence::Connection& conn,
                                               std::string_view tenant,
                                               std::string_view holder,
                                               std::string_view engram_id) {
    persistence::Stmt q(conn.raw(),
                        "SELECT id FROM statements WHERE tenant_id=?1 AND holder_id=?2 "
                        "AND evidence_json LIKE ?3 ORDER BY rowid ASC");
    const std::string like_pat =
        std::string("%\"engram_ref\":\"") + std::string(engram_id) + "\"%";
    q.bind(tenant, holder, like_pat);
    std::vector<std::string> ids;
    while (q.step_row()) ids.push_back(column_string(q.raw(), 0));
    return ids;
}

}  // namespace

std::int64_t next_seq(persistence::Connection& conn, std::string_view tenant) {
    persistence::Stmt q(conn.raw(),
                        "SELECT COALESCE(MAX(seq) + 1, 0) FROM events WHERE tenant_id=?1");
    q.bind(tenant);
    q.step_row();
    return sqlite3_column_int64(q.raw(), 0);
}

std::vector<PendingEventRow> pending_events(persistence::Connection& conn,
                                            std::string_view tenant) {
    persistence::Stmt q(conn.raw(),
                        "SELECT key, text, interlocutor, seq, failure_category FROM events "
                        "WHERE tenant_id=?1 AND state='pending' ORDER BY seq ASC");
    q.bind(tenant);
    std::vector<PendingEventRow> rows;
    while (q.step_row()) {
        PendingEventRow row;
        row.key = column_string(q.raw(), 0);
        row.text = column_string(q.raw(), 1);
        row.interlocutor = column_string(q.raw(), 2);
        row.seq = sqlite3_column_int64(q.raw(), 3);
        row.failure_category = column_string(q.raw(), 4);
        rows.push_back(std::move(row));
    }
    return rows;
}

RememberOutcome remember_event(persistence::SqliteAdapter& adapter,
                               extractor::LLMAdapter& llm,
                               const RememberParams& base,
                               const RememberPrompts& prompts,
                               std::string_view key,
                               std::string_view text,
                               std::string_view epoch_iso,
                               const extractor::ValidationPolicy& policy) {
    governance::require_write_admission(adapter);   // 门前抛 = 零 DB 写
    auto& conn = adapter.connection();
    const std::string text_sha = crypto::sha256_hex(text);

    // ── 第 1 段:短事务,读收据行,无行则占位。事务在本段末尾结束。 ──
    EventRow row;
    bool retrying_pending = false;   // 只有重试已存在的 pending 行才进补齐分支
    {
        persistence::TransactionGuard txn(conn);
        row = read_event(conn, base.tenant_id, key);
        if (row.found) {
            if (row.state == "abandoned") {
                throw EventConflict(
                    "remember_event: key already abandoned; pick a new key (key=" +
                    std::string(key) + ")");
            }
            if (row.text_sha256 != text_sha) {
                throw EventConflict(
                    "remember_event: key already records a different text (key=" +
                    std::string(key) + ")");
            }
            if (row.state == "committed") {
                // 已提交:取行里存的结果,一次 LLM 都不调(第 2、3 段都不走)。
                RememberOutcome done;
                done.holder_id     = base.holder_id;
                done.engram_ref    = row.engram_ref;
                done.statement_ids = parse_statement_ids(row.statement_ids_json);
                done.outcome       = "idempotent";
                done.source_preserved = !row.engram_ref.empty();
                done.structured_claims_persisted = !done.statement_ids.empty();
                txn.commit();
                return done;
            }
            // state == "pending":重试,用行里原来的 seq 与原文,不另分配序号。
            retrying_pending = true;
        } else {
            row.found       = true;
            row.state       = "pending";
            row.text        = std::string(text);
            row.text_sha256 = text_sha;
            row.seq         = next_seq(conn, base.tenant_id);
            persistence::Stmt ins(
                conn.raw(),
                "INSERT INTO events(tenant_id,key,text,interlocutor,text_sha256,seq,state) "
                "VALUES(?1,?2,?3,?4,?5,?6,'pending')");
            ins.bind(base.tenant_id, key, row.text, base.interlocutor, text_sha, row.seq);
            ins.step_done();
        }
        txn.commit();
    }

    // ── 第 2 段:事务外。抽取要走网络,这里绝不持写事务。 ──
    // payload 用行里存的原文(重试时与首次一致),key 作为前缀(设计源 4.3)。
    const std::string payload_text = "[" + std::string(key) + "] " + row.text;
    RememberParams params = base;
    params.payload.assign(payload_text.begin(), payload_text.end());
    params.created_at_iso8601 = add_seconds_to_iso(epoch_iso, row.seq);

    RememberOutcome result;
    bool completed_from_engram = false;
    // 补齐分支(只在重试已有 pending 行时走):② 落了语句、③ 没写成。按 payload 的
    // content_hash 找 engram,挂在它上面的语句就是上次抽取的成果——直接拿来用,不再
    // 抽取一次。新 key 不进这里:哪怕同一段文本早先被裸 remember 写过,新 key 也该
    // 照自己的前缀走一遍(前缀不同 → payload 不同 → content_hash 本就不同)。
    if (retrying_pending) {
        const std::string content_hash = evidence::compute_engram_content_hash(
            params.payload, /*declared_transformations=*/{});  // 与 remember_prepare 一致
        for (const auto& engram_id :
                 engrams_with_content_hash(conn, base.tenant_id, content_hash)) {
            auto ids = statements_for_engram(conn, base.tenant_id, base.holder_id, engram_id);
            if (ids.empty()) continue;
            result.holder_id     = base.holder_id;
            result.engram_ref    = engram_id;
            result.statement_ids = std::move(ids);
            result.outcome       = "idempotent";
            result.source_preserved = true;
            result.structured_claims_persisted = true;
            completed_from_engram = true;
            break;
        }
    }
    if (!completed_from_engram) {
        // remember_all 抛异常时行留 pending(不 catch),异常原样上抛。
        result = remember_all(adapter, llm, params, prompts, policy);
    }

    // ── 第 3 段:短事务,收尾写收据行。 ──
    // 只有「证据真入库了」且「抽取没失败」才算提交。只看 extraction_failed 不够:
    // no_store / rejected 在 remember_commit 之前就早退,source_missing 返回默认构造的
    // RememberOutcome,三者的 extraction_failed 都是 false(这个标记的含义只是「证据已
    // 入库但抽取 LLM 失败」,见 memory_ops.hpp 的注释)。若据此标 committed,这个 key
    // 以后每次调用都回 idempotent + 空语句,记忆静默丢失(设计源 §9 禁止)。stored 的
    // 判据与 memory_ops.cpp 里 converse_commit 算 remember_ok 的那一处一致。
    const bool stored = (result.outcome == "accepted" || result.outcome == "idempotent");
    {
        persistence::TransactionGuard txn(conn);
        if (!stored || result.extraction_failed) {
            // 行留 pending:下次调用照原 seq 重试,不另分配序号。不抛——留着 pending 行
            // 才让 rise 看得见(pending_events 带 failure_category,门②据此记 T2 失败)。
            const std::string category = result.extraction_failed
                ? result.failure_category : ("not_stored:" + result.outcome);
            // 返回值也带上这个原因:未入库时 remember_all 的 failure_category 是空的
            // (那条路径不填),只记进行里会让调用方拿到一个空原因——又是一种静默。
            // 行里记什么就返回什么,与抽取失败那一支的既有不变式一致。
            if (result.failure_category.empty()) result.failure_category = category;
            persistence::Stmt upd(conn.raw(),
                                  "UPDATE events SET failure_category=?1, "
                                  "engram_ref=COALESCE(NULLIF(?2,''), engram_ref) "
                                  "WHERE tenant_id=?3 AND key=?4");
            upd.bind(category, result.engram_ref, base.tenant_id, key);
            upd.step_done();
        } else {
            persistence::Stmt upd(conn.raw(),
                                  "UPDATE events SET state='committed', engram_ref=?1, "
                                  "statement_ids_json=?2, failure_category='' "
                                  "WHERE tenant_id=?3 AND key=?4");
            upd.bind(result.engram_ref,
                     nlohmann::json(result.statement_ids).dump(),
                     base.tenant_id, key);
            upd.step_done();
        }
        txn.commit();
    }
    return result;
}

}  // namespace starling::memoryops
