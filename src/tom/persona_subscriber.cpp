#include "starling/tom/persona_subscriber.hpp"
#include "starling/neocortex/persona_container.hpp"

#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>

#include <set>
#include <string>
#include <utility>
#include <vector>

namespace starling::tom {

using starling::persistence::detail::bind_sv;
using starling::persistence::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

namespace {
std::string col(sqlite3_stmt* stmt, int idx) {
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    const char* txt = reinterpret_cast<const char*>(sqlite3_column_text(stmt, idx));
    return txt != nullptr ? txt : "";
}
}  // namespace

int PersonaSubscriber::tick_one_batch(persistence::SqliteAdapter& adapter,
                                      persistence::Connection& conn,
                                      std::string_view now_iso,
                                      int batch_size) {
    sqlite3* dbh = conn.raw();

    // 1. read checkpoint.
    int last_seq = 0;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(dbh,
            "SELECT last_processed_outbox_sequence FROM persona_subscriber_checkpoint WHERE id=1",
            -1, &raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(dbh, "persona_subscriber: read checkpoint prepare");
        }
        StmtHandle handle(raw);
        if (sqlite3_step(handle.get()) == SQLITE_ROW) {
            last_seq = sqlite3_column_int(handle.get(), 0);
        }
    }

    // 2. read trigger events after the checkpoint (subject-carrying primary_id).
    struct Event {
        std::string primary_id;
        std::string tenant;
        int seq = 0;
    };
    std::vector<Event> events;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(dbh,
            "SELECT primary_id, tenant_id, outbox_sequence FROM bus_events "
            "WHERE outbox_sequence > ? AND event_type IN "
            "('statement.derived','statement.consolidated','statement.superseded') "
            "ORDER BY outbox_sequence LIMIT ?", -1, &raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(dbh, "persona_subscriber: read events prepare");
        }
        StmtHandle handle(raw);
        sqlite3_bind_int(handle.get(), 1, last_seq);
        sqlite3_bind_int(handle.get(), 2, batch_size);
        while (sqlite3_step(handle.get()) == SQLITE_ROW) {
            events.push_back({col(handle.get(), 0), col(handle.get(), 1),
                              sqlite3_column_int(handle.get(), 2)});
        }
    }
    if (events.empty()) {
        return 0;
    }

    // 3. resolve each event's affected subject via primary_id (NEVER aggregate_id
    //    — it differs across the three event types); dedup (tenant, subject).
    int max_seq = last_seq;
    std::set<std::pair<std::string, std::string>> affected;
    for (const auto& evt : events) {
        max_seq = evt.seq;
        std::string subject;
        {
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(dbh,
                "SELECT subject_id FROM statements WHERE id=? AND tenant_id=?",
                -1, &raw, nullptr) != SQLITE_OK) {
                throw make_sqlite_error(dbh, "persona_subscriber: resolve subject prepare");
            }
            StmtHandle handle(raw);
            bind_sv(handle.get(), 1, evt.primary_id);
            bind_sv(handle.get(), 2, evt.tenant);
            if (sqlite3_step(handle.get()) != SQLITE_ROW) {
                continue;
            }
            subject = col(handle.get(), 0);
        }
        affected.emplace(evt.tenant, subject);
    }

    // 4. rebuild each affected subject's PersonaContainer from its consolidated,
    //    approved/review_requested statements. anchor_type is the trivial
    //    holder==subject mapping (spec locked "no allowlist").
    neocortex::PersonaContainer container(adapter);
    for (const auto& [tenant, subject] : affected) {
        std::vector<neocortex::AnchorStatement> sources;
        {
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(dbh,
                "SELECT id, holder_id, predicate, object_value, confidence FROM statements "
                "WHERE tenant_id=? AND subject_id=? AND consolidation_state='consolidated' "
                "AND review_status IN ('approved','review_requested')",
                -1, &raw, nullptr) != SQLITE_OK) {
                throw make_sqlite_error(dbh, "persona_subscriber: anchor query prepare");
            }
            StmtHandle handle(raw);
            bind_sv(handle.get(), 1, tenant);
            bind_sv(handle.get(), 2, subject);
            while (sqlite3_step(handle.get()) == SQLITE_ROW) {
                neocortex::AnchorStatement anchor;
                anchor.stmt_id = col(handle.get(), 0);
                const std::string holder = col(handle.get(), 1);
                anchor.anchor_type =
                    (holder == subject) ? "self_model_anchor" : "profile_anchor";
                anchor.dimension = col(handle.get(), 2);
                anchor.value = col(handle.get(), 3);
                anchor.confidence = sqlite3_column_double(handle.get(), 4);
                sources.push_back(std::move(anchor));
            }
        }
        if (sources.empty()) {
            continue;
        }
        try {
            container.rebuild(conn, tenant, subject, sources, now_iso);
        } catch (const neocortex::ConcurrentRebuildError&) {
            // Another writer advanced this holder's version between our read and
            // write; skip — a later tick reconverges. Mirrors the swallow-and-
            // move-on idiom in common_ground_subscriber.cpp.
        }
    }

    // 5. advance checkpoint (events were seen).
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(dbh,
            "UPDATE persona_subscriber_checkpoint SET last_processed_outbox_sequence=?, "
            "last_updated_at=? WHERE id=1", -1, &raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(dbh, "persona_subscriber: advance checkpoint prepare");
        }
        StmtHandle handle(raw);
        sqlite3_bind_int(handle.get(), 1, max_seq);
        bind_sv(handle.get(), 2, now_iso);
        sqlite3_step(handle.get());
    }

    // 6. number of trigger events consumed this batch.
    return static_cast<int>(events.size());
}

}  // namespace starling::tom
