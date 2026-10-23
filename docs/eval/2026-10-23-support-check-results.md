# 前提核验验收结果：未通过，保持关闭

预注册：`2026-10-23-support-check-prereg.md`（冻结于 `6c2041a`，修订 5 于 `5040cea`，均在任何作答之前）。
留出集：BEAM-500K 会话 7–35，29 会话 × 20 题 = 580 题（弃答 58、可答 522），14 个类别。
产物：`build/dual_brain_20261017/spike/support_check/`（gitignored）。

## 结论

**核验保持关闭。四条判据全部不成立。** 决定规则按冻结顺序输出「S2 不成立 → 无效」，但更要紧的是
**S3、S4 也不成立，且区间远离门槛——核验对可答题有实质伤害**：

| 判据 | 门槛 | 实测 | 结果 |
|---|---|---|---|
| S1 弃答错误率（C）Wilson 上界 | ≤ 15% | 5/58，上界 **18.6%** | ✗ |
| S2 McNemar 精确单侧 | p < 0.05 | 改善 6、恶化 1，**p = 0.0625** | ✗ |
| S3 可答题低分率增幅上界 | ≤ +3pp | 188 → 238/522，增幅 **[+6.3, +13.0]pp** | ✗ |
| S4 可答题均分配对差下界 | ≥ −0.02 | 0.602 → 0.515，**[−0.113, −0.060]** | ✗ |

运行健康：580/580 作答成功、0 条缺原文行、判定失败 0（M5 = 0%，未降级）、改写一致性 0 违规、
裁判 2052 行无重复、解析失败 2 条。

token：作答 + 判定 + 裁判实测 **1.85e7**；建库抽取未计量，按用户话轮字数估约 4.2e6，另有修订 5 的
10 个半截库浪费约 1.5e6。合计约 **2.4e7**，在 3.6e7 上限内。

## 机制做对了它要做的事

弃答题上方向正确：错误作答 10/58 → 5/58，6 题被修好、1 题被弄坏。阶段 B 未过的那道线
（C3：弃答错误 Wilson 上界 ≤ 25%）在这里 **B 臂过不了（28.9%）、C 臂过得了（18.6%）**——描述性参照，
不作决定。

但幅度只差一点点：S1 需要错误 ≤ 3 题，实测 5 题；S2 需要至少 5 对不一致且全部有利，实测 6:1。

## 但它把大量可答题也判成了「未陈述」

判定在弃答题上 55/58（95%）判为 unsupported，这是它该做的；**但在可答题上也有 391/522（74.9%）**。
它几乎对所有题都触发，区分度很低。被改写的可答题均分 0.557 → 0.441。

**B 臂原本答得好（≥ 0.75）的 258 道可答题里，172 道（67%）被判为 unsupported 并改写**，改写后掉分。
最极端的三道 B 满分、C 零分：

- 「How do I find the derivative of h(x) = x^(3/5)?」——判定理由：证据讨论过 5/3、5/4、3/2 次幂，
  「但从未陈述 x^(3/5) 的导数」。B 臂直接用幂法则算出了答案。
- 「What should I consider when organizing my upcoming event?」——判定理由：证据里有很多活动规划偏好，
  「但没有一行直接陈述用户该考虑什么」。
- 「What improvements have been made in the latest version of the software?」——同类。

按能力的改写率与均分（描述性）：

| 能力 | 改写率 | B | C |
|---|---|---|---|
| event_ordering | 100% | 0.328 | 0.323 |
| summarization | 100% | 0.528 | **0.346** |
| abstention | 95% | 0.836 | **0.931** |
| preference_following | 90% | 0.899 | **0.617** |
| temporal_reasoning | 90% | 0.530 | **0.353** |
| multi_session_reasoning | 88% | 0.602 | 0.532 |
| instruction_following | 86% | 0.631 | 0.565 |
| knowledge_update | 59% | 0.565 | 0.595 |
| information_extraction | 38% | 0.782 | 0.770 |
| contradiction_resolution | 24% | 0.548 | 0.534 |

改写率最低的两项（information_extraction、contradiction_resolution）恰好是**答案以单一陈述存在于原文**
的题型；改写率 100% 的两项（summarization、event_ordering）是**答案必须综合多条原文**的题型。

## 根因：判定的语义与「可答」不是一回事

判定问的是「所问的具体细节**是否被某一行直接陈述过**」。这对弃答题是对的，但对大多数可答题都不成立：

- **综合题**（summarization、event_ordering、multi_session_reasoning）：答案是多条原文的组合，
  没有任何一行「直接陈述」它。
- **推理题**（temporal_reasoning、数学类 instruction_following）：答案要从陈述中**算出来**。
- **偏好/建议题**（preference_following、instruction_following）：用户要的是基于记忆的建议，
  不是某行原话的复述。

判定理由里出现「does not state」138 次、「not directly」70 次、「never states」65 次——它在忠实执行
「直接陈述」这个标准，**错的是标准本身**。弃答题与综合/推理题在「没有一行直接陈述答案」这一点上
**无法区分**；区分它们需要的是「证据**足以推出**答案」，而那正是作答模型本身的工作。

这也解释了为什么 information_extraction 几乎不受伤（答案就是某行原话），而 preference_following 掉了
0.28（判定认为「没有一行说用户该怎么做」，改写指令让模型改为罗列「记忆里有什么」，丢掉了建议）。

## 这否定了什么、没否定什么

否定的：
- **「独立判定 + 改写指令」这一具体方案**。按预注册 §2，判定措辞在验收期间不修；要换标准
  （如「足以推出」）就是新设计，须在新的留出集上重验。
- 「判定与作答分离能解决前提半真诱答」这个假设的**朴素版本**：分离后判定缺少作答时的推理能力，
  会把「需要推理才能答」误认为「没有答案」。

没否定的：
- 弃答问题本身真实存在、方向可修（10 → 5）。
- **lane 本身**：本次 B 臂（lane 开、核验关）的弃答错误 10/58 = 17.2%，Wilson 上界 28.9%——
  仍然过不了阶段 B 的 C3（≤ 25%）。lane 默认关闭的结论不变。

## 数据使用

BEAM-500K 会话 7–35 **已用掉**，不可再用于验收任何弃答相关的设计。剩下的未用数据：LongMemEval-S 的
17 道未碰过的 `_abs`（太少，撑不起判据）、BEAM-1M（未下载）。

## 复现

```
cd build/dual_brain_20261017/spike/support_check
python c1_fetch.py --start 7 --n 29          # beam500k_heldout.json, sha256 ceafebfd…
python b1_build.py --workers 10              # DASHSCOPE_* 用官方端点（见修订 5）
python s2_query.py --workers 12              # answers.jsonl
python s3_judge.py --workers 24              # judged.jsonl（B 全判两次，C 只判改写题两次）
python s4_analyze.py                         # analysis.json
```
