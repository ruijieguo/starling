// bind_13_memory_ops — remember/tick_all 管线编排绑定(2026-06-11 边界归位)。
//
// 两个入口都用 gil_scoped_release:remember 内含 LLM 网络调用(真模型
// 20-110s+ 重试退避)、tick_all 内含批量嵌入网络调用——绑定层若持 GIL,
// dashboard 把工作丢进 anyio 线程也救不了事件循环(线程换了、GIL 没放,
// 其余请求与 WS 心跳照样冻结)。释放期间只执行纯 C++,不触碰 Python 对象。

#include "bind_common.hpp"

#include <cstdint>
#include <string>
#include <vector>

#include "starling/extractor/statement_validator.hpp"
#include "starling/memory/memory_ops.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/store/episodic_event_store.hpp"

namespace starling::bindings {

namespace {

// Build a TokenSink that relays deltas to a Python callback, or an empty sink
// when on_token is None. Extracted verbatim (incl. every comment) from the
// memory_converse binding body so memory_generate_stream can share the exact
// same noexcept PyGILState relay logic — behavior-neutral extraction, not a
// rewrite.
//
// Lifetime contract (unchanged): the sink captures on_token BY REFERENCE, so
// the caller must keep on_token alive across every sink invocation — both
// call sites (memory_converse's and memory_generate_stream's lambdas) satisfy
// this because on_token is a function parameter that outlives the C++ call
// the sink is invoked from (converse()/generate_stream() call the sink
// synchronously on this thread, inside the gil_scoped_release block the
// caller wraps around it).
starling::extractor::TokenSink make_token_sink(const py::object& on_token) {
    // 流式回调:非空 Python on_token → C++ TokenSink。converse 在 GIL
    // 释放下运行(下方 release 块),sink 每个 delta 重新 acquire GIL 再
    // 回调 Python(标准 pybind「从已释放 GIL 回调 Python」模式)。
    // on_token=None → 空 sink,converse 走非流式路径(等价旧行为)。
    // sink 在 release 块外声明,其析构(decref on_token)在 GIL 重持后发生。
    starling::extractor::TokenSink sink;
    if (!on_token.is_none()) {
        // Capture on_token by reference: converse() calls the sink
        // synchronously on THIS thread (inside the gil_scoped_release
        // block below), so the param outlives every sink invocation,
        // and a reference capture keeps the closure trivially
        // destructible (no py::object copy/move/dtor to reason about).
        sink = [&on_token](std::string_view delta) noexcept {
            // Relay one delta to the Python callback. Pure C-API + raw
            // PyGILState ensure/release — all noexcept — so the sink
            // PROVABLY cannot throw: nothing can escape into the C++
            // converse across the released GIL (a thrown pybind call or
            // a non-noexcept gil RAII ctor would). The C-API sets PyErr
            // instead of throwing; a failed relay just drops the delta
            // (the reply is still generated + persisted). Runs on the
            // C++ worker thread, so PyGILState_Ensure (not a held GIL)
            // is the correct acquire.
            const PyGILState_STATE gstate = PyGILState_Ensure();
            PyObject* arg = PyUnicode_FromStringAndSize(
                delta.data(), static_cast<Py_ssize_t>(delta.size()));
            if (arg != nullptr) {
                Py_XDECREF(PyObject_CallOneArg(on_token.ptr(), arg));
                Py_DECREF(arg);
            }
            if (PyErr_Occurred() != nullptr) {
                PyErr_Clear();
            }
            PyGILState_Release(gstate);
        };
    }
    return sink;
}

}  // namespace

void bind_13_memory_ops(pybind11::module_& m) {
    using namespace pybind11::literals;

    m.def("memory_remember",
          [](starling::persistence::SqliteAdapter& adapter,
             starling::extractor::LLMAdapter& llm,
             const std::string& prompt_template,
             const std::string& tenant_id, const std::string& holder_id,
             const std::string& interlocutor, const std::string& adapter_name,
             const std::string& source_prefix, const std::string& created_at_iso8601,
             const py::bytes& payload,
             starling::extractor::ValidationPolicy policy) {
              starling::memoryops::RememberParams p;
              p.tenant_id         = tenant_id;
              p.holder_id         = holder_id;
              p.interlocutor      = interlocutor;
              p.adapter_name      = adapter_name;
              p.source_prefix     = source_prefix;
              p.created_at_iso8601 = created_at_iso8601;
              {   // bytes → vector 必须在持 GIL 时完成
                  const std::string raw = payload;
                  p.payload.assign(raw.begin(), raw.end());
              }
              starling::memoryops::RememberOutcome r;
              {
                  py::gil_scoped_release release;
                  r = starling::memoryops::remember(adapter, llm, prompt_template, p, policy);
              }
              return py::dict("engram_ref"_a = r.engram_ref,
                              "statement_ids"_a = r.statement_ids,
                              "outcome"_a = r.outcome);
          },
          py::arg("adapter"), py::arg("llm"), py::arg("prompt_template"),
          py::arg("tenant_id"), py::arg("holder_id"), py::arg("interlocutor"),
          py::arg("adapter_name"), py::arg("source_prefix"),
          py::arg("created_at_iso8601"), py::arg("payload"),
          py::arg("policy") = starling::extractor::ValidationPolicy{});

    // Phase 2c: chat-with-memory turn. chat_llm + extraction_llm may be the same
    // object (chat role falls back to extraction). GIL released around the whole
    // C++ converse (recall + generate network + remember); the adapters are C++
    // objects so their virtuals run lock-free during the release.
    m.def("memory_converse",
          [](starling::persistence::SqliteAdapter& adapter,
             starling::extractor::LLMAdapter& chat_llm,
             starling::extractor::LLMAdapter& extraction_llm,
             starling::retrieval::SemanticRetriever& semantic,
             const std::string& extraction_prompt,
             const std::string& tenant_id, const std::string& holder_id,
             const std::string& interlocutor, const std::string& adapter_name,
             const std::string& source_prefix, const std::string& created_at_iso8601,
             const std::string& message, int recall_k,
             const starling::extractor::ValidationPolicy& policy,
             const py::object& on_token) {
              starling::memoryops::ConverseParams p;
              p.tenant_id          = tenant_id;
              p.holder_id          = holder_id;
              p.interlocutor       = interlocutor;
              p.adapter_name       = adapter_name;
              p.source_prefix      = source_prefix;
              p.created_at_iso8601 = created_at_iso8601;
              p.message            = message;
              p.recall_k           = recall_k;
              auto sink = make_token_sink(on_token);
              starling::memoryops::ConverseOutcome r;
              {
                  py::gil_scoped_release release;
                  r = starling::memoryops::converse(adapter, chat_llm, extraction_llm,
                                                    semantic, extraction_prompt, p, policy, sink);
              }
              return py::dict("reply"_a = r.reply, "ok"_a = r.ok, "error"_a = r.error,
                              "context_pack"_a = r.context_pack, "abstained"_a = r.abstained,
                              "statement_ids"_a = r.statement_ids,
                              "remember_ok"_a = r.remember_ok,
                              "remember_error"_a = r.remember_error,
                              "gen_prompt_tokens"_a = r.gen_prompt_tokens,
                              "gen_completion_tokens"_a = r.gen_completion_tokens,
                              "gen_total_tokens"_a = r.gen_total_tokens,
                              "gen_latency_ms"_a = r.gen_latency_ms);
          },
          py::arg("adapter"), py::arg("chat_llm"), py::arg("extraction_llm"),
          py::arg("semantic"), py::arg("extraction_prompt"),
          py::arg("tenant_id"), py::arg("holder_id"), py::arg("interlocutor"),
          py::arg("adapter_name"), py::arg("source_prefix"),
          py::arg("created_at_iso8601"), py::arg("message"), py::arg("recall_k") = 6,
          py::arg("policy") = starling::extractor::ValidationPolicy{},
          py::arg("on_token") = py::none());

    // 三相拆分(2026-07-05 锁外生成):host 在 prepare/commit 段持引擎锁、
    // generate 段释放——三个绑定共享单体的语义(C++ 内联同三相)。
    py::class_<starling::memoryops::ConversePrepared>(m, "ConversePrepared")
        .def_readonly("prompt",       &starling::memoryops::ConversePrepared::prompt)
        .def_readonly("context_pack", &starling::memoryops::ConversePrepared::context_pack)
        .def_readonly("abstained",    &starling::memoryops::ConversePrepared::abstained);

    m.def("memory_converse_prepare",
          [](starling::persistence::SqliteAdapter& adapter,
             starling::retrieval::SemanticRetriever& semantic,
             const std::string& tenant_id, const std::string& holder_id,
             const std::string& interlocutor, const std::string& adapter_name,
             const std::string& source_prefix, const std::string& created_at_iso8601,
             const std::string& message, int recall_k) {
              starling::memoryops::ConverseParams params;
              params.tenant_id          = tenant_id;
              params.holder_id          = holder_id;
              params.interlocutor       = interlocutor;
              params.adapter_name       = adapter_name;
              params.source_prefix      = source_prefix;
              params.created_at_iso8601 = created_at_iso8601;
              params.message            = message;
              params.recall_k           = recall_k;
              starling::memoryops::ConversePrepared prep;
              {
                  py::gil_scoped_release release;   // 内含 query-embed 网络
                  prep = starling::memoryops::converse_prepare(adapter, semantic, params);
              }
              return prep;
          },
          py::arg("adapter"), py::arg("semantic"), py::arg("tenant_id"),
          py::arg("holder_id"), py::arg("interlocutor"), py::arg("adapter_name"),
          py::arg("source_prefix"), py::arg("created_at_iso8601"),
          py::arg("message"), py::arg("recall_k") = 6);

    m.def("memory_generate_stream",
          [](starling::extractor::LLMAdapter& chat_llm, const std::string& prompt,
             const py::object& on_token) {
              auto sink = make_token_sink(on_token);
              starling::extractor::LLMResponse resp;
              {
                  py::gil_scoped_release release;   // 纯网络段
                  resp = chat_llm.generate_stream(prompt, sink);
              }
              return resp;
          },
          py::arg("chat_llm"), py::arg("prompt"), py::arg("on_token") = py::none());

    m.def("memory_converse_commit",
          [](starling::persistence::SqliteAdapter& adapter,
             starling::extractor::LLMAdapter& extraction_llm,
             const std::string& extraction_prompt,
             const std::string& tenant_id, const std::string& holder_id,
             const std::string& interlocutor, const std::string& adapter_name,
             const std::string& source_prefix, const std::string& created_at_iso8601,
             const std::string& message, int recall_k,
             const starling::memoryops::ConversePrepared& prepared,
             const starling::extractor::LLMResponse& gen_resp,
             const starling::extractor::ValidationPolicy& policy) {
              starling::memoryops::ConverseParams params;
              params.tenant_id          = tenant_id;
              params.holder_id          = holder_id;
              params.interlocutor       = interlocutor;
              params.adapter_name       = adapter_name;
              params.source_prefix      = source_prefix;
              params.created_at_iso8601 = created_at_iso8601;
              params.message            = message;
              params.recall_k           = recall_k;
              starling::memoryops::ConverseOutcome outcome;
              {
                  py::gil_scoped_release release;   // 内含 extraction 网络
                  outcome = starling::memoryops::converse_commit(
                      adapter, extraction_llm, extraction_prompt, params, prepared,
                      gen_resp, policy);
              }
              return py::dict("reply"_a = outcome.reply, "ok"_a = outcome.ok,
                              "error"_a = outcome.error,
                              "context_pack"_a = outcome.context_pack,
                              "abstained"_a = outcome.abstained,
                              "statement_ids"_a = outcome.statement_ids,
                              "remember_ok"_a = outcome.remember_ok,
                              "remember_error"_a = outcome.remember_error,
                              "gen_prompt_tokens"_a = outcome.gen_prompt_tokens,
                              "gen_completion_tokens"_a = outcome.gen_completion_tokens,
                              "gen_total_tokens"_a = outcome.gen_total_tokens,
                              "gen_latency_ms"_a = outcome.gen_latency_ms);
          },
          py::arg("adapter"), py::arg("extraction_llm"), py::arg("extraction_prompt"),
          py::arg("tenant_id"), py::arg("holder_id"), py::arg("interlocutor"),
          py::arg("adapter_name"), py::arg("source_prefix"),
          py::arg("created_at_iso8601"), py::arg("message"), py::arg("recall_k") = 6,
          py::arg("prepared"), py::arg("gen_resp"),
          py::arg("policy") = starling::extractor::ValidationPolicy{});

    m.def("memory_tick_all",
          [](starling::persistence::SqliteAdapter& adapter,
             starling::embedding::EmbeddingWorker& worker,
             starling::prospective::PolicyEngine& policy,
             const std::string& now_iso,
             starling::RuntimeHealth health) {
              starling::memoryops::TickOutcome t;
              {
                  py::gil_scoped_release release;
                  t = starling::memoryops::tick_all(adapter, worker, policy, now_iso, health);
              }
              py::list stages;
              for (const auto& timing : t.stage_timings_ms) {
                  stages.append(py::dict("stage"_a = timing.stage,
                                         "ms"_a = timing.duration_ms));
              }
              return py::dict("embedded"_a = t.embedded, "fired"_a = t.fired,
                              "broken"_a = t.broken, "auto_withdrawn"_a = t.auto_withdrawn,
                              "replay_sampled"_a = t.replay_sampled,
                              "consolidated"_a = t.consolidated,
                              "ttl_archived"_a = t.ttl_archived,
                              "projected"_a = t.projected,
                              "dispatched"_a = t.dispatched,
                              "stage_timings_ms"_a = stages,
                              "stages_skipped"_a = t.stages_skipped);
          },
          py::arg("adapter"), py::arg("worker"), py::arg("policy"), py::arg("now_iso"),
          py::arg("health") = starling::RuntimeHealth::READY);

    m.def("memory_forget",
          [](starling::persistence::SqliteAdapter& adapter,
             const std::string& tenant, const std::vector<std::string>& ids,
             const std::string& now_iso) {
              int n = 0;
              {
                  py::gil_scoped_release release;
                  n = starling::memoryops::forget(adapter, tenant, ids, now_iso);
              }
              return n;
          },
          py::arg("adapter"), py::arg("tenant"), py::arg("ids"), py::arg("now_iso"));

    // 片 6 干预集:人工审批 review_requested → approved(守卫幂等、tenant-scoped)。
    // 返回转换计数(1=已批准,0=非 review_requested 行 no-op)。reject 不在此(=memory_forget)。
    m.def("memory_approve_review",
          [](starling::persistence::SqliteAdapter& adapter,
             const std::string& tenant, const std::string& stmt_id,
             const std::string& now_iso) {
              int n = 0;
              {
                  py::gil_scoped_release release;
                  n = starling::memoryops::approve_review(adapter, tenant, stmt_id, now_iso);
              }
              return n;
          },
          py::arg("adapter"), py::arg("tenant"), py::arg("stmt_id"), py::arg("now_iso"));

    // sub-project A phase 6 Task 6.1:暴露 EpisodicEventStore::latest_event_location。
    // 主题 theme 的最高 seq 事件的 location(地面真值「当前所在」),无事件返回 ""。
    // 纯本地 SQLite 读(无网络),薄绑定转发到核心层单属主 store。
    m.def("latest_event_location",
          [](starling::persistence::Connection& conn, const std::string& tenant,
             const std::string& theme) {
              starling::store::EpisodicEventStore store(conn);
              return store.latest_event_location(tenant, theme);
          },
          py::arg("connection"), py::arg("tenant"), py::arg("theme"));
}

}  // namespace starling::bindings
