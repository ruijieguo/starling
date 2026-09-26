#pragma once

#include <string>
#include <nlohmann/json.hpp>
#include "starling/persistence/connection.hpp"
#include "starling/retrieval/retrieval_receipt.hpp"
#include "starling/retrieval/statement_row.hpp"

namespace starling::retrieval {
// Empty evidence is the legacy path. Contract errors are returned as stable
// receipt reason keys; source metadata lookup always includes the row tenant.
std::string claim_evidence_error(persistence::Connection& conn, const StatementRow& row);
void record_claim_exclusion(RetrievalReceipt& receipt, const std::string& tenant_id,
                            const std::string& statement_id, const std::string& reason);
void record_claim_link(persistence::Connection& conn, RetrievalReceipt& receipt, const StatementRow& row);
nlohmann::json parse_claim_evidence(const StatementRow& row);
}  // namespace starling::retrieval
