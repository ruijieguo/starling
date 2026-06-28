// bind_14_governance — P3.c1 Phase 1: RuntimeSupervisor (capability+index
// preflight -> READY/UNREADY, exit-78, write-gate) bound FLAT on _core.
// Registered after bind_13; requires ProfileCapability/RuntimeHealth (bind_01)
// and SqliteAdapter (bind_02) to be registered first.

#include "bind_common.hpp"

#include <pybind11/functional.h>
#include <pybind11/stl.h>

#include "starling/governance/capability_policy.hpp"
#include "starling/governance/runtime_health_event.hpp"
#include "starling/governance/runtime_supervisor.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/profile_capability.hpp"

namespace starling::bindings {

// NOLINTNEXTLINE(readability-identifier-length) — `m` matches all 13 sibling bind_NN units (module handle)
void bind_14_governance(pybind11::module_& m) {
    using namespace pybind11::literals;
    namespace gov = starling::governance;

    m.attr("kExConfig") = gov::kExConfig;

    m.def("required_capabilities", &gov::required_capabilities, py::arg("embedded"),
          "Pure effective required-capability list for a profile "
          "(embedded=True waives the deferred caps). No global state.");

    py::enum_<gov::StartOutcome>(m, "StartOutcome")
        .value("kReady", gov::StartOutcome::kReady)
        .value("kUnready", gov::StartOutcome::kUnready);

    py::enum_<gov::WriteGateDecision>(m, "WriteGateDecision")
        .value("kAccept", gov::WriteGateDecision::kAccept)
        .value("kPreconditionFailed", gov::WriteGateDecision::kPreconditionFailed);

    py::class_<gov::PreflightReport>(m, "PreflightReport")
        .def_readonly("passed", &gov::PreflightReport::passed)
        .def_readonly("missing_capabilities", &gov::PreflightReport::missing_capabilities)
        .def_readonly("warnings", &gov::PreflightReport::warnings);

    // Value types backing the event log (Task 2.1). MetricsSnapshot + HealthDecision
    // are also constructible from Python (def_readwrite + default init): HealthDecision
    // is the note_health() input; Phase 2 metrics are all 0 (Phase 5 fills them).
    // RuntimeHealthEvent is pure OUTPUT (events()/last_event()) — def_readonly, no init.
    py::class_<gov::MetricsSnapshot>(m, "MetricsSnapshot")
        .def(py::init<>())
        .def_readwrite("outbox_lag_sequence", &gov::MetricsSnapshot::outbox_lag_sequence)
        .def_readwrite("subscriber_failure_rate", &gov::MetricsSnapshot::subscriber_failure_rate)
        .def_readwrite("extraction_queue_depth", &gov::MetricsSnapshot::extraction_queue_depth)
        .def_readwrite("projection_lag_seconds", &gov::MetricsSnapshot::projection_lag_seconds)
        .def_readwrite("runtime_event_loop_lag_ms", &gov::MetricsSnapshot::runtime_event_loop_lag_ms)
        .def_readwrite("vector_delete_lag", &gov::MetricsSnapshot::vector_delete_lag)
        .def_readwrite("erased_evidence_visible_count",
                       &gov::MetricsSnapshot::erased_evidence_visible_count);

    py::class_<gov::RuntimeHealthEvent>(m, "RuntimeHealthEvent")
        .def_readonly("previous_status", &gov::RuntimeHealthEvent::previous_status)
        .def_readonly("current_status", &gov::RuntimeHealthEvent::current_status)
        .def_readonly("trigger", &gov::RuntimeHealthEvent::trigger)
        .def_readonly("metrics_snapshot", &gov::RuntimeHealthEvent::metrics_snapshot)
        .def_readonly("missing_capabilities", &gov::RuntimeHealthEvent::missing_capabilities);

    py::class_<gov::HealthDecision>(m, "HealthDecision")
        .def(py::init<>())
        .def_readwrite("target_status", &gov::HealthDecision::target_status)
        .def_readwrite("trigger", &gov::HealthDecision::trigger)
        .def_readwrite("metrics_snapshot", &gov::HealthDecision::metrics_snapshot);

    py::class_<gov::RuntimeSupervisor>(m, "RuntimeSupervisor")
        // Production ctor FIRST: binds the C++ index probe (adapter.has_index).
        // keep_alive<1,4>: the supervisor stores a lambda capturing a reference
        // to `adapter` (arg 4), so the adapter must outlive the supervisor (arg 1).
        .def(py::init<starling::ProfileCapability, bool,
                      starling::persistence::SqliteAdapter&>(),
             py::arg("caps"), py::arg("embedded"), py::arg("adapter"),
             py::keep_alive<1, 4>())
        // Test-seam ctor: a Python callable becomes std::function<bool()>.
        .def(py::init<starling::ProfileCapability, bool, std::function<bool()>>(),
             py::arg("caps"), py::arg("embedded"), py::arg("idx_present"))
        .def("run_preflight", &gov::RuntimeSupervisor::run_preflight)
        .def("start", &gov::RuntimeSupervisor::start)
        .def("health", &gov::RuntimeSupervisor::health)
        .def("exit_code", &gov::RuntimeSupervisor::exit_code)
        .def("check_write", &gov::RuntimeSupervisor::check_write)
        .def("note_health", &gov::RuntimeSupervisor::note_health, py::arg("decision"))
        .def("begin_drain", &gov::RuntimeSupervisor::begin_drain,
             py::arg("trigger") = "admin_drain")  // OV-8: wire the C++ default
        .def("events", &gov::RuntimeSupervisor::events)        // OV-2: DEFAULT (copy) policy
        .def("last_event", &gov::RuntimeSupervisor::last_event);  // OV-6
}

}  // namespace starling::bindings
