<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.5 扩大开发验证实施计划

> 执行流程：使用 superpowers:subagent-driven-development，任务完成后依次进行合同审查、代码质量审查。用户已授权自主迭代，不重复索取授权；保留现有工作树，不自动提交。

目标：在固定新增133题上验证冻结v9相对于健康v6的问答提升。
架构：核心逻辑和提示仍由冻结C++完成；Python只编排、身份检查、账本与统计。先完成设计，再RED/GREEN，最后真实执行。
技术：现有C++核心、SQLite账本、Python评测入口；不新增依赖。

合同见[中文设计](../specs/2026-09-25-socialmem-r55-expanded-development-design.md)。

## 任务一：新增样本与健康建库入口

文件：新增 `scripts/run_socialmem_r55_expanded.py`、`tests/python/test_socialmem_r55_expanded.py`。

- [x] 先写失败测试：SHA固定选样；禁止reserved或旧network、重复题和history漂移；scope健康必须完整holder、非零statement、成功embedding；零请求prepare和check；episodic HTTP失败、截断、缺失回执不得被holder成功掩盖；拒覆盖。
- [x] 运行 `.venv/bin/python -m pytest tests/python/test_socialmem_r55_expanded.py -q` 保存RED，确认缺少新行为导致失败。
- [x] 实现 `select_records`、`validate_scope_health`、`prepare`、`check`、`build`。复用baseline.prepare_groups、冻结_imports、_build_scope_database；每个scope在临时工作目录运行helper，归档稳定frozen.db/全部回执；失败以SQLite backup归档诊断快照；不把仍打开的network.db/WAL/SHM纳入seal。增加真实native+FakeLLM子进程退出后验封测试。每个scope输出health、DB SHA、完整回执及持久账本。阶段上限12000，抽取upper=9*holders；部分失败阻断。
- [x] 运行同一测试得到GREEN；只读合同审查后再代码质量审查，修复发现项。

## 任务二：双臂检索和fresh QA

- [x] 先写失败测试：完整133题/8scope身份绑定、266检索终态、baseline逐holder健康、source10零embedding、532 QA任务、956 QA上限、失败计零及拒覆盖。
- [x] 实现 `retrieve` 和 `qa` 阶段；复用r54_ablation.query_one/validate_row及r54_qa.build_task/run_task/compare_scores，不调用固定57题的validate_inputs。覆盖旧门槛字段：133题至少净增7题、全题CI下界>0、共同正常同向、grounded每臂正常至少127/133；测试6题净增不达标及正常率单臂不足。
- [x] 来源/声明/上下文字节均走冻结native，配置不改；source10锚点是否提升不作为QA执行条件。
- [x] seal覆盖实际依赖和各阶段产物，SQLite账本与回执核对；fresh QA主要终点grounded，次要legacy，不重新挑选主要终点。裁判翻转按真实judge_prompt及配置分组，不用answer prompt限制；保存事件通道空结果/未解析歧义计数。
- [x] 同一测试GREEN，执行既有R5.4相关回归；完成合同与质量审查。

## 任务三：真实运行、分析与文档同步

- [x] 运行 `... run_socialmem_r55_expanded.py prepare`，离线核验固定core、输入、输出无覆盖，再 `check`。
- [ ] 使用既有DashScope授权依次 `build`、`retrieve`、`qa`，每阶段通过健康与身份门槛再进下一阶段；失败即时封存、定位，不用删题补齐分母。
- [ ] 新增 `docs/eval/2026-09-25-socialmem-r55-expanded-development.md`，记录实际完成边界、分数、置信区间、技术失败、锚点和token成本；独立重算统计与验证全部seal。
- [ ] 同步 `docs/design/**/*.md`、`docs/superpowers/{specs,plans}/**/*.md` 与两份技术报告的中文状态入口，校验链接并保存清单。
- [ ] `.venv/bin/python -m pytest tests/python/test_socialmem_r55_expanded.py tests/python/test_socialmem_r54_ablation.py tests/python/test_socialmem_r54_qa.py -q` 与 `git diff --check` 通过后交付；无C++改动不重复全量C++测试。

报告必须分别标注R5.4旧57题与R5.5新133题，若建库失败只报告失败诊断、未执行的检索/QA，不声称扩大评测完成。产品默认bm25、开发对照v6不变。
