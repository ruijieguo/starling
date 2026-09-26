<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.5：抽取输出容量恢复设计

日期：2026-09-25。状态：R5.5首轮在第二个scope的Kwame belief输出截断后停止；用户既有自主迭代及DashScope授权继续有效。先文档、失败测试，再实现与真实预检。

## 已确认的问题

首轮采用固定8192抽取token、120000ms超时。Kwame有33条话轮、6926字节正文，最大话轮321字节；实际prompt为22123 token。原始响应HTTP200、8192 completion token、耗时113595ms、finish_reason=length，原生适配器正确标记completion_truncated。scope因此partial，后续检索和QA均未启动。51次模型加24次嵌入为75实际请求，117保守抽取单位加24实际嵌入为141账本单位；失败seal已核验，不能把首个健康scope当133题成绩。

## 最小恢复选择

先执行一个严格绑定失败输入的容量预检：使用相同冻结C++核心、相同模型qwen3.8-27b、相同原始prompt及其hash、相同ClaimExtractionV2/json_object合同，仅将抽取max_tokens提高至16384、该预检请求timeout提高至240000ms，HTTP重试保持0，extract_enable_thinking=false；endpoint/model及其余参数从失败配置继承且逐项验证。最多一次模型请求，不做admission、嵌入、检索或QA。

不补全或修剪截断JSON。候选解析、来源资格、span验证继续调用C++ claim_parse_response；Python只核对封存、读取数据库payload、绑定hash、编排请求和保存原始回执。必须验证数据库payload SHA与失败receipt source_payload_hash一致，且C++重新生成prompt与失败请求逐字一致。所有依赖、输入hash、请求参数、响应和原生解析回执封存到新目录，拒绝覆盖；异常按1请求上界保守计账，保留未知状态；原生回执缺失时实际请求数标记未知，不能把保守1单位写成观测1次。

成功门槛：HTTP单次正常返回、finish_reason=stop、无适配器错误、C++解析errors为空（包括来源/span错误均不能忽略）且至少一条合格候选。语义拒收单列，不以候选越多越好作为成功标准。预检成功仅证明这个失败输入在更大输出预算下可完整解析，不证明抽取完整、admission通过、健康建库或问答提升。

若预检仍截断或失败，停止提高额度，依据原始响应设计C++有界分段或输出紧凑化；不能在Python复制此能力。若预检成功，下一步另冻结同一133题的完整新建库方案，使全部8库使用统一的新抽取容量；原首轮产物保留为失败诊断，不混用旧健康scope构造新成绩。回答512、裁判64及两种回答策略保持既有协议；真实扩大验证的主要终点与技术门槛不改。

## 测试与验收

先失败测试覆盖：错误failure/holder/payload/prompt/core拒绝且零请求；输出目录拒覆盖；一次请求上限、无隐式重试、长输出/异常保留失败终态；使用原生parse结果决定协议成功，不在Python重写claim parser。用真实冻结C++与FakeLLM验证绑定边界，再执行单次DashScope容量预检。同步所有设计文档中文状态入口与当前报告。
