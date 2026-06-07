// embedding_worker.cpp -- M0.9 EmbeddingWorker (spec §3.4/§5).
//
// Scan-driven asynchronous embedding, OFF the synchronous write path. The
// runtime drives tick_one_batch serially (like the Replay idle tick). Each
// batch: LEFT JOIN scans statements lacking a (non-failed/under-retry) vector,
// embeds them, finds existing neighbors via search_topk, runs pattern
// separation, then atomically (SAVEPOINT) writes statement_vectors +
// MAY_OVERLAP_WITH soft edges + a vector.embedded outbox event. Transient
// embed failures mark status='failed' with a bumped retry_count for backoff.

#include "starling/embedding/embedding_worker.hpp"

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/vector/pattern_separator.hpp"
#include "starling/vector/vector_math.hpp"

#include <sqlite3.h>

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <optional>
#include <random>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace starling::embedding {

namespace {

using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::bus::compute_idempotency_key;
using starling::bus::compute_window_bucket;
using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

// render_text: deterministic text fed to the embedder. Mirrors the test seed.
std::string render_text(std::string_view subject_id, std::string_view predicate,
                        std::string_view object_value) {
    std::string out;
    out.reserve(subject_id.size() + predicate.size() + object_value.size() + 2);
    out.append(subject_id);
    out.push_back(' ');
    out.append(predicate);
    out.push_back(' ');
    out.append(object_value);
    return out;
}

// 32 random hex chars for edge ids (mirrors arbitration.cpp).
std::string random_hex_32() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng();
    const std::uint64_t b = rng();
    char buf[33];
    std::snprintf(buf, sizeof(buf), "%016llx%016llx",
                  static_cast<unsigned long long>(a),
                  static_cast<unsigned long long>(b));
    return std::string(buf, 32);
}

// emit_event helper (mirrors projection_maintainer.cpp). MUST run inside an
// open transaction/savepoint so OutboxWriter's at-least-once guarantee holds.
void emit_event(persistence::Connection& conn, std::string_view event_type,
                std::string_view primary_id, std::string_view aggregate_id,
                std::string_view tenant_id, std::string payload_json) {
    BusEvent ev;
    ev.tenant_id = std::string(tenant_id);
    ev.event_type = std::string(event_type);
    ev.primary_id = std::string(primary_id);
    ev.aggregate_id = std::string(aggregate_id);
    const std::string window_bucket =
        compute_window_bucket(event_type, std::chrono::system_clock::now());
    const std::string canonical_key =
        std::string(tenant_id) + ":" + std::string(primary_id);
    ev.idempotency_key = compute_idempotency_key(
        event_type, aggregate_id, canonical_key, /*causation_root=*/"", window_bucket);
    ev.payload_json = std::move(payload_json);
    OutboxWriter ow(conn);
    ow.append(ev);
}

// Pending row collected from the scan (snapshot — no nested writes in cursor).
struct PendingRow {
    std::string id;
    std::string tenant_id;
    std::string subject_id;
    std::string predicate;
    std::string object_value;
    int retry_count = 0;
};

std::string col_text(sqlite3_stmt* s, int i) {
    const char* t = reinterpret_cast<const char*>(sqlite3_column_text(s, i));
    return t ? t : "";
}

// Mark a transient embed failure: UPSERT status='failed', bump retry_count.
void mark_failed(persistence::Connection& conn, const PendingRow& row,
                 int dim, const std::string& model, std::string_view now_iso) {
    const char* sql =
        "INSERT INTO statement_vectors"
        "(stmt_id,tenant_id,dim,model,status,retry_count,last_attempt_at)"
        " VALUES(?,?,?,?,'failed',1,?)"
        " ON CONFLICT(tenant_id,stmt_id) DO UPDATE SET"
        "   status='failed',"
        "   retry_count=retry_count+1,"
        "   last_attempt_at=excluded.last_attempt_at";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(conn.raw(), "embedding_worker: mark_failed prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, row.id);
    bind_sv(h.get(), 2, row.tenant_id);
    sqlite3_bind_int(h.get(), 3, dim);
    bind_sv(h.get(), 4, model);
    bind_sv(h.get(), 5, now_iso);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(conn.raw(), "embedding_worker: mark_failed step");
}

}  // namespace

EmbeddingStats EmbeddingWorker::tick_one_batch(persistence::Connection& conn,
                                               std::string_view now_iso) {
    EmbeddingStats stats;

    // 1. Scan pending statements (collect first; don't nest writes in cursor).
    std::vector<PendingRow> pending;
    {
        const char* sql =
            "SELECT s.id, s.tenant_id, s.subject_id, s.predicate, s.object_value, "
            "       COALESCE(v.retry_count,0) "
            "FROM statements s "
            "LEFT JOIN statement_vectors v ON v.stmt_id = s.id AND v.tenant_id = s.tenant_id "
            "WHERE s.consolidation_state NOT IN ('archived','forgotten') "
            "  AND (v.stmt_id IS NULL OR (v.status='failed' AND v.retry_count < ?)) "
            "LIMIT ?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(conn.raw(), "embedding_worker: scan prepare");
        StmtHandle h(raw);
        sqlite3_bind_int(h.get(), 1, cfg_.max_retry);
        sqlite3_bind_int(h.get(), 2, cfg_.batch_size);
        while (sqlite3_step(h.get()) == SQLITE_ROW) {
            PendingRow row;
            row.id           = col_text(h.get(), 0);
            row.tenant_id    = col_text(h.get(), 1);
            row.subject_id   = col_text(h.get(), 2);
            row.predicate    = col_text(h.get(), 3);
            row.object_value = col_text(h.get(), 4);
            row.retry_count  = sqlite3_column_int(h.get(), 5);
            pending.push_back(std::move(row));
        }
    }

    const int dim = embedder_.dim();
    const std::string model = embedder_.model();

    // 2. Process each pending statement.
    for (const auto& row : pending) {
        const std::string text =
            render_text(row.subject_id, row.predicate, row.object_value);

        EmbeddingResult er;
        try {
            er = embedder_.embed(text);
        } catch (const EmbeddingError&) {
            // Transient failure → mark failed, bump retry for backoff.
            mark_failed(conn, row, dim, model, now_iso);
            stats.failed++;
            continue;
        }

        // 3. Find neighbors via search_topk; fetch their index_vectors.
        std::vector<starling::vector::ScoredId> scored = index_.search_topk(
            conn, er.vector, cfg_.top_k_neighbors,
            starling::vector::SearchScope{row.tenant_id, std::nullopt, std::nullopt, true});

        std::vector<std::pair<std::string, std::vector<float>>> neighbors;
        for (const auto& sc : scored) {
            if (sc.stmt_id == row.id) continue;  // exclude self
            const char* nsql =
                "SELECT index_vector FROM statement_vectors "
                "WHERE stmt_id=? AND tenant_id=?";
            sqlite3_stmt* nraw = nullptr;
            if (sqlite3_prepare_v2(conn.raw(), nsql, -1, &nraw, nullptr) != SQLITE_OK)
                throw make_sqlite_error(conn.raw(), "embedding_worker: neighbor fetch prepare");
            StmtHandle nh(nraw);
            bind_sv(nh.get(), 1, sc.stmt_id);
            bind_sv(nh.get(), 2, row.tenant_id);
            if (sqlite3_step(nh.get()) == SQLITE_ROW) {
                const void* bp = sqlite3_column_blob(nh.get(), 0);
                int bn = sqlite3_column_bytes(nh.get(), 0);
                if (bp && bn > 0) {
                    std::string blob(static_cast<const char*>(bp), static_cast<size_t>(bn));
                    neighbors.emplace_back(sc.stmt_id,
                                           starling::vector::from_blob(blob));
                }
            }
        }

        // 4. Pattern separation.
        starling::vector::SeparationResult sep = starling::vector::separate(
            er.vector, neighbors, cfg_.theta_sep, cfg_.strength);

        // 5. Atomic write in a SAVEPOINT (nests under any outer txn/savepoint).
        if (sqlite3_exec(conn.raw(), "SAVEPOINT emb", nullptr, nullptr, nullptr) != SQLITE_OK)
            throw make_sqlite_error(conn.raw(), "embedding_worker: SAVEPOINT emb");
        try {
            // UPSERT statement_vectors (index_vector = separated; raw = original).
            {
                const char* sql =
                    "INSERT INTO statement_vectors"
                    "(stmt_id,tenant_id,index_vector,raw_embedding,dim,model,status,retry_count,embedded_at)"
                    " VALUES(?,?,?,?,?,?,'embedded',0,?)"
                    " ON CONFLICT(tenant_id,stmt_id) DO UPDATE SET"
                    "   index_vector=excluded.index_vector,"
                    "   raw_embedding=excluded.raw_embedding,"
                    "   dim=excluded.dim,"
                    "   model=excluded.model,"
                    "   status='embedded',"
                    "   retry_count=0,"
                    "   embedded_at=excluded.embedded_at";
                sqlite3_stmt* raw = nullptr;
                if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
                    throw make_sqlite_error(conn.raw(), "embedding_worker: upsert vector prepare");
                StmtHandle h(raw);
                bind_sv(h.get(), 1, row.id);
                bind_sv(h.get(), 2, row.tenant_id);
                const std::string ivec = starling::vector::to_blob(sep.index_vector);
                const std::string rvec = starling::vector::to_blob(er.vector);
                sqlite3_bind_blob(h.get(), 3, ivec.data(), static_cast<int>(ivec.size()), SQLITE_TRANSIENT);
                sqlite3_bind_blob(h.get(), 4, rvec.data(), static_cast<int>(rvec.size()), SQLITE_TRANSIENT);
                sqlite3_bind_int(h.get(), 5, er.dim);
                bind_sv(h.get(), 6, er.model);
                bind_sv(h.get(), 7, now_iso);
                if (sqlite3_step(h.get()) != SQLITE_DONE)
                    throw make_sqlite_error(conn.raw(), "embedding_worker: upsert vector step");
            }

            // MAY_OVERLAP_WITH soft edges (similarity in weight).
            for (const auto& [nid, sim] : sep.overlaps) {
                const char* sql =
                    "INSERT INTO statement_edges"
                    "(id,tenant_id,src_id,dst_id,edge_kind,weight,created_at,metadata_json)"
                    " VALUES(?,?,?,?,'MAY_OVERLAP_WITH',?,?,'{\"resolved\":false}')";
                sqlite3_stmt* raw = nullptr;
                if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
                    throw make_sqlite_error(conn.raw(), "embedding_worker: insert edge prepare");
                StmtHandle h(raw);
                const std::string edge_id = random_hex_32();
                bind_sv(h.get(), 1, edge_id);
                bind_sv(h.get(), 2, row.tenant_id);
                bind_sv(h.get(), 3, row.id);
                bind_sv(h.get(), 4, nid);
                sqlite3_bind_double(h.get(), 5, sim);
                bind_sv(h.get(), 6, now_iso);
                if (sqlite3_step(h.get()) != SQLITE_DONE)
                    throw make_sqlite_error(conn.raw(), "embedding_worker: insert edge step");
            }

            // vector.embedded outbox event.
            emit_event(conn, "vector.embedded", row.id, row.id, row.tenant_id, "{}");

            if (sqlite3_exec(conn.raw(), "RELEASE emb", nullptr, nullptr, nullptr) != SQLITE_OK)
                throw make_sqlite_error(conn.raw(), "embedding_worker: RELEASE emb");
        } catch (...) {
            sqlite3_exec(conn.raw(), "ROLLBACK TO emb", nullptr, nullptr, nullptr);
            sqlite3_exec(conn.raw(), "RELEASE emb", nullptr, nullptr, nullptr);
            throw;
        }

        stats.embedded++;
        stats.overlaps_created += static_cast<int>(sep.overlaps.size());
    }

    return stats;
}

}  // namespace starling::embedding
