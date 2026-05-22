#pragma once

#include <string>

#include "starling/profile_capability.hpp"

namespace starling {

// Minimal Adapter contract for M0.0. Concrete backends arrive in M0.2.
// Today the abstract class only fixes the two contracts every adapter must honor:
// (1) declare_capability returns the ProfileCapability used by preflight,
// (2) check_final_query gates every read/write SQL against tenant + holder predicates.
class Adapter {
public:
    Adapter() = default;
    virtual ~Adapter() = default;

    Adapter(const Adapter&) = delete;
    Adapter& operator=(const Adapter&) = delete;
    Adapter(Adapter&&) = delete;
    Adapter& operator=(Adapter&&) = delete;

    virtual ProfileCapability declare_capability() const = 0;

    // Returns true if the SQL string contains required tenant_id and holder_scope predicates.
    // Used by final_query_assertion. Concrete adapters should call this before issuing queries.
    virtual bool check_final_query(const std::string& sql) const = 0;
};

}  // namespace starling
