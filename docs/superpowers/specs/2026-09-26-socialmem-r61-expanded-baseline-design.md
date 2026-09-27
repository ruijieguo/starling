<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

# SocialMemBench R6.1：以新核心真实探测绑定八库 baseline

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

## 前置条件和目标

本设计属于已授权的自主建库与评测闭环。只有 R6.1 四任务对照完成、两名候选 holder 均健康且非空、独立原生回放及消费审计通过，才允许新的八库 provider 调用。首轮传输故障不构成资格；运行器必须绑定后续通过的实际 seal，不能引用 R5.8 或只看人工摘要。

## 运行器设计

保留 R5.9 和 R6.0 的历史身份。将现有 `run_socialmem_r60_expanded.py` 内少量版本标签提取为常量，默认值严格保持 R6.0；不复制其八百余行 scope、回放和账本实现。新增 `run_socialmem_r61_expanded.py`，加载独立模块实例并注入 R6.1 core、历史 parent、实际 probe/prepare seal、专用 schema/arm、源码清单、隔离 core 路径及资格检查函数。原生 profile仍为 statement-first，行为版本通过新 core SHA区分。

资格函数必须在独立进程运行 R6.1 probe `check`，重算原生终态并要求：四任务均有可核验终态，两名 candidate 均非空，候选SHA与建库SHA完全相同，run及prepare seal与预先固定值相同，账本无保留额度。prepare封存该审计输出、程序指纹及run/prepare seal；build再次验证。已存在输出目录在读取输入或构造adapter之前拒绝。不得把旧core探测改标为新候选。

候选core固定为隔离构建 `d2f60d1836336f9114efd437fec428050ac77e6bbec6abeea02a0e219b9df793`。固定133题、8库、65 holder、1322来源单元、197批；belief上界591、三通道上界851。DashScope qwen3.8-27b、8192输出、thinking=false、HTTP retry=0、协议纠错预算1。串行fresh build，一库失败后停止后续库并封存原始回执、健康检查及账本。不拼接不同core或不同轮的健康库。

## 文档之后的测试

- 先验证新入口缺失导致RED；测试旧probe、错误core、不完整probe、空candidate、错误seal均在provider构造前拒绝。
- 复用已有R5.9八库原生fixture用例以验证共享stage实现；新测试把driver明确指向R6.1实例。固定旧SHA/profile的历史用例保留在旧文件，新增专属断言；不修改历史期望。
- 新prepare必须离线、分母及原生plan固定，篡改core/profile/source/config/summary/ledger或重封seal仍被拒绝；覆盖scope部分失败、原生回放、通道隔离和八库统计。
- R6.0只读历史check继续得到3/8 incomplete，验证提取版本常量未改变历史审计行为。

## 评分与边界

8/8全部健康才进入既定266检索、532fresh QA。评测入口也必须绑定R6.1 builder、core和build seal，不能放宽R5.9 evaluator门禁。评分实现仍先写专属测试并复用既有审计逻辑，首次完整分数称baseline。当前设计不改变语义作用域、谓词、检索和回答政策；这些能力修复须在baseline之后独立对照。

真实结果与失败结果都同步报告；本设计本身不表示探测已通过或八库已完成。
