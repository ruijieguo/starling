# 否定范围真实模型探针（qwen3.8-27b）

日期：2026-10-03。这是对 `negative_target_scope` 的一次小样本真实抽取探针，不是 SocialMemBench 评测，不产生新的准确率。

## 当前结论

- 在 `qwen3.8-27b`、生产默认 belief 提示下，`Dana: I do not prefer no downtime.` 连续 5 次都抽成 `prefers / "no downtime" / NEG / DESIRES`，原生落库后 `polarity=neg`。否定范围落在被偏好的选项上，没有被误存成对"停机"的正向偏好。
- 对照用例 `preference_contrast` 5 次都抽成 `green room / NEG` 加 `red room / POS`。
- 3 个标签目标 × 5 次共 15 个格子，15 个覆盖，0 个技术失败，0 条未匹配行。共 10 次请求、63615 tokens，全部 `finish_reason=stop`。
- 2026-09-12 文档记录的该用例技术失败这次没有复现。该失败只出现在当天 source-turn 那一次运行，之后 generation、protocol-boundary、recovery-a 三轮的 `native_ok` 都是 `true`。当时的提示和核心与现在不同，所以它只是旧结论，不是现行缺陷。

## 这个结果不能说明什么

- 适配器把 `temperature` 固定为 0，5 次重复不是独立采样。它只说明该输入在该服务上输出稳定，不说明模型对否定范围整体可靠。
- 样本只有 2 个用例、3 个目标。不能外推到其他措辞、其他语言或长对话。
- 标签是读过一次探索性抽取之后才写的，不是盲预注册。覆盖率因此偏乐观，只适合当回归哨兵，不适合当能力证据。
- `preference_contrast` 出现 2 种行集合，只是两条行的写入顺序不同，内容一致。

## 为什么新增独立标签和打分，而不是改冻结标签

冻结的 `eval_socialmem_extended_labels.json` 里这个用例是 `targets: []`、`legacy_channel_only`，所有历史统计都把它排除在分母外。直接补标签有两个问题：

1. 冻结打分器只认 `feels / uncertain_about / decided_on / indifferent_to / trusts` 五个补充谓词。离线核对显示 `prefers` 行会被计入 `excluded_predictions`，目标覆盖为 0，所以补了标签也打不出分。
2. 历史 `legacy` 通道的落库行没有 `semantic_claim_json`，topic、scope、time 三个维度无法打分。
3. 现有测试钉住了 14 个目标、4 个显式排除，且历史归档的 `extended_labels_sha256` 依赖该文件的哈希。

因此冻结标签文件和它的哈希一字未动，新增 `tests/data/eval_socialmem_negation_scope_labels.json`。每个标签绑定源句 SHA-256，源句漂移会拒绝运行。打分只做对落库行字段的字面匹配，一行至多覆盖一个目标，沿用冻结打分器的一对一最大匹配。

## 复现

```bash
eval "$(grep -E '^export DASHSCOPE_(BASE_URL|API_KEY)=' ~/.zshrc)"
.venv/bin/python scripts/probe_socialmem_negation_scope.py \
  --out build/socialmem_<日期>_negation_scope_probe --repeats 5
```

脚本只从环境变量读取 `DASHSCOPE_API_KEY` 与 `DASHSCOPE_BASE_URL`，要求显式 HTTPS 端点，不回退到其他供应商，不重试，gold 答案不进入抽取。归档不含密钥，运行后已逐文件检查。

离线测试 `tests/python/test_probe_socialmem_negation_scope.py` 用原生 fake 适配器覆盖：标签源哈希绑定、极性翻转与否定范围移位不计覆盖、一行不能同时覆盖两个目标、传输失败留在严格分母内且密钥不落盘、输出目录已存在时拒绝、环境变量校验与还原。

## 本次归档

归档在 `build/socialmem_20261003_negation_scope_probe/`，被 `.gitignore` 忽略，不入库。

| 项 | 值 |
| --- | --- |
| 模型与端点 | `qwen3.8-27b`，DashScope compatible-mode |
| 请求参数 | max_tokens 8192，timeout 120000ms，max_retries 0，thinking 关闭 |
| 核心 SHA-256 | `b9d6e83ac80f970fbcda5cf48633aa150f4332189f0b9b2ea40d34e65a6d7aac` |
| 标签 SHA-256 | `428137514352745f68648add0711feaddbb54cbee026749990a749a67199ab06` |
| results.json | `d26978ab9f79f908c3cbdad5163751a169986b2a2f74f332563cc48ee4a05c78` |
| runs.jsonl | `8151022cc18b0f500127738d6d5b74c9d477da7e9034196d0f4f18f24920edf4` |
