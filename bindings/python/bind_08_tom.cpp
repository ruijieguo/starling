// bind_08_tom — 09_tom: mentalizing / common ground entry / ToMEngine / belief tracker
// Split verbatim from bindings/python/module.cpp (original lines 1010-1170).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include <vector>
#include "starling/tom/mentalizing.hpp"
#include "starling/tom/common_ground.hpp"
#include "starling/tom/tom_engine.hpp"
#include "starling/tom/belief_tracker.hpp"
#include "starling/tom/nesting_depth_writer.hpp"
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::bindings {

void bind_08_tom(pybind11::module_& m) {
    using namespace pybind11::literals;

    // ── 09_tom ─────────────────────────────────────────────────────────────

    // FactKey — read-write (builders need to set fields)
    py::class_<starling::tom::mentalizing::FactKey>(m, "FactKey")
        .def(py::init<>())
        .def(py::init([](std::string subject_kind,
                         std::string subject_id,
                         std::string predicate,
                         std::string canonical_object_hash) {
            return starling::tom::mentalizing::FactKey{
                std::move(subject_kind),
                std::move(subject_id),
                std::move(predicate),
                std::move(canonical_object_hash),
            };
        }),
        py::arg("subject_kind") = "",
        py::arg("subject_id") = "",
        py::arg("predicate") = "",
        py::arg("canonical_object_hash") = "")
        .def_readwrite("subject_kind",           &starling::tom::mentalizing::FactKey::subject_kind)
        .def_readwrite("subject_id",             &starling::tom::mentalizing::FactKey::subject_id)
        .def_readwrite("predicate",              &starling::tom::mentalizing::FactKey::predicate)
        .def_readwrite("canonical_object_hash",  &starling::tom::mentalizing::FactKey::canonical_object_hash);

    // KnowsResult enum
    py::enum_<starling::tom::mentalizing::KnowsResult>(m, "KnowsResult")
        .value("FullKnowledge", starling::tom::mentalizing::KnowsResult::FullKnowledge)
        .value("NotKnown",      starling::tom::mentalizing::KnowsResult::NotKnown)
        .value("Unknowable",    starling::tom::mentalizing::KnowsResult::Unknowable);

    // SharedFact — read-only
    py::class_<starling::tom::mentalizing::SharedFact>(m, "SharedFact")
        .def_readonly("subject_kind",           &starling::tom::mentalizing::SharedFact::subject_kind)
        .def_readonly("subject_id",             &starling::tom::mentalizing::SharedFact::subject_id)
        .def_readonly("predicate",              &starling::tom::mentalizing::SharedFact::predicate)
        .def_readonly("canonical_object_hash",  &starling::tom::mentalizing::SharedFact::canonical_object_hash)
        .def_readonly("polarity",               &starling::tom::mentalizing::SharedFact::polarity)
        .def_readonly("source_statement_ids",   &starling::tom::mentalizing::SharedFact::source_statement_ids);

    // Misalignment — read-only vectors; confidence_diverges exposed as list of
    // 2-tuples (x_row, y_row) via a property lambda.
    py::class_<starling::tom::mentalizing::Misalignment>(m, "Misalignment")
        .def_readonly("only_x_believes",  &starling::tom::mentalizing::Misalignment::only_x_believes)
        .def_readonly("only_y_believes",  &starling::tom::mentalizing::Misalignment::only_y_believes)
        .def_property_readonly("confidence_diverges",
            [](const starling::tom::mentalizing::Misalignment& m_) {
                py::list result;
                for (const auto& p : m_.confidence_diverges) {
                    result.append(py::make_tuple(p.first, p.second));
                }
                return result;
            });

    // CommonGroundEntry — read-only
    py::class_<starling::tom::CommonGroundEntry>(m, "CommonGroundEntry")
        .def_readonly("id",            &starling::tom::CommonGroundEntry::id)
        .def_readonly("tenant_id",     &starling::tom::CommonGroundEntry::tenant_id)
        .def_readonly("statement_id",  &starling::tom::CommonGroundEntry::statement_id)
        .def_readonly("status",        &starling::tom::CommonGroundEntry::status)
        .def_readonly("parties_json",  &starling::tom::CommonGroundEntry::parties_json)
        .def_readonly("created_at",    &starling::tom::CommonGroundEntry::created_at)
        .def_readonly("updated_at",    &starling::tom::CommonGroundEntry::updated_at);

    // Context — read-only snapshot from perspective_take
    py::class_<starling::tom::Context>(m, "Context")
        .def_readonly("visible_engram_ids",  &starling::tom::Context::visible_engram_ids)
        .def_readonly("target_beliefs",      &starling::tom::Context::target_beliefs)
        .def_readonly("cg",                  &starling::tom::Context::cg);

    // NestingDepthOverflow exception
    py::register_exception<starling::tom::NestingDepthOverflow>(
        m, "NestingDepthOverflow", PyExc_RecursionError);

    // ToMEngine — takes references to adapter/hub/frontier (keep_alive on all).
    py::class_<starling::tom::ToMEngine>(m, "ToMEngine")
        .def(py::init<starling::persistence::SqliteAdapter&,
                      starling::cognizer::CognizerHub&,
                      starling::cognizer::KnowledgeFrontier&>(),
             py::keep_alive<1, 2>(), py::keep_alive<1, 3>(), py::keep_alive<1, 4>(),
             py::arg("adapter"), py::arg("hub"), py::arg("frontier"))
        .def("perspective_take",
             [](const starling::tom::ToMEngine& eng,
                const std::string& target,
                const std::string& tenant,
                const std::string& as_of) {
                 return eng.perspective_take(target, tenant, as_of);
             },
             py::arg("target"), py::arg("tenant"), py::arg("as_of"));

    // Free function bindings for mentalizing primitives

    m.def("what_does_X_believe",
        [](starling::persistence::SqliteAdapter& adapter,
           const std::string& x,
           const std::string& about_y,
           const std::string& tenant,
           const std::string& as_of,
           const std::string& modality_filter) {
            return starling::tom::mentalizing::what_does_X_believe(
                adapter, x, about_y, tenant, as_of, modality_filter);
        },
        py::arg("adapter"), py::arg("x"), py::arg("about_y"),
        py::arg("tenant"), py::arg("as_of"), py::arg("modality_filter") = "",
        "Return all statements held by X about Y. Optional modality_filter.");

    m.def("does_X_know",
        [](starling::persistence::SqliteAdapter& adapter,
           starling::cognizer::KnowledgeFrontier& frontier,
           const std::string& x,
           const starling::tom::mentalizing::FactKey& fact,
           const std::string& tenant,
           const std::string& as_of) {
            return starling::tom::mentalizing::does_X_know(
                adapter, frontier, x, fact, tenant, as_of);
        },
        py::arg("adapter"), py::arg("frontier"), py::arg("x"),
        py::arg("fact"), py::arg("tenant"), py::arg("as_of"),
        "Tri-valued query: FullKnowledge / NotKnown / Unknowable.");

    m.def("find_misalignment",
        [](starling::persistence::SqliteAdapter& adapter,
           const std::string& x,
           const std::string& y,
           const std::string& subject_kind,
           const std::string& subject_id,
           const std::string& tenant,
           const std::string& as_of) {
            return starling::tom::mentalizing::find_misalignment(
                adapter, x, y, subject_kind, subject_id, tenant, as_of);
        },
        py::arg("adapter"), py::arg("x"), py::arg("y"),
        py::arg("subject_kind"), py::arg("subject_id"),
        py::arg("tenant"), py::arg("as_of"),
        "Find belief misalignments between cognizers X and Y.");

    m.def("shared_with",
        [](starling::persistence::SqliteAdapter& adapter,
           const std::vector<std::string>& members,
           const std::string& tenant,
           const std::string& as_of) {
            return starling::tom::mentalizing::shared_with(adapter, members, tenant, as_of);
        },
        py::arg("adapter"), py::arg("members"), py::arg("tenant"), py::arg("as_of"),
        "Return facts believed by ALL members.");

    // TickStats — read-only
    py::class_<starling::tom::belief_tracker::TickStats>(m, "TickStats")
        .def_readonly("events_processed",       &starling::tom::belief_tracker::TickStats::events_processed)
        .def_readonly("frontier_facts_written",  &starling::tom::belief_tracker::TickStats::frontier_facts_written)
        .def_readonly("trust_prior_updates",     &starling::tom::belief_tracker::TickStats::trust_prior_updates)
        .def_readonly("last_seen_updates",       &starling::tom::belief_tracker::TickStats::last_seen_updates)
        .def_readonly("presence_log_writes",     &starling::tom::belief_tracker::TickStats::presence_log_writes);

    // belief_tracker_tick — free function for Python consumers
    m.def("belief_tracker_tick",
        [](starling::persistence::SqliteAdapter& adapter, int batch_size) {
            return starling::tom::belief_tracker::tick_one_batch(adapter, batch_size);
        },
        py::arg("adapter"), py::arg("batch_size") = 100,
        "Process one batch of bus events through BeliefTracker. Returns TickStats.");
}

}  // namespace starling::bindings
