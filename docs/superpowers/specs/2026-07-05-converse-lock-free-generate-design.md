# converse 生成段出锁(三相拆分)— Design Spec

**Date:** 2026-07-05
**Slice:** 修复 converse 持 engine 锁跨 LLM I/O 的放大器:把最长的网络腿(chat 生成)移出
`DashboardEngine._lock`,tick / recall / forget 等在生成期间自由穿插。
**Branch:** `fix/converse-lock-free-generate`(off `main@2a23546`)。

## Problem / Context

2026-07-05 实证(线上取证 + `extraction_attempt` 台账):一轮被网络黑洞的 converse 占引擎锁
~8 分钟(chat 60s×4 重试链 + extraction 60s×4 链),6 轮排队 ≈ 50 分钟整站假死——tick、全部
命令端点阻塞(`POST /api/tick` 8s 超时探测证实锁被占)。且**健康路径同样成立**:长生成
(5 阶信念故事)合法地跑 295s,期间整个引擎锁死。

现状:
- `DashboardEngine._lock`(RLock,`engine.py:153`)串行化所有引擎调用;
  `converse`/`converse_stream`(`engine.py:392-419`)全程持锁 + `_role_override` 换全局
  adapter slot。
- C++ `memoryops::converse`(`src/memory/memory_ops.cpp:105-194`)是单体但**内部已四相**:
  ① recall(DB 读,含 query-embed 短网络)→ ② fence + prompt build(纯计算)→
  ③ `generate_stream`(网络,结构性不持写事务)→ ④ remember(extraction 网络 + DB 写)。
- 失败语义 A 在 C++:generate 失败 → 干净无回复轮;remember 失败 → 回复保留 +
  `remember_ok=false` 可观测。

**目标(用户裁定 2026-07-05):只解阻塞** —— converse 的 chat 生成段不再占引擎锁;多轮
converse 之间的真并发**非目标**(prepare/commit 仍按到达顺序串行)。

## 方案取舍(已裁定:方案 1)

- **方案 1(选定)— 生成段出锁**:C++ 拆 `converse_prepare` / (host 驱动 generate) /
  `converse_commit`,单体 `converse` 保留并内联同三相(单一语义源、字节级行为不变)。
  健康路径锁占用 ~300s → ~15-25s(降一个量级);黑洞最坏 ~500s → ~250s 且只影响本轮
  commit,不再全站放大。
- 方案 2(**deferred**,gated-on-实测)— 连 extraction 也出锁:remember 拆
  extract(锁外)/persist(锁内)。attempt ledger 每次尝试写库(审计纪律)需缓冲或短锁,
  `Extractor::run`/PipelineRun/幂等纪律全要重审——收益增量只有 extraction 的 13-23s
  (健康),风险面翻倍。若方案 1 落地后 extraction 占锁仍是实测痛点再做。
- 收紧超时预算(不动锁结构)已否决:治不了健康路径的长生成。

## Design

### §1 C++ 核心(`src/memory/memory_ops.cpp` + `include/starling/memory/memory_ops.hpp`)

新增两个核心入口 + 一个 DTO;单体重构为内联三相:

```cpp
// 相位 1+2:admission fail-fast + recall + fence + prompt build(现有代码原样移入)。
struct ConversePrepared {
    std::string prompt;         // 已围栏的完整 chat prompt
    std::string context_pack;   // 供 outcome 回显
    bool abstained = false;
};
ConversePrepared converse_prepare(persistence::SqliteAdapter& adapter,
                                  retrieval::SemanticRetriever& semantic,
                                  const ConverseParams& p);

// 相位 4 + 失败语义 A 统一收口:gen_resp.ok=false → 干净无回复轮(不碰 DB);
// ok=true → 填 reply/gen_* 成本字段 + remember(现有 try/catch 原样移入——
// remember 门前的 require_write_admission(#45)天然处理「解锁窗口中途翻
// DRAINING」:reply 保留、remember_ok=false、remember_error 可观测)。
ConverseOutcome converse_commit(persistence::SqliteAdapter& adapter,
                                extractor::LLMAdapter& extraction_llm,
                                std::string_view extraction_prompt,
                                const ConverseParams& p,
                                const ConversePrepared& prepared,
                                const extractor::LLMResponse& gen_resp);

// 单体保留:prepare → chat_llm.generate_stream(prepared.prompt, on_token) → commit。
// 行为字节级不变;既有全部 C++/Python converse 测试照跑;非 dashboard 调用方零感知。
ConverseOutcome converse(...现签名不变...);
```

要点:
- `converse_prepare` 开头保留 `require_write_admission(adapter)`(fail-fast:UNREADY/
  DRAINING 时别白烧 300s 生成)。
- `converse_commit` **不**另查 admission:remember 自身是 #45 的门前抛函数,现有
  `try/catch`(`memory_ops.cpp:169-192`)已把中途拒写降级为「回复保留 +
  remember_ok=false」——正是失败语义 A 想要的。
- 架构边界自检:围栏、prompt、失败语义、诚实 remember_ok 全在 C++;host 只做「三行顺序
  调用 + 锁管理」,锁本来就是 host 专属关切;调用顺序由类型签名强制(commit 需要
  prepared)。换绑定语言只需重写这三行胶水——与 host 驱动 tick/run_replay 同类。

### §2 绑定(`bindings/python/bind_13_memory_ops.cpp`)

- `memory_converse_prepare(...) → ConversePrepared`:参数展开与现 `memory_converse` 相同
  (去掉两个 llm + on_token);`py::class_<ConversePrepared>` 只读三字段。GIL:
  `gil_scoped_release` 包 C++ 调用(内含 query-embed 网络)。
- `memory_generate_stream(chat_llm, prompt, on_token) → LLMResponse`:纯转发
  `chat_llm.generate_stream`;**逐字复用**现 `memory_converse` 绑定的 noexcept
  PyGILState token-sink 模式(`bind_13_memory_ops.cpp:84-110`)+ `gil_scoped_release`。
  `LLMResponse`/`LLMAdapter` 已有绑定(`bind_06_extractor.cpp:111/124`),零新类型。
- `memory_converse_commit(adapter, extraction_llm, extraction_prompt, <params 展开>,
  prepared, gen_resp) → dict`:返回 shape 与现 `memory_converse` 完全一致。
  `gil_scoped_release` 包 C++(内含 extraction 网络)。
- 现 `memory_converse` 绑定**保留不动**(单体路径)。

### §3 Python 适配(`python/starling/_memory_core.py` + `python/starling/dashboard/engine.py`)

- `MemoryCore` 增三个薄转发:`converse_prepare` / `generate_stream` / `converse_commit`
  (签名归一、DTO 缺省——绑定层允许项);现 `converse()` 保留。
- `engine.converse` / `engine.converse_stream` 三段化(两者共用一条私有路径):

```python
with self._lock:                       # ① 锁内:短
    chat = self._resolve_chat(provider)      # 局部引用,见下
    prepared = self._core.converse_prepare(message, holder=..., ...)
gen = self._core.generate_stream(chat, prepared.prompt, on_token)   # ② 锁外:长网络
with self._lock:                       # ③ 锁内:extraction+写
    return self._core.converse_commit(prepared, gen, holder=..., ...)
```

- `_role_override` 在 converse 路径改为 `_resolve_chat(provider) → adapter 局部引用`
  (锁内解析,锁外使用)——**顺手消灭拆锁后必然爆发的竞态**:换全局 slot 的旧模式在
  锁外生成期间会被并发轮读到错误模型。`remember` 路径的 `_role_override("llm", ...)`
  维持现状(remember 本 slice 不动)。
- REST `/api/converse` 与 WS `/ws/converse` 都经此路径;WS 的 on_token 桥
  (`call_soon_threadsafe`)不动。

### §4 并发 hazard 审查

- **单写者不变**:锁外段(②)零 DB 访问——`generate_stream` 是纯网络调用,adapter 是
  C++ 对象,虚函数在 GIL 释放下运行。
- **锁外窗口 DB 漂移**(tick 在 ② 期间写库):remember 幂等由 evidence span key 持有;
  context_pack 本就是查询时刻快照(对话最终一致)。可接受,设计上明示。
- **写门语义**:prepare fail-fast 拒;② 期间翻 DRAINING → commit 内 remember 门前抛 →
  reply 保留 + `remember_error`。drain 语义(先拒写、后停 tick)不变。
- **多轮 converse**:prepare/commit 短段仍按锁序串行;两轮的 ② 可自然重叠(副产品,
  不承诺、不测序)。
- **on_token**:锁外调用,回调契约不变(cheap、thread-safe、不碰 DB/socket)。

### §5 Testing

**C++(tests/cpp)**
- 三相 parity 钉测:同输入下 `prepare+generate_stream+commit` 与单体 `converse` 的
  `ConverseOutcome` 逐字段一致(FakeLLMAdapter,含流式与非流式、generate 失败两分支)。
- generate 失败 → commit 返回干净无回复轮(ok=false、error 透传、零 statement)。
- commit 在写门关闭下(测试夹具翻 gate)→ reply 保留 + remember_ok=false +
  remember_error 非空。

**Python(tests/python)**
- 锁纪律:慢速 stub chat adapter(sleep 数百 ms)驱动 `engine.converse_stream`,并发线程
  在生成段内成功执行 `engine.tick`(锁可得性探测,拆锁前该测试必然超时/阻塞)。
- `_resolve_chat` parity:provider override 选中注册表 adapter、None 回退 role-bound;
  并发两轮不同 provider 各用各的(旧全局 slot 模式做不到)。
- 既有 converse/converse_stream 测试全绿(REST/WS shape 不变)。

**门**:全量 ctest + pytest;`--python-editable` 重装;clang-tidy 由构清洁(新增 C++ 面按
gotcha 清单写);真机 re-dogfood:长生成期间并发打 `/api/tick`+检视端点,实测不阻塞。

## Out of Scope

- 方案 2:extraction 出锁(remember 拆 extract/persist、attempt ledger 缓冲)——deferred,
  gated-on-实测。
- 直接 `/api/remember` 的持锁 extraction(同归方案 2)。
- 多 converse 真并发(独立事务窗口/乱序完成)。
- 查询 embed 缓存 / 交互路径超时预算调整(P3.c 已有 gated 决定,不混入)。
