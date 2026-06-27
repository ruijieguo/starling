// bind_09_brain_dynamics — M0.8: ReplayScheduler / ReconsolidationEngine / ProjectionMaintainer
// Split verbatim from bindings/python/module.cpp (original lines 1172-1281).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include <vector>
#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/replay/replay_scheduler.hpp"
#include "starling/replay/forgetting_curve.hpp"
#include "starling/extractor/llm_adapter.hpp"
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
        .def_readonly("gist_candidates",       &starling::replay::ReplayStats::gist_candidates)
        .def_readonly("gist_failed",           &starling::replay::ReplayStats::gist_failed)
        .def_readonly("gist_gated",            &starling::replay::ReplayStats::gist_gated)
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
             [](starling::replay::ReplayScheduler& sched, const std::string& now,
                starling::extractor::LLMAdapter* llm) {
                 return sched.run_idle(sched.connection(), now, llm);
             },
             py::arg("now_iso"), py::arg("llm") = nullptr)
        .def("run_sleep",
             [](starling::replay::ReplayScheduler& sched, const std::string& now,
                starling::extractor::LLMAdapter* llm) {
                 return sched.run_sleep(sched.connection(), now, llm);
             },
             py::arg("now_iso"), py::arg("llm") = nullptr);

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

    // ── P3.a3: reconsolidate.requested 显式触发(再巩固触发器 #4) ──
    // audit/用户编辑场景的入口:发一条 reconsolidate.requested 事件,
    // ReconsolidationEngine 异步消费开窗(payload {stmt_id, request_id})。
    m.def("request_reconsolidation",
          [](starling::persistence::SqliteAdapter& adapter,
             const std::string& tenant_id, const std::string& stmt_id,
             const std::string& request_id, const std::string& now_iso) {
              auto& conn = adapter.connection();
              starling::persistence::TransactionGuard tx(conn);
              starling::bus::BusEvent ev;
              ev.tenant_id    = tenant_id;
              ev.event_type   = "reconsolidate.requested";
              ev.primary_id   = stmt_id;
              ev.aggregate_id = stmt_id;
              ev.payload_json = std::string("{\"stmt_id\":\"") + stmt_id +
                  "\",\"request_id\":\"" + request_id + "\"}";
              ev.version = "v1";
              ev.idempotency_key = starling::bus::compute_idempotency_key(
                  "reconsolidate.requested", stmt_id, stmt_id, request_id,
                  now_iso.substr(0, 10));   // 同 request_id 当日去重
              starling::bus::OutboxWriter w(conn);
              w.append(ev);
              tx.commit();
              return ev.event_id;
          },
          py::arg("adapter"), py::arg("tenant_id"), py::arg("stmt_id"),
          py::arg("request_id"), py::arg("now_iso"),
          "Emit reconsolidate.requested (explicit trigger #4); engine opens "
          "the plastic window asynchronously.");

    // ── P3 片 5: 衰减曲线只读投影(forgetting_curve 纯函数转发,无 DB/无状态) ──
    // 公式与其逆都在 src/replay/forgetting_curve.cpp;这里仅构造 ForgettingInputs
    // 转发,绝不在绑定层复算(换绑定语言不需重写 = 守边界)。dashboard 只读消费。
    m.def("forgetting_s_t",
          [](double salience, std::int64_t access_count, bool active_grounded,
             const std::string& modality, double affect_valence,
             const std::string& last_accessed_iso, const std::string& now_iso) {
              starling::replay::ForgettingInputs in;
              in.salience          = salience;
              in.access_count      = access_count;
              in.active_grounded   = active_grounded;
              in.modality          = modality;
              in.affect_valence    = affect_valence;
              in.last_accessed_iso = last_accessed_iso;
              return starling::replay::compute_s_t(in, now_iso);
          },
          py::arg("salience"), py::arg("access_count"), py::arg("active_grounded"),
          py::arg("modality"), py::arg("affect_valence"),
          py::arg("last_accessed_iso"), py::arg("now_iso"),
          "Read-only projection of the C++ forgetting curve S(t)=exp(-Δt/S0).");

    m.def("forgetting_seconds_until",
          [](double salience, std::int64_t access_count, bool active_grounded,
             const std::string& modality, double affect_valence, double target) {
              starling::replay::ForgettingInputs in;
              in.salience        = salience;
              in.access_count    = access_count;
              in.active_grounded = active_grounded;
              in.modality        = modality;
              in.affect_valence  = affect_valence;
              return starling::replay::seconds_until_retrievability(in, target);
          },
          py::arg("salience"), py::arg("access_count"), py::arg("active_grounded"),
          py::arg("modality"), py::arg("affect_valence"), py::arg("target"),
          "Seconds from last_accessed until S(t) reaches target (curve inverse).");
}

}  // namespace starling::bindings
