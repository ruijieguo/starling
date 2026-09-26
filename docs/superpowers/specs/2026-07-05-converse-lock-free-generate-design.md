<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# converse 生成段出锁(三相拆分)— Design Spec
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **JSON mode 请求实验（2026-09-12）**：C++ `OpenAIAdapter::Config::json_object_output` 默认关闭，仅约束抽取请求格式并保留响应原文，普通生成单独绕开。旧数组抽取使用默认实例；非法枚举继续严格拒绝。配置不代表服务器支持或 schema 保证，评测显式开启并归档参数；Python 仅绑定与编排。完整范围及待验证状态见 [中文优化设计](2026-09-12-socialmem-optimization-design.md)。

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
