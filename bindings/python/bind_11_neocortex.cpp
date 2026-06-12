// bind_11_neocortex — M0.8/P2.j: CommonGroundWriter / PersonaContainer / CommonGroundContainer / _common_ground_tick
// Split verbatim from bindings/python/module.cpp (original lines 1452-1578).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include <vector>
#include "starling/tom/common_ground_writer.hpp"
#include "starling/tom/common_ground_subscriber.hpp"
#include "starling/neocortex/persona_container.hpp"
#include "starling/neocortex/common_ground_container.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::bindings {

void bind_11_neocortex(pybind11::module_& m) {
    using namespace pybind11::literals;

    // ── M0.8: CommonGroundWriter ──────────────────────────────────────────

    py::class_<starling::tom::CommonGroundWriter>(m, "CommonGroundWriter")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("assert_",
             [](starling::tom::CommonGroundWriter& s,
                std::string tenant_id, std::string stmt_id,
                std::vector<std::string> parties, std::string now) {
                 return s.assert_(s.connection(), tenant_id, stmt_id, parties, now);
             },
             py::arg("tenant_id"), py::arg("stmt_id"),
             py::arg("parties"), py::arg("now_iso"))
        .def("acknowledge",
             [](starling::tom::CommonGroundWriter& s,
                std::string cg_id, std::string actor, std::string now) {
                 s.acknowledge(s.connection(), cg_id, actor, now);
             },
             py::arg("cg_id"), py::arg("actor"), py::arg("now_iso"))
        .def("repair",
             [](starling::tom::CommonGroundWriter& s,
                std::string cg_id, std::string actor, std::string now) {
                 s.repair(s.connection(), cg_id, actor, now);
             },
             py::arg("cg_id"), py::arg("actor"), py::arg("now_iso"))
        .def("withdraw",
             [](starling::tom::CommonGroundWriter& s,
                std::string cg_id, std::string actor, std::string now) {
                 s.withdraw(s.connection(), cg_id, actor, now);
             },
             py::arg("cg_id"), py::arg("actor"), py::arg("now_iso"))
        .def("supersede_ground",
             [](starling::tom::CommonGroundWriter& s,
                std::string old_cg_id, std::string new_stmt_id, std::string now) {
                 s.supersede_ground(s.connection(), old_cg_id, new_stmt_id, now);
             },
             py::arg("old_cg_id"), py::arg("new_stmt_id"), py::arg("now_iso"))
        .def("sweep_timeout_downgrade",
             [](starling::tom::CommonGroundWriter& s, std::string now) {
                 return s.sweep_timeout_downgrade(s.connection(), now);
             },
             py::arg("now_iso"))
        // P3.a2: 七幕补全。
        .def("expire_ground",
             [](starling::tom::CommonGroundWriter& s,
                std::string cg_id, std::string actor, std::string now) {
                 s.expire_ground(s.connection(), cg_id, actor, now);
             },
             py::arg("cg_id"), py::arg("actor"), py::arg("now_iso"))
        .def("unground",
             [](starling::tom::CommonGroundWriter& s,
                std::string cg_id, std::string actor, std::string now) {
                 s.unground(s.connection(), cg_id, actor, now);
             },
             py::arg("cg_id"), py::arg("actor"), py::arg("now_iso"))
        .def("acknowledge_manual",
             [](starling::tom::CommonGroundWriter& s,
                std::string cg_id, std::string audit_actor, std::string now) {
                 s.acknowledge_manual(s.connection(), cg_id, audit_actor, now);
             },
             py::arg("cg_id"), py::arg("audit_actor"), py::arg("now_iso"));

    // ── M0.8: PersonaContainer + AnchorStatement + ConcurrentRebuildError ─

    py::class_<starling::neocortex::PersonaView>(m, "PersonaView")
        .def_readonly("found",      &starling::neocortex::PersonaView::found)
        .def_readonly("tenant_id",  &starling::neocortex::PersonaView::tenant_id)
        .def_readonly("holder_id",  &starling::neocortex::PersonaView::holder_id)
        .def_readonly("version",    &starling::neocortex::PersonaView::version)
        .def_readonly("dimensions", &starling::neocortex::PersonaView::dimensions);

    py::class_<starling::neocortex::AnchorStatement>(m, "AnchorStatement")
        .def(py::init<>())
        .def(py::init([](std::string stmt_id, std::string anchor_type,
                         std::string dimension, std::string value, double confidence) {
            return starling::neocortex::AnchorStatement{
                std::move(stmt_id), std::move(anchor_type),
                std::move(dimension), std::move(value), confidence};
        }),
        py::arg("stmt_id") = "",
        py::arg("anchor_type") = "",
        py::arg("dimension") = "",
        py::arg("value") = "",
        py::arg("confidence") = 0.0)
        .def_readwrite("stmt_id",     &starling::neocortex::AnchorStatement::stmt_id)
        .def_readwrite("anchor_type", &starling::neocortex::AnchorStatement::anchor_type)
        .def_readwrite("dimension",   &starling::neocortex::AnchorStatement::dimension)
        .def_readwrite("value",       &starling::neocortex::AnchorStatement::value)
        .def_readwrite("confidence",  &starling::neocortex::AnchorStatement::confidence);

    py::register_exception<starling::neocortex::ConcurrentRebuildError>(
        m, "ConcurrentRebuildError", PyExc_RuntimeError);

    py::class_<starling::neocortex::PersonaContainer>(m, "PersonaContainer")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("rebuild",
             [](starling::neocortex::PersonaContainer& s,
                std::string tenant_id, std::string holder_id,
                std::vector<starling::neocortex::AnchorStatement> sources,
                std::string now_iso) {
                 s.rebuild(s.connection(), tenant_id, holder_id, sources, now_iso);
             },
             py::arg("tenant_id"), py::arg("holder_id"), py::arg("sources"),
             py::arg("now_iso"))
        .def("read",
             [](starling::neocortex::PersonaContainer& self,
                const std::string& tenant_id, const std::string& holder_id) {
                 return self.read(self.connection(), tenant_id, holder_id);
             },
             py::arg("tenant_id"), py::arg("holder_id"));

    // ── M0.8: CommonGroundContainer ───────────────────────────────────────

    py::class_<starling::neocortex::CommonGroundView>(m, "CommonGroundView")
        .def_readonly("found",             &starling::neocortex::CommonGroundView::found)
        .def_readonly("tenant_id",         &starling::neocortex::CommonGroundView::tenant_id)
        .def_readonly("cg_ref",            &starling::neocortex::CommonGroundView::cg_ref)
        .def_readonly("version",           &starling::neocortex::CommonGroundView::version)
        .def_readonly("grounded",          &starling::neocortex::CommonGroundView::grounded)
        .def_readonly("asserted_unack",    &starling::neocortex::CommonGroundView::asserted_unack)
        .def_readonly("suspected_diverge", &starling::neocortex::CommonGroundView::suspected_diverge);

    py::class_<starling::neocortex::CommonGroundContainer>(m, "CommonGroundContainer")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("rebuild",
             [](starling::neocortex::CommonGroundContainer& s,
                std::string tenant_id, std::string cg_ref, std::string now_iso) {
                 s.rebuild(s.connection(), tenant_id, cg_ref, now_iso);
             },
             py::arg("tenant_id"), py::arg("cg_ref"), py::arg("now_iso"))
        .def("read",
             [](starling::neocortex::CommonGroundContainer& self,
                const std::string& tenant_id, const std::string& cg_ref) {
                 return self.read(self.connection(), tenant_id, cg_ref);
             },
             py::arg("tenant_id"), py::arg("cg_ref"));

    // P2.j: CommonGroundSubscriber tick（供 Memory.tick / 测试确定性 flush 滞后事件）
    m.def("_common_ground_tick",
          [](starling::persistence::SqliteAdapter& adapter, const std::string& now_iso) {
              return starling::tom::CommonGroundSubscriber::tick_one_batch(
                  adapter, adapter.connection(), now_iso);
          },
          py::arg("adapter"), py::arg("now_iso"));
}

}  // namespace starling::bindings
