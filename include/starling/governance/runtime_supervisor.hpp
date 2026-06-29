#ifndef STARLING_GOVERNANCE_RUNTIME_SUPERVISOR_HPP
#define STARLING_GOVERNANCE_RUNTIME_SUPERVISOR_HPP

#include <cstddef>
#include <cstdint>
#include <functional>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

#include "starling/governance/runtime_health_event.hpp"
#include "starling/profile_capability.hpp"
#include "starling/runtime_health.hpp"

namespace starling::persistence {
class SqliteAdapter;  // fwd-decl; production ctor binds its has_index()
}  // namespace starling::persistence

namespace starling::governance {

inline constexpr int kExConfig = 78;  // POSIX EX_CONFIG; was runtime.py:15

enum class StartOutcome : std::uint8_t { kReady, kUnready };
enum class WriteGateDecision : std::uint8_t { kAccept, kPreconditionFailed };

// Supervisor-level view mirroring 05_governance.md:133-137's PreflightResult.
struct PreflightReport {
  bool passed = false;
  std::vector<std::string> missing_capabilities;
  std::vector<std::string> warnings;
};

// Phase-2 governance supervisor: the full RuntimeHealth 4-state machine
// (READY/DEGRADED/DRAINING/UNREADY) with validated transitions + an internal
// event log, atop Phase 1's capability+index preflight / exit-78 / write gate.
// Self-synchronizing: a single mutex guards all mutable state, so the dashboard
// read path (worker thread) is safe against the drain/sampler mutators. Holds
// NO external callback; the event log is read via events()/last_event()
// snapshots. Real metric sampling that drives DEGRADED is Phase 5; Phase 2
// transitions come from start(), begin_drain(), and note_health() (test/Phase-5).
class RuntimeSupervisor {
 public:
  // PRODUCTION ctor: index probe is C++ (adapter.has_index). `adapter` MUST
  // outlive this supervisor.
  RuntimeSupervisor(ProfileCapability caps, bool embedded,
                    starling::persistence::SqliteAdapter& adapter);

  // C++ UNIT-TEST SEAM ONLY: inject the index-present predicate directly.
  RuntimeSupervisor(ProfileCapability caps, bool embedded,
                    std::function<bool()> idx_present);

  [[nodiscard]] PreflightReport run_preflight() const;
  StartOutcome start();

  // Apply a health decision (Phase 5's sampler produces these; Phase 2: tests).
  void note_health(const HealthDecision& decision);
  // Enter DRAINING (host shutdown). No-op if the transition is illegal.
  void begin_drain(std::string trigger = "admin_drain");

  [[nodiscard]] RuntimeHealth health() const;
  [[nodiscard]] int exit_code() const;
  [[nodiscard]] WriteGateDecision check_write() const;
  [[nodiscard]] std::vector<RuntimeHealthEvent> events() const;        // snapshot copy
  [[nodiscard]] std::optional<RuntimeHealthEvent> last_event() const;  // snapshot copy

 private:
  // OV-1: lock-assuming helpers. Public methods lock mtx_ then delegate here;
  // internal call paths use ONLY these (never the public locked overloads),
  // which is what prevents start()->run_preflight() self-deadlock on the
  // non-recursive mutex.
  [[nodiscard]] PreflightReport run_preflight_locked() const;
  // Returns true iff the transition was legal (and applied). Emits an event iff
  // from != target OR target == UNREADY (OV-3); caps the log at kMaxEvents.
  bool transition_to_locked(RuntimeHealth target, std::string trigger,
                            MetricsSnapshot snapshot,
                            std::vector<std::string> missing);

  static constexpr std::size_t kMaxEvents = 64;  // D-P2-3 event-log retention cap

  mutable std::mutex mtx_;
  ProfileCapability caps_;
  bool embedded_;
  std::function<bool()> idx_present_;
  RuntimeHealth health_ = RuntimeHealth::UNREADY;
  int exit_code_ = 0;
  std::vector<RuntimeHealthEvent> events_;
};

}  // namespace starling::governance

#endif
