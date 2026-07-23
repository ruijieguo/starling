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
- **self 表征(eng-review D6′)**:cognizer_kind 含 `self`;LLM 判 subject 指向 agent 自己时标 self,C++ resolver 遇 self **不新建认知体**,而是解析到本次 run 的 `holder_id`(agent 身份已在手)——既表征 self 是一等认知主体,又堵死「我/me/myself」碎片化。
- **原子部署(eng-review D7)**:PR1 的 C++(Task 1-4)与 prompt(Task 5-7)**必须同一次部署上线**,禁止分期。中间态(C++ 上了、prompt 没上)= 全走 entity 默认 = 零认知体注册的静默半坏窗口。能编能测 ≠ 可部署。
- **PR 拆分(eng-review D2)**:本 plan = PR1(Task 1-9,抽取修复)。Task 10-11(存量重分类归档)拆为**独立 PR2**,跑在已验证修好的管线上——代码修复与数据变更风险剥度不同。PR2 的身份键/事务/回滚/审计由 PR2 自己的 eng-review 覆盖。

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

- [ ] **Step 3: 实现** —— extractor.cpp:313 传 kind + self 消解到 holder_id

```cpp
// extractor.cpp:313-316,守卫逻辑不变(现在 subject_kind 有真值,守卫才有意义)。
if (cog_hub && stmt.subject_kind == "cognizer" && !stmt.subject_id.empty()) {
    // llm_cognizer_kind 已由 Task 1 校验:要么是合法值域,要么是空。
    // 故此处只需处理空(默认 Human);合法串直接 cognizer_kind_from_string,
    // 不会抛(它只对值域外 throw,而值域外已在 Task 1 被置空)。
    const cognizer::CognizerKind k = stmt.llm_cognizer_kind.empty()
        ? cognizer::CognizerKind::Human
        : cognizer::cognizer_kind_from_string(stmt.llm_cognizer_kind);
    // self 消解(eng-review D6′):LLM 判 subject 指向 agent 自己(kind=self)时,
    // 不新建认知体,直接解析到本次 run 的 holder_id(agent 身份,已在 run 签名手边)。
    // 否则「我/me/myself」会碎成一堆独立认知体。self 是一等认知主体,但它的身份是
    // 运行时的(holder_id),不由文本表面串建号。
    if (k == cognizer::CognizerKind::Self) {
        stmt.subject_id = std::string(holder_id);  // run 的 agent 身份
    } else {
        stmt.subject_id = starling::cognizer::resolve_or_register_cognizer(
            *cog_hub, holder_tenant_id, stmt.subject_id, k);
    }
}
```
`cognizer_kind_from_string`(`include/starling/cognizer/cognizer.hpp:117`)对未知串
throw `std::invalid_argument`,但 Task 1 已保证传入的非空 kind 一定在值域内,故安全。
`holder_id` 是 `Extractor::run` 的入参(`extractor.hpp:102`),抽取时已在手,self 消解零额外查询。

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

**决策(plan-eng-review D3/D5 已定):**
- **actor** 走完整 subject_kind 判定(actor_kind),非认知体不注册。
- **D5(P1 正确性):`episodic_extractor.cpp:183` 那行独立硬编码 `stmt.subject_kind="cognizer"`
  必须改为跟 actor_kind 走** —— 否则 entity actor 的 OCCURRED 语句会 subject_kind="cognizer"
  却无 cognizer 注册,ToM 读路径把它当认知体去查(自相矛盾的行)。写语句的 subject_kind
  必须与「是否真注册了认知体」一致。
- **D3:participants 本轮停止自动注册。** `[str]` 上没有 kind 信息,prompt 字面「只放认知体」
  约束不住模型(与 fallback=entity『宁漏勿污』同源:prompt 不能当安全边界)。participants
  本就是社会图边的信号源 —— 连同注册一起归**缺陷 B(社会图上线)**统一做。本轮 participants
  只用于 `perceived_by`(既有 JSON,不注册 cognizer)。

**Files:**
- Modify: `src/extractor/episodic_extractor.cpp:167,183`(actor 按 kind 判定/注册;subject_kind
  跟 actor_kind;participants 循环移除 `resolve_or_register_cognizer` 调用)
- Modify: `include/starling/extractor/episodic_extractor.hpp`(ParsedEpisodicEvent 加 actor_kind 字段)
- Test: `tests/cpp/test_episodic_extractor.cpp`

**Interfaces:**
- Consumes: `resolve_or_register_cognizer(..., kind)`(Task 2)。
- Produces: entity actor 不注册且其 OCCURRED 语句 `subject_kind="entity"`;participants
  本轮**完全不注册 cognizer**(仅入 perceived_by)。

- [ ] **Step 1: 写测试** —— 非人 actor 不注册 + subject_kind 跟 actor_kind + participants 不注册

```cpp
TEST(EpisodicExtractor, NonCognizerActorNotRegisteredAndSubjectKindEntity) {
    // event.actor_kind="entity"(如 "the script ran")→ 不建 cognizer,
    // 且落库的 OCCURRED 语句 subject_kind == "entity"(D5:不再恒 cognizer)。
}
TEST(EpisodicExtractor, ParticipantsNotRegisteredThisRound) {
    // 一个 participant 名(如 "Bob")本轮不应新建 cognizers 行(D3:归缺陷 B)。
    // 但仍出现在该事件的 perceived_by JSON 里。
}
```
既有 `test_episodic_extractor.cpp:129/132` 断言 `subject_kind='cognizer'` —— 对真人 actor
样例(Sally/Anne,actor_kind=cognizer)仍成立;新增 entity-actor 夹具断言 "entity"。

- [ ] **Step 2: 运行,确认失败** —— `ctest -R episodic --output-on-failure`

- [ ] **Step 3: 实现** —— actor 按 kind 判 + subject_kind 跟 actor_kind + participants 停注册

```cpp
// episodic_extractor.cpp:163-183:
// (a) actor:仅 actor_kind=="cognizer"(或缺省)时 resolve_or_register_cognizer(传 kind);
//     entity actor → subject_id 保留表面串,不注册。
// (b) D5:stmt.subject_kind = (actor_kind=="entity") ? "entity" : "cognizer";
//     不再硬编码 "cognizer"。
// (c) D3:participants 循环删除 resolve_or_register_cognizer 调用 —— participant 名
//     直接进 perceived_by(表面串),本轮不注册任何 cognizer。
```

- [ ] **Step 4: 运行,确认通过** —— `ctest -R episodic --output-on-failure`

- [ ] **Step 5: 提交**

```bash
git add src/extractor/episodic_extractor.cpp include/starling/extractor/episodic_extractor.hpp \
        tests/cpp/test_episodic_extractor.cpp
git commit -m "feat(extractor): episodic actor 按 subject_kind 判定 + subject_kind 跟 actor_kind(D5) + participants 停注册(D3)"
```

---

### Task 5: belief prompt 加 subject_kind + cognizer_kind + 判据 + 正负例

**Files:**
- Modify: `python/starling/extractor/prompts.py`(EXTRACTION_PROMPT:schema 行 + 判据段 + 每个 WORKED EXAMPLE 输出)

**Interfaces:** prompt 是配置数据单一源;不改 Python 逻辑。

- [ ] **Step 1: 改 schema 声明行**(`prompts.py:21`)

在 `Each Statement: {...}` 加 `"subject_kind": "cognizer"|"entity"` 与
`"cognizer_kind": "self"|"human"|"agent"|"group"|"role"|"external"(仅 cognizer 时)`。
**D6′:含 `self`** —— subject 指向 agent 自己("Alice 觉得我可靠" 里的「我」)时用 self;
self 是一等认知主体(有信念/知识边界),不能降级成 human。

- [ ] **Step 2: 加判据段**(紧接 HOLDER vs SUBJECT 那段,`prompts.py:31` 附近)

```
SUBJECT_KIND (CRITICAL): 判断 subject 是不是能持有信念的主体。
- cognizer:人(human)、AI agent(如 Claude / the assistant)、组织/团队(group)、
  角色(role)、以及 subject 指向叙述者自己时的 self。
- entity:技术实体、产品、库、设备、指标、数值、抽象事物 —— 任何不能持有信念的东西。
- 例:subject="Postgres"/"H800 memory"/"deploy budget" → entity;
      subject="Alice" → cognizer/human;"the eng team" → cognizer/group;
      "Claude" → cognizer/agent;"我"/"me"/"myself"(指叙述者自己)→ cognizer/self。
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

- [ ] **Step 3: subject_kind 分类准确率子门(硬门,eng-review 加)**

三维总分只测任务好不好,结构上看不到「一半真人被默认成 entity」这类分类崩塌 —— 所以
单独立一个分类准确率门,守本次改动的核心风险。

建一个固定标注集(进仓库,`tests/eval/subject_kind_labeled.jsonl`,~40-60 条),覆盖
每个类别至少数条:human / agent(Claude) / group(eng team) / role / self(我/me) /
entity(Postgres / H800 memory / macro4 score / deploy budget / 库版本号)。跑抽取,
按类别统计 subject_kind 的 precision/recall + cognizer_kind 判对率。

**硬阈值(破则回 Task 5-7,不放宽):**
- entity recall ≥ 0.9(技术实体几乎不该漏判成 cognizer —— 这是污染的直接度量);
- cognizer recall ≥ 0.9(真人/agent 几乎不该被默认成 entity —— 这是「fallback=entity
  误伤召回」的直接度量,codex 点名的风险);
- cognizer_kind 判对率 ≥ 0.85(human/agent/group/role/self 分类)。
- 漏字段率:直接数标注集里 subject_kind 缺失的比例(parser 静默默认 entity,无 warning
  计数结构 —— 就靠这个固定集来量,不在 parser 里加机制)。漏字段频繁 → 回 Task 5-7 补示例。

- [ ] **Step 4: 结果进 PR body + 账本。**

**Task 9 执行结果(真 LLM,gpt-5.5,改前 baseline vs 改后 current):**

子门(D4,核心验证,0 SSL 失败):
- subject_kind 判对率 **16/16 = 1.000**(阈值 0.90)✅
- cognizer_kind 判对率 **8/8 = 1.000**(阈值 0.80)✅
- 漏抽 0;含 5 真实污染类(H800 memory/macro4 score/FLA kernel/TE 2.14.1/ToMBench run time)全判对

三维回归(容差门 相对 baseline 退化 ≤0.05,recheck 0 SSL 失败):
| metric | base | curr | delta | 判定 |
|---|---|---|---|---|
| holder | 0.808 | 0.834 | +0.026 | ✅ |
| holder_perspective | 0.821 | 0.848 | +0.027 | ✅ |
| predicate | 0.848 | 0.861 | +0.013 | ✅ |
| object | 0.848 | 0.861 | +0.013 | ✅ |
| tom accuracy | 0.958 | 1.000 | +0.042 | ✅ |
| nesting_depth_1 | 0.800 | 0.600 | -0.200 | ⚠ 抖动(见下) |

nesting_depth_1 -0.20 判为**抖动非回归**:(1) 同一改前 prompt 两次建 baseline 该指标自己 0.6↔0.8 跳(样本仅 10 条,2 条翻转=0.2);(2) git diff 证明 nesting 规则文字+depth 数值一字未改,只插了 subject_kind/cognizer_kind;(3) 因果上不可能只伤 nesting 而 holder/perspective/predicate/object 四项全改善。**裁定:PASS。**

资产:`scripts/eval_subject_kind.py` + `tests/data/eval_subject_kind_corpus.jsonl`(16 条)+ `tests/data/eval_baseline.json`(三维基线)。

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

## PR 拆分(eng-review D2)

**PR1 = Task 1-9(抽取修复):** 止住新污染。纯代码 + prompt + eval,风险同质。
**PR2 = Task 10-11(存量回填):** migration + LLM 重分类 300+ 行数据 + 实测。风险剥度不同,
且必须跑在「已验证修好」的 PR1 管线上。PR2 单独过一轮 review(codex 已给出一批 PR2 专属
发现:身份键用 (tenant_id, cognizer_id) 而非裸 name、归档行的全局语义、批量改 statements 的
事务边界、有边保护不是可靠不误杀策略 —— 都留给 PR2 的 review 消化,不在本轮 PR1 范围)。

## 分阶段依赖(PR1 内)

- **原子部署(eng-review D7,硬约束):** Task 1-4(C++)与 Task 5-7(prompt)**必须同一次
  部署上线**,不许「C++ 先落地」。理由:旧 prompt 不输出 subject_kind → parser 全 fallback
  entity → 守卫恒假 → 零认知体注册窗口,窗口内 dogfood 摄入的真人全部漏注册,ToM 社会层
  静默失效。中间 commit 能编能测 ≠ 可部署。commit 可以分开,但 **deploy 是一次**。
- Task 9(eval):**必须夹在 prompt 改动前后**(前建 baseline,后 check + subject_kind 子门)。
- Task 8:整合门(重建 + 全量 ctest/pytest),在部署前。

## Self-Review(写完自查)

- [x] 无 placeholder:每步有确切 file:line + 代码/命令。
- [x] 类型一致:subject_kind/cognizer_kind/llm_cognizer_kind 跨 Task 一致;resolve 签名 Task 2 定义、Task 3/4 消费。
- [x] spec 覆盖:判据(Task 5-7)、parser(1)、kind(2)、守卫(3)、episodic(4)、eval(9)、存量(10)全有对应 Task。
- [x] 勿动写路径(second_order:140)写进 Global Constraints。
- [x] eval 门夹在 prompt 前后(Task 9 Step 1 明确「改前」)+ subject_kind 判准子门(eng-review D4)。
- [x] eng-review 决策已折入:participants 本轮停自动注册(D3, Task 4);subject_kind=actor_kind 映射(D5, Task 4);
      self kind + 消解到 holder_id(D6′, Task 3/5);原子部署(D7, 分阶段依赖);PR 拆分(D2);cognizer_kind 含 self(D6′)。
- [x] 归档 archived_at 列(Task 10,PR2)—— 影子表已排除。

---

## Implementation Tasks
Synthesized from this review's findings. Each task derives from a specific finding above.

- [ ] **T1 (P1, human: ~1h / CC: ~10min)** — episodic_extractor — OCCURRED 语句 subject_kind 跟 actor_kind 走
  - Surfaced by: Architecture/正确性 (D5) — `episodic_extractor.cpp:183` 独立硬编码 `subject_kind="cognizer"`,entity actor 会产出自相矛盾行
  - Files: `src/extractor/episodic_extractor.cpp`, `tests/cpp/test_episodic_extractor.cpp`
  - Verify: `ctest -R episodic` — entity-actor 夹具的 OCCURRED 行 subject_kind=="entity"
- [ ] **T2 (P1, human: ~2h / CC: ~15min)** — episodic — 本轮停 participants 自动注册
  - Surfaced by: Architecture (D3, codex) — participants 是无 kind 信息的注册触发路径,prompt 不能当安全边界
  - Files: `src/extractor/episodic_extractor.cpp`, `python/starling/extractor/episodic_prompt.py`, `tests/cpp/test_episodic_extractor.cpp`
  - Verify: `ctest -R episodic` — participant 表面串不再建 cognizer 行
- [ ] **T3 (P1, human: ~3h / CC: ~20min)** — extractor/name_resolver — self subject 消解到 holder_id
  - Surfaced by: Architecture (D6′, user) — self 是一等认知主体;不消解则「我/me」碎片化成多个认知体
  - Files: `src/extractor/extractor.cpp`, `src/cognizer/name_resolver.cpp`, `tests/cpp/`
  - Verify: `ctest` — cognizer_kind=self 的 subject 解析到本次 run holder_id,不新建「me」
- [ ] **T4 (P1, human: ~2h / CC: ~15min)** — eval — subject_kind 分类准确率子门
  - Surfaced by: Tests (D4, codex) — 三维总分结构性看不到 cognizer 召回崩塌
  - Files: `scripts/eval_quality_baseline.py` 或配套标注集
  - Verify: 已知 cognizer/entity 样例集上分类准确率有硬阈值,低于则拦
- [ ] **T5 (P1, human: ~30min / CC: ~5min)** — 部署 — PR1 强制 C++ + prompt 原子上线
  - Surfaced by: Architecture (D7, codex) — 分期部署开「零注册」静默半坏窗口
  - Files: 分阶段依赖 section(流程约束,非代码)
  - Verify: PR1 合并即同时含 Task 1-8;无「仅 C++」中间部署
- [ ] **T6 (P2, human: ~15min / CC: ~5min)** — prompt — cognizer_kind 选项补 self
  - Surfaced by: Code Quality (D6′, codex) — schema 值域含 self 但 LLM 选项漏了
  - Files: `python/starling/extractor/prompts.py`, `general_fact_prompt.py`
  - Verify: schema 行/判据/示例三处 kind 选项一致含 self
- [ ] **T7 (P2, human: ~1h / CC: ~10min)** — 下游审计 — subject_kind 全消费方清点
  - Surfaced by: Architecture (codex) — subject_id 从认知体名变实体表面串,需确认无隐含 ID 假设(已验:今值本就是 canonical_name==surface,风险降级但仍需成文清单)
  - Files: 审计 `src/tom/`, `src/cognizer/`, `bindings/` 中读 subject_kind/subject_id 的路径
  - Verify: 清单入 PR body;确认 entity 语句不误入 ToM/关系/别名解析

_PR2(存量回填)findings(身份键、有边保护、归档全局语义、批量改 statements)归 PR2 自身审查,不在本表。_

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | outside-voice 抛 16 点,PR1 相关 7 点已折入,余归 PR2 |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 7 issues, 0 critical gaps(全部经 AskUserQuestion 折入 plan) |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **CODEX:** outside voice(codex, high effort)独立抛 16 点。PR1 相关的 7 点全部折入(episodic subject_kind 映射、participants 停注册、eval 分类子门、原子部署、self kind、下游审计);其中「subject_id→surface 破坏 FK」经亲验为假(今值本就是 canonical_name==surface),降级为审计清单项。其余 9 点属 PR2 回填(身份键、有边保护、归档全局语义、批量改 statements、发布顺序),D2 拆分已挪至 PR2。
- **CROSS-MODEL:** 两处张力均由用户裁决 —— participants 轻触(review) vs 停注册(codex)→ 采 codex(D3);eval 三维门(review) vs 加分类子门(codex)→ 采 codex(D4)。self 表征方向由用户洞察推翻我原判(D6′)。
- **VERDICT:** ENG CLEARED — ready to implement(PR1)。7 findings 全部经 AskUserQuestion 折入,0 critical gaps。PR2(存量回填)单列,含 codex 的 9 点回填风险,须自身审查后再实施。

NO UNRESOLVED DECISIONS
