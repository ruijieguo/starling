// bind_12_prospective — P2.c: affect / ActionGuard / CommitmentEngine / PolicyEngine
// Split verbatim from bindings/python/module.cpp (original lines 1580-1698).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include "starling/affect/affect_vector.hpp"
#include "starling/prospective/action_guard.hpp"
#include "starling/prospective/commitment_engine.hpp"
#include "starling/prospective/policy_engine.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::bindings {

void bind_12_prospective(pybind11::module_& m) {
    using namespace pybind11::literals;

    // ── P2.c: affect ──────────────────────────────────────────────────────

    py::class_<starling::affect::AffectVector>(m, "AffectVector")
        .def(py::init<>())
        .def_readwrite("valence",   &starling::affect::AffectVector::valence)
        .def_readwrite("arousal",   &starling::affect::AffectVector::arousal)
        .def_readwrite("dominance", &starling::affect::AffectVector::dominance)
        .def_readwrite("novelty",   &starling::affect::AffectVector::novelty)
        .def_readwrite("stakes",    &starling::affect::AffectVector::stakes);

    m.def("affect_salience", &starling::affect::salience,
          py::arg("v"), py::arg("surprise_decay") = 1.0);
    m.def("affect_parse_json", &starling::affect::parse_affect_json,
          py::arg("json"));

    // ── P2.c: prospective ActionGuard ─────────────────────────────────────

    py::class_<starling::prospective::ActionGuard>(m, "ActionGuard")
        .def(py::init<>())
        .def_readwrite("profile_name",
                       &starling::prospective::ActionGuard::profile_name)
        .def_readwrite("allowed_actions",
                       &starling::prospective::ActionGuard::allowed_actions)
        .def_readwrite("requires_approval",
                       &starling::prospective::ActionGuard::requires_approval)
        .def_readwrite("idempotency_window_sec",
                       &starling::prospective::ActionGuard::idempotency_window_sec);

    py::enum_<starling::prospective::GuardVerdict>(m, "GuardVerdict")
        .value("Allow",            starling::prospective::GuardVerdict::Allow)
        .value("RequiresApproval", starling::prospective::GuardVerdict::RequiresApproval)
        .value("Blocked",          starling::prospective::GuardVerdict::Blocked);

    m.def("action_guard_check", &starling::prospective::check,
          py::arg("guard"), py::arg("action_name"));

    // ── P2.c: prospective CommitmentView (read result) ────────────────────

    py::class_<starling::prospective::CommitmentView>(m, "CommitmentView")
        .def_readonly("stmt_id",      &starling::prospective::CommitmentView::stmt_id)
        .def_readonly("state",        &starling::prospective::CommitmentView::state)
        .def_readonly("deadline",     &starling::prospective::CommitmentView::deadline)
        .def_readonly("subject_id",   &starling::prospective::CommitmentView::subject_id)
        .def_readonly("predicate",    &starling::prospective::CommitmentView::predicate)
        .def_readonly("object_value", &starling::prospective::CommitmentView::object_value)
        .def_readonly("fired",        &starling::prospective::CommitmentView::fired);

    // ── P2.c: prospective CommitmentEngine (conn-free) ────────────────────

    py::class_<starling::prospective::CommitmentEngine>(m, "CommitmentEngine")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("create_from_statement",
             [](starling::prospective::CommitmentEngine& s,
                std::string stmt_id, std::string tenant, std::string deadline,
                std::string now) {
                 s.create_from_statement(s.connection(), stmt_id, tenant,
                                         deadline, now);
             },
             py::arg("stmt_id"), py::arg("tenant_id"),
             py::arg("deadline"), py::arg("now_iso"))
        .def("fulfill",
             [](starling::prospective::CommitmentEngine& s,
                std::string stmt_id, std::string tenant, std::string now) {
                 return s.fulfill(s.connection(), stmt_id, tenant, now);
             },
             py::arg("stmt_id"), py::arg("tenant_id"), py::arg("now_iso"))
        .def("withdraw",
             [](starling::prospective::CommitmentEngine& s,
                std::string stmt_id, std::string tenant, std::string now) {
                 return s.withdraw(s.connection(), stmt_id, tenant, now);
             },
             py::arg("stmt_id"), py::arg("tenant_id"), py::arg("now_iso"))
        .def("on_deadline_expired",
             [](starling::prospective::CommitmentEngine& s,
                std::string stmt_id, std::string tenant, std::string now) {
                 s.on_deadline_expired(s.connection(), stmt_id, tenant, now);
             },
             py::arg("stmt_id"), py::arg("tenant_id"), py::arg("now_iso"))
        .def("renegotiate",
             [](starling::prospective::CommitmentEngine& s,
                std::string old_stmt_id, std::string new_stmt_id,
                std::string tenant, std::string now) {
                 return s.renegotiate(s.connection(), old_stmt_id,
                                      new_stmt_id, tenant, now);
             },
             py::arg("old_stmt_id"), py::arg("new_stmt_id"),
             py::arg("tenant_id"), py::arg("now_iso"))
        .def("pending",
             [](starling::prospective::CommitmentEngine& self,
                const std::string& tenant_id, const std::string& holder_id,
                const std::string& interlocutor_id) {
                 return self.pending(self.connection(), tenant_id, holder_id, interlocutor_id);
             },
             py::arg("tenant_id"), py::arg("holder_id"), py::arg("interlocutor_id"));

    // ── P2.c: prospective PolicyEngine (conn-free) ────────────────────────

    py::class_<starling::prospective::PolicyTickStats>(m, "PolicyTickStats")
        .def_readonly("fired",
                      &starling::prospective::PolicyTickStats::fired)
        .def_readonly("broken",
                      &starling::prospective::PolicyTickStats::broken)
        .def_readonly("auto_withdrawn",
                      &starling::prospective::PolicyTickStats::auto_withdrawn);

    py::class_<starling::prospective::PolicyEngine>(m, "PolicyEngine")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("run_post_write",
             [](starling::prospective::PolicyEngine& s, std::string now) {
                 s.run_post_write(s.connection(), now);
             },
             py::arg("now_iso"))
        .def("tick",
             [](starling::prospective::PolicyEngine& s, std::string now) {
                 return s.tick(s.connection(), now);
             },
             py::arg("now_iso"));
}

}  // namespace starling::bindings
