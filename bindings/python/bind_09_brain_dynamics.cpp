// bind_09_brain_dynamics — M0.8: ReplayScheduler / ReconsolidationEngine / ProjectionMaintainer
// Split verbatim from bindings/python/module.cpp (original lines 1172-1281).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include <vector>
#include "starling/replay/replay_scheduler.hpp"
#include "starling/reconsolidation/reconsolidation_engine.hpp"
#include "starling/projection/projection_maintainer.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/hippocampus/working_set.hpp"

namespace starling::bindings {

void bind_09_brain_dynamics(pybind11::module_& m) {
    using namespace pybind11::literals;

    // ── M0.8: ReplayScheduler ──────────────────────────────────────────────

    py::class_<starling::replay::ReplayStats>(m, "ReplayStats")
        .def_readonly("sampled",               &starling::replay::ReplayStats::sampled)
        .def_readonly("compressed",            &starling::replay::ReplayStats::compressed)
        .def_readonly("abstracted",            &starling::replay::ReplayStats::abstracted)
        .def_readonly("reinforced",            &starling::replay::ReplayStats::reinforced)
        .def_readonly("decayed",               &starling::replay::ReplayStats::decayed)
        .def_readonly("reconciled",            &starling::replay::ReplayStats::reconciled)
        .def_readonly("forced_consolidated",   &starling::replay::ReplayStats::forced_consolidated)
        .def_readonly("ttl_archived",          &starling::replay::ReplayStats::ttl_archived)
        .def_readonly("replay_batch_id",       &starling::replay::ReplayStats::replay_batch_id);

    py::class_<starling::replay::ReplayScheduler>(m, "ReplayScheduler")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("enforce_oscillation_guard",
             [](starling::replay::ReplayScheduler& s) {
                 return s.enforce_oscillation_guard(s.connection());
             })
        .def("sweep_volatile_ttl",
             [](starling::replay::ReplayScheduler& s, std::string now) {
                 return s.sweep_volatile_ttl(s.connection(), now);
             },
             py::arg("now_iso"))
        .def("run_decay",
             [](starling::replay::ReplayScheduler& s,
                std::vector<std::string> ids, std::string now) {
                 return s.run_decay(s.connection(), ids, now);
             },
             py::arg("candidate_ids"), py::arg("now_iso"))
        .def("tick_online",
             [](starling::replay::ReplayScheduler& s, std::string now) {
                 return s.tick_online(s.connection(), now);
             },
             py::arg("now_iso"))
        .def("run_idle",
             [](starling::replay::ReplayScheduler& s, std::string now) {
                 return s.run_idle(s.connection(), now);
             },
             py::arg("now_iso"))
        .def("run_sleep",
             [](starling::replay::ReplayScheduler& s, std::string now) {
                 return s.run_sleep(s.connection(), now);
             },
             py::arg("now_iso"));

    // ── M0.8: ReconsolidationEngine ───────────────────────────────────────

    py::class_<starling::reconsolidation::EngineStats>(m, "EngineStats")
        .def_readonly("events_processed", &starling::reconsolidation::EngineStats::events_processed)
        .def_readonly("windows_opened",   &starling::reconsolidation::EngineStats::windows_opened)
        .def_readonly("windows_closed",   &starling::reconsolidation::EngineStats::windows_closed);

    py::class_<starling::reconsolidation::ReconsolidationEngine>(m, "ReconsolidationEngine")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("tick_one_batch",
             [](starling::reconsolidation::ReconsolidationEngine& s, std::string now) {
                 return s.tick_one_batch(s.connection(), now);
             },
             py::arg("now_iso"))
        .def("close_due_windows",
             [](starling::reconsolidation::ReconsolidationEngine& s, std::string now) {
                 return s.close_due_windows(s.connection(), now);
             },
             py::arg("now_iso"))
        .def("reconsolidate",
             [](starling::reconsolidation::ReconsolidationEngine& s,
                std::string stmt_id, std::string event_type,
                std::string payload_hash, double weight, std::string now) {
                 s.reconsolidate(s.connection(), stmt_id, event_type,
                                 payload_hash, weight, now);
             },
             py::arg("stmt_id"), py::arg("event_type"),
             py::arg("payload_hash"), py::arg("weight"), py::arg("now_iso"));

    // ── M0.8: ProjectionMaintainer ────────────────────────────────────────

    py::class_<starling::projection::MaintainerStats>(m, "MaintainerStats")
        .def_readonly("events_processed", &starling::projection::MaintainerStats::events_processed)
        .def_readonly("rows_upserted",    &starling::projection::MaintainerStats::rows_upserted);

    py::class_<starling::projection::RebuildReport>(m, "RebuildReport")
        .def_readonly("projection_name",      &starling::projection::RebuildReport::projection_name)
        .def_readonly("ground_truth_count",   &starling::projection::RebuildReport::ground_truth_count)
        .def_readonly("rebuilt_count",        &starling::projection::RebuildReport::rebuilt_count)
        .def_readonly("truncation_suspected", &starling::projection::RebuildReport::truncation_suspected);

    py::class_<starling::projection::ProjectionMaintainer>(m, "ProjectionMaintainer")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("tick_one_batch",
             [](starling::projection::ProjectionMaintainer& s, std::string now) {
                 return s.tick_one_batch(s.connection(), now);
             },
             py::arg("now_iso"))
        .def("rebuild_projection",
             [](starling::projection::ProjectionMaintainer& s,
                std::string name, std::string now) {
                 return s.rebuild_projection(s.connection(), name, now);
             },
             py::arg("projection_name"), py::arg("now_iso"))
        .def("rebuild_projection_with_injected_count",
             [](starling::projection::ProjectionMaintainer& s,
                std::string name, std::int64_t injected, std::string now) {
                 return s.rebuild_projection_with_injected_count(
                     s.connection(), name, injected, now);
             },
             py::arg("projection_name"), py::arg("injected_rebuilt"), py::arg("now_iso"));

    // ── P2.e Working Set(2026-06-11 边界归位:核心逻辑自 python/starling/
    //    working_set.py 迁入 src/hippocampus/working_set.cpp,Python 只剩转发)──

    py::class_<starling::hippocampus::WorkingBlock>(m, "WorkingBlock")
        .def_readonly("label",          &starling::hippocampus::WorkingBlock::label)
        .def_readonly("content",        &starling::hippocampus::WorkingBlock::content)
        .def_readonly("token_estimate", &starling::hippocampus::WorkingBlock::token_estimate);

    py::class_<starling::hippocampus::ContextBlock>(m, "ContextBlock")
        .def_readonly("blocks",    &starling::hippocampus::ContextBlock::blocks)
        .def_readonly("truncated", &starling::hippocampus::ContextBlock::truncated)
        .def("render",             &starling::hippocampus::ContextBlock::render);

    m.def("working_set_assemble",
          &starling::hippocampus::assemble,
          py::arg("sections"), py::arg("token_budget"));

    m.def("build_working_set",
          [](starling::persistence::SqliteAdapter& adapter,
             starling::retrieval::SemanticRetriever& retriever,
             const std::string& tenant_id, const std::string& agent_id,
             const std::string& interlocutor, const std::string& goal,
             int token_budget, int recall_k) {
              starling::hippocampus::WorkingSetParams p;
              p.tenant_id    = tenant_id;
              p.agent_id     = agent_id;
              p.interlocutor = interlocutor;
              p.goal         = goal;
              p.token_budget = token_budget;
              p.recall_k     = recall_k;
              return starling::hippocampus::build_working_set(adapter, retriever, p);
          },
          py::arg("adapter"), py::arg("retriever"),
          py::arg("tenant_id"), py::arg("agent_id"), py::arg("interlocutor"),
          py::arg("goal") = std::string(),
          py::arg("token_budget") = 2000, py::arg("recall_k") = 5);
}

}  // namespace starling::bindings
