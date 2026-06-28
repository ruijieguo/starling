#include "starling/governance/runtime_supervisor.hpp"

#include <string_view>
#include <utility>

#include "starling/governance/capability_policy.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/preflight.hpp"

namespace starling::governance {

namespace {
// Legacy compatibility probe: has_index() proves a named SQLite index EXISTS;
// it does NOT prove tenant-isolation semantics (the (id, tenant_id)
// composite-key invariant). Kept because TC-NEW-PREFLIGHT pins this index.
constexpr std::string_view kLegacyTenantIndex = "idx_statement_id_tenant";
}  // namespace

RuntimeSupervisor::RuntimeSupervisor(ProfileCapability caps, bool embedded,
                                     starling::persistence::SqliteAdapter& adapter)
    : caps_(std::move(caps)),
      embedded_(embedded),
      idx_present_([&adapter]() { return adapter.has_index(kLegacyTenantIndex); }) {}

RuntimeSupervisor::RuntimeSupervisor(ProfileCapability caps, bool embedded,
                                     std::function<bool()> idx_present)
    : caps_(std::move(caps)),
      embedded_(embedded),
      idx_present_(std::move(idx_present)) {}

PreflightReport RuntimeSupervisor::run_preflight() const {
  const std::vector<std::string> required = required_capabilities(embedded_);
  const PreflightResult result = preflight(caps_, required);
  PreflightReport report;
  report.missing_capabilities = result.missing;
  if (!idx_present_()) {
    report.missing_capabilities.emplace_back(kLegacyTenantIndex);
  }
  report.passed = report.missing_capabilities.empty();
  return report;
}

StartOutcome RuntimeSupervisor::start() {
  if (run_preflight().passed) {
    health_ = RuntimeHealth::READY;
    return StartOutcome::kReady;
  }
  health_ = RuntimeHealth::UNREADY;
  exit_code_ = kExConfig;  // fail-closed; set once, never cleared
  return StartOutcome::kUnready;
}

WriteGateDecision RuntimeSupervisor::check_write() const noexcept {
  return health_ == RuntimeHealth::READY
             ? WriteGateDecision::kAccept
             : WriteGateDecision::kPreconditionFailed;
}

}  // namespace starling::governance
