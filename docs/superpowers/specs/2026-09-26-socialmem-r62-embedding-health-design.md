<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

# SocialMemBench R6.2：最终向量健康与可审计恢复

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

## 问题与证据

R6.1 八库建库封存为 incomplete，1/8 通过。第二库抽取及原生回放通过，189/189 条声明都有 embedded、1024 维向量，但累计失败尝试为 32，运行器把它误当最终失败数。108 次聊天请求、1,291,057 个已知聊天 tokens、29 次 embedding 请求必须保留。最初 embedding 故障的 HTTP 原因和 tokens 未暴露，不能推断为 429 或零消费。只读诊断保存在 `build/socialmem_20260926_r62_work/embedding-diagnosis.json`。

## 选择与边界

按既有自主迭代授权继续，顺序为中文文档、失败测试、实现、评测。仅把 Python 门禁改为忽略 failed 会放过重试耗尽；在 Python 复制健康 SQL 违背核心逻辑归属。因此选择 C++ 最终健康快照，所有 binding 复用。抽取、向量生成、检索排序和回答政策保持既有语义；本轮没有准确率改善主张。

## 原生合同

`EmbeddingWorker::health` 对当前连接作只读检查。使用与 worker 相同的活动声明范围（排除 archived、forgotten），以 `(tenant_id, stmt_id)` 关联，返回 total、embedded、missing、retryable_failed、exhausted、invalid 互斥计数及 complete。合法 embedded 必须匹配当前 embedder 的 dim/model，raw_embedding 与 index_vector 都是正确长度的非零有限浮点向量，retry_count 为零。未知状态、非法 retry_count、损坏 blob 归 invalid；失败项按 max_retry 分组。空库 complete=true，但评测仍独立要求声明非空。

同一原生实现提供只读文件检查，拒绝不存在或带 WAL/SHM 的非冻结文件，不执行迁移、不生成 sidecar、不调用模型。支持显式维度、模型及重试上限，参数非法立即失败。输出不包含历史尝试数；历史次数来自执行回执，不能从最终数据库臆造。

`embed_seeded` 保留 embedded/failed/ticks 的历史含义，新增 final_health。累计 failed 大于零且 final_health.complete=true 可以继续；最终失败、缺失、损坏不得继续。max_ticks 仍有界。所有调用方停止把 failed 当最终失败。八库校验重新调用原生健康检查并绑定回执，不信任手写 complete=true。

## 历史与恢复

所有 R6.1 封存目录原样保留；新代码不能重写其 summary、账本或失败标记。历史 checker 必须用封存 source 在独立临时工作区执行，避免当前 Python 演进导致 audit program drift；仍核验原 seal、源码清单、核心和全部原始回执，不能放宽 SHA。

R6.2 核心单独构建。恢复阶段标注 recovered/revalidated，不宣称 fresh-from-zero。复用历史库前，须通过历史独立 checker，并在新核心下对完整来源、所有原始响应及写入结果重放；声明逻辑行及来源必须等价，最终向量由新原生检查重新核验。任何不一致拒绝复用。复用库和后续新建库分别记录原始核心、验证核心、数据库 SHA 和费用来源；不把历史消费计为本轮新增、不把已知聊天 tokens 当 embedding 总费用。新阶段不执行历史失败的未知请求，不静默覆盖证据。若恢复合同尚未验证，不启动付费建库。

## 验收

先复现累计失败误阻断，再测试恢复成功、耗尽、缺失、错模型/维度、损坏或非有限向量、同 ID 跨租户、归档范围、只读性和伪造回执。C++ 与 Python 聚焦回归通过后验证隔离核心、历史 checker 与恢复 fixture。健康八库后才进入 266 次检索与 532 次 fresh QA；评分仍使用既有基准合同，133 题开发 cohort 不是全量或保留集。
