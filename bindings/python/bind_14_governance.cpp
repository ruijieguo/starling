// bind_14_governance — P3.c1 Phase 1: RuntimeSupervisor (capability+index
// preflight -> READY/UNREADY, exit-78, write-gate) bound FLAT on _core.
// Registered after bind_13; requires ProfileCapability/RuntimeHealth (bind_01)
// and SqliteAdapter (bind_02) to be registered first.

#include "bind_common.hpp"

#include <pybind11/functional.h>
#include <pybind11/stl.h>

#include "starling/governance/capability_policy.hpp"
#include "starling/governance/runtime_supervisor.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/profile_capability.hpp"

namespace starling::bindings {

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
        .def("check_write", &gov::RuntimeSupervisor::check_write);
}

}  // namespace starling::bindings
