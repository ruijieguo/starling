# 确定性多阶信念查询注入 (Deterministic Multi-Order Belief Query Injection) — 设计

> sub-project #3,HiToM 评测优化序列的核心杠杆。承接 #1(dump 修复:perception 进 dump)+ #2-dump(聚焦脚手架)已收口的 in-loop 评测,直击 order 3-4 瓶颈。

## 1. 动机 (Motivation)

100 题 HiToM in-loop 实测(dump 修复后,卡死修复后)定位了瓶颈,数据如下:

| order | fallback 率 | 含义 |
|---|---|---|
| 0 | 0/17 (0%) | 浅题,模型轻松收敛 |
| 1 | 0/18 (0%) | 同上 |
| 2 | 3/28 (11%) | dump 一阶信念帮上忙(net +4 胜) |
| 3 | 7/18 (**39%**) | 嵌套推理烧爆 token |
| 4 | 13/19 (**68%**) | 同上,更严重 |

fallback 随 order 单调上升、order 0-1 为零 → 这**不是** SSL/超时(那会跨 order 随机),而是 **deepseek-v4-pro 在 order 3-4 的嵌套信念上烧光 32768-token 推理预算、返回 `http-200 content=""`**(实测 `lat≈480s`)。

根因诊断:当前 dump 提供的是**一阶**信念(每 cognizer 最后所见),但「A think B think C think the X is」的**嵌套**仍要模型自己递归算 → 推理不收敛。可答题上 dump 修复已给 +9.1%(0.844 vs 0.753),但 order 3-4 因烧爆而拿不到答案。

**核心思路**:让 Starling 用确定性 ToM 引擎**算出**嵌套信念,把答案注入 dump,使 deepseek「读而非推」order 3-4 → 不再烧爆。

## 2. 目标 / 非目标 (Goals / Non-Goals)

**目标**
- C++ 核心新增**任意阶**感知链式查询,泛化现有 order-2 observer 交集到 N 阶。
- 补全 perception_state:HiToM scene-initial 位置(stative)对初始在场 agent 可感知。
- in-loop server 解析 HiToM 问题链 → 查询 → **定论注入**算出的嵌套位置。
- 出口:order 3-4 fallback 率显著下降、可答题准确率上升(实测,不许诺固定升幅)。

**非目标 (YAGNI)**
- **不建模 HiToM 的 lie/trust 变体**(后出场者说谎、信任更晚出场者)——基础「全程见证」模型先行;lie 题靠注入里的对冲提示让 deepseek 据故事覆盖。
- 不碰 ToMBench 路径(in-loop ToMBench 0.827 已稳;链式注入仅 gated 在匹配「A think B think … the X is」的 HiToM 问题上)。
- 不改 canonicalize、不动 order-1/2 既有 `what_does_X_think`(链式是**加性**新函数)。

## 3. 已锁决策 (Locked Decisions)

| # | 决策 | 选择 |
|---|---|---|
| D1 | 范围 | **完整修复**:链式查询(C++)+ #2-reconstructor(初始位置)+ server 注入,基础模型 |
| D2 | #2 初始位置 perception 落点 | **抽取侧**:episodic 抽取捕获 stative 为 location 事件,复用 reconstructor witness 逻辑(不改 reconstructor) |
| D3 | 注入策略 | **定论注入**:dump 明给 Starling 算出的嵌套答案 + 极简 per-cognizer 轨迹 + lie 对冲提示 |
| D4 | 链式查询语义 | **交集泛化**:`cN` 在「所有链成员都感知的事件」中 position 最高的状态(见 §5,可证为 HiToM 结构的正确递归,且阶内顺序无关) |

## 4. 架构 (Architecture) — 3 组件跨边界

```
story
  └─ remember()  [belief → episodic → general-fact passes]
        episodic pass 现产「初始位置」事件 (组件①)
  └─ PerceptionReconstructor  [现有 witness 逻辑,不改]
        → 完整 perception_state(初始位置 + 各 move)
  └─ server: 解析问题链 → what_does_X_think_chain (组件②, C++核心)
        → 注入定论位置 (组件③, Python评测)
  └─ deepseek 读定论 → \boxed{匹配选项字母}
```

| 组件 | 落点 | 边界归属 |
|---|---|---|
| ① #2 抽取完整性 | `python/starling/extractor/episodic_prompt.py`(prompt 数据)+ 复用 `src/cognizer/perception_reconstructor.cpp`(不改) | prompt=配置数据(Python);witness 逻辑=核心(C++,已存在) |
| ② 任意阶链式查询 | `src/tom/`(新增 fn)+ `include/starling/tom/mentalizing.hpp`(声明)+ `bindings/python/bind_08_tom.cpp`(绑定)+ `python/starling/tom/primitives.py`(瘦包装) | **核心 ToM 逻辑 = C++**;绑定/包装=瘦转发 |
| ③ server 注入 + 重命名 | `scripts/starling_tombench_server.py` → **`git mv` → `starling_tomeval_server.py`** | 评测适配(Python) |

## 5. 组件② 任意阶链式查询 (C++ 核心)

### 5.1 语义 (Semantics)

现有 order-2(`mentalizing_think.cpp:42-53`):"observer thinks x thinks" = 取 `x` 的感知行中、`source_event_id` 也在 `observer` 感知事件集里的、position 最高的状态。

**泛化到链 `[c1, c2, …, cN]`**(问题「c1 think c2 think … cN think the theme is」,最深 `cN` 是信念持有者,`c1..c_{N-1}` 是层层 observer):

```
holder    = cN                       # 最深 = 信念持有者
observers = [c1 … c_{N-1}]
h_rows    = perceived_for_theme(holder, theme)        # 按 position 升序
obs_sets  = [ { r.source_event_id for r in perceived_for_theme(oi, theme) }
              for oi in observers ]
# 取 h_rows 中 state_dim==dim、且 source_event_id ∈ 每个 obs_set 的、position 最高的行
for row in reversed(h_rows):
    if row.state_dim == dim and all(row.source_event_id in S for S in obs_sets):
        return row.state_value
return has_belief=false
```

- N=1:`observers` 空 → 退化为 `last_known(holder, theme)`(一阶)。
- N=2:等价现有 observer 逻辑。
- N≥3:多 observer 交集。

**正确性**(HiToM 结构:共同进入 seq 1、各自单次顺序离开、move 发生于在场期间):每个 agent 感知的事件 = position ≤ 其离开时刻的事件;`∩(c1..cN)` = position ≤ `min(离开时刻)` 的事件;`cN` 在其中 position 最高的状态 = 最早离开的链成员离场时的物体位置 = 标准嵌套 ToM 递归结果。交集可交换 → **阶内顺序无关**(只取决于链的成员集合 + 谁是最深持有者)。

**环/深度安全**:链长由问题决定(HiToM 最深 order 4 → 链长 4);上限对齐 `limiting.hpp:kChainMax`(超限截断或返回 has_belief=false)。

### 5.2 接口 (Interface)

`include/starling/tom/mentalizing.hpp`(在 `what_does_X_think` 声明 `:166-173` 之后新增):

```cpp
// 9. 任意多阶感知 ToM:chain=[c1..cN],"c1 think c2 think … cN think theme is where"。
//    holder=cN,observers=c1..c_{N-1}。返回 holder 在「所有链成员都感知过的事件」中
//    最后(position 最高)感知的状态。N=1 等价一阶 what_does_X_think;N=2 等价其
//    observer 分支。空链 / dim 不可定 / 无交集行 → has_belief=false。
StateBelief what_does_X_think_chain(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    const std::vector<std::string>& chain,   // 表层名,内部各自 resolve_cognizer
    std::string_view theme,
    std::string_view tenant,
    std::string_view as_of);
```

- 复用 `StateBelief`(`mentalizing.hpp:156-162`)。
- 复用 `PerceptionStateStore::{perceived_for_theme, last_known, dim_for_theme, latest_actual}`、`normalize_theme`、`resolve_cognizer`(查询侧 lookup-only,镜像 `mentalizing_think.cpp:24-33`)。
- `is_stale` 同一阶口径(`latest_actual` 对比)。
- 落点:新增 `src/tom/mentalizing_chain.cpp`(单一职责),进 `starling_core`;或紧邻扩 `mentalizing_think.cpp`。**`what_does_X_think` 本体不动**(保 order-1/2 钉测绿)。

### 5.3 绑定 (Binding)
- `bindings/python/bind_08_tom.cpp`:镜像 `what_does_X_think` 的 `.def`,加 `what_does_X_think_chain`(`chain` 收 `std::vector<std::string>`)。
- `python/starling/tom/primitives.py`:加瘦包装(转发到 `_core`),与现有 `what_does_X_think` 同形。

## 6. 组件① #2 抽取完整性 (extraction-side)

`python/starling/extractor/episodic_prompt.py`:扩规则 + worked example,把 scene-initial 纯 stative「X is in Y」(无动作主语)捕获为 **location 事件**:`{theme: X(归一), location: Y, participants: []}`,定位于首个 move 事件**之前**(按 story seq 自然落位)。

下游(不改):`PerceptionReconstructor`(`perception_reconstructor.cpp:147-199`)的物理位置分支(`:193`)对该事件计算 `witnesses = present ∪ evp`;`evp` 空 → `witnesses = present`(初始时刻 = 全 cast)→ 给**所有初始在场 agent** 写 `perception_state(theme, location, Y, source_event=该事件)`。

**正确性自证**:Noah/Emma 进场 → 见初始 Y;Noah 早离 → 不见后续 move → perception 停在 Y;Emma move 后 → perception 更新。链式查询遂可对「只见初始就离开」的 agent 返回初始位置(此前 `has_belief=false` 的根因)。

**双通道无冲突**:同一句「X is in Y」原本就被 belief pass 抽为 `located_at`-believes 语句(供 dump 的位置轨迹,不变);#2 让 episodic pass **另**抽一条 location 事件(供 reconstructor 建 perception)。二者服务不同用途、各自落表,不去重、不互扰。

**风险与守卫**:共享 episodic prompt 改动可能动既有 episodic 抽取钉测。守卫:① 只对纯 stative-定位(`see X in Y` 走 content 维的路由不变,见完整性里程碑裁定)② TDD stub-LLM 钉测先确认新例不回归既有 enter/move/exit/leave 抽取 ③ 全量 ctest/pytest 出口绿。

## 7. 组件③ server 注入 + 重命名 (Python 评测)

`scripts/starling_tombench_server.py` → **`git mv` → `scripts/starling_tomeval_server.py`**(基准中立:服务 ToMEval harness 抛来的 ToMBench/HiToM);同步改 uvicorn 启动引用 `scripts.starling_tomeval_server:app`、docstring、内存笔记。cfg 只引端口,无需改。

新增逻辑(在 `_memory_dump` / `_answer` 链路):
1. **问题链解析**(意图级;确切正则由 server pytest 钉死):从「Where does … the … is?」里取「does」与「the … is」之间的跨度,按 `thinks?` 边界(robust 处理首个「think」+ 其余「thinks」混用)切出 cognizer 序列 `chain=[c1..cN]`,theme = 「the」与「is」之间的名词。**仅当 `len(chain) >= 2`(真有嵌套)才触发链注入**;order 0-1 的「X really think」单 cognizer(及 ToMBench、不匹配句)→ 跳过,用现有 dump 脚手架(order 0-1 实测 0% fallback,无需)。
2. **查询**:`what_does_X_think_chain(chain, theme, as_of=<高哨兵,涵盖全部事件>)` → `StateBelief`(单次 remember,全事件 observed_at ≤ now,as_of 取 `"9999-..."` 类上界)。
3. **定论注入**(`has_belief=true` 时):
   ```
   Starling's deterministic ToM engine computed the answer to this exact nested-belief
   question:  <c1> thinks <c2> thinks … <cN> thinks the <theme> is in: <state_value>
   (Basis — each character's last directly-observed <theme> location: <极简 per-cognizer 轨迹>)
   Use this as the primary answer. If the story explicitly shows a character lied about
   the location, adjust accordingly.
   ```
   deepseek 把 `state_value`(位置名)匹配到选项字母输出 `\boxed{X}`。
4. **退化**:`has_belief=false` → 回落现有 dump,不注入定论。绝不破坏作答。

## 8. 错误处理 / 退化 (Error Handling)
- 链式查询返回 `has_belief=false`(perception 不全 / dim 不可定)→ 不注入定论,用现有 dump 脚手架。
- 问题不匹配链式模式 → 不注入。
- cognizer/theme resolve 失败 → 查询侧 lookup-only 原样透传(可能 has_belief=false)→ 退化。
- lie / 多场景题 → 算基础模型答案 + 对冲提示让 deepseek 据故事覆盖。
- best-effort:任何异常都不 fail 请求(沿用 server 既有 `contextlib.suppress` / try 退化)。

## 9. 测试 (Testing, TDD)

**C++ 链式查询 ctest**(`tests/cpp/`,构造 perception_state,确定性):
- order-1 退化:`chain=[c1]` == `what_does_X_think(c1)`(回归)。
- order-2 等价:`chain=[c1,c2]` == `what_does_X_think(c2, observer=c1)`(回归)。
- order-3 早离:c1,c2,c3 进场见初始 A;c3 离场;c2 move 到 B;`chain=[c1,c2,c3]` → A(c3 只见初始)。
- order-3 全程:三人全程在场过 move;`chain=[c1,c2,c3]` → B。
- order-4 链。
- 空链 / 未知 cognizer / theme 无感知 → `has_belief=false`。

**#2 抽取 ctest/pytest**(stub-LLM):「X is in Y」→ episodic location 事件 → `perception_state` 含所有初始在场 agent @ Y;既有 enter/move/exit/leave 抽取不回归。

**round-trip pytest**(stub-LLM):HiToM 式 story → `remember` → `what_does_X_think_chain` → 正确嵌套位置(早离→初始;全程→move 后)。

**server pytest**:问题链正则解析单测(order 1/3/4 phrasings + 不匹配的「really think」/ToMBench)+ 注入格式快照。

**出口**:全量 `ctest`/`pytest` 绿(链式加性、`what_does_X_think` 不动 → order-1/2 与既有 ToM/B 感知/A 情景/六态/冲突/grounding 钉测全绿);canonicalize parity 绿;`perceived_by_json` 不变。

## 10. 约束 (Constraints,注入实施)
- 核心 ToM 逻辑全 C++(`src/tom/`);绑定/包装瘦转发;问题解析+注入=Python 评测;#2=prompt 数据 + 复用 C++ reconstructor。
- **不改 `canonicalize_*`、`what_does_X_think` 本体、`perceived_by_json`**。
- normalize_theme 只对 entity/str-kind(承 M8)。cognizer 查询侧 lookup-only(不注册,best-effort 透传)。
- TDD 先红后绿;构建 repo 根 `configure_build.py --build`,改 C++/绑定后 `--python-editable` 重建 + `cmake --install` 刷可编辑 `_core.so`;ctest 用 `.venv/bin/ctest`。
- explicit-path `git add`(绝不 `.`/`-A`);commit 尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`;无 `--no-verify`/`--amend`;不推 main、不合 main、不登记 roadmap(需用户显式 consent)。

## 11. 成功标准 / 测量 (Success Criteria)
- **首要**:order 3-4 fallback 率显著下降(当前 39%/68%;定论注入后嵌套不再要模型推理 → 预期大降)。
- **次要**:in-loop HiToM 可答题准确率上升(基线 dump 修复后 0.844)、整体 lift 提升。
- **测量**:重跑 100/300 样本 HiToM(快失败预算已稳,不再卡死),同 id 匹配对比基线 0.738 + dump-修复 Starling,per-order 看 order 3-4。**不许诺固定升幅**;设计/实现阶段不烧 API,出口按需重跑。
