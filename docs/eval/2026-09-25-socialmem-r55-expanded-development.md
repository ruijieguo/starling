# SocialMemBench R5.5：扩大开发验证报告

日期：2026-09-25。当前状态：设计→失败测试→实现→独立合同与质量审查已完成，主流程102项回归通过。固定133题输入已封存验核；首轮真实建库在第二scope因输出截断停止，失败产物完整封存。独立16384容量预检随后发生传输失败并封存，未重试。检索与fresh QA未执行，尚无新增分数。

## 已核验的边界

R5.4 封存再次通过离线核验；旧57题的legacy为18/57→23/57，grounded_memory_v1为18/57→25/57。这是历史开发cohort结果，本报告不把它当作R5.5新增成绩。

本轮从33个开发网络中排除旧6个，按network ID的SHA-256顺序选取6个新增网络的全部题目，固定133题、8 scopes、65 holder-scope、1322话轮、106自由题。选样未参考新分数；数据曾属于历史开发评测范围，不能称为未见集。298题历史保留集未进入本轮样本。

样本共有263个题目—来源锚点；Q1至Q9题量分别25、10、1、10、12、8、24、40、3，其中Q3与Q9样本极少，分题型结果只作诊断。回答形式为27道选择题、20道短答、86道长答。独立输入盘点见[审计清单](../../build/socialmem_20260925_r55_work/input-independent-audit.json)。

8个历史frozen.db均为零statements的纯来源库，因此必须先重建结构化记忆才能得到健康v6 hybrid对照。Python仅新增编排与验收，C++核心沿用R5.4冻结版本。

## 执行合同

详见[设计](../superpowers/specs/2026-09-25-socialmem-r55-expanded-development-design.md)与[计划](../superpowers/plans/2026-09-25-socialmem-r55-expanded-development.md)。双臂为v6 hybrid k10与v9 sources k10，fresh QA为两臂×两policy共532终态。主要终点固定grounded_memory_v1全题准确率差值，技术失败计零；legacy为次要终点。

建库计账预算12000、检索查询嵌入1336、QA956。保守上界计账与实际HTTP请求分列，未执行预算不能写成实际成本。只有全部scope和检索健康才开始QA，不根据锚点是否提升决定QA资格。若失败，保留完整产物，阻断后续，不删题或混用历史得分。

## 执行前发现并修正的编排问题

- 人物级抽取成功状态未汇总episodic通道，新增逐通道HTTP/截断/回执检查；空结果与解析失败的原生歧义单列，不在Python补语义解析。
- 补齐episodic.response的实际请求和token计数，题型使用query_type，裁判翻转按真实judge输入分组。
- 真实WAL格式SQLite库仅以mode=ro读取仍会生成空WAL/SHM副文件，导致第二次健康检查失败。已用临时真实库副本复现；修复采用immutable只读并显式关闭。会话核验生成的14个副文件已可恢复归档，7个历史主DB SHA与R5.4封存清单全部一致，R5.4验封恢复通过。

## 验证与执行记录

新增R5.5编排测试50项，加R5.4相关回归52项，主流程复验102/102通过。离线fixture覆盖8库、266检索、532 QA与956请求计账，这些是编排测试，不是真实模型成绩。另有真实原生核心+FakeLLM的跨进程封存测试。证据见[最终回归](../../build/socialmem_20260925_r55_work/root-final-regression.log)。

prepare阶段零请求并已验封，seal SHA-256为`66b13d7e22b0794903467d9ea89f21b91379118d43866b4504b49fd9bd0178d0`。[首轮真实建库日志](../../build/socialmem_20260925_r55_work/build.log)已终止：1个scope健康、1个partial、6个未执行；8库完整健康门槛未通过。

## 首轮真实建库失败与恢复

Kwame的belief响应为HTTP200，但finish_reason=length，8192个completion token，耗时113595ms，原生适配器标记completion_truncated。该holder的33条话轮正文仅6926字节，最大话轮321字节；完整prompt为22123 token。输出有40个完整statement对象和第41个半对象，前40个无重复，来源单元从c0单调推进到c17，只覆盖18/33；字符串外格式空白占32.1%。这些仅作离线诊断，截断响应未修补或写作合格声明。

按观测密度粗估完整输出约15019 token，不是供应商容量保证。先执行[独立容量恢复预检](../superpowers/specs/2026-09-25-socialmem-r55-capacity-recovery-design.md)：相同core、模型、prompt和原生合同，只将单次抽取容量升至16384、该请求超时240000ms，最多1次请求。成功也只证明该输入可完整返回，不代表133题建库或问答成功。

| 首轮范围 | 状态 | 声明/向量 | 模型请求 | 嵌入请求 | 观测模型token |
|---|---|---:|---:|---:|---:|
| grp_7a8b9c0d / ae45ef45 | 健康 | 28/28 | 16 | 3 | 113942 |
| grp_a5b6c7d8 / 1c2838ef | partial，Kwame belief截断 | 163/163 | 35 | 21 | 434863 |

合计51次模型HTTP+24次native嵌入计数=75次观测请求；548805个模型token不含缺失的embedding usage。账本117保守抽取单位+24实际嵌入=141单位，reserved=0。partial库即使163条声明都有向量也未获准进入检索，证明健康门槛没有把部分成功冒充完整baseline。

失败seal `75b2f99f02253a11ea8c03f025a1f6f440bf9e594624eb1e6d06ce6b319af522` 的1202个文件清单及hash全部复验一致。首scope独立审计见[报告](../../build/socialmem_20260925_r55_work/first-scope-independent-audit.md)，截断专项见[诊断](../../build/socialmem_20260925_r55_work/truncation-diagnosis.md)。

## 单次16384容量预检结果

已按先文档、失败测试、实现、合同/质量审查的顺序完成独立入口；probe测试34/34，联合回归136/136。主代理再次运行34项及真实冻结核心validate-only均通过且零请求。随后仅执行一次DashScope请求，结果为technical_failure：curl_code=56，http_status=0，execution_certainty=unknown，原生错误为`transport_error:Failure when receiving data from the peer`，耗时74938ms；响应正文与completion均为空。账本settled=1、reserved=0，输入前后核验通过，全部结果封存。

这里只能确认一次本地HTTP尝试，远端是否执行或完成未知。回执prompt/completion/total tokens均为0是缺失用量，不能写成实际消费为0。也不能把这次失败解释为16384容量不足，或用空响应的envelope_failure归因模型JSON能力。没有admission、embedding或QA请求，没有自动重试。[原始终态](../../build/socialmem_20260925_r55_capacity_probe/terminal.json)、[原生回执](../../build/socialmem_20260925_r55_capacity_probe/native-response.json)、[主代理回归](../../build/socialmem_20260925_r55_work/root-probe-regression.log)。

原8192响应已证实输出截断，但更高容量的充分性仍未知。下一步转向[R5.6 C++目标来源单元分批抽取](../superpowers/specs/2026-09-25-socialmem-r56-bounded-claim-design.md)，保留完整上下文与全局证据坐标，降低单次生成体量；这是一项待验证的可靠性改进，不能预先宣称可以消除传输失败或提高准确率。

## 当前结论

尚无扩大开发验证成绩，不能确认R5.4增益可迁移到新增网络。后续依据实际健康检查、fresh QA及独立重算更新本报告；默认策略不自动变更。

后续原生分批实施与新证据集中于[R5.6报告](2026-09-25-socialmem-r56-bounded-claim.md)，本R5.5报告保留原失败轮的统计边界。
