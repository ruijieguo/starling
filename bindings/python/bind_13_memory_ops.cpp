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
             starling::extractor::ValidationPolicy policy) {
              starling::memoryops::ConverseParams p;
              p.tenant_id          = tenant_id;
              p.holder_id          = holder_id;
              p.interlocutor       = interlocutor;
              p.adapter_name       = adapter_name;
              p.source_prefix      = source_prefix;
              p.created_at_iso8601 = created_at_iso8601;
              p.message            = message;
              p.recall_k           = recall_k;
              starling::memoryops::ConverseOutcome r;
              {
                  py::gil_scoped_release release;
                  r = starling::memoryops::converse(adapter, chat_llm, extraction_llm,
                                                    semantic, extraction_prompt, p, policy);
              }
              return py::dict("reply"_a = r.reply, "ok"_a = r.ok, "error"_a = r.error,
                              "context_pack"_a = r.context_pack, "abstained"_a = r.abstained,
                              "statement_ids"_a = r.statement_ids,
                              "remember_ok"_a = r.remember_ok,
                              "remember_error"_a = r.remember_error);
          },
          py::arg("adapter"), py::arg("chat_llm"), py::arg("extraction_llm"),
          py::arg("semantic"), py::arg("extraction_prompt"),
          py::arg("tenant_id"), py::arg("holder_id"), py::arg("interlocutor"),
          py::arg("adapter_name"), py::arg("source_prefix"),
          py::arg("created_at_iso8601"), py::arg("message"), py::arg("recall_k") = 6,
          py::arg("policy") = starling::extractor::ValidationPolicy{});

    m.def("memory_tick_all",
          [](starling::persistence::SqliteAdapter& adapter,
             starling::embedding::EmbeddingWorker& worker,
             starling::prospective::PolicyEngine& policy,
             const std::string& now_iso) {
              starling::memoryops::TickOutcome t;
              {
                  py::gil_scoped_release release;
                  t = starling::memoryops::tick_all(adapter, worker, policy, now_iso);
              }
              return py::dict("embedded"_a = t.embedded, "fired"_a = t.fired,
                              "broken"_a = t.broken, "auto_withdrawn"_a = t.auto_withdrawn,
                              "replay_sampled"_a = t.replay_sampled,
                              "consolidated"_a = t.consolidated,
                              "ttl_archived"_a = t.ttl_archived,
                              "projected"_a = t.projected,
                              "dispatched"_a = t.dispatched);
          },
          py::arg("adapter"), py::arg("worker"), py::arg("policy"), py::arg("now_iso"));

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
