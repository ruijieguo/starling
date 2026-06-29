# BDI+K 心智态内化 (Mental-State Internalization) — 设计 (SP-A)

> 「把多维社会认知能力内化进 Starling 核心」arc 的第一个子项目。承接 ToMBench 逐家族 gap 分析:Starling 只有 belief 接通了「抽取→查询→注入」三层,Knowledge/Desire/Intention 家族表征底座在、管线没通。

## 1. 动机 (Motivation)

ToMBench 实测(400 样本,Starling-in-loop vs 裸 deepseek):整体 ≈ baseline(81.2 vs 82.5),仅 **Belief 家族 +0.8**;**Knowledge −4.4 / Desire −3.6 / Intention −2.4**。根因不是 Starling 不能表征这些心智态——modality 菜单已含 `BELIEVES/DESIRES/INTENDS/COMMITS`,原语 `what_does_X_believe`/`does_X_know`/`predict_X_would` 俱在——而是**两处管线断裂**:
1. **抽取偏 belief**:`prompts.py` 的 modality 菜单列了 `DESIRES/INTENDS/COMMITS`,但 worked example 几乎全 `believes`/`prefers` → LLM 非信念心智态**抽取率低**。
2. **无聚合查询面**:没有一个「X 的完整心智态」核心能力把已抽的 beliefs/knowledge/desires/intentions/commitments 一次性吐给消费方;Belief 之外的家族拿不到 X 的相关心智内容。

**内化原则(用户裁定)**:能力做进核心(C++),开箱即用;评测 server / OpenClaw / 未来绑定只是瘦消费方,不在外围重实现。

## 2. 目标 / 非目标 (Goals / Non-Goals)

**目标**
- 抽取可靠捕获 **BDI+K**(beliefs / desires / intentions / commitments / knowledge / preferences),不止 beliefs。
- 新增**核心 C++ 聚合** `mental_state_of(X)`:一次调用返回 X 的全部心智态,按 attitude 分组。开箱即用(ToMEval、OpenClaw、未来绑定共享)。
- 瘦消费方(eval server)按家族 gated 注入 `mental_state_of`,验证 Knowledge/Desire/Intention 家族提升。

**非目标 (YAGNI)**
- 不做 `reconcile_desires`(欲望调和)、`detect_faux_pas`(SP-B)、`appraise_emotion`(SP-C)——本 SP 只铺**抽取地基 + 心智态聚合面**。
- 不在 server 写社会认知逻辑(faux-pas/路由/调和)——那违反内化原则。
- 不改 `what_does_X_think`/`what_does_X_believe`/`does_X_know` 本体(加性);不改 canonicalize、perceived_by_json、schema(复用现有 modality/predicate/StatementRow)。

## 3. 已锁决策 (Locked Decisions)

| # | 决策 | 选择 |
|---|---|---|
| D1 | arc 定序 | SP-A 抽取地基先行(B faux-pas / C emotion-appraisal 顺延) |
| D2 | 内化形态 | `mental_state_of` 是**核心 C++ 聚合原语**(`src/tom/`),非 server 路由 |
| D3 | 抽取增强 | prompt 加 DESIRES/INTENDS/knows/prefers worked example(配置数据,加性);抽取机器不改(已支持全 modality) |
| D4 | 消费方 | server 瘦调用 + 按家族 gated 注入(只对 Knowledge/Desire/Intention,不对 emotion/belief-only) |

## 4. 架构 (Architecture) — 两个内化件 + 一个瘦消费方

```
story
 └─ remember() [belief/episodic/general-fact passes]
      belief pass 现可靠抽 BDI+K (组件①,prompt 增强)
 └─ mental_state_of(X)  (组件②,核心 C++ 聚合,新)
      → {beliefs, knowledge, desires, intentions, commitments, preferences}
 └─ server 瘦注入(组件③,gated to Knowledge/Desire/Intention)
      → answerer 读 X 的心智态作答
```

| 组件 | 落点 | 边界 |
|---|---|---|
| ① 抽取增强 | `python/starling/extractor/prompts.py`(配置数据) | prompt=数据;抽取机器=C++(不改) |
| ② `mental_state_of` | `src/tom/mentalizing_profile.cpp`(新)+ `include/starling/tom/mentalizing.hpp`(声明)+ `bindings/python/bind_08_tom.cpp` + `python/starling/tom/primitives.py` | **核心 ToM 逻辑=C++**;绑定/包装瘦转发 |
| ③ 瘦消费 | `scripts/starling_tomeval_server.py` | 评测适配(Python),只调用+格式化 |

## 5. 组件② `mental_state_of(X)` 核心聚合 (C++)

### 5.1 接口

`include/starling/tom/mentalizing.hpp`(在既有结构体附近新增):
```cpp
// X 的完整心智态快照:按 attitude(BDI + 知识/偏好)分组 X 持有(holder_id=x)
// 的语句,observed_at <= as_of。开箱即用的「X 心里有什么」聚合。
struct MentalState {
    std::vector<retrieval::StatementRow> beliefs;       // modality BELIEVES
    std::vector<retrieval::StatementRow> knowledge;     // modality KNOWS 或 predicate='knows'
    std::vector<retrieval::StatementRow> desires;       // modality DESIRES
    std::vector<retrieval::StatementRow> intentions;    // modality INTENDS
    std::vector<retrieval::StatementRow> commitments;   // modality COMMITS
    std::vector<retrieval::StatementRow> preferences;   // predicate='prefers'
};

MentalState mental_state_of(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view tenant,
    std::string_view as_of);
```

### 5.2 语义与分组

- 单次查询 `statements WHERE tenant_id=? AND holder_id=x AND observed_at<=as_of`(复用既有 StatementRow 列;不另查)。
- 按 (modality, predicate) 分桶。**确切的 stored modality 字符串大小写由 ctest 钉死**——ctest 用真实 stored 值 seed(参 `test_mentalizing_think.cpp` 的 seed_helper:stored modality 形如 `'occurred'` 小写),实现匹配该契约。已知映射意图:
  - `modality` ∈ {believes→beliefs, desires→desires, intends→intentions, commits→commitments}
  - `predicate='knows'`(或 modality=knows)→ knowledge
  - `predicate='prefers'` → preferences
- 分桶优先级(一条语句**恰好一个**桶):**先按 predicate**——`prefers`→preferences、`knows`→knowledge;**其余按 modality**——believes→beliefs、desires→desires、intends→intentions、commits→commitments。OCCURRED / NORM_* / ENFORCES / OBSERVES 不入任何桶(非 X 的命题态度)。predicate 优先解决「modality=BELIEVES 且 predicate=prefers」的归属歧义。
- 排序:每桶按 observed_at(或 rowid)升序(可读时间线)。
- 复用 holder 隔离(P3.a1 多 holder 隔离已有):只取 holder_id=x 的语句 → 是 X 自己的心智态,不混他人。
- 落点 `src/tom/mentalizing_profile.cpp`(单一职责,进 starling_core);`what_does_X_*` 本体不动。

### 5.3 绑定
- `bindings/python/bind_08_tom.cpp`:`MentalState` POD(`def_readonly` 6 字段)+ `mental_state_of` `.def`(镜像 `what_does_X_believe`,GIL release 围查询)。
- `python/starling/tom/primitives.py`:瘦包装 `mental_state_of(adapter, *, x, tenant_id='default', as_of=None)`(`_iso_now_or_convert`)。

## 6. 组件① 抽取增强 (extraction-side)

`python/starling/extractor/prompts.py`:在既有 worked example 后**加性**补 DESIRES/INTENDS/knows/prefers 的示例(belief 示例不动)。

**关键:desires/intentions 由 `modality`(DESIRES/INTENDS)承载** —— 现有 predicate 词表(responsible_for/knows/prefers/promises/forbids/requires/located_at/member_of/believes/doubts)**没有干净的「想要做 X」动词**,所以欲望/意图语句用最接近的 predicate,真正的信号是 modality。`mental_state_of` 的 desires/intentions 桶**按 modality 分(predicate-agnostic)**,故分桶对 predicate 不敏感、稳健。

确切示例:
- **INTENDS**(predicate 干净):`"Mei: I'm going to finish the report tonight"` → `{holder:"Mei", subject:"Mei", predicate:"responsible_for", object:"report", modality:"INTENDS", ...}`。
- **DESIRES**(predicate 取最近似):`"Li Hua: I want to spend the weekend outdoors"` → `{holder:"Li Hua", subject:"Li Hua", predicate:"prefers", object:"outdoors", modality:"DESIRES", ...}`(prefers 作最近似;modality=DESIRES 是分桶信号)。
- **KNOWS**:`"Tom: I know the keys are in the drawer"` → `predicate:"knows"`(抽取 prompt 当前把 `knows` 列为 predicate;knowledge 桶据此 `predicate='knows'`)。
- 守卫:示例须与既有 OBJECT BREVITY / HOLDER vs SUBJECT 规则一致;不引入与 belief 示例冲突的 holder/subject 归属。

**plan 评估点(非本 spec 强制)**:是否给 predicate 词表加 `wants`(prompt 配置数据 + general-fact predicate constexpr 类,**非 schema**)以让欲望对象更自然。若加,desires 桶仍按 modality 分,向后兼容。

> 注:抽取增强的真实效果(LLM 是否可靠产出这些 modality)由**真模型重测**衡量;stub-LLM 钉测只锁「给定这些 modality 的语句,mental_state_of 正确分组」的下游契约。

## 7. 组件③ 瘦消费方 + dump-gating (server)

`scripts/starling_tomeval_server.py`:
- 问题分类(轻量,意图级):识别 Knowledge / Desire / Intention 类问题(关键词/句式),对这些题在 dump 注入相关角色的 `mental_state_of`(beliefs/knowledge/desires/intentions/preferences 的紧凑文本)。
- **dump-gating**:belief-only / emotion / non-literal 题**不注入** mental_state(避免上轮发现的「无关 dump 噪声拖累非目标家族」)。
- 失败/空 → 回落现有 dump。绝不破坏作答。
- server 只**调用核心 `mental_state_of` + 格式化**,无社会认知逻辑(内化原则)。

## 8. 错误处理 / 退化
- `mental_state_of` 空(X 无语句 / 未知 cognizer)→ 返回空 MentalState(各桶空向量),不抛。
- cognizer 查询侧 lookup-only best-effort(镜像现有 ToM 查询);未知 surface 透传。
- server 注入异常 → `contextlib.suppress` 回落裸 dump(沿用既有 best-effort)。

## 9. 测试 (Testing, TDD)
- **C++ ctest**(`tests/cpp/test_mental_state.cpp`,直接 seed statements):seed X 持有 believes/knows/desires/intends/commits/prefers 各一 + 他人语句 + OCCURRED → `mental_state_of(X)` 各桶恰含对应行、不含他人/OCCURRED;未知 X → 全空;as_of 早于某语句 → 该语句不入桶。**此测试钉死 modality/predicate→桶 的确切 stored 值契约**。
- **绑定 smoke**(pytest):`_core.mental_state_of` 可调 + `primitives.mental_state_of` 包装存在。
- **round-trip**(stub-LLM,pytest):一段含 desire+intention+knowledge 的对话 → `remember` → `mental_state_of` 各桶非空且归类正确。
- **抽取回归**:既有 belief/extractor 钉测不变(prompt 加性)。
- **出口**:全量 ctest/pytest 绿(纯加性:新 `mental_state_of` + 新 prompt 例 + 绑定 + server 注入;canonicalize parity、既有 ToM/belief/六态/冲突/感知/grounding/#3 链 钉测全绿)。

## 10. 约束 (Constraints)
- 核心 ToM 逻辑全 C++(`src/tom/mentalizing_profile.cpp`);抽取 prompt=配置数据;绑定/包装/server 瘦转发。
- 不改 `canonicalize_*`、`what_does_X_think`/`what_does_X_believe`/`does_X_know` 本体、`perceived_by_json`、schema/migration(复用现有 modality/predicate/StatementRow)。
- cognizer 查询侧 lookup-only;holder 隔离复用 P3.a1。
- TDD 先红后绿;构建 repo 根 `configure_build.py --build`,改 C++/绑定后 `--python-editable`(+ 必要 `cmake --install`);ctest 用 `.venv/bin/ctest`。
- explicit-path `git add`;无 `--no-verify`/`--amend`;不推/合 main/登记 roadmap(需显式 consent)。

## 11. 成功标准 / 测量 (Success Criteria)
- **首要**:`mental_state_of` 作为开箱即用核心能力落地(ctest 钉死分组契约)+ 抽取可靠捕获 BDI+K。
- **次要**:重跑 ToMBench(server gated 注入 mental_state)→ Knowledge/Desire/Intention 家族相对当前(−4.4/−3.6/−2.4)回升,不拖累其它家族(gating)。**不许诺固定升幅**;出口按需重跑(设计/实现阶段不烧 API)。
