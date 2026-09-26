<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.6：同输入分批抽取验收

日期：2026-09-25。此文补充分批核心设计，限定首次真实请求范围；不等于133题评测方案。

## 固定输入与核心

只使用R5.5 Kwame失败输入，来源为已独立核验的容量预检封存目录`build/socialmem_20260925_r55_capacity_probe`，seal SHA-256 `7c6f48b79f05d960201c5d2a9f13312c1c6c17686c4c8021236ff317aa888a04`。原payload SHA `739a240bde63ee1286da19474305fb620be683fd48f4bf29defd3144cac7fab9`，12133字节、33个source units；原prompt SHA `615351de9d8c0a8e477232190d6b95c05c9848623482d3d4a0e5467c0b4cb52a`。先严格核验全部封存文件和输入DB的engram内容、holder和source hash。

在新prepare目录冻结已测试的新C++核心、当前Python binding与源码/构建证据。新核心的未分批claim_extraction_prompt必须与原prompt逐字一致；分批仅通过原生planner和新增目标指令改变抽取范围。原生8单元planner须产生5批和15次belief请求上界。Python不得自行规划/修JSON/重做语义过滤。prepare/check禁止构造provider或发送请求。

## 真实执行边界

新增入口`prepare/check/run`，输出拒覆盖，不自动续跑。运行在新临时数据库，原生remember_prepare保留source→memory_extract_llm分批belief+admission→memory_remember_commit原生全批写入。即使抽取失败也提交原生失败审计，必须零claim入库。结束用SQLite backup保存稳定数据库快照，避免live WAL导致封存漂移。

固定模型qwen3.8-27b，抽取8192 token、120000ms、thinking=false、HTTP retry0、claim_batch_size=8、协议纠正预算1、ClaimExtractionV2/json_object。参数从原配置继承，其余不漂移。本入口只测belief，最多15次本地HTTP尝试；无general_fact、episodic、embedding、retrieval、answer或judge调用。预算一次预留15，正常按逐原生回执的attempt_count结算；异常或回执不全按上界计账并明确未知。不能把保守扣账当观测调用。远端execution_certainty=unknown与本地attempt数分列；usage缺失不能写成消费0。

## 成功与失败判定

成功需要原生batch完成性通过、5批均成功、所有原生HTTP回执健康且无截断/拒绝；协议恢复前失败须单列，不隐瞒原始响应。原生commit非失败且至少1条合格claim真正入库，DB数量/ID与commit回执一致，每条证据仍绑定同一原始engram/hash/span。所有来源单元有且只有一个负责批，不要求每单元必须生成claim；语义拒收和admission拒收均单列。Python只核验原生决定及持久结果，不解析/生成声明语义。

任何批传输或截断失败后不自动重试，不继续未到达批、不增加额度；封存全部已得到的原生receipt与本地计账。若失败仅得失败诊断，不开展8库/QA。成功只证明同输入分批抽取及写入完成，不能宣称完整语义召回、133题建库健康或问答准确率提升。

## 测试顺序

先失败测试覆盖：父seal/payload/core/参数/规划漂移零请求；prepare与check离线；拒覆盖；单次原生入口与15上界；多次HTTP真实计数及unknown用量；后批失败0claim、原始回执不丢；成功写入及DB稳定封存；输入/依赖请求前后漂移拒收。新核心可用后做真实C++加FakeLLM离线集成，再执行一次既有授权的有界run。
