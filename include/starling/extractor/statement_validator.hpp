#pragma once

#include "starling/extractor/extracted_statement.hpp"
#include "starling/schema/statement_enums.hpp"

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

}  // namespace starling::extractor
