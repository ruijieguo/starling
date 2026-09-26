<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# P3.b2 OpenClaw memory 插件契约(Task 3 探查产出)
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

**日期:** 2026-06-15
**来源:** OpenClaw v2026.x `/opt/homebrew/lib/node_modules/openclaw/dist/`,引自 `plugin-sdk/src/plugins/types.d.ts`、`plugin-sdk/src/plugins/memory-state.d.ts`、`plugin-sdk/packages/memory-host-sdk/src/host/types.d.ts`、`plugin-sdk/src/plugin-sdk/plugin-entry.d.ts`,以及两个参考实现 `extensions/memory-core/index.js`(runtime 路线)、`extensions/memory-lancedb/index.js`(纯 tool 路线)。
**决策:** Starling 用 **hybrid runtime 路线**(用户 2026-06-15 裁定)——真正的 drop-in memory provider。

## A. 占槽机制

插件靠 manifest `kind:"memory"`(`openclaw.plugin.json`)+ `definePluginEntry({kind:"memory",...})` 占据 `plugins.slots.memory` 槽(`docs/plugins/manifest.md:271`)。`plugins.slots.memory="none"` 禁用。注册 **不是** 单一 god-object,而是 composite:三个 memory 专属注册器(exclusive slot)+ 通用 `registerTool`/`registerCli`/`registerService`/`api.on`。

## B. 七能力 → OpenClaw 落点 + 确切签名

**核心鸿沟:** `MemorySearchManager` 是**文件/行读模型**,**无 write/delete 方法**。Starling statement(subject/predicate/object)须映射进 file/line。

```ts
// registerMemoryRuntime(runtime) 收的对象 — memory-state.d.ts:36-50
type MemoryPluginRuntime = {
  getMemorySearchManager(params: { cfg: OpenClawConfig; agentId: string; purpose?: "default"|"status" })
    : Promise<{ manager: MemorySearchManager | null; error?: string }>;
  resolveMemoryBackendConfig(params: { cfg: OpenClawConfig; agentId: string }): MemoryRuntimeBackendConfig;
  closeAllMemorySearchManagers?(): Promise<void>;
};
// getMemorySearchManager 返回的 manager — host/types.d.ts:71-95
interface MemorySearchManager {
  search(query: string, opts?: { maxResults?: number; minScore?: number; sessionKey?: string })
    : Promise<MemorySearchResult[]>;
  readFile(params: { relPath: string; from?: number; lines?: number }): Promise<{ text: string; path: string }>;
  status(): MemoryProviderStatus;
  sync?(params?: { reason?: string; force?: boolean; sessionFiles?: string[];
                   progress?: (u: MemorySyncProgressUpdate) => void }): Promise<void>;
  probeEmbeddingAvailability(): Promise<MemoryEmbeddingProbeResult>;
  probeVectorAvailability(): Promise<boolean>;
  close?(): Promise<void>;
}
// search 结果行 — host/types.d.ts:2-10
type MemorySearchResult = { path: string; startLine: number; endLine: number;
  score: number; snippet: string; source: "memory"|"sessions"; citation?: string };
```

| Starling 能力 | OpenClaw 落点(注册器/方法) | dashboard API | 适配规则 |
|---|---|---|---|
| **search** | `MemorySearchManager.search()` (registerMemoryRuntime) | `POST /api/recall` `{query,k:maxResults}` | recall `{results:[{subject,predicate,object,score}]}` → `MemorySearchResult[]`:`path="statement://<tenant>/<id>"`(synthetic 稳定)、`startLine=endLine=0`、`snippet="<subject> <predicate> <object>"`、`score`、`source:"memory"`、`citation=<id>` |
| **get** | `MemorySearchManager.readFile()` | `GET /api/statement/{id}` | `relPath`(=search 给的 `statement://.../<id>`)解析出 id → statement → `{text:渲染文本, path:relPath}`;ENOENT 降级 `{text:"",path}` |
| **index** | `MemorySearchManager.sync()` | `POST /api/tick` | 触发嵌入/巩固维护(Starling 已后台自管,可轻量调 tick 或 no-op) |
| **recall**(auto-inject) | `api.on("before_agent_start", h)` → `{prependContext}` | `GET /api/working_set` | working_set `render` → `prependContext` 字符串。结果类型 `PluginHookBeforePromptBuildResult.prependContext?:string`(types.d.ts:1593) |
| **capture** | `registerTool({name:"memory_store",...})` | `POST /api/remember` | tool params `{text}` → remember,`holder`=agent id;OpenClaw runtime 无 capture 方法,必走 tool |
| **flush**(pre-compaction) | `registerMemoryFlushPlan(resolver)` (+ 可选 `api.on("before_compaction")`) | `POST /api/remember` | 见 E。plan 让 agent 自己写;若 Starling 要自持久化 transcript,用 before_compaction hook 的 `sessionFile` |
| **remove** | `registerTool({name:"memory_forget",...})` | `POST /api/forget` | tool params `{memoryId}`(=statement id,来自 search citation) → `forget {ids:[memoryId]}`;runtime 无 delete,必走 tool |

`status()` → Starling dashboard `GET /api/overview` 或固定 ok;`probeEmbeddingAvailability/probeVectorAvailability` → 查 dashboard config 的 embedder/vector_backend 是否就绪(reads 降级:不可达返回 unavailable,不抛)。

## C. `definePluginEntry` + `register(api)` skeleton

`definePluginEntry` 是真实导出函数(`plugin-entry.d.ts:7-22`,`openclaw/plugin-sdk/plugin-entry`)。`integrations/openclaw/src/index.ts` 骨架(仿 memory-core/index.js:409-435):

```ts
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { Type } from "@sinclair/typebox";
import { configSchema } from "./config.js";
import { makeStarlingRuntime, buildPromptSection, buildFlushPlan } from "./runtime.js";

export default definePluginEntry({
  id: "starling", name: "Starling Memory",
  description: "Starling-backed long-term cognitive memory",
  kind: "memory", configSchema,
  register(api) {
    const cfg = configSchema.parse(api.pluginConfig);   // D: config 经 api.pluginConfig
    const rt = makeStarlingRuntime(cfg, api);           // 内含 StarlingClient
    api.registerMemoryRuntime(rt);                       // search/get/index
    api.registerMemoryPromptSection(buildPromptSection);
    api.registerMemoryFlushPlan(buildFlushPlan);         // E
    api.registerTool({ name:"memory_store", label:"Memory Store",
      description:"Save durable info into Starling.",
      parameters: Type.Object({ text: Type.String() }),
      async execute(_id, p) { /* client.remember(p.text) */ return { content:[{type:"text",text:"Stored."}], details:{} }; }
    }, { name:"memory_store" });
    api.registerTool({ name:"memory_forget", label:"Memory Forget",
      description:"Forget a memory by id.",
      parameters: Type.Object({ memoryId: Type.String() }),
      async execute(_id, p) { /* client.forget([p.memoryId]) */ return { content:[{type:"text",text:"Forgotten."}], details:{} }; }
    }, { name:"memory_forget" });
    if (cfg.autoRecall) api.on("before_agent_start", async (e, ctx) => ({ prependContext: /* working_set */ "" }));
    if (cfg.autoCapture) api.on("before_compaction", async (e, ctx) => { /* persist e.sessionFile transcript */ });
  },
});
```

`OpenClawPluginApi`(types.d.ts:1481-1547)在 `register` 内可用:`id,name,source,config:OpenClawConfig,pluginConfig?:Record<string,unknown>,logger,resolvePath(input),runtime`,以及全部 `register*`/`on`。tool 对象形(lancedb index.js:6829-6867):`{name,label,description,parameters(TypeBox schema),execute(toolCallId,params)=>{content:[{type:"text",text}],details}}`。

## D. config 注入

config 落在 `api.pluginConfig: Record<string,unknown>`(types.d.ts:1490),用自己的 `configSchema.parse(api.pluginConfig)` 校验(lancedb index.js:6823 同款)。entry 的 `configSchema` 是运行时 parser(`{parse?,safeParse?,validate?,uiHints?,jsonSchema?}`,Zod/TypeBox 兼容);manifest 的 `openclaw.plugin.json configSchema` 是 JSON-Schema(校验/doctor/UI,`uiHints` 标 `sensitive`/`advanced`)。用户 config 供在 `plugins.<id>` 下。Starling 字段:`dashboardUrl`(required)、`token`(required,sensitive)、`tenant`、`holder`、`autoRecall`、`autoCapture`。`api.resolvePath` 把相对路径转绝对。

## E. pre-compaction flush

```ts
// memory-state.d.ts:8-19
type MemoryFlushPlan = {
  softThresholdTokens: number; forceFlushTranscriptBytes: number; reserveTokensFloor: number;
  prompt: string; systemPrompt: string; relativePath: string;   // 如 "memory/2026-06-15.md"
};
type MemoryFlushPlanResolver = (params: { cfg?: OpenClawConfig; nowMs?: number }) => MemoryFlushPlan | null;
```
plan 模型:OpenClaw 跑 silent agentic turn 让 **agent 自己**写文件到 `relativePath`(memory-core/index.js:112-134:softThresholdTokens=4000、forceFlushTranscriptBytes=2MiB、reserveTokensFloor=20000,prompt 末尾带 NO_REPLY)。**Starling 自持久化路线:** 用 `api.on("before_compaction", h)`(types.d.ts:1645-1656),`event.sessionFile`(JSONL transcript 已落盘)→ 异步读 + `POST /api/remember`,与 compaction LLM 并行。

## 路线决策与边界

- **hybrid:** registerMemoryRuntime(search/get/index 经 MemorySearchManager)为骨架 → 白盒复用 builtin `memory_search`/`memory_get` 工具、`memory` CLI、status/doctor、embedding 接线;`registerTool`(memory_store/memory_forget)补 runtime 缺的写/删;FlushPlan + hooks 补 flush/recall/capture。
- **synthetic path 不变式:** `path="statement://<tenant>/<id>"` 必须稳定且可反解出 id(get/remove 依赖)。OpenClaw 用 path 去重/引用。
- **reads 降级:** search/get/working_set 经 StarlingClient,dashboard 不可达 → 空结果 + warn,不抛(不中断 agent)。writes(capture/remove)→ 本地重试队列。
- **不实现:** registerMemoryEmbeddingProvider(Starling 自带 embedder);Markdown 双写(Starling 接管槽)。

## 2026.6.6 类型核对补注(Task 3 骨架后)

契约主体引自本机全局 OpenClaw **2026.3.28**;Task 3 骨架本地 `npm install` 拉到 **2026.6.6**(integrations/openclaw lockfile 锁定)。两版签名一致编译通过,但以 **2026.6.6** 为实现基准(docker 集成 Task 7 须 pin 同版本)。核对结论:

- **`MemorySearchManager` 确有 `search`/`readFile`**(`dist/plugin-sdk/memory-state-BiCvbkji.d.ts:104-131`):`getMemorySearchManager` 返回 `{manager: MemorySearchManager|null}`,interface = `search(query,opts?{maxResults,minScore,sessionKey,signal,...})→Promise<MemorySearchResult[]>` + `readFile({relPath,from?,lines?})→Promise<MemoryReadResult>` + `status()` + `sync?` + `probeEmbeddingAvailability()` + `probeVectorAvailability()` + `close?`。**§B 正确。** ⚠️ Task 3 骨架用 `runtime as Parameters<typeof registerMemoryRuntime>[0]` 整体断言绕过了 manager 类型检查,故 stub 未实现 search/readFile 也编译过——**Task 6 必须实现真实 search/readFile**(否则运行时 OpenClaw 调 `manager.search` 失败)。
- **`MemoryProviderStatus.backend` 限 `"builtin"|"qmd"`**(:50-102),非任意字符串。Starling 作外部 provider 宜报 `backend:"qmd"`、`provider:"starling"`、`vector:{enabled,available,dims}`(反映 dashboard embedder/vector 就绪)。
- **`MemoryReadResult`** = `{text,path,truncated?,from?,lines?,nextFrom?}`(:41-48,比 §B 的 `{text,path}` 多分页 optional 字段)。
- **备选 `registerMemoryCorpusSupplement`**(`MemoryCorpusSupplement.search→MemoryCorpusSearchResult{corpus,path,score,snippet,id?,startLine?,endLine?,citation?}`、`.get→MemoryCorpusGetResult`):corpus 结果**原生带 `id`**,比 MemorySearchManager 的 synthetic path 更贴 statement 模型。Task 6 可评估主用 runtime(MemorySearchManager)还是 corpus supplement,或并用(runtime 占主槽 + corpus 补 statement 检索)。
