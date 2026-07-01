# Faux-Pas 检测算子 (detect_faux_pas) — 设计 (SP-B)

> 「per-family 确定性社会认知计算算子」arc 的第一个算子。承接 SP-A 教训:surface 心智态 ≈ baseline(deepseek 能从故事读);增益在 COMPUTE deepseek 系统性失败/跟丢的东西(#3 链查询 COMPUTE 嵌套信念 +4.4)。

## 0. 修订 (Amendment 2026-06-24) — 改走 per-event 感知

实施中 Task 3 round-trip 可行性 gate 揭示:`does_X_know` 的知/不知经 `KnowledgeFrontier.presence_log`,而 presence_log 锚在 **OCCURRED 语句的 engram_ref**,**同一次 `remember()` 抽出的所有事件共享一个 engram**(整段一个 engram)→ 单次 `remember(整故事)`(eval server 的摄入方式)下全员 `NotKnown` → **零候选,注入失效**。而 `perception_state` 是 reconstructor 按 cognizer **per-event** 归属的(单 passage 内已正确排除不在场者)。

**裁定(用户)**:内化 — 算子改走 **per-event 感知**(`what_does_X_think` 的 `is_stale`),不在外围改 server 摄入。faux-pas 的结构 = **不在场者持有过期(stale)的主题状态**(他离场前的旧值,而全局已变),即 false-belief 结构;`what_does_X_think(X,theme).is_stale` 正好刻画它,且 per-event、holder-robust、在自然单 passage 上 fire。**D3、§5.1、§5.2 据此改写(下文)**;§8 ctest 改为 seed perception_state 状态变更而非 frontier/engram 三态。

## 1. 动机 (Motivation)

ToMBench-400 逐家族:Non-Literal Communication(含 Faux pas)83% baseline。faux-pas 题(「故事里有没有人说了不当的话?」)的核心 = **有人在不知道某敏感事实时说话,因为他在该事实确立时不在场**。deepseek 在多步故事里容易**跟丢「谁在场、谁因此知道/不知道什么」**——而这正是 Starling 的强项:`perception_state` 是 reconstructor 按 cognizer 归属的、per-character、绕开 SP-A 暴露的 holder 坑。

**思路**:核心算子 `detect_faux_pas` 用感知机器算出**无知不对称**(谁不知道某个在场他人知道的事)——faux-pas 的确定性前置条件——注入给 deepseek。

## 2. 目标 / 非目标 (Goals / Non-Goals)

**目标**
- 新核心 C++ 算子 `detect_faux_pas`:从感知派生出 faux-pas 候选(ignorant cognizer + 他不知的事实 + 在场知情者)。
- server 瘦 gated 注入(Non-Literal/faux-pas 题)。
- 出口:重跑 ToMBench Non-Literal 家族,看是否提升。

**非目标 (YAGNI)**
- 不做语义敏感性判断(「那句话是否真伤人」留给 deepseek)——算子只算**结构化前置**(无知不对称)。
- 不做 reconcile_desires / appraise_emotion(后续算子)。
- 不改 canonicalize、perceived_by_json、既有原语本体(加性)、schema。

## 3. 已锁决策 (Locked Decisions)

| # | 决策 | 选择 |
|---|---|---|
| D1 | arc 内定序 | detect_faux_pas 先行(感知派生稳健、复用现有原语、输出干净) |
| D2 | 算子边界 | 核心算**无知不对称前置**(确定性);语义敏感性留 deepseek |
| D3 | 知识机制 | **(修订)** 用 `what_does_X_think(X, theme).is_stale`(per-event 感知,`perception_state`):**ignorant = is_stale**(X 最后感知的状态 ≠ 全局最新 truth = 持过期视图 = 不在场/没看到变更)、**knower = has_belief && !is_stale**(感知到最新 = 在场知情);`!has_belief` = 从未感知该主题 → 跳过(无可作的信念)。`is_stale` 经 `PerceptionStateStore.latest_actual` 比对,per-character、reconstructor 归属、绕 holder 坑,**且单 passage 内 per-event 区分**(原 `does_X_know`/frontier 是 per-passage,单次 remember 失效——见 §0)。 |
| D4 | 注入 | 定论式(「Starling 检测到 faux-pas 前置:X 不知 F」)+ gated |

## 4. 架构 (Architecture) — 核心算子 + 瘦消费方

```
story → remember()(belief/episodic/general-fact;perception_reconstructor 按 cognizer 建 perception_state)
     → detect_faux_pas(adapter, frontier, tenant, as_of)  (核心 C++,新)
         → [FauxPasCandidate{ignorant, theme, state_dim, stale_value, actual_value, who_knows}]
     → server 瘦 gated 注入(Non-Literal 题)→ deepseek 判 faux-pas
```

| 组件 | 落点 | 边界 |
|---|---|---|
| ① `detect_faux_pas` | `src/tom/mentalizing_fauxpas.cpp`(新)+ `mentalizing.hpp` 声明 + `bind_08_tom.cpp` + `primitives.py` | **核心 ToM 逻辑=C++**;绑定/包装瘦 |
| ② 瘦消费 | `scripts/starling_tomeval_server.py` | 评测适配,只调用+格式化+gating |

## 5. 组件① `detect_faux_pas` 核心算子 (C++)

### 5.1 接口

`include/starling/tom/mentalizing.hpp`(新增):
```cpp
// (修订) faux-pas 候选:ignorant 对 theme 持过期视图(stale_value),而 who_knows
// 已感知到最新 actual_value。perception-native(无 StatementRow 依赖),便于绑定/格式化,
// 且 stale↔actual 对比正是给 deepseek 的 faux-pas 信号。
struct FauxPasCandidate {
    std::string ignorant;                // 持过期视图的 cognizer(faux-pas 风险方)
    std::string theme;                   // 状态过期的主题
    std::string state_dim;               // "location" | "content"
    std::string stale_value;             // ignorant 仍以为的旧状态
    std::string actual_value;            // 他不知道的当前真值
    std::vector<std::string> who_knows;  // 已感知到 actual_value 的在场他人
};

// 扫 cast × themes:某在场 X 对 theme 持过期视图(is_stale)、而某在场 Y 已知最新 →
// 候选(faux-pas 前置)。知/过期按 what_does_X_think 感知派生(per-event、per-character)。
// 语义敏感性不在此判。
std::vector<FauxPasCandidate> detect_faux_pas(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    std::string_view tenant,
    std::string_view as_of);
```

### 5.2 语义与算法

```
cast   = perception_state 的 distinct cognizer_id(在场者)
themes = perception_state 的 distinct theme_id(被感知的主题)
for T in themes:
    knowers = [], stale = []
    for X in cast:
        sb = what_does_X_think(X, T)          # 一阶,perception_state last_known + is_stale
        if not sb.has_belief: continue        # 从未感知 T → 跳过
        if sb.is_stale: stale.push(X)         # 持过期视图 = faux-pas 风险
        else: knowers.push(X)                 # 已感知最新
    if knowers 非空 and stale 非空:
        actual = knowers[0] 的 sb.state_value  # 当前真值(知情者均一致)
        for X in stale: emit {ignorant=X, theme=T, state_dim=sb.state_dim,
                              stale_value=X 的 sb.state_value, actual_value=actual, who_knows=knowers}
```
- **机制(修订 D3,已核 `mentalizing_think.cpp`)**:`what_does_X_think(X,T).is_stale = (truth != X 的 last_known)`,truth = `PerceptionStateStore.latest_actual`(全 cognizer 最高 position)。所以 **is_stale = 持过期视图 → ignorant**,**!is_stale = 已知最新 → knower**——per-event(单 passage 内区分,因 perception_state 按事件归属)、per-character、绕 holder 坑。**ctest seed perception_state 状态变更钉死「B 离场前感知旧值、A/C 感知新值 → what_does_X_think(B)=stale(ignorant)、A/C=current(knower)」契约**。
- 复用 `what_does_X_think`/`PerceptionStateStore`(`mentalizing_think.cpp`);themes/cast 即 perception_state 的 distinct theme_id/cognizer_id。`frontier` 形参透传给 `what_does_X_think`(其当前忽略,签名稳定留 seam)。
- 落点 `src/tom/mentalizing_fauxpas.cpp`(单一职责,进 starling_core);既有原语本体不动。
- cognizer 查询侧 lookup-only;holder/感知归属复用既有。

### 5.3 绑定
- `bind_08_tom.cpp`:`FauxPasCandidate` POD(`def_readonly`:ignorant/theme/state_dim/stale_value/actual_value/who_knows)+ `detect_faux_pas` `.def`(镜像 `what_does_X_think_chain`,GIL release)。
- `primitives.py`:瘦包装 `detect_faux_pas(adapter, frontier, *, tenant_id='default', as_of=None)`。

## 6. 组件② 瘦 gated 消费方 (server)

`scripts/starling_tomeval_server.py`:
- gating:识别 Non-Literal/faux-pas 题(关键词:inappropriate / faux pas / say something / 不当 / 失礼),其余不注入。
- 调 `_core.detect_faux_pas(mem._rt.adapter, frontier, tenant, as_of)`(需 `mem.tick()` 先巩固,沿用 SP-A 的发现);格式化候选:「Starling 检测到 faux-pas 前置:[X] 不知道 [F 的 subject/predicate/object](当时不在场),而 [who_knows] 知道——若 X 就此说话即失礼。」
- 优先级:chain(belief)> mental_state(K/D/I)> faux_pas(Non-Literal);互斥 gating,各家族走各自路径。空/失败 → 回落现有 dump。
- server 只调用核心 + 格式化 + gating,无社会认知逻辑(内化原则)。

## 7. 错误处理 / 退化
- `detect_faux_pas` 无候选 → 返回空 vector,不抛。
- cognizer/fact 解析失败 → best-effort 透传 / 跳过。
- server 注入异常 → `contextlib.suppress` 回落裸 dump。

## 8. 测试 (Testing, TDD)
- **C++ ctest**(`tests/cpp/test_faux_pas.cpp`,seed perception_state 状态变更):场景——主题 T 在 position 0 旧值(B 感知),position 1 新值(A、C 感知,B 不在场)→ `detect_faux_pas` 产候选 {ignorant=B, theme=T, stale_value=旧, actual_value=新, who_knows⊇{A,C}};无不对称(全员感知最新)→ 空;单人 cast → 空。**此 ctest 钉死过期不对称契约 + 修订 D3 的感知机制**。
- **绑定 smoke**(pytest):`_core.detect_faux_pas` 可调 + POD 字段 + `primitives.detect_faux_pas` 包装。
- **round-trip**(stub-LLM):一段「A 见证结果、B 不在场后说话」的故事 → remember → tick → `detect_faux_pas` 标记 B。
- **server pytest**:gating(faux-pas 题触发、belief/emotion 题不触发)+ 注入格式。
- **出口**:全量 ctest/pytest 绿(纯加性:新算子 + 绑定 + server;canonicalize parity、既有 ToM/belief/六态/冲突/感知/grounding/#3 链/SP-A mental_state 钉测全绿)。

## 9. 约束 (Constraints)
- 核心逻辑全 C++(`src/tom/mentalizing_fauxpas.cpp`);绑定/包装/server 瘦转发。
- 不改 `canonicalize_*`、`does_X_know`/`find_misalignment`/`what_does_X_think*` 本体、`perceived_by_json`、schema/migration(复用现有原语/perception/FactKey,无新表)。
- 感知归属复用 reconstructor(per-character);cognizer 查询侧 lookup-only。
- TDD 先红后绿;构建 repo 根 `configure_build.py --build`,改 C++/绑定后 `--python-editable`(+ 必要 `cmake --install`);ctest 用 `.venv/bin/ctest`。
- explicit-path `git add`;无 `--no-verify`/`--amend`;不推/合 main/登记 roadmap/烧 API(需显式 consent)。

## 10. 成功标准 / 诚实风险 (Success Criteria / Honest Risk)
- **首要**:`detect_faux_pas` 作为核心算子落地(ctest 钉死无知不对称契约)。
- **次要**:重跑 ToMBench(server gated 注入)→ Non-Literal 家族提升,不拖累其它。
- **诚实风险(lower-confidence bet,写明)**:
  1. Non-Literal 已 83%——deepseek 做得还行,room 中等;算子只算前置(语义敏感性 deepseek 判),可能仍 ≈ baseline(像 SP-A)。
  2. **依赖 F 的证据 engram 可见性是 per-character 且正确排除不在场者**(does_X_know 的 NotKnown/Unknowable 区分靠 `perceived_by`/`KnowledgeFrontier`)。若 ToMBench faux-pas 的敏感事实其 engram 对全员可见(perceived_by 未排除不在场者),则不对称算不出 → 无候选。实测前未知该比例(Task 1 核实 perceived_by 行为 + 重测衡量)。
  3. 出口=重测实测,**不许诺固定升幅**;若 ≈ baseline,则进一步印证「单阶 ToMBench deepseek 已强、Starling 增益主要在深嵌套 regime」这一边界结论。设计/实现阶段不烧 API。
