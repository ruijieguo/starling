<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.9：统一八库 baseline 实施计划

> 使用 superpowers:subagent-driven-development。用户已授权自主执行；中文文档 → RED → 编排实现 → 本地验证 → 合同/质量审查 → 一次有界真实运行，不自动提交。

设计见[统一八库 baseline](../specs/2026-09-26-socialmem-r59-expanded-baseline-design.md)。核心固定 ead804，仅复用已经验证的 C++ 能力；Python 不增加语义算法。

## 任务一：新身份与八库入口

- [x] 独立审查设计，确认三个 R5.8 B 真实终态及封印、固定 cohort 和核心；将历史身份与候选身份分开。
- [x] 先新增 `tests/python/test_socialmem_r59_expanded.py` 的 RED，覆盖设计列出的身份、调度、费用、数据与异常边界，日志置于 `build/socialmem_20260926_r59_work/`。
- [x] 新增 `scripts/run_socialmem_r59_expanded.py`，组合无旧身份副作用的既有 helpers，提供 prepare/build/check；不改旧 runner 常量或借 globals 切换实验。
- [x] 在独立进程验证固定新核心的全 cohort 原生 plan，并补真实 native/Fake/本机 HTTP/Stub embedding 的非空集成；修复后 77 项通过，合同差量审查通过。
- [x] 合同审查后质量审查；发现问题先 RED 再最小修复，日志与最终源码 SHA 归档。

## 任务二：重新建立八库

- [x] 在全新 `build/socialmem_20260926_r59_expanded/prepare` 冻结输入、候选 core、配置、源码、实际 helpers 与验证证据；独立 check 零 provider。
- [x] 串行 build 至全新目录，第一处健康失败即停止；不复用任何 R5.6 旧库，不续跑失败目录。实际首库通过，第二库 Tomas 第二批两次 schema_failure，后六库未执行，退出 1。
- [x] 独立原始 HTTP、费用账本、逐 holder 原生回放和 SQLite 证据审计，保存封印及未执行清单。独立 check 逐字段一致，34 个封印文件匹配；这证明失败产物可审计，不代表 8/8 健康。
- [x] 更新中文报告和全部设计/计划、两份技术报告入口；8/8 未通过时只报告失败诊断，禁止 QA。

## 任务三：健康 baseline 的检索与 QA

- 具体接入合同见[新核心检索与 QA 设计](../specs/2026-09-26-socialmem-r59-expanded-evaluation-design.md)；函数依赖、已复现的费用缺陷与 RED 矩阵见[评测复用审计](../../../build/socialmem_20260926_r59_work/evaluation-reuse-audit.md)。仅新增 `scripts/run_socialmem_r59_evaluate.py` 和 `tests/python/test_socialmem_r59_evaluate.py`，不修改旧阶段 globals 或核心。
- [x] 八库入口稳定后为 R5.9 评测身份适配补充具体设计及 RED；保留现有 133 题任务、主要终点、预算及评分合同。完整本机回归另发现账本连接生命周期问题，正在按补充设计修复。
- [ ] 实现、验证和审查独立 evaluate 入口，拒绝不完整八库，冻结单一运行身份。
- [ ] 8/8 健康后执行固定 baseline v6 hybrid10/source10 v9 sources10 两臂的 266 检索；仅 266/266 检索健康且 context/ledger 审计通过后执行 532 fresh QA，逐原始回执和固定分母复算。
- [ ] 输出整体、题型、网络和证据链诊断，区分抽取协议、语义遗漏、检索选取、回答与 judge 波动；无同 cohort 旧分数时明确这是首个健康 baseline，不虚构提升幅度。
