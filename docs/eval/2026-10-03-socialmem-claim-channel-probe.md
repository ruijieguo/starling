# claim 合同通道真实模型探针（qwen3.8-27b）

日期：2026-10-03。这是对 claim 合同补充通道（`claim_extraction_prompt` 加准入）的小样本真实调用探针，不是 SocialMemBench 评测，不产生准确率。它接着[否定范围探针](2026-10-03-socialmem-negation-scope-probe.md)，回答那份文档留下的问题：2026-09-12 记录的 `negative_target_scope` 技术失败在这条通道上是否还在。

## 当前结论

- **旧失败本次没有复现，但这不等于它不会再发生。** 36 格里没有任何 `schema_failure`。该校验仍然生效：离线用 fake 适配器喂入空串、纯空白、数字三种 topic，都得到同一条 `topic must be null or a nonempty string`，null 和非空字符串被接受，见 `test_invalid_topic_reproduces_the_historical_schema_failure`。qwen3.8-27b 在这 36 格里没有产出过这类 topic。2026-09-12 当时用的是 `deepseek-v3`：generation 分析 JSON 的可比性记录显示，该轮与 source-turn 轮的抽取传输相同，均为 `deepseek-v3`、JSON mode、max_tokens 4096、timeout 60000ms、重试 3 次。本次是 `qwen3.8-27b`、8192、120000ms、零重试，两边的模型和重试都不同，所以无法判断原模型现在是否还会触发。
- **`negative_target_scope` 在这条通道上 6 格只有 1 格入库。** legacy 模式 3 格入库 1 格，json_object 模式 3 格入库 0 格。其余 5 格都被确定性守卫拒绝，原因是 `explicit source marker missing: NEGATED`：模型给出了 polarity=NEG，但 scope_markers 只写了 ASSERTED。守卫按设计工作，没有把错误极性写进库，代价是这条事实被丢掉。
- **问题出在这句双重否定，不是 `prefers` 谓词。** 同一模型对 `preference_contrast` 里的 "I don't prefer the green room" 6 格都带了 NEGATED，`emotion_negative` 和 `reported_distrust` 共 12 格也全部带了 NEGATED 并入库。
- **准入响应的 JSON 外壳在 legacy 模式下对 2 个候选很脆弱。** 候选数为 2 的 legacy 格有 9 个，准入响应字面可解析的只有 1 个，其余 8 个都是 `envelope_failure: invalid JSON envelope`，整条响应被丢弃，两个候选都没入库。8 个里 5 个少一个 `}`，3 个多一个 `}`。json_object 模式下候选数为 2 的 9 格全部可解析。候选数为 1 时，legacy 7 格里 6 个可解析，json_object 6 格全部可解析。
- **这不是长度截断。** 31 次准入的 `finish_reason` 全部是 `stop`，2 个候选的响应只有 35 到 36 个 completion token，远低于 8192 的上限。为什么多写或少写一个括号，这里没有证据，不下结论。

## 影响范围

claim 合同通道默认关闭：C++ 的 `ValidationPolicy::semantic_claim_contract` 默认 false，Python 的 `ExtractionConfig` 同样默认 False。截至 2026-10-03 的仓库检索，仓库内把它打开的只有评测脚本（`run_socialmem_baseline.py` 由配置字典决定），dashboard 和 integrations 不引用这个配置键。但 `ExtractionConfig` 是公开 API，库的使用者可以通过 `Memory.open(extraction=...)` 显式打开它。所以这些发现不影响默认路径，只对显式打开这条通道的人有意义，包括评测脚本和库的使用者。

## 这个结果不能说明什么

- 只有 6 个用例，每格 3 次重复，`temperature` 固定为 0，重复不独立。`mixed_emotions` 在 legacy 下 3 次里 1 次正常、2 次多一个括号，说明即使温度为 0，同一输入的结果也会变，但变化幅度只有这一个例子。
- 只测了一个模型和一个服务。`deepseek-v3` 没测，所以旧失败的原始触发条件没有被检验。
- json_object 的好结果只来自 3 种不同的 2 候选输入，每种 3 次。它不是对该参数的能力证明，也没有设对照去排除时间段的影响，只是两种模式的先后顺序随重复次数交替。
- json_object 没有救回 `negative_target_scope`：它 0/3 入库，legacy 是 1/3，n 太小，分不出差别。
- 没有标签、没有准确率。`admitted` 只表示通过了确定性守卫和准入调用，没有另外人工核对语义。

## 方法

- 用例是 6 个冻结的 synthetic：`negative_target_scope` 是目标，`preference_contrast` 是同谓词的否定对照，`emotion_negative` 和 `reported_distrust` 是其他谓词的否定对照，`decision_change` 和 `mixed_emotions` 是多候选用例，用来检验准入响应的外壳。
- 两种模式：legacy 不带 `response_format`，json_object 带 `response_format: {"type":"json_object"}`。两种模式的先后顺序随重复次数交替：第 0、2 次 legacy 在前，第 1 次 json_object 在前。
- 每格一次抽取加至多一次准入，不重试，gold 答案不进入提示。
- 准入响应是否合法只按字面 `json.loads` 判定。带 ```json 围栏的响应算不可解析，但评测脚本的策略设置了 `claim_allow_code_fence=True`，C++ 接受了围栏，所以 `reported_distrust` 的那一格终态仍是 `admitted`。因此结果表里 9 个字面不可解析等于 8 个真正的技术失败加 1 个被接受的围栏响应。
- 探索阶段另跑过若干未脚本化的调用，归档在 `build/socialmem_20261003_claim_channel_exploration/`，方向与本文一致，但不计入本文数字。

## 结果

| 用例 | 模式 | 终态（3 次） | 准入调用 | 字面不可解析 |
| --- | --- | --- | --- | --- |
| `negative_target_scope` | legacy | admitted 1、semantic_rejection 2 | 1 | 0 |
| `negative_target_scope` | json_object | semantic_rejection 3 | 0 | 0 |
| `preference_contrast` | legacy | technical_failure 3 | 3 | 3 |
| `preference_contrast` | json_object | admitted 3 | 3 | 0 |
| `emotion_negative` | legacy | admitted 3 | 3 | 0 |
| `emotion_negative` | json_object | admitted 3 | 3 | 0 |
| `reported_distrust` | legacy | admitted 3 | 3 | 1 |
| `reported_distrust` | json_object | admitted 3 | 3 | 0 |
| `decision_change` | legacy | technical_failure 3 | 3 | 3 |
| `decision_change` | json_object | admitted 3 | 3 | 0 |
| `mixed_emotions` | legacy | admitted 1、technical_failure 2 | 3 | 2 |
| `mixed_emotions` | json_object | admitted 3 | 3 | 0 |

## 复现

```bash
eval "$(grep -E '^export DASHSCOPE_(BASE_URL|API_KEY)=' ~/.zshrc)"
.venv/bin/python scripts/probe_socialmem_claim_channel.py \
  --out build/socialmem_<日期>_claim_channel_probe --repeats 3
```

默认 6 个用例、2 种模式、3 次重复，共 36 格，至多 72 次请求。脚本只从环境变量读取 `DASHSCOPE_API_KEY` 与 `DASHSCOPE_BASE_URL`，要求显式 HTTPS 端点，不回退到其他供应商。归档不含密钥，运行后已逐文件检查。离线测试 `tests/python/test_probe_socialmem_claim_channel.py` 用原生 fake 适配器覆盖终态分类、准入外壳的两种畸形、topic 校验、传输失败口径、模式顺序和密钥不落盘。

## 本次归档

归档在 `build/socialmem_20261003_claim_channel_probe/`，被 `.gitignore` 忽略，不入库。

| 项 | 值 |
| --- | --- |
| 模型与端点 | `qwen3.8-27b`，https://dashscope.aliyuncs.com/compatible-mode/v1 |
| 请求参数 | max_tokens 8192，timeout 120000ms，max_retries 0，thinking 关闭 |
| 两种模式 | legacy（json_object_output=False）、json_object（json_object_output=True） |
| 规模 | 36 格，36 次抽取加 31 次准入，共 67 次请求，392,581 tokens |
| 核心 SHA-256 | `b9d6e83ac80f970fbcda5cf48633aa150f4332189f0b9b2ea40d34e65a6d7aac` |
| 脚本 SHA-256 | `658230715186229e33c0f53c6a1504adcb995c4a14dc765de6dd2890662649af` |
| results.json | `7d6d756b8d7aa9315865a5156ea29fcf2cfb8ffbf80f0defc39ceca272c882dd` |
| runs.jsonl | `156e7b021605d027a1b5f14f8fc3ce2791186ff56bcb5319f37b11ece71a40a7` |
