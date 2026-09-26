# SocialMemBench R6.1：来源纠错实现与真实探测

## 当前结论

目标批次来源越界现在可以使用原有的一次协议纠错额度，逻辑在 C++ 内实现，真实抽取与原生完整性回放共用判断。严格 parser、来源范围、admission 和 holder belief 原子写入保持。候选完整 holder 真实探测通过，但本轮没有触发纠错，不能声称真实稳定性、语义质量或 QA 已提升。133题仍须健康八库 baseline。

## 设计、测试、实现顺序

先写 [R6.1 中文设计](../superpowers/specs/2026-09-26-socialmem-r61-scope-correction-design.md)及计划，再补用例运行RED，最后修改 `src/extractor/extractor.cpp`。真实 RED 为19项聚焦测试中4项失败；修复后两个分批测试组36/36通过。候选完整 C++ 执行1362/1362通过，包括沙箱外localhost HTTP用例；沙箱内曾为1339通过/23跳过，两次口径分别留存。

Python候选binding回归9/9，新探测入口和真实双核心localhost fixture 10/10。fixture覆盖：旧核心越界立即终止、新核心恰好一次纠错并准入、所有失败费用保留、独立只读回放、重封summary/HTTP伪造拒绝、缺失usage停止、worker失败封存。模拟增益只是机制证据，不能代替真实QA。

R6.0欠缺的参考示例证据内部键序、还原声明旧顺序后的整段历史SHA、错层与两层重复字段无admission/无写入/费用保留断言已补齐通过。常规build和venv仍保持R6.0核心；R6.1隔离构建SHA为 `d2f60d1836336f9114efd437fec428050ac77e6bbec6abeea02a0e219b9df793`。

## 两轮真实调用分别报告

第一轮 `build/socialmem_20260926_r61_work/run-real`：首个Lionel旧核心任务在curl52/HTTP0时停止。观察到1次HTTP尝试、无响应和usage、远端执行未知；账本按1次本地请求结算，token消费未知，不是零。候选未调用。独立check重算为incomplete且退出1，符合封存状态。

端点不带密钥GET返回401，确认HTTPS可达；按明确记录的一次独立重启，从新目录执行相同四任务。第二轮 `build/socialmem_20260926_r61_work/run-real-retry`：

| 固定顺序 | 完整终态 | 写入声明 | 纠错次数 |
|---|---|---:|---:|
| Lionel旧核心 | 健康 | 9 | 0 |
| Lionel候选核心 | 健康 | 8 | 0 |
| Miriam候选核心 | 健康 | 10 | 0 |
| Miriam旧核心 | 健康 | 10 | 0 |

第二轮18聊天HTTP、200561已知tokens，预算30额度中结算18、保留0；未调用embedding。独立进程check重算通过，无provider调用。四任务完整来源、初始prompt hash、plan/schema保持一致；不同随机生成使声明数略有差异，不能解释为保留质量改善。两轮合计观察到19次尝试，只有第二轮token完整可知，不能把200561称总消费。

候选两名holder均健康且非空，满足推进八库的技术门槛。通过轮run seal为 `1a2a9f20a82e87880272a9058f8599fa8117ff8a92662833b35f560e49f2e60c`，prepare seal为 `285cbea5751c37b6c43809f8e7c3cbafc62ff0159a2dd1dc09cba460d46feedb`。

## 八库入口

按 [八库中文设计](../superpowers/specs/2026-09-26-socialmem-r61-expanded-baseline-design.md)，新入口复用既有scope/回放/账本实现，并硬绑定上述候选core与真实probe seal。R6.0旧探测资格不再用于新的候选建库。新入口先RED；默认参数仍指旧probe的问题由新增prepare测试复现并修正。完整原生八库fixture回归81/81通过。离线prepare完成：133题、8库、65 holder、1322来源单元、197批、belief上界591、三通道上界851。真实八库fresh build已封存为incomplete，1/8通过。第二库189/189向量最终健康，却被累计failed=32误阻断；108次聊天请求/1,291,057已知tokens、29次embedding请求。真实retrieve/QA未启动，详见[R6.2诊断](2026-09-26-socialmem-r62-embedding-health.md)。

## 下一步质量诊断

R6.0四库249条本地语义拒绝中，147条缺QUESTIONED标记，45条缺CONDITIONAL。整turn作用域可能错误覆盖其中独立的陈述句，已有Mum“提问后表达担忧”等明确复核线索。它解释了为什么仅扩充谓词无法恢复状态保留；但计数不是误拒率。先取得健康baseline，再以C++候选子句作用域的正反例与真实同口径QA验证优化。

所有证据位于 `build/socialmem_20260926_r61_work/`。R6.0历史失败和第一轮传输失败未覆盖、未改标。

## 评测入口验证

R6.1检索/QA入口完整回归117/117通过，使用R6.1双核心隔离后构建的本机八库fixture，覆盖266检索上下文与532答案、raw HTTP/答案/judge绑定、只读独立check、失败账本、连接释放、环境并发和联合篡改拒绝。固定新profile的门禁同时包含合法输入可通过和各项非法输入拒绝，避免旧profile使负例意外全部失败。真实八库已因embedding统计误判停止，fixture不是实际分数。对应中文合同见[评测设计](../superpowers/specs/2026-09-26-socialmem-r61-expanded-evaluation-design.md)。

### 疑问作用域的进一步定位

当前核心并非完全没有候选级作用域处理：`claim_scope.cpp::resolve_claim_question_scope`已有保守的leading_statement例外，要求首句内唯一逐字object、可判定完整句界，且后续问句无相关指代/词汇碰撞。未满足时回退到整turn标记。147条QUESTIONED拒绝的原生scope_resolution原因分别为object_not_literal 82、ambiguous_boundary 39、context_dependency 10、ineligible_claim 9、nonleading_object 5、unsupported_question_form 2。问题主要集中在改写object与自然对话句界超出现有窄规则，而非单纯缺少一个分句开关。上述原因只解释回退路径，不证明每条候选都应被接纳。后续应在完整基线上衡量扩展候选支撑片段解析带来的召回和错误接纳，保留真实问句/条件/引用的反例。
