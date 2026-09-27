<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

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

# P2.e 应用接口层（Application Surface）设计
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

**里程碑**：P2.e（P2 收尾三里程碑第二个，见 [2026-05-31-p2-completion-scope.md](../plans/2026-05-31-p2-completion-scope.md)）
**日期**：2026-06-01
**状态**：设计已 user approved，待 writing-plans
**依赖**：P2.d 模式补全已合并 main（HEAD d57a8da，`PatternCompletor` 可用）；M0.8 Neocortex 容器、P2.c CommitmentEngine/PolicyEngine、M0.9 retrievers 均已落地

---

## 0. 背景与目标

P2 验收口径是「**支持小规模应用**」。当前 Python 侧只有 `from starling import _core` + `Runtime`(preflight/health 监督器) + `starling.bus.append_evidence.BusFacade`，**没有一个小应用开发者能直接拿来用的门面**，也没有把记忆喂进 prompt 的 Working Set 渲染，更没有可运行示例。这是「支持小规模应用」最大的硬缺口。

P2.e 交付：公开 `starling.Memory` 门面 + `render_working_set` 渲染 prompt-ready `ContextBlock` + `commitment.fire→提醒`端到端 + 可运行 `examples/quickstart.py`。

**目标一句话**：让一个小应用能用十几行 Python 写记忆、检索、把"我是谁 / 我们的共识 / 相关记忆 / 待办承诺 / 当前情绪"渲染进一轮对话的 prompt，且离线可跑。

---

## 1. 范围

**范围内（P2.e 交付）：**
- C++ 只读接口（加 read 方法到现有类）+ pybind 绑定：`PersonaContainer.read`、`CommonGroundContainer.read`、`CommitmentEngine.pending`；`StatementRow` 加 `affect_json` 列。
- Python 门面 `starling.Memory`：`open / remember / recall / tick / render_working_set / close` + extractor helper。
- Python `working_set` 模块：`ContextBlock` / `WorkingBlock` dataclass + `render_working_set` 组装器 + 近似 token 预算 + `render()`。
- `examples/quickstart.py`（离线 stub extractor，兼 README quickstart + 冒烟）。
- C++ 单测（readers）+ Python 测试（门面 / working set）+ quickstart 冒烟。

**明确范围外（→P3）：**
- 完整 Retrieval Planner（7 步 / 9 QueryIntent）、Context Pack 8 标签（P3.a）。
- 二阶 ToM、外部 tool 执行、ActionPolicyGraph（P3）。
- persona / common_ground 的**自动 rebuild**（从 statements 构 anchor/persona 属 Replay/巩固范畴）——本期门面读**已物化**的容器，rebuild 由 app 显式触发。
- 精确承诺受益人建模（`pending` 的 interlocutor 过滤本期 best-effort）。
- 真 tokenizer（tiktoken 等）——本期用近似 char 预算。
- `remember` 的结构化直写旁路——本期 `remember` 只走 extractor（保持 Starling 抽取本意）。

---

## 2. 架构（三层）

```
┌─ examples/quickstart.py（离线 demo，stub extractor）
├─ Python: starling.Memory 门面  +  starling.working_set（ContextBlock 组装/渲染/token 预算）
│     └─ 组合 → _core retrievers（Basic/Semantic/PatternCompletor）、Extractor、新 readers、PolicyEngine.tick、EmbeddingWorker
└─ C++（新增只读接口 + 绑定）: PersonaContainer.read / CommonGroundContainer.read / CommitmentEngine.pending；StatementRow.affect_json
```

**结构原则**：read 方法加到**现有类**（谁 rebuild 谁 read，职责内聚）；组装/渲染/token 预算是表现层逻辑，落 Python；门面绑定一个 self agent。

---

## 3. C++ 只读接口

返回**结构化 view**（C++ 内解析 content_json，facade 不碰 JSON/SQL）。read 方法 conn-free（pybind lambda 内 `self.connection()`）。

```cpp
// neocortex —— PersonaContainer 新增:
struct PersonaView {
    bool found = false;
    std::string tenant_id, holder_id;
    int version = 0;
    std::map<std::string, std::string> dimensions;  // dimension → 仲裁值(per-dim 单值,跳 null/diverged)
};
PersonaView PersonaContainer::read(persistence::Connection&,
                                   std::string_view tenant_id, std::string_view holder_id);

// neocortex —— CommonGroundContainer 新增:
struct CommonGroundView {
    bool found = false;
    std::string tenant_id, cg_ref;
    int version = 0;
    std::vector<std::string> grounded, asserted_unack, suspected_diverge;
};
CommonGroundView CommonGroundContainer::read(persistence::Connection&,
                                             std::string_view tenant_id, std::string_view cg_ref);

// prospective —— CommitmentEngine 新增(query;五态机写路径不改):
struct CommitmentView {
    std::string stmt_id, state, deadline;
    std::string subject_id, predicate, object_value;   // ⋈ statements 取承诺内容
    bool fired = false;                                 // EXISTS(commitment_triggers status='fired')
};
std::vector<CommitmentView> CommitmentEngine::pending(persistence::Connection&,
        std::string_view tenant_id, std::string_view holder_id, std::string_view interlocutor_id);
```

- `read` 解析的 content_json shape 须对齐对应 `rebuild` 写的 shape（implementer 读 rebuild 实现对拍）。`found=false` 表示容器未物化（持有空 view）。
- `pending`：查 `commitments` WHERE tenant + state='ACTIVE'（含被 trigger 标 fired 的，仍 ACTIVE），⋈ `statements` 取 holder=holder 的承诺内容；`interlocutor_id` 非空时 best-effort 过滤（`subject_id` 或 `object_value` 命中）；`fired` 经 `commitment_triggers` 的 `status='fired'` EXISTS 判定。tenant 谓词 + `(id,tenant_id)` PK 锁租户。
- **affect**：`StatementRow` 加 `affect_json` 字段（additive）：`statement_row.hpp` struct + `basic_retriever.cpp`/`semantic_retriever.cpp`/`pattern_completor.cpp` 三处 SELECT 末尾追 `affect_json` 列 + 对应 row 填充 + `module.cpp` `StatementRow` 加 `def_readonly("affect_json", …)`。默认 ""。最低优先段,scope 吃紧可砍。

绑定：三个 view 经 pybind（`std::map`/`std::vector` → dict/list）；`read`/`pending` lambda 内 `self.connection()`，Python conn-free。

---

## 4. Python 门面 `starling.Memory`

`python/starling/memory.py`，从 `starling` 顶层导出。绑定一个 self agent，单租户默认。

```python
class Memory:
    @classmethod
    def open(cls, db_path, *, agent="self", tenant_id="default", llm=None) -> "Memory":
        # 打开 adapter（_build_local_store_sqlite_runtime 风格）+ 跑 preflight + 连 retrievers/readers。

    def remember(self, text, *, holder=None, source_kind="user_input", now=None) -> "RememberResult":
        # holder 默认 = self agent。append_evidence(EngramInput) → _core.Extractor(conn, llm).run(...) → Statement。
        # RememberResult = {engram_ref, statement_ids: list[str], outcome: str}。llm 为 None → 抛清晰错误。

    def recall(self, query, *, perspective="first_person", k=10, mode="semantic") -> list["Scored"]:
        # mode "semantic"=vector_recall | "completion"=pattern_completion。默认 semantic。
        # scoped to self + perspective;隐私先行（复用 retrievers 过滤）。Scored = {row: StatementRow, score: float}。

    def tick(self, now=None) -> "TickStats":
        # EmbeddingWorker.tick_one_batch(嵌入待嵌) + PolicyEngine.tick(到期 commitment fire)。
        # TickStats = {embedded: int, fired: int, broken: int, auto_withdrawn: int}。

    def render_working_set(self, interlocutor, *, goal=None, token_budget=2000) -> "ContextBlock":
        # agent = self;组装 5 段(见 §5)。

    def close(self) -> None: ...
```

**llm adapter helper**（`starling` 顶层；门面收一个 LLM adapter,内部建 `_core.Extractor(conn, llm).run(...)`；Extractor pybind 接受 `LLMAdapter` 基类,Fake/OpenAI 均可)：
- `starling.make_openai_llm(model=…, base_url=…)`：生产 `OpenAIAdapter`,key 走 env `OPENAI_API_KEY`（**绝不入参 / 不 log / 不绑 Python 形参**）。
- `starling.make_stub_llm(default_xml=…)`：离线 / 测试,`FakeLLMAdapter` + `set_default_response`,把输入抽成 Statement（quickstart 用;canned XML 须对齐 Extractor 解析,`<holder ref>`/`<perceived_by ref>` = agent）。

口径：agent 在 open 时绑定（默认 `"self"`）；单租户默认 `"default"`；`remember` 只收 text；`recall` 默认 semantic；`tick` 是 facade 唯一推进点（app 每回合调一次）。

---

## 5. `render_working_set` / `ContextBlock`

```python
@dataclass
class WorkingBlock:
    label: str            # persona | common_ground | relevant_memories | pending_commitments | affect
    content: str
    token_estimate: int   # 近似 = len(content)//4

@dataclass
class ContextBlock:
    blocks: list[WorkingBlock]
    truncated: list[str]          # 因预算被截断的 label
    def render(self) -> str:       # 拼成带小标题的 prompt 字符串,空段省略
```

**5 段 + 读路径：**

| 段 | 读路径 | 渲染 |
|---|---|---|
| **persona** | `PersonaContainer.read(tenant, holder=agent)` → dimensions | "About me: …" |
| **common_ground** | `CommonGroundContainer.read(tenant, cg_ref)`，`cg_ref = f"{agent}::{interlocutor}"` | grounded + asserted_unack |
| **relevant_memories** | `recall(goal, mode)`（goal 为空 → 取最近高 salience） | top-k 记忆 bullet |
| **pending_commitments** | `CommitmentEngine.pending(tenant, agent, interlocutor)` | ACTIVE 列表 + **fired 标 ⚠ 提醒** |
| **affect** | relevant_memories 的 `affect_json` 经 `affect_parse_json`+`affect_salience` 取 peak | "Current tone: …" |

**token 预算（近似、零依赖）**：`token_estimate = len(text)//4`（≈4 char/token，不引 tiktoken）。`token_budget` 默认 2000，按**优先序**分配，超额段截断并记入 `truncated`：
`pending_commitments`（动作关键，先保）→ `persona` → `common_ground` → `relevant_memories`（吃剩余大头）→ `affect`。空段省略。

**`render()` 输出示意：**
```
## About me
Alice — prefers concise answers; values reliability.

## What we share
- We agreed the auth refactor ships Friday.

## Relevant memories
- Bob said he'd take over the auth module (2 days ago).
- The deadline was moved up from next week.

## Pending commitments
- ⚠ DUE: You promised Bob a design doc by Thursday 09:00.
- You owe Bob the API stub.

## Current tone
High-stakes, mildly positive.
```

**B3 提醒注入闭环**：`tick()` 跑 `PolicyEngine.tick` 把到期承诺的 trigger 标 fired → `CommitmentEngine.pending` 读出 `fired=true` 的 → working set 的 pending_commitments 段标 ⚠。这就是"commitment.fire → reminder 注入"端到端，**不接外部执行**。

`cg_ref = f"{agent}::{interlocutor}"`：common ground 容器按这个 pair key 物化/读取（quickstart rebuild 时用同一 key）。

---

## 6. quickstart + 测试

**`examples/quickstart.py`（离线，兼 README + 冒烟）**：
```python
mem = Memory.open(db_path, agent="alice", llm=make_stub_llm(default_xml=CANNED_XML))
mem.remember("Bob said he'd take over the auth module")            # stub 抽取 → Statement
# 显式物化 persona / common ground(本期不自动):
PersonaContainer(adapter).rebuild(tenant, "alice", anchor_sources, now)
CommonGroundContainer(adapter).rebuild(tenant, "alice::bob", now)
# 立一个到期承诺(modality=COMMITS statement + create_from_statement + 过期 time trigger):
...
mem.tick(now)                                                      # 嵌入 + PolicyEngine.tick → 承诺 fired
cb = mem.render_working_set(interlocutor="bob", goal="auth refactor")
print(cb.render())                                                # persona + 共识 + 记忆 + ⚠ 提醒 + tone
```

**测试**：
- **C++ 单测**：`PersonaContainer.read`(rebuild→read 往返 + found=false 空态)、`CommonGroundContainer.read`(三组分类)、`CommitmentEngine.pending`(ACTIVE 过滤 + `fired` 标志 + interlocutor best-effort)、`StatementRow.affect_json` 透传(检索返回带 affect)。
- **Python 测试**：`Memory` 门面 —— open/remember(stub extractor)/recall(semantic + completion)/tick/render_working_set；断言 ContextBlock 5 段、token 截断记入 `truncated`、**tick 后 ⚠ 提醒进 pending_commitments**。
- **quickstart 冒烟**：`examples/quickstart.py` 可跑通 + 断言关键输出(import 或 subprocess)。
- **回归**：ctest + pytest 全绿；`affect_json` 加列 additive 不回归既有 retriever 测试；单一 `starling_tests`。

**红线**：
- **无 migration**（只读现有表 + 加 `StatementRow` 列纯 SELECT 改；最高现存 0021 不变）。
- Persona/CommonGround 的 `rebuild` 写路径不改（只加 `read`）；CommitmentEngine 五态机写路径不改（只加 `pending`）。
- WAL：raw SQL 读用 open-and-close 连接（沿用 runtime.py 模式）——但本期读走 C++ readers（adapter 连接内），无并发写争用。
- API key env-only，绝不入参 / log / 绑 Python 形参。

---

## 7. 实施约束（注入 writing-plans）

- worktree 隔离（`worktree-p2-e-application-surface`），从 main HEAD 切出。
- `starling_core` 显式 `target_sources` append 新 `.cpp`（若 read 方法落在现有 .cpp 则无新增；新 view/reader 若拆文件则 append）；单一 `starling_tests` append 新测试。
- pybind/绑定改动后刷新 `_core.so`：`cmake --build build` + `cmake --install build --prefix .venv/lib/python3.14/site-packages` + `pip install -e . --no-deps --force-reinstall`（`cmake --install` 是关键）。
- SQL helpers：`bus::detail::bind_sv` / `make_sqlite_error`、`persistence::StmtHandle`、checked `sqlite3_prepare_v2`；JSON 解析用项目既有 nlohmann。read 方法参考 `projection_maintainer.cpp` / `semantic_retriever.cpp`。
- pybind：view 结构 `def_readonly` 暴露字段；reader 方法 lambda 内 `self.connection()`，`py::keep_alive` 按需。
- `:memory:` SQLite（unit）/ `tmp_path` + `relax_preflight_for_m0_3`（runtime fixture）。
- 无 `--no-verify` / `--amend`；plan 文件 untracked 直到 close；API key env-only。
- `make_stub_llm` 须真能离线把 quickstart 的输入抽成 Statement（`FakeLLMAdapter` + `set_default_response`,canned XML 对齐 Extractor 解析）。

---

## 8. 验收

- `from starling import Memory` 可用；`open/remember/recall/tick/render_working_set/close` 走通。
- `render_working_set` 产出含 5 段的 `ContextBlock`，`render()` 成 prompt；token 超预算时截断并记 `truncated`。
- **`tick` 后到期承诺以 ⚠ 提醒出现在 working set**（B3 闭环验证）。
- 3 个 C++ reader + `StatementRow.affect_json` 单测全绿；Python 门面 / working set 测试全绿；`examples/quickstart.py` 离线跑通。
- M0.8 + M0.9 + P2.a–d 无回归；ctest + pytest 全绿。
