# Python 回归边界修复与最终验收

日期：2026-09-27。起点为 `codex/socialmem-r53-sidecar` 的 `5a945ca078b1584fe8ce87b071650df0536d029d`。这是[全面回归与 Dashboard 验收](2026-09-27-regression-dashboard.md)的后续，不重跑真实模型评测，不产生新的 SocialMemBench 分数。

## 修复范围

按中文设计、失败测试、实现、完整回归的顺序完成以下调整：

1. 将配置字典、当前 binding 与原生 localhost HTTP 测试迁移到人工夹具；spawn 场景复制实际受版本管理的 runner 至临时目录。没有恢复退役语料、数据库或旧预测。
2. 32 个文件按真实依赖显式标注历史回放，混合文件中的自包含测试仍默认运行。R6.7/R6.8 四文件的驱动在加载时就读取历史 `native-build.json`，因此整文件归入历史环境。R4.0 三项仍能通过的测试也归入历史回放，因为其 `prepare()` 隐式读取 R3.5 题集与七库；分类不等于按失败名单跳过。
3. `--run-historical` 显式恢复执行，缺失文件、错误 SHA、错误来源和旧语义契约仍真实失败。默认报告跳过原因；未知 marker 拒绝。保留全部原断言和历史驱动，没有将缺失依赖改成成功或 xfail。
4. 测试结束时、fixture teardown 完成后回收不可达循环对象，避免连接资源在同一个 Python 进程中累积；产品核心与 binding 行为未改变。

新的测试基础设施契约有六项：默认跳过且不执行历史 fixture、显式回放保留缺失文件错误、普通失败照常上报、拒绝未知标记、fixture 资源环及时回收、teardown 错误不被抑制。与样例写入测试一起验证真实子进程边界。

## 本地 HTTP 故障的诊断证据

第一轮分离后为 2379 通过、7 失败、1 报错、605 跳过。六个 HTTP 失败记录了 `transport_error:A libcurl function was given a bad argument`，本机服务收不到请求；另外两项是人工预算字段与变异值相同、R6.1 别名 fixture 未被标记，均已按实际依赖修正。

HTTP 两文件单独执行 21 项全部通过，和相邻测试一起执行 22 项通过。完整前缀则复现 3 失败、1408 通过、23 跳过；HTTP 前已有 1037 个文件描述符，`lsof` 显示大量临时 SQLite 文件来自已结束测试。仅增加一次垃圾回收的对照诊断中，描述符从 1110 降至 124，相同前缀变为 1411 通过、23 跳过。这个实验支持资源回收时机的诊断，不把问题归因于远端模型或 sandbox。

资源回收子进程测试在实现前真实失败，表现为下一测试无法观察到前一 fixture 的 finalizer；实现后通过。未修改 libcurl 请求实现、增加网络重试或跳过 HTTP 断言。新测试应继续显式关闭连接，测试钩子只回收已经不可达的对象，不能代替产品生命周期验证。

## 验证结果

最终完整默认套件为 **2385 通过、609 跳过、0 失败/报错**，耗时 228.57 秒。609 项中，**594 项为明确的历史回放、15 项为原有跳过**（2 项真实 LLM E2E 未开启、13 项既有 covered_by/deferred）。12 条警告来自 `test_socialmem_run_guard.py` 在多线程进程中使用 `fork()` 的 Python 3.14 弃用提示；本次测试通过，但不应称为无警告。

此前第一次完整绿色执行为 2388 通过、606 跳过。最后依赖审查将上述 R4.0 三项转入历史回放，并单独验证其全部通过；最终结果来自修改后的另一次完整执行，不是多轮去重或数值推算。

历史独立进程验证：冻结 baseline 2 项、context audit 9 项、R4.0 3 项通过，共 **14 项**。显式执行已退役 R6.8 的一个用例仍以 `FileNotFoundError` 失败，证明开关没有吞掉缺失归档问题。不能据 14 项通过推断其余历史测试通过，也不能把默认跳过数当作修复数量。

主 dashboard 与样例 dashboard 复核 **39 项 API 检查通过**，实际映射的核心均为当前安装版本：

`b9d6e83ac80f970fbcda5cf48633aa150f4332189f0b9b2ea40d34e65a6d7aac`

前一阶段同一核心已完成 C++ **1396/1396**、前端 **208 项**、类型检查、静态构建、Playwright smoke 和真实九页浏览器验收。本阶段只修改测试组织与文档；这些结果保留在前一阶段报告，不冒充本阶段重复执行。

## 服务、文档与证据

主服务为 http://127.0.0.1:8787/，独立样例服务为 http://127.0.0.1:8788/。主库保持原有内容；样例有 8 人、6 条人物关系、26 条声明、5 个承诺和 2 个 gist，支持本机召回测试。样例无真实模型绑定，首次访问使用现有 dashboard 令牌登录。

144 份现行设计文档统一补充回归和历史回放边界，覆盖系统、子系统、specs 及单独保存在 eval 下的设计。`docs/design/history` 是历史版本快照，正文保持原样。Dashboard README、测试说明、两份新中文设计及本报告互相对应；已有历史分数、负面结论、seal 与 SHA 不改写。

证据目录为 `build/regression_partition_20260927/`：`red.log`、`resource-red.log`、`python-junit.xml`、`python-final-junit.xml`、`python-verified-junit.xml`、`history-*-final-junit.xml`、`history-unavailable-junit.xml`、`http-order-*`、`http-gc-*`、`history-marker-review.json`、`design-sync.json`、`dashboard-api-recheck.json`。命令见[测试说明](../../tests/README.md)。日志和摘要保留，测试期间生成的数据库及冻结目录副本在验收后清理，不重新长期保留大体积中间产物。

验收后已删除本轮 15 个临时目录，合计 **2071.1 MiB 逻辑文件大小**；不将其表述为 APFS 物理可用空间增量。正式日志、JUnit、原生错误摘要、代码指纹、服务样例库和上一阶段原数据库备份均保留。回执见 `temporary-cleanup.json`，最终结果及代码指纹见 `verification-summary.json`。
