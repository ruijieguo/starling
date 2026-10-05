# NEG 与 NEGATED 提醒行（qwen3.8-27b 与 deepseek-v3）

日期：2026-10-05。承接 [claim 通道修复尝试](2026-10-04-socialmem-claim-channel-fix.md)，那份记录留下一个没解决的问题：模型写出 polarity=NEG 却不带 `NEGATED` 标记，被作用域守卫拒收。这不是 SocialMemBench 评测，不产生准确率。

## 当前结论

- **在抽取提示末尾的格式检查块里加一行，按我事先登记的规则判为有效。** 该行说明：polarity 为 NEG 时 `scope_markers` 必须含 `NEGATED`，否则该声明会被拒收。守卫和解析没有改动。
- **qwen3.8-27b，预先登记的 24 条 NEG 声明：** 带 `NEGATED` 由 12/24 到 24/24（Fisher 精确检验双侧 p=0.0001），四个分组里没有任何一组倒退。变体 C（在示例里加一条 `ASSERTED` 加 `[ASSERTED, NEGATED]` 的否定偏好示例）18/24，p=0.1351，不满足规则，已撤回。
- **回归检查，两个天花板对照没有退化：** `emotion_negative` 和 `reported_distrust` 在 qwen 和 deepseek 上都保持 6/6。非 NEG 声明里带 `NEGATED` 的，qwen 0/30、deepseek 0/84，没有出现过度触发。
- **qwen3.8-27b 36 格：** 逐格配对变好 4、变差 0，终态 admitted 由 32 到 36，技术失败 0。
- **deepseek-v3 96 格（同传输）：** NEG 声明带 `NEGATED` 由 15/30 到 30/30。同一抽取提示的两次未改动运行是 20/30 和 15/30，合并 35/60，对 30/30 的 Fisher 双侧 p<0.0001，所以这个差异远大于运行间漂移。逐格配对变好 14、变差 2，`缺 NEGATED` 拒收由 15 条到 0 条。
- **变差的 2 格已逐个取证，见下文。** 一格是准入响应写了目录外的理由名，一格是 topic 逐字校验，后者在其它归档里本来就出现。

## 预先登记的规则

在任何变体运行之前，我把问题、设计、主要指标和判定规则写在本机文件 `build/socialmem_20261004_claim_channel_fix/prereg_negated_variants.txt`（未入库），运行结束后只按它判定。要点如下：

- 设计：`negative_target_scope` 与 `preference_contrast`，legacy 与 json_object，6 轮；三个核心的先后顺序按轮转交错，每轮每核心 1 次调用；qwen3.8-27b，默认传输，temperature 固定为 0。
- 主要指标：模型写出的 NEG 声明里 `scope_markers` 含 `NEGATED` 的比例（两用例两模式合并，每核心 24 条）。
- 有效规则，两条都满足才算有效：合并比例高于对照且 Fisher 双侧 p<0.05；逐（用例，模式）分组，变体含 `NEGATED` 的 NEG 声明数不比对照少 2 条或以上。
- 无效时不交付，不再追加同类变体。有效时先在两个天花板对照和 deepseek-v3 上做回归检查，之后才考虑提交。

## 结果

### 预先登记的对照（qwen3.8-27b，72 格）

| 核心 | NEG 声明带 NEGATED | 终态 | 请求 | tokens |
| --- | --- | --- | --- | --- |
| 对照：交付版本 `9b7bf154` | 12/24 | admitted 12、semantic_rejection 12 | 36 | 234,309 |
| 变体 C `1861c241` | 18/24 | admitted 18、semantic_rejection 6 | 42 | 259,015 |
| 变体 D `82fc43f2` | 24/24 | admitted 24 | 48 | 273,895 |

| 用例 | 模式 | 对照带 NEGATED | 变体 D 带 NEGATED | 抽取原文的不同写法数（对照 / 变体 D） |
| --- | --- | --- | --- | --- |
| `negative_target_scope` | json_object | 0/6 | 6/6 | 1 / 2 |
| `negative_target_scope` | legacy | 0/6 | 6/6 | 1 / 1 |
| `preference_contrast` | json_object | 6/6 | 6/6 | 1 / 1 |
| `preference_contrast` | legacy | 6/6 | 6/6 | 1 / 1 |

### 回归：deepseek-v3 NEG 声明带 `NEGATED`（两种模式合并，每用例 6 条）

| 用例 | 交付版本 | 变体 D |
| --- | --- | --- |
| `emotion_negative` | 6/6 | 6/6 |
| `negative_target_scope` | 0/6 | 6/6 |
| `preference_contrast` | 0/6 | 6/6 |
| `preference_qualifiers` | 3/6 | 6/6 |
| `reported_distrust` | 6/6 | 6/6 |
| 合计 | 15/30 | 30/30 |

### 变差的两格

- `preference_qualifiers`，json_object，第 3 次：交付版本 admitted，变体 D technical_failure，原因 `invalid admission reason`。这是真实的退步：交付版本在这一格入库了 1 条声明，变体 D 一条都没入库。机制上，交付版本里模型写了 2 条声明，NEG 那条缺 `NEGATED` 被守卫提前拦下，只有 1 个候选进入准入；变体 D 里 2 条都带齐标记，2 个候选都进入准入，而准入对第二个候选写了目录外的理由 `wrong_polarity`，整条响应被严格解析丢弃。准入提示没有改动，这个失败模式在本任务的全部运行归档里只出现这一次，它属于准入阶段已知的模型行为（2026-09-12 的报告记录过同类现象），只是原本被守卫挡住的候选现在会到达那一阶段。这是对机制的解释，不是免责：样本只有一格，但那一格确实丢了一条此前能入库的声明。
- `property_and_desire`，json_object，第 3 次：交付版本 admitted，变体 D semantic_rejection，原因 `topic is absent from source unit`。两次抽取原文不同，变体 D 写的 object 和 topic 是 "the boiler inspected tomorrow" 与 "the boiler inspected"，topic 不是来源里的逐字片段。这条拒收在 deepseek 的四个归档里出现过：修复前核心 3 次、交付版本 2 次、示例加收尾句核心 1 次、变体 D 2 次，是旧有现象，与提醒行没有关联证据。

## 这些结果不能说明什么

- 所有重复都是 temperature 固定为 0 的同一输入，重复不独立。预先登记的对照里，交付版本在每个（用例，模式）分组里 6 轮只写出 1 种抽取原文，变体 D 只有 `negative_target_scope` 的 json_object 分组写出 2 种。所以 24 条 NEG 声明实际只对应 4 个分组的少数几种输出，p 值描述的是这批格子，不是对模型的能力结论。deepseek-v3 的重复有较多变化（同一抽取提示的两次运行只有 28/96 格逐字节相同），那组更接近有效样本，但仍不独立。
- 这条提醒行重复了提示里已有的一条规则：指导段第 6 条已经写着 "NEG relation polarity requires NEGATED in scope_markers"。新增的是位置，它放在来源数据之后、格式检查块里，离模型生成答案更近。为什么位置有用，没有证据，不下结论。
- 只测了英文来源，句型限于偏好、情绪和信任的否定。中文来源没有测。只测了 qwen3.8-27b 和 deepseek-v3。
- 变体 D 让模型更常把主作用域写成 `NEGATED`：NEG 声明里 qwen 11 条、deepseek 18 条（其中 5 条的标记数组同时含 `ASSERTED`），而不是 `ASSERTED` 加 `NEGATED`。读侧检查接受这种形状，离线核对结果见"改动、测试与钉点"一节。
- 没有标签、没有准确率。`admitted` 只表示通过了确定性守卫和准入调用。

## 改动、测试与钉点

- 改动：`src/extractor/claim_contract.cpp` 的格式检查块加一行，只涉及抽取提示。准入提示、批计划不变。
- 新增 C++ 测试 `ClaimContract.FinalFormatCheckTiesNegativePolarityToTheNegatedMarker`：断言提醒行出现在来源数据之后的格式检查块里，并且 NEG 缺 `NEGATED` 的候选仍被守卫拒收，拒收原因是 `explicit source marker missing: NEGATED`。先单独加测试，确认它失败，再加提醒行，确认通过。
- 有意重录 6 个提示哈希钉点（C++ 5 处、Python 1 处），批计划钉点保持原值。
- 全量 ctest 1398/1398 通过。
- 读侧核对（离线，fake 适配器，变体 D 核心）：主作用域 `NEGATED` 加标记 `[ASSERTED, NEGATED]`、主作用域 `NEGATED` 加 `[NEGATED]`、旧形状 `ASSERTED` 加 `[ASSERTED, NEGATED]` 三种都 admitted，证据完整性校验无错误，管线 finished，入库为 NEG；`ASSERTED` 加 `[ASSERTED]` 的守卫对照仍被拒收，没有入库。

## 复现与归档

对照由 `scripts/probe_socialmem_claim_channel.py` 产生。每个核心都是把构建出的 `.so` 复制到仓库外，用 `importlib` 按路径加载，运行前断言提示里有或没有提醒行、示例和收尾句，断言不过就在花任何 token 之前退出。三个核心：交付版本 `9b7bf154`、变体 C `1861c241`、变体 D `82fc43f2`。变体 D 就是本次提交构建出的核心，装好后与测过的核心字节相同。变体 C 的源码改动脚本与预先登记文本、分析脚本、各运行脚本都归档在 `build/socialmem_20261004_claim_channel_fix/`，没有入库。

归档在 `build/` 下，被 `.gitignore` 忽略，不入库；密钥只从环境变量读取，所有归档目录已逐文件检查，没有出现密钥。

| 归档（build/socialmem_20261004_claim_channel_…） | 格数 | 请求 | tokens |
| --- | --- | --- | --- |
| variant_{main,C,D}_r0…r5（18 个目录） | 72 | 126 | 767,219 |
| variantD_default6 | 36 | 72 | 411,192 |
| variantD_deepseek | 96 | 190 | 1,157,968 |
