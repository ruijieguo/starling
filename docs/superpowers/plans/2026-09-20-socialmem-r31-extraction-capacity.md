<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench R3.1 抽取容量实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 在固定 SocialMemBench 57 题协议下，只将结构化抽取上限从 4096 提升到 8192，验证抽取截断是否是 R2.3 技术损失的主要来源。

**架构：** Python 评测运行器按 arm 传递容量配置，C++ native adapter 继续承担请求、解析、谓词、admission、写入和检索语义。来源臂保持 4096，五个结构化臂使用 8192；回答、裁判、超时、重试、题目和评分全部保持不变。

**Tech Stack:** Python 3、pytest、现有 Starling C++ core/binding、SocialMemBench 本地冻结快照、DashScope `qwen3.8-27b`。

**Spec:** `docs/superpowers/specs/2026-09-20-socialmem-r31-extraction-capacity-design.md`

## Global Constraints

- 所有设计和评测说明使用中文。
- 先文档，再 RED 测试，再最小实现，再回归，再独立评测和分析。
- Python 只做评测编排和配置传递；核心语义和协议逻辑保持在 C++。
- `sources` 的 `extract_max_tokens=4096`；五个结构化 arm 为 `8192`。
- `answer_max_tokens=512`、`judge_max_tokens=64`、`timeout_ms=120000`、`max_retries=0` 固定。
- 不改谓词目录、解析器、提示、写入、检索、题目、裁判和生产默认开关。
- 不覆盖或清理共享工作区已有修改和历史评测目录。

---

### Task 1: 写入并同步中文设计文档

**Files:**
- Create: `docs/superpowers/specs/2026-09-20-socialmem-r31-extraction-capacity-design.md`
- Create: `docs/superpowers/plans/2026-09-20-socialmem-r31-extraction-capacity.md`
- Modify: `docs/design/system_design.md`
- Modify: `docs/design/claim_contract_sync.md`
- Modify: `docs/design/subsystems_design/07_neocortex.md`
- Modify: `docs/design/subsystems_design/08_cognizer.md`
- Modify: `docs/design/subsystems_design/13_retrieval.md`

**Interfaces:** 设计文档规定 `arm_config(arm)["extract_max_tokens"]` 的新契约；后续测试和实现必须只依赖该字段，不新增 Python 语义逻辑。

- [x] **Step 1: 写入中文 spec 和本计划**
- [x] **Step 2: 在五个现行设计入口追加 R3.1 状态、单变量边界和待评测结论**
- [x] **Step 3: 检查文档不存在占位符和相互矛盾的容量值**

运行：`rg -n "R3\.1|extract_max_tokens|4096|8192" docs/superpowers/specs/2026-09-20-socialmem-r31-extraction-capacity-design.md docs/superpowers/plans/2026-09-20-socialmem-r31-extraction-capacity.md docs/design/system_design.md docs/design/claim_contract_sync.md docs/design/subsystems_design/07_neocortex.md docs/design/subsystems_design/08_cognizer.md docs/design/subsystems_design/13_retrieval.md`

### Task 2: RED 测试锁定容量分层

**Files:**
- Modify: `tests/python/test_socialmem_structured_eval_guard.py`

**Interfaces:** 测试调用现有 `runner.arm_config`，断言来源臂为 4096、每个结构化臂为 8192，并确认回答/裁判容量不变。

- [x] **Step 1: 添加最小失败断言**

```python
def test_r31_raises_only_structured_extraction_capacity():
    assert runner.arm_config("sources")["extract_max_tokens"] == 4096
    for arm in ("statements", "statements_fenced", "hybrid_fenced",
                "hybrid_dialogue", "hybrid_dialogue_expanded"):
        config = runner.arm_config(arm)
        assert config["extract_max_tokens"] == 8192
        assert config["answer_max_tokens"] == 512
        assert config["judge_max_tokens"] == 64
```

- [x] **Step 2: 运行 RED**

运行：`./.venv/bin/python -m pytest tests/python/test_socialmem_structured_eval_guard.py::test_r31_raises_only_structured_extraction_capacity -q`

预期：失败，结构化 arm 当前返回 4096 而非 8192。

### Task 3: 最小 Python 配置实现

**Files:**
- Modify: `scripts/run_socialmem_structured_eval.py:110-150`

**Interfaces:** `arm_config(arm: str) -> dict` 保持原签名；仅根据 `structured = arm != "sources"` 计算 `extract_max_tokens`。

- [x] **Step 1: 将配置表达式改为 `8192 if structured else 4096`**
- [x] **Step 2: 不修改其他配置键和 C++ binding**
- [x] **Step 3: 运行单测确认 RED 断言转绿**

运行：`./.venv/bin/python -m pytest tests/python/test_socialmem_structured_eval_guard.py -q`

预期：该模块全部通过，且既有 arm 协议守卫仍通过。

### Task 4: 回归与离线评测门禁

**Files:**
- Create: `build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_r31_extract8192/`（运行产物，不修改历史目录）

- [x] **Step 1: 运行相关 Python 回归和 `git diff --check`**
- [x] **Step 2: 用独立目录执行 `prepare` 和 `check`**
- [x] **Step 3: 核对 manifest 中来源、题目、配置和代码指纹**

### Task 5: 运行并分析 57 题评测

**Files:**
- Create: 独立 R3.1 运行目录下的请求账本、逐题回执、scope 数据库和分析 JSON
- Create: `docs/eval/2026-09-20-socialmem-r31-extraction-capacity.md`
- Modify: 五个现行设计入口，追加真实评测结论

- [x] **Step 1: 在已授权 DashScope/qwen3.8-27b 环境执行固定 57 题运行**
- [x] **Step 2: 统计截断、超时、协议失败、scope/holder 和主评分**
- [x] **Step 3: 与 R2.3 按 `item_id` 做共同 `ok` 逐题转移分析**
- [x] **Step 4: 写中文报告，明确 QA 提升、技术可靠性和生产晋升边界**
- [x] **Step 5: 运行最终回归、`git diff --check`，仅凭新鲜输出汇报结论**
