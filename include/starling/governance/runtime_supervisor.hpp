#ifndef STARLING_GOVERNANCE_RUNTIME_SUPERVISOR_HPP
#define STARLING_GOVERNANCE_RUNTIME_SUPERVISOR_HPP

#include <functional>
#include <string>
#include <vector>

#include "starling/profile_capability.hpp"
#include "starling/runtime_health.hpp"

namespace starling::persistence {
class SqliteAdapter;  // fwd-decl; production ctor binds its has_index()
}  // namespace starling::persistence

namespace starling::governance {

inline constexpr int kExConfig = 78;  // POSIX EX_CONFIG; was runtime.py:15

enum class StartOutcome { kReady, kUnready };
enum class WriteGateDecision { kAccept, kPreconditionFailed };

// Supervisor-level view mirroring 05_governance.md:133-137's
// PreflightResult{passed, missing_capabilities, warnings}. WRAPS the core
// starling::PreflightResult: passed = (no missing), missing_capabilities = the
// core `missing` list (+ the index name when absent). `warnings` exists for
// spec-shape parity; Phase 1 leaves it empty (Phase 2 populates it).
struct PreflightReport {
  bool passed = false;
  std::vector<std::string> missing_capabilities;
  std::vector<std::string> warnings;
};

// Phase-1 governance supervisor: capability+index preflight -> READY/UNREADY,
// fail-closed EX_CONFIG exit, READY write-gate. Holds its OWN RuntimeHealth
// (READY/UNREADY only in Phase 1) as a plain member; the RuntimeHealthMonitor,
// the runtime.health_changed event log, and events() are Phase 2 -- NOT here.
// Not thread-safe (single supervisor caller, mirrors runtime_health.hpp).
class RuntimeSupervisor {
 public:
  // PRODUCTION ctor: index probe is C++ -- it calls
  // adapter.has_index("idx_statement_id_tenant"). `adapter` MUST outlive this.
  RuntimeSupervisor(ProfileCapability caps, bool embedded,
                    starling::persistence::SqliteAdapter& adapter);

  // C++ UNIT-TEST SEAM ONLY: inject the index-present predicate directly.
  RuntimeSupervisor(ProfileCapability caps, bool embedded,
                    std::function<bool()> idx_present);

  PreflightReport run_preflight() const;
  StartOutcome start();
  RuntimeHealth health() const noexcept { return health_; }
  int exit_code() const noexcept { return exit_code_; }
  WriteGateDecision check_write() const noexcept;

 private:
  ProfileCapability caps_;
  bool embedded_;
  std::function<bool()> idx_present_;
  RuntimeHealth health_ = RuntimeHealth::UNREADY;
  int exit_code_ = 0;
};

}  // namespace starling::governance

#endif
