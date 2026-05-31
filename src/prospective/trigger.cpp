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

// Maximum nesting depth for compound triggers. A spec nested beyond this is
// treated as a non-match rather than blowing the stack (an adversarial/malformed
// commitment_triggers row could nest arbitrarily deep).
constexpr int kMaxCompoundDepth = 16;

// Forward declare for recursion (depth-counted).
bool eval_dispatch(persistence::Connection& conn, const std::string& kind,
                   const nlohmann::json& spec_obj, const TriggerContext& ctx,
                   int depth);

// Extract (kind, spec) from a compound child, tolerating malformed children: a
// child missing "kind" or "spec" (or with a non-object spec) evaluates to a
// non-match instead of throwing. Returns the evaluation result.
bool eval_child(persistence::Connection& conn, const nlohmann::json& child,
                const TriggerContext& ctx, int depth) {
    if (!child.is_object()) return false;
    auto kind_it = child.find("kind");
    auto spec_it = child.find("spec");
    if (kind_it == child.end() || !kind_it->is_string()) return false;
    if (spec_it == child.end()) return false;
    return eval_dispatch(conn, kind_it->get<std::string>(), *spec_it, ctx, depth);
}

bool eval_compound(persistence::Connection& conn, const nlohmann::json& spec,
                   const TriggerContext& ctx, int depth) {
    auto all_it = spec.find("all_of");
    if (all_it != spec.end() && all_it->is_array()) {
        for (const auto& child : *all_it) {
            if (!eval_child(conn, child, ctx, depth)) return false;
        }
        return true;
    }
    auto any_it = spec.find("any_of");
    if (any_it != spec.end() && any_it->is_array()) {
        for (const auto& child : *any_it) {
            if (eval_child(conn, child, ctx, depth)) return true;
        }
        return false;
    }
    return false;
}

bool eval_dispatch(persistence::Connection& conn, const std::string& kind,
                   const nlohmann::json& spec_obj, const TriggerContext& ctx,
                   int depth) {
    if (depth > kMaxCompoundDepth) return false;  // over-deep nesting → non-match
    if (!spec_obj.is_object()) return false;      // malformed spec → non-match
    if (kind == "time")     return eval_time(spec_obj, ctx);
    if (kind == "event")    return eval_event(spec_obj, ctx);
    if (kind == "state")    return eval_state(conn, spec_obj, ctx);
    if (kind == "compound") return eval_compound(conn, spec_obj, ctx, depth + 1);
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

    return eval_dispatch(conn, std::string(kind), spec, ctx, /*depth=*/0);
}

}  // namespace starling::prospective
