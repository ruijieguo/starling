<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# 共同知识算子 `is_common_knowledge` 设计
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

**目标:** 内化第三个确定性社会认知 compute-算子 —— 群体**共同知识/迭代互信念**。计算 deepseek 在复杂故事上"算不动"、Starling 可确定性计算的深度社会认知。

**教训(已确立,勿重探):** Starling 算子只在 deepseek 系统性失败的 COMPUTE regime 解锁(HiToM 嵌套信念链 fixed-Starling +6.4%,o3 +16.7%/o4 +15.8%);surface 算子(mental_state / faux_pas / appraise)deepseek 能从故事读 → ≈ baseline。共同知识是下一个 compute regime:deepseek 在 public/private × 谁在场 × 多事件序列上跟丢迭代互信念。

---

## 1. 能力定义:共同知识 ≠ 一阶共享

现有 `shared_with(members)` 算**一阶**:全员都"相信"某事实。这**不是共同知识**。反例:Anne 分别私下告诉 A、B、C 同一事 → 三人都信(shared_with 命中),但**非共同知识**(A 不知道 B 知道)。

**共同知识**(迭代互信念,"人人知人人知…")由 **public 事件**建立:G 全员**同时目击**同一事件 ⇒ 人人见人人见 ⇒ CK。private tell / 子集目击 ⇒ 非 CK。

**关键洞察(接上 HiToM 机器):** X 的当前状态在 G 中是共同知识 ⇔ **G 全员对其最新建立事件都有 perception 行**(全员 co-witness)。这正是 `what_does_X_think_chain` 里那套 source_event_id 全员交集逻辑,直接复用。

---

## 2. 算子 `is_common_knowledge`(C++ 核心)

**位置:** `include/starling/tom/mentalizing.hpp`(声明)+ `src/tom/mentalizing_common_knowledge.cpp`(实现,~参考 mentalizing_chain.cpp 158 行体量)。

**签名:**
```cpp
struct CommonKnowledgeResult {
    bool is_ck = false;                  // 群 G 对 theme 当前状态有共同知识
    std::string ck_value;                // 最新被 G 全员 co-witness 的事件值(CK 的值;非空即末次公共已知)
    std::string establishing_event_id;   // 建立该 CK 的 source_event_id(审计)
};
CommonKnowledgeResult is_common_knowledge(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,            // parity(与 chain 一致,保留位)
    const std::vector<std::string>& group,            // G 的成员 cognizer_ids
    std::string_view theme,
    std::string_view tenant,
    std::string_view as_of);
```

**算法(全部复用既有查询):**
1. `group` 空 / `dim_for_theme(theme)` 空(从未感知)→ `{false}`。
2. 对 G 每个成员:`perceived_for_theme(member, theme_n)` → 行集(每行带 `source_event_id`、`position`、`state_value`)。
3. `g_max` = G 全体成员里 position 最高的那行(群 G 对 theme 的**最新信息**)→ (g_event_id, g_value)。
4. `cw` = **被 G 每个成员都有的 source_event_id 集**(全员 co-witness 交集;同 chain 的 obs_sets 交集)。
5. `is_ck = (g_event_id ∈ cw)` —— 群 G 看到的最新 theme 事件是否被**全员**共目击。`ck_value` = cw 中 position 最高那个事件的值(末次公共已知);`establishing_event_id` 同。
   - public 末次建立(全员在场)→ g_max ∈ cw → **is_ck=true**。
   - private 末次(某 G 成员私下被告知/目击 L2,他人没)→ 该成员 g_max ∉ cw → **is_ck=false**(子集已分化,非 CK)。
   - 非-G agent 的私下移动(无 G 成员目击)→ 不影响 G 内 CK(CK 是**群内互信念**,非全局物理态)→ G 仍 CK 末次公共值。✓

**复用(不另起炉灶):** `perceived_for_theme` / `dim_for_theme`(perception_state_store,已有)+ source_event_id 全员交集(搬 `what_does_X_think_chain`)+ 概念上 `shared_with` 的一阶前置(CK 在其上加"public 建立")。

---

## 3. 抽取:无新抽取

public/private 区分**已由现有抽取支持**:`publicly claimed` → 抽成 `tell`,participants = 全体在场者(实测 predcheck:`Charlotte publicly claimed` → tell participants=[Charlotte, William, Jack, Noah, Hannah]);reconstructor 给每个 recipient 写 perception 行(同 source_event_id)→ 全员 co-witness → CK。`privately told` → tell participants=[teller, 单 recipient] → 只 recipient 有 → 非 CK。物理移动(全员在场)→ 全员见证 → CK。**抽取层零改动。**

## 4. 注入/门控(server,瘦)

`scripts/starling_tomeval_server.py`:加一个 CK 问题识别(parse "common knowledge among {…} that … is …")→ 调 `is_common_knowledge` → 定论注入(同 chain 的 `_format_chain_injection` 风格:"Starling 确定性算得:X 在 G 中是/不是共同知识,值=…")。**复用 STARLING_CHAIN_ONLY 同款能力门控**:只在 CK 问题注入,其它静默。

## 5. 验证评测(构造新评测,诚实)

现有 ToMBench/HiToM/EmoBench 增益面已基本捕获 → 构造**新合成评测** `CommonKnowledge`:
- **故事生成器:** HiToM 风格(多 agent 进/出房间 + 物理移动),末次 theme 建立**随机 public(全员在场)或 private(子集 tell / 子集目击)**,叠加干扰事件(其它 theme 移动 / 进出)制造复杂度。
- **问句(用户定:bool 直接问):** "Is it common knowledge among {A, B, C} that the X is in Y?"(Y = 末次建立的位置)。选项 yes/no(+ 可加"X 不在 Y"类干扰减猜测)。
- **金标:** yes ⇔ 末次建立事件被 {A,B,C} 全员 co-witness(public)。private → no。
- **假设:** deepseek 在复杂序列上跟不动"末次建立被谁全员目击" → 失败;Starling co-witness 交集确定性算对。
- **出口:** 跑 Starling-in-loop vs baseline,配对检验。**这是 lower-confidence bet,不许诺升幅** —— 若 deepseek 能从故事读出 public/private 则 ≈ baseline(像 surface 算子),实测定夺。

## 6. 错误处理 / 边界

- 空 group / theme 从未感知 / 无 co-witness 交集 → `is_ck=false`(优雅退化,server 静默)。
- 单成员 group(|G|=1)→ co-witness 退化为该成员自身感知(CK 对单人 = 其知道)→ is_ck = 该成员见过最新事件。
- theme 多维(content/location):沿用 chain 的 `dim_for_theme` 选维。

## 7. 测试(TDD,ctest)

`tests/cpp/test_mentalizing_common_knowledge.cpp`,复用 perception fixture(seed_event 直插,无 API):
- **public → CK:** A/B/C 全员在场,X 移到 L → `is_ck=true, ck_value=L`。
- **private tell → not CK:** X 公共在 L1,后 D 私下告诉 A "在 L2" → 对 {A,B,C} `is_ck=false`(A 分化)。
- **subset move → not CK:** A 先离场,B/C 见 X 移到 L2 → 对 {A,B,C} `is_ck=false`(A 没见)。
- **非-G 私动不破 G 内 CK:** X 公共在 L1(A/B/C 见),后非-G 的 D 私下移到 L2 → 对 {A,B,C} `is_ck=true, ck_value=L1`。
- **|G|=1 退化。**

## 8. 硬约束

核心逻辑全 C++(`mentalizing_common_knowledge.cpp`);抽取零改动;绑定(`bind_08_tom.cpp` 加 `is_common_knowledge` def,同 chain/shared_with 模式)+ server 瘦转发。复用 perception_state / 交集逻辑 / dim_for_theme,不另起炉灶。不破既有钉测(canonicalize/perception/六态/冲突/grounding/chain/shared_with)。perceived_for_theme 不可变。TDD 先红后绿。explicit-path git add;改 C++/绑定后 `--python-editable`;构建 repo 根;不推/合 main/登记 roadmap/烧 API(评测)需显式 consent。

**诚实定调:** 这是 lower-confidence bet。共同知识的计算是确定的、复用干净;但**增益取决于 deepseek 是否真在复杂 public/private 序列上失败**——若它能读出,则像 surface 算子 ≈ baseline。出口=构造评测实测,不预先许诺升幅。
