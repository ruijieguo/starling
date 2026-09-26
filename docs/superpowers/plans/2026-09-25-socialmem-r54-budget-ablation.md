<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.4 实施计划

> 执行代理：使用 superpowers:subagent-driven-development 或 executing-plans 逐项实施。用户已授权自主迭代，不重复询问执行方式；保留全部前序未提交改动。

**目标：**隔离来源容量与声明追加，恢复 v6 的证据覆盖次序，并对预先指定的 source10 候选执行门槛约束评测。

**架构：**v9 复用 v6 的 C++ 来源选择和 v8 的 sidecar 渲染；Python 仅透传及编排。使用现有实验分支与独立 build 输出，不改生产默认。

**技术栈：**现有 C++/SQLite 核心、Python binding、pytest/GoogleTest、DashScope 原生适配器。

## 任务1：文档与基线

- [x] 写入对应中文设计，固定四组配置、QA候选及请求上限。
- [x] 备份本轮将修改的核心、测试和binding文件到 `build/socialmem_20260925_r54_work/before/`，保存哈希。
- [x] 检查R5.3最终seal及当前core一致，不引用未封存或降级结果。

## 任务2：C++先测试再实现

文件：`tests/cpp/test_source_retriever.cpp`、`src/retrieval/source_retriever.cpp`、`include/starling/retrieval/source_retriever.hpp`。

- [x] 增加v9反例并运行RED：

```cpp
q.source_strategy="evidence_profile_v6"; q.mode="sources";
const auto expected=run();
q.source_strategy="evidence_profile_v9";
EXPECT_EQ(run()["source_refs"],expected["source_refs"]);
q.mode="hybrid";
const auto hybrid=run();
EXPECT_EQ(hybrid["source_refs"],expected["source_refs"]);
EXPECT_GT(hybrid["statement_count"].get<int>(),0);
```

夹具使用现有 `save_claim` 与 `embed_latest_statement` 创建真实可检索声明，补齐预算/来源关联/失败embedder和隔离对照，不能只断言上界。

- [x] 最小实现：profile内 `v6` 包含v9，但v8分支保持仅v8；Observer内共享 `independent_sidecar = v8 || v9` 用于来源上限、字节分项、追加和trace；v9 sources跳过planner。策略校验及profile入口注册v9。
- [x] 构建并GREEN：

```sh
.venv/bin/cmake --build build --target starling_tests _core -j2
build/tests/cpp/starling_tests --gtest_filter='SourceProfile.*:SourceClaimProfile.*'
```

- [x] 独立合同及代码审查；完整C++回归及相关Python回归。

## 任务3：binding与四组检索编排

新增 `scripts/run_socialmem_r54_ablation.py`、`tests/python/test_socialmem_r54_ablation.py`；修改 `tests/python/test_source_retriever_binding.py`。

- [x] 先写RED，固定 `baseline=(v6,hybrid,10)`、`source7=(v6,sources,7)`、`source10=(v9,sources,10)`、`sidecar=(v9,hybrid,10)`；断言重复/缺失题、错误策略/字节/非终态/降级均阻断。
- [x] 最小编排复用R5.3 stage/父manifest封存辅助，不修改历史runner的语义；每题临时数据库，主线程构造adapter避免环境并发，异常回执保留请求计数。
- [x] Python GREEN后运行四组真实检索，独立输出 `build/socialmem_20260925_r54_budget_ablation/`，最多690嵌入；比较source7→source10锚点、sidecar来源不变、baseline健康及context变化。
- [x] 保存完整seal、独立审计及门槛判定，不在Python重排来源/生成声明。

## 任务4：门槛通过后fresh QA

新增 `scripts/run_socialmem_r54_qa.py`、`tests/python/test_socialmem_r54_qa.py`。

- [x] 先写配置/上下文封存拒绝及统计方向RED；实现baseline/source10参数化双臂，复用冻结提示、裁判、native adapters与BudgetLedger。每条prompt/context绑定哈希；账本500上限，无历史复用。
- [x] 运行fresh QA：两臂各57题×两policy，最多228回答及相应自由题裁判；每次尝试及异常上界入账。
- [x] 分析配对四格、网络bootstrap、技术失败、裁判稳定性及tokens；只作组合效果结论。

## 任务5：同步与交付

- [x] 写 `docs/eval/2026-09-25-socialmem-r54-budget-ablation.md`，区分历史、当前检索及fresh QA，列出未执行环节。
- [x] 同步全部design/spec/plan与两份技术报告中文状态入口并验链，保留历史正文。
- [x] 核对core/源码/回执哈希、测试退出码、请求账本、`git diff --check`。不自动提交、合并或清理历史产物。

前置测试发现声明有效期漏洞：任务2补齐 `src/retrieval/retrieval_planner.cpp` 与对应planner测试，语义候选和source claim metadata对齐现有valid_from<=as_of<valid_to边界，NULL无界；先RED后修复，再重建同核心baseline。

检索执行恢复：首轮4条预检回执、8次embedding后因一holder降级停止；新`_retry1`目录完整重建，上限690、本轮累计698，旧incomplete封存保留。


## 执行完成记录

完整检索为`build/socialmem_20260925_r54_budget_ablation_retry1`，fresh QA为`build/socialmem_20260925_r54_qa_fresh`。QA进程退出0，228终态，398请求，legacy18→23/57、grounded18→25/57；两policy均达到事前扩大开发验证门槛。原始QA、独立SQLite账本/统计审计及文档同步清单已保存；扩大开发验证属于下一阶段，未在本轮冒记完成。
