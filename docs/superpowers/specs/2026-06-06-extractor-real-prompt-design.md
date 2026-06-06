# Extractor 真实抽取 prompt + JSON 解析器 设计

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
