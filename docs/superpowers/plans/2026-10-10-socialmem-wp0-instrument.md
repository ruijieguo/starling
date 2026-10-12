# WP0 评测仪器标定 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让归因梯子能按 SocialMemBench 官方口径作答与判分，每题留痕可复核，并能按历史内容复用建库。

**Architecture:** 官方口径的纯函数独立成一个无网络模块；梯子只在 config 键打开时才走官方路径，默认路径逐字节不变；库缓存按历史内容键在 pipeline 模块里实现，梯子在 `_real_answer` 里按台阶接入。

**Tech Stack:** Python 3.14、pytest、`_core` 原生模块（只读使用，不改 C++）、DashScope 兼容端点。

**Spec:** `docs/superpowers/specs/2026-10-10-socialmem-wp0-instrument-design.md`；预注册 `build/prereg_wp0_instrument.md`（本机文件，未入库）。

**补写说明：** 本计划在实现与离线验证完成后补写，用来固定任务边界与验收命令。代码以仓库文件为准，已完成的步骤打勾。

## Global Constraints

- 不改 C++，不做抽取，不跑 S_star，不改任何默认行为。
- fixture 模式与不带新参数的既有 real 模式，产物与 stdout 与改动前逐字节相同。
- journal 行按白名单构造，不含环境变量、配置对象或密钥；真跑后扫描两个密钥的值。
- 官方提示文本不入库，运行时按路径与 SHA-256 读取，摘要不符则拒跑。
- 裁判请求失败时抛出，梯子写 error 行并排除出统计，不记 0 分。
- git 只用显式路径 `git add`，不用 `--no-verify` 与 `--amend`；用户未要求时不提交、不推送。
- 提交门：全量 `python -m pytest tests/python` 绿，基线 2404 passed, 629 skipped；ctest 基线 1401/1401。

---

### Task 1: 官方口径纯函数

**Files:**
- Create: `scripts/eval_official_protocol.py`
- Test: `tests/python/test_eval_official_protocol.py`

**Interfaces:**
- Produces: `load_official_prompts(path, expected_sha256=None) -> dict`；`official_answer_prompt(prompts, record, recalled, *, full_context=False) -> str`；`official_full_context(history) -> str`；`parse_official_mc(text) -> str`；`official_mc_correct(text, record) -> bool`；`official_judge_prompts(prompts, question, golden, generated) -> tuple[str, str]`；`parse_official_judge(content) -> tuple[float, str, str]`；`make_official_judge_fn(chat, prompts, *, max_tokens=400)`；`CORRECT_THRESHOLD = 0.7`；`official_is_correct(score) -> bool`。

- [x] **Step 1:** 写失败测试，覆盖提示渲染、全上下文格式、字母解析（含句首冠词 A 的官方怪癖）、裁判解析三种状态、阈值 0.7、裁判请求失败即抛出、提示文件摘要校验。
- [x] **Step 2:** 运行确认因功能缺失而失败。
- [x] **Step 3:** 实现模块，yaml 只在读提示文件时惰性导入。
- [x] **Step 4:** 运行 `.venv/bin/python -m pytest tests/python/test_eval_official_protocol.py -q`，期望 27 passed, 1 skipped；加 `--run-historical` 期望 28 passed。

### Task 2: 共用 chat 辅助的两个可选参数

**Files:**
- Modify: `scripts/eval_judge_audit.py`（`_chat_completion`）
- Test: `tests/python/test_eval_official_protocol.py`、`tests/python/test_eval_judge_audit.py`

**Interfaces:**
- Produces: `_chat_completion(prompt, backbone, max_tokens, *, system=None, enable_thinking=None)`；两者为 None 时请求体与此前逐字节相同。

- [x] **Step 1:** 测试默认请求体不变，且 system 与 thinking 开关会进请求体。
- [x] **Step 2:** 实现：有 system 时在 messages 开头插一条，`enable_thinking` 仅在非 None 时写入。
- [x] **Step 3:** 运行 `.venv/bin/python -m pytest tests/python/test_eval_judge_audit.py tests/python/test_eval_official_protocol.py -q`，期望全绿。

### Task 3: 历史内容键与库缓存

**Files:**
- Modify: `scripts/eval_ladder_pipeline.py`
- Test: `tests/python/test_eval_ladder_official.py`

**Interfaces:**
- Produces: `history_key(history) -> str`（SHA-256 前 10 位）；`LibraryCache(root)` 的 `get_or_build(stage, key, build) -> (path, "hit"|"miss", meta)` 与 `checkout(src, dest)`；建库失败不留半成品，目标已存在时 `checkout` 抛 `FileExistsError`。

- [x] **Step 1:** 写失败测试：键按内容寻址、同键只建一次、副本相互隔离、失败不缓存。
- [x] **Step 2:** 实现，`checkout` 走 sqlite 备份接口。
- [x] **Step 3:** 运行 `.venv/bin/python -m pytest tests/python/test_eval_ladder_official.py -q -k "history_key or library_cache or checkout or failed_build"`，期望全绿。

### Task 4: 梯子官方口径、逐题留痕、分数与命令行

**Files:**
- Modify: `scripts/eval_ladder.py`
- Test: `tests/python/test_eval_ladder_official.py`

**Interfaces:**
- Consumes: Task 1 的函数、Task 3 的 `LibraryCache`。
- Produces: config 键 `answer_style`、`official_prompts`、`official_judge`、`judge_model`、`strict_corun`、`library_cache`、`full_format`；命令行 `--answer-style --official-prompts --official-prompts-sha256 --judge-model --strict-corun --library-cache --full-format`；journal 行在既有六字段之外追加 `recall_block recall_abstained prompt response score judge_raw judge_status strict_verdict library`；cell 在有分数时多出 `mean_score` 与 `by_query_type`；`make_real_answerer_fn(max_tokens=512, enable_thinking=None)`。

- [x] **Step 1:** 写失败测试：留痕与续跑契约、无配置泄漏、官方阈值、选择题字母、裁判模型路由、严格同跑、S_full 官方格式、命令行校验、缓存下 S_rag 只嵌入一次、S_star 每个历史只抽取一次且共享库不被召回写入。
- [x] **Step 2:** 实现并保持默认路径不变。
- [x] **Step 3:** 运行 `.venv/bin/python -m pytest tests/python/test_eval_ladder_official.py -q`，期望 28 passed。
- [x] **Step 4:** 回归：既有梯子相关测试全绿，fixture 报告与 stdout 对 HEAD 逐字节一致（试点语料与 longmemeval 样例各一次）。

### Task 5: 九月开放题重判脚本

**Files:**
- Create: `scripts/rescore_socialmem_official.py`
- Test: `tests/python/test_rescore_socialmem_official.py`

**Interfaces:**
- Produces: `answer_text(question) -> str`；`iter_question_files(root)`；`load_corpus(path)`；`rescore(root, corpus, out, judge, *, backbone="") -> dict`；`summarize(rows) -> dict`。只重判开放题，状态非 ok 或回答为空的题跳过并计数，输出文件按题号续跑。

- [x] **Step 1:** 写失败测试，覆盖回答正文取法、续跑、跳过规则、按题型汇总、不触碰逐题目录。
- [x] **Step 2:** 实现，裁判失败的题不写行。
- [x] **Step 3:** 运行 `.venv/bin/python -m pytest tests/python/test_rescore_socialmem_official.py -q`，期望 13 passed。

### Task 6: 全量门与预注册真跑

**Files:**
- 产物（本机，不入库）：`build/wp0_pilot/*`

- [x] **Step 1:** 全量 `.venv/bin/python -m pytest tests/python -q`，实测 2470 passed, 630 skipped。
- [x] **Step 2:** 冒烟：关闭思考的参数被端点接受；两题官方路径与库缓存命中跑通；两个密钥的值不在 journal 与报告里。
- [x] **Step 3:** 四个台阶各一个进程跑试点 110 题，外加九月重判；监视 journal 的 error 行与解析失败率，触及预注册的中止线就停。实测四个台阶全部跑满，error 行 0，解析失败 0，未触及中止线。
- [x] **Step 4:** 合并四份报告，按预注册的 G0 三条逐条出结论，不事后改线。实测三条全部通过，汇总脚本为本机的 `build/wp0_g0_report.py`。
- [x] **Step 5:** 对按「题号加台阶」哈希升序前 40 份开放题回答做 deepseek-v3 二裁，报告与主裁的分数差。实测均差 +0.010，判定一致 35/40，脚本为本机的 `build/wp0_second_judge.py`。
- [x] **Step 6:** 把结果追加到预注册的「运行后追加」一节；密钥值扫描。两个密钥的值在 build/wp0_pilot 的文本产物里均未出现。

### Task 7: 提交（仅在用户要求时）

- [ ] **Step 1:** 用户要求提交时，只用显式路径：

```bash
git add scripts/eval_official_protocol.py scripts/rescore_socialmem_official.py scripts/eval_ladder.py scripts/eval_ladder_pipeline.py scripts/eval_judge_audit.py tests/python/test_eval_official_protocol.py tests/python/test_eval_ladder_official.py tests/python/test_rescore_socialmem_official.py docs/superpowers/specs/2026-10-10-socialmem-wp0-instrument-design.md docs/superpowers/plans/2026-10-10-socialmem-wp0-instrument.md
git commit -m "feat(eval): 梯子支持官方评测口径、逐题留痕与网络级库复用（WP0）"
```

## Self-Review

- **Spec 覆盖：** 官方纯函数、chat 辅助参数、梯子新增键与命令行、pipeline 的 `history_key` 与 `LibraryCache`、重判脚本、数据泄漏防线、测试先行，均有对应任务。
- **占位扫描：** 无 TBD；未完成步骤是真跑与二裁，依赖运行结果，不是占位。
- **类型一致：** 判官返回字典字段在 Task 1、4、5 里均为 `score rationale raw status`。
