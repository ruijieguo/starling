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

# Extractor 真实抽取 prompt + JSON 解析器 设计
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **JSON mode 请求实验（2026-09-12）**：C++ `OpenAIAdapter::Config::json_object_output` 默认关闭，仅约束抽取请求格式并保留响应原文，普通生成单独绕开。旧数组抽取使用默认实例；非法枚举继续严格拒绝。配置不代表服务器支持或 schema 保证，评测显式开启并归档参数；Python 仅绑定与编排。完整范围及待验证状态见 [中文优化设计](2026-09-12-socialmem-optimization-design.md)。

> **后续修复同步（2026-09-12）**：可空主题允许缺省或 null，无效类型统一在 C++ 预检；情绪校验不以“觉得/感觉”或整轮认知词直接拒绝。写入与检索共用原生契约。重复裁判一致率与有效分母单列，原严格门槛保持。实现范围及尚未完成的能力见 [中文优化设计](2026-09-12-socialmem-optimization-design.md)。

> **2026-09-11 契约补充**：旧数组格式保留；仅实验补充通道启用 v2 契约。 当前扩展见 [已确认语义证据设计](2026-09-11-source-grounded-claim-contract-design.md)。下文保留本版本原有适用范围。


**里程碑**：补完 C++ Extractor 的真实抽取（M0.4/P1 期遗留）。建议号 **P2.i**（完成 P1 抽取闭环；与 P2.g/h 不同，本里程碑**改 C++**）。
**日期**：2026-06-06
**状态**：设计已 user approved，待 writing-plans
**依赖**：P2.h 已合并 main（HEAD 24922fd）；现有 `Extractor` / `xml_parser` / `OpenAIAdapter` / `FakeLLMAdapter` / `eval_p1_extractor.py` 均已落地

---

## 0. 背景与目标

P2.h dashboard 真实交互 QA 发现：`remember` 接真实 LLM（DeepSeek）抽出 **0 statements**。根因——`src/extractor/extractor.cpp` 的生产 `Extractor::run()` 用 **`build_prompt_body_for_tests`**（M0.4 占位 prompt，字面量 `[M0.4 extractor prompt v1.0]\nholder_id=...\npayload_size=...`，**连实际文本都不带**），源码注释（约 line 126-127）写「真实 prompt 在 `python/starling/extractor/prompts.py`」，但**该文件不存在**。所以真实 LLM 收到无意义 prompt → 抽不出东西；只有 `FakeLLMAdapter`（无视 prompt 返回 canned `<statements>` XML）才"能用"。`starling.Memory.remember` + 真 DeepSeek 同样 0，确认是 C++ 抽取器的既有缺口（从没拿真实 LLM 端到端验证过）。

**目标一句话**：落地真实抽取 prompt（复用 `eval_p1_extractor.py` 已验证的成熟 prompt，单一源）并接进 C++ Extractor 的 run 路径——切 JSON 输出 + 重写解析器，让 `remember`（`starling.Memory` + dashboard 共用）接真实 LLM 能真正抽出 Statement。

**Extractor 构造点**（仅 Python 绑定，C++ 管线不构造它）：`python/starling/memory.py:136`、`python/starling/dashboard/engine.py:140`、`bindings/python/module.cpp:734`——故 prompt 可从 Python 注入。

---

## 1. 范围与口径

口径（user 选定）：**切 JSON + 重写解析器（复用 eval 成熟 prompt）+ prompt 住 Python 单一源注入 C++**。

**范围内（交付）：**
- 单一源 prompt（`prompts.py`）+ `eval_p1_extractor.py` 改 import。
- C++ Extractor 注入 prompt template + run 插 payload。
- JSON 解析器（替代 XML）+ 字段簿记。
- OpenAIAdapter 加 max_tokens。
- 全套 FakeLLM canned 测试 XML→JSON 迁移（C++ ~3 + Python 13 文件）。
- gated 真实 LLM 端到端烟测。

**明确范围外（→后续）：**
- 二阶 ToM / perspective 细则极致调优（用 eval prompt 现状，borderline 可接受）。
- `observed_at` 精确 thread engram 观测时间（本期默认 now）。
- chunk 分块（M0.4 仍 1 chunk/engram，不动）。
- prompt 大改 / 多模型适配。
- 无 migration（schema 不变）；不改 Statement 写入/校验/dedup 路径。

---

## 2. 单一源 prompt

- **`python/starling/extractor/prompts.py`（新）**：导出 `EXTRACTION_PROMPT`——把 `eval_p1_extractor.py` 的 `_EXTRACT_PROMPT`（约 line 102-302，~201 行：抽取规则 + worked examples + `{convo}` 占位，要求输出 **JSON 数组**）原样移过来作权威源。
- **`scripts/eval_p1_extractor.py`**：删除内联 `_EXTRACT_PROMPT`，改 `from starling.extractor.prompts import EXTRACTION_PROMPT`；其余 urllib 路径不动（eval 继续作 prompt 质量验证 + 共享同一 prompt）。
- JSON 输出 schema（eval prompt 现产）：每条 `{holder, holder_perspective, subject, predicate, object, modality, polarity, nesting_depth}`。

---

## 3. 注入 C++ Extractor

- **`Extractor` 构造加 prompt template**：`Extractor(Connection&, LLMAdapter&, std::string prompt_template = "")`（`extractor.hpp` 构造签名 + `extractor.cpp` 存成员）。绑定（`module.cpp:734`）相应加可选第三参数。
- **Memory / dashboard engine 传入**：`memory.py` + `dashboard/engine.py` `from starling.extractor.prompts import EXTRACTION_PROMPT` → `_core.Extractor(conn, llm, EXTRACTION_PROMPT)`。
- **`Extractor::run` 建真实 prompt**：把 `payload_bytes` 解码为 UTF-8 文本，填进模板的 `{convo}` 占位（C++ 侧字符串替换），得到发给 `adapter_.extract` 的真实 prompt。`build_prompt_body_for_tests` 退役为 fallback（当 prompt_template 为空时用——FakeLLM 测试无视 prompt，故 fallback 内容无所谓；`compute_prompt_input_hash` 仍按最终 prompt body 算）。

---

## 4. JSON 解析器（替代 XML）

- **`src/extractor/json_parser.cpp` + `include/starling/extractor/json_parser.hpp`（新）**：`parse_extractor_json(std::string_view raw, const ExistingRefMap&) -> ParseResult`，用已在 extractor 引入的 `nlohmann/json`。解析 LLM 的 JSON 数组（容错：剥 ```json fence、找第一个 `[`）→ `std::vector<ExtractedStatement>`。
- **`Extractor::run` 改调** `parse_extractor_json(resp.raw_xml, ...)`（替代 `parse_extractor_xml`）。**`xml_parser.cpp/.hpp` 退役**（删除——user 选重写非并行）。
- **字段来源（LLM 出语义，C++ 填簿记）**：
  - LLM JSON → `holder_id`(holder)、`holder_perspective`、`subject_id`(subject)、`predicate`、`object_value`(object)、`modality`、`polarity`、nesting（object_kind 推断）。
  - C++ 填：`subject_kind` 默认 `cognizer`；`object_kind` 默认 `str`（nesting_depth≥2 → `statement`）；`canonical_object_hash` **计算**（复用 canonicalize_object / M0.5 逻辑）；`perceived_by` = holder；`confidence` 默认 **0.7**；`observed_at` 默认 **now**（ISO-8601 UTC）。
  - 校验/dedup/写入仍走既有 `validate_extracted_statement` + `StatementWriter`（不动）。
- **`LLMResponse.raw_xml` 字段名保留**（现承载 JSON 文本；加注释说明），减小 blast radius；只改 canned 值不改字段名。

---

## 5. OpenAIAdapter 加 max_tokens

- **`OpenAIAdapter::Config` 加 `int max_tokens = 4096`**（`openai_adapter` Config struct + `module.cpp` 的 `OpenAIAdapterConfig` 绑定 `def_readwrite("max_tokens", ...)`）。
- **`OpenAIAdapter::extract`** 请求体加 `{"max_tokens", cfg_.max_tokens}`——JSON 多 Statement 输出 + 推理模型（deepseek-v4-*）留余量（eval 已验证 4096 够，避免截断致 `json.loads` 失败）。
- `from_env` 默认 4096；dashboard 的 `_build_chat_adapter` 可透传（沿用现有 model/base_url 覆写模式）。

---

## 6. 测试迁移（本里程碑大头）

- **C++（ctest）**：
  - `tests/cpp/test_xml_parser.cpp` → **`test_json_parser.cpp`**（重写为 JSON 解析单测：合法数组、容错剥 fence、字段映射 + C++ 簿记默认、错误 JSON → ParseResult.errors）。
  - `tests/cpp/test_extractor_orchestrator.cpp`、`test_fake_llm_adapter.cpp`：canned `LLMResponse.raw_xml` 从 `<statements>` XML 改 **JSON 数组**。
  - 单一 `starling_tests`；**ctest 数会变**（xml_parser 测试换 json_parser；orchestrator 用例数大致守恒）。
- **Python（pytest，13 文件）**：`make_stub_llm` 的 default XML（`memory.py` 文档串 + 调用方）+ 各 extractor/dashboard/m0_4 测试的 canned stub 全改 **JSON 数组格式**。涉及：`python/starling/memory.py`（make_stub_llm 文档/默认）、`tests/python/test_extractor_*`（dead_letter/partial_success/idempotency/holder_perspective/chunk_duplicate）、`test_m0_4_acceptance.py`、`test_memory_facade.py`、`test_dashboard_engine/commands/config_routes.py`。统一新建一个 JSON stub 常量复用。
- **gated 真实 LLM 端到端烟测**（需 key，不入 CI）：`scripts/` 或 `tests/python` 一个 gated 脚本/标记——`Memory.open` + `make_openai_llm`（DeepSeek）→ `remember(真实文本)` → 断言 `statement_ids` 非空（正是本次 QA 暴露、从没验证过的端到端路径）。`eval_p1_extractor.py`（现共享 prompts.py）继续作 prompt 质量 gated 验证。
- **红线回归**：M0.8/M0.9/P2.a–h 全绿；pytest 不回归（迁移后全绿）；ctest 重建后全绿（数随 parser 测试调整）。

---

## 7. 实施约束（注入 writing-plans）

- **本里程碑改 C++**（json_parser/extractor/openai_adapter/binding）→ **worktree 隔离 + cmake 重建**：改后 `cmake --build build && cmake --install build --prefix .venv/lib/python<ver>/site-packages`（关键，否则 `_core.so` 陈旧；pip 撞 json 网络错加 `--config-settings cmake.define.FETCHCONTENT_SOURCE_DIR_JSON=$(pwd)/build/_deps/json-src`）。参见记忆 [[editable-core-needs-cmake-install]]、[[python-additive-milestones-run-on-main]]（纯 Python 才在 main 跑；本期改 C++ 用 worktree）。
- 无 migration（最高 0021 不动，schema 不变）；单一 `starling_tests`；不改 Statement 写入/校验/dedup/bus。
- API key env-only（`OPENAI_API_KEY`），绝不入参/log/绑形参/提交；gated 测试 key 经 env，不入 CI。
- Co-Authored-By trailer 每 commit；无 `--no-verify`/`--amend`；plan untracked 直到 close；合并 main 需 dangerouslyDisableSandbox + 显式 consent。
- FakeLLM 离线路径保留（stub 无视 prompt，仅换 canned 格式 XML→JSON）。

---

## 8. 验收

- `prompts.py` 为权威 prompt 源，`eval_p1_extractor.py` import 它（单一源）。
- C++ Extractor 经注入的真实 prompt + payload 文本调真实 LLM，`parse_extractor_json` 解析 JSON → Statement；`canonical_object_hash`/`observed_at`/`perceived_by`/`confidence`/`subject_kind`/`object_kind` 由 C++ 正确填。
- **`Memory.remember`（+ dashboard remember）接真实 DeepSeek 抽出 statements >0**（gated 烟测断言）。
- OpenAIAdapter 带 max_tokens；推理模型不截断。
- FakeLLM 离线测试全绿（canned 改 JSON）；pytest 全绿；worktree 重建后 ctest 全绿；M0.8/M0.9/P2.a–h 不回归；无 migration。
- roadmap 登记本里程碑。

> **错误回执边界（2026-09-12）**：C++ 将 JSON 解析异常收敛为稳定、可编码的 `envelope_failure`，避免第三方异常中的多字节 token 截断破坏回执；响应原文保持完整，拒绝状态和严格分母不变。


> **中文边界同步（2026-09-12）**：C++ 只将明确“X 负责……”视为中文责任认知命题；情绪对象中的“职责/责任”交由准入判断。主题空白按 UTF-8 ASCII、NBSP、U+3000 统一处理，空主题报告 schema 失败。


## 来源时间与独立扩展标签（2026-09-12）

按已批准优化范围执行 [中文来源话轮设计](2026-09-12-source-turn-evaluation-design.md)。C++ 生成并解析版本化话轮，保留原始消息时间与 UTF-8 来源位置，正文与元数据分开校验；Bus/检索重建 source_turn 防止篡改。Python 仅映射和统计，独立扩展标签不进入模型输入，不修改原 P1 金标。真实时间不推断为事件时间或 UTC；已完成 C++ 实现、全量测试、离线与真实核验；真实诊断为 verified / complete_with_errors，质量门槛未通过。普通正文冒号保留完整语义，直接写入/回读使用共享严格解析器拒绝嵌套重复键。详见 [来源话轮评测报告](../../eval/2026-09-12-socialmem-source-turn.md)。


## 生成契约完整性同步（2026-09-12）

按 [中文生成契约设计](2026-09-12-claim-generation-design.md)，C++ 在抽取提示中明确对象、逐字主题、原始时间限定和字段类型约束，并提供与本次来源隔离的通用中英文参考示例。模型输出校验、准入、存储/检索与默认开关保持既有约束，Python 仅绑定和评测编排；参考示例不作为当前证据。本轮 C++ 实现、完整回归、离线核验及历史响应 140/140 一致性重放已完成；真实诊断于北京时间 2026-09-13 完成核验，为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、独立对象 12/14、主题/联合各 1/14，原生技术失败 5；主题字面匹配分数不能解释为字段缺失。P1 兼容与逐例不退步门槛仍失败，Q1/Q9 结构化及链接组仍为 0/3，默认关闭。详见 [生成契约评测报告](../../eval/2026-09-12-socialmem-generation.md)。其他专项职责沿用设计同步清单，历史快照保持。

## 输出协议与偏好边界同步（2026-09-13）

按 [中文修复设计](2026-09-13-claim-protocol-boundary-design.md) 继续已批准优化：C++ 提示强调键唯一、时间原文及同话轮引用，准入与解析共用合法原因目录，窄范围拒绝把明确偏好对象写成 feels。真情绪不因同源其他偏好句被拒；Bus/回读复用共享契约，Python 仅绑定与编排。当前已完成 RED、C++ 实现与复审修复后的完整回归（C++ 1,062 项，Python 1,319 项通过/15 项跳过）；旧响应重解析 137/140 一致，3 条偏好误标候选提前拒绝。复合/因果情绪及被动 preferred 感受保留准入，句尾标点边界有正反例覆盖。独立复审发现均已关闭，最终离线 140 条/144 数据库核验通过；真实诊断已完成并由原生验证器核验为 `verified / complete_with_errors`：140 条重放、144 个数据库；固定候选 56/64（TP 30、TN 26、误收 0、误拒 1、技术失败 7），synthetic 冻结 11/16、契约 11/16（有效分母 15/16），P1 combined F1 为 holder 0.7317、holder/perspective 0.6829、predicate/object 0.7683；扩展标签 object/topic/scope/time/joint 为 12/14、2/14、12/14、12/14、2/14（有效目标 13）；Q1/Q9 的 baseline、structured、linked 均为 0/3，full 均为 3/3；实际证据链仍受入库与证据聚合限制。原生技术失败共 10 条，主要为重复 JSON 键和准入 JSON 后追加文本；无效裁判票 0。`promotion_ready=false`，生产默认保持关闭，不运行 1,031 题全量。默认、原标签、检索与历史归档保持。

## 声明范围与覆盖诊断职责（2026-09-15）

后继范围修复首先保持生成/准入提示逐字不变，避免和 S1 提示变化混成同一变量。核心 C++ 定位仅处理受限句首声明，完整原文仍进入准入；原始行诊断不得进入模型 candidates。生成覆盖策略 R1 留作独立后继设计。

详见[声明范围定位与生成覆盖诊断设计](2026-09-15-claim-scope-localization-design.md)。

## 2026-09-16 范围字段协议对齐

本轮 C++ schema 生成与本地 wire 校验共同要求 scope_markers 非空且唯一；主范围成员关系、范围组合、来源与主体语义仍由 C++ 原生契约执行，binding 不重复判定。评测脚本冻结指定核心、来源、配置及调度，并在每次请求前复验能力和预约预算。真实端点拒绝数组 uniqueItems（两次 HTTP 400），C1 未通过能力门槛，来源样本、入库、检索、QA 均未执行；本地约束对齐不得解释为谓词召回或问答质量提升。当前实验开关继续关闭，提供商 schema profile 分离方案仍待下一轮单独设计与验证。

## 2026-09-16 能力与得分路线修订（已授权自主迭代）

后续抽取输入须保留会话、话轮与来源时间，并通过原生连续窗口保留指代/事件上下文。优先补表示与生成缺口，不以任意加谓词作为替代；无题目参考答案或金标锚点进入写入。 具体范围、测试与验收见[统一方案](2026-09-16-socialmem-capability-and-score-design.md)。本段描述计划，不代表已经实现或获得新分数。

最新执行顺序已按用户指令调整：先冻结当前默认 Starling 并完成全部 1031 题基线，再按真实失分执行中文文档→失败测试→C++ 改进→同条件复测，循环自主迭代，无需重复申请常规步骤授权。基线前仅补评测编排及题目允许来源范围，不预修被测能力。详见[基线优先执行计划](../plans/2026-09-16-socialmem-baseline-first.md)。
