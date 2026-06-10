// bind_07_cognizer — 08_cognizer: CognizerHub / KnowledgeFrontier / relation edges / error types
// Split verbatim from bindings/python/module.cpp (original lines 799-1008).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include <map>
#include <vector>
#include "starling/cognizer/cognizer.hpp"
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::bindings {

void bind_07_cognizer(pybind11::module_& m) {
    using namespace pybind11::literals;

    // ── 08_cognizer ────────────────────────────────────────────────

    py::enum_<starling::cognizer::CognizerKind>(m, "CognizerKind")
        .value("Self",     starling::cognizer::CognizerKind::Self)
        .value("Human",    starling::cognizer::CognizerKind::Human)
        .value("Agent",    starling::cognizer::CognizerKind::Agent)
        .value("Group",    starling::cognizer::CognizerKind::Group)
        .value("Role",     starling::cognizer::CognizerKind::Role)
        .value("External", starling::cognizer::CognizerKind::External);

    py::enum_<starling::cognizer::FiskeMode>(m, "FiskeMode")
        .value("Communal",  starling::cognizer::FiskeMode::Communal)
        .value("Authority", starling::cognizer::FiskeMode::Authority)
        .value("Equality",  starling::cognizer::FiskeMode::Equality)
        .value("Market",    starling::cognizer::FiskeMode::Market);

    py::class_<starling::cognizer::Cognizer>(m, "Cognizer")
        .def_readonly("id",              &starling::cognizer::Cognizer::id)
        .def_readonly("tenant_id",       &starling::cognizer::Cognizer::tenant_id)
        .def_readonly("kind",            &starling::cognizer::Cognizer::kind)
        .def_readonly("canonical_name",  &starling::cognizer::Cognizer::canonical_name)
        .def_readonly("external_id",     &starling::cognizer::Cognizer::external_id)
        .def_readonly("aliases",         &starling::cognizer::Cognizer::aliases)
        .def_readonly("created_at",      &starling::cognizer::Cognizer::created_at)
        .def_readonly("last_seen_at",    &starling::cognizer::Cognizer::last_seen_at);

    py::class_<starling::cognizer::RelationEdge>(m, "RelationEdge")
        .def_readonly("id",               &starling::cognizer::RelationEdge::id)
        .def_readonly("tenant_id",        &starling::cognizer::RelationEdge::tenant_id)
        .def_readonly("a_id",             &starling::cognizer::RelationEdge::a_id)
        .def_readonly("b_id",             &starling::cognizer::RelationEdge::b_id)
        .def_readonly("affinity",         &starling::cognizer::RelationEdge::affinity)
        .def_readonly("power_asymmetry",  &starling::cognizer::RelationEdge::power_asymmetry)
        .def_readonly("created_at",       &starling::cognizer::RelationEdge::created_at)
        .def_readonly("updated_at",       &starling::cognizer::RelationEdge::updated_at);

    py::class_<starling::cognizer::CognizerHub>(m, "CognizerHub")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("register_cognizer",
             [](starling::cognizer::CognizerHub& hub,
                const std::string& kind_str,
                const std::string& external_id,
                const std::string& canonical_name,
                const std::string& tenant_id,
                const std::vector<std::string>& aliases,
                bool tenant_explicitly_set) {
                 starling::cognizer::CognizerRegistration req;
                 req.external_id = external_id;
                 req.canonical_name = canonical_name;
                 req.tenant_id = tenant_id;
                 req.aliases = aliases;
                 req.tenant_explicitly_set = tenant_explicitly_set;
                 if      (kind_str == "self")     req.kind = starling::cognizer::CognizerKind::Self;
                 else if (kind_str == "human")    req.kind = starling::cognizer::CognizerKind::Human;
                 else if (kind_str == "agent")    req.kind = starling::cognizer::CognizerKind::Agent;
                 else if (kind_str == "group")    req.kind = starling::cognizer::CognizerKind::Group;
                 else if (kind_str == "role")     req.kind = starling::cognizer::CognizerKind::Role;
                 else if (kind_str == "external") req.kind = starling::cognizer::CognizerKind::External;
                 else throw py::value_error("unknown kind: " + kind_str);
                 return hub.register_cognizer(req);
             },
             py::arg("kind"), py::arg("external_id"), py::arg("canonical_name"),
             py::arg("tenant_id") = "default",
             py::arg("aliases") = std::vector<std::string>{},
             py::arg("tenant_explicitly_set") = false)
        .def("lookup_by_alias",
             [](const starling::cognizer::CognizerHub& hub,
                const std::string& tenant_id,
                const std::string& alias) -> py::object {
                 auto r = hub.lookup_by_alias(tenant_id, alias);
                 if (!r) return py::none();
                 return py::str(*r);
             },
             py::arg("tenant_id"), py::arg("alias"))
        .def("get",
             [](const starling::cognizer::CognizerHub& hub,
                const std::string& id,
                const std::string& tenant_id) -> py::object {
                 auto r = hub.get(id, tenant_id);
                 if (!r) return py::none();
                 return py::cast(*r);
             },
             py::arg("id"), py::arg("tenant_id") = "default")
        .def("update_last_seen_at",
             [](starling::cognizer::CognizerHub& hub,
                const std::string& id,
                const std::string& tenant_id,
                const std::string& at_iso8601) {
                 hub.update_last_seen_at(id, tenant_id, at_iso8601);
             },
             py::arg("id"), py::arg("tenant_id"), py::arg("at"))
        .def("upsert_relation",
             [](starling::cognizer::CognizerHub& hub,
                const std::string& a_id, const std::string& b_id,
                const std::string& tenant_id,
                const std::map<std::string, double>& fiske_map,
                double affinity, double power_asymmetry) {
                 starling::cognizer::RelationEdgeInput req;
                 req.a_id = a_id;
                 req.b_id = b_id;
                 req.tenant_id = tenant_id;
                 req.affinity = affinity;
                 req.power_asymmetry = power_asymmetry;
                 for (auto& [k, v] : fiske_map) {
                     if      (k == "communal")  req.fiske_weights[starling::cognizer::FiskeMode::Communal]  = v;
                     else if (k == "authority") req.fiske_weights[starling::cognizer::FiskeMode::Authority] = v;
                     else if (k == "equality")  req.fiske_weights[starling::cognizer::FiskeMode::Equality]  = v;
                     else if (k == "market")    req.fiske_weights[starling::cognizer::FiskeMode::Market]    = v;
                 }
                 return hub.upsert_relation(req);
             },
             py::arg("a_id"), py::arg("b_id"),
             py::arg("tenant_id") = "default",
             py::arg("fiske_weights") = std::map<std::string, double>{},
             py::arg("affinity") = 0.5,
             py::arg("power_asymmetry") = 0.0)
        .def("relations_of",
             &starling::cognizer::CognizerHub::relations_of,
             py::arg("cognizer_id"), py::arg("tenant_id") = "default");

    py::class_<starling::cognizer::KnowledgeFrontier>(m, "KnowledgeFrontier")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("record_presence_from_statement",
             [](starling::cognizer::KnowledgeFrontier& f,
                const std::string& tenant_id,
                const std::vector<std::string>& perceived_by,
                const std::string& engram_id,
                const std::string& observed_at,
                starling::persistence::Connection& conn) {
                 f.record_presence_from_statement(tenant_id, perceived_by,
                                                   engram_id, observed_at, conn);
             },
             py::arg("tenant_id"), py::arg("perceived_by"),
             py::arg("engram_id"), py::arg("observed_at"), py::arg("conn"))
        .def("record_explicit_told",
             [](starling::cognizer::KnowledgeFrontier& f,
                const std::string& tenant_id,
                const std::vector<std::string>& perceived_by,
                const std::string& statement_id,
                const std::string& source_engram_id,
                const std::string& observed_at,
                starling::persistence::Connection& conn) {
                 f.record_explicit_told(tenant_id, perceived_by, statement_id,
                                        source_engram_id, observed_at, conn);
             },
             py::arg("tenant_id"), py::arg("perceived_by"),
             py::arg("statement_id"), py::arg("source_engram_id"),
             py::arg("observed_at"), py::arg("conn"))
        .def("record_accessible_source",
             [](starling::cognizer::KnowledgeFrontier& f,
                const std::string& tenant_id,
                const std::string& cognizer_id,
                const std::string& adapter_name,
                const std::string& source_engram_id,
                const std::string& observed_at,
                starling::persistence::Connection& conn) {
                 f.record_accessible_source(tenant_id, cognizer_id, adapter_name,
                                             source_engram_id, observed_at, conn);
             },
             py::arg("tenant_id"), py::arg("cognizer_id"),
             py::arg("adapter_name"), py::arg("source_engram_id"),
             py::arg("observed_at"), py::arg("conn"))
        .def("record_group_membership",
             [](starling::cognizer::KnowledgeFrontier& f,
                const std::string& tenant_id,
                const std::string& cognizer_id,
                const std::string& group_id,
                const std::string& at_iso8601,
                starling::persistence::Connection& conn) {
                 f.record_group_membership(tenant_id, cognizer_id, group_id,
                                            at_iso8601, conn);
             },
             py::arg("tenant_id"), py::arg("cognizer_id"),
             py::arg("group_id"), py::arg("at"), py::arg("conn"))
        .def("record_explicit_negation",
             [](starling::cognizer::KnowledgeFrontier& f,
                const std::string& tenant_id,
                const std::string& cognizer_id,
                const std::string& referenced_statement_id,
                const std::string& source_engram_id,
                const std::string& observed_at,
                starling::persistence::Connection& conn) {
                 f.record_explicit_negation(tenant_id, cognizer_id,
                                             referenced_statement_id,
                                             source_engram_id, observed_at, conn);
             },
             py::arg("tenant_id"), py::arg("cognizer_id"),
             py::arg("referenced_statement_id"), py::arg("source_engram_id"),
             py::arg("observed_at"), py::arg("conn"))
        .def("visible_engrams_at",
             [](const starling::cognizer::KnowledgeFrontier& f,
                const std::string& tenant_id,
                const std::string& cognizer_id,
                const std::string& as_of) {
                 auto s = f.visible_engrams_at(tenant_id, cognizer_id, as_of);
                 return std::vector<std::string>(s.begin(), s.end());
             },
             py::arg("tenant_id"), py::arg("cognizer_id"), py::arg("as_of"));

    // Error types (§6.7)
    py::register_exception<starling::cognizer::AliasCollision>(
        m, "AliasCollision", PyExc_RuntimeError);
    py::register_exception<starling::cognizer::FiskeWeightsInvalid>(
        m, "FiskeWeightsInvalid", PyExc_ValueError);
    py::register_exception<starling::cognizer::GroupTenantImplicit>(
        m, "GroupTenantImplicit", PyExc_ValueError);
    py::register_exception<starling::cognizer::CognizerNotFound>(
        m, "CognizerNotFound", PyExc_KeyError);
}

}  // namespace starling::bindings
