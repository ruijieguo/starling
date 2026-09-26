<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.3 来源预算与结构化声明 sidecar 实施计划

> **执行要求：** 使用 superpowers:executing-plans 按任务执行，并在每个任务后运行规定的验证命令。步骤使用复选框跟踪。

**目标：** 在 C++ 中实现 evidence_profile_v8，使来源先占用 k 名额、结构化声明以最多 3 条 sidecar 追加，并用同库离线回放验证其对 SocialMemBench 检索上下文的影响。

**架构：** ObserverRetriever 在 C++ 中完成来源排序、source span 回链、sidecar 准入、UTF-8 预算和诊断；Python 只透传策略、调用 binding、编排离线回放和归档 QA。v6/v7 行为保持兼容，v8 只作为实验策略。

**技术栈：** C++20、SQLite、GoogleTest、pybind11、pytest、现有 eval_ladder_pipeline、冻结 SocialMemBench R5.1 数据和 qwen3.8-27B DashScope。

**设计依据：** docs/superpowers/specs/2026-09-25-socialmem-r53-source-sidecar-design.md

---

## 全局约束

- 不 reset、清理或覆盖当前工作区已有变更；所有新输出放在独立 build/socialmem_20260925_r53_* 目录。
- 生产核心选择逻辑只写在 src/retrieval/source_retriever.cpp；Python 不复制排序、回链、谓词或预算判断。
- 先写并运行 RED 测试，再写 C++ 实现；RED 失败必须来自 v8 策略未注册或预期行为未实现。
- evidence_profile_v6、v7 和 bm25 的既有测试及上下文哈希不得改变。
- 本轮默认策略仍为 v6；fresh QA 只有离线门槛全部通过后才允许发起。

## 任务 1：编写 C++ v8 RED 测试

**文件：**

- 修改：tests/cpp/test_source_retriever.cpp，在现有 SourceClaimProfile 测试组中追加 v8 用例。
- 不修改：生产 C++ 文件和 CMake；该文件已加入 starling_tests。

### 步骤 1：写来源不被 sidecar 挤出的失败测试

在 SourceClaimProfile 后追加以下行为的测试。测试使用已有的 turn、save、save_claim、run 和 expect_exact_lanes 辅助函数。

    TEST_F(SourceClaimProfile, V8KeepsSourceQuotaWhenStatementsExist) {
        q.source_strategy = "evidence_profile_v8";
        q.mode = "hybrid";
        q.allowed_holders = {"Alice"};
        q.k = 2;
        q.question = "Which kiln approach does Alice use?";
        save(Json::array({
            turn("Alice", "I use a shared kiln for bowls.", 1),
            turn("Alice", "I use a private kiln for tests.", 2)
        }));
        save_claim(turn("Alice", "I prefer the shared kiln for bowls.", 3),
                   "prefers", "the shared kiln for bowls");
        const auto result = run();
        ASSERT_EQ(result["source_count"], 2);
        EXPECT_EQ(result["source_refs"].size(), 2u);
        EXPECT_LE(result["statement_count"].get<int>(), 3);
        EXPECT_EQ(result["source_count"].get<int>() +
                  result["statement_count"].get<int>(),
                  result["labels"].size());
        EXPECT_EQ(result["source_diagnostics"]["evidence_profile"]["source_limit"], 2);
    }

运行该单测时，当前代码应因不接受 evidence_profile_v8 而失败；失败信息必须是 invalid observer query 或等价的策略未注册错误。

### 步骤 2：写直接来源优先于低相关 semantic link 的失败测试

    TEST_F(SourceClaimProfile, V8DirectSourceOutranksLowRelevanceSemanticLink) {
        q.source_strategy = "evidence_profile_v8";
        q.mode = "hybrid";
        q.allowed_holders = {"Alice", "Bob"};
        q.k = 1;
        q.question = "What changed in Alice's kiln approach?";
        save(Json::array({
            turn("Alice", "My kiln approach changed after the winter tests.", 1)
        }));
        save_claim(turn("Bob", "I believe the studio budget is stable.", 2),
                   "believes", "the studio budget is stable");
        embed_latest_statement("Bob", q.question);
        const auto result = run();
        ASSERT_EQ(result["source_count"], 1);
        EXPECT_EQ(result["source_refs"][0]["speaker"], "Alice");
        EXPECT_EQ(result["source_diagnostics"]
                      ["selection_trace"][0]["selected_by"], "relevance");
    }

这条测试验证低相关 semantic link 不能替换直接命中来源；当前代码应先因策略未注册失败。

### 步骤 3：写 sidecar 回链、预算和硬过滤失败测试

追加以下三个用例：

- V8RejectsStatementWhoseSourceWasNotSelected：k=1，Alice 的直接来源和 Bob 的结构化声明同时存在，断言 source_count=1、statement_count=0、sidecar_rejections.source_not_selected 大于 0。
- V8SidecarBudgetNeverReducesSources：先以 mode=sources、bm25 得到两条来源的 context_bytes，再以 mode=hybrid、v8 使用相同 max_context_bytes，断言 source_count 仍为 2、statement_count 为 0。
- V8PreservesTenantHolderAndAsOfFilters：复用现有跨 tenant、holder、as_of fixture，策略改为 v8，断言越权来源与声明均不出现在 source_refs、statement_ids 中。

### 步骤 4：运行 RED

    cmake --build build --target starling_tests -j2
    ./build/tests/cpp/starling_tests \
      --gtest_filter='SourceClaimProfile.V8*'

预期：编译成功但全部 v8 用例因策略未注册而失败；若测试编译错误，先修正测试夹具，不触碰生产实现。

---

## 任务 2：编写 Python binding RED 测试

**文件：**

- 修改：tests/python/test_source_retriever_binding.py

### 步骤 1：写 binding 透传用例

    def test_binding_forwards_evidence_profile_v8_to_native(native):
        rt, observer, q = native
        q.mode = "hybrid"
        q.k = 1
        q.source_strategy = "evidence_profile_v8"
        _core.retain_source_turns(
            rt.adapter, "default", ["Ada"], json.dumps(TURNS),
            "2026-01-01T00:00:00Z")
        result = json.loads(observer.run(q))
        assert result["source_count"] == 1
        assert result["source_diagnostics"]["evidence_profile"]["source_limit"] == 1

该测试只断言 Python 设置的策略被 C++ 接收，不实现任何排序或准入逻辑。

### 步骤 2：运行 Python RED

    python -m pytest tests/python/test_source_retriever_binding.py \
      -k evidence_profile_v8 -q

预期：因 C++ 尚未注册 v8 而失败；若出现 binding 导入错误，先用现有 build 重新生成扩展并复跑。

---

## 任务 3：实现 C++ v8 最小闭环

**文件：**

- 修改：src/retrieval/source_retriever.cpp
- 必要时修改：include/starling/retrieval/source_retriever.hpp（只增加声明，不把选择逻辑放入 header）
- 修改：bindings/python/bind_05_retrieval.cpp 仅在新增字段时透传；本方案默认不新增字段，因此应保持不变。

### 步骤 1：注册策略并保持旧策略分支不变

在 ObserverRetriever::run 的策略校验、source dialogue 参数校验、claim metadata 加载、degraded receipt 和 evidence profile 分支中加入 evidence_profile_v8。v8 只允许 hybrid 产生 sidecar；sources 模式仍只返回来源，statements 模式保持原有拒绝规则。

把现有 v7 的 semantic source span 回链逻辑抽成可复用的 C++ 局部 helper，v8 复用同一证据合同；不得把校验复制到 Python。

### 步骤 2：实现 v8 来源选择

在 profile_sources 附近增加 v8 分支或独立 profile_sources_v8 函数：

- source_limit 固定为 q.k，不从 statement 数量扣减；
- 保持现有硬过滤、holder coverage、时间链和 event 邻接候选；
- 先按 subject_match、topic_score/topic_overlap、BM25 score 和稳定时间排序；
- semantic_linked 只在上述相关性相等时用 semantic_score 打破平局；无直接相关来源时允许 semantic link 回退；
- event 只能由已经保留的 semantic anchor 派生；
- 将来源选择轨迹写入 evidence_profile.source_selection_order；
- 旧 v6/v7 使用原分支，避免改变历史上下文。

### 步骤 3：实现 sidecar 选择与渲染

在来源集合完全确定后执行 v8 sidecar：

- 遍历 planner statements，校验 statement_source_key、授权来源池、已选 source key、tenant/holder/as-of 和现有 claim evidence 合同；
- 用 C++ 现有 terms/BM25 和问题车道标记计算声明相关性；不满足条件的声明写入 sidecar_rejections；
- 以固定 3 为 sidecar_limit，声明通过后才调用现有 append lambda；
- append 前保留来源的 context bytes，声明只消耗剩余 max_context_bytes；超限只增加 budget_rejected；
- block 顺序固定为全部 SOURCE 行后再接 sidecar 行，更新 source_context_bytes、statement_context_bytes、sidecar_selection_order；
- selected 继续等于 source_count，source_quota_satisfied 由实际 source_count 与 source_limit 派生；
- labels、source_refs、statement_ids 去重，context_bytes 必须等于 block 的 UTF-8 字节长度。

### 步骤 4：运行最小 GREEN

    cmake --build build --target starling_tests -j2
    ./build/tests/cpp/starling_tests \
      --gtest_filter='SourceClaimProfile.V8*'

预期：Task 1 的 v8 用例全部通过，且 v6/v7 相关测试未被改动。

---

## 任务 4：完成 C++/Python 回归

### 步骤 1：运行来源专项和绑定专项

    ./build/tests/cpp/starling_tests \
      --gtest_filter='SourceProfile.*:SourceClaimProfile.*'
    python -m pytest tests/python/test_source_retriever_binding.py -q

预期：C++ 来源与声明测试全部通过；Python binding 全部通过。任何 v6/v7 快照变化都要停止并先定位。

### 步骤 2：运行编译和静态检查

    cmake --build build -j2
    git diff --check

确认新策略只存在于 C++ 核心路径，Python 仅保留 binding/编排调用。

---

## 任务 5：编写离线回放 RED 测试与脚本

**文件：**

- 新增：tests/python/test_socialmem_r53_offline.py
- 新增：scripts/run_socialmem_r53_offline.py

### 步骤 1：先写离线脚本合同测试

测试脚本的纯函数必须覆盖：

- 缺少 R5.1 execution-plan、comparison 或 seal 时 fail closed；
- v8 recall 每题只能有一条终态记录，且 source_count、statement_count、context_bytes 与 block 一致；
- gold anchor 的召回统计按 item_id 去重，不能把 statement 命中当作 source 命中；
- 输出目录已存在时拒绝覆盖；
- 生成的 manifest 固定 core、题目、数据库和策略哈希。

运行：

    python -m pytest tests/python/test_socialmem_r53_offline.py -q

预期：因入口脚本不存在而 RED。

### 步骤 2：实现零请求离线回放

scripts/run_socialmem_r53_offline.py 只做评测编排：

- 复用 R5.1 same-db 的 frozen loader、sample 和身份校验；
- 对每个 item 调用 eval_ladder_pipeline.recall_observer_block，传入 source_strategy=evidence_profile_v8、与 v6/v7 相同的 k、max_context_bytes、holders 和 as_of；
- 保存每题 recall、source/block SHA-256、selection diagnostics、gold source anchors 和拒绝原因；
- 生成 comparison.json，比较 v6、v7、v8 的 source_count 分布、gold anchor 命中、sidecar 数量/拒绝率和上下文预算；
- 不发送 answer/judge 请求，不写入冻结数据库，不改历史输出目录。

### 步骤 3：运行离线 GREEN

    python -m pytest tests/python/test_socialmem_r53_offline.py -q
    python scripts/run_socialmem_r53_offline.py \
      --contexts build/socialmem_20260925_r51_same_db_v6_v7 \
      --out build/socialmem_20260925_r53_source_sidecar_offline

预期：57/57 题完成，v8 source_count 不因 sidecar 低于 v6；所有 hard filter 和 UTF-8 budget 审计通过。

---

## 任务 6：离线门槛审计与结果文档

**文件：**

- 新增：docs/eval/2026-09-25-socialmem-r53-source-sidecar.md
- 修改：docs/design/system_design.md
- 修改：docs/design/subsystems_design/13_retrieval.md
- 修改：docs/Starling_Technical_Report.zh-CN.md

### 步骤 1：审计离线门槛

用脚本输出和独立 Python 重计确认：

- v8 source anchor recall 不低于 v6；
- 57/57 题 source_count 不因 sidecar 下降；
- sidecar 抽样相关性至少 0.8，拒绝原因可逐条回链；
- source_context_bytes + statement_context_bytes == context_bytes；
- tenant、holder、as_of、source hash/span 和数据库哈希全部通过。

若任一门槛失败，停止在离线诊断，不能发送 DashScope 请求；把失败原因写入 R5.3 中文报告。

### 步骤 2：写离线中文报告

报告必须区分 R5.2 历史结果、R5.3 当前 HEAD 结果、离线夹具诊断和未执行的 fresh QA；不能把来源召回或 sidecar 数量写成 QA 提升。

### 步骤 3：运行文档审计

    git diff --check
    rg -n '待定|占位' \
      docs/eval/2026-09-25-socialmem-r53-source-sidecar.md \
      docs/superpowers/specs/2026-09-25-socialmem-r53-source-sidecar-design.md

---

## 任务 7：通过离线门槛后执行 fresh QA/judge

**文件：**

- 新增：scripts/run_socialmem_r53_v8_qa.py
- 新增：tests/python/test_socialmem_r53_v8_qa.py
- 新增：build/socialmem_20260925_r53_v8_qa_fresh/
- 修改：docs/eval/2026-09-25-socialmem-r53-source-sidecar.md
- 修改：docs/design/system_design.md
- 修改：docs/design/subsystems_design/13_retrieval.md
- 修改：docs/Starling_Technical_Report.zh-CN.md

### 步骤 1：先写 QA provenance RED

测试必须拒绝 v8 context 数量不足、prompt/context SHA-256 漂移、模型/answer/judge 配置漂移、重复 item、非终态回执和已存在输出目录；并验证双臂配对差值按 v8-v6 计算。

运行：

    python -m pytest tests/python/test_socialmem_r53_v8_qa.py -q

预期：因 v8 QA runner 尚不存在而 RED。

### 步骤 2：实现双臂 QA 编排

runner 复用 R5.2 的冻结 answer_prompt、grounded_memory_v1、option parser、judge parser、BudgetLedger 和 native adapter；新增 v8 arm，保持同一进程、同一题目、同一模型配置、同一请求账本和同一裁判协议。Python 只编排请求和统计，不实现检索逻辑。所有请求和回执写入独立 R5.3 目录，不复用或覆盖 R5.2 结果。

### 步骤 3：运行 fresh QA/judge

仅在 Task 6 门槛通过后运行：

    python scripts/run_socialmem_r53_v8_qa.py \
      --contexts build/socialmem_20260925_r53_source_sidecar_offline \
      --out build/socialmem_20260925_r53_v8_qa_fresh \
      --fresh-v8

确认 DashScope 请求的模型为 qwen3.8-27B，answer/judge 上限、thinking、重试、预算和账本均与 R5.2 相同。

### 步骤 4：分析并更新文档

报告 legacy/native 的 v6/v8 正确数、共同正常子集、四格转移、network bootstrap、技术失败、judge 翻转、token 与请求账本；只有共同正常子集净增至少 5 题且 network bootstrap 95% 区间下界大于 0 才允许讨论晋升，否则默认继续 v6。

---

## 任务 8：最终验证与交付

### 步骤 1：运行针对性验证

    ./build/tests/cpp/starling_tests \
      --gtest_filter='SourceProfile.*:SourceClaimProfile.*'
    python -m pytest \
      tests/python/test_source_retriever_binding.py \
      tests/python/test_socialmem_r53_offline.py \
      tests/python/test_socialmem_r53_v8_qa.py -q
    git diff --check

### 步骤 2：复核工作区边界

确认 git status 中的历史未提交变更没有被 reset、删除或覆盖；R5.3 新输出均位于独立目录；报告明确区分历史分数、当前 HEAD、离线结果和 fresh 结果。

### 步骤 3：完成中文进展报告

最终报告只声明已验证的事实，列出代码、测试、离线回放、fresh QA（若执行）的路径和命令；若门槛未通过，明确说明停止点和默认策略仍为 evidence_profile_v6。

## 执行修订

以设计 §7.1 为准：所有 C++ 用例显式嵌入声明，断言实际正向 sidecar 数而非仅上界；先验证 50 项既有来源测试（已通过），再新增测试。检索复评如需真实查询嵌入，使用既有授权且单列成本。QA 仅 v6/v8 两臂。产品默认 bm25、开发对照 v6 均保持。当前分支 codex/socialmem-r53-sidecar，逐任务内联执行，不再等待执行方式确认。

- [x] 中文方案与实施计划。
- [x] 既有 C++ 50 项基线。
- [x] C++/binding RED。
- [x] C++ v8 实现与 GREEN；排序、span 一致性、语义邻居反例均完成。
- [x] 真实同库检索比较与审计：两次各171健康回执，最终51→45/104。
- [x] 按未通过门槛分支完成诊断；QA 未启动，任务7的runner及模型调用不执行。
- [x] 全部设计文档同步与最终复核。

本轮检索执行补充：三组 v6/v8/v8_sources，同一真实向量库及新核心，最大 1035 次查询嵌入、零重试，不调用 answer/judge。旧 R5.1 v6 的 345 次嵌入全部降级，必须重建健康对照。6 项评测编排测试已先 RED 后 GREEN。

最终复核补充：首轮171健康检索已封存，锚点51→44/104、QA停止。审查补充邻居也有semantic link的RED→GREEN后，另建_source_sidecar_verified复核目录；本轮两次检索合计最多2070查询嵌入，避免将首轮分数误标为最终核心。

## 执行终态

最终C++1304/1304、来源专项60/60、相关Python87/87。两轮检索各171健康回执；最终v6 51/104、v8 45/104，来源控制0差异、68sidecar。累计2070嵌入，answer/judge为0。任务7因检索门槛失败不实施，任务6/8依停止分支完成。[中文诊断报告](../../eval/2026-09-25-socialmem-r53-source-sidecar.md)。
