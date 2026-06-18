// bind_06_extractor — M0.4/M0.5/M0.7/P2.l: statement enums / ExtractedStatement / Connection / LLM adapters / Extractor
// Split verbatim from bindings/python/module.cpp (original lines 586-797).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include <cstdint>
#include <map>
#include <utility>
#include <vector>
#include "starling/schema/enums.hpp"
#include "starling/schema/statement_enums.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/extractor/extractor.hpp"
#include "starling/extractor/episodic_extractor.hpp"
#include "starling/cognizer/perception_reconstructor.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/extractor/openai_adapter.hpp"
#include "starling/extractor/anthropic_adapter.hpp"
#include "starling/persistence/connection.hpp"

namespace starling::bindings {

void bind_06_extractor(pybind11::module_& m) {
    using namespace pybind11::literals;

    // ----- M0.4: enums -----
    py::enum_<starling::schema::Perspective>(m, "Perspective")
        .value("FIRST_PERSON", starling::schema::Perspective::FIRST_PERSON)
        .value("QUOTED",       starling::schema::Perspective::QUOTED)
        .value("INFERRED",     starling::schema::Perspective::INFERRED)
        .value("HEARSAY",      starling::schema::Perspective::HEARSAY)
        .export_values();

    py::enum_<starling::schema::Modality>(m, "Modality")
        .value("BELIEVES",    starling::schema::Modality::BELIEVES)
        .value("KNOWS",       starling::schema::Modality::KNOWS)
        .value("ASSUMES",     starling::schema::Modality::ASSUMES)
        .value("DOUBTS",      starling::schema::Modality::DOUBTS)
        .value("DESIRES",     starling::schema::Modality::DESIRES)
        .value("INTENDS",     starling::schema::Modality::INTENDS)
        .value("COMMITS",     starling::schema::Modality::COMMITS)
        .value("PREFERS",     starling::schema::Modality::PREFERS)
        .value("NORM_OUGHT",  starling::schema::Modality::NORM_OUGHT)
        .value("NORM_FORBID", starling::schema::Modality::NORM_FORBID)
        .value("RECANTED",    starling::schema::Modality::RECANTED)
        .value("OCCURRED",    starling::schema::Modality::OCCURRED)
        .export_values();

    py::enum_<starling::schema::Polarity>(m, "Polarity")
        .value("POS",     starling::schema::Polarity::POS)
        .value("NEG",     starling::schema::Polarity::NEG)
        .value("UNKNOWN", starling::schema::Polarity::UNKNOWN)
        .export_values();

    py::enum_<starling::schema::ReviewStatus>(m, "ReviewStatus")
        .value("APPROVED",            starling::schema::ReviewStatus::APPROVED)
        .value("PENDING_REVIEW",      starling::schema::ReviewStatus::PENDING_REVIEW)
        .value("INFERRED_UNREVIEWED", starling::schema::ReviewStatus::INFERRED_UNREVIEWED)
        .value("REVIEW_REQUESTED",    starling::schema::ReviewStatus::REVIEW_REQUESTED)
        .value("REJECTED",            starling::schema::ReviewStatus::REJECTED)
        .export_values();

    py::enum_<starling::schema::StatementProvenance>(m, "StatementProvenance")
        .value("USER_INPUT",              starling::schema::StatementProvenance::USER_INPUT)
        .value("REPLAY_DERIVED",          starling::schema::StatementProvenance::REPLAY_DERIVED)
        .value("TOM_INFERRED",            starling::schema::StatementProvenance::TOM_INFERRED)
        .value("RECONSOLIDATION_DERIVED", starling::schema::StatementProvenance::RECONSOLIDATION_DERIVED)
        .export_values();

    // ----- M0.5: ExtractedStatement DTO -----
    // Bound for the TC-NEW-CONFLICT-SEVERE acceptance test (§15.3.4): the test
    // constructs S_old / S_new in Python and feeds them to Bus::write to
    // exercise the atomic SUPERSEDES path. M0.4 extractor pipelines build
    // these structs in C++ from XML and never round-trip through Python; this
    // binding is purely for tests that need to construct an ExtractedStatement
    // outside the XML parser (the M0.5 XML schema doesn't yet carry
    // valid_from/valid_to, so the conflict-probe test must bypass it).
    py::class_<starling::extractor::ExtractedStatement>(m, "ExtractedStatement")
        .def(py::init<>())
        .def_readwrite("holder_id",             &starling::extractor::ExtractedStatement::holder_id)
        .def_readwrite("holder_tenant_id",      &starling::extractor::ExtractedStatement::holder_tenant_id)
        .def_readwrite("holder_perspective",    &starling::extractor::ExtractedStatement::holder_perspective)
        .def_readwrite("subject_kind",          &starling::extractor::ExtractedStatement::subject_kind)
        .def_readwrite("subject_id",            &starling::extractor::ExtractedStatement::subject_id)
        .def_readwrite("predicate",             &starling::extractor::ExtractedStatement::predicate)
        .def_readwrite("object_kind",           &starling::extractor::ExtractedStatement::object_kind)
        .def_readwrite("object_value",          &starling::extractor::ExtractedStatement::object_value)
        .def_readwrite("canonical_object_hash", &starling::extractor::ExtractedStatement::canonical_object_hash)
        .def_readwrite("modality",              &starling::extractor::ExtractedStatement::modality)
        .def_readwrite("polarity",              &starling::extractor::ExtractedStatement::polarity)
        .def_readwrite("confidence",            &starling::extractor::ExtractedStatement::confidence)
        .def_readwrite("observed_at",           &starling::extractor::ExtractedStatement::observed_at)
        .def_readwrite("valid_from",            &starling::extractor::ExtractedStatement::valid_from)
        .def_readwrite("valid_to",              &starling::extractor::ExtractedStatement::valid_to)
        .def_readwrite("event_time_start",      &starling::extractor::ExtractedStatement::event_time_start)
        .def_readwrite("chunk_index",           &starling::extractor::ExtractedStatement::chunk_index)
        .def_readwrite("source_hash",           &starling::extractor::ExtractedStatement::source_hash)
        .def_readwrite("perceived_by",          &starling::extractor::ExtractedStatement::perceived_by)
        .def_readwrite("provenance",            &starling::extractor::ExtractedStatement::provenance)
        .def_readwrite("review_status",         &starling::extractor::ExtractedStatement::review_status)
        .def_readwrite("derived_from",          &starling::extractor::ExtractedStatement::derived_from)
        .def_readwrite("provenance_protocol_id", &starling::extractor::ExtractedStatement::provenance_protocol_id);

    // ----- M0.4: Connection (opaque) -----
    py::class_<starling::persistence::Connection>(m, "Connection");

    // ----- M0.4: LLMResponse + LLMAdapter base + FakeLLMAdapter -----
    py::class_<starling::extractor::LLMResponse>(m, "LLMResponse")
        .def(py::init<>())
        .def(py::init([](std::string raw_xml, bool ok, std::string error) {
            return starling::extractor::LLMResponse{std::move(raw_xml), ok, std::move(error)};
        }), py::arg("raw_xml"), py::arg("ok"), py::arg("error") = "")
        .def_readwrite("raw_xml", &starling::extractor::LLMResponse::raw_xml)
        .def_readwrite("ok",      &starling::extractor::LLMResponse::ok)
        .def_readwrite("error",   &starling::extractor::LLMResponse::error);

    // Abstract base — register so pybind knows FakeLLMAdapter / OpenAIAdapter /
    // AnthropicAdapter share it. `extract` is bound here on the base so EVERY
    // adapter exposes it to Python (the dashboard /api/config/test probe calls
    // it on real OpenAI/Anthropic adapters, not just FakeLLMAdapter).
    py::class_<starling::extractor::LLMAdapter>(m, "LLMAdapter")
        .def("extract",
             [](starling::extractor::LLMAdapter& self, const std::string& prompt,
                const std::string& prompt_input_hash) {
                 return self.extract(prompt, prompt_input_hash);
             },
             py::arg("prompt"), py::arg("prompt_input_hash") = "",
             // 真模型探测(/api/config/test)走这里:网络期间释放 GIL。
             py::call_guard<py::gil_scoped_release>());

    py::class_<starling::extractor::FakeLLMAdapter, starling::extractor::LLMAdapter>(m, "FakeLLMAdapter")
        .def(py::init<>())
        .def("set_response",
             [](starling::extractor::FakeLLMAdapter& self, const std::string& hash,
                const std::string& raw_xml, bool ok, const std::string& error) {
                 self.set_response(hash, starling::extractor::LLMResponse{raw_xml, ok, error});
             },
             py::arg("hash"), py::arg("raw_xml"),
             py::arg("ok") = true, py::arg("error") = "")
        .def("set_default_response",
             [](starling::extractor::FakeLLMAdapter& self,
                const std::string& raw_xml, bool ok, const std::string& error) {
                 self.set_default_response(starling::extractor::LLMResponse{raw_xml, ok, error});
             },
             py::arg("raw_xml"), py::arg("ok") = true, py::arg("error") = "")
        .def("set_delay_ms",
             &starling::extractor::FakeLLMAdapter::set_delay_ms,
             py::arg("delay_ms"))
        .def("extract",
             &starling::extractor::FakeLLMAdapter::extract,
             py::arg("prompt"), py::arg("prompt_input_hash"));

    // ----- M0.7: OpenAIAdapter (real LLM, P2 pull-forward) -----
    {
        using starling::extractor::OpenAIAdapter;
        py::class_<OpenAIAdapter::Config>(m, "OpenAIAdapterConfig")
            .def(py::init<>())
            .def_readwrite("base_url",     &OpenAIAdapter::Config::base_url)
            .def_readwrite("model",        &OpenAIAdapter::Config::model)
            .def_readwrite("timeout_ms",   &OpenAIAdapter::Config::timeout_ms)
            .def_readwrite("max_retries",  &OpenAIAdapter::Config::max_retries)
            .def_readwrite("max_tokens",   &OpenAIAdapter::Config::max_tokens)
            .def_static("from_env",        &OpenAIAdapter::Config::from_env);
        py::class_<OpenAIAdapter, starling::extractor::LLMAdapter>(m, "OpenAIAdapter")
            .def(py::init<OpenAIAdapter::Config>());
    }

    // ----- P2.l: AnthropicAdapter (native Messages API) -----
    {
        using starling::extractor::AnthropicAdapter;
        py::class_<AnthropicAdapter::Config>(m, "AnthropicAdapterConfig")
            .def(py::init<>())
            .def_readwrite("base_url",    &AnthropicAdapter::Config::base_url)
            .def_readwrite("model",       &AnthropicAdapter::Config::model)
            .def_readwrite("api_version", &AnthropicAdapter::Config::api_version)
            .def_readwrite("timeout_ms",  &AnthropicAdapter::Config::timeout_ms)
            .def_readwrite("max_retries", &AnthropicAdapter::Config::max_retries)
            .def_readwrite("max_tokens",  &AnthropicAdapter::Config::max_tokens)
            .def_static("from_env",       &AnthropicAdapter::Config::from_env);
        py::class_<AnthropicAdapter, starling::extractor::LLMAdapter>(m, "AnthropicAdapter")
            .def(py::init<AnthropicAdapter::Config>());
    }

    // ----- M0.4: ExtractionRunResult -----
    py::class_<starling::extractor::ExtractionRunResult>(m, "ExtractionRunResult")
        .def_readonly("accepted_statement_ids",
                      &starling::extractor::ExtractionRunResult::accepted_statement_ids)
        .def_readonly("rejected_fragments",
                      &starling::extractor::ExtractionRunResult::rejected_fragments)
        .def_readonly("run_id", &starling::extractor::ExtractionRunResult::run_id)
        .def_property_readonly("status",
            [](const starling::extractor::ExtractionRunResult& r) -> std::string {
                switch (r.status) {
                    case starling::extractor::ExtractionRunResult::Status::SUCCESS:
                        return "success";
                    case starling::extractor::ExtractionRunResult::Status::PARTIAL_SUCCESS:
                        return "partial_success";
                    case starling::extractor::ExtractionRunResult::Status::FAILED:
                        return "failed";
                }
                return "unknown";
            });

    // ----- M0.4: Extractor -----
    py::class_<starling::extractor::Extractor>(m, "Extractor")
        .def(py::init([](starling::persistence::Connection& conn,
                         starling::extractor::LLMAdapter& a,
                         const std::string& prompt_template) {
            return new starling::extractor::Extractor(conn, a, prompt_template);
        }), py::keep_alive<1, 2>(), py::keep_alive<1, 3>(),
           py::arg("connection"), py::arg("adapter"),
           py::arg("prompt_template") = "")
        .def_static("compute_prompt_input_hash",
                    &starling::extractor::Extractor::compute_prompt_input_hash)
        .def_static("build_prompt_body",
                    [](const std::string& holder_id,
                       py::bytes payload,
                       const std::map<std::string, std::string>& refs) {
                        std::string s = payload;
                        std::vector<std::uint8_t> v(s.begin(), s.end());
                        return starling::extractor::Extractor::build_prompt_body_for_tests(
                            holder_id, v, refs);
                    },
                    py::arg("holder_id"), py::arg("payload_bytes"),
                    py::arg("existing_ref_map"))
        .def("run",
             [](starling::extractor::Extractor& self,
                const std::string& engram_ref_id,
                py::bytes payload,
                const std::string& holder_id,
                const std::string& holder_tenant_id,
                const std::map<std::string, std::string>& existing_ref_map,
                const std::string& interlocutor) {
                 std::string s = payload;
                 std::vector<std::uint8_t> v(s.begin(), s.end());
                 // LLM 网络调用(含重试退避)期间释放 GIL:否则 anyio 线程
                 // 持锁,事件循环照样冻结(完成 P0「脱离事件循环」的另一半)。
                 py::gil_scoped_release release;
                 return self.run(engram_ref_id, v, holder_id, holder_tenant_id, existing_ref_map, interlocutor);
             },
             py::arg("engram_ref_id"),
             py::arg("payload_bytes"),
             py::arg("holder_id"),
             py::arg("holder_tenant_id"),
             py::arg("existing_ref_map"),
             py::arg("interlocutor") = "");

    // ----- sub-project A phase 5: EpisodicExtractor (second extraction pass) -----
    // 镜像 Extractor 绑定:ctor(connection, adapter, prompt_template),extract()
    // 在 LLM 网络调用期间释放 GIL。返回本次写入的 OCCURRED 语句 id 列表。
    py::class_<starling::extractor::EpisodicExtractor>(m, "EpisodicExtractor")
        .def(py::init([](starling::persistence::Connection& conn,
                         starling::extractor::LLMAdapter& a,
                         const std::string& prompt_template) {
            return new starling::extractor::EpisodicExtractor(conn, a, prompt_template);
        }), py::keep_alive<1, 2>(), py::keep_alive<1, 3>(),
           py::arg("connection"), py::arg("adapter"),
           py::arg("prompt_template") = "")
        .def("extract",
             [](starling::extractor::EpisodicExtractor& self,
                const std::string& passage,
                const std::string& engram_ref,
                const std::string& tenant,
                const std::string& agent_self,
                const std::string& now) {
                 py::gil_scoped_release release;
                 const auto r = self.extract(passage, engram_ref, tenant, agent_self, now);
                 return r.event_statement_ids;
             },
             py::arg("passage"), py::arg("engram_ref"), py::arg("tenant"),
             py::arg("agent_self"), py::arg("now"));

    // ----- sub-project B phase 1: PerceptionReconstructor (post-pass) -----
    // 镜像 EpisodicExtractor 绑定:ctor 持 Connection&(keep_alive),reconstruct()
    // 扫描租户全部 OCCURRED 事件重建 perception_state。
    // Phase 5 (Task 5.1): 可选第二个 ctor 额外接 SqliteAdapter&,使重建在写
    // perception_state 之余,把见证者事件 engram 记入 KnowledgeFrontier(does_X_know
    // 事件感知)。两条 ctor 都 keep_alive 各引用参数,使其活过 reconstructor。
    py::class_<starling::cognizer::PerceptionReconstructor>(m, "PerceptionReconstructor")
        .def(py::init<starling::persistence::Connection&>(), py::arg("conn"), py::keep_alive<1, 2>())
        .def(py::init<starling::persistence::Connection&, starling::persistence::SqliteAdapter&>(),
             py::arg("conn"), py::arg("adapter"),
             py::keep_alive<1, 2>(), py::keep_alive<1, 3>())
        .def("reconstruct",
            [](starling::cognizer::PerceptionReconstructor& self, const std::string& tenant) {
                self.reconstruct(tenant);
            },
            py::arg("tenant"));
}

}  // namespace starling::bindings
