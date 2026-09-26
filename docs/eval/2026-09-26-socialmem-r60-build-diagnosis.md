# SocialMemBench R6.0 建库终态与故障诊断

## 当前结论

R6.0 的声明布局实现已完成，真实八库建库停在 **3/8 健康**。第四库两名 holder 引用了批外来源；后四库未执行，133 题尚无 baseline，也没有检索或 QA 提升证据。独立离线 `check` 重算成功，返回 `incomplete`，退出码 1 表示阶段不完整。

| 实际执行 | 健康库 | 聊天请求 | 已知聊天 tokens | embedding 请求 |
|---|---:|---:|---:|---:|
| R6.0 候选前两库探测 | 2/2 | 109 | 1,308,638 | 25 |
| R6.0 从头八库建库 | 3/8 | 263 | 2,605,938 | 60 |

两次调用独立消费；embedding tokens 未暴露。另一次沙箱网络失败记录了 20 个本地 transport attempts，不能称 provider 收到 20 次请求。账本额度单位不能等同实际请求数。

## 直接证据与根因

运行根为 `build/socialmem_20260926_r60_work/build-real`。第四库为 `7313df353a6801409499b156`，其 `scope.json`、原始回执和数据库均已封存。只读诊断清单在 `build/socialmem_20260926_r60_work/diagnosis/failure-analysis.json`，包含来源文件与错误 response 的 SHA-256。

- Lionel 的 batch 1 允许 c8–c15，返回四行，其中第二行引用 c7，内容是偏好咖啡而非啤酒。整批在 admission 前被拒绝。
- Miriam 的 batch 0 允许 c0–c7，唯一返回行引用 c12，内容是偏好安静晨跑。同样在 admission 前被拒绝。
- 两者均只有一次抽取请求；HTTP 200、完整 usage、非截断。不是网络失败、字段错层、写入异常或审计器误报。
- 当前 `Extractor::extract_llm` 和 `claim_batch_integrity` 仅将 `envelope_failure`、`schema_failure` 列入协议纠错。`batch_scope_failure` 立即终止。因此已经配置的一次纠错预算未用于修正批外引用。
- 四库合计 40 名 holder，38 名完整；99 个 belief 尝试含两个批外引用错误，没有 schema 错误。这是已执行子集的描述，不能推断未执行库全部健康，也不能证明布局改善的因果关系。

第四库 18 名 holder 中 16 名完整。数据库仍含独立通道与其他 holder 的合法记录，不能当成完整 baseline 库。两个失败 holder 的 belief 原子性边界保持，不通过删除越界行或修改 clause id 挽救原始结果。

## R6.0 执行偏差及证据限制

1. 原设计要求旧/新三 holder 交错对照；实际执行了候选单臂前两库。该结果只能说明两库可运行性，不是配对实验，也未按原计划证明所有指定 holder 的非空准入。
2. `run_socialmem_r60_expanded.py` 仍用 R5.8 探测作资格输入，放宽了 core 身份检查；新 probe 未被 build 硬门禁绑定，也缺少独立完整 check/finalize。这些入口不能作为新候选晋级已被完整验证的证据。
3. 常规 build/venv core 被更新为 `600a17182d920d4a7379892eec5440dec4409516352c3fee4750f70706ceaf27`，未按计划隔离构建。历史 R5.9 frozen core 保留。固定旧 SHA 的 R5.9 测试因此失败，不应放宽历史 SHA 门禁。
4. 上一阶段本机 C++ 执行为 1357 项发现、1334 通过、23 跳过；不是所有测试均执行。新 Python 入口六项测试覆盖身份和入口边界，不足以验证完整运行器。
5. `r60-layout-red.log` 是事后摘要，不能称原始 RED 日志；原布局测试尚缺 evidence 键序和整段恢复比较等承诺的断言。旧实施审查对覆盖和晋级的肯定需要以上述限制修正。

## 后续闭环

先在独立 R6.1 候选中验证目标批次的有界来源纠错，保持一次总协议额度，不修改 parser/admission，不静默搬移证据或吞掉错误行。先中文设计、真实失败测试、C++ 实现，再做旧/新完整 holder 验证。候选探测必须具备原始 HTTP、原生回放、预算及 core/source 绑定；健康且非空后再实现其正式建库准入。任何新失败保存阴性结果，不复用健康子库拼接不同 core 的 baseline。最后仍须统一 core 的 8/8 新建库、266 检索和 532 fresh QA。

## 语义保留的下一处能力短板（静态诊断，尚未修复）

四库已执行部分的249条本地语义拒绝中，147条缺QUESTIONED标记（59.0%），45条缺CONDITIONAL标记（18.1%）。这些计数是拒绝记录的分布，不是误拒率；同一来源的多个候选可重复计数，且后批失败的候选不等于已写入声明。聚合明细见 `diagnosis/semantic-rejection-patterns.json`。

至少存在需要复核的作用域过宽模式：一个完整turn中包含独立问句，系统就要求同turn中陈述性的心理状态也带QUESTIONED。例如 Mum 的原文“Has anyone heard from your father today? He's being very quiet and I'm slightly worried.”，候选“slightly worried about your father being very quiet today”因缺QUESTIONED被拒绝。Imogen 对办大聚会组织负担的判断也被后一句对母亲的提问影响。另一方面，“Should we do something special?”本身可能并不支持已明确的行动犹豫，不能把所有QUESTIONED拒绝一律放行。

因此，完成健康baseline之后，下一阶段应区分“整轮来源定位”和“候选所依附子句的断言作用域”，用对照用例验证独立陈述、真实问题、条件结果、引用、共现否定等边界。只增加谓词种类无法解决此类状态丢失。本轮先修建库终止机制，不同时改语义准入；后续需中文设计、反例测试与C++实现，再评估召回、错误接纳和QA差量。
