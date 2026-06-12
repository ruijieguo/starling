#include "starling/tom/common_ground_subscriber.hpp"
#include "starling/tom/common_ground_writer.hpp"
#include "starling/neocortex/common_ground_container.hpp"

#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <string>
#include <utility>
#include <vector>

namespace starling::tom {

using starling::persistence::detail::bind_sv;
using starling::persistence::detail::make_sqlite_error;
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
        if (sqlite3_prepare_v2(db,
            "SELECT last_processed_outbox_sequence FROM common_ground_subscriber_checkpoint WHERE id=1",
            -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "cg_subscriber: read checkpoint prepare");
        StmtHandle h(raw);
        if (sqlite3_step(h.get()) == SQLITE_ROW) last_seq = sqlite3_column_int(h.get(), 0);
    }
    // 2. read statement.written / statement.superseded events after checkpoint
    //    (P3.a2:superseding 是 CommonGround 过时治理的主触发器,spec 09_tom §5)
    struct Ev { std::string stmt_id, tenant, type, payload; int seq; };
    std::vector<Ev> evs;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "SELECT primary_id, tenant_id, event_type, COALESCE(payload_json,''), "
            "outbox_sequence FROM bus_events "
            "WHERE outbox_sequence > ? AND event_type IN "
            "('statement.written','statement.superseded') "
            "ORDER BY outbox_sequence LIMIT ?", -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "cg_subscriber: read events prepare");
        StmtHandle h(raw);
        sqlite3_bind_int(h.get(), 1, last_seq);
        sqlite3_bind_int(h.get(), 2, batch_size);
        while (sqlite3_step(h.get()) == SQLITE_ROW)
            evs.push_back({col(h.get(), 0), col(h.get(), 1), col(h.get(), 2),
                           col(h.get(), 3), sqlite3_column_int(h.get(), 4)});
    }

    CommonGroundWriter writer(adapter);
    neocortex::CommonGroundContainer container(adapter);
    int max_seq = last_seq;
    std::vector<std::pair<std::string, std::string>> rebuilt;   // (tenant, cg_ref) 去重

    // 超时降级(T=24h)每批运行——时间驱动,与事件无关;受影响 pair 先收集
    // 再 sweep,容器随后统一重建。
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "SELECT tenant_id, parties_json FROM common_ground "
            "WHERE status='asserted_unack' AND created_at < ?",
            -1, &raw, nullptr) == SQLITE_OK) {
            StmtHandle h(raw);
            // cutoff 与 writer.sweep_timeout_downgrade 同口径(now-24h)。
            // 直接复用 writer 的扫描:先粗收集所有 asserted_unack 的 pair,
            // sweep 后只有真降级的行影响容器;多重建无害(幂等)。
            bind_sv(h.get(), 1, now_iso);   // created_at < now 的超集,sweep 内部再判 24h
            while (sqlite3_step(h.get()) == SQLITE_ROW) {
                const std::string tenant = col(h.get(), 0);
                std::string pj = col(h.get(), 1);
                try {
                    auto a = nlohmann::json::parse(pj);
                    if (a.is_array() && a.size() >= 2)
                        rebuilt.emplace_back(tenant,
                            a[0].get<std::string>() + "::" + a[1].get<std::string>());
                } catch (...) {}
            }
        }
        if (writer.sweep_timeout_downgrade(conn, now_iso) == 0) {
            rebuilt.clear();   // 没有任何降级,无需为此重建
        }
    }
    if (evs.empty() && rebuilt.empty()) return 0;

    for (const auto& ev : evs) {
        max_seq = ev.seq;
        // ── superseding → SupersedeGround 联动(grounded 旧共识标记被取代)──
        if (ev.type == "statement.superseded") {
            std::string old_id, new_id;
            try {
                auto p = nlohmann::json::parse(ev.payload);
                old_id = p.value("old_stmt_id", "");
                new_id = p.value("new_stmt_id", "");
            } catch (...) {}
            if (old_id.empty() || new_id.empty()) continue;
            struct Hit { std::string cg_id, parties; };
            std::vector<Hit> hits;
            {
                sqlite3_stmt* raw = nullptr;
                if (sqlite3_prepare_v2(db,
                    "SELECT id, parties_json FROM common_ground "
                    "WHERE tenant_id=? AND statement_id=? AND status='grounded' "
                    "AND superseded_by IS NULL",
                    -1, &raw, nullptr) != SQLITE_OK)
                    throw make_sqlite_error(db, "cg_subscriber: superseded select");
                StmtHandle h(raw);
                bind_sv(h.get(), 1, ev.tenant);
                bind_sv(h.get(), 2, old_id);
                while (sqlite3_step(h.get()) == SQLITE_ROW)
                    hits.push_back({col(h.get(), 0), col(h.get(), 1)});
            }
            for (const auto& hit : hits) {
                writer.supersede_ground(conn, hit.cg_id, new_id, now_iso);
                try {
                    auto a = nlohmann::json::parse(hit.parties);
                    if (a.is_array() && a.size() >= 2)
                        rebuilt.emplace_back(ev.tenant,
                            a[0].get<std::string>() + "::" + a[1].get<std::string>());
                } catch (...) {}
            }
            continue;
        }
        std::string holder, subject_id, predicate, hash, polarity, sp_json;
        {
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db,
                "SELECT holder_id, subject_id, predicate, canonical_object_hash, polarity, "
                "       COALESCE(scope_parties_json,'') FROM statements WHERE id=? AND tenant_id=?",
                -1, &raw, nullptr) != SQLITE_OK)
                throw make_sqlite_error(db, "cg_subscriber: load statement prepare");
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
            if (sqlite3_prepare_v2(db,
                "SELECT cg.id, st.holder_id, st.polarity FROM common_ground cg "
                "JOIN statements st ON st.id=cg.statement_id AND st.tenant_id=cg.tenant_id "
                "WHERE cg.tenant_id=? AND cg.status='asserted_unack' "
                "  AND st.subject_id=? AND st.predicate=? AND st.canonical_object_hash=?",
                -1, &raw, nullptr) != SQLITE_OK)
                throw make_sqlite_error(db, "cg_subscriber: match prepare");
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
        // 无另一方匹配 → 新命题入库。注：若仅自己先前断言过同命题（matches 全 asserter==holder），
        // 也走这里再 assert_——本期接受（重复 asserted_unack）；去重细则留后续。
        if (!handled) {
            writer.assert_(conn, ev.tenant, ev.stmt_id, parties, now_iso);
        }
        // #2 共同在场推定：该 scope 下 asserted_unack 条目轮次+1，达 N=3 自动 grounded。
        // 设计要求 perceived_by⊇parties；本期恒成立——extractor.cpp 在对话语境把
        // perceived_by 设成与 scope_parties 同一 sorted pair，故此处不再单独校验。
        // parties_js 须与 writer 的 json_array_of_strings 字节一致（2 方 ["a","b"] 无空格）。
        const std::string parties_js = std::string("[\"") + parties[0] + "\",\"" + parties[1] + "\"]";
        {
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db,
                "UPDATE common_ground SET rounds_since_assert = rounds_since_assert + 1 "
                "WHERE tenant_id=? AND status='asserted_unack' AND parties_json=?",
                -1, &raw, nullptr) != SQLITE_OK)
                throw make_sqlite_error(db, "cg_subscriber: bump rounds prepare");
            StmtHandle h(raw);
            bind_sv(h.get(), 1, ev.tenant);
            bind_sv(h.get(), 2, parties_js);
            sqlite3_step(h.get());
        }
        {
            // 达 N=3 → grounded（co-presence），逐条 acknowledge 走审计 + grounded_at。
            std::vector<std::string> due;
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db,
                "SELECT id FROM common_ground WHERE tenant_id=? AND status='asserted_unack' "
                "AND parties_json=? AND rounds_since_assert >= 3",
                -1, &raw, nullptr) != SQLITE_OK)
                throw make_sqlite_error(db, "cg_subscriber: copresence select prepare");
            StmtHandle h(raw);
            bind_sv(h.get(), 1, ev.tenant);
            bind_sv(h.get(), 2, parties_js);
            while (sqlite3_step(h.get()) == SQLITE_ROW) due.push_back(col(h.get(), 0));
            for (const auto& id : due) writer.acknowledge(conn, id, "copresence", now_iso);
        }
        // cg_ref = sorted "a::b"（与 Task 7 Python 读路径一致）。本期假设 2 方对话；
        // parties>2 时仅取前两个（多方 grounding 超本期范围，见 spec §1）。
        rebuilt.emplace_back(ev.tenant, parties[0] + "::" + parties[1]);
    }

    // 3. rebuild affected containers（去重）
    std::sort(rebuilt.begin(), rebuilt.end());
    rebuilt.erase(std::unique(rebuilt.begin(), rebuilt.end()), rebuilt.end());
    for (const auto& [tenant, ref] : rebuilt) container.rebuild(conn, tenant, ref, now_iso);

    // 4. advance checkpoint
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "UPDATE common_ground_subscriber_checkpoint SET last_processed_outbox_sequence=?, last_updated_at=? WHERE id=1",
            -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "cg_subscriber: advance checkpoint prepare");
        StmtHandle h(raw);
        sqlite3_bind_int(h.get(), 1, max_seq);
        bind_sv(h.get(), 2, now_iso);
        sqlite3_step(h.get());
    }
    return static_cast<int>(evs.size());
}

}  // namespace starling::tom
