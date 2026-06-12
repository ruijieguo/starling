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

#include "starling/memory/memory_ops.hpp"

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
             const py::bytes& payload) {
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
                  r = starling::memoryops::remember(adapter, llm, prompt_template, p);
              }
              return py::dict("engram_ref"_a = r.engram_ref,
                              "statement_ids"_a = r.statement_ids,
                              "outcome"_a = r.outcome);
          },
          py::arg("adapter"), py::arg("llm"), py::arg("prompt_template"),
          py::arg("tenant_id"), py::arg("holder_id"), py::arg("interlocutor"),
          py::arg("adapter_name"), py::arg("source_prefix"),
          py::arg("created_at_iso8601"), py::arg("payload"));

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
}

}  // namespace starling::bindings
