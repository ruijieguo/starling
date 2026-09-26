# SocialMemBench R6.2：向量误阻断诊断

> **终态更新（2026-09-26）**：八库已完成，R6.3零请求恢复266个检索上下文，532个新答案完成并独立核验。133题开发集grounded为36→41，legacy为37→37，未晋升。完整结果见[八库配对报告](2026-09-26-socialmem-r62-expanded-baseline.md)。以下故障起点和中间诊断按原时间顺序保留。

R6.1 真实八库已停止并封存为 incomplete，1/8 通过；133 题 baseline 尚未完成，真实检索和 QA 未执行。这不是与旧轮可比的健康率退化结论。

第二库完整抽取、原生回放和聊天回执通过。189 条声明对应 189 条 embedded 向量，均为 qwen3.7-text-embedding、1024 维，raw/index blob 均 4096 字节，retry_count=0；其中 32 条留有失败尝试时间。运行器因累计 failed=32 抛错，混淆了历史尝试与最终状态。重试机制已恢复，不应由此重做全部付费抽取。

本轮历史建库消费为 108 次聊天请求、1,291,057 个已知聊天 tokens、29 次 embedding 请求。embedding 的原始 HTTP 和 tokens 未暴露，首次故障原因未知。原封存结果不改标。修复按[中文设计](../superpowers/specs/2026-09-26-socialmem-r62-embedding-health-design.md)实施，目前没有新增 QA 分数。


## 实施与验证

已先写设计，再得到8项管线/原生API反例失败与建库 `embedding technical failures: 32` 原始失败日志，最后实现 C++ 健康快照与薄 binding。保留累计 failed，新增 final_health；重试耗尽、错误模型/维度、非有限或零向量、错误租户关联仍拒绝。

隔离候选核心 SHA：`949484630a9c83d93fb0582c9b37ff6a228e3f39bc80fe020b1384441e0c9bfb`。聚焦C++14/14、完整C++1368/1368（含localhost HTTP）、管线和binding31/31、独立baseline运行器19/19通过。历史封存审计2/2通过；当前源码升级后仍可用原封存程序重算R6.1的1/8终态和原消费。

恢复集成4/4通过，包含两库重放、不重新构造provider、保留原32次失败、篡改拒绝，以及后六库localhost原生抽取/embedding流程。模拟首次embedding HTTP503经原生重试恢复，最终8/8健康；模拟新增257次聊天/3084tokens、8次embedding与继承108次聊天/1291057tokens、29次embedding分开统计。这些是fixture，不是实际baseline或QA分数。

## 真实恢复阶段

`build/socialmem_20260926_r62_expanded/prepare` 已封存。新 `build` 已启动，前两库以 revalidated_recovery 模式通过；原始数据库SHA保持，候选核心重放完整三通道来源、响应、准入和逻辑声明行等价。第二库缺失的执行期 embedded/ticks计数明确为null，不能从最终数据库填造；原failed=32保留。后六库已完成真实新建，模型仍qwen3.8-27b。现已8/8通过并完成独立检查，合计934条声明、934条有效向量；新增398次聊天请求/4,336,627已知聊天tokens/89次embedding请求。合计含继承506次聊天/5,627,684已知聊天tokens/118次embedding；embedding tokens仍未知。build seal为 `02922356edb7b78761b3ab97d97e1989bc287baea023bdaff57b519d2d98a2a2`。266个上下文与532个新答案的后续终态已在置顶报告汇总。

## 后续能力线索

两个继承库的44次belief尝试中，原生保留100条候选、本地拒绝137条；其中80条缺QUESTIONED、28条缺CONDITIONAL。计数不是误拒率，下一阶段仍应基于baseline检索/回答失败逐例检查候选作用域，而不是一律放宽标记。

另在localhost的完全相同向量fixture中，现有pattern separation对重复共线邻居反复扣减，10条向量出现7条零index_vector；新健康检查正确阻断。该发现保存在 `synthetic-collinear-diagnosis.json`，仅是可复现的合成边界，当前原生189条真实向量未发现此问题。先用有效且不同的fixture向量验收本轮健康/恢复合同；分离算法作为baseline后的独立C++修复项。

检索/QA入口完整回归117/117通过，覆盖266上下文、532答案、原始HTTP/答案/judge绑定、独立check、费用和篡改拒绝。上述回归使用localhost fixture；真实检索与QA现均已结束，结果见置顶报告。

候选拒绝的详细分层、真实正反例与baseline后的验证顺序见[作用域诊断](2026-09-26-socialmem-r62-source-scope-diagnosis.md)。QUESTIONED占比高并不意味着应全部放行。

真实前三库的只读几何统计进一步发现：266条向量均非零，其中9条raw/index余弦低于0.5，1条为负；最小值约-0.0392。中位数均为1.0，说明多数向量未发生分离偏移。该指标只刻画向量变化，不能直接归因为QA错误；详见 `real-vector-geometry-diagnosis.json`，待baseline后做同库检索消融。

## 八库补充诊断

197个belief批次均仅一次抽取尝试，未触发真实协议纠错。原生本地检查拒绝451个候选事件，其中QUESTIONED 194、CONDITIONAL 134；通过本地检查681条，LLM准入进一步拒绝159条（wrong_relation 104），最终保留522条。候选事件不能直接当作误拒率或唯一事实数。全部934条向量非零，但27条raw/index余弦低于0.5、4条为负；这仍是几何诊断，尚未建立与QA失败的因果联系。证据：`build/socialmem_20260926_r62_work/eight-scope-build-diagnosis.json`。

## 检索结束核验的后续阻塞

266个检索终端实际均返回ok，1336次embedding调用已记账。结束核验发现Python传入标签字符串而C++要求ContextPackLabel枚举，原检索阶段保持incomplete。R6.3已补原生声明渲染反例并最小修复，已在不重发检索的前提下重新核验全部266个上下文并完成QA；最终进展见[八库配对报告](2026-09-26-socialmem-r62-expanded-baseline.md)。
