// trigger.cpp -- P2.c Trigger evaluator (spec §3.3/§6).
// Evaluates a trigger kind + spec_json against a TriggerContext.
// 4 kinds: time / event / state / compound (all_of / any_of, recursive short-circuit).

#include "starling/prospective/trigger.hpp"

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <nlohmann/json.hpp>
#include <sqlite3.h>

#include <set>
#include <string>
#include <string_view>

namespace starling::prospective {

namespace {

using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

// Whitelisted statement column names for the state kind.
// Prevents SQL injection via the field parameter.
const std::set<std::string_view> kAllowedFields = {
    "predicate",
    "modality",
    "consolidation_state",
    "review_status",
    "subject_id",
    "object_value",
    "holder_id",
};

// Map op string to SQL operator. Returns empty string if not allowed.
std::string map_op(const std::string& op) {
    if (op == "eq") return "=";
    if (op == "ne") return "!=";
    if (op == "gt") return ">";
    if (op == "lt") return "<";
    return {};
}

bool eval_time(const nlohmann::json& spec, const TriggerContext& ctx) {
    auto at = spec.value("at", std::string());
    return !at.empty() && at <= ctx.now_iso;
}

bool eval_event(const nlohmann::json& spec, const TriggerContext& ctx) {
    return !ctx.event_type.empty() &&
           spec.value("event_type", std::string()) == ctx.event_type;
}

bool eval_state(persistence::Connection& conn, const nlohmann::json& spec,
                const TriggerContext& ctx) {
    auto field = spec.value("field", std::string());
    auto op    = spec.value("op", std::string());
    auto value = spec.value("value", std::string());

    // Whitelist field
    if (kAllowedFields.find(field) == kAllowedFields.end()) return false;

    // Map op to SQL
    std::string sqlop = map_op(op);
    if (sqlop.empty()) return false;

    // Build safe SQL — field is whitelisted, op is mapped from fixed set, value is
    // bound. Tenant-scope: a trigger belongs to a tenant's commitment, so the
    // statements predicate must not match another tenant's rows.
    std::string sql = "SELECT EXISTS(SELECT 1 FROM statements WHERE " + field + " " +
                      sqlop + " ? AND tenant_id = ?)";

    sqlite3_stmt* raw_stmt = nullptr;
    int rc = sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw_stmt, nullptr);
    if (rc != SQLITE_OK) return false;
    StmtHandle stmt(raw_stmt);

    bind_sv(stmt.get(), 1, value);
    bind_sv(stmt.get(), 2, ctx.tenant_id);

    rc = sqlite3_step(stmt.get());
    if (rc != SQLITE_ROW) return false;

    return sqlite3_column_int(stmt.get(), 0) != 0;
}

// Forward declare for recursion
bool eval_dispatch(persistence::Connection& conn, const std::string& kind,
                   const nlohmann::json& spec_obj, const TriggerContext& ctx);

bool eval_compound(persistence::Connection& conn, const nlohmann::json& spec,
                   const TriggerContext& ctx) {
    if (spec.contains("all_of")) {
        for (const auto& child : spec["all_of"]) {
            std::string child_kind = child.value("kind", std::string());
            const auto& child_spec = child["spec"];
            if (!eval_dispatch(conn, child_kind, child_spec, ctx)) return false;
        }
        return true;
    }
    if (spec.contains("any_of")) {
        for (const auto& child : spec["any_of"]) {
            std::string child_kind = child.value("kind", std::string());
            const auto& child_spec = child["spec"];
            if (eval_dispatch(conn, child_kind, child_spec, ctx)) return true;
        }
        return false;
    }
    return false;
}

bool eval_dispatch(persistence::Connection& conn, const std::string& kind,
                   const nlohmann::json& spec_obj, const TriggerContext& ctx) {
    if (kind == "time")     return eval_time(spec_obj, ctx);
    if (kind == "event")    return eval_event(spec_obj, ctx);
    if (kind == "state")    return eval_state(conn, spec_obj, ctx);
    if (kind == "compound") return eval_compound(conn, spec_obj, ctx);
    return false;
}

}  // namespace

bool evaluate_trigger(persistence::Connection& conn,
                      std::string_view kind,
                      std::string_view spec_json,
                      const TriggerContext& ctx) {
    nlohmann::json spec;
    try {
        spec = nlohmann::json::parse(spec_json);
    } catch (...) {
        return false;
    }

    return eval_dispatch(conn, std::string(kind), spec, ctx);
}

}  // namespace starling::prospective
