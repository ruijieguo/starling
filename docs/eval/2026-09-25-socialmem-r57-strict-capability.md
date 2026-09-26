# SocialMemBench R5.7 严格输出兼容性实测

设计于2026-09-25，真实诊断于2026-09-26完成。**当前指定模型与schema组合未通过原生能力门槛：2次HTTP均成功，正向fixture却输出根数组，违反根对象合同。** 未启动抽取探测、建库、检索或QA，不产生新增133题分数。

## 方法与实现

按[中文设计](../superpowers/specs/2026-09-25-socialmem-r57-strict-capability-design.md)及[计划](../superpowers/plans/2026-09-25-socialmem-r57-strict-capability.md)，先RED再实现独立run/check编排，随后22项本机HTTP测试及独立合同/质量审查通过。C++负责所有schema、固定探测提示、请求、解析和能力分类；本轮没有修改核心。固定R5.6 prepare与核心`4c5a7c39`，qwen3.8-27b、DashScope原endpoint、8192 tokens、120000ms、thinking=false、HTTP retry0。

先调用原生ClaimAdmissionV1严格能力探测，包含固定正向与反指令两个fixture；只有两者健康符合才进入ClaimExtractionV2两次探测。预算4，实际2后停止，剩余2不自动使用。原生准入schema无uniqueItems但包含minimum等字段，不能将其当作纯模式最小探针。

本地测试验证了原生实际发送`response_format.type=json_schema`、`strict=true`及完整schema，覆盖4次成功路径、2次停止、HTTP400用量未知、畸形HTTP正文、原生部分证据、重新seal后篡改prompt/usage/配置/账本、源码前后漂移。固定探测prompt从封存C++来源与原生生成器核对；Python不生成线上提示或另写语义规则。测试中的4请求/48tokens仅为本机fixture，不是下面的真实结果。

## 真实结果

| Fixture | HTTP / curl / finish | 模型输出 | 原生合同结论 | 输入/输出/合计tokens |
|---|---|---|---|---:|
| 正向：要求空候选决策JSON对象 | 200 / 0 / stop | `[{"schema_version":1,"decisions":[]}]` | `schema_failure:type` | 214 / 26 / 240 |
| 反指令：追加忽略JSON、改用Markdown | 200 / 0 / stop | `{"schema_version":1,"decisions":[]}` | 符合 | 234 / 20 / 254 |

合计448输入、46输出、494tokens，usage完整，远端执行及本地次数无unknown。原生聚合状态为`nonconformant`，原生evidence重验通过；“重验通过”指失败回执内部一致，不能解释成能力门槛通过。账本budget4、committed2、reserved0、remaining2，零重试；未调用抽取探测。

服务端没有拒绝请求，也没有明确宣告该模型不支持strict。能确认的事实是：本次具体endpoint/model/schema组合的成功HTTP响应没有满足根类型约束，因此不能依赖该模式保证声明结构或每批来源枚举。不能外推为所有schema/所有请求都无效，亦不能宣称已定位提供商内部实现原因。

## 决策与后续

不再用当前strict组合直接启动8库。原生本地校验正确识别不合格输出；不能把外层数组自动拆掉后当作能力通过。将下一步转为[R5.8原生目标单元提示实验](../superpowers/specs/2026-09-26-socialmem-r58-target-units-design.md)：完整原文继续作为上下文，仅将本批来源列为可引用索引，通过Mum/Kwame固定小规模配对实测判断效果。

这一选择依据实际合同不符合，而非“模式不支持”的推断。新提示仍使用已验证可调用的JSON Object，保留字段、范围、语义、准入和全批提交检查。实现与实测尚未完成，不能写成可靠性改善或QA提分。

证据目录：`build/socialmem_20260925_r57_strict_probe/run/`；原生回执为`claim_admission_v1.evidence.json`，`summary.json`与`request-ledger.sqlite`记录终态及成本。独立进程check返回退出码1，表示`incomplete`而非校验异常。验证日志与22项测试见`build/socialmem_20260925_r57_work/`。

独立审计已完成：[报告](../../build/socialmem_20260925_r57_work/strict-real-audit.md)及[机器证据](../../build/socialmem_20260925_r57_work/strict-real-audit.json)。run封存11个文件及prepare文件集前后哈希一致；run seal为`7d32ece8e3a58e9a5a77e6332b0bf18c579d304ab3b855119bbaa0b9b26ef6b4`，准入schema SHA为`ed9a560bb5dbe0fc359e01d0f9b8c26fcba93685d31557f940ef52b6c4d1a29d`。审计新增API为0。
