# 认知体过度注册修复:抽取时判定 subject 是否认知体（subject_kind）

**日期**:2026-07-21
**状态**:设计定稿,待 plan
**范围**:缺陷 A（过度注册）。缺陷 B（社会图上线）单列独立 spec,不在本轮。

---

## 背景与问题

dashboard 认知体页显示 334 个「认知体」,其中 328 个孤立(无关系边),名字如
`H800 memory` / `macro4 score` / `ToMBench run time` / `TE 2.14.1` / `._* files` /
`FLA chunk backward kernel` —— 全是技术实体/事实陈述的主语,不是能持有信念的主体,
却都被建成 `kind=human` 认知体。且总数持续增长(233→334),dogfood 摄入在持续污染。

### 根因(已逐行核实)

系统隐含假设「每一条抽取语句的 subject 都是认知体」。实现:

1. `src/extractor/json_parser.cpp:103` `s.subject_kind = "cognizer";` —— **无条件硬编码**。
   LLM 的输出 JSON schema 里**根本没有 subject_kind 字段**,是 C++ 对每条抽取语句
   一律标 cognizer。
2. `src/extractor/extractor.cpp:313` 守卫 `stmt.subject_kind == "cognizer"` 因此**恒为真**,
   从未过滤任何东西。
3. `src/cognizer/name_resolver.cpp:41` `resolve_or_register_cognizer` 把每个没见过的
   subject 表面串注册成新认知体。
4. `src/cognizer/name_resolver.cpp:49` `reg.kind = CognizerKind::Human;` —— **无条件贴 Human**。

三条抽取管线各自触发这条链,**general-fact(gf) 是污染放大器**:它专抽
`Postgres is_a relational database` / `deploy budget has_value $40k` 这类世界事实,
subject 就是技术名词/设备型号/指标名,且与 belief 复用同一个 C++ `extractor::Extractor`
类。episodic 更彻底 —— 对 actor + 每个 participant 无条件注册,连那道(即便永真也算存在的)
守卫都没有(`episodic_extractor.cpp:167`)。

注册**先于** validate、同一事务、FAILED 也 commit(`extractor.cpp:225/313/346`):
即便语句被 validator 拒绝没进 statements 表,subject 也已注册成认知体并提交。

### 为什么启发式救不了

判据只有读句子的 LLM 有。`H800 memory` / `macro4 score` / `ToMBench run time` 不含
任何技术符号,字符串规则无从区分它们与人名;`the server depends_on the database`
是实体-实体,谓词规则也失效。判「是不是认知体」本质是语义理解。

### 关键事实:数据模型早已预留两态,只是抽取层烂尾

- `include/starling/extractor/extracted_statement.hpp:21` `subject_kind` 注释即
  `// "cognizer" | "entity"` —— 两态是设计意图。
- `migrations/0001_initial_schema.sql:23` DB 层第一版就有约束
  `subject_kind TEXT NOT NULL CHECK (subject_kind IN ('cognizer','entity'))`。
- `migrations/0008_cognizer_schema.sql:114` backfill 用 `WHERE s.subject_kind = 'cognizer'`
  才建 cognizers 行。

**基础设施从 schema 到数据模型都为「非 cognizer 的 subject」留好了路,只有抽取代码
从没产出过 `entity`。** 本修复不是加新概念,是补完一个烂尾的两态设计。

---

## 目标与非目标

**目标**
- 抽取时逐句判定 subject 是认知体还是实体,只有认知体才注册进 cognizers 表。
- 认知体的 kind(human/agent/group/role/external)由 LLM 判定,不再焊死 Human。
- 存量 328 条污染认知体一次性 LLM 重分类,entity 标记归档(可逆,不硬删)。
- 抽取质量不回归(belief/gf/tom 三维经 eval 基线验证)。

**非目标(本轮不做)**
- 缺陷 B:社会图上线(cognizer_relations 在线写入 + affinity/power 产生)。单列独立 spec。
- 二阶信念/嵌套 subject 的重构。
- CognizerKind 中 self 的运行时接线(RuntimeConfig.self_cognizer_id 仍是设计文档层)。

---

## 判据(锁定)

**认知体 = 能持有信念的主体。** 涵盖 human / agent / group / role / self / external。

- `Alice`(人名)→ cognizer, kind=human
- `the eng team`(群体)→ cognizer, kind=group
- `Claude` / `the assistant`(AI)→ cognizer, kind=agent
- `Postgres` / `H800 memory`(技术实体)→ entity
- `the deploy budget`(抽象事物)→ entity

---

## 设计

### 数据流(改后)

```
LLM 抽取(每条语句自带 subject_kind[+cognizer_kind])
  → json_parser 读 LLM 的 subject_kind(不再焊死)
  → subject_kind=="cognizer" ? resolve_or_register(kind=LLM 的 cognizer_kind) : 跳过注册,subject_id=实体表面串
  → 落库 statements.subject_kind ∈ {cognizer, entity}(DB CHECK 早已允许)
  → ToM 读路径按 subject_kind='cognizer' 过滤 —— entity 语句自动落选(对齐,非破坏)
```

### 组件 1:三份 prompt 输出 schema 加字段

**belief**(`python/starling/extractor/prompts.py`)与 **gf**
(`python/starling/extractor/general_fact_prompt.py`)—— 二者输出结构相同
(`{holder, subject, predicate, object, ...}`),各加:

- `subject_kind`: `"cognizer" | "entity"` —— 必填。
- `cognizer_kind`: `"human" | "agent" | "group" | "role" | "external"` —— 仅当
  `subject_kind == "cognizer"` 时给,否则省略/null。

prompt 正文加一段判据说明(逐字给,plan 里定稿):
- cognizer = 能持有信念的主体(人/AI agent/组织/角色)。
- entity = 技术实体、产品、抽象事物、指标、数值 —— 任何不能持有信念的东西。
- 给正负例:`Postgres`/`H800 memory`/`deploy budget` → entity;`Alice`/`the eng team`/
  `Claude` → cognizer(分别 human/group/agent)。

**每一个 WORKED EXAMPLE 的输出都要带上新字段**(LLM 极其可靠地复制示例里出现的字段;
示例不带,LLM 就漏)。gf 的示例尤其要示范:`Postgres is_a relational database` →
`subject_kind:"entity"`,`Alice reports_to Bob` → `subject_kind:"cognizer", cognizer_kind:"human"`。

**episodic**(`python/starling/extractor/episodic_prompt.py`)—— 结构不同
(`{actor, action, theme, participants, ...}`),没有 `subject` 字段。等价判断是
「每个 actor/participant 是不是认知体」。设计皱褶:actor/participants 各带一个
认知体标志。方案(plan 定稿):
- actor 加 `actor_kind`: `"cognizer"|"entity"`(+ cognizer 时的 kind);participants
  从 `[str]` 变 `[{name, kind}]` 或并列一个 `participant_kinds`。
- episodic 语义本就假定 actor 是「做动作的人」,故 cognizer 是强先验,但仍要 LLM 判
  (事件里出现 `the script ran` 这类非人 actor 时不误注册)。

### 组件 2:parser 读字段,不再硬编码

`src/extractor/json_parser.cpp:103`:
```cpp
// 改前:s.subject_kind = "cognizer";  // 无条件
// 改后:读 LLM 的 subject_kind,校验值域,非法/缺失 → 安全侧默认 "entity"
```

**fallback = entity(安全侧,锁定)**:LLM 漏输出或输出非 {cognizer,entity} 时,默认
`entity`(不注册)。理由:**过度注册是病,漏注册无害得多** —— 漏一个真认知体,语句
照常存储,只是暂不进社会层;错注册一个 `H800 memory` 就是污染。失败朝「少注册」倒。
**漏输出计一个 parse warning**(不是 error,不杀语句),好在 eval 里量 LLM 漏字段的频率。

`episodic_extractor.cpp:183` 同样从 LLM 读,不再焊死。

### 组件 3:name_resolver 的 kind 从 LLM 来

`src/cognizer/name_resolver.cpp`:`resolve_or_register_cognizer` 增一个 `CognizerKind`
入参(调用方从 LLM 的 `cognizer_kind` 传入):
```cpp
// 改前:reg.kind = CognizerKind::Human;  // 无条件
// 改后:reg.kind = 调用方传入的 kind;缺失时默认 Human
```

**cognizer_kind 缺失默认 human(锁定)**:`subject_kind==cognizer` 但没给 kind 时回退
human(历史行为,多数确实是人)。字符串→枚举用既有 `cognizer_kind_from_string`
(`cognizer_hub.cpp:361`)。

### 组件 4:注册守卫真正生效

`extractor.cpp:313` 的 `if (subject_kind == "cognizer")` 与 `episodic_extractor.cpp:167`
的 resolve 调用 —— 逻辑不变,但现在 subject_kind 有真值,守卫从此有意义。
**entity 的 subject_id = 原样表面串(锁定)**:不注册、不建 cognizers 行,subject_id
就是实体名(DB 早支持 `subject_kind='entity'`)。

### 组件 5:存量 328 条一次性 LLM 重分类

新脚本 `scripts/reclassify_cognizers.py`(手动运维,非 CI):
- 读 cognizers 表全部 name → 分批交 LLM 判 cognizer/entity(+kind)。
- entity 的:标记归档(**可逆,不硬删**)。具体机制 plan 定(加一列 `archived_at`
  或迁到影子表);它们引用的 statements 的 subject_kind 也回改为 entity。
- cognizer 的:若 kind 判得比 human 更准(agent/group),更新 kind。
- **不误杀**:那 6 个有关系边的(seed 种的 Sam/Frank/Alice/Bob/Carol)是真人,重分类
  应保留为 cognizer。
- Clash TUN 不稳 → 脚本可重入、失败换时刻重跑(照既有 eval 脚本惯例)。

### 组件 6:既有测试改动

- `tests/cpp/test_json_parser.cpp` 的 `EXPECT_EQ(s.subject_kind, "cognizer")`
  把硬编码钉死 —— 改为断言「读 LLM 值 + 缺失默认 entity」。
- `test_episodic_extractor.cpp:129/132` 同类。
- 新增负例测试:技术实体 subject(`subject_kind:"entity"`)不触发 cognizer 注册。
  这是既有测试体系从来没有的负例。

---

## 测试策略

### 纯逻辑单测(进 CI,零真 LLM)
- json_parser 读 subject_kind:合法值/缺失/非法值 → 分别得 cognizer/entity(默认)/entity。
- name_resolver:传入各 kind → 落库 kind 正确;entity 不注册。
- parse warning 计数:漏字段时 warning +1,语句不被杀。

### 真机 eval(手动,非 CI,最大风险门)
改抽取 prompt = 改核心语义,可能回归抽取质量。用既有质量基线 harness
(`scripts/eval_quality_baseline.py` + `eval_p1_extractor.py` + `eval_tom_bench.py`):
1. **改前**跑一次基线,记 belief/gf/tom 三维中位数分数。
2. **改后**重跑,确认:三维分数不回归(相对退化在容差内);subject_kind 判准率高
   (新增一个抽样核对:LLM 对已知 cognizer/entity 样例判对率)。
3. Clash 黑洞换时刻重跑。
**这是不能跳的门** —— prompt 改坏了抽取,是比认知体污染更严重的回归。

---

## 分阶段(plan 细化)

1. **纯逻辑先行**:parser 读字段 + name_resolver kind 入参 + 守卫 + 负例单测(TDD,零真 LLM,进 CI 门)。
   —— C++ 内核改动,可先于 prompt 落地(parser 有安全默认,即便 prompt 没改也不崩,只是全走 entity 默认)。
2. **三份 prompt 加字段 + worked example**:belief/gf/episodic schema + 判据说明 + 正负例。
3. **eval 门**:改前基线 → 改后重跑 → 三维不回归 + subject_kind 判准。
4. **存量重分类脚本**:reclassify_cognizers.py + 归档机制 + 真机跑一次。

---

## 风险与开放取舍(交 plan-eng-review)

1. **eval 回归**(最大):prompt 加字段可能干扰 LLM 对 subject/predicate 本身的抽取。
   缓解:字段加在末尾、worked example 完整示范、eval 三维守门。
2. **episodic schema 皱褶**:participants 从 `[str]` 变结构化,改动面比 belief/gf 大;
   要不要 episodic 本轮就上、还是 episodic 单独一步 —— plan 权衡。
3. **fallback=entity 的召回损失**:若 LLM 漏字段频繁,大量真认知体被默认成 entity。
   缓解:parse warning 计数 + eval 量漏字段率;worked example 压低漏字段概率。
4. **存量归档的可逆性**:archived_at 列 vs 影子表 —— 哪种更不破坏既有查询/ToM。
5. **ToM 读/写路径要分清**(自审已核实,plan 必须区分,别误改写路径):
   - **读路径过滤**:`mentalizing_know.cpp:39/84` 有真 `WHERE subject_kind=?3`;
     `mentalizing_believe.cpp:26` 用 `StatementFilter.subject_kind="cognizer"`。
     改后 entity 语句从这些查询落选是**期望行为**(H800 memory 不该进信念追踪),非回归。
   - **写路径硬编码**:`second_order.cpp:140` `st.subject_kind="cognizer"` 是二阶信念
     **写**语句(subject 是认知体 partner,天然 cognizer),**应保留硬编码,不要动**。
     plan 执行者容易把它误当成「又一处该改的硬编码」—— 明确排除。

---

## 全局约束(copy verbatim,plan 每个任务隐含继承)

- 核心语义(判据、注册策略)在 C++ 内核(src/ + include/);prompt 是配置数据单一源
  (python/starling/extractor/),绑定层只转发。
- 枚举值 DB/序列化一律小写,C++ to_string + Python enum + DB CHECK 三处一致。
- 单写者 SQLite;写后/订阅者路径 SAVEPOINT 不用 BEGIN。
- 改 C++/绑定/migration 后必须 `python scripts/configure_build.py --build --python-editable`
  重装 _core;pytest 一律 `.venv/bin/python -m pytest tests/python`。
- 提交门:全量 ctest + pytest 绿;dashboard 前端 npm run check / vitest / build。
- git 显式路径 add(禁 . / -A);不用 --no-verify / --amend;commit 尾
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
- 不打印/提交 API key(从环境读)。
- eval(真 LLM)不进 CI(Clash TUN 不可靠);纯逻辑 fixture 单测进 CI。
- NEVER merge:PR + CI 绿 + 用户明确合并。
