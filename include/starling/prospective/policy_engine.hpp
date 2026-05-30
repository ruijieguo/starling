#pragma once
#include "starling/prospective/commitment_engine.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::prospective {

struct PolicyTickStats { int fired = 0; int broken = 0; int auto_withdrawn = 0; };

class PolicyEngine {
public:
    explicit PolicyEngine(persistence::SqliteAdapter& a) : adapter_(a), commitment_engine_(a) {}
    void run_post_write(persistence::Connection&, std::string_view now_iso);
    PolicyTickStats tick(persistence::Connection&, std::string_view now_iso);
    persistence::Connection& connection() { return adapter_.connection(); }
private:
    persistence::SqliteAdapter& adapter_;
    CommitmentEngine commitment_engine_;
};

}  // namespace starling::prospective
