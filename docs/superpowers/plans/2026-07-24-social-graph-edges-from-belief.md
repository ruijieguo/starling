# PR4 — 社会图建边(从 belief 关系谓词)

缺陷 B 收尾。`remember()` 三条抽取 pass 从不调用 `upsert_relation` —— 只建点不建边,
`cognizer_relations` 里 6 条全是 `seed_demo.py` 手灌。本 PR 给现成的 `upsert_relation`
API 接一个抽取时的调用方:belief 的 `reports_to` / `member_of` 语句 → 有向带类型的社会图边。

## 决策(用户已拍板,全按建议 A)

1. **边来源:只做 belief 关系谓词** —— `reports_to` / `member_of`。数据最干净(prompt 已强制
   subject/object 双 cognizer),有向有类型。episodic 共现(a)/二阶信念(c)本轮不做。
2. **object 反查 miss → 跳过不建边**(只对已存在认知体建边)。绝不注册新认知体 —— 那正是
   「过度注册」的病根,PR1/2/3 刚清理完,不能从建边路径重新引入污染。
3. **边保持底层有向,本轮不动前端**(前端继续无向渲染,方向渲染增强单独做)。
4. **Fiske 按谓词硬编码映射**:reports_to → Authority 重,member_of → Communal 重。

## Global Constraints

- **只 resolve 已存在认知体**:object 串走 `lookup_by_alias`(不 register)。miss 跳过。
- **subject 已是 cognizer id**:写路径 313-329 已把 `subject_kind=cognizer` 的 subject resolve
  成 cognizer id(存在 `stmt.subject_id`)。建边复用它,不重复 resolve。
- **建边在 statement 写成功之后**(`StatementWriteAccepted` 分支内),失败/noop 的语句不建边。
- **best-effort**:建边失败(FiskeWeightsInvalid/DB 错)不回滚语句、不中断 run —— 社会图是
  observer,与语句写入解耦。try/catch 包住。
- **self 边过滤**:subject==holder_id(self 消解结果)或 a_id==b_id 的自环不建。
- **勿动写路径的既有语义**:holder attribution(343-351)、scope_parties(352-359)不碰。

## 边来源判据

只有同时满足才建边:
- `stmt.subject_kind == "cognizer"` 且 `stmt.subject_id` 非空(已 resolve 成 cognizer id)
- `stmt.predicate` ∈ {`reports_to`, `member_of`}
- `stmt.object_value` 经 `lookup_by_alias(tenant, object_value)` 命中已存在认知体 → b_id
- a_id(subject_id 对应) != b_id(不建自环)

Fiske 映射(和为 1.0):
- `reports_to`:Authority 0.7 / Equality 0.1 / Communal 0.1 / Market 0.1
  (上下级 = Authority Ranking 主导);power_asymmetry = 0.5(A 从属于 B)
- `member_of`:Communal 0.7 / Equality 0.1 / Authority 0.1 / Market 0.1
  (归属 = Communal Sharing 主导);power_asymmetry = 0.0

## 方向语义

- `reports_to(A→B)`:a_id=A(下级/subject),b_id=B(上级/object)。边表「A 向 B 汇报」。
- `member_of(A→B)`:a_id=A(成员/subject),b_id=B(组织/object)。边表「A 属于 B」。
- 与 upsert 的 (tenant,a_id,b_id,valid_from) 唯一键一致:同向重复 = upsert 更新,不重复建。

---

## Task 1: 建边纯逻辑函数(可单测,不碰 DB)

**Files:**
- New: `include/starling/extractor/relation_edge_builder.hpp`
- New: `src/extractor/relation_edge_builder.cpp`
- Test: `tests/cpp/test_relation_edge_builder.cpp`(注册进 CMakeLists.txt)

**Interfaces:**
- `struct EdgePlan { std::string a_id; std::string b_id; std::unordered_map<FiskeMode,double> fiske; double power_asymmetry; };`
- `std::optional<EdgePlan> plan_relation_edge(const std::string& predicate, const std::string& subject_id, const std::string& b_id);`
  - subject_id/b_id 都是**已 resolve 的 cognizer id**(调用方负责 resolve)。
  - predicate 不在 {reports_to,member_of} → nullopt。
  - subject_id == b_id → nullopt(自环)。
  - subject_id 或 b_id 空 → nullopt。
  - 否则返回带 Fiske 映射 + power_asymmetry 的 EdgePlan。

纯函数:不碰 hub、不碰 lookup、不碰 DB。反查(lookup_by_alias)由调用方在 extractor 里做,
这样纯逻辑可零依赖单测。

- [ ] Step 1: 写失败测试 —— reports_to 映射/member_of 映射/非关系谓词→nullopt/自环→nullopt/空→nullopt/Fiske 和为1
- [ ] Step 2: 跑,确认失败(函数未实现)
- [ ] Step 3: 实现 plan_relation_edge
- [ ] Step 4: 跑,确认通过
- [ ] Step 5: 提交

## Task 2: extractor 接线(reslve object + 调 upsert)

**Files:**
- Modify: `src/extractor/extractor.cpp`(写成功分支内,~392 行后加建边)
- Test: `tests/cpp/test_social_edge_extraction.cpp`(新,端到端:喂 reports_to 语句 → 断言 cognizer_relations 有边)

**接线逻辑**(插在 `StatementWriteAccepted` 分支内,statement 写成功后):
```cpp
// 社会图建边(缺陷 B):belief 的关系谓词 → cognizer_relations 有向边。
// best-effort,与语句写入解耦;失败不影响 run。
if (cog_hub && stmt.subject_kind == "cognizer" && !stmt.subject_id.empty()
        && (stmt.predicate == "reports_to" || stmt.predicate == "member_of")) {
    try {
        // object 只反查不注册(决策 2:miss 跳过,绝不新建认知体)。
        auto b = cog_hub->lookup_by_alias(holder_tenant_id, stmt.object_value);
        if (b.has_value()) {
            if (auto plan = plan_relation_edge(stmt.predicate, stmt.subject_id, *b)) {
                cognizer::RelationEdgeInput e;
                e.tenant_id = std::string(holder_tenant_id);
                e.a_id = plan->a_id; e.b_id = plan->b_id;
                e.fiske_weights = plan->fiske;
                e.power_asymmetry = plan->power_asymmetry;
                cog_hub->upsert_relation(e);
            }
        }
    } catch (const std::exception&) { /* observer:建边失败不影响语句/run */ }
}
```

- [ ] Step 1: 写端到端失败测试 —— seed 两个 cognizer(Alice/Bob)→ 喂 reports_to(Alice→Bob) 语句 → 断言 cognizer_relations 有 1 条 a=Alice b=Bob 边 + Fiske Authority 主导。再喂 member_of。再测 object miss(object=陌生名)→ 0 边。再测自环(subject==object)→ 0 边。
- [ ] Step 2: 跑,确认失败
- [ ] Step 3: 实现接线(引 relation_edge_builder.hpp)
- [ ] Step 4: 跑,确认通过 + 全量 ctest 无回归
- [ ] Step 5: 提交

## Task 3: 整合门 + 无回归

- [ ] 重建 _core
- [ ] 全量 ctest(975+) + pytest(955+)零回归
- [ ] 确认无新 clang-tidy 违规(短名/括号/.count — PR1 踩过的坑,本地无 tidy,靠手动审所有新增行)

## Self-Review(写完自查)

- [ ] object 只 lookup 不 register(决策 2)—— 代码里无 resolve_or_register 调用于建边路径。
- [ ] 建边在写成功分支内,失败/noop 语句不建边。
- [ ] best-effort try/catch,不回滚语句、不中断 run。
- [ ] 自环(a==b)、self(subject==holder)、object miss 三种都跳过。
- [ ] Fiske 和为 1.0(纯逻辑单测覆盖)。
- [ ] 前端未改(决策 3);无 migration(表已存在)。
- [ ] 新增 C++ 无 <3 字符标识符/无括号 if/.count(clang-tidy 门)。
