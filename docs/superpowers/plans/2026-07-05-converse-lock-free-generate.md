# converse 生成段出锁(三相拆分)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 converse 的 chat 生成段移出 `DashboardEngine._lock`:C++ 拆 `converse_prepare` /(host 驱动 `generate_stream`)/ `converse_commit`,单体 `converse` 内联同三相(字节级行为不变、单一语义源);engine 三段化(锁内 prepare + 局部 chat 引用 → 锁外 generate → 锁内 commit)。

**Architecture:** C++ 核心持有全部语义(写门 fail-fast、围栏/prompt、失败语义 A、诚实 remember_ok);host 只做三行顺序调用 + 锁管理,顺序由类型签名强制(commit 需要 prepared)。锁外段零 DB 访问(generate_stream 纯网络),单写者纪律不变。

**Tech Stack:** C++20(`src/memory/`)、GoogleTest、pybind11(`bindings/python/bind_13_memory_ops.cpp`)、FastAPI host(`python/starling/dashboard/engine.py`)。

**Approved spec:** `docs/superpowers/specs/2026-07-05-converse-lock-free-generate-design.md`(branch `fix/converse-lock-free-generate` @ `8c7376e`,off `main@2a23546`)。
**Spec 偏差(计划钉死):** `converse_commit` 需要 `const extractor::ValidationPolicy& policy = {}` 参数(spec 签名草图漏了——单体相位 4 的 `remember(..., policy)` 需要它)。

## Global Constraints

- 架构边界(硬):围栏/prompt/失败语义 A/诚实 remember_ok 全在 C++;host 只做三行顺序调用+锁管理;单体 converse 与三相共用同一实现(单一语义源)。
- 单写者不变:锁外段零 DB 访问(generate_stream 纯网络)。
- 失败语义 A 不变:generate 失败→干净无回复;remember 失败(含中途 DRAINING 写门拒)→reply 保留+remember_ok=false。
- WS on_token 桥(call_soon_threadsafe)与回调契约(cheap/thread-safe/不碰 DB)不动。
- 构建:`export PATH="$PWD/.venv/bin:$PATH"` 后 `python scripts/configure_build.py --build --python-editable`(cmake/ninja 在 .venv/bin;build 目录 build-macos);提交门:全量 ctest + pytest tests/python 绿。
- pytest 一律 `.venv/bin/python -m pytest`。
- clang-tidy CI-only,新 C++ 由构清洁:标识符≥3字符(**从单体移入新函数的行算新行**——原 `h`/`q`/`r`/`rp`/`rem` 必须改名 `seed_hash`/`query`/`outcome`/`rem_params`/`rem_result`)、braces around statements、designated init、bind_13 的 noexcept PyGILState sink 模式逐字复用勿改写;tests/cpp 不受门。
- git:显式路径 `git add`(禁 `.`/`-A`);不用 `--no-verify`/`--amend`;commit 尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- NEVER merge:PR + CI 绿 + 用户明确合并。

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `include/starling/memory/memory_ops.hpp` | converse 契约 | + `ConversePrepared` + 两个入口声明(现 converse 声明后、`neutralize_recall_fence` 前) |
| `src/memory/memory_ops.cpp` | converse 实现 | 105-194 行重组为 prepare/commit + 单体内联 |
| `tests/cpp/test_converse_phases.cpp` | 三相钉测 | 新文件(parity/失败语义/写门) |
| `tests/cpp/CMakeLists.txt` | 测试注册 | + `test_converse_phases.cpp`(显式列表,按字母序插入) |
| `bindings/python/bind_13_memory_ops.cpp` | 绑定 | + `ConversePrepared` 类 + 三个 m.def;现 `memory_converse` 不动 |
| `python/starling/_memory_core.py` | MemoryCore 薄转发 | + `_converse_turn_args` helper + `converse_prepare`/`generate_stream`/`converse_commit`;现 `converse()` 改用 helper(去重),行为不变 |
| `python/starling/dashboard/engine.py` | 锁三段化 | + `_resolve_chat` + `_converse_phased`;`converse`/`converse_stream` 改走它;删 `_role_override("chat_llm",…)` 用法(`remember` 的 `_role_override("llm",…)` 不动) |
| `tests/python/test_converse_lock_release.py` | 锁纪律 | 新文件 |

---

### Task 1: C++ 三相拆分 + 钉测

**Files:**
- Modify: `include/starling/memory/memory_ops.hpp`(在 `converse` 声明之后、`neutralize_recall_fence` 声明之前插入)
- Modify: `src/memory/memory_ops.cpp:105-194`(converse 重组)
- Test: `tests/cpp/test_converse_phases.cpp`(新)
- Modify: `tests/cpp/CMakeLists.txt`(注册新测试文件)

**Interfaces:**
- Consumes(现有):`ConverseParams`/`ConverseOutcome`(memory_ops.hpp:59-85);`memoryops::remember`;`governance::require_write_admission`(WriteGateRejected 抛);`extractor::LLMResponse`/`LLMAdapter::generate_stream(prompt, TokenSink)`;`neutralize_recall_fence`;`crypto::sha256_hex`;`retrieval::RetrievalPlanner/PlannerQuery`。
- Produces(Task 2/3 依赖,签名逐字):
  - `struct ConversePrepared { std::string prompt; std::string context_pack; bool abstained = false; };`
  - `ConversePrepared converse_prepare(persistence::SqliteAdapter& adapter, retrieval::SemanticRetriever& semantic, const ConverseParams& params);`
  - `ConverseOutcome converse_commit(persistence::SqliteAdapter& adapter, extractor::LLMAdapter& extraction_llm, std::string_view extraction_prompt, const ConverseParams& params, const ConversePrepared& prepared, const extractor::LLMResponse& gen_resp, const extractor::ValidationPolicy& policy = {});`

- [ ] **Step 1: 写失败的钉测**

新建 `tests/cpp/test_converse_phases.cpp`。include 块与夹具:`make_adapter`/`kCannedJson`/`row_count` 逐字抄 `tests/cpp/test_memory_ops.cpp:6-40`;`StubEmbeddingAdapter`/`SqliteBlobVectorIndex`/`SemanticRetriever` 的 include 路径与构造逐字抄 `tests/cpp/test_pattern_completor.cpp` 头部(`SemanticRetriever sr(*adapter, emb, idx);` 模式)。核心内容:

```cpp
// tests/cpp/test_converse_phases.cpp — converse 三相拆分(2026-07-05 锁外生成)。
// 钉住:prepare+generate+commit ≡ 单体 converse(parity)、generate 失败 →
// commit 干净无回复、写门中途关闭 → reply 保留 + remember_ok=false。零网络。

namespace starling::memoryops {
namespace {

ConverseParams conv_params(std::string_view message) {
    ConverseParams cp;
    cp.tenant_id          = "default";
    cp.holder_id          = "cog-self";
    cp.interlocutor       = "alice";
    cp.adapter_name       = "facade";
    cp.source_prefix      = "conv-";
    cp.created_at_iso8601 = "2026-07-05T10:00:00Z";
    cp.message            = std::string(message);
    cp.recall_k           = 6;
    return cp;
}

struct Fixture {   // 每条路径一套独立 :memory: 库(parity 需要隔离副作用)
    std::unique_ptr<persistence::SqliteAdapter> adapter = make_adapter();
    embedding::StubEmbeddingAdapter emb{8};
    vector_index::SqliteBlobVectorIndex idx;   // 命名空间以 test_pattern_completor.cpp 实际 using 为准
    retrieval::SemanticRetriever semantic{*adapter, emb, idx};
    extractor::FakeLLMAdapter chat;
    extractor::FakeLLMAdapter extraction;
    Fixture() {
        chat.set_default_response(extractor::LLMResponse{.raw_xml = "Reply text.", .ok = true});
        extraction.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    }
};

void expect_parity(const ConverseOutcome& mono, const ConverseOutcome& phased) {
    EXPECT_EQ(mono.ok, phased.ok);
    EXPECT_EQ(mono.reply, phased.reply);
    EXPECT_EQ(mono.error, phased.error);
    EXPECT_EQ(mono.context_pack, phased.context_pack);
    EXPECT_EQ(mono.abstained, phased.abstained);
    EXPECT_EQ(mono.statement_ids.size(), phased.statement_ids.size());  // id 含随机成分,比数量
    EXPECT_EQ(mono.remember_ok, phased.remember_ok);
    EXPECT_EQ(mono.remember_error, phased.remember_error);
    EXPECT_EQ(mono.gen_total_tokens, phased.gen_total_tokens);
}

}  // namespace

TEST(ConversePhases, PhasedEqualsMonolithNonStreaming) {
    Fixture mono_fx;
    const auto mono = converse(*mono_fx.adapter, mono_fx.chat, mono_fx.extraction,
                               mono_fx.semantic, "", conv_params("hello"), {}, {});
    Fixture phased_fx;
    const auto prepared = converse_prepare(*phased_fx.adapter, phased_fx.semantic,
                                           conv_params("hello"));
    const auto gen_resp = phased_fx.chat.generate_stream(prepared.prompt, {});
    const auto phased = converse_commit(*phased_fx.adapter, phased_fx.extraction, "",
                                        conv_params("hello"), prepared, gen_resp);
    expect_parity(mono, phased);
    EXPECT_TRUE(phased.ok);
    EXPECT_TRUE(phased.remember_ok);
}

TEST(ConversePhases, PhasedEqualsMonolithStreaming) {
    // 流式:两条路径都挂 sink,delta 拼接 == 最终 reply,且 parity 保持。
    Fixture mono_fx;
    std::string mono_streamed;
    const auto mono = converse(*mono_fx.adapter, mono_fx.chat, mono_fx.extraction,
                               mono_fx.semantic, "", conv_params("hi"), {},
                               [&mono_streamed](std::string_view d) { mono_streamed += d; });
    Fixture phased_fx;
    const auto prepared = converse_prepare(*phased_fx.adapter, phased_fx.semantic,
                                           conv_params("hi"));
    std::string phased_streamed;
    const auto gen_resp = phased_fx.chat.generate_stream(
        prepared.prompt, [&phased_streamed](std::string_view d) { phased_streamed += d; });
    const auto phased = converse_commit(*phased_fx.adapter, phased_fx.extraction, "",
                                        conv_params("hi"), prepared, gen_resp);
    expect_parity(mono, phased);
    EXPECT_EQ(mono_streamed, mono.reply);
    EXPECT_EQ(phased_streamed, phased.reply);
}

TEST(ConversePhases, CommitOnGenerateFailureIsCleanNoReply) {
    Fixture fx;
    const auto prepared = converse_prepare(*fx.adapter, fx.semantic, conv_params("hello"));
    const int before = row_count(fx.adapter->connection(),
                                 "SELECT COUNT(*) FROM statements");
    extractor::LLMResponse failed;
    failed.ok = false;
    failed.error = "transport_error:SSL connect error";
    const auto out = converse_commit(*fx.adapter, fx.extraction, "",
                                     conv_params("hello"), prepared, failed);
    EXPECT_FALSE(out.ok);
    EXPECT_EQ(out.error, "transport_error:SSL connect error");
    EXPECT_TRUE(out.reply.empty());
    EXPECT_TRUE(out.statement_ids.empty());
    EXPECT_FALSE(out.remember_ok);
    EXPECT_EQ(out.context_pack, prepared.context_pack);   // 轨迹仍可回显
    EXPECT_EQ(row_count(fx.adapter->connection(),
                        "SELECT COUNT(*) FROM statements"), before);  // 零沉淀
}

TEST(ConversePhases, PrepareFailsFastWhenGateClosed) {
    Fixture fx;
    fx.adapter->set_write_admit([] { return false; });
    EXPECT_THROW(converse_prepare(*fx.adapter, fx.semantic, conv_params("x")),
                 governance::WriteGateRejected);   // include write_gate.hpp
}

TEST(ConversePhases, GateClosingMidTurnKeepsReplyAndFlagsRememberError) {
    // 模拟「锁外生成期间翻 DRAINING」:prepare 时门开,commit 前关门。
    Fixture fx;
    const auto prepared = converse_prepare(*fx.adapter, fx.semantic, conv_params("hello"));
    const auto gen_resp = fx.chat.generate_stream(prepared.prompt, {});
    fx.adapter->set_write_admit([] { return false; });
    const auto out = converse_commit(*fx.adapter, fx.extraction, "",
                                     conv_params("hello"), prepared, gen_resp);
    EXPECT_TRUE(out.ok);                       // 失败语义 A:回复绝不丢
    EXPECT_EQ(out.reply, "Reply text.");
    EXPECT_FALSE(out.remember_ok);
    EXPECT_FALSE(out.remember_error.empty());  // WriteGateRejected e.what() 可观测
}

}  // namespace starling::memoryops
```

并在 `tests/cpp/CMakeLists.txt` 的 `add_executable(starling_tests` 显式列表中按字母序加一行 `    test_converse_phases.cpp`。

- [ ] **Step 2: 跑测试确认编译失败(符号不存在)**

Run: `export PATH="$PWD/.venv/bin:$PATH" && python scripts/configure_build.py --build 2>&1 | tail -5`
Expected: 编译错误 `converse_prepare`/`converse_commit`/`ConversePrepared` 未声明。

- [ ] **Step 3: 实现三相拆分**

`include/starling/memory/memory_ops.hpp` 在 converse 声明(:106)后插入(Interfaces 节的三条签名 + 注释,注释含:prepare 开头写门 fail-fast、commit 不另查 admission 因 remember 门前抛已处理中途 DRAINING、单体内联同三相=单一语义源)。

`src/memory/memory_ops.cpp` 把现 `converse`(105-194)重组为(**变量改名对齐 clang-tidy:`h`→`seed_hash`、`q`→`query`、`r`→`outcome`、`rp`→`rem_params`、`rem`→`rem_result`;原相位注释与安全注释(围栏/二阶注入块)原样保留搬运**):

```cpp
ConversePrepared converse_prepare(persistence::SqliteAdapter& adapter,
                                  retrieval::SemanticRetriever& semantic,
                                  const ConverseParams& params) {
    governance::require_write_admission(adapter);   // fail-fast:别白烧生成段
    ConversePrepared prep;
    // ── 1. recall (read) ──(原相位 1 原样,变量改名)
    const std::string seed_hash = crypto::sha256_hex(
        params.tenant_id + "|" + params.created_at_iso8601 + "|" + params.message);
    retrieval::PlannerQuery query;
    query.tenant_id     = params.tenant_id;
    query.querier       = params.holder_id;
    query.intent        = retrieval::QueryIntent::FACT_LOOKUP;
    query.text          = params.message;
    query.as_of_iso8601 = params.created_at_iso8601;
    query.k             = params.recall_k;
    query.trace_id      = "conv-" + seed_hash.substr(0, 16);
    query.query_id      = "convq-" + seed_hash.substr(16, 16);
    retrieval::RetrievalPlanner planner(adapter, semantic);
    const auto plan = planner.run(query);
    prep.context_pack = plan.context_pack;
    prep.abstained    = plan.abstained;
    // ── 2. inject ──(原相位 2 原样:安全注释块 + 围栏 + prompt 字面量逐字搬运)
    const std::string fenced = neutralize_recall_fence(plan.context_pack);
    prep.prompt = /* 原 142-150 的 prompt 拼接字面量,逐字 */;
    return prep;
}

ConverseOutcome converse_commit(persistence::SqliteAdapter& adapter,
                                extractor::LLMAdapter& extraction_llm,
                                std::string_view extraction_prompt,
                                const ConverseParams& params,
                                const ConversePrepared& prepared,
                                const extractor::LLMResponse& gen_resp,
                                const extractor::ValidationPolicy& policy) {
    ConverseOutcome outcome;
    outcome.context_pack = prepared.context_pack;
    outcome.abstained    = prepared.abstained;
    if (!gen_resp.ok) {   // 失败语义 A:generate 失败 → 干净的无回复轮
        outcome.ok = false;
        outcome.error = gen_resp.error.empty() ? "generate_failed" : gen_resp.error;
        return outcome;
    }
    outcome.ok = true;
    outcome.reply = gen_resp.raw_xml;
    outcome.gen_prompt_tokens     = gen_resp.prompt_tokens;
    outcome.gen_completion_tokens = gen_resp.completion_tokens;
    outcome.gen_total_tokens      = gen_resp.total_tokens;
    outcome.gen_latency_ms        = gen_resp.latency_ms;
    // ── 4. remember the exchange (write) ──(原相位 4 的 try/catch 原样搬运,
    // 变量改名;remember 门前的写门抛在 catch 里降级为 remember_error)
    try {
        const std::string exchange =
            "User: " + params.message + "\nAssistant: " + outcome.reply;
        RememberParams rem_params;
        rem_params.tenant_id          = params.tenant_id;
        rem_params.holder_id          = params.holder_id;
        rem_params.interlocutor       = params.interlocutor;
        rem_params.adapter_name       = params.adapter_name;
        rem_params.source_prefix      = params.source_prefix;
        rem_params.created_at_iso8601 = params.created_at_iso8601;
        rem_params.payload.assign(exchange.begin(), exchange.end());
        const auto rem_result =
            remember(adapter, extraction_llm, extraction_prompt, rem_params, policy);
        outcome.statement_ids = rem_result.statement_ids;
        const bool stored = (rem_result.outcome == "accepted" ||
                             rem_result.outcome == "idempotent");
        outcome.remember_ok = stored && !rem_result.extraction_failed;
        if (!outcome.remember_ok) {
            outcome.remember_error = rem_result.extraction_failed
                ? "extraction_failed" : ("not_stored:" + rem_result.outcome);
        }
    } catch (const std::exception& exc) {
        outcome.remember_ok = false;
        outcome.remember_error = exc.what();
    }
    return outcome;
}

ConverseOutcome converse(persistence::SqliteAdapter& adapter,
                         extractor::LLMAdapter& chat_llm,
                         extractor::LLMAdapter& extraction_llm,
                         retrieval::SemanticRetriever& semantic,
                         std::string_view extraction_prompt,
                         const ConverseParams& params,
                         const extractor::ValidationPolicy& policy,
                         const extractor::TokenSink& on_token) {
    // 单体 = 三相内联(单一语义源;host 分相调用与此逐字段等价,见钉测)。
    const ConversePrepared prepared = converse_prepare(adapter, semantic, params);
    const auto gen_resp = chat_llm.generate_stream(prepared.prompt, on_token);
    return converse_commit(adapter, extraction_llm, extraction_prompt,
                           params, prepared, gen_resp, policy);
}
```

(原相位 3 的 `!resp.ok` 短路与成本填充已全部移入 commit;原 `converse` 函数体删除仅剩内联。原相位 2 的安全注释块 134-141 与 prompt 字面量 142-150 逐字搬进 prepare。)

- [ ] **Step 4: 跑新钉测 + 既有全量 ctest**

Run: `export PATH="$PWD/.venv/bin:$PATH" && python scripts/configure_build.py --build && ctest --test-dir build-macos -R ConversePhases --output-on-failure 2>&1 | tail -10 && ctest --test-dir build-macos --output-on-failure 2>&1 | tail -3`
Expected: ConversePhases 5/5 PASS;全量 ctest 全绿(948±)。

- [ ] **Step 5: Commit**

```bash
git add include/starling/memory/memory_ops.hpp src/memory/memory_ops.cpp tests/cpp/test_converse_phases.cpp tests/cpp/CMakeLists.txt
git commit -m "refactor(memory): split converse into prepare/commit phases (monolith inlines them)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 绑定三入口

**Files:**
- Modify: `bindings/python/bind_13_memory_ops.cpp`(在现 `memory_converse` m.def 之后插入;现绑定不动)
- Test: `tests/python/test_converse_phases_binding.py`(新)

**Interfaces:**
- Consumes(Task 1):`ConversePrepared`/`converse_prepare`/`converse_commit`(签名见 Task 1 Produces);现绑定的 sink 模式(bind_13:84-118)与 outcome→dict 转换(bind_13:125-133)。
- Produces(Task 3 依赖):
  - `_core.ConversePrepared`:只读属性 `prompt`/`context_pack`/`abstained`
  - `_core.memory_converse_prepare(adapter, semantic, *, tenant_id, holder_id, interlocutor, adapter_name, source_prefix, created_at_iso8601, message, recall_k=6) → ConversePrepared`
  - `_core.memory_generate_stream(chat_llm, prompt, on_token=None) → LLMResponse`
  - `_core.memory_converse_commit(adapter, extraction_llm, extraction_prompt, *, tenant_id, holder_id, interlocutor, adapter_name, source_prefix, created_at_iso8601, message, recall_k=6, prepared, gen_resp, policy=ValidationPolicy()) → dict`(键与 `memory_converse` 返回完全一致)

- [ ] **Step 1: 写失败的绑定冒烟测试**

新建 `tests/python/test_converse_phases_binding.py`:

```python
"""三相绑定冒烟:prepare→generate→commit 组合的 dict shape 与单体 converse 一致。
夹具模式抄 tests/python/test_dashboard_commands.py(FakeLLMAdapter + DashboardEngine)。"""
from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _core_handles(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "b.db"), token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter(); fake.set_default_response(_STUB_JSON, True, "")
    eng.llm = fake
    return eng._core, fake     # MemoryCore + 抽取/聊天两用 fake


def test_phased_binding_matches_monolith_shape(tmp_path):
    core, fake = _core_handles(tmp_path)
    mono = core.converse("Bob owns auth", holder="self", now="2026-07-05T10:00:00Z")

    prepared = core.converse_prepare("Bob owns auth", holder="self",
                                     now="2026-07-05T10:00:00Z")
    assert prepared.prompt and "recalled_memory" in prepared.prompt
    gen = core.generate_stream(fake, prepared.prompt, None)
    assert gen.ok
    phased = core.converse_commit("Bob owns auth", prepared, gen, holder="self",
                                  now="2026-07-05T10:00:00Z")
    assert set(phased) == set(mono)          # dict 键完全一致
    assert phased["ok"] and phased["reply"] == gen.raw_xml
    assert phased["remember_ok"] in (True, False)


def test_generate_stream_relays_tokens(tmp_path):
    core, fake = _core_handles(tmp_path)
    prepared = core.converse_prepare("hi", holder="self", now="2026-07-05T10:00:00Z")
    seen: list[str] = []
    gen = core.generate_stream(fake, prepared.prompt, seen.append)
    assert gen.ok and "".join(seen) == gen.raw_xml
```

(注:该测试同时依赖 Task 3 的 MemoryCore 转发——Task 2 先以 `_core.memory_converse_prepare(...)` 直呼绑定写一版断言 ConversePrepared 属性 + LLMResponse 往返;Task 3 落地后本文件改为上面的 MemoryCore 版。为避免双写,Task 2 的 Step 1 直接写绑定层版本:用 `eng._core.rt.adapter`、`eng._core.semantic`、显式关键字参数,断言 `prepared.prompt` 非空、`memory_generate_stream` 的 sink 收到 delta、`memory_converse_commit` 返回键 == `memory_converse` 返回键。)

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/python/test_converse_phases_binding.py -q`
Expected: FAIL `AttributeError: module 'starling._core' has no attribute 'memory_converse_prepare'`。

- [ ] **Step 3: 实现绑定**

`bind_13_memory_ops.cpp` 在 `memory_converse` 的 m.def 之后加(ConverseParams 组装 lambda 与现 memory_converse 的 60-82 行同构;sink 块从 84-118 **逐字复制**;dict 转换从 125-133 **逐字复制**):

```cpp
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
              starling::memoryops::ConverseParams p;
              /* 字段赋值与 memory_converse 的 75-82 行同构 */
              starling::memoryops::ConversePrepared prep;
              {
                  py::gil_scoped_release release;   // 内含 query-embed 网络
                  prep = starling::memoryops::converse_prepare(adapter, semantic, p);
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
              starling::extractor::TokenSink sink;
              if (!on_token.is_none()) {
                  /* noexcept PyGILState sink —— 从 memory_converse 绑定逐字复制 */
              }
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
              starling::memoryops::ConverseParams p;
              /* 同上组装 */
              starling::memoryops::ConverseOutcome r;
              {
                  py::gil_scoped_release release;   // 内含 extraction 网络
                  r = starling::memoryops::converse_commit(
                      adapter, extraction_llm, extraction_prompt, p, prepared,
                      gen_resp, policy);
              }
              return py::dict(/* 与 memory_converse 的 dict 转换逐字一致 */);
          },
          py::arg("adapter"), py::arg("extraction_llm"), py::arg("extraction_prompt"),
          py::arg("tenant_id"), py::arg("holder_id"), py::arg("interlocutor"),
          py::arg("adapter_name"), py::arg("source_prefix"),
          py::arg("created_at_iso8601"), py::arg("message"), py::arg("recall_k") = 6,
          py::arg("prepared"), py::arg("gen_resp"),
          py::arg("policy") = starling::extractor::ValidationPolicy{});
```

- [ ] **Step 4: 构建 + 重装 + 测试绿**

Run: `export PATH="$PWD/.venv/bin:$PATH" && python scripts/configure_build.py --build --python-editable && .venv/bin/python -m pytest tests/python/test_converse_phases_binding.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add bindings/python/bind_13_memory_ops.cpp tests/python/test_converse_phases_binding.py
git commit -m "feat(bindings): expose converse prepare/generate/commit phases

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: MemoryCore 转发 + engine 锁三段化

**Files:**
- Modify: `python/starling/_memory_core.py:240-268`(converse 附近)
- Modify: `python/starling/dashboard/engine.py:362-419`(_role_override / converse / converse_stream)
- Test: `tests/python/test_converse_lock_release.py`(新);改 `tests/python/test_converse_phases_binding.py` 为 MemoryCore 版(Task 2 Step 1 里的正式版本)

**Interfaces:**
- Consumes(Task 2):`_core.memory_converse_prepare/memory_generate_stream/memory_converse_commit`、`_core.ConversePrepared`。
- Produces:
  - `MemoryCore.converse_prepare(message, *, holder=None, interlocutor=None, k=6, now=None) → ConversePrepared`
  - `MemoryCore.generate_stream(chat_llm, prompt, on_token=None) → LLMResponse`
  - `MemoryCore.converse_commit(message, prepared, gen_resp, *, holder=None, interlocutor=None, k=6, now=None) → dict`
  - `DashboardEngine._resolve_chat(provider) → LLMAdapter`(锁内调用)
  - `engine.converse/converse_stream` 外部签名不变。

- [ ] **Step 1: 写失败的锁纪律测试**

新建 `tests/python/test_converse_lock_release.py`:

```python
"""锁纪律:converse 的 chat 生成段不得持有 DashboardEngine._lock。
FakeLLMAdapter.set_delay_ms 在 C++ extract() 内睡(GIL 已释放)——生成段
人为拉长到 700ms;并发 tick 必须在生成期间拿到锁(<0.4s),拆锁前必然
阻塞 ≥0.55s(先 sleep(0.15) 再 tick)。chat/llm 注入模式抄
tests/python/test_dashboard_converse.py。"""
import threading
import time

from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _engine(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "lock.db"), token="")
    eng = DashboardEngine(cfg)
    extraction = _core.FakeLLMAdapter()
    extraction.set_default_response(_STUB_JSON, True, "")
    eng.llm = extraction
    chat = _core.FakeLLMAdapter()
    chat.set_default_response("a slow reply", True, "")
    chat.set_delay_ms(700)          # 生成段 = C++ 内睡 700ms(零网络)
    return eng, chat


def test_tick_interleaves_during_generate(tmp_path):
    eng, chat = _engine(tmp_path)
    eng.set_chat_adapter_for_test(chat)   # 如无此注入口,用 test_dashboard_converse.py 的既有方式
    out: dict = {}
    turn = threading.Thread(
        target=lambda: out.update(eng.converse("hello", holder="self")))
    turn.start()
    time.sleep(0.15)                       # prepare 是毫秒级 → 已进生成段
    start = time.monotonic()
    eng.tick("2026-07-05T00:00:00Z")       # 拆锁后:生成段中锁可得
    elapsed = time.monotonic() - start
    turn.join(timeout=5)
    assert out.get("ok") is True
    assert elapsed < 0.4, f"tick 等锁 {elapsed:.2f}s —— 生成段仍持锁"


def test_resolve_chat_local_reference(tmp_path):
    eng, chat = _engine(tmp_path)
    # None → role-bound 回退(chat_llm 未绑 → 抽取 llm)
    assert eng._resolve_chat(None) is eng._core.chat_llm or eng._resolve_chat(None) is eng._core.llm
    # 未配 provider → LLMNotConfigured
    import pytest
    from starling.dashboard.engine import _LLMNotConfigured
    with pytest.raises(_LLMNotConfigured):
        eng._resolve_chat("no-such-provider")
```

(实现时若 chat 注入方式与既有 `tests/python/test_dashboard_converse.py` 不同,以该文件的既有模式为准并同步修此测试——不得为测试在 engine 上新增 public 接口;`eng._core.chat_llm = chat` 直赋即可,MemoryCore 的 chat_llm 是公有属性。)

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/python/test_converse_lock_release.py -q`
Expected: `test_tick_interleaves_during_generate` FAIL(elapsed ≥0.55 —— 现单体持锁);`test_resolve_chat_local_reference` FAIL(`_resolve_chat` 不存在)。

- [ ] **Step 3: 实现 MemoryCore 转发**

`_memory_core.py`:从现 `converse()` 抽参数规整 helper 并让三方共用(现 converse 行为不变):

```python
    def _converse_turn_args(self, holder, now):
        """converse 三相共享的参数规整(与单体 converse 相同的缺省逻辑)。"""
        if self.llm is None:
            raise LLMNotConfigured(
                "converse requires an extraction llm adapter "
                "(configure a provider + bind the extraction role)")
        holder_id = holder or self.agent
        created_iso = parse_now(now).astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        return holder_id, created_iso

    def converse_prepare(self, message: str, *, holder=None, interlocutor=None,
                         k: int = 6, now=None):
        """三相之一(锁内):写门 fail-fast + recall + 围栏 + prompt。"""
        holder_id, created_iso = self._converse_turn_args(holder, now)
        return _core.memory_converse_prepare(
            self.rt.adapter, self.semantic,
            tenant_id=self.tenant, holder_id=holder_id,
            interlocutor=interlocutor or "",
            adapter_name=self.adapter_name, source_prefix=self.source_prefix,
            created_at_iso8601=created_iso, message=message, recall_k=k)

    def generate_stream(self, chat_llm, prompt: str, on_token=None):
        """三相之二(锁外):纯网络,绑定释放 GIL、逐 delta 回调。"""
        return _core.memory_generate_stream(chat_llm, prompt, on_token)

    def converse_commit(self, message: str, prepared, gen_resp, *, holder=None,
                        interlocutor=None, k: int = 6, now=None) -> dict:
        """三相之三(锁内):失败语义 A 收口 + remember。now 必须与 prepare
        同值(幂等键/召回哈希共用 created_at)——调用方负责传同一时刻。"""
        holder_id, created_iso = self._converse_turn_args(holder, now)
        return _core.memory_converse_commit(
            self.rt.adapter, self.llm, self._extraction.belief_prompt,
            tenant_id=self.tenant, holder_id=holder_id,
            interlocutor=interlocutor or "",
            adapter_name=self.adapter_name, source_prefix=self.source_prefix,
            created_at_iso8601=created_iso, message=message, recall_k=k,
            prepared=prepared, gen_resp=gen_resp,
            policy=_build_policy(self._extraction))
```

现 `converse()` 的前四行(llm None 检查 / holder_id / created_iso)改调 `self._converse_turn_args(holder, now)`(去重;`chat = self.chat_llm or self.llm` 一行保留)。

- [ ] **Step 4: 实现 engine 三段化**

`engine.py`:`_role_override` 的 chat 分支逻辑改造为局部解析(generator 函数保留给 remember 用):

```python
    def _resolve_chat(self, provider: str | None):
        """锁内调用:解析本轮 chat 适配器为局部引用(锁外使用)。取代旧
        _role_override('chat_llm', …) 的全局 slot 换入换出——锁外生成期间
        换 slot 会被并发轮读到错误模型。"""
        if provider:
            cfg = self._cfg.resolve_provider(provider)
            if not cfg or not cfg.get("api_key"):
                raise _LLMNotConfigured(
                    f"selected provider '{provider}' is not configured")
            return _build_chat_adapter(cfg)
        return self._core.chat_llm or self._core.llm

    def _converse_phased(self, message: str, *, on_token=None, holder=None,
                         interlocutor=None, k: int = 6, now=None,
                         provider: str | None = None) -> dict:
        # prepare 与 commit 必须共用同一时刻(幂等键/召回哈希含 created_at)。
        now = now or datetime.now(timezone.utc)
        with self._lock:                                    # ① 短:读 + prompt
            chat = self._resolve_chat(provider)
            prepared = self._core.converse_prepare(
                message, holder=holder, interlocutor=interlocutor, k=k, now=now)
        gen_resp = self._core.generate_stream(chat, prepared.prompt, on_token)  # ② 锁外
        with self._lock:                                    # ③ 抽取 + 写
            return self._core.converse_commit(
                message, prepared, gen_resp, holder=holder,
                interlocutor=interlocutor, k=k, now=now)

    def converse(self, message: str, *, holder=None, interlocutor=None,
                 k: int = 6, now=None, provider: str | None = None) -> dict:
        return self._converse_phased(message, holder=holder,
                                     interlocutor=interlocutor, k=k, now=now,
                                     provider=provider)

    def converse_stream(self, message: str, *, on_token, holder=None,
                        interlocutor=None, k: int = 6, now=None,
                        provider: str | None = None) -> dict:
        return self._converse_phased(message, on_token=on_token, holder=holder,
                                     interlocutor=interlocutor, k=k, now=now,
                                     provider=provider)
```

(原 converse/converse_stream 的 docstring 语义并入 `_converse_phased` 注释;`datetime`/`timezone` 已在 engine.py 导入,若无则补。`_role_override` 函数本体保留——remember 仍用。)

- [ ] **Step 5: 全量测试绿**

Run: `.venv/bin/python -m pytest tests/python/test_converse_lock_release.py tests/python/test_converse_phases_binding.py -q && .venv/bin/python -m pytest tests/python -q 2>&1 | tail -2`
Expected: 新测试 PASS;全量 823+ passed(既有 test_dashboard_converse*.py 不动全绿)。

- [ ] **Step 6: Commit**

```bash
git add python/starling/_memory_core.py python/starling/dashboard/engine.py tests/python/test_converse_lock_release.py tests/python/test_converse_phases_binding.py
git commit -m "feat(dashboard): converse generate phase runs outside the engine lock

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 真机 re-dogfood(手动,非 CI 门)

**Files:**
- Create: `$CLAUDE_JOB_DIR/tmp/converse_lock_dogfood.py`(ephemeral,不提交)

**Interfaces:** 消费运行中 dashboard(`~/.starling/starling.json` 的 token/端口;`DASHSCOPE_API_KEY` 已在环境,勿打印)。

- [ ] **Step 1: 重启 dashboard 上新内核**

```bash
kill -TERM $(lsof -tnP -iTCP:8787 -sTCP:LISTEN); sleep 2
cd /Users/jaredguo-mini/develop/memory/starling-web
nohup .venv/bin/python scripts/run_dashboard.py --no-build > "$CLAUDE_JOB_DIR/tmp/dash.log" 2>&1 &
```

- [ ] **Step 2: 写并跑并发探测脚本**

`$CLAUDE_JOB_DIR/tmp/converse_lock_dogfood.py`:WS `/ws/converse`(带内 token 首帧)发「生成一段5阶信念推理的故事」;收到首 token 后,循环 5 次:`POST /api/tick` + `GET /api/vitals`(带 token,逐次计时);轮末等 done。断言:
- 每次 tick/vitals 均 `<3s` 返回(拆锁前 tick 会阻塞到整轮生成完,~40-300s);
- done 帧 `ok=true` 且 `statement_ids` 非空(沉淀成功);
- 打印各请求耗时进 PR body。

- [ ] **Step 3: 记录结果(无提交)**

数字与结论写入 PR 描述;若环境层(Clash)抖动导致生成失败,如实记录并重跑一次(生成失败不影响锁纪律断言——tick 计时仍有效)。

---

## Self-Review

**1. Spec coverage:** §1 三相拆分+单体内联→Task 1;§2 三绑定+ConversePrepared 类+sink 逐字复用→Task 2;§3 MemoryCore 转发+engine 三段+_resolve_chat→Task 3;§4 hazard(同刻 now、写门中途、单写者)→Task 1 测试 + Task 3 实现注释;§5 测试矩阵(parity/失败语义/写门/锁纪律/真机)→Task 1/3/4。Spec 签名缺 policy 已在头部「Spec 偏差」钉死。✅
**2. Placeholder scan:** Task 1 Step 3 有两处「逐字搬运」指令(prompt 字面量、安全注释)——指向明确行号(134-150),是搬运指令而非 TBD;Task 2 有三处「逐字复制」同理(源行号 60-82/84-118/125-133)。✅
**3. Type consistency:** `ConversePrepared` 三字段、`converse_commit` 含 policy 缺省参、MemoryCore 三方法名与 engine 调用一致;`_resolve_chat` 在 Task 3 Step 1 测试与 Step 4 实现同名。`set_chat_adapter_for_test` 在测试注释中已声明按既有注入模式替换、不新增 public 接口。✅

## Execution Handoff

Execute via **superpowers:subagent-driven-development**(每任务 fresh implementer + task-reviewer,最后 whole-branch review),按项目 cadence。然后 PR;CI 绿 + 用户明确合并。
