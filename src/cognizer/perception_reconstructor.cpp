// sub-project B phase 1 Task 1.2: PerceptionReconstructor 实现。
//
// 后置管线:扫描一个租户的全部 OCCURRED 事件,在一条 (observed_at, seq) 时间线上
// 重建场景级在场时间线(默认全员在场;enter/leave 覆盖),并把每个物理 location
// 事件的结果位置写入在场见证者的 perception_state(append-only,幂等 upsert)。
// 事件已在前面的管线提交,故本类在自己的顶层 TransactionGuard 里跑——失败回滚
// 也不会动到已提交的事件(TransactionGuard 析构默认 rollback,需显式 .commit(),
// 镜像 src/extractor/episodic_extractor.cpp 的提交语义)。
//
// 注:TransactionGuard 声明在 persistence/connection.hpp(无独立 transaction_guard.hpp),
// 已由 perception_reconstructor.hpp 传递包含。
#include "starling/cognizer/perception_reconstructor.hpp"
#include "starling/store/perception_state_store.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include <sqlite3.h>
#include <nlohmann/json.hpp>
#include <set>
#include <string>
#include <vector>
namespace starling::cognizer {
namespace {
struct ScanEvent {
    std::string stmt_id, actor, predicate, theme, observed_at, location, participants_json;
    long long seq = 0;
};
bool is_leave(const std::string& p) { return p == "leave" || p == "exit" || p == "depart"; }
bool is_enter(const std::string& p) { return p == "enter" || p == "return" || p == "arrive"; }
bool is_presence_change(const std::string& p) { return is_leave(p) || is_enter(p); }
// tell/inform: informational channel — does NOT establish physical presence (N1).
bool is_tell(const std::string& p) { return p == "tell" || p == "inform"; }
std::vector<std::string> participants_of(const ScanEvent& ev) {
    std::vector<std::string> ps;
    if (!ev.actor.empty()) ps.push_back(ev.actor);
    if (!ev.participants_json.empty()) {
        auto j = nlohmann::json::parse(ev.participants_json, nullptr, /*allow_exceptions=*/false);
        if (j.is_array()) for (auto& p : j) if (p.is_string()) ps.push_back(p.get<std::string>());
    }
    return ps;
}
}  // namespace

PerceptionReconstructor::PerceptionReconstructor(persistence::Connection& conn) : conn_(conn) {}

void PerceptionReconstructor::reconstruct(std::string_view tenant) {
    sqlite3* db = conn_.raw();
    // 1. Scan ALL OCCURRED events for the tenant on one timeline (observed_at, seq).
    const char* sql =
        "SELECT s.id, s.subject_id, s.predicate, s.object_value, s.observed_at, "
        "e.seq, e.location, e.participants_json "
        "FROM statements s JOIN episodic_events e "
        "ON e.statement_id=s.id AND e.tenant_id=s.tenant_id "
        "WHERE s.tenant_id=? AND s.modality='occurred' "
        "ORDER BY s.observed_at, e.seq";
    std::vector<ScanEvent> events;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
            throw persistence::detail::make_sqlite_error(db, "PerceptionReconstructor scan prepare");
        persistence::StmtHandle h(raw);
        persistence::detail::bind_sv(h.get(), 1, tenant);
        auto col = [&](int i) {
            const auto* t = sqlite3_column_text(h.get(), i);
            return t ? std::string(reinterpret_cast<const char*>(t)) : std::string();
        };
        int rc;
        while ((rc = sqlite3_step(h.get())) == SQLITE_ROW) {
            ScanEvent ev;
            ev.stmt_id = col(0); ev.actor = col(1); ev.predicate = col(2); ev.theme = col(3);
            ev.observed_at = col(4); ev.seq = sqlite3_column_int64(h.get(), 5);
            ev.location = col(6); ev.participants_json = col(7);
            events.push_back(std::move(ev));
        }
        if (rc != SQLITE_DONE)
            throw persistence::detail::make_sqlite_error(db, "PerceptionReconstructor scan step");
    }
    if (events.empty()) return;

    // 2. Physical cast = everyone named in a physical / presence-change event.
    //    tell/inform events are excluded — a cognizer named ONLY in a tell must NOT
    //    be presumed physically present (N1: e.g. "Anne phones absent Bob" must not
    //    make Bob a witness of the room's events).
    std::set<std::string> cast;
    for (const auto& ev : events) {
        if (is_tell(ev.predicate)) continue;  // tell does not establish physical presence
        for (const auto& p : participants_of(ev)) cast.insert(p);
    }

    // 3. Walk events; present set defaults to the whole cast; enter/leave override;
    //    physical witnesses (present ∪ this event's actor/participants) learn the location.
    store::PerceptionStateStore ps(conn_);
    persistence::TransactionGuard tx(conn_);  // own top-level tx (events already committed)
    std::set<std::string> present(cast.begin(), cast.end());
    long long position = 0;
    for (const auto& ev : events) {
        const auto evp = participants_of(ev);
        std::set<std::string> witnesses(present.begin(), present.end());
        for (const auto& p : evp) witnesses.insert(p);  // actor/participants present at their event
        if (is_tell(ev.predicate)) {
            // Told channel: recipient(s) = participants minus the teller (index 0).
            // Write each recipient's perception_state regardless of physical presence.
            // A tell is neither a presence change nor a physical witnessing.
            if (!ev.location.empty()) {
                for (std::size_t i = 1; i < evp.size(); ++i) {
                    store::PerceptionStateRow row;
                    row.tenant_id = std::string(tenant); row.cognizer_id = evp[i];
                    row.theme_id = ev.theme; row.state_dim = "location"; row.state_value = ev.location;
                    row.observed_at = ev.observed_at; row.position = position; row.source_event_id = ev.stmt_id;
                    ps.upsert(row);
                }
            }
            ++position; continue;  // skip presence update and physical witness branch
        } else if (is_presence_change(ev.predicate)) {
            if (is_leave(ev.predicate)) for (const auto& p : evp) present.erase(p);   // gone AFTER this
            else                        for (const auto& p : evp) present.insert(p);  // here from now
        } else if (!ev.location.empty()) {  // physical location event
            for (const auto& w : witnesses) {
                store::PerceptionStateRow row;
                row.tenant_id = std::string(tenant); row.cognizer_id = w;
                row.theme_id = ev.theme; row.state_dim = "location"; row.state_value = ev.location;
                row.observed_at = ev.observed_at; row.position = position; row.source_event_id = ev.stmt_id;
                ps.upsert(row);
            }
        }
        ++position;
    }
    tx.commit();  // TransactionGuard dtor rolls back unless committed (see episodic_extractor.cpp).
}
}  // namespace starling::cognizer
