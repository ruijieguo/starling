// bind_10_embedding — M0.9/P2.f/P2.d: embedding adapters / vector index / EmbeddingWorker / SemanticRetriever / PatternCompletor
// Split verbatim from bindings/python/module.cpp (original lines 1283-1450).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include <utility>
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/embedding/embedding_worker.hpp"
#include "starling/embedding/openai_embedding_adapter.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/vector/zvec_vector_index.hpp"
#include "starling/retrieval/semantic_retriever.hpp"
#include "starling/retrieval/pattern_completor.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::bindings {

void bind_10_embedding(pybind11::module_& m) {
    using namespace pybind11::literals;

    // ── M0.9: Embedding / Vector / Worker / SemanticRetriever ─────────────

    // Abstract bases (no init) so derived-to-base-ref passing works.
    py::class_<starling::embedding::EmbeddingAdapter>(m, "EmbeddingAdapter")
        // dim() 在基类暴露,使 set_embedder 对所有 embedder(stub/openai)可取维度
        // (向量后端工厂 zvec collection 需固定 dim)。
        .def("dim", &starling::embedding::EmbeddingAdapter::dim)
        .def("embed",
             [](starling::embedding::EmbeddingAdapter& self, const std::string& text) {
                 return self.embed(text).vector;  // list[float]; len == dim. Real call → connectivity probe.
             },
             py::arg("text"),
             // 真 embedder 网络调用期间释放 GIL(/api/config/test 探测路径)。
             py::call_guard<py::gil_scoped_release>());
    py::class_<starling::vector::VectorIndex>(m, "VectorIndex");

    py::class_<starling::embedding::StubEmbeddingAdapter,
               starling::embedding::EmbeddingAdapter>(m, "StubEmbeddingAdapter")
        .def(py::init<int>(), py::arg("dim") = 8)
        .def("dim", &starling::embedding::StubEmbeddingAdapter::dim)
        .def("model", &starling::embedding::StubEmbeddingAdapter::model)
        .def("fail_next",
             [](starling::embedding::StubEmbeddingAdapter& s, std::string text) {
                 s.fail_next(text);
             },
             py::arg("text"));

    // ----- P2.f: OpenAIEmbeddingAdapter (real embedder for gated evals) -----
    {
        using starling::embedding::OpenAIEmbeddingAdapter;
        py::class_<OpenAIEmbeddingAdapter::Config>(m, "OpenAIEmbeddingConfig")
            .def(py::init<>())
            .def_readwrite("base_url",    &OpenAIEmbeddingAdapter::Config::base_url)
            .def_readwrite("model",       &OpenAIEmbeddingAdapter::Config::model)
            .def_readwrite("dim",         &OpenAIEmbeddingAdapter::Config::dim)
            .def_readwrite("timeout_ms",  &OpenAIEmbeddingAdapter::Config::timeout_ms)
            .def_readwrite("max_retries", &OpenAIEmbeddingAdapter::Config::max_retries)
            .def_static("from_env",       &OpenAIEmbeddingAdapter::Config::from_env);
        py::class_<OpenAIEmbeddingAdapter, starling::embedding::EmbeddingAdapter>(
                m, "OpenAIEmbeddingAdapter")
            .def(py::init<OpenAIEmbeddingAdapter::Config>(), py::arg("config"));
    }

    py::class_<starling::vector::SqliteBlobVectorIndex,
               starling::vector::VectorIndex>(m, "SqliteBlobVectorIndex")
        .def(py::init<>());

#ifdef STARLING_HAS_ZVEC
    // zvec 后端(STARLING_VECTOR_ZVEC=ON 编译时可用)。构造接 store_path + dimension
    // (collection schema 固定维度);default OFF 构建里此类不注册。
    py::class_<starling::vector::ZvecVectorIndex,
               starling::vector::VectorIndex>(m, "ZvecVectorIndex")
        .def(py::init<const std::string&, int>(),
             py::arg("store_path"), py::arg("dimension"));
#endif

    py::class_<starling::embedding::EmbeddingStats>(m, "EmbeddingStats")
        .def_readonly("embedded",         &starling::embedding::EmbeddingStats::embedded)
        .def_readonly("failed",           &starling::embedding::EmbeddingStats::failed)
        .def_readonly("overlaps_created", &starling::embedding::EmbeddingStats::overlaps_created);

    // EmbeddingWorker holds REFERENCES to adapter/embedder/index — keep_alive on
    // all three (without it you get a use-after-free).
    py::class_<starling::embedding::EmbeddingWorker>(m, "EmbeddingWorker")
        .def(py::init<starling::persistence::SqliteAdapter&,
                      starling::embedding::EmbeddingAdapter&,
                      starling::vector::VectorIndex&>(),
             py::keep_alive<1, 2>(), py::keep_alive<1, 3>(), py::keep_alive<1, 4>(),
             py::arg("adapter"), py::arg("embedder"), py::arg("index"))
        .def("tick_one_batch",
             [](starling::embedding::EmbeddingWorker& s, std::string now) {
                 return s.tick_one_batch(s.connection(), now);
             },
             py::arg("now_iso"),
             // 批量嵌入逐条走网络:释放 GIL,手动 Tick 期间面板不冻结。
             py::call_guard<py::gil_scoped_release>());

    py::class_<starling::retrieval::SemanticRetrieverParams>(
            m, "SemanticRetrieverParams")
        .def(py::init([](std::string tenant_id, std::string holder_id,
                         std::string holder_perspective, std::string query_text,
                         int k, std::string trace_id, std::string query_id) {
            starling::retrieval::SemanticRetrieverParams p;
            p.tenant_id = std::move(tenant_id);
            p.holder_id = std::move(holder_id);
            p.holder_perspective = std::move(holder_perspective);
            p.query_text = std::move(query_text);
            p.k = k;
            p.trace_id = std::move(trace_id);
            p.query_id = std::move(query_id);
            return p;
        }),
        py::arg("tenant_id") = "",
        py::arg("holder_id") = "",
        py::arg("holder_perspective") = "",
        py::arg("query_text") = "",
        py::arg("k") = 10,
        py::arg("trace_id") = "",
        py::arg("query_id") = "")
        .def_readwrite("tenant_id",          &starling::retrieval::SemanticRetrieverParams::tenant_id)
        .def_readwrite("holder_id",          &starling::retrieval::SemanticRetrieverParams::holder_id)
        .def_readwrite("holder_perspective", &starling::retrieval::SemanticRetrieverParams::holder_perspective)
        .def_readwrite("query_text",         &starling::retrieval::SemanticRetrieverParams::query_text)
        .def_readwrite("k",                  &starling::retrieval::SemanticRetrieverParams::k)
        .def_readwrite("trace_id",           &starling::retrieval::SemanticRetrieverParams::trace_id)
        .def_readwrite("query_id",           &starling::retrieval::SemanticRetrieverParams::query_id);

    py::class_<starling::retrieval::SemanticScored>(m, "SemanticScored")
        .def_readonly("row",   &starling::retrieval::SemanticScored::row)
        .def_readonly("score", &starling::retrieval::SemanticScored::score);

    py::class_<starling::retrieval::SemanticResult>(m, "SemanticResult")
        .def_readonly("rows",     &starling::retrieval::SemanticResult::rows)
        .def_readonly("degraded", &starling::retrieval::SemanticResult::degraded);

    py::class_<starling::retrieval::SemanticRetriever>(m, "SemanticRetriever")
        .def(py::init<starling::persistence::SqliteAdapter&,
                      starling::embedding::EmbeddingAdapter&,
                      starling::vector::VectorIndex&>(),
             py::keep_alive<1, 2>(), py::keep_alive<1, 3>(), py::keep_alive<1, 4>(),
             py::arg("adapter"), py::arg("embedder"), py::arg("index"))
        .def("vector_recall",
             [](starling::retrieval::SemanticRetriever& s,
                const starling::retrieval::SemanticRetrieverParams& p) {
                 return s.vector_recall(s.connection(), p);
             },
             py::arg("params"));

    // ── P2.d: Pattern Completion ──────────────────────────────────────────
    py::class_<starling::retrieval::PatternCompletionParams>(
            m, "PatternCompletionParams")
        .def(py::init([](std::string tenant_id, std::string holder_id,
                         std::string holder_perspective, std::string cue_text,
                         int seed_k, int budget, int result_k, int node_cap,
                         double theta_propagate, double decay,
                         std::string trace_id, std::string query_id) {
            starling::retrieval::PatternCompletionParams p;
            p.tenant_id = std::move(tenant_id);
            p.holder_id = std::move(holder_id);
            p.holder_perspective = std::move(holder_perspective);
            p.cue_text = std::move(cue_text);
            p.seed_k = seed_k; p.budget = budget; p.result_k = result_k;
            p.node_cap = node_cap; p.theta_propagate = theta_propagate; p.decay = decay;
            p.trace_id = std::move(trace_id); p.query_id = std::move(query_id);
            return p;
        }),
        py::arg("tenant_id") = "", py::arg("holder_id") = "",
        py::arg("holder_perspective") = "", py::arg("cue_text") = "",
        py::arg("seed_k") = 5, py::arg("budget") = 20, py::arg("result_k") = 20,
        py::arg("node_cap") = 1000, py::arg("theta_propagate") = 0.05,
        py::arg("decay") = 0.5, py::arg("trace_id") = "", py::arg("query_id") = "")
        .def_readwrite("tenant_id",          &starling::retrieval::PatternCompletionParams::tenant_id)
        .def_readwrite("holder_id",          &starling::retrieval::PatternCompletionParams::holder_id)
        .def_readwrite("holder_perspective", &starling::retrieval::PatternCompletionParams::holder_perspective)
        .def_readwrite("cue_text",           &starling::retrieval::PatternCompletionParams::cue_text)
        .def_readwrite("seed_k",             &starling::retrieval::PatternCompletionParams::seed_k)
        .def_readwrite("budget",             &starling::retrieval::PatternCompletionParams::budget)
        .def_readwrite("result_k",           &starling::retrieval::PatternCompletionParams::result_k)
        .def_readwrite("node_cap",           &starling::retrieval::PatternCompletionParams::node_cap)
        .def_readwrite("theta_propagate",    &starling::retrieval::PatternCompletionParams::theta_propagate)
        .def_readwrite("decay",              &starling::retrieval::PatternCompletionParams::decay)
        .def_readwrite("trace_id",           &starling::retrieval::PatternCompletionParams::trace_id)
        .def_readwrite("query_id",           &starling::retrieval::PatternCompletionParams::query_id);

    py::class_<starling::retrieval::CompletionScored>(m, "CompletionScored")
        .def_readonly("row",        &starling::retrieval::CompletionScored::row)
        .def_readonly("activation", &starling::retrieval::CompletionScored::activation);

    py::class_<starling::retrieval::CompletionResult>(m, "CompletionResult")
        .def_readonly("rows",                 &starling::retrieval::CompletionResult::rows)
        .def_readonly("completion_truncated", &starling::retrieval::CompletionResult::completion_truncated)
        .def_readonly("degraded",             &starling::retrieval::CompletionResult::degraded);

    py::class_<starling::retrieval::PatternCompletor>(m, "PatternCompletor")
        .def(py::init<starling::persistence::SqliteAdapter&,
                      starling::retrieval::SemanticRetriever&>(),
             py::keep_alive<1, 2>(), py::keep_alive<1, 3>(),
             py::arg("adapter"), py::arg("seeds"))
        .def("complete",
             [](starling::retrieval::PatternCompletor& s,
                const starling::retrieval::PatternCompletionParams& p) {
                 return s.complete(s.connection(), p);
             },
             py::arg("params"));
}

}  // namespace starling::bindings
