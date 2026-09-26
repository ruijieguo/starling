> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：开发332/733=45.29%，对上一轮37.24%提升8.05百分点；60回答截断等74技术失败计零。本文历史结果保留原冻结身份；最新开发结论及限制见[当前报告](2026-09-17-socialmem-grounded-answer.md)，无本轮保留或全量成绩。

# SocialMemBench 谓词与来源上下文优化评测

> 后继结果（2026-09-12）：[来源话轮与独立扩展标签诊断](2026-09-12-socialmem-source-turn.md)已完成并核验，固定候选 61/64、synthetic 契约 8/16、扩展对象覆盖 9/14/联合覆盖 1/14，质量门槛未通过。以下保留各自阶段的历史结果。

**日期：** 2026-09-12（Asia/Shanghai）
**状态：** 本文件为首轮优化的冻结结果。后续修复最新状态见文末链接。本轮 C++ 实现、全量工程验证、离线 smoke 和修复后的真实诊断均已完成；真实目录已由验证器核验为 `verified`，运行状态为 `complete_with_errors`。

## 实现

关系校验、SourceTurn 元数据、主题字段和 Context Pack 展示均在 C++。Python 仅增加 `SourceTurn`/证据字段的数据类，并把未完成 pipeline 作为技术失败归档。默认契约开关保持关闭。

## 验证

- C++：1027 通过、1 跳过（本地 HTTP 流式重试边界测试需外部服务）。
- Python：1274 通过、15 跳过（`PYTHONPATH=.`）。
- 离线 smoke：140 次原生重放、144 个数据库，验证器状态 `verified`。
- 新增 RED 用例覆盖认知 `feels`、职责 `trusts`、第一人称 `said yes`、SourceTurn/session/turn/topic；实现后全部 GREEN。
- 真实诊断归档：76 次抽取、64 个固定候选、51 次准入调用、8 个回答尝试、120 次裁判投票；验证器核对原生回执、来源、数据库和回答上下文完整性通过。

## 真实结果

新的真实目录为 `build/socialmem_20260912_optimization_real_final/`。64 个固定候选正确 61/64（30 个正例保留、31 个负例拒绝、0 个误收、2 个误拒、1 个技术失败）。synthetic 冻结组 13/16，契约组 4/16；配对退步集中在 `emotion_positive`、`emotion_negative`、`relief_cause`、`possible_not_decided`、`decided_decline`、`decision_change`、`indifference`、`trust_target`、`topic_reference`。P1 base F1 为 holder .7500、holder/perspective .7000、predicate/object .7875；加入新抽取后的 combined F1 降至 .7317、.6829、.7683。Q1 四臂通过数为 baseline 3/3、structured 1/3、linked 1/3、full 3/3；Q9 为 baseline 0/3、structured 0/3、linked 0/3、full 3/3。

本次运行共归档 16 个技术失败，主要为 schema 信封失败；来源证据、embedding、检索和裁判链路未出现失败。验证器记录 `native_ingestion_replays=140`、`databases=144`、`extraction_calls=76`、`fixed_injections=64`、`admission_calls=51`、`judge_votes=120`，manifest SHA-256 为 `f09e8cbf2cec599b4b84ea9da969ecf24fa3e7e1eb45b51d9ca3020790951b77`。

## 结论

本轮工程证据支持 C++ 边界和诊断可追溯性，且评测器已能把技术失败与语义拒绝分开归档；真实结果仍显示 synthetic 退步、P1 合并指标下降，不能证明总体准确率提升。质量门槛未通过，`promotion_ready=false`，生产默认关闭，1031 题全量评测不启动。下一轮优先修复言语行为误拒、主题与原始时间上下文保真，以及 schema/传输稳定性，再重新进行小规模配对评测。

## 后续修复记录

可空主题和中文情绪误拒已进入后续修复，详细证据见 [修复报告](2026-09-12-socialmem-repair.md)。本文件分数对应原冻结目录，不能当作修复后的结果。原 C++ 沙箱跳过用例是自建本地回环 HTTP 服务测试，并非依赖外部服务。
