#include "starling/replay/consolidation_ops.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include <stdexcept>

namespace starling::replay {
using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

std::string_view to_string(ConsolidationOp op) {
    switch (op) {
        case ConsolidationOp::Compress:  return "compress";
        case ConsolidationOp::Abstract:  return "abstract";
        case ConsolidationOp::Reinforce: return "reinforce";
        case ConsolidationOp::Decay:     return "decay";
        case ConsolidationOp::Reconcile: return "reconcile";
    }
    throw std::invalid_argument("unknown ConsolidationOp");
}

OpResult op_compress(persistence::Connection& conn,
                     const std::vector<std::string>& input_stmt_ids,
                     std::string_view tenant_id,
                     std::string_view replay_batch_id) {
    OpResult r{ConsolidationOp::Compress, {}, 0};
    sqlite3* db = conn.raw();
    for (const auto& id : input_stmt_ids) {
        const char* sql =
            "UPDATE statements SET consolidation_state='consolidated', "
            "  last_replay_batch_id=?, replay_count=replay_count+1 "
            " WHERE id=? AND tenant_id=? AND consolidation_state='volatile'";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "op_compress: prepare");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, replay_batch_id);
        bind_sv(h.get(), 2, id);
        bind_sv(h.get(), 3, tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "op_compress: step");
        r.affected += sqlite3_changes(db);
    }
    if (!input_stmt_ids.empty()) r.output_stmt_id = input_stmt_ids.front();
    return r;
}

OpResult op_reinforce(persistence::Connection& conn,
                      const std::vector<std::string>& input_stmt_ids,
                      std::string_view tenant_id,
                      std::string_view replay_batch_id) {
    OpResult r{ConsolidationOp::Reinforce, {}, 0};
    sqlite3* db = conn.raw();
    for (const auto& id : input_stmt_ids) {
        const char* sql =
            "UPDATE statements SET access_count=access_count+1, "
            "  consolidation_state='consolidated', "
            "  last_replay_batch_id=?, replay_count=replay_count+1 "
            " WHERE id=? AND tenant_id=?";
        sqlite3_stmt* raw=nullptr;
        if (sqlite3_prepare_v2(db,sql,-1,&raw,nullptr)!=SQLITE_OK)
            throw make_sqlite_error(db,"op_reinforce: prepare");
        StmtHandle h(raw);
        bind_sv(h.get(),1,replay_batch_id); bind_sv(h.get(),2,id); bind_sv(h.get(),3,tenant_id);
        if (sqlite3_step(h.get())!=SQLITE_DONE) throw make_sqlite_error(db,"op_reinforce: step");
        r.affected += sqlite3_changes(db);
    }
    return r;
}

OpResult op_abstract(persistence::Connection& conn,
                     const std::vector<std::string>& input_stmt_ids,
                     std::string_view tenant_id,
                     std::string_view replay_batch_id) {
    OpResult r{ConsolidationOp::Abstract, {}, 0};
    sqlite3* db = conn.raw();
    for (const auto& id : input_stmt_ids) {
        const char* sql =
            "UPDATE statements SET last_replay_batch_id=?, replay_count=replay_count+1 "
            " WHERE id=? AND tenant_id=?";
        sqlite3_stmt* raw=nullptr;
        if (sqlite3_prepare_v2(db,sql,-1,&raw,nullptr)!=SQLITE_OK)
            throw make_sqlite_error(db,"op_abstract: prepare");
        StmtHandle h(raw);
        bind_sv(h.get(),1,replay_batch_id); bind_sv(h.get(),2,id); bind_sv(h.get(),3,tenant_id);
        if (sqlite3_step(h.get())!=SQLITE_DONE) throw make_sqlite_error(db,"op_abstract: step");
        r.affected += sqlite3_changes(db);
    }
    if (!input_stmt_ids.empty()) r.output_stmt_id = input_stmt_ids.front();
    return r;
}

}  // namespace starling::replay
