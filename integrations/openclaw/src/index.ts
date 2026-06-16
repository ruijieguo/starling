/**
 * Starling memory plugin for OpenClaw — full hybrid runtime entry (P3.b2).
 *
 * Claims the `plugins.slots.memory` slot via manifest `kind:"memory"` +
 * `definePluginEntry({ kind:"memory" })` and wires all seven memory
 * capabilities (contract docs/superpowers/specs/2026-06-15-p3-b2-openclaw-contract.md):
 *
 *   search / get / index → registerMemoryRuntime(MemoryPluginRuntime)
 *   recall (auto-inject)  → api.on("before_agent_start")  → prependContext
 *   capture               → registerTool("memory_store")  → POST /api/remember
 *   flush (pre-compaction)→ registerMemoryFlushPlan + api.on("before_compaction")
 *   remove                → registerTool("memory_forget")  → POST /api/forget
 *
 * Reads degrade (StarlingClient returns []/null on a dashboard outage, never
 * throws), so a not-yet-reachable backend cannot interrupt an agent turn.
 * The token is read from config and used only as a Bearer header inside the
 * client; it is never logged or surfaced.
 */
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { Type } from "@sinclair/typebox";

import type { OpenClawPluginApi } from "openclaw/plugin-sdk/memory-core";
import { parseConfig, configSchema } from "./config.js";
import type { StarlingMemoryConfig } from "./config.js";
import { StarlingClient } from "./client.js";
import {
  makeStarlingRuntime,
  buildPromptSection,
  buildFlushPlan,
} from "./runtime.js";
import { workingSetToContext, collectUserText } from "./map.js";

/**
 * Reads a required string field from an OpenClaw-validated tool params object.
 *
 * The host validates raw tool-call arguments against the tool's TypeBox
 * `parameters` schema before invoking `execute`, but the runtime-neutral
 * `AnyAgentTool.execute` signature types `params` as `unknown`. This narrows it
 * back to the validated shape without an `as` cast on the whole object.
 */
function readStringField(params: unknown, key: string): string {
  if (params !== null && typeof params === "object" && key in params) {
    const v = (params as Record<string, unknown>)[key];
    if (typeof v === "string") return v;
  }
  return "";
}

/**
 * Wires the plugin's capabilities onto the OpenClaw api. Exported separately from
 * definePluginEntry so the registration can be unit-tested with a mock api (see
 * test/wiring.test.ts) rather than only through docker.
 */
export function wirePlugin(
  api: OpenClawPluginApi,
  cfg: StarlingMemoryConfig,
  client: StarlingClient,
): void {
  const rt = makeStarlingRuntime(cfg, client);

  // Unified memory capability (2026.6.6): runtime (search/get/index) + prompt
  // section + flush plan in one call. Replaces the deprecated
  // registerMemoryRuntime / registerMemoryPromptSection / registerMemoryFlushPlan
  // trio that left the plugin as a "non-capability shape" in `plugins doctor`.
  api.registerMemoryCapability({
    runtime: rt,
    promptBuilder: buildPromptSection,
    flushPlanResolver: buildFlushPlan,
  });

  // capture — runtime has no write method, so expose a tool.
  api.registerTool(
    {
      name: "memory_store",
      label: "Memory Store",
      description: "Save durable info into Starling.",
      parameters: Type.Object({ text: Type.String() }),
      async execute(_toolCallId, params) {
        const text = readStringField(params, "text");
        await client.remember(text, cfg.holder);
        return { content: [{ type: "text", text: "Stored." }], details: {} };
      },
    },
    { name: "memory_store" },
  );

  // remove — runtime has no delete method, so expose a tool. memoryId is the
  // statement id surfaced as a search-result citation.
  api.registerTool(
    {
      name: "memory_forget",
      label: "Memory Forget",
      description: "Forget a memory by its id.",
      parameters: Type.Object({ memoryId: Type.String() }),
      async execute(_toolCallId, params) {
        const memoryId = readStringField(params, "memoryId");
        await client.forget([memoryId]);
        return {
          content: [{ type: "text", text: "Forgotten." }],
          details: {},
        };
      },
    },
    { name: "memory_forget" },
  );

  // recall — auto-inject the Starling working set as prepended context.
  if (cfg.autoRecall) {
    // before_prompt_build is the modern prompt-injection hook (2026.6.6);
    // before_agent_start is deprecated for new work. holder = cfg.holder so the
    // working set matches the holder we capture under.
    api.on("before_prompt_build", async () => {
      const ws = await client.workingSet(cfg.holder, cfg.holder);
      return ws ? { prependContext: workingSetToContext(ws) } : {};
    });
  }

  // capture (flush) — Starling self-persists the recent user-stated window in
  // parallel with OpenClaw's compaction. before_compaction exposes `messages`
  // (and `sessionFile`); we distil the recent user text. Full sessionFile JSONL
  // ingestion remains a follow-up.
  if (cfg.autoCapture) {
    api.on("before_compaction", async (event) => {
      const text = collectUserText(event.messages);
      if (text) {
        await client.remember(text, cfg.holder);
      }
    });
  }
}

export default definePluginEntry({
  id: "starling",
  name: "Starling Memory",
  description: "Starling-backed long-term cognitive memory",
  kind: "memory",
  configSchema,
  register(api) {
    // D: config arrives on api.pluginConfig and is validated by our own parser.
    const cfg = parseConfig(api.pluginConfig);
    const client = new StarlingClient(cfg);
    wirePlugin(api, cfg, client);
  },
});
