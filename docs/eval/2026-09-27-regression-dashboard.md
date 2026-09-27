# 全面回归、Dashboard 重启与样例验收

> 后续修复及当前 Python 回归入口见[回归边界修复报告](2026-09-27-python-regression-boundary.md)。下文保留本阶段首次全面检查的失败与诊断事实，不能用后续默认跳过覆盖历史失败。

日期：2026-09-27。检验起点：`codex/socialmem-r53-sidecar`，HEAD `5a945ca078b1584fe8ce87b071650df0536d029d`。本阶段首次验收时，新增样例修复、测试及中文文档尚未提交；未推送或合并。后续修复与整体交付见上方链接。

## 结论

当前 C++、前端及 dashboard 专项回归通过，主服务和独立样例服务均已启动并完成真实 API、浏览器验收。修复了旧样例脚本成功退出却生成零人物、零关系的问题。

**Python 全量套件未全绿。** 首轮出现 567 条失败或报错记录；独立进程复测后，其中 10 项恢复通过，剩余 557 项依赖退役历史文件、旧构建身份或旧实验契约。没有删除这些测试、放宽来源校验或恢复已退役的无效实验数据。此报告不代表重新完成 SocialMemBench 模型评测，也不提供新的准确率成绩。

## 回归结果

| 检查 | 本轮结果 | 证据 |
| --- | --- | --- |
| CMake 配置、构建、安装 | 全部成功 | `configure.log`、`build.log`、`install.log` |
| 完整 C++ CTest | 1396 通过，0 失败、0 跳过 | `cpp-junit.xml`、`cpp-tests.log` |
| 完整 Python 首轮 | 2405 通过、117 失败、450 报错、15 跳过 | `python-junit.xml`、`python-tests.log` |
| Dashboard 与新增样例契约 | 215 通过 | `dashboard-final-junit.xml` |
| 冻结 baseline 独立进程 | 19 通过 | `baseline-isolated-junit.xml` |
| 上下文审计独立进程 | 9 通过 | `context-isolated.log` |
| R6.3 独立进程 | 2 通过、5 报错；进一步暴露历史源码清单问题 | `r63-isolated-junit.xml` |
| 前端类型检查 | 0 错误、0 警告 | `frontend-tests.log` |
| 前端单元测试 | 26 文件、208 项通过 | `frontend-tests.log` |
| 前端静态构建 | 成功 | `frontend-build.log` |
| 仓库原有 Playwright smoke | 1 通过 | `playwright-smoke.json` |
| 真实服务 API | 主服务 11 项、样例服务 28 项通过 | `api-checks.json` |
| 真实浏览器页面与交互 | 样例 9 页、主服务首页壳通过；0 控制台错误、0 页面异常、0 失败响应 | `browser-checks.json`、四张样例截图 |

证据均位于仓库内 `build/regression_dashboard_20260927/`。前端单元测试输出存在 Node 关于 `--localstorage-file` 的运行警告，不影响测试通过。

按测试标识合并首轮与专项复测，本轮共验证 **2416 个不同 Python 用例通过、557 个未通过、15 个跳过**，其中包含 1 个新增样例用例。这是多次执行的去重汇总，不能表述为另一次完整套件通过；原始全量失败日志仍保留。15 个跳过中，2 个为未开启的真实 LLM E2E，13 个为仓库既有 covered_by/deferred 标记。

## Python 全量未通过项的具体归因

| 最终归因 | 数量 | 证据及边界 |
| --- | ---: | --- |
| 退役历史文件缺失 | 329 | 例如 answer_capacity_v2、dialogue_expansion 配置，R5.9/R6.1/R6.2 evaluator fixture 的 seal，以及 R6.4–R6.8 原始候选、离线选择和 native-build 文件。清理背景见[数据退役报告](2026-09-27-evaluation-artifact-retirement.md)。 |
| 固定历史核心或源码身份不匹配 | 194 | 例如 `current/frozen core mismatch`、`fixed candidate core mismatch`、`current/frozen source set/hash drift`、`audit program drift`。这些测试绑定旧实验源码及二进制，并非自动适配未来 HEAD 的产品单元测试。 |
| 历史原生提示词契约不匹配 | 29 | R5.8 用例要求 `target_units_v1`；当前 C++ 为 `target_units_statement_first_v1`，因此原有配对计划门禁拒绝。未为迁就旧实验而改回核心。 |
| 历史封存源码集合缺少后来新增文件 | 5 | R6.3 独立进程显示 `archived implementation dependency missing`；缺少 `include/starling/retrieval/source_selection.hpp` 和 `src/retrieval/source_selection.cpp`。原历史封存清单未被改写。 |

初轮另有 15 条 `non-frozen module already loaded: starling._core.testing`。这是将当前原生模块和冻结历史模块放在同一 pytest 进程时触发的来源保护：baseline 的 1 项与上下文审计的 9 项在各自独立进程中通过；其余 R6.3 的 5 项隔离后暴露上述源码集合不兼容。最终 557 项中已包含这 5 项，未重复计数。

逐项测试标识、原始原因及后续诊断位于 `python-failure-classification-final.json`。后续若要使默认 Python 套件可持续全绿，应把历史封存回放明确拆为独立进程的可选验收，并为长期维护的通用能力建设自包含夹具；不应通过重写历史 SHA、删断言或伪造旧实验产物解决。

## 样例缺陷修复

旧 `scripts/seed_demo.py` 使用 FakeLLM 生成抽取 JSON，但未给出 `subject_kind`。当前 C++ 解析器对缺失类型安全默认为 `entity`，人物注册只接受明确的 `cognizer`，因此原脚本写出了 26 条声明、5 个承诺，却没有人物及关系。

本轮按中文设计、失败测试、实现、验证的顺序修复：

1. 编写[样例契约修复设计](../superpowers/specs/2026-09-27-dashboard-demo-contract-design.md)。
2. 新增 `tests/python/test_seed_demo.py`，通过真实脚本子进程写入临时 SQLite，并验证八个人物、非人物排除、六条关系、声明与向量、承诺四状态、两个 gist；RED 阶段明确失败于人物集合为空。
3. 在人工样例 JSON 中显式标注 `subject_kind` 与人物种类；发布计划及服务仍是 `entity`。解析、注册、声明写入和关系持久化仍由 C++ 执行，未添加 Python 核心规则或 SQL 插入捷径。
4. 新增用例通过，全部 dashboard 专项 215 项通过，并以真实 API 与页面验证修复效果。

同时修正样例 `--reset` 的说明：它删除整个指定数据库及 WAL/SHM 文件，不是只清空一个租户。本轮未对用户数据库执行 reset。Dashboard README、基础设计与重设计入口均同步链接此次中文设计和验收报告。

## 服务与样例数据

| 服务 | 地址 | 数据与配置 |
| --- | --- | --- |
| 主 Dashboard | http://127.0.0.1:8787/ | 保留原 `~/.starling/dashboard.db` 与 `~/.starling/starling.json`；原配置内容校验一致。 |
| 离线样例 Dashboard | http://127.0.0.1:8788/ | `build/regression_dashboard_20260927/demo/validated.db`；独立配置及摄入队列，没有真实模型绑定，自动维护 tick 关闭以保留样例状态。 |

样例服务复用现有 dashboard 的登录令牌；浏览器不同端口的本地存储相互独立，首次访问 8788 时使用现有令牌登录。配置与启动日志按敏感文件保存为 `0600`，备份目录为 `0700`，报告不包含令牌或密钥。

样例包含：26 条声明、24 条原文证据、26 条向量、8 名具名人物、6 条人物关系、2 个 gist、5 个承诺。其中 ACTIVE 2、BROKEN 1、FULFILLED 1、WITHDRAWN 1。关系图按现有设计仅绘制有边的 6 人，其余 2 人仍显示在八人人物表格中。概览中的「关系边」统计的是 `statement_edges`，本样例为 0；它不同于社会图的 6 条 `cognizer_relations`。

API 检验覆盖鉴权（未授权请求预期 401）、概览、声明、人物、关系、承诺、gist 及成员、脑区图、证据、生命周期、预报、队列、指标、工作集、运行健康和语义召回。样例召回能够返回 authentication service 相关记忆。

浏览器检验覆盖概览、人物图、声明、承诺、gist、脑区图、原始证据、运行健康、生命体征九页；验证人物详情、26 行声明的三页翻页、承诺筛选及 gist 来源详情。样例使用 FakeLLM 和确定性嵌入，页面显示模型未配置是预期状态；不代表真实模型对话质量已验收。

原进程加载过时的 `~tarling/_core...so`。重启后主服务与样例服务均为 READY，实际映射的原生库与当前构建/安装产物 SHA-256 一致：

`b9d6e83ac80f970fbcda5cf48633aa150f4332189f0b9b2ea40d34e65a6d7aac`

## 数据保全与临时文件清理

停止旧服务前已通过 SQLite backup API 生成一致性备份。原数据库的声明、原文证据、人物及承诺既有 ID 集合全部仍存在；主服务恢复后计数为 9569 条声明、1524 条证据、1352 个人物、111 个承诺，未灌入人工样例。原库及样例库 `PRAGMA quick_check` 均为 `ok`。主服务按既有配置继续后台工作，计数不承诺长期固定。

完成测试后清理本轮 pytest 临时副本和初次缺陷样例库，释放约 1022.9 MiB 逻辑文件大小；这是逻辑字节统计，不冒充精确物理磁盘回收量。日志、JUnit、分类清单、样例库、样例配置、截图及原数据库备份保留。证据：`original-data-preservation.json`、`database-final.json`、`temporary-cleanup.json`。

## 复现入口

```bash
.venv/bin/cmake -S . -B build -G Ninja -DCMAKE_MAKE_PROGRAM="$PWD/.venv/bin/ninja"
.venv/bin/cmake --build build -j 4
.venv/bin/cmake --install build --prefix "$PWD/.venv/lib/python3.14/site-packages"
.venv/bin/ctest --test-dir build --output-on-failure -j 4
PYTHONDONTWRITEBYTECODE=1 STARLING_RUN_LLM_E2E= .venv/bin/python -m pytest tests/python -q -o addopts=-ra
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/python/test_dashboard*.py tests/python/test_seed_demo.py -q -o addopts=-ra
```

上述完整 Python 命令在本阶段首次检查时仍失败，不能把专项通过替代其结果。后续默认回归与历史回放已分开，当前命令及边界见[测试说明](../../tests/README.md)；覆盖 addopts 时保留 `--strict-markers`。冻结 baseline 与上下文审计应分别在独立 Python 进程执行。前端命令为 `dashboard/web` 内的 `npm run check`、`npm test -- --run`、`npm run build` 和 `playwright test`；真实服务的本轮验收脚本为证据目录中的 `check_api.py`、`check_browser.cjs`。
