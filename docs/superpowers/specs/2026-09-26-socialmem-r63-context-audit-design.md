# R6.3 混合上下文核验修复与零请求恢复

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

## 问题与证据

R6.2八库通过，266个检索终端全部返回ok。结束核验调用`render_context_line(StatementRow, "FACT")`，但binding只接受C++的`ContextPackLabel`枚举，因此133个baseline终端被审计阻断；source10来源文本路径未触发问题。原检索已封存incomplete，实际计数1336次embedding，QA请求零。旧fixture只生成来源文本/空结构声明，未覆盖这条真实边界。

这是评测编排的参数类型错误，C++核心和检索语义无需修改。Python仅把原生packet中的合法标签名称转换为已暴露的C++枚举，继续调用C++渲染并逐字核对。未知标签、缺失声明、篡改内容继续拒绝；不在Python复制渲染或标签推断逻辑。

## 恢复合同

新增R6.3评测入口，使用同一R6.2固定核心、八库、cohort、回答政策、费用和评分规则。恢复只接受固定SHA绑定的R6.2失败封存：先完整验证seal清单、历史身份/来源副本、输入build绑定、执行计划、失败类型，再用修复后的核验逐条检查全部266个回执、started日志、租户声明和ledger。旧核验异常包含进程地址，旧失败摘要无法稳定重算；本轮不宣称旧checker成功，而是明确记录新checker重新验证。

新目录保留逐字相同的回执、调用日志和ledger，另写`recovery.json`绑定原失败、原seal、旧/新审计源码以及继承消费。新的检索阶段标为重新核验恢复，外部新增请求必须为零。原incomplete不改写；已有目标拒绝覆盖。独立check必须再次验证恢复来源和逐文件复制等价，拒绝只改本地summary或recovery元数据。

通过恢复和独立check后才构造QA provider，产生原计划的532个fresh答案。QA继续固定qwen3.8-27b、并发4、预算956；不以覆盖诊断筛题，不重发检索。统计说明133题为开发cohort，技术失败计错。

## 测试顺序

1. 原生StatementRow + FACT、BELIEF等实际标签：C++渲染成功的packet应通过核验；原字符串传参必须RED。
2. 缺行、文本篡改、来源元数据篡改保持拒绝。
3. 在已封存266上下文上离线恢复；禁止任何provider工厂调用，完整核验成功且新请求为零。
4. 篡改来源seal、上下文/started/ledger、复制关系或恢复记录均被拒绝；原产物SHA不变。
5. 既有评测回归及独立check通过后开始QA，最终同步所有中文设计状态和报告。
