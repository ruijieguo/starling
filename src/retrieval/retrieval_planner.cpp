#include "starling/retrieval/retrieval_planner.hpp"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>

#include <sqlite3.h>

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/tom/common_ground.hpp"

namespace starling::retrieval {

using persistence::StmtHandle;
using persistence::detail::bind_sv;
using persistence::detail::make_sqlite_error;

namespace {

// 候选行 + planner 需要、StatementRow 不含的三列。
struct FetchedRow {
    StatementRow row;
    double salience = 0.0;
    double activation = 0.0;
    std::string provenance;
    double base = 1.0;   // 结构化路径=1.0;语义路径=cosine
};

constexpr const char* kSelectCols =
    "SELECT id, tenant_id, holder_id, holder_perspective, subject_kind, "
    "subject_id, predicate, object_kind, object_value, canonical_object_hash, "
    "modality, polarity, confidence, observed_at, valid_from, valid_to, "
    "consolidation_state, review_status, evidence_json, affect_json, "
    "salience, activation, provenance FROM statements ";

FetchedRow read_row(sqlite3_stmt* st) {
    auto txt = [&](int i) {
        const auto* p = sqlite3_column_text(st, i);
        return p ? std::string(reinterpret_cast<const char*>(p)) : std::string();
    };
    FetchedRow f;
    auto& r = f.row;
    r.id = txt(0); r.tenant_id = txt(1); r.holder_id = txt(2);
    r.holder_perspective = txt(3); r.subject_kind = txt(4); r.subject_id = txt(5);
    r.predicate = txt(6); r.object_kind = txt(7); r.object_value = txt(8);
    r.canonical_object_hash = txt(9); r.modality = txt(10); r.polarity = txt(11);
    r.confidence = sqlite3_column_double(st, 12);
    r.observed_at = txt(13); r.valid_from = txt(14); r.valid_to = txt(15);
    r.consolidation_state = txt(16); r.review_status = txt(17);
    r.evidence_json = txt(18); r.affect_json = txt(19);
    f.salience = sqlite3_column_double(st, 20);
    f.activation = sqlite3_column_double(st, 21);
    f.provenance = txt(22);
    return f;
}

// 稳定状态 + 审核过滤 + 时间窗,全部结构化路径共用的 WHERE 尾巴。
constexpr const char* kStableTail =
    " AND consolidation_state IN ('consolidated','archived')"
    " AND review_status NOT IN ('rejected','pending_review')"
    " AND (valid_from IS NULL OR valid_from <= ?9)"
    " AND (valid_to   IS NULL OR valid_to   >  ?9) ";

void push_filter(RetrievalScopeStep& step, std::string name, std::string value) {
    step.filters.emplace_back(std::move(name), std::move(value));
}

}  // namespace

PlannerResult RetrievalPlanner::run(const PlannerQuery& q) {
    if (q.tenant_id.empty() || q.querier.empty() || q.as_of_iso8601.empty()
        || q.query_id.empty()) {
        throw std::invalid_argument(
            "RetrievalPlanner: tenant_id/querier/as_of/query_id are required");
    }
    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();

    PlannerResult out;
    auto& rc = out.receipt;
    rc.trace_id = q.trace_id; rc.query_id = q.query_id;
    rc.querier = q.querier;
    rc.perspective = q.perspective.empty() ? q.querier : q.perspective;
    rc.intent_name = to_string(q.intent);
    rc.runtime_health = q.runtime_health;
    rc.scope_plan.plan_id = q.query_id;
    rc.scope_plan.mode =
        (q.intent == QueryIntent::ABSTAIN_CHECK) ? "exhaustive" : "progressive";
    const std::string perspective = rc.perspective;

    // ── 1. parse:意图显式传入;归一结构化提示。──────────────────────────
    rc.plan_steps.push_back({"parse",
        std::string("intent=") + rc.intent_name +
        (q.subject_id.empty() ? "" : " subject=" + q.subject_id) +
        (q.predicate.empty() ? "" : " predicate=" + q.predicate)});

    // ── 2. mask:perspective ≠ querier 时取 KnowledgeFrontier 可见集。────
    const bool need_mask = perspective != q.querier;
    std::unordered_set<std::string> visible;
    if (need_mask) {
        cognizer::KnowledgeFrontier frontier(adapter_);
        visible = frontier.visible_engrams_at(q.tenant_id, perspective,
                                              q.as_of_iso8601);
    }
    rc.plan_steps.push_back({"mask",
        need_mask ? "frontier visible_engrams=" + std::to_string(visible.size())
                  : "perspective==querier, no mask"});

    // ── ground 集预查(COMMON_GROUND intent 的 fetch 也要用,提前到这里;
    //    plan_steps 的 "ground" 行仍按管线位序在 fuse 之后写入)。──────────
    PackContext pctx;
    pctx.querier = q.querier;
    const std::string cg_other = q.target.empty() ? perspective : q.target;
    for (const auto& e : tom::common_ground::query(adapter_, q.querier, cg_other,
                                                   q.tenant_id, q.as_of_iso8601)) {
        if (e.status == "grounded") pctx.common_ids.insert(e.statement_id);
        if (e.status == "recanted") pctx.recanted_ids.insert(e.statement_id);
    }

    // ── 3. plan:Intent→Path。────────────────────────────────────────────
    auto add_step = [&](std::string scope, std::string holder,
                        int max_candidates) {
        RetrievalScopeStep step;
        step.scope = std::move(scope);
        step.holder_scope = std::move(holder);
        step.max_candidates = max_candidates;
        push_filter(step, "tenant_id", q.tenant_id);
        push_filter(step, "holder_scope", step.holder_scope);
        push_filter(step, "perspective", perspective);
        rc.scope_plan.steps.push_back(std::move(step));
    };
    // 每个 case 决定 statement_main 的附加 WHERE 与 holder。
    std::string extra_where;
    switch (q.intent) {
        case QueryIntent::FACT_LOOKUP:
            add_step("statement_main", q.querier, q.k * 5);
            add_step("semantic_index", q.querier, q.k * 5);
            break;
        case QueryIntent::BELIEF_OF_OTHER:
            add_step("statement_main", q.target, q.k * 5);
            break;
        case QueryIntent::HISTORY:
            add_step("statement_main", q.querier, q.k * 10);
            add_step("graph_index", q.querier, q.k * 5);   // supersedes 链
            break;
        case QueryIntent::META_BELIEF:
            extra_where = " AND nesting_depth >= 1 ";
            add_step("statement_main", q.querier, q.k * 5);
            break;
        case QueryIntent::COMMITMENT_DUE:
            extra_where =
                " AND id IN (SELECT stmt_id FROM commitments WHERE tenant_id = ?1"
                "            AND state IN ('ACTIVE','created')) ";
            add_step("statement_main", q.querier, q.k * 5);
            break;
        case QueryIntent::PREFERENCE:
            extra_where = " AND predicate = 'prefers' ";
            add_step("statement_main",
                     q.target.empty() ? q.querier : q.target, q.k * 5);
            break;
        case QueryIntent::NORM_LOOKUP:
            extra_where = " AND predicate IN ('forbids','requires') ";
            add_step("statement_main", q.querier, q.k * 5);
            break;
        case QueryIntent::COMMON_GROUND:
            add_step("container_view", q.querier,
                     static_cast<int>(pctx.common_ids.size()));
            break;
        case QueryIntent::ABSTAIN_CHECK:
            add_step("statement_main", q.querier, q.k * 5);
            add_step("semantic_index", q.querier, q.k * 5);
            break;
    }
    // 混合过滤拒绝(spec §filter 混合形式拒绝规则)。
    if (!q.global_holder_filter.empty()) {
        for (const auto& step : rc.scope_plan.steps) {
            if (step.holder_scope != q.global_holder_filter) {
                rc.abstention_reason = "invalid_scope_filter_mix";
                rc.sufficiency_status = Sufficiency::ABSTAINED;
                rc.plan_steps.push_back({"plan", "rejected: scope filter mix"});
                out.abstained = true;
                out.context_pack = render_pack({}, rc.abstention_reason);
                return out;
            }
        }
    }
    rc.plan_steps.push_back({"plan",
        "steps=" + std::to_string(rc.scope_plan.steps.size()) +
        " mode=" + rc.scope_plan.mode});

    // ── 4. fetch:按 plan 逐 scope;progressive 早停。─────────────────────
    std::vector<FetchedRow> fetched;
    auto fetch_statement_main = [&](const RetrievalScopeStep& step) {
        std::string sql = std::string(kSelectCols) +
            "WHERE tenant_id = ?1 AND holder_id = ?2 ";
        if (!q.subject_id.empty()) sql += " AND subject_id = ?3 ";
        if (!q.predicate.empty())  sql += " AND predicate  = ?4 ";
        sql += extra_where;
        sql += kStableTail;
        sql += (q.intent == QueryIntent::HISTORY)
                   ? " ORDER BY observed_at ASC LIMIT ?5"
                   : " ORDER BY observed_at DESC LIMIT ?5";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "planner: statement_main prepare");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, q.tenant_id);
        bind_sv(h.get(), 2, step.holder_scope);
        if (!q.subject_id.empty()) bind_sv(h.get(), 3, q.subject_id);
        if (!q.predicate.empty())  bind_sv(h.get(), 4, q.predicate);
        sqlite3_bind_int(h.get(), 5, step.max_candidates);
        bind_sv(h.get(), 9, q.as_of_iso8601);
        while (sqlite3_step(h.get()) == SQLITE_ROW) fetched.push_back(read_row(h.get()));
    };
    auto fetch_by_id = [&](const std::string& id) {
        sqlite3_stmt* raw = nullptr;
        const std::string sql = std::string(kSelectCols) +
            "WHERE id = ?1 AND tenant_id = ?2" + kStableTail;
        if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
            return;
        StmtHandle h(raw);
        bind_sv(h.get(), 1, id);
        bind_sv(h.get(), 2, q.tenant_id);
        bind_sv(h.get(), 9, q.as_of_iso8601);
        if (sqlite3_step(h.get()) == SQLITE_ROW) fetched.push_back(read_row(h.get()));
    };
    auto fetch_semantic = [&](const RetrievalScopeStep& step) {
        if (q.text.empty()) {
            rc.skipped_scopes.push_back({"semantic_index", "empty_query_text",
                                         rc.scope_plan.stop_policy});
            return;
        }
        SemanticRetrieverParams sp;
        sp.tenant_id = q.tenant_id; sp.holder_id = step.holder_scope;
        sp.query_text = q.text; sp.k = step.max_candidates;
        sp.trace_id = q.trace_id; sp.query_id = q.query_id;
        const auto sr = semantic_.vector_recall(conn, sp);
        if (sr.degraded)
            rc.degraded_paths.push_back({"semantic_index", "embedder_unavailable",
                                         "statement_main_only"});
        for (const auto& s : sr.rows) {
            FetchedRow f; f.row = s.row; f.base = s.score;
            // salience/activation/provenance 语义路径不带列 → 单行补查。
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db,
                "SELECT salience, activation, provenance FROM statements "
                "WHERE id=?1 AND tenant_id=?2", -1, &raw, nullptr) == SQLITE_OK) {
                StmtHandle h(raw);
                bind_sv(h.get(), 1, s.row.id); bind_sv(h.get(), 2, q.tenant_id);
                if (sqlite3_step(h.get()) == SQLITE_ROW) {
                    f.salience   = sqlite3_column_double(h.get(), 0);
                    f.activation = sqlite3_column_double(h.get(), 1);
                    const auto* p = sqlite3_column_text(h.get(), 2);
                    f.provenance = p ? reinterpret_cast<const char*>(p) : "";
                }
            }
            fetched.push_back(std::move(f));
        }
    };
    auto fetch_graph_supersedes = [&]() {
        // HISTORY 辅路:从已取行沿 supersedes 边补链上行。
        std::unordered_set<std::string> have;
        for (const auto& f : fetched) have.insert(f.row.id);
        std::vector<std::string> seeds(have.begin(), have.end());
        for (const auto& id : seeds) {
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db,
                "SELECT dst_id FROM statement_edges WHERE src_id=?1 AND "
                "tenant_id=?2 AND edge_kind='supersedes' "
                "UNION SELECT src_id FROM statement_edges WHERE dst_id=?1 AND "
                "tenant_id=?2 AND edge_kind='supersedes'",
                -1, &raw, nullptr) != SQLITE_OK) continue;
            StmtHandle h(raw);
            bind_sv(h.get(), 1, id); bind_sv(h.get(), 2, q.tenant_id);
            std::vector<std::string> others;
            while (sqlite3_step(h.get()) == SQLITE_ROW) {
                const auto* p = sqlite3_column_text(h.get(), 0);
                if (p) others.emplace_back(reinterpret_cast<const char*>(p));
            }
            for (const auto& other : others) {
                if (have.count(other)) continue;
                fetch_by_id(other);
                have.insert(other);
            }
        }
    };
    auto fetch_container_view = [&]() {
        for (const auto& id : pctx.common_ids) fetch_by_id(id);
    };

    for (const auto& step : rc.scope_plan.steps) {
        const bool progressive = rc.scope_plan.mode == "progressive";
        if (progressive && static_cast<int>(fetched.size()) >= q.k
            && step.scope == "semantic_index") {
            rc.skipped_scopes.push_back({step.scope, "sufficient_from_prior_scope",
                                         rc.scope_plan.stop_policy});
            rc.stop_reason = "after_first_sufficient";
            continue;
        }
        if (step.scope == "statement_main")       fetch_statement_main(step);
        else if (step.scope == "semantic_index")  fetch_semantic(step);
        else if (step.scope == "graph_index")     fetch_graph_supersedes();
        else if (step.scope == "container_view")  fetch_container_view();
        rc.scopes_searched.push_back(step.scope);
    }
    rc.candidate_counts.fetched = static_cast<std::int64_t>(fetched.size());
    rc.plan_steps.push_back({"fetch",
        "fetched=" + std::to_string(fetched.size())});

    // mask 应用:rerank 之前(spec :107 位序硬约束);evidence 任一可见即可见。
    std::int64_t masked = 0;
    const std::size_t before_mask = fetched.size();
    if (need_mask) {
        std::vector<FetchedRow> kept;
        kept.reserve(fetched.size());
        for (auto& f : fetched) {
            bool any_visible = false;
            for (const auto& eng : visible) {
                if (f.row.evidence_json.find(eng) != std::string::npos) {
                    any_visible = true; break;
                }
            }
            if (any_visible) kept.push_back(std::move(f));
            else ++masked;
        }
        fetched = std::move(kept);
    }
    rc.frontier_masked_count = masked;

    // ── 5. fuse:按 id 去重(保最高 base)→ Affect-aware rerank → 截断 k。──
    std::unordered_map<std::string, FetchedRow> dedup;
    for (auto& f : fetched) {
        auto it = dedup.find(f.row.id);
        if (it == dedup.end() || f.base > it->second.base)
            dedup[f.row.id] = std::move(f);
    }
    std::vector<RerankCandidate> cands;
    std::unordered_map<std::string, std::string> provenance_by_id;
    cands.reserve(dedup.size());
    for (auto& [id, f] : dedup) {
        provenance_by_id[id] = f.provenance;
        cands.push_back({std::move(f.row), f.base, f.salience, f.activation});
    }
    QuerierAffectState qa{};
    auto breakdown = rerank(cands, qa, q.as_of_iso8601);
    if (static_cast<int>(cands.size()) > q.k) {
        cands.resize(static_cast<std::size_t>(q.k));
        breakdown.resize(static_cast<std::size_t>(q.k));
    }
    rc.score_breakdown = breakdown;
    rc.plan_steps.push_back({"fuse",
        "deduped=" + std::to_string(dedup.size()) +
        " returned<=" + std::to_string(q.k)});

    // ── 6. ground:承诺/冲突两集补查 + 共识集(已预查)记录。──────────────
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "SELECT stmt_id FROM commitments WHERE tenant_id=?1 AND "
            "state IN ('ACTIVE','created')", -1, &raw, nullptr) == SQLITE_OK) {
            StmtHandle h(raw);
            bind_sv(h.get(), 1, q.tenant_id);
            while (sqlite3_step(h.get()) == SQLITE_ROW) {
                const auto* p = sqlite3_column_text(h.get(), 0);
                if (p) pctx.todo_ids.insert(reinterpret_cast<const char*>(p));
            }
        }
    }
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "SELECT src_id, dst_id FROM statement_edges WHERE tenant_id=?1 AND "
            "edge_kind='CONFLICTS_WITH'", -1, &raw, nullptr) == SQLITE_OK) {
            StmtHandle h(raw);
            bind_sv(h.get(), 1, q.tenant_id);
            while (sqlite3_step(h.get()) == SQLITE_ROW) {
                const auto* a = sqlite3_column_text(h.get(), 0);
                const auto* b = sqlite3_column_text(h.get(), 1);
                if (a) pctx.conflict_ids.insert(reinterpret_cast<const char*>(a));
                if (b) pctx.conflict_ids.insert(reinterpret_cast<const char*>(b));
            }
        }
    }
    rc.plan_steps.push_back({"ground",
        "common=" + std::to_string(pctx.common_ids.size()) +
        " todo=" + std::to_string(pctx.todo_ids.size()) +
        " conflict=" + std::to_string(pctx.conflict_ids.size())});

    // ── 7. abstain:四条件。──────────────────────────────────────────────
    AbstentionInput ab;
    ab.any_candidates = !cands.empty();
    ab.max_score = breakdown.empty() ? 0.0 : breakdown.front().final_score;
    ab.frontier_denied = need_mask && before_mask > 0 && cands.empty();
    if (!cands.empty()) {
        bool all_recanted = true;
        for (const auto& c : cands)
            if (!pctx.recanted_ids.count(c.row.id)) { all_recanted = false; break; }
        ab.only_recanted_evidence = all_recanted;
        ab.unresolved_conflict = pctx.conflict_ids.count(cands.front().row.id) > 0;
    }
    rc.abstention_reason = evaluate_abstention(ab, q.abstention);
    rc.plan_steps.push_back({"abstain",
        rc.abstention_reason.empty() ? "pass" : rc.abstention_reason});

    // ── 输出组装 + sufficiency + projection lag + 中心化 emit。────────────
    if (!rc.abstention_reason.empty()) {
        out.abstained = true;
        out.context_pack = render_pack({}, rc.abstention_reason);
        rc.sufficiency_status = Sufficiency::ABSTAINED;
        rc.candidate_counts.returned = 0;
        return out;
    }
    std::vector<PackEntry> entries;
    for (std::size_t i = 0; i < cands.size(); ++i) {
        const auto label = classify_with_provenance(
            cands[i].row, pctx, provenance_by_id[cands[i].row.id]);
        entries.push_back({label, cands[i].row.id,
                           render_line(cands[i].row, label)});
        out.entries.push_back({std::move(cands[i].row),
                               breakdown[i].final_score, label});
    }
    out.context_pack = render_pack(entries, "");
    rc.candidate_counts.returned = static_cast<std::int64_t>(out.entries.size());
    rc.sufficiency_status = out.entries.empty() ? Sufficiency::MISSING_INFO
                                                : Sufficiency::SUFFICIENT;
    {   // projection lag:outbox 头 − 最慢 checkpoint(无消费者按 0)。
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "SELECT COALESCE((SELECT MAX(outbox_sequence) FROM bus_events),0) - "
            "COALESCE((SELECT MIN(last_dispatched_sequence) FROM consumer_checkpoints),"
            "(SELECT COALESCE(MAX(outbox_sequence),0) FROM bus_events))",
            -1, &raw, nullptr) == SQLITE_OK) {
            StmtHandle h(raw);
            if (sqlite3_step(h.get()) == SQLITE_ROW)
                rc.projection_lag_events = sqlite3_column_int64(h.get(), 0);
        }
    }
    // fire-and-forget recalled emit(键公式与 basic_retriever 一致;失败仅
    // stderr,不上抛——读副作用契约)。
    try {
        persistence::TransactionGuard tx(conn);
        bus::OutboxWriter w(conn);
        const auto now = std::chrono::system_clock::now();
        const std::string bucket =
            bus::compute_window_bucket("statement.recalled", now);
        for (const auto& e : out.entries) {
            bus::BusEvent ev;
            ev.tenant_id    = q.tenant_id;
            ev.event_type   = "statement.recalled";
            ev.primary_id   = e.row.id;
            ev.aggregate_id = e.row.id;
            ev.payload_json = std::string("{\"statement_id\":\"") + e.row.id +
                "\",\"querier\":\"" + q.querier + "\",\"perspective\":\"" +
                perspective + "\",\"intent\":\"" + rc.intent_name +
                "\",\"query_id\":\"" + q.query_id + "\"}";
            ev.version = "v1";
            ev.idempotency_key = bus::compute_idempotency_key(
                "statement.recalled", e.row.id, e.row.id, q.query_id, bucket);
            try {
                w.append(ev);
                rc.emitted_events.push_back(ev.event_id);
            } catch (const persistence::SqliteError& err) {
                if (err.code() != SQLITE_CONSTRAINT_UNIQUE) throw;  // 2s 窗口去重
            }
        }
        tx.commit();
    } catch (const std::exception& e) {
        std::fprintf(stderr,
            "retrieval_planner: recalled emit failed for query_id=%s: %s\n",
            q.query_id.c_str(), e.what());
    }
    return out;
}

}  // namespace starling::retrieval
