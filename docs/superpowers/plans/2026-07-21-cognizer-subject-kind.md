# 认知体过度注册修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 抽取时逐句判定 subject 是认知体还是实体(subject_kind),只有认知体才注册进
cognizers 表,kind 由 LLM 判定不再焊死 Human;存量污染一次性重分类归档。

**Architecture:** 判据由 LLM 逐句输出(补完 schema/DB 早已预留的两态字段),C++ parser 读它
不再硬编码,注册守卫真正生效。核心语义在 C++ 内核 + prompt(单一源);fallback=entity(安全侧)。

**Tech Stack:** C++20 内核(src/ + include/)、pybind11 绑定、Python host、SQLite、
prompt 配置(python/starling/extractor/)、eval harness(scripts/eval_*.py)。

## Global Constraints

- 核心语义(判据、注册策略)在 C++ 内核;prompt 是配置数据单一源(python/starling/extractor/),绑定层只转发。
- 枚举值 DB/序列化一律小写;C++ to_string + Python enum + DB CHECK 三处一致。
- 单写者 SQLite;写后/订阅者路径 SAVEPOINT 不用 BEGIN。
- 改 C++/绑定/migration 后必须 `python scripts/configure_build.py --build --python-editable` 重装 _core;只 pip install -e . 不够。
- pytest 一律 `.venv/bin/python -m pytest tests/python`;C++ 用 ctest。
- git 显式路径 add(禁 . / -A);不用 --no-verify / --amend;commit 尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
- 不打印/提交 API key(从环境读)。
- eval(真 LLM)不进 CI(Clash TUN 不可靠);纯逻辑 fixture 单测进 CI。
- NEVER merge:PR + CI 绿 + 用户明确合并。
- **判据锁定**:认知体 = 能持有信念的主体(human/agent/group/role/self/external);技术实体/抽象事物 = entity。
- **fallback 锁定**:LLM 漏输出或非法值 → subject_kind 默认 "entity"(不注册);cognizer_kind 缺失 → 默认 human。
- **勿动写路径**:`src/tom/second_order.cpp:140` `st.subject_kind="cognizer"` 是二阶信念写语句(subject 天然是认知体),保留硬编码,不改。

---

### Task 1: json_parser 读 LLM 的 subject_kind(纯逻辑,C++,进 CI)

**Files:**
- Modify: `src/extractor/json_parser.cpp:103`(subject_kind 硬编码 → 读 LLM + 安全默认)
- Modify: `include/starling/extractor/extracted_statement.hpp`(若需加 llm_cognizer_kind advisory 字段,与 llm_holder 并列)
- Test: `tests/cpp/test_json_parser.cpp`

**Interfaces:**
- Consumes: `parse_extractor_json(raw_json, existing_ref_map)` 既有签名不变。
- Produces: `ExtractedStatement.subject_kind ∈ {"cognizer","entity"}`;新增 advisory
  `ExtractedStatement.llm_cognizer_kind`(string,cognizer 时的 kind,空=缺失)。

- [ ] **Step 1: 写失败测试** —— subject_kind 三情形 + cognizer_kind 透传

```cpp
// tests/cpp/test_json_parser.cpp 追加
TEST(JsonParser, ReadsSubjectKindFromLlm) {
    // 合法 entity:不再无条件 cognizer
    auto r = parse_extractor_json(
        R"([{"holder":"self","subject":"Postgres","predicate":"is_a","object":"database","subject_kind":"entity"}])", {});
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].subject_kind, "entity");
}
TEST(JsonParser, DefaultsToEntityWhenSubjectKindMissing) {
    // fallback=entity(安全侧:漏字段宁可不注册)。parser 本就 lenient,
    // 缺失 → 默认 entity,语句照常产出(不 skip、不 error)。
    auto r = parse_extractor_json(
        R"([{"holder":"self","subject":"H800 memory","predicate":"has_value","object":"80GB"}])", {});
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].subject_kind, "entity");
}
TEST(JsonParser, IgnoresInvalidCognizerKind) {
    // cognizer_kind 值域外(如 "robot")→ advisory 置空,由下游回退 human,
    // 绝不让非法串流到 cognizer_kind_from_string(它对未知串 throw)。
    auto r = parse_extractor_json(
        R"([{"holder":"self","subject":"X","predicate":"p","object":"o","subject_kind":"cognizer","cognizer_kind":"robot"}])", {});
    EXPECT_EQ(r.statements[0].subject_kind, "cognizer");
    EXPECT_EQ(r.statements[0].llm_cognizer_kind, "");  // 非法 → 空 → 下游默认 human
}
TEST(JsonParser, DefaultsToEntityOnInvalidValue) {
    auto r = parse_extractor_json(
        R"([{"holder":"self","subject":"x","predicate":"p","object":"o","subject_kind":"garbage"}])", {});
    EXPECT_EQ(r.statements[0].subject_kind, "entity");
}
TEST(JsonParser, CarriesCognizerKindAdvisory) {
    auto r = parse_extractor_json(
        R"([{"holder":"self","subject":"Alice","predicate":"responsible_for","object":"auth","subject_kind":"cognizer","cognizer_kind":"human"}])", {});
    EXPECT_EQ(r.statements[0].subject_kind, "cognizer");
    EXPECT_EQ(r.statements[0].llm_cognizer_kind, "human");
}
```

- [ ] **Step 2: 改既有钉死硬编码的断言**

`tests/cpp/test_json_parser.cpp` 里 `ParsesSemanticCoreAndFillsBookkeeping` 的
`EXPECT_EQ(s.subject_kind, "cognizer")` —— 该样例若没给 subject_kind 字段,按新语义
应为 "entity"。改断言(或给夹具补 subject_kind:"cognizer")。**明确说明改了哪条、为什么**。

- [ ] **Step 3: 运行,确认失败**

Run: `cd build-macos && ctest -R json_parser --output-on-failure`
Expected: 新测试 FAIL(subject_kind 仍恒 cognizer);Step 2 改的断言 FAIL。

- [ ] **Step 4: 实现** —— parser 读字段 + 值域校验 + 安全默认

```cpp
// src/extractor/json_parser.cpp,替换 :103 那行
// 安全侧默认 entity:漏字段/非法值宁可不注册(过度注册是病,漏注册无害)。
// parser 本就 lenient(:26 注释),缺失走默认即可,不新增 warnings 结构。
{
    const std::string sk = to_lower(el.value("subject_kind", std::string()));
    s.subject_kind = (sk == "cognizer" || sk == "entity") ? sk : "entity";  // fallback
}
// cognizer 时读 advisory kind,并【在此校验值域】:cognizer_kind_from_string 对未知串
// throw(cognizer.hpp:117),故非法/缺失一律置空,让下游(Task 3)默认 human,绝不把
// 非法串传下去。entity 时忽略 kind。
{
    static const std::set<std::string> kValidKinds =
        {"self","human","agent","group","role","external"};
    const std::string ck = (s.subject_kind == "cognizer")
        ? to_lower(el.value("cognizer_kind", std::string())) : std::string();
    s.llm_cognizer_kind = kValidKinds.count(ck) ? ck : std::string();
}
```

`llm_cognizer_kind` 加到 `ExtractedStatement`(advisory,与 llm_holder/llm_nesting_depth
同类)。**不新增 warnings 结构** —— parser 既有风格是 lenient 静默默认;漏字段率改到
Task 9 eval 阶段用「抽样跑 + 数 entity 占比异常」来量,而非在 parser 里加计数机制
(YAGNI:除非 eval 显示漏字段是真问题,不预建)。

- [ ] **Step 5: 运行,确认通过**

Run: `cd build-macos && ctest -R json_parser --output-on-failure`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add src/extractor/json_parser.cpp include/starling/extractor/extracted_statement.hpp \
        include/starling/extractor/json_parser.hpp tests/cpp/test_json_parser.cpp
git commit -m "feat(extractor): json_parser 读 LLM subject_kind + cognizer_kind,安全默认 entity"
```

---

### Task 2: name_resolver 的 kind 从调用方传入(纯逻辑,C++,进 CI)

**Files:**
- Modify: `include/starling/cognizer/name_resolver.hpp:14`(签名加 kind 入参)
- Modify: `src/cognizer/name_resolver.cpp:41-56`(kind 用入参,不焊死 Human)
- Test: `tests/cpp/test_name_resolver.cpp`

**Interfaces:**
- Produces: `resolve_or_register_cognizer(hub, tenant, surface, kind = CognizerKind::Human)`
  —— 新增末位默认参数,保持既有调用兼容(Task 4 才传真值)。

- [ ] **Step 1: 写失败测试** —— 传入 kind 落库正确 + 缺省仍 human

```cpp
TEST(NameResolver, RegistersWithGivenKind) {
    // ... 构造 hub、tenant ...
    resolve_or_register_cognizer(hub, tenant, "Claude", CognizerKind::Agent);
    auto id = hub.lookup_by_alias(tenant, "Claude");
    ASSERT_TRUE(id.has_value());
    EXPECT_EQ(hub.get(*id, tenant)->kind, CognizerKind::Agent);
}
TEST(NameResolver, DefaultsToHumanWhenKindOmitted) {
    resolve_or_register_cognizer(hub, tenant, "Alice");  // 不传 kind
    auto id = hub.lookup_by_alias(tenant, "Alice");
    EXPECT_EQ(hub.get(*id, tenant)->kind, CognizerKind::Human);
}
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd build-macos && ctest -R name_resolver --output-on-failure`
Expected: FAIL(编译错:签名无 kind 参数)。

- [ ] **Step 3: 实现**

```cpp
// name_resolver.hpp:14 签名末位加(默认 Human 保兼容)
std::string resolve_or_register_cognizer(CognizerHub& hub, std::string_view tenant,
                                         std::string_view surface,
                                         CognizerKind kind = CognizerKind::Human);
// name_resolver.cpp:49 改
reg.kind = kind;   // 改前:CognizerKind::Human 硬编码
```

- [ ] **Step 4: 运行,确认通过**

Run: `cd build-macos && ctest -R name_resolver --output-on-failure`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add include/starling/cognizer/name_resolver.hpp src/cognizer/name_resolver.cpp \
        tests/cpp/test_name_resolver.cpp
git commit -m "feat(cognizer): name_resolver kind 由调用方传入,缺省 human(不再焊死)"
```

---

### Task 3: 注册守卫接线 + 负例(整合,C++,进 CI)

**Files:**
- Modify: `src/extractor/extractor.cpp:313-316`(传 llm_cognizer_kind 的枚举给 resolver)
- Test: `tests/cpp/test_extractor_orchestrator.cpp` 或新建 `test_cognizer_registration_gate.cpp`

**Interfaces:**
- Consumes: `ExtractedStatement.subject_kind`(Task 1)、`llm_cognizer_kind`(Task 1)、
  `resolve_or_register_cognizer(..., kind)`(Task 2)、`cognizer_kind_from_string`
  (`src/cognizer/cognizer_hub.cpp:361`,既有,string→enum)。

- [ ] **Step 1: 写负例测试**(既有测试体系从来没有的)

```cpp
// 技术实体 subject(subject_kind="entity")不触发 cognizer 注册
TEST(RegistrationGate, EntitySubjectNotRegistered) {
    // 构造一条 subject_kind="entity" 的 ExtractedStatement,过 persist,
    // 断言 cognizers 表里没有该 subject 的行。
}
// cognizer subject 用 LLM 的 kind 注册
TEST(RegistrationGate, CognizerSubjectUsesLlmKind) {
    // subject_kind="cognizer", llm_cognizer_kind="agent" → 落库 kind=agent
}
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd build-macos && ctest -R "RegistrationGate|orchestrator" --output-on-failure`

- [ ] **Step 3: 实现** —— extractor.cpp:313 传 kind

```cpp
// extractor.cpp:313-316,守卫逻辑不变(现在 subject_kind 有真值,守卫才有意义),
// resolve 调用传入 LLM 判的 kind:
if (cog_hub && stmt.subject_kind == "cognizer" && !stmt.subject_id.empty()) {
    // llm_cognizer_kind 已由 Task 1 校验:要么是合法值域,要么是空。
    // 故此处只需处理空(默认 Human);合法串直接 cognizer_kind_from_string,
    // 不会抛(它只对值域外 throw,而值域外已在 Task 1 被置空)。
    const cognizer::CognizerKind k = stmt.llm_cognizer_kind.empty()
        ? cognizer::CognizerKind::Human
        : cognizer::cognizer_kind_from_string(stmt.llm_cognizer_kind);
    stmt.subject_id = starling::cognizer::resolve_or_register_cognizer(
        *cog_hub, holder_tenant_id, stmt.subject_id, k);
}
```
`cognizer_kind_from_string`(`include/starling/cognizer/cognizer.hpp:117`)对未知串
throw `std::invalid_argument`,但 Task 1 已保证传入的非空 kind 一定在值域内,故安全。

- [ ] **Step 4: 运行,确认通过 + 全量 ctest 不回归**

Run: `cd build-macos && ctest --output-on-failure`
Expected: 新负例 PASS;全量绿。

- [ ] **Step 5: 提交**

```bash
git add src/extractor/extractor.cpp tests/cpp/test_cognizer_registration_gate.cpp
git commit -m "feat(extractor): 注册守卫接 LLM subject_kind/cognizer_kind + 技术实体负例"
```

---

### Task 4: episodic 判据接线(C++,进 CI)

**决策(交 plan-eng-review 质疑):episodic actor 走完整 subject_kind 判定;participants
采「轻触」—— 保持 `[str]`,靠 prompt 强化不放非人进 participants,而非把 `[str]` 重构成
`[{name,kind}]`。** 理由:(1) actor 是主要注册触发点、也是非人污染源("the script ran");
(2) participants 被 prompt 定义为「ONLY the cognizers NAMED」,是策展过的人名列表,污染
风险低,而 [str]→[obj] 重构横扫 parser/writer/perceived_by JSON,代价高收益低。
**替代方案(eng-review 若否决轻触):participants 也结构化带 kind。**

**Files:**
- Modify: `src/extractor/episodic_extractor.cpp:167,183`(actor 按 kind 判定/注册)
- Modify: `include/starling/extractor/episodic_extractor.hpp`(EpisodicEvent 加 actor_kind 字段)
- Test: `tests/cpp/test_episodic_extractor.cpp`

**Interfaces:**
- Consumes: `resolve_or_register_cognizer(..., kind)`(Task 2)。
- Produces: episodic actor 非认知体时不注册(subject_kind="entity" 的 OCCURRED 语句
  仍可落,但不建 cognizer);participants 维持既有注册(轻触)。

- [ ] **Step 1: 写测试** —— 非人 actor 不注册 + actor kind 透传

```cpp
TEST(EpisodicExtractor, NonCognizerActorNotRegistered) {
    // event.actor_kind="entity"(如 "the script")→ 不建 cognizer
}
```
既有 `test_episodic_extractor.cpp:129/132` 断言 `subject_kind='cognizer'` —— 对真人 actor
样例(Sally/Anne)仍成立(它们是 cognizer);无需改,除非新增 entity-actor 夹具。

- [ ] **Step 2: 运行,确认失败** —— `ctest -R episodic --output-on-failure`

- [ ] **Step 3: 实现** —— actor 按 kind 判;participants 保持

```cpp
// episodic_extractor.cpp:163-177 的 resolve_name lambda 与 actor 处理:
// actor 只在 actor_kind=="cognizer"(或缺省)时 resolve_or_register;
// entity actor → subject_id 保留表面串,不注册。
// participants 循环维持既有(轻触:靠 prompt 挡非人)。
```

- [ ] **Step 4: 运行,确认通过** —— `ctest -R episodic --output-on-failure`

- [ ] **Step 5: 提交**

```bash
git add src/extractor/episodic_extractor.cpp include/starling/extractor/episodic_extractor.hpp \
        tests/cpp/test_episodic_extractor.cpp
git commit -m "feat(extractor): episodic actor 按 subject_kind 判定,非人不注册(participants 轻触)"
```

---

### Task 5: belief prompt 加 subject_kind + cognizer_kind + 判据 + 正负例

**Files:**
- Modify: `python/starling/extractor/prompts.py`(EXTRACTION_PROMPT:schema 行 + 判据段 + 每个 WORKED EXAMPLE 输出)

**Interfaces:** prompt 是配置数据单一源;不改 Python 逻辑。

- [ ] **Step 1: 改 schema 声明行**(`prompts.py:21`)

在 `Each Statement: {...}` 加 `"subject_kind": "cognizer"|"entity"` 与
`"cognizer_kind": "human"|"agent"|"group"|"role"|"external"(仅 cognizer 时)`。

- [ ] **Step 2: 加判据段**(紧接 HOLDER vs SUBJECT 那段,`prompts.py:31` 附近)

```
SUBJECT_KIND (CRITICAL): 判断 subject 是不是能持有信念的主体。
- cognizer:人、AI agent(如 Claude / the assistant)、组织/团队(group)、角色(role)。
- entity:技术实体、产品、库、设备、指标、数值、抽象事物 —— 任何不能持有信念的东西。
- 例:subject="Postgres"/"H800 memory"/"deploy budget" → entity;
      subject="Alice" → cognizer/human;"the eng team" → cognizer/group;
      "Claude" → cognizer/agent。
只有 subject_kind=="cognizer" 时才给 cognizer_kind。
```

- [ ] **Step 3: 每个 WORKED EXAMPLE 的输出补字段**

`prompts.py` 里 `:86,88,98,125,126,135,144` 等每条示例 JSON 加
`"subject_kind":"cognizer","cognizer_kind":"human"`(Bob/Alice 都是人)。
**每条都补 —— LLM 极其可靠地复制示例出现的字段;漏一条,LLM 就可能漏。**

- [ ] **Step 4: 手工核对** —— 通读改后 prompt,确认 schema 行/判据/示例三处一致,无矛盾。

- [ ] **Step 5: 提交**

```bash
git add python/starling/extractor/prompts.py
git commit -m "feat(prompt): belief 抽取加 subject_kind/cognizer_kind + 判据 + 正负例"
```

---

### Task 6: gf prompt 加字段(污染主源,示范 entity)

**Files:**
- Modify: `python/starling/extractor/general_fact_prompt.py`

- [ ] **Step 1: schema 行 + 判据段**(同 Task 5 的字段与判据文案)。

- [ ] **Step 2: WORKED EXAMPLE 补字段 —— 重点示范 entity**

`general_fact_prompt.py:46` `Postgres is_a relational database` → `subject_kind:"entity"`;
`:47` `deploy budget has_value $40k` → `subject_kind:"entity"`;
`Alice reports_to Bob`(:30 提到)→ `subject_kind:"cognizer","cognizer_kind":"human"`。
gf 是污染放大器 —— 示例必须清楚示范「技术名词/数值 = entity」。

- [ ] **Step 3: 手工核对一致。**

- [ ] **Step 4: 提交**

```bash
git add python/starling/extractor/general_fact_prompt.py
git commit -m "feat(prompt): general-fact 抽取加 subject_kind,示例示范技术实体=entity"
```

---

### Task 7: episodic prompt 强化(轻触:不放非人进 actor/participants)

**Files:**
- Modify: `python/starling/extractor/episodic_prompt.py`

- [ ] **Step 1: actor 加 actor_kind 字段 + 判据**

schema(`episodic_prompt.py:27`)actor 旁加 `actor_kind: "cognizer"|"entity"`。
判据:actor 通常是人(cognizer),但脚本/进程/物体做「动作」时(如 "the script ran")
actor_kind="entity"。

- [ ] **Step 2: 强化 participants 说明**(轻触核心)

在 participants 规则(`:36`)加:participants 只放**人/agent**(命名的认知体);
产品/库/指标绝不进 participants(它们是 theme/location)。给一个负例。

- [ ] **Step 3: WORKED EXAMPLE 补 actor_kind**(Sally/Anne → cognizer)。

- [ ] **Step 4: 手工核对 + 提交**

```bash
git add python/starling/extractor/episodic_prompt.py
git commit -m "feat(prompt): episodic actor_kind + 强化 participants 只放认知体"
```

---

### Task 8: 重建 + 全量门(整合验证)

- [ ] **Step 1: 重建 _core**(改了 C++ + 绑定接触面)

Run: `python scripts/configure_build.py --build --python-editable`
Expected: 构建绿 + _core 重装。

- [ ] **Step 2: 全量 ctest**

Run: `cd build-macos && ctest --output-on-failure`
Expected: 全绿(含 Task 1-4 新测试)。

- [ ] **Step 3: 全量 pytest**

Run: `.venv/bin/python -m pytest tests/python -q`
Expected: 全绿(无回归)。

- [ ] **Step 4: 提交**(若重建产生需提交的产物;否则跳过)

---

### Task 9: eval 三维基线守门(手动,真 LLM,非 CI —— 最大风险门)

**不进 CI。** Clash TUN 黑洞换时刻重跑。key 从环境读不打印。

- [ ] **Step 1: 改 prompt「前」建/确认基线**

**注意:必须在 Task 5-7 改 prompt 之前的代码上跑 baseline。** 若 Task 5-7 已提交,
先 `git stash` 或在改前 commit 上跑。
Run: `python scripts/eval_quality_baseline.py --update`
记下 belief/gf/tom 三维中位数分数(进 progress 账本)。

- [ ] **Step 2: 改 prompt「后」重跑查回归**

Run: `python scripts/eval_quality_baseline.py --check`
Expected: 三维相对退化在容差(0.05)内、不破阈值。**退化超容差 = prompt 改坏了抽取,
回 Task 5-7 修 prompt,不是放宽容差。**

- [ ] **Step 3: subject_kind 判准抽样**

用一小组已知 cognizer/entity 样例(Alice/eng team/Claude vs Postgres/H800 memory/budget)
跑抽取,人工核对 LLM 的 subject_kind 判对率 + 漏字段率(json_parser 的
MissingSubjectKind warning 计数)。判对率低或漏字段频繁 → 回 Task 5-7 强化 prompt 示例。

- [ ] **Step 4: 结果进 PR body + 账本。**

---

### Task 10: 存量 328 条一次性 LLM 重分类归档

**Files:**
- Create: `migrations/0031_cognizer_archive.sql`(cognizers 加 `archived_at TEXT`)
- Create: `scripts/reclassify_cognizers.py`(手动运维,非 CI)
- Modify: `python/starling/dashboard/queries.py`(cognizers 查询过滤 `archived_at IS NULL`)
- Test: `tests/python/test_dashboard_cognizers.py`(归档行不出现在 /cognizers)

- [ ] **Step 1: migration** —— cognizers 加可空 archived_at(可逆:NULL=活,时戳=归档)

```sql
-- migrations/0031_cognizer_archive.sql
ALTER TABLE cognizers ADD COLUMN archived_at TEXT;  -- NULL=活;时戳=一次性重分类判为 entity 而归档(可逆)
```

- [ ] **Step 2: /cognizers 查询过滤归档**(`queries.py` cognizers 的 nodes SELECT 加
  `AND archived_at IS NULL`)+ 前端不受影响(字段不变)。测试:归档行不出现。

- [ ] **Step 3: reclassify 脚本(纯逻辑部分先 TDD)**

分离:`classify_names(names, llm) -> dict[name, {kind, is_cognizer}]`(真 LLM,不测)
与 `plan_archive(rows, classification) -> (archive_ids, kind_updates)`(纯逻辑,单测)。
纯逻辑单测:
- entity 判定 → 进 archive_ids;
- **有关系边的不归档**(那 6 个真人:即便 LLM 判错也保护 —— 有边=已证实社会主体);
- cognizer 但 kind 更准(agent/group)→ 进 kind_updates;
- 幂等重入(已归档的不重复处理)。

- [ ] **Step 4: 脚本真机跑一次**(手动,真 LLM,Clash 换时刻重跑)

对 default tenant 的 334 行分批分类 → 归档 entity + 更新 kind。结果(归档数/kind 更新数/
保护的有边节点数)进 PR body。**可逆核对:随机抽一条归档的,确认 UPDATE archived_at=NULL
能恢复。**

- [ ] **Step 5: 提交**

```bash
git add migrations/0031_cognizer_archive.sql scripts/reclassify_cognizers.py \
        python/starling/dashboard/queries.py tests/python/test_dashboard_cognizers.py
git commit -m "feat(cognizer): 存量污染一次性 LLM 重分类归档(可逆)+ /cognizers 过滤归档"
```

---

### Task 11: 部署 + 浏览器实测认知体页

- [ ] **Step 1: 重建前端不需要(无前端改动);重启服务加载新 _core + 重分类后的库**

Run: `launchctl kickstart -k gui/$(id -u)/io.starling.dashboard`

- [ ] **Step 2: 浏览器实测**(用 /browse):认知体页现在应只剩真认知体(十几个量级),
  技术实体已归档不显示。截图给用户。核对:6 个有边真人还在。

- [ ] **Step 3: 结果进 PR body。**

---

## 分阶段依赖

- Task 1-4(C++ 纯逻辑,安全默认):可先落地,即便 prompt 未改也不崩(全走 entity 默认)。
- Task 5-7(prompt):加字段,让 LLM 真正判。
- Task 9(eval):**必须夹在 prompt 改动前后**(前建 baseline,后 check)。
- Task 10(存量):独立,可在代码修好后任意时刻跑。
- Task 8/11:整合门 + 实测。

## Self-Review(写完自查)

- [x] 无 placeholder:每步有确切 file:line + 代码/命令。
- [x] 类型一致:subject_kind/cognizer_kind/llm_cognizer_kind 跨 Task 一致;resolve 签名 Task 2 定义、Task 3/4 消费。
- [x] spec 覆盖:判据(Task 5-7)、parser(1)、kind(2)、守卫(3)、episodic(4)、eval(9)、存量(10)全有对应 Task。
- [x] 勿动写路径(second_order:140)写进 Global Constraints。
- [x] eval 门夹在 prompt 前后(Task 9 Step 1 明确「改前」)。
- 遗留给 eng-review 的开放取舍:episodic participants 轻触 vs 结构化(Task 4);归档 archived_at 列 vs 影子表(Task 10 选了列)。
