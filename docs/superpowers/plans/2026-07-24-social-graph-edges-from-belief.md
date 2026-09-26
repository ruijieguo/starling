<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# PR4 — 社会图建边(从 belief 关系谓词)
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

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
