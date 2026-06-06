#include "starling/tom/common_ground_subscriber.hpp"
#include "starling/tom/common_ground_writer.hpp"
#include "starling/neocortex/common_ground_container.hpp"

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <string>
#include <utility>
#include <vector>

namespace starling::tom {

using starling::bus::detail::bind_sv;
using starling::persistence::StmtHandle;

namespace {
std::string col(sqlite3_stmt* h, int i) {
    const char* t = reinterpret_cast<const char*>(sqlite3_column_text(h, i));
    return t ? t : "";
}
}  // namespace

int CommonGroundSubscriber::tick_one_batch(persistence::SqliteAdapter& adapter,
                                           persistence::Connection& conn,
                                           std::string_view now_iso,
                                           int batch_size) {
    sqlite3* db = conn.raw();
    // 1. read checkpoint
    int last_seq = 0;
    {
        sqlite3_stmt* raw = nullptr;
        sqlite3_prepare_v2(db,
            "SELECT last_processed_outbox_sequence FROM common_ground_subscriber_checkpoint WHERE id=1",
            -1, &raw, nullptr);
        StmtHandle h(raw);
        if (sqlite3_step(h.get()) == SQLITE_ROW) last_seq = sqlite3_column_int(h.get(), 0);
    }
    // 2. read statement.written events after checkpoint
    struct Ev { std::string stmt_id, tenant; int seq; };
    std::vector<Ev> evs;
    {
        sqlite3_stmt* raw = nullptr;
        sqlite3_prepare_v2(db,
            "SELECT primary_id, tenant_id, outbox_sequence FROM bus_events "
            "WHERE outbox_sequence > ? AND event_type='statement.written' "
            "ORDER BY outbox_sequence LIMIT ?", -1, &raw, nullptr);
        StmtHandle h(raw);
        sqlite3_bind_int(h.get(), 1, last_seq);
        sqlite3_bind_int(h.get(), 2, batch_size);
        while (sqlite3_step(h.get()) == SQLITE_ROW)
            evs.push_back({col(h.get(), 0), col(h.get(), 1), sqlite3_column_int(h.get(), 2)});
    }
    if (evs.empty()) return 0;

    CommonGroundWriter writer(adapter);
    neocortex::CommonGroundContainer container(adapter);
    int max_seq = last_seq;
    std::vector<std::pair<std::string, std::string>> rebuilt;   // (tenant, cg_ref) 去重

    for (const auto& ev : evs) {
        max_seq = ev.seq;
        std::string holder, subject_id, predicate, hash, polarity, sp_json;
        {
            sqlite3_stmt* raw = nullptr;
            sqlite3_prepare_v2(db,
                "SELECT holder_id, subject_id, predicate, canonical_object_hash, polarity, "
                "       COALESCE(scope_parties_json,'') FROM statements WHERE id=? AND tenant_id=?",
                -1, &raw, nullptr);
            StmtHandle h(raw);
            bind_sv(h.get(), 1, ev.stmt_id);
            bind_sv(h.get(), 2, ev.tenant);
            if (sqlite3_step(h.get()) != SQLITE_ROW) continue;
            holder = col(h.get(), 0); subject_id = col(h.get(), 1); predicate = col(h.get(), 2);
            hash = col(h.get(), 3); polarity = col(h.get(), 4); sp_json = col(h.get(), 5);
        }
        std::vector<std::string> parties;
        if (!sp_json.empty()) {
            try {
                auto a = nlohmann::json::parse(sp_json);
                if (a.is_array())
                    for (auto& e : a)
                        if (e.is_string()) parties.push_back(e.get<std::string>());
            } catch (...) {}
        }
        if (parties.size() < 2) continue;
        std::sort(parties.begin(), parties.end());

        struct Match { std::string cg_id, asserter, polarity; };
        std::vector<Match> matches;
        {
            sqlite3_stmt* raw = nullptr;
            sqlite3_prepare_v2(db,
                "SELECT cg.id, st.holder_id, st.polarity FROM common_ground cg "
                "JOIN statements st ON st.id=cg.statement_id AND st.tenant_id=cg.tenant_id "
                "WHERE cg.tenant_id=? AND cg.status='asserted_unack' "
                "  AND st.subject_id=? AND st.predicate=? AND st.canonical_object_hash=?",
                -1, &raw, nullptr);
            StmtHandle h(raw);
            bind_sv(h.get(), 1, ev.tenant);
            bind_sv(h.get(), 2, subject_id);
            bind_sv(h.get(), 3, predicate);
            bind_sv(h.get(), 4, hash);
            while (sqlite3_step(h.get()) == SQLITE_ROW)
                matches.push_back({col(h.get(), 0), col(h.get(), 1), col(h.get(), 2)});
        }

        bool handled = false;
        for (const auto& m : matches) {
            if (m.asserter == holder) continue;            // 同一方不算确认/repair
            if (m.polarity == polarity) writer.acknowledge(conn, m.cg_id, holder, now_iso);  // #1/#3
            else                        writer.repair(conn, m.cg_id, holder, now_iso);        // 矛盾
            handled = true;
        }
        if (!handled) {
            writer.assert_(conn, ev.tenant, ev.stmt_id, parties, now_iso);   // 新命题
        }
        rebuilt.emplace_back(ev.tenant, parties[0] + "::" + parties[1]);     // cg_ref = sorted a::b
    }

    // 3. rebuild affected containers（去重）
    std::sort(rebuilt.begin(), rebuilt.end());
    rebuilt.erase(std::unique(rebuilt.begin(), rebuilt.end()), rebuilt.end());
    for (const auto& [tenant, ref] : rebuilt) container.rebuild(conn, tenant, ref, now_iso);

    // 4. advance checkpoint
    {
        sqlite3_stmt* raw = nullptr;
        sqlite3_prepare_v2(db,
            "UPDATE common_ground_subscriber_checkpoint SET last_processed_outbox_sequence=?, last_updated_at=? WHERE id=1",
            -1, &raw, nullptr);
        StmtHandle h(raw);
        sqlite3_bind_int(h.get(), 1, max_seq);
        bind_sv(h.get(), 2, now_iso);
        sqlite3_step(h.get());
    }
    return static_cast<int>(evs.size());
}

}  // namespace starling::tom
