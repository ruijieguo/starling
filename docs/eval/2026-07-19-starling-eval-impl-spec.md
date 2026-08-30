# Starling 评测组合 — 实现规格(归因阶梯 + judge 对抗审计)

> 配套文档:
> - `2026-07-19-agent-memory-benchmark-landscape.md`(调研:领域全景与方法论警示)
> - `2026-07-19-starling-eval-plan.md`(三件套评测方案)
> - `2026-07-19-starling-eval-portfolio.md`(两段式组合方案)
>
> 本文把组合方案里两个最关键、别人普遍没做对的机制——**受控归因阶梯**与
> **judge 对抗审计**——下沉为可直接落地的实现规格:脚本接口、schema、
> 复用点、CI 接线、以及一个必须先解决的**前置阻塞项**。

---

## 0. 前置状态核查:S_star 已可从 Python 调用(原判"阻塞"已证伪)

整套组合的支点是归因阶梯的 `S_star`(Starling 认知层)对 `S_rag`(裸向量召回)
的**受控 A/B**。二者的唯一差异,必须是 Starling 的认知层:**视角遮蔽先于
语义排序** + **8 标签心智摘要 context_pack** + **四条件结构化弃答**。

**更正(2026-07-19 直查代码 + `.venv` 运行时验证):本文早前把"给
`RetrievalPlanner` 补 Python 绑定"列为前置阻塞项,这个判断是错的**——当时只读了
`python/starling/retrieval/__init__.py`(那里确实只有 `basic_retrieve`),漏看了
`_memory_core.py`。实际状态:

| 层 | C++ 实现 | Python 可达性 | 归因阶梯角色 |
|---|---|---|---|
| 裸向量召回 | `SemanticRetriever::vector_recall` | ✅ `_core.SemanticRetriever` | **S_rag** |
| 7 步规划 | `RetrievalPlanner::run`(`parse→mask→plan→fetch→fuse→ground→abstain`) | ✅ **已绑定**(`bind_05_retrieval.cpp` "P3.a1" 段,带 GIL 释放)+ facade `Memory.query()` / `_memory_core.plan_query()` | **S_star** |
| P1 结构化取 | `BasicRetriever::run` | ✅ `basic_retrieve`(仅 FACT_LOOKUP、单 holder) | 都不是 |

坐实 S_star 全路径可达的运行时证据(离线 `StubEmbeddingAdapter`,无网络):
- 有证据时:`plan_steps == [parse,mask,plan,fetch,fuse,ground,abstain]`,
  `context_pack` 非空且带标签(`[FACT] bob knows cats (conf 0.90, holder alice)`),
  `sufficiency == SUFFICIENT`。
- 空库时:`abstained == True`,`abstention_reason == "low_score"`,
  `context_pack == "[ABSTAIN] 无可靠记忆,主动拒答(low_score)"`。

**真正的缺口只有一个**:现有 `eval_longmemeval.py` 的 real-mode(`:144` 调
`vector_recall`)走的是 **S_rag 路径**,评测侧从没调过 S_star。且 grep 全仓,
**没有任何 Python 测试直接驱动 `_core.RetrievalPlanner` 走离线管线**——S_star
可达性没有回归钉子。所以 PR-0 从"补绑定"缩为"补这颗钉子"。

---

## 1. PR-0(已实现):S_star 可达性回归钉测

**目标**:钉死"S_star 全路径可从 Python 离线驱动并产出带标签 context_pack /
结构化弃答"这一归因阶梯最关键前提。绑定与 facade 均已存在(§0),故本 PR
**不碰 C++、不碰绑定、不碰 harness**,只补一颗此前缺失的 parity/可达性钉子。

**交付物**:`tests/python/test_eval_ladder_sstar_reachable.py`(已落地,2 测试通过):

- `test_sstar_returns_labelled_context_pack`:沿用 `test_semantic_retrieve_e2e.py`
  的离线管线(`_build_local_store_sqlite_runtime` + raw-sqlite seed +
  `StubEmbeddingAdapter(8)` + `EmbeddingWorker.tick_one_batch` +
  `SemanticRetriever`),经 `_core.RetrievalPlanner.run(PlannerQuery)` 断言:
  七步 `plan_steps` 齐备、`abstained is False`、`context_pack` 含 `[FACT]` 标签、
  top entry 命中 seed。
- `test_sstar_abstains_on_empty_store`:空库查询,断言 `abstained is True`、
  `abstention_reason == "low_score"`、`entries == []`——这是 S_star 相对
  S_rag(无弃答能力)的结构性差异,§4 认识论诚实主张的地基。

**为何用 `_core.RetrievalPlanner` 而非 `Memory.query()`**:钉的是**绑定层**
可达性(阶梯 runner 将直接组装 planner 以锁死 embedder/k/answerer 与 S_rag 一致),
故直接驱动 `_core`;`Memory.query()` 的高层封装另有 `test_dashboard_commands.py`
覆盖。二者互补。

**验收**:`.venv` 下 `pytest tests/python/test_eval_ladder_sstar_reachable.py`
2 passed(已验证)。因不碰 C++/绑定,无需重装 `_core`;并入常规
`pytest tests/python` 门即可。

> 归因阶梯 runner(`eval_ladder.py`)把 S_star 接成一个 stage 的工作,归属
> **PR-1**(§6.2),不在本 PR。本 PR 只解除"S_star 可达性无钉子"这一项。

---

## 2. 归因阶梯:六台阶的统一 runner

### 2.1 六台阶到代码的精确映射

同一 (语料, backbone, embedder, answer-prompt, judge, 种子) 下,只有"喂给
answerer 的记忆块"这一处不同:

| 台阶 | 记忆块来源 | 代码路径 |
|---|---|---|
| **S0** | 空(只有问题) | 不检索,`recall_block=""` |
| **S_rand** | 从全库随机抽 k 行 | `SELECT ... ORDER BY random() LIMIT k`(同一 seed) |
| **S_full** | 全部 history 行(截断到 window) | 直接拼 `_build_history_lines` |
| **S_rag** | `SemanticRetriever.vector_recall(k)` | **现有 real-mode 逻辑**(`eval_longmemeval.py:144`) |
| **S_star_oracle** | planner 检索,但库里 statement 由 gold 喂入(绕开 Extractor) | `plan_retrieve(...)`,seed 用 §2.3 oracle 注入 |
| **S_star** | planner 检索,库里 statement 由真实 Extractor 抽出 | `plan_retrieve(...).context_pack` |

关键纪律:

- **S_star 与 S_rag 的差 = 认知层的净贡献**,这是"归因"的全部意义。二者共用
  同一 embedder + 同一 k + 同一 answerer,唯一变量是 planner vs 裸召回。
- **S_star_oracle 与 S_star 的差 = 抽取质量的税**。两台阶用同一 planner、同一
  answerer,唯一变量是"库里 statement 是 gold 喂入还是 Extractor 抽出"。这把
  一个原本会静默污染归因的混淆项显式量化(见 §2.4):
  - `S_star_oracle ≈ S_star`:抽取够好,S_star 的表现就是表征能力的真实反映。
  - `S_star_oracle ≫ S_star`:表征本身有价值,但**当前被抽取拖累**——失败要
    归因到 Extractor,不是表征。技术报告 §5.3/§8 已实测 OOD/文学体/跨语言叙事
    上抽取退化会 −9~−20pp,SocialMemBench 这类多方对话抽取更难,更需要这台阶
    把"表征无效"和"抽取失效"分开。
  - `S_star_oracle` 是**表征能力的上界**;进攻主张的"机制强度"应引用它,而
    可部署强度引用 `S_star`。二者都报,不藏抽取税。
- **S_star 的 abstain 要计入评分**:弃答题(LongMemEval abstention / 假前提)
  上,`abstained=True` 且该题本就无答案 → 记为**正确**;有答案却弃答 → 记为
  错误。这样 §4 的进攻主张(认识论诚实)才测得出来,而 S_rag 无弃答能力
  → 在这些题上只能瞎猜。这是 S_star>S_rag 的一个结构性来源。
- **S_full 是"长上下文上限"对照**:若 `S_star ≤ S_full`,说明"其实窗口够大就行",
  差异化主张作废(直接回应调研里"语料能塞进上下文窗口"的警示)。

### 2.2 Runner 接口

新增 `scripts/eval_ladder.py`,是所有基准共用的归因编排器(不是每个基准各写一份):

```
python scripts/eval_ladder.py \
    --benchmark {locomo|longmemeval|beam|stale|socialmem|fantom|...} \
    --corpus tests/data/<...>.jsonl \
    --stages S0,S_rand,S_full,S_rag,S_star_oracle,S_star \
    --backbones deepseek-v4-flash,zing-14b,gpt-5.5 \
    --seeds 0,1,2,3,4 \
    --embedder text-embedding-v3 \
    --k 10 \
    --judge-config configs/judge_gpt5.json \
    --report build/ladder_<benchmark>.json \
    [--router-gate on|off]      # §4 差异化项的路由门控双版
```

- `--benchmark` 只选一个**适配器**(见 §2.3),语料形状由适配器归一。
- 每个 (stage × backbone × seed) 是一个独立 cell;runner 笛卡尔展开、串行或
  受控并发跑(注意 Clash 抖动:真 LLM 调用必须带重试 + 裸 curl 探活,见
  内存 `clash-tun-owns-all-network-flakiness`)。
- 输出**单一 JSON**(schema 见 §2.4),不写散装 md;记分卡由 §5 的 reporter 生成。

### 2.3 基准适配器(把异构语料归一成 runner 能吃的形状)

每个基准一个薄适配器,只做 I/O 归一,放 `scripts/eval_adapters/`:

```python
# 统一中间表示
@dataclass
class EvalItem:
    item_id: str
    raw_turns: list[dict]         # 原始对话轮(喂给真实 Extractor → S_star 的 statement 来源)
    gold_statements: list[dict] | None  # 该题所需的 gold statement(喂给 oracle → S_star_oracle);无则该题不参与 oracle 台阶
    question: str
    querier: str                  # 从谁问
    perspective: str              # 站在谁视角(视角题非空)
    intent: str                   # FACT_LOOKUP / BELIEF_OF_OTHER / ABSTAIN_CHECK ...
    gold: str | int               # 答案(MC=index,gen=文本);abstain 题 gold=None
    subset: str                   # 子集标签(用于逐子集报告)
    is_abstain: bool              # 无答案题
```

- **LoCoMo / LongMemEval / BEAM**:大多是无主体事实题 → `perspective=""`,
  `intent=FACT_LOOKUP`,`is_abstain` 仅 LongMemEval abstention 子集为真。
- **MemSyco-Bench / SocialMemBench / FanToM / 自建探针**:`perspective` / `target`
  有值,`intent∈{BELIEF_OF_OTHER, ABSTAIN_CHECK}` —— 这才是 S_star 施展空间。
- 适配器负责把原始 turn 归一成 `raw_turns`(给 S_star 走真实 Extractor 抽取);
  抽取**用固定 backbone + 固定 prompt**,并把抽取产物 hash 进 corpus_hash
  (见 §3 可比性),避免"换抽取模型偷偷刷分"(MemDelta 警示)。

**oracle 台阶的 gold 来源(`gold_statements` 怎么填)** —— 按基准原生结构化程度分三种,
决定 `S_star_oracle` 台阶对该基准是否可跑:

| 基准 | gold_statements 来源 | oracle 台阶可跑? |
|---|---|---|
| SocialMemBench | `personas`/`networks`/`qa` 已是结构化表,直接映射成带 holder 的 statement | ✅ 原生 gold |
| MemSyco-Bench | JSONL 已标注"有效记忆 / 冲突证据",可机械转 statement | ✅ 原生 gold |
| STALE | 生成管线的 `ontology_seeds` 即结构化种子,是天然 gold | ✅ 原生 gold |
| LongMemEval | 官方给 `answer_session_ids`(证据 session),可半自动抽 gold | ◐ 半自动 |
| LoCoMo / BEAM | 无结构化 gold;人工标注成本高 | ✗ 抽样几十题人工标,只作抽取税抽查 |

- oracle 注入走与 S_star **同一条 ingest + planner 路径**,唯一差别是库里 statement
  的来源是 `gold_statements` 而非 Extractor 产物——所以 `S_star_oracle − S_star`
  干净地隔离出"抽取税",不掺入 planner/embedder 差异。
- gold_statements 为 `None` 的题**不进 oracle 台阶**(如未标注的 LoCoMo 题),
  记分卡在 oracle 行注明覆盖率(如 "oracle over 62% of items"),不把缺 gold
  的题当作 0 分拉低上界。

### 2.4 报告 JSON schema

```json
{
  "benchmark": "longmemeval",
  "corpus_hash": "sha256:...",          // 含抽取产物,保证可比性
  "config": {"embedder": "...", "k": 10, "judge": "sha256:...", "router_gate": "on"},
  "cells": [
    {"stage": "S_star", "backbone": "deepseek-v4-flash", "seed": 0,
     "subset_scores": {"knowledge-update": 0.71, "abstention": 0.83, ...},
     "overall": 0.74,
     "ingest_cost": {"llm_calls": 1240, "tokens": 918273, "wall_s": 512.3},  // 写入成本必报
     "recall_latency_p95_s": 0.19,
     "abstain_stats": {"correct_abstain": 41, "wrong_abstain": 7}}
  ],
  "judge_audit": { ... see §3 ... }
}
```

`ingest_cost` 是**强制字段**(MemDelta:写入成本占 agent 执行 80%+ 却普遍不报)。
S_star 的 ingest 走完整巩固管线,必然比 S_rag 贵——把这个成本明确摆出来,
让"提升值不值这个写入代价"成为可判断的问题,而非被隐藏。

---

## 3. judge 对抗审计 + 可比性脊柱

### 3.1 judge 对抗审计(照搬 Penfield Labs 方法)

新增 `scripts/eval_judge_audit.py`,在**任何 A/B 数字发布前**先跑一次:

1. 对目标语料每题,用一个**廉价扰动器**生成"故意错但话题相邻"的答案
   (prompt:"给出一个与正确答案同话题、但事实错误的回答")。
2. 用**与正式评测完全相同的 judge 配置**给这些错答打分。
3. 统计 judge 的**错答接受率** `α`。

产物写进报告 `judge_audit`:

```json
"judge_audit": {
  "adversarial_accept_rate": 0.31,     // α
  "uninterpretable_band": 0.31,        // |Δ| < α 的一律标 n.s.
  "n_probes": 500,
  "judge_config_hash": "sha256:..."
}
```

**硬规则**:任何 stage 间差 `|S_a − S_b| < α` 一律在记分卡标记 **`n.s.
(< judge band)`**,不得作为"提升/不降"证据。这一条**同时保护防守层和进攻层**——
防守层的"不降"若落在 band 内,只能说"无法区分",不能吹"持平";进攻层
低于 band 的增益直接作废。

若 `α` 高得离谱(Penfield 在 LoCoMo 上实测 62.81%),说明该基准的默认 judge
不可用 → 换更强 judge 重跑审计,或换 exact-match/结构化评分(见 §3.3)。

### 3.2 标注核查(轻量,抽样)

- LoCoMo 已知 6.4% 标注错误(Penfield)。对每个基准**分层抽样 ~50 题**人工/
  强模型核对 gold,报告本地错误率 `e`。
- 若某子集 `e` 高,该子集的绝对分设"诚实上限 = 1 − e",记分卡里标注,
  避免把"基准错误"当成"系统失败"。

### 3.3 可比性(corpus_hash + 全配置锁定)

复用现有 `eval_quality_baseline.py:corpus_hash` 的思路,但**扩展 hash 域**:

```
corpus_hash = sha256( 原始语料 + 抽取产物 + 抽取prompt版本 + embedder标识 )
```

理由:MemDelta 实测"仅换 embedder(MiniLM→OpenAI)就能逆转 Mem0 vs RAG 的
结论方向"。所以 embedder 必须进 hash,两份报告 embedder 不同 → 直接判不可比,
reporter 拒绝并列展示。judge 配置也单独 hash 进 `config.judge`。

---

## 4. 判据(把两段主张写成可判的布尔式)

所有判据都建立在"过了 judge band + 过了可比性"的前提上。令 `Δ = S_star − X`。

### 4.1 防守层("普通基准不降")

对 LoCoMo / LongMemEval-S / BEAM-{100K,500K} 的**每个子集**:

- **PASS(不降)**:`S_star ≥ S_rag − α`(落在 judge band 内视为不降)。
- **PASS+(提升)**:`S_star − S_rag > α` 且**≥2 个 backbone 同号**。
- **FAIL(回归)**:`S_rag − S_star > α`(单模型即触发调查,不等多模型)。
- 总分附加:不掉出"已发表主流带"(达标带见 plan 文档),但**不追 SOTA**。

### 4.2 进攻层标的:数据可得性核实(2026-07-19 直查 arXiv/GitHub)

进攻层的外部基准必须先过"数据真的拿得到"这一关,否则 PR-4 撞墙。已逐一核实:

| 基准 | 数据公开 | 规模 | 格式/许可 | 判定 |
|---|---|---|---|---|
| **MemSyco-Bench** | ✅ 确认(`github.com/XMUDepLIT/MemSyco-Bench`) | 1,550 样本(5 任务 300–350) | JSONL + 评测代码 + 基线,**MIT** | **首选外部基准** |
| **SocialMemBench** | ✅ 确认(`hf.co/datasets/anon4data/socialmembench`) | 43 网络 / 430 人设 / 7,355 轮 / 1,031 QA(9 类) | 4 个 Parquet(networks/personas/conversations/qa),`datasets` 直读,`gated:false`,**C BY 4.0** | **首选外部基准(命中竞品结构盲区)** |
| **STALE** | ◐ 生成管线+种子(`github.com/icedreamc/STALE`) | 目标 400 场景 / 1,200 查询(需自跑生成) | seeds JSON + 生成/评测脚本,**MIT** | 追加确证(自跑生成,有前置成本) |
| **BeliefShift** | ❌ 无任何发布链接 | 2,400 轨迹 | 未公开 | gated / 改自建探针 |

**由此重排进攻层标的**(按数据在手程度,而非仅按机会大小):

1. **地基(数据已在仓库,不依赖外部发布)**:HiToM(已实测)、FanToM / ToMBench /
   Faux pas(已有 harness)、LongMemEval `knowledge-update` + `abstention` 子集
   (数据在 `tests/data/`)。进攻层主力落在这里,最稳。
2. **首选外部新基准(两个,均成品可用、零前置成本)**:
   - **SocialMemBench**(HF `anon4data/socialmembench`,Parquet,C BY 4.0,`gated:false`):
     43 网络 / 430 人设 / 7,355 轮 / 1,031 题(9 类),`multiple-choice-qa`。
     **进攻层最锋利的一把刀**——多方社会群组记忆正是竞品的结构盲区:调研实测
     Mem0/LangMem/Graphiti/Cognee 全聚在 0.12–0.18,远低于全上下文 0.369,因其
     用无主体事实 + 隔离键建模,天生表达不了"成员离开后的归属""区分群体规范与
     个人例外""A 知道 B 不知道"。而这恰是 Starling 的 per-cognizer 归属 + 视角化
     社会关系图 + 知识边界遮蔽 + 共目击求交的正面主场,潜在落差最大。
   - **MemSyco-Bench**(`github.com/XMUDepLIT/MemSyco-Bench`,JSONL,MIT):
     1,550 样本、五任务(拒绝记忆作事实证据 / 尊重适用范围 / 记忆-证据冲突消解 /
     追踪更新 / 有效记忆个性化)几乎逐条命中 Starling 的 mask / 观测优先 / 不覆盖 / 弃答。
3. **追加确证(数据可得但有前置成本)**:**STALE**。官方 repo(MIT)提交的是
   *生成管线 + 种子*,而非成品数据——要填 API key 自跑 5 步生成才产出
   `outputs/*_MAIN.json`。好处:官方 `full_eval_performance.py` 已给 SR/PR/IPA
   三维判定口径,且其隐式冲突 + IPA(记忆更新了但行为没跟进)极度契合 Starling
   的不覆盖再巩固,值得为它承担生成成本。代价:生成引入随机性,损害"对齐已发表
   数字"的能力,故**不进 PR-4 关键路径,作 PR-4 之后的扩展确证**;自跑的生成配置
   (backbone/seed/prompt)必须 hash 进 corpus_hash 以求可复现。
4. **gated / 自建探针**:仅剩 **BeliefShift** 数据完全未公开,**不进主计划关键路径**。
   其立意(理性修正 vs 谄媚漂移)极契合,务实做法是借鉴其**任务设计**、用 Starling
   自有 corpus 构造机制自建小型等价探针集——同时规避"用他人未发布数据"的可复现性
   与许可风险。

### 4.2b 进攻层判据

对 HiToM / MemSyco-Bench / FanToM / LongMemEval 强项子集(+ STALE 自跑生成 / gated 追加项):

- **CONFIRMED(大幅提升)**:同时满足
  1. `S_star − max(S_full, S_rag) > max(α, 0.05)`(超过两个上限,且超 judge band);
  2. **≥2 backbone 同号**(单模型记 `PLAUSIBLE — 待复现`);
  3. 机制可解释(能指到是 mask / abstain / 观测优先 / 不覆盖 哪条带来的)。
- **路由门控双版**:进攻项必须同时报 `router_gate=on/off`。技术报告已证分布
  外叙事上无差别注入会 −9~−20pp,门控收敛到 ≈ −0.7pp。所以:
  - `off` 版展示**原始机制强度**(有益区间内的真实增益);
  - `on` 版展示**可部署形态**(最坏退化被门控兜住)。
  - 记分卡两栏并列,不藏 off 版的负尾巴。

### 4.3 组合级成功标准(可证伪)

整套组合"成功"当且仅当:

1. 防守层**无 FAIL 子集**(有则先修回归,不发布);
2. 进攻层**≥3 个基准 CONFIRMED**,其中至少含 1 个非 HiToM(证明不是只会 HiToM);
3. 每个 CONFIRMED 都附了机制归因 + 通过了 judge band + ingest_cost 已披露。

任一条不满足 → 如实降级主张(如"仅 HiToM 与 STALE 上确证,余项待复现"),
**不修辞化**。这直接对应技术报告 §5 的诚实纪律。

---

## 5. 记分卡 reporter

新增 `scripts/eval_scorecard.py`,吃一组 `build/ladder_*.json`,出一张 md 记分卡:

```
## Starling 评测组合记分卡  (corpus_hash 组: 见脚注)

### 防守层(证明不下降)
| 基准 / 子集        | S_rag | S_star | Δ      | judge band | 多模型 | 判定      |
|--------------------|-------|--------|--------|-----------|-------|-----------|
| LoCoMo single-hop  | 0.72  | 0.73   | +0.01  | ±0.06     | —     | 不降(n.s.)|
| LoCoMo multi-hop   | 0.55  | 0.61   | +0.06  | ±0.06     | 2/3 ✓ | 提升       |
| LongMemEval 总     | 0.68  | 0.69   | +0.01  | ±0.05     | —     | 不降       |

### 进攻层(证明大幅提升)
| 基准               | max(full,rag) | S_star(off) | S_star(on) | Δ vs 上限 | 多模型 | 判定       |
|--------------------|--------------|-------------|------------|-----------|-------|------------|
| HiToM 3-order      | 0.66         | 0.77        | 0.77       | +0.11     | 2/2 ✓ | CONFIRMED  |
| SocialMemBench 多方 | 0.37        | 0.58        | 0.57       | +0.20     | 2/3 ✓ | CONFIRMED  |
| MemSyco 记忆-证据冲突 | 0.41       | 0.63        | 0.62       | +0.21     | 2/3 ✓ | CONFIRMED  |
| LongMemEval abstain | 0.48        | 0.66        | 0.65       | +0.17     | 2/3 ✓ | CONFIRMED  |
| STALE 隐式冲突(追加)| 0.55       | 0.71        | 0.70       | +0.15     | 2/3 ✓ | CONFIRMED  |

脚注:embedder=text-embedding-v3 | judge=gpt-5.5(band 见各行) | ingest_cost 见 JSON | STALE=自跑生成 config-hash 附注
```

规则:band 内标 `n.s.`;进攻项 off/on 双栏;未过多模型标 PLAUSIBLE;
**绝不输出掩盖子集结构的单一聚合 SOTA 数字**。

---

## 6. 复用矩阵与 PR 序列

### 6.1 复用现有设施(不重造)

| 需求 | 复用 |
|---|---|
| 多轮取中位数 / corpus_hash / per-metric 容差回归判定 | `scripts/eval_quality_baseline.py`(扩展 hash 域) |
| real-mode pipeline 装配(adapter+emb+worker+retriever) | `eval_longmemeval.py:_real_answer`(66-196) |
| MC 答案解析 / prompt 构造 | `eval_longmemeval.py:_parse_option_index / _build_answer_prompt` |
| ToM 逐阶评分 / 同模型在环范式 | `eval_tom_bench.py` / `eval_tom2_starling.py` / `eval_perception_starling.py` |
| commitment / fantom harness | `eval_commitment.py` / `eval_fantom.py` |
| Clash 抖动重试纪律 | 内存 `clash-tun-owns-all-network-flakiness`(dig+curl 探活) |

### 6.2 PR 序列(每个都可独立落地 + 全绿门)

- **PR-0**:`RetrievalPlanner` Python 绑定 + parity 钉测(§1)。**前置阻塞,先做。**
- **PR-1**:`eval_ladder.py` runner + LoCoMo/LongMemEval 适配器,先只跑
  fixture-mode 打通六台阶骨架(CI 可跑,offline)。
- **PR-2**:`eval_judge_audit.py` + 可比性 hash 扩展 + 记分卡 reporter(§3、§5)。
- **PR-3**:real-mode 全量接 S_star,补 BEAM-100K/500K 适配器;防守层判据落地(§4.1)。
- **PR-4**:进攻层适配器(地基:HiToM / FanToM / LongMemEval 强项子集;首选外部成品:
  **SocialMemBench**(HF Parquet,多方社会记忆——竞品结构盲区,潜在最大落差)
  + **MemSyco-Bench**(记忆-证据冲突/弃答))+ 路由门控双版
  + 组合级成功标准报告(§4.2、§4.3)。
- **PR-5**(追加,非关键路径):STALE 自跑生成管线接入(官方 `full_eval_performance.py`
  的 SR/PR/IPA 口径)作扩展确证;仅 BeliefShift 数据未公开,视获取情况自建探针。

CI 只跑 fixture-mode(offline、确定性);real-mode 全量是**非 CI 的 gated 真跑**
(OPENAI/DASHSCOPE key + 多 backbone + 多种子,受 Clash 影响需人值守),
产物 JSON 落 `build/`,记分卡人工核阅后入库。

---

## 7. 一页纸执行摘要

1. **先解锁能力**:S_star 现在根本没接进评测(real-mode 跑的是 S_rag)——
   PR-0 给 `RetrievalPlanner` 补 Python 绑定,否则整套归因阶梯不成立。
2. **一个 runner 打天下**:`eval_ladder.py` + 薄适配器,五台阶(S0/rand/full/rag/star)
   共用,防守与进攻同一套代码,差异只在语料适配器与判据阈值。
3. **归因是支点**:`S_star − S_rag` = 认知层净贡献;进攻还要 `> max(S_full,S_rag)`
   才排除"窗口够大/检索够用";多 backbone 同号才坐实。
4. **诚信脊柱前置**:judge band(错答接受率)、可比性 hash(含 embedder)、
   写入成本必报、标注核查——都在发布 A/B 前先跑,band 内一律 n.s.。
5. **记分卡而非单分**:两段主张分层展示,子集粒度,off/on 双版,不发聚合 SOTA。
6. **可证伪的成功**:防守无 FAIL + 进攻 ≥3 CONFIRMED(含非 HiToM);不达标就
   如实降级主张,不修辞化。
