#pragma once

#include "starling/extractor/extracted_statement.hpp"
#include "starling/schema/statement_enums.hpp"

#include <functional>
#include <optional>
#include <string>

namespace starling::extractor {

struct ValidationOutcome {
    bool                                accepted = false;
    std::string                         error_kind;     // empty when accepted
    std::string                         detail;         // human-readable
    std::optional<schema::ReviewStatus> review_status_override;  // set when accepted but downgraded

    bool ok() const { return accepted; }
};

// M0.4 minimal validator. Enforces the §15.3.1 EXTRACTOR contracts
// (TC-Q2-001..004) and the §15.3.2 confidence / review_status defaults.
// Does NOT enforce cross-tenant explicit-protocol path (§3.11 — M0.5+)
// and does NOT run ConflictProbe (M0.5). Pure function: no DB, no I/O.
ValidationOutcome validate_extracted_statement(const ExtractedStatement& s);

// M0.7: cross-tenant derived_from gate (§15.3.1 TC-NEG-CROSSTENANT).
// Runs the base validator first; on success, checks each parent id via
// resolve_parent_tenant. If a parent lives in a different tenant and
// provenance_protocol_id is empty, returns a rejection with
// error_kind="cross_tenant_derivation_forbidden". If protocol_id is set,
// returns accepted with review_status_override=REVIEW_REQUESTED.
// resolve_parent_tenant must return:
//   - the parent tenant when exactly one parent row is found,
//   - "" when the parent row is not found,
//   - an error sentinel (for example "ambiguous:<id>") when the bare
//     StatementRef is not enough to resolve a unique (id, tenant_id) row.
ValidationOutcome validate_for_write(
    const ExtractedStatement& s,
    const std::function<std::string(const std::string&)>& resolve_parent_tenant);

}  // namespace starling::extractor
