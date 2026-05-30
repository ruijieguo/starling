#include "starling/replay/consolidation_ops.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/replay/forgetting_curve.hpp"
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

OpResult op_decay(persistence::Connection& conn,
                  const std::vector<std::string>& candidate_stmt_ids,
                  std::string_view tenant_id,
                  std::string_view now_iso) {
    OpResult r{ConsolidationOp::Decay, {}, 0};
    sqlite3* db = conn.raw();
    for (const auto& id : candidate_stmt_ids) {
        ForgettingInputs in;
        sqlite3_stmt* sel=nullptr;
        if (sqlite3_prepare_v2(db,
            "SELECT salience,access_count,modality,last_accessed,consolidation_state "
            "FROM statements WHERE id=? AND tenant_id=?",-1,&sel,nullptr)!=SQLITE_OK)
            throw make_sqlite_error(db,"op_decay: prepare select");
        StmtHandle hsel(sel);
        bind_sv(hsel.get(),1,id); bind_sv(hsel.get(),2,tenant_id);
        if (sqlite3_step(hsel.get())!=SQLITE_ROW) continue;
        in.salience = sqlite3_column_double(hsel.get(),0);
        in.access_count = sqlite3_column_int64(hsel.get(),1);
        in.modality = reinterpret_cast<const char*>(sqlite3_column_text(hsel.get(),2));
        in.last_accessed_iso = reinterpret_cast<const char*>(sqlite3_column_text(hsel.get(),3));
        std::string state = reinterpret_cast<const char*>(sqlite3_column_text(hsel.get(),4));
        // active_grounded: 受 ACTIVE commitment 反向保护 (P2.c §7) → 不衰减
        {
            sqlite3_stmt* pst = nullptr;
            const char* psql =
                "SELECT EXISTS(SELECT 1 FROM commitment_protection cp "
                " JOIN commitments c ON c.stmt_id = cp.commitment_stmt_id "
                " WHERE cp.protected_stmt_id = ?1 AND c.state = 'ACTIVE')";
            if (sqlite3_prepare_v2(db, psql, -1, &pst, nullptr) != SQLITE_OK)
                throw make_sqlite_error(db, "op_decay: prepare protection EXISTS");
            StmtHandle hp(pst);
            bind_sv(hp.get(), 1, id);
            in.active_grounded = (sqlite3_step(hp.get()) == SQLITE_ROW && sqlite3_column_int(hp.get(), 0) == 1);
        }
        if (state != "consolidated") continue;  // 串行守护: 已变即跳过
        if (compute_s_t(in, now_iso) < 0.05 && !in.active_grounded) {
            sqlite3_stmt* upd=nullptr;
            if (sqlite3_prepare_v2(db,
                "UPDATE statements SET consolidation_state='archived' "
                "WHERE id=? AND tenant_id=? AND consolidation_state='consolidated'",
                -1,&upd,nullptr)!=SQLITE_OK)
                throw make_sqlite_error(db,"op_decay: prepare update");
            StmtHandle hupd(upd);
            bind_sv(hupd.get(),1,id); bind_sv(hupd.get(),2,tenant_id);
            if (sqlite3_step(hupd.get())!=SQLITE_DONE) throw make_sqlite_error(db,"op_decay: step");
            r.affected += sqlite3_changes(db);
        }
    }
    return r;
}

OpResult op_reconcile(persistence::Connection& conn,
                      const std::string& stmt_id,
                      std::string_view tenant_id) {
    OpResult r{ConsolidationOp::Reconcile, stmt_id, 0};
    sqlite3* db = conn.raw();
    const char* sql =
        "UPDATE statements SET consolidation_state='replaying_reconsolidating' "
        "WHERE id=? AND tenant_id=? AND consolidation_state='consolidated'";
    sqlite3_stmt* raw=nullptr;
    if (sqlite3_prepare_v2(db,sql,-1,&raw,nullptr)!=SQLITE_OK)
        throw make_sqlite_error(db,"op_reconcile: prepare");
    StmtHandle h(raw);
    bind_sv(h.get(),1,stmt_id); bind_sv(h.get(),2,tenant_id);
    if (sqlite3_step(h.get())!=SQLITE_DONE) throw make_sqlite_error(db,"op_reconcile: step");
    r.affected = sqlite3_changes(db);
    return r;
}

}  // namespace starling::replay
