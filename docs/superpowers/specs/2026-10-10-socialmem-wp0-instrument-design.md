# WP0：对口题评测仪器标定（官方口径）

## 依据与范围

日期 2026-10-10。承接本机未入库的设计草案 `build/design_cognitive_layer_draft_20261010.md` 第 4 节的 WP0。用户已确认：放行每题留痕（召回块、提示、回答、裁判原文落盘）；阶段一收窄到 Q5 为主，Q9 为辅，Q2 Q4 Q6 只验证不退步；结构化记忆层走声明合同路径并改 C++ 规划器可见性（WP2，不在本文）；官方分项裁判用 qwen3.8-27b 主裁、deepseek-v3 对抽样二裁；多人在场延后；保留切分只在阶段一收尾复测一次。

本文只覆盖 WP0：让梯子能在官方评测口径下产出可与论文量级对照的数字，并让每题的召回块、提示、回答、裁判原文可复核。**不改 C++，不做抽取，不跑 S_star，不改任何默认行为。**

## 为什么先做这一步

- 梯子裁判是单词 YES/NO 严格等价，答题提示没有题型指引且允许答「不知道」，max_tokens 为 512；官方评测器按 0 到 1 分项评分，答题提示含题型指引并要求选择题必须选一项，max_tokens 为 1000。
- 按 free31 题型构成折算，后续论文的全上下文期望约 19.8/31，梯子 S_full 只有 10/31。差距混着裁判、提示、作答模型三个因素，在量清之前 S_star 与 S_full 的差距没有尺度。
- 九月来源路径已存 733 + 298 份回答和裁判回执，可以只付裁判费量出严格口径的低估。

## 官方协议要点（取自匿名镜像源码，当数据读，SHA-256 见预注册）

- 开放题：`prompts.yaml` 的 `llm_judge`，输出 `{"score","rationale"}`，temperature 0；evaluator 的头条指标是全体均分，另以分数大于等于 0.7 计「正确」的附带计数。
- 选择题：字母比对，必须选一项，不得弃答。
- 答题：temperature 0，max_tokens 1000；开放题提示含全部题型指引，只有记忆里一无所有才答信息不足。
- 官方 `rescore.py` 记载 evaluator 原循环有选择题与开放题顺序错位的缺陷，且 rescore 内联了另一份更简的裁判提示。本设计只借用 `prompts.yaml` 的提示与 evaluator 的解析、阈值语义，逐题独立打分，不使用其循环。

## 接口合同

**新模块 `scripts/eval_official_protocol.py`（纯函数，无网络）**

- `load_official_prompts(path, expected_sha256=None) -> dict`：读 yaml，给定摘要时不符则抛错。yaml 只在此函数内惰性导入。
- `official_answer_prompt(prompts, record, recalled, *, full_context=False) -> str`：选择题与开放题各一套；选项格式化为 `A. 名字`；无记忆时上下文为 `[No memories retrieved]`；`full_context=True` 时改用官方 `llm_answer` 模板（全上下文基线的写法）且上下文原样不加 `- ` 前缀。
- `official_full_context(history) -> str`：`--- Session N, 日期 ---` 头加 `[Session N, 2:47pm] 说话人: 正文`，十二小时制。日期取该会话首轮的日期，与官方按会话日期的写法不逐字相同，记录在案。
- `parse_official_mc(text) -> str` 与 `official_mc_correct(text, record) -> bool`：移植官方字母解析，金标字母取自选项下标。
- `official_judge_prompts(prompts, question, golden, generated) -> tuple[str, str]`：返回 system 与 user。
- `parse_official_judge(content) -> tuple[float, str, str]`：返回分数、理由、状态，状态为 `ok`、`regex_fallback` 或 `parse_failed`；分数夹在 0 到 1。
- `make_official_judge_fn(chat, prompts, *, max_tokens=400) -> Callable`：返回 `(question, reference, candidate, backbone) -> dict`，字段 `score rationale raw status`。
- `CORRECT_THRESHOLD = 0.7` 与 `official_is_correct(score) -> bool`（大于等于阈值）。
- 裁判请求失败时 `make_official_judge_fn` 直接抛出，不像官方实现那样吞成 0 分：梯子对抛错的题写 error 行并排除出统计，续跑重试，这条纪律不变。

**`eval_judge_audit._chat_completion` 增加两个仅限关键字的可选参数** `system=None` 与 `enable_thinking=None`：为 None 时请求体逐字节不变，既有调用与测试里的替身函数不受影响。

**`eval_ladder` 新增（默认值全部保持旧行为）**

- config 键 `answer_style`（`ladder` 默认、`official`）、`official_prompts`、`official_judge`、`strict_corun`、`library_cache`、`full_format`（`ladder` 默认、`official`）。
- 命令行 `--answer-style --official-prompts PATH --official-prompts-sha256 HEX --judge-model NAME --strict-corun --library-cache DIR --full-format`。
- `_real_answer` 仍返回 bool；官方风格下返回 `score >= 0.7`，分数写进 `diagnostics`。
- `run_cell` 在 real-mode 为每题传入新建的 `diagnostics` 字典，journal 行在既有字段（`key stage backbone seed item_id ok`）之外只增不改地加入 `recall_block recall_abstained prompt response score judge_raw judge_status strict_verdict library`；`load_journal` 的续跑语义不变。
- cell 在既有字段之外加入 `mean_score` 与 `by_query_type`，仅当至少一题产出分数时才出现；fixture 产物与既有 real 产物的字节不变。

**`scripts/eval_ladder_pipeline.py` 新增** `history_key(history) -> str`（话轮内容的 SHA-256 前 10 位）与 `LibraryCache(root)`：`get_or_build(stage, key, build) -> (path, "hit"|"miss", meta)`（`build(db_path)` 返回可 JSON 化的 meta，与库一同落盘，命中时原样返回；建库失败不留半成品条目） 与 `checkout(src, dest)`（sqlite 备份接口）。同一历史键的题共用一次建库，每题检出一份独立副本再召回，召回写入的事件不会跨题泄漏。库缓存开启时：S0 与 S_full 不建库（它们的记忆块只来自历史文本）；S_rag 与 S_star 按「台阶、历史键、说话人标签、嵌入模型、回放模式、查询时间、抽取配置」缓存；S_star_oracle 的金标语句按题不同，仍按题建库。关闭时行为与现状逐字节相同。

**`scripts/rescore_socialmem_official.py`（WP0.2）**：读九月逐题文件，从嵌套的 HTTP 回执取出回答正文，用官方裁判重判开放题，逐行追加、按题号续跑，汇总严格口径与官方口径的差。只重判开放题：九月选择题的回答是 0 起下标整数，官方字母口径不适用，选择题只保留严格口径读数；状态不是 ok 或回答为空的题跳过并计数。

## 数据泄漏防线

journal 行字段用白名单构造，不含环境变量、配置对象或密钥。测试在环境里放入假密钥，断言它不出现在任何落盘行中；真跑后另做一次密钥扫描。

## 测试先行

红测写在 `tests/python/test_eval_official_protocol.py`、`tests/python/test_eval_ladder_official.py`、`tests/python/test_rescore_socialmem_official.py`，每个先看到因功能缺失而失败再实现。依赖归档官方文件的用例用 `historical_eval` 标记。现有 118 个梯子相关测试必须保持通过。

## 未验证与风险

- 官方答题与裁判提示按字节取自镜像快照，我没有逐文件核对镜像完整性；README 称 CC BY 4.0，论文脚注称流水线 MIT。提示文本不入库，运行时按路径与摘要读取，仓库只保存摘要与署名说明。
- 官方裁判默认模型是 GPT-4o-mini 或 Gemini；本机用 qwen3.8-27b，自评偏差未测，二裁只抽样。
- 关闭思考的请求参数是否被该端点接受要用冒烟确认；确认前不假定。
- 网络级库缓存的 S_star 路径只在离线下用假抽取器验证，真抽取要到 WP2 才验证。
- 单 seed、单模型；试点 110 题只能判仪器，不能判提升。
