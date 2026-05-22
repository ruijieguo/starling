#pragma once

#include <stdexcept>
#include <string>
#include <string_view>

namespace starling {

class FinalQueryAssertionError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

// Throws FinalQueryAssertionError if the SQL string lacks both required guard
// predicates: a tenant_id reference outside any -- comment AND a holder_scope
// reference outside any -- comment. Case-insensitive. Parenthesized predicates
// and IN(...) clauses are allowed.
//
// This is M0.0's runtime defense for TC-NEG-TENANT and TC-NEW-PREFLIGHT branch (c).
// Adapter implementations MUST call this before issuing any final SELECT/UPDATE/DELETE.
void assert_final_query_safe(std::string_view sql);

// Pure predicate variant for tests / programmatic checks. Returns true iff sql
// passes all guards.
bool is_final_query_safe(std::string_view sql) noexcept;

}  // namespace starling
