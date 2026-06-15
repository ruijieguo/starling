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

import { parseConfig, configSchema } from "./config.js";
import { StarlingClient } from "./client.js";
import {
  makeStarlingRuntime,
  buildPromptSection,
  buildFlushPlan,
} from "./runtime.js";
import { workingSetToContext } from "./map.js";

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
    const rt = makeStarlingRuntime(cfg, client);

    // search / get / index — the MemorySearchManager-backed runtime (real
    // MemoryPluginRuntime type; the skeleton's whole-object `as` cast is gone).
    api.registerMemoryRuntime(rt);
    // Advertise the write/remove tools in the memory system-prompt section.
    api.registerMemoryPromptSection(buildPromptSection);
    // Pre-compaction flush plan resolver (the agent self-writes a durable note).
    api.registerMemoryFlushPlan(buildFlushPlan);

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
      api.on("before_agent_start", async () => {
        // holder = cfg.holder so the working set is built for the same holder
        // we capture under (matches the dashboard holder dimension).
        const ws = await client.workingSet(cfg.holder, cfg.holder);
        return ws ? { prependContext: workingSetToContext(ws) } : {};
      });
    }

    // capture (flush) — Starling self-persists the transcript in parallel with
    // OpenClaw's compaction. The before_compaction event exposes `sessionFile`
    // (a JSONL transcript already on disk) and an in-memory `messages` array.
    //
    // MVP: rather than parse the full JSONL transcript here, capture the last
    // user-authored message text (when present in `event.messages`) as a single
    // durable memory. Full transcript ingestion from `event.sessionFile` is a
    // follow-up (the file path is acknowledged below but not yet streamed).
    if (cfg.autoCapture) {
      api.on("before_compaction", async (event) => {
        // event.sessionFile is the on-disk JSONL transcript; full-file ingestion
        // is deferred. For now, persist the latest user message if available.
        const text = lastUserMessageText(event.messages);
        if (text) {
          await client.remember(text, cfg.holder);
        }
      });
    }
  },
});

/**
 * Best-effort extraction of the most recent user-authored message text from the
 * before_compaction event's `messages` array (typed `unknown[]` by the host).
 *
 * Walks from the end, returning the first `{ role: "user" }` entry whose content
 * is a non-empty string, or the concatenated text blocks of an array content.
 * Returns "" when nothing usable is found — the caller then skips the write.
 */
function lastUserMessageText(messages: unknown[] | undefined): string {
  if (!Array.isArray(messages)) return "";
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m === null || typeof m !== "object") continue;
    const rec = m as Record<string, unknown>;
    if (rec["role"] !== "user") continue;
    const content = rec["content"];
    if (typeof content === "string") {
      const t = content.trim();
      if (t) return t;
      continue;
    }
    if (Array.isArray(content)) {
      const parts: string[] = [];
      for (const block of content) {
        if (
          block !== null &&
          typeof block === "object" &&
          (block as Record<string, unknown>)["type"] === "text"
        ) {
          const bt = (block as Record<string, unknown>)["text"];
          if (typeof bt === "string") parts.push(bt);
        }
      }
      const joined = parts.join("\n").trim();
      if (joined) return joined;
    }
  }
  return "";
}
