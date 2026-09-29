# 回归与历史评测回放

## 日常回归

从仓库根目录执行，先安装当前代码对应的原生扩展：

```bash
.venv/bin/ctest --test-dir build --output-on-failure -j 4
PYTHONDONTWRITEBYTECODE=1 STARLING_RUN_LLM_E2E= .venv/bin/python -m pytest tests/python
```

默认运行当前核心、binding、编排、dashboard 和人工夹具测试。本机 HTTP 用例需要允许监听及访问 loopback；关闭真实 LLM E2E 不会关闭本机协议测试。普通失败、fixture 报错及 teardown 错误都必须使命令失败。

`historical_eval(reason=...)` 标记需要特定历史语料、数据库、封存源码或二进制的测试。默认在 fixture 执行前跳过，并输出原因和 `--run-historical` 提示。报告必须分别列出通过数、历史跳过数与原有跳过数，不能称为所有历史评测通过。标记只由显式代码决定，不读取上次失败清单、不依据文件是否存在动态变绿。未知标记通过 `--strict-markers` 拒绝；覆盖 `addopts` 时须保留该参数。

## 人工夹具与资源清理

`python/socialmem_fixtures.py` 中的配置是人工协议样例，不是历史实跑证据。固定 SHA 字段仅用于输入验证器契约，不声称对应当前已安装核心；本机原生行为测试仍载入实际扩展并校验其路径：路径由 `conftest.py` 的 `native_core_path` fixture 通过 `importlib.util.find_spec('starling._core')` 解析已安装扩展得到，随平台与解释器后缀变化，不得在测试里硬编码；HTTP 端点由用例改为本机临时服务。模型名只是被测试的配置字段，不触发外部请求。

新增测试应明确关闭数据库连接；Python SQLite 的事务上下文不应被当作连接关闭。测试基础设施在 fixture teardown 完成后执行一次循环垃圾回收，释放已经不可达的连接环，避免长进程积累描述符使后续本机 HTTP 失败。它不关闭仍被使用的模块级 fixture，不改变产品资源管理，也不抑制原始测试异常。

入口契约由 `python/test_regression_selection.py` 的隔离子进程覆盖：默认跳过与函数复用、显式历史失败、普通失败、未知标记、fixture 环回收顺序以及 teardown 错误传播。

## 历史回放

显式执行仍要求原始依赖完整，保留全部 SHA、seal、模块来源和语义断言。`--run-historical` 仅解除默认跳过，不能自动补齐归档或放宽验证。按文件使用独立 Python 进程，并以 `-m historical_eval` 选择历史部分，避免与其他文件的当前/冻结核心混装：

```bash
.venv/bin/python -m pytest tests/python/test_run_socialmem_baseline.py --run-historical -m historical_eval
.venv/bin/python -m pytest tests/python/test_socialmem_context_audit.py --run-historical -m historical_eval
```

每条命令都是独立回放；一个文件通过不代表其他轮次可回放。缺失已退役文件时应真实失败；需要恢复来源时另行提供经核验的原始证据，不能重新生成“相同历史”替代原件。

| 测试组 | 历史依赖 |
| --- | --- |
| 冻结 baseline、context/frozen audit、answer capacity | 当轮 frozen 核心、配置、来源数据库与封存清单 |
| scope latency、focus/k30/source speaker/structured scope | 固定题集、开发/保留网络划分、原始实验配置或产物 |
| R4.0 的三项 prepared 回放 | `prepare()` 默认读取 R3.5 固定题集和七个来源数据库，即使本机仍能通过也属于历史依赖 |
| R5.5–R6.2 原生探测、扩大建库与评测 | 各轮固定原生构建、源码清单、历史输入、原生提示词契约和 seal |
| R6.3–R6.6 恢复、候选评测与离线回放 | 原始对照数据库、题集、回答/召回回执、候选核心及封存身份 |
| R6.7/R6.8 selection 和 evaluate 四个文件 | 驱动加载时即读取该轮 `native-build.json`；整文件需要历史环境，包括看似仅测参数的用例 |

其余混合文件逐测试标记，共享函数会继承标记；同文件可自包含的预算、调度、账本、失败封存和输入校验仍默认运行。当前核心的来源选择规则继续由 C++ 回归覆盖。

部分无有效提升实验已依用户要求退役，见[退役记录](../docs/eval/2026-09-27-evaluation-artifact-retirement.md)。日常回归与历史回放分离不会产生新的 SocialMemBench 准确率；设计见[回归边界方案](../docs/superpowers/specs/2026-09-27-python-regression-boundary-design.md)。
