# 共同知识算子 `is_common_knowledge` 设计

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

核心逻辑全 C++(`mentalizing_common_knowledge.cpp`);抽取零改动;绑定(`bind_08_tom.cpp` 加 `is_common_knowledge` def,同 chain/shared_with 模式)+ server 瘦转发。复用 perception_state / 交集逻辑 / dim_for_theme,不另起炉灶。不破既有钉测(canonicalize/perception/六态/冲突/grounding/chain/shared_with)。perceived_for_theme 不可变。TDD 先红后绿。explicit-path git add;commit 尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`;改 C++/绑定后 `--python-editable`;构建 repo 根;不推/合 main/登记 roadmap/烧 API(评测)需显式 consent。

**诚实定调:** 这是 lower-confidence bet。共同知识的计算是确定的、复用干净;但**增益取决于 deepseek 是否真在复杂 public/private 序列上失败**——若它能读出,则像 surface 算子 ≈ baseline。出口=构造评测实测,不预先许诺升幅。
