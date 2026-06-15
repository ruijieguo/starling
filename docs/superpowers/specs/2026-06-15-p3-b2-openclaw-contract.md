# P3.b2 OpenClaw memory 插件契约(Task 3 探查产出)

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
