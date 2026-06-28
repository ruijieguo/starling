#include "starling/governance/runtime_supervisor.hpp"

#include <mutex>
#include <string_view>
#include <utility>

#include "starling/governance/capability_policy.hpp"
#include "starling/governance/runtime_health_event.hpp"
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
  const std::lock_guard<std::mutex> lock(mtx_);
  return run_preflight_locked();
}

PreflightReport RuntimeSupervisor::run_preflight_locked() const {
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
  const std::lock_guard<std::mutex> lock(mtx_);
  const PreflightReport report = run_preflight_locked();
  if (report.passed) {
    transition_to_locked(RuntimeHealth::READY, "preflight_passed", MetricsSnapshot{},
                         {});
    return StartOutcome::kReady;
  }
  transition_to_locked(RuntimeHealth::UNREADY, "preflight_failed", MetricsSnapshot{},
                       report.missing_capabilities);
  exit_code_ = kExConfig;  // OV-4: under lock, outside transition_to_locked; set once
  return StartOutcome::kUnready;
}

void RuntimeSupervisor::note_health(const HealthDecision& decision) {
  const std::lock_guard<std::mutex> lock(mtx_);
  transition_to_locked(decision.target_status, decision.trigger,
                       decision.metrics_snapshot, {});
}

void RuntimeSupervisor::begin_drain(std::string trigger) {
  const std::lock_guard<std::mutex> lock(mtx_);
  transition_to_locked(RuntimeHealth::DRAINING, std::move(trigger), MetricsSnapshot{},
                       {});
}

RuntimeHealth RuntimeSupervisor::health() const {
  const std::lock_guard<std::mutex> lock(mtx_);
  return health_;
}

int RuntimeSupervisor::exit_code() const {
  const std::lock_guard<std::mutex> lock(mtx_);
  return exit_code_;
}

WriteGateDecision RuntimeSupervisor::check_write() const {
  const std::lock_guard<std::mutex> lock(mtx_);
  // D-P2-5: foreground writes continue in READY and DEGRADED; rejected in
  // UNREADY (fail-closed) and DRAINING (retry_after is Phase 5).
  const bool accept = (health_ == RuntimeHealth::READY) ||
                      (health_ == RuntimeHealth::DEGRADED);
  return accept ? WriteGateDecision::kAccept
                : WriteGateDecision::kPreconditionFailed;
}

std::vector<RuntimeHealthEvent> RuntimeSupervisor::events() const {
  const std::lock_guard<std::mutex> lock(mtx_);
  return events_;  // OV-2: snapshot copy, never a reference into events_
}

std::optional<RuntimeHealthEvent> RuntimeSupervisor::last_event() const {
  const std::lock_guard<std::mutex> lock(mtx_);
  if (events_.empty()) {
    return std::nullopt;
  }
  return events_.back();
}

bool RuntimeSupervisor::transition_to_locked(RuntimeHealth target,
                                             std::string trigger,
                                             MetricsSnapshot snapshot,
                                             std::vector<std::string> missing) {
  if (!is_legal_transition(health_, target)) {
    return false;  // illegal: no state change, no event (no callback under lock)
  }
  const bool should_emit =
      (health_ != target) || (target == RuntimeHealth::UNREADY);  // OV-3
  const RuntimeHealth previous = health_;
  health_ = target;
  if (should_emit) {
    events_.push_back(RuntimeHealthEvent{
        .previous_status = previous,
        .current_status = target,
        .trigger = std::move(trigger),
        .metrics_snapshot = snapshot,
        .missing_capabilities = std::move(missing),
    });
    if (events_.size() > kMaxEvents) {
      events_.erase(events_.begin());  // D-P2-3: FIFO, drop the oldest
    }
  }
  return true;
}

}  // namespace starling::governance
