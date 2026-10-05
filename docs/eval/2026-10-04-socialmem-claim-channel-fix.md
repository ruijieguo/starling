# claim 合同通道修复尝试与 deepseek-v3 补测

日期：2026-10-04。承接 [claim 通道探针](2026-10-03-socialmem-claim-channel-probe.md)。那份文档留下两件事：准入响应外壳畸形和 `NEG` 缺 `NEGATED` 被守卫拒收这两个发现要不要修，旧的 topic `schema_failure` 对原模型是否还在。这不是 SocialMemBench 评测，不产生准确率。

## 当前结论

- **交付的改动只有一处。** 准入提示末尾加一句，要求闭合所有括号，完整响应是以 `}]}` 结尾的单个 JSON 对象，其后没有文字。改动在 `src/extractor/claim_contract.cpp` 的 `claim_admission_prompt`。抽取提示和固定参考示例逐字节不变，抽取提示与批计划的哈希钉点保持原值。
- **它对 qwen3.8-27b 有效。** 同一批 36 格（6 用例 × 2 模式 × 3 次），legacy 模式下 2 候选的准入响应字面可解析从 1/9 升到 9/9（Fisher 精确检验双侧 p=0.0004），技术失败从 8 降到 0，终态 admitted 从 23 升到 32。json_object 模式本来就是 9/9，没有变化。
- **撤回了另一项改动。** 在抽取提示的固定参考示例里加一条否定偏好示例，让 `negative_target_scope` 的入库从 7/12 升到 12/12（p=0.037）。但它在 json_object 模式下让 `preference_contrast` 的 NEG 声明带 `NEGATED` 的比例从 6/6 降到 0/6（新旧核心交错对照，p=0.002）。deepseek-v3 上的 20/30 到 15/30 不能算这条示例的回归：后来在 deepseek 上跑了抽取提示未改动的交付版本，同样是 15/30（见下文），这个下降是同一提示两次运行之间的漂移。撤回的依据只剩 qwen3.8-27b 的 json_object 对照。净效果不明确且有回归，所以不交付。
- **"NEG 缺 `NEGATED`" 被拒的问题没有解决。** 交付版本下 `negative_target_scope` 在 legacy 模式 3 格里 1 格被拒，json_object 模式 3 格全部被拒。守卫保持原样，没有放宽。后续已由 [NEG 与 NEGATED 提醒行](2026-10-05-socialmem-negated-reminder.md) 解决，同样没有放宽守卫。
- **deepseek-v3 补测：旧的 topic `schema_failure` 在 96 格里出现 0 次，但这不是对当年核心的检验。** 同模型、同传输参数、当前核心，冻结的全部 16 个用例 × 2 模式 × 3 次，没有出现 `topic must be null or a nonempty string`。2026-09-12 的核心不在 git 历史里（`claim_contract.cpp` 在 2026-09-27 才首次入库），无法运行。归档里能对照的只有先后顺序：前一轮 source-turn 有 5 个用例触发这条错误，其中包括 `negative_target_scope`；同日之后的 generation 轮报告写明在抽取提示里新增了主题逐字选取、空值与字段类型等规则，该轮分析里没有这条错误。这是历史归档的先后对照，不是重跑，而且两轮的模型输出都是重新生成的，不能把错误消失单独归因于提示规则。本机最早的冻结副本是 2026-09-15 的，其中 topic 规则句与当前源码逐字相同，所以这条规则的表述自 09-15 起没有变化。
- **deepseek-v3 上另有 3 个围栏失败，已在修复前核心复现。** 3 格都是 `possible_not_decided`，准入响应在 ```json 围栏之后又写了一段解释，原生因此判为 `incomplete or trailing code fence`。示例加收尾句核心上这 3 格变成 0，后来单独跑的交付版本上也是 0（见下文）。但 3 格里只有 1 格的抽取原文与基线逐字节相同，准入响应围栏后另有文字的比例是 3/85 到 0/81（Fisher 精确检验双侧 p=0.246），没有证据说这个改善来自收尾句。

## 三个核心

| 名称 | SHA-256 前 8 位 | 内容 | 用途 |
| --- | --- | --- | --- |
| 基线 | `b9d6e83a` | 2026-09-27 安装到 venv 的核心，早于 #71；没有逐字节对应的提交，见下文 | 修复前对照 |
| 示例加收尾句 | `3fd28b12` | main@e4f722d 的源码加否定偏好示例加收尾句 | 撤回前的候选，没有交付 |
| 交付版本 | `9b7bf154` | main@e4f722d 的源码加收尾句 | 交付 |

基线核心不是从 main@e4f722d 重建的。它是 2026-09-27 09:36 安装到 venv 的核心，晚于 5a945ca（当天 01:52），早于 #71（2026-09-29）。5a945ca 与 e4f722d 之间 `src`、`include`、`bindings` 下被改动的 23 个文件，来自 #71（clang-tidy 违规批量修复，补括号和改名）和 #69（注释），其中 `claim_contract.cpp` 为 56 行增 36 行删。我没有对基线核心做源码级核对。行为层面的证据是离线回放：把三组基线归档（10-03 探针 36 格、`before_nts12` 12 格、`deepseek_before` 96 格，共 144 格）里记录的原始抽取响应和原始准入响应，用 fake 适配器经交付核心重放，逐格比较终态、失败原因、留存数、入库行、结构错误、语义拒收和是否调用准入，144/144 一致。这只说明解析、守卫和准入这一段对同一批原始响应的行为一致，不说明提示或模型输出一致。两个核心的抽取提示相同，准入提示只差那一句。

每个核心都是把构建出的 `.so` 复制到仓库外，用 `importlib` 按路径加载，运行前断言提示里有或没有新示例、有或没有收尾句，断言不过就在花任何 token 之前退出。这样重装 venv 里的核心不会影响还没跑完的对照。

## 结果

### 交付版本对基线（qwen3.8-27b，36 格）

| 用例 | 模式 | 基线（3 次） | 交付版本（3 次） |
| --- | --- | --- | --- |
| `negative_target_scope` | legacy | admitted 1、semantic_rejection 2 | admitted 2、semantic_rejection 1 |
| `negative_target_scope` | json_object | semantic_rejection 3 | semantic_rejection 3 |
| `preference_contrast` | legacy | technical_failure 3 | admitted 3 |
| `preference_contrast` | json_object | admitted 3 | admitted 3 |
| `emotion_negative` | legacy | admitted 3 | admitted 3 |
| `emotion_negative` | json_object | admitted 3 | admitted 3 |
| `reported_distrust` | legacy | admitted 3 | admitted 3 |
| `reported_distrust` | json_object | admitted 3 | admitted 3 |
| `decision_change` | legacy | technical_failure 3 | admitted 3 |
| `decision_change` | json_object | admitted 3 | admitted 3 |
| `mixed_emotions` | legacy | admitted 1、technical_failure 2 | admitted 3 |
| `mixed_emotions` | json_object | admitted 3 | admitted 3 |

legacy 模式下 2 候选的准入响应：基线 9 格里字面可解析 1 个、技术失败 8 个，交付版本 9/9、0。json_object 模式两边都是 9/9、0。结构错误从 8 条 `invalid JSON envelope` 降到 0。两个核心的抽取提示完全相同，抽取阶段的差异只来自服务端波动。

### 准入响应单独回放（qwen3.8-27b）

4 个夹具（`preference_contrast`、`decision_change`、`mixed_emotions` 和一个把 `green room` 的极性改成 POS 的错误极性对照），每个夹具每个变体 3 次，只重放准入请求。

| 准入提示变体 | 次数 | 字面可解析 | 决定与期望一致 | 目录外的理由名 |
| --- | --- | --- | --- | --- |
| 不改（基线） | 12 | 6 | 6 | 2 |
| 加一个两候选的响应示例 | 12 | 12 | 12 | 0 |
| 加闭合规则一句（交付） | 12 | 12 | 12 | 0 |
| 两者都加 | 12 | 12 | 9 | 0 |

决定一致只比较 retain 序列，目录外的理由名单独列出。基线在错误极性对照里 2 次写了目录外的理由 `wrong_polarity`，这在原生里是 `invalid admission reason`。加一个两候选示例和只加闭合规则都是 12/12。两者都加时错误极性对照仍被正确拒收，但 `preference_contrast` 的第二个候选 3 次都被拒，一致率降到 9/12。我选了改动更小、不带 retain:false 示例的闭合规则，样本只有 12 次，这个取舍不是统计结论。

### 撤回的示例

- `negative_target_scope`，legacy，12 次，基线核心对示例加收尾句核心：入库 7/12 到 12/12，`缺 NEGATED` 拒收 5 到 0。
- `preference_contrast`，6 轮，新旧核心交错、先后顺序交替：legacy 模式 NEG 声明带 `NEGATED` 6/6 对 6/6，json_object 模式 6/6 对 0/6。json_object 模式下新核心的这 6 格都被守卫拒收了 green room 那条。
- 留出句：`Priya`、`Kofi`、`Lena` 三句仓库里不存在的否定偏好、一句肯定偏好和 `emotion_negative`，各 4 次，旧核心和新核心都是 20/20 入库。旧核心本来就对这 3 句 NEG 都写了 `NEGATED`，所以留出句没有给出示例有泛化收益的证据，只有输出形状从 `ASSERTED`+`NEGATED` 变成 `NEGATED`。
- 示例句 `Tomas` 是被测句型的近邻，不是独立留出的句子，`negative_target_scope` 上的改善不能当作泛化证据。
- 早先那组只跑 legacy 的提示变体实验没有覆盖 json_object，所以没有看到上面的回归。

### deepseek-v3（同传输）

传输：max_tokens 4096、timeout 60000ms、重试 3 次，legacy 与 json_object 两种模式，各 96 格。

| 原因 | 修复前核心 | 示例加收尾句核心 |
| --- | --- | --- |
| 结构错误: incomplete or trailing code fence | 3 | 0 |
| 语义拒收: explicit source marker missing: NEGATED | 10 | 15 |
| 语义拒收: topic is absent from source unit | 3 | 1 |

NEG 声明带 `NEGATED`（两种模式合并）：

| 用例 | NEG 声明带 NEGATED（前） | （后） |
| --- | --- | --- |
| `emotion_negative` | 6/6 | 6/6 |
| `negative_target_scope` | 2/6 | 1/6 |
| `preference_contrast` | 2/6 | 2/6 |
| `preference_qualifiers` | 4/6 | 0/6 |
| `reported_distrust` | 6/6 | 6/6 |

deepseek-v3 的准入响应在 171 次里全部包在 ```json 围栏里，围栏被评测策略 `claim_allow_code_fence=True` 接受，所以围栏本身不是失败。171 次里没有目录外的理由名。准入单独回放里，只有在人为构造的错误极性对照上它才写 `wrong_polarity`（不加收尾句 5/5，加了 3/5），原生映射要求极性问题用 `wrong_scope`。2026-09-12 的 generation 轮报告也记录过同类现象（同样是 deepseek-v3）：3 个固定负候选的准入原因使用了未定义的 `wrong_polarity` 或 `wrong_time`，计为 schema 失败。不含这个对照时，不加收尾句 10 次里 1 次围栏后有文字，加了 0/10，样本太小，不能作为收尾句对 deepseek 有效的证据。

### deepseek-v3 交付版本端到端（同传输）

合并 #75 之后补跑：交付版本核心 `9b7bf154` 对 deepseek-v3，传输参数与上面相同，全部 16 个用例 × 2 模式 × 3 次，共 96 格。运行前断言核心副本确为交付版本，并核对了基线核心与交付核心在全部 16 个用例上的抽取提示逐字节相同。归档目录 `socialmem_20261004_claim_channel_deepseek_delivered`，177 次请求，1,105,725 tokens，runs.jsonl SHA-256 前 16 位 `0fbc91d693986ca0`，没有出现密钥。

| 终态 | 基线 | 交付版本 | 示例加收尾句 |
| --- | --- | --- | --- |
| admitted | 80 | 75 | 80 |
| semantic_rejection | 13 | 21 | 16 |
| technical_failure | 3 | 0 | 0 |

| 原因（按条数，只列结构错误和作用域守卫） | 基线 | 交付版本 |
| --- | --- | --- |
| 结构错误: incomplete or trailing code fence | 3 | 0 |
| 语义拒收: explicit source marker missing: NEGATED | 10 | 15 |
| 语义拒收: negative relation repeats object denial | 0 | 1 |
| 语义拒收: topic is absent from source unit | 3 | 2 |

- 逐格配对：变好 4、变差 6、不变 86。10 个终态不同的格里 9 个的抽取原文本身就不同，而两个核心的抽取提示逐字节相同，所以这是同一提示两次运行之间的漂移，不是收尾句的效果。
- 唯一抽取原文逐字节相同而终态不同的格，是基线的一个围栏失败。准入响应围栏后另有文字的比例是 3/85 到 0/81（Fisher 精确检验双侧 p=0.246），没有证据说它来自收尾句。
- 抽取原文逐字节相同、两边都调用了准入的 22 格里，准入决定完全相同。
- 同一抽取提示的两次运行，deepseek-v3 只有 28/96 格的抽取原文逐字节相同，qwen3.8-27b 是 34/36。所以 deepseek 上的逐格比较噪声很大。
- 交付版本新出现的 1 条 `negative relation repeats object denial` 来自 `emotion_negative` 的一次抽取：模型把否定同时写进了关系和对象。
- NEG 声明带 `NEGATED`（两种模式合并，每用例 6 条）：

| 用例 | 基线 | 交付版本 | 示例加收尾句 |
| --- | --- | --- | --- |
| `emotion_negative` | 6/6 | 6/6 | 6/6 |
| `negative_target_scope` | 2/6 | 0/6 | 1/6 |
| `preference_contrast` | 2/6 | 0/6 | 2/6 |
| `preference_qualifiers` | 4/6 | 3/6 | 0/6 |
| `reported_distrust` | 6/6 | 6/6 | 6/6 |
| 合计 | 20/30 | 15/30 | 15/30 |

基线与交付版本的抽取提示相同，两次运行之间就差了 5 条（20/30 对 15/30，p=0.295）。示例加收尾句核心的 15/30 对这两次合并的 35/60，p=0.504。所以前文说的 deepseek-v3 上 20/30 到 15/30，不能算示例的回归。逐用例的表是事后分组，一共 5 组，没有做多重比较校正，其中 `preference_qualifiers` 的 0/6 对合并的 7/12 单看 p=0.038，不作结论。

## 这些结果不能说明什么

- 所有重复都是 `temperature` 固定为 0 的同一输入，重复不独立，p 值只描述这批格子。
- 交付版本在 qwen3.8-27b（36 格）和 deepseek-v3（96 格）上都跑过端到端。deepseek-v3 上交付版本与基线的差异几乎都来自抽取阶段的漂移，不能归到收尾句。
- 36 格只有 6 个用例，其中只有 `negative_target_scope` 和 `preference_contrast` 涉及 `NEGATED`。
- 没有标签、没有准确率。`admitted` 只表示通过了确定性守卫和准入调用。
- 示例对 `json_object` 模式回归的原因没有证据，不下结论。

## 复现与归档

端到端对照由 `scripts/probe_socialmem_claim_channel.py` 产生（本次提交新增了 `--profile` 和 `--cases all`），`--profile deepseek-2026-09-12` 复现 2026-09-12 记录的抽取传输，`--cases all` 展开全部 16 个用例。基线核心是 2026-09-27 安装的 venv 核心，不是从当前提交重建的，出处见上文；交付版本核心是本次提交构建出的核心；示例加收尾句核心需要在本次提交上再加回那条示例才能得到，示例已从提交里去掉。核心复制与断言的包装脚本、留出句脚本和各个运行脚本归档在 `build/socialmem_20261004_claim_channel_fix/`，没有入库。2026-10-03 那组 36 格基线由 #74 合并时的脚本产生，当时还没有 `--profile` 和 `--cases all`，manifest 里的脚本哈希与现在的脚本不同；2026-10-04 的各次运行都由现在这份脚本产生，manifest 里的脚本哈希与现在一致，提交前已逐个核对（共 18 个）。

归档在 `build/` 下，被 `.gitignore` 忽略，不入库。密钥只从环境变量读取，所有归档目录已逐文件检查，没有出现密钥。

| 归档（build/socialmem_20261004_claim_channel_…） | 格数 | 请求 | tokens | runs.jsonl SHA-256 前 16 位 |
| --- | --- | --- | --- | --- |
| before_nts12 | 12 | 19 | 117,074 | `9748b69253a58e73` |
| after_nts12 | 12 | 24 | 136,152 | `09d238435173bfec` |
| after_default6 | 36 | 72 | 417,592 | `f83844b7f196afeb` |
| bonly_default6 | 36 | 68 | 397,220 | `652165907f5f1c67` |
| deepseek_before | 96 | 181 | 1,120,899 | `1039614130ede682` |
| deepseek_after | 96 | 182 | 1,146,610 | `976c82e550a81e4c` |
| pcab_*（12 个目录合并） | 24 | 48 | 280,035 | `948edeb3dce9f6b1` |

另有三组实验的 tokens 当时只在终端打印、没有逐行归档：提示变体的抽取调用 193,452、提示变体的准入调用 170,215、deepseek 准入回放 115,313。上表加留出句日志（320,416 tokens）的可数合计为 3,935,998 tokens，加上这三组共约 4,414,978 tokens，是下限。
