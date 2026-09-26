<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.9 检索与 fresh QA 实施计划

> 执行方式：使用 `superpowers:subagent-driven-development`，按本计划依次完成失败测试、最小实现、合同审查和质量审查。用户已授权本轮自主迭代与 DashScope 请求，无需再次确认。保留现有未提交修改，不执行提交或重置。

**目标：** 在统一新核心的八库技术验收后，取得固定新增开发 133 题的首个健康 baseline，并比较既定两种检索配置。

**架构：** 仅新增评测编排入口与测试。通过显式参数复用原生检索、回答、解析及既有统计；Python 不实现产品语义逻辑，不改旧模块全局变量。运行时只从 build 绑定的 prepare/frozen 加载，当前审计程序及实际依赖保留指纹。

**技术组成：** C++ 冻结核心 `ead8046e…`、Python 评测编排、SQLite 费用账本、pytest、本机 HTTP 与 Stub/Fake 原生集成。真实模型固定 `qwen3.8-27b`。

设计依据：[评测设计](../specs/2026-09-26-socialmem-r59-expanded-evaluation-design.md)、[复用审计](../../../build/socialmem_20260926_r59_work/evaluation-reuse-audit.md)。设计预审已通过。本计划不表示八库、检索或 QA 已完成。

## 文件及边界

- 新增 `scripts/run_socialmem_r59_evaluate.py`：retrieve、qa、check；阶段身份与冻结、两级放行、局部费用/终态适配、失败审计。
- 新增 `tests/python/test_socialmem_r59_evaluate.py`：下述合同回归及真实 native 本机集成。
- 验证日志写入 `build/socialmem_20260926_r59_work/`；不可修改运行中的 builder、helpers、核心或其源码清单。
- 复用 `run_socialmem_r56_evaluate.py` 中经审计的参数化函数；涉及旧 builder/core/identity 的闭包以及旧 accounting/verdict/terminal/failure 链由新入口明确实现。

## 任务一：身份与调用前门槛

- [x] 在实现文件不存在时先建立并运行身份、任务数、两臂配置和既有输出目录拒绝测试；确认失败来自缺失的新入口，不把 import 环境错误当作行为 RED。
- [x] 实现 `validated_build`、唯一 runtime 加载、R59 seal/identity 和源码清单。通过新 builder 正式 check 后，核验八库健康、canonical cohort、数据库哈希、无 WAL/SHM、严格 true 开关与 target_units_v1。
- [x] 给旧核心、7/8 库、伪健康摘要、profile 漂移、题目重复/缺失、源库漂移和另一冻结根分别写拒绝用例；provider 构造回调必须保持未调用。
- [x] 固定 133 题、266 检索、532 QA；检索上界 1336、QA 上界 956。检索臂明确为 v6/hybrid/k10 与 v9/sources/k10，不从历史统计变量名推断配置。

执行：`.venv/bin/python -B -m pytest tests/python/test_socialmem_r59_evaluate.py -k 'identity or build or cohort or gate' -v`。先保存 RED，再保存对应 GREEN。

## 任务二：原始消费、严格类型和失败审计

- [x] 为 `choices=[]`、`choices=[null]`、`message=null`、refusal、length、usage 副本冲突先写测试。原始合法 usage 仍保留；技术健康为 false；未知用量保留 null 与已知小计。
- [x] 实现局部 `raw_accounting` 及调用它的 QA accounting/verdict/terminal/failure 路径。先提取原始回执费用，再判输出结构和副本一致性；不能经旧 wrapper 闭包绕回旧费用函数。
- [x] 为预约 ID、upper_bound、actual、charged_requests 的 bool/float/string 篡改先写拒绝测试；检查实际 SQLite 的 scope、stage、state 与上界。计数的最低类型约束如下，空值由所在状态另行判断：

```python
def require_count(value, *, positive=False):
    if type(value) is not int or value < int(positive):
        raise ValueError('strict integer count required')
    return value
```

- [x] 为 provider 构造失败、进入 native 后无回执、helper 已写中间文件、结算/汇总/写盘失败分别写失败审计用例。保留 started、预约、可见费用、未知量和未执行清单；不得生成伪正常终态。

执行：`.venv/bin/python -B -m pytest tests/python/test_socialmem_r59_evaluate.py -k 'accounting or usage or reservation or interruption or failure' -v`。

### 任务二补充：关闭评测预算账本连接

原始证据为 `build/socialmem_20260926_r59_work/evaluation-fd-diagnostic.jsonl` 及对应日志。首轮 105/106 的唯一失败来自本机全量 QA；此项补充在失败测试和实现修改之前写入。

- [x] 新增连接寿命测试，禁止靠垃圾回收：构造、reserve、settle、charge_upper、snapshot 返回或抛出 SQL 异常后，创建的每个连接均已关闭；另外保留跨线程预约和已有账本状态断言。
- [x] 在 `scripts/run_socialmem_r59_evaluate.py` 实现本阶段专用预算账本，通过 `make_ledger` 注入。沿用旧表、预算及锁，所有 `sqlite3.connect` 使用 `contextlib.closing` 包住事务上下文，例如 `with closing(sqlite3.connect(path)) as db: with db: ...`；不修改旧 helper 或产品核心。
- [x] 先保存新增测试 RED，再验证 GREEN。用完整四线程本机检索/QA重新验证 1336 次 embedding、956 次聊天和 532 个健康终态；独立 check 与前后库哈希检查继续必需。
- [x] 重跑描述符诊断，保存修复后的增长曲线和原始证据；不增加重试、调整模型或降低并发来规避失败。完整回归通过后再冻结交接。

### 任务二再补充：规范化答案绑定回原生 C++

合同探针发现联合篡改 `raw_xml` 与 `response.raw_response` 可以改变一个选择题分数，同时保留原始 HTTP/message.content、`raw_completion` 和 usage。该问题必须在真实 provider 前修复。

- [x] 在 `tests/python/test_socialmem_r59_evaluate.py` 固定 Q6 反例：HTTP/raw completion 保留错误选项、同时伪造 normalized `raw_xml`/`response.raw_response` 仍拒绝；合法 `<think>trace</think>answer` 经原生清理仍通过。保存 RED 日志和探针 JSON。
- [x] 在 C++ 现有 reasoning helper 上增加只读 Python binding，不在 Python 复制清理算法；绑定纯函数输入字符串、返回 C++ 清理结果。
- [x] 在 `scripts/run_socialmem_r59_evaluate.py` 的 raw accounting/terminal 链中，先核对 HTTP message.content↔raw_completion，再用 native binding 核对 raw_xml↔清理结果，并继续核对 response.raw_response↔raw_xml。任何联合篡改判技术失败、保留 raw usage 和未知边界；failure audit 的初始 raw accounting 也使用 native binding。
- [x] 跑 GREEN、完整 115 项、隔离候选 fixture 独立 check，并在独立进程复验新 binding 的实际 `_core` 路径；旧 builder/helper/正式 frozen core 不修改，真实 provider 不调用。

## 任务三：检索、QA 与 native 集成

- [x] 先测试 265/266 正常、坏 context、坏 ledger 均在 answer/judge 构造前拒绝；全部正常但 anchor 为零仍允许进入 QA。
- [x] 实现逐题源库副本、新 embedder 与持久 started；source10 只用 Stub，embedding 计数为零。检索调用既有 `query_one`，context 验证使用原生 grounded packet 与 renderer。
- [x] 从合格检索行构造固定 QA 任务；使用既有 `run_task` 与 DeferredLedger，最终判定和结算进入新的费用链。并发严格为整数 1..4。
- [x] 用候选 C++ + 本机 HTTP/Stub 完成检索、上下文、回答、原生 legacy reasoning 清理和独立进程 check。HTTP content 绑定 raw_completion；原生 raw_response 绑定 raw_xml，不错误要求 raw_xml 等于 raw_completion。
- [x] 对 context/source/策略/数据库声明、prompt 与 hash 同改重新 seal、fresh=false 分别验证拒绝；原八库阶段前后哈希不变。

执行：`.venv/bin/python -B -m pytest tests/python/test_socialmem_r59_evaluate.py -v`。本机监听受沙箱限制时使用已有授权的工具提权，测试不得向真实 provider 发请求。

## 任务四：统计、复验与两阶段审查

- [x] 同一全量合成 rows 输入原统计与新摘要，核对主要终点、固定 133 分母、失败零分、配对四格表和共同正常统计一致；正式 bootstrap 为 100000 次、seed=20260925。
- [x] 跑新增完整回归及复用边界：`tests/python/test_socialmem_r54_ablation.py`、`tests/python/test_socialmem_r54_qa.py`、`tests/python/test_socialmem_r55_expanded.py`、`tests/python/test_socialmem_r56_evaluate.py`。只在变更、失败或新增疑点要求时扩大范围。新增最终115项通过；旧边界为120通过/8失败/32setup errors，独立审计确认历史核心/源码身份不适配，不计为全套通过，具体覆盖限制见交接。
- [x] 冻结最终源码 SHA 与日志，完成合同与质量差量审查；主代理独立运行关键 CLI check，核对实际执行源码清单。真实执行仍受8/8 build gate约束。（差量合同与质量复审均 PASS；115 项回归与隔离候选 check 已完成，真实执行仍待8/8 build。）
- [ ] 更新中文报告及全库设计状态入口；真实运行引用不可变验证证据副本，避免报告更新引起运行证据漂移。

## 任务五：真实执行与结论

- [ ] 仅正式八库 8/8 验收后，在全新目录执行 retrieve；独立 check 必须证明 266/266 正常且 context/ledger 健康。
- [ ] 门槛通过后在全新目录执行 532 fresh QA，逐原始回执复算，不续跑或用旧答案补缺失。
- [ ] 输出整体、网络、题型、配对变化、正常率和成本；明确此为新增 133 题首个 baseline。两臂使用同一抽取核心，不能把检索差异归因于 R5.8 抽取 A/B。
- [ ] 依据真实错题区分来源缺失、语义遗漏、证据选取、回答利用和 judge 波动。后续 C++ 改进另按文档、失败测试、实现及同口径复评执行。
