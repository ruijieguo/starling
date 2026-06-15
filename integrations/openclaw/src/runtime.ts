/**
 * runtime.ts — Assembles a real OpenClaw MemoryPluginRuntime from a
 * StarlingMemoryConfig + StarlingClient.
 *
 * This is the search/get/index path of the hybrid memory provider:
 * `registerMemoryRuntime(makeStarlingRuntime(cfg, client))` plugs Starling in
 * behind the builtin `memory_search` / `memory_get` tools, the `memory` CLI,
 * and status/doctor surfaces.
 *
 * Capability mapping (contract §B):
 *   search   → MemorySearchManager.search  → POST /api/recall
 *   get      → MemorySearchManager.readFile → GET  /api/statement/{id}
 *   index    → MemorySearchManager.sync     → no-op (Starling self-maintains)
 *   status / probes → dashboard config snapshot (degrade, never throw)
 *
 * All reads degrade: StarlingClient returns []/null on a dashboard outage, so
 * a not-yet-reachable backend never interrupts an agent turn.
 */

// Real openclaw 2026.6.6 types. `MemoryPluginRuntime`, `MemoryFlushPlan`, and
// `MemoryPromptSectionBuilder` are re-exported by-name from the public
// `plugin-sdk/memory-core` subpath. The host-side manager/result/status/probe
// shapes and the backend-config union are NOT individually re-exported by name
// from any public subpath, so they are derived structurally (indexed-access)
// from `MemoryPluginRuntime` — these resolve to the genuine interfaces, with no
// `as` assertions and no fragile single-letter alias imports.
import type {
  MemoryPluginRuntime,
  MemoryFlushPlan,
  MemoryPromptSectionBuilder,
} from "openclaw/plugin-sdk/memory-core";

/** getMemorySearchManager() resolution — { manager: ... | null; error?: ... }. */
type GetManagerResult = Awaited<
  ReturnType<MemoryPluginRuntime["getMemorySearchManager"]>
>;
/** The registered manager (RegisteredMemorySearchManager = MemorySearchManager). */
type MemorySearchManager = NonNullable<GetManagerResult["manager"]>;
/** One ranked search hit — the element type of MemorySearchManager.search(). */
type MemorySearchResult = Awaited<
  ReturnType<MemorySearchManager["search"]>
>[number];
/** readFile() resolution — the genuine MemoryReadResult shape. */
type MemoryReadResult = Awaited<ReturnType<MemorySearchManager["readFile"]>>;
/** status() return — the genuine MemoryProviderStatus shape. */
type MemoryProviderStatus = ReturnType<MemorySearchManager["status"]>;
/** probeEmbeddingAvailability() resolution — genuine MemoryEmbeddingProbeResult. */
type MemoryEmbeddingProbeResult = Awaited<
  ReturnType<MemorySearchManager["probeEmbeddingAvailability"]>
>;
/** resolveMemoryBackendConfig() return — genuine MemoryRuntimeBackendConfig union. */
type MemoryRuntimeBackendConfig = ReturnType<
  MemoryPluginRuntime["resolveMemoryBackendConfig"]
>;

import type { StarlingMemoryConfig } from "./config.js";
import type { StarlingClient } from "./client.js";
import {
  decodePath,
  recallToSearchResults,
  statementToReadResult,
  type StatementRow,
} from "./map.js";

// ---------------------------------------------------------------------------
// Flush plan defaults (contract §E, mirrors memory-core/index.js:112-134)
// ---------------------------------------------------------------------------

/** Soft prompt-token threshold above which a pre-compaction flush is suggested. */
const SOFT_THRESHOLD_TOKENS = 4000;
/** Hard transcript-byte ceiling that forces a flush regardless of tokens (2 MiB). */
const FORCE_FLUSH_TRANSCRIPT_BYTES = 2 * 1024 * 1024;
/** Token floor the planner reserves so flushing never starves the live turn. */
const RESERVE_TOKENS_FLOOR = 20_000;

/** Marker appended to the flush prompt so the silent agentic turn stays silent. */
const NO_REPLY = "\n\nNO_REPLY";

// ---------------------------------------------------------------------------
// Statement-row coercion (dashboard rows are Record<string, unknown>)
// ---------------------------------------------------------------------------

/** Read a string field from an untrusted statement row, defaulting to "". */
function field(row: Record<string, unknown>, key: string): string {
  const v = row[key];
  return typeof v === "string" ? v : "";
}

/** Narrow a raw dashboard statement row into the StatementRow map() expects. */
function toStatementRow(row: Record<string, unknown> | null): StatementRow {
  if (row === null) {
    return { subject_id: "", predicate: "", object_value: "" };
  }
  return {
    subject_id: field(row, "subject_id"),
    predicate: field(row, "predicate"),
    object_value: field(row, "object_value"),
  };
}

// ---------------------------------------------------------------------------
// MemorySearchManager — search / readFile / status / sync / probes
// ---------------------------------------------------------------------------

/**
 * Builds the Starling-backed MemorySearchManager.
 *
 * @internal exported for unit tests; production code goes through
 * makeStarlingRuntime().getMemorySearchManager().
 */
export function makeStarlingManager(
  cfg: StarlingMemoryConfig,
  client: StarlingClient,
): MemorySearchManager {
  return {
    async search(
      query: string,
      opts?: { maxResults?: number },
    ): Promise<MemorySearchResult[]> {
      const k = opts?.maxResults ?? 10;
      // Recall under the SAME holder we capture with (cfg.holder), else the
      // dashboard's holder_id predicate excludes our own rows (P3.b2 root cause).
      const hits = await client.recall(query, k, cfg.holder);
      // recallToSearchResults already yields source:"memory" rows; satisfies
      // MemorySearchResult (source is the "memory" | "sessions" union member).
      return recallToSearchResults(hits, cfg.tenant);
    },

    async readFile(params: { relPath: string }): Promise<MemoryReadResult> {
      const decoded = decodePath(params.relPath);
      if (decoded === null || decoded.tenant !== cfg.tenant) {
        // Not a statement:// path we own, or a cross-tenant path — ENOENT-style
        // degrade with no client call (defense-in-depth; the dashboard is
        // already tenant-scoped, but the plugin never reaches across tenants).
        return { text: "", path: params.relPath };
      }
      const row = await client.statement(decoded.id);
      return statementToReadResult(toStatementRow(row), params.relPath);
    },

    status(): MemoryProviderStatus {
      // backend is constrained to "builtin" | "qmd"; Starling is an external
      // provider, so it reports under the "qmd" external-backend bucket with a
      // distinguishing provider label.
      return {
        backend: "qmd",
        provider: "starling",
      };
    },

    // index path: Starling runs embedding/consolidation maintenance in its own
    // background loop, so a host-driven sync is a no-op rather than a tick call.
    async sync(): Promise<void> {
      // intentional no-op
    },

    async probeEmbeddingAvailability(): Promise<MemoryEmbeddingProbeResult> {
      // MVP: Starling ships its own embedder. We optimistically report ready;
      // a true unreachable dashboard still degrades search to [] (no throw),
      // so an over-optimistic probe never wedges a turn.
      return { ok: true, checked: false };
    },

    async probeVectorAvailability(): Promise<boolean> {
      // MVP default: vector search is assumed available (Starling-managed).
      return true;
    },
  };
}

// ---------------------------------------------------------------------------
// MemoryPluginRuntime — the object handed to api.registerMemoryRuntime()
// ---------------------------------------------------------------------------

/**
 * Assembles the runtime adapter. A fresh manager is returned per call; the
 * manager is stateless (it closes over cfg + client), so there is nothing to
 * cache or to close in closeAllMemorySearchManagers.
 */
export function makeStarlingRuntime(
  cfg: StarlingMemoryConfig,
  client: StarlingClient,
): MemoryPluginRuntime {
  const manager = makeStarlingManager(cfg, client);
  return {
    async getMemorySearchManager() {
      return { manager };
    },
    resolveMemoryBackendConfig(): MemoryRuntimeBackendConfig {
      // Starling is registered as the active external memory runtime. The
      // backend-config union only models "builtin" | "qmd"; we expose "qmd"
      // (external runtime) with no qmd command override.
      return { backend: "qmd" };
    },
  };
}

// ---------------------------------------------------------------------------
// Pre-compaction flush plan (contract §E)
// ---------------------------------------------------------------------------

/**
 * Resolver passed to api.registerMemoryFlushPlan. Returns the plan that drives
 * OpenClaw's silent pre-compaction agentic turn: the agent itself writes a
 * durable note to `relativePath`. Starling's own transcript capture runs in
 * parallel via the before_compaction hook (see index.ts).
 *
 * Signature matches MemoryFlushPlanResolver: (params: { cfg?; nowMs? }) =>
 * MemoryFlushPlan | null. Params are unused here (static thresholds).
 */
export function buildFlushPlan(): MemoryFlushPlan | null {
  return {
    softThresholdTokens: SOFT_THRESHOLD_TOKENS,
    forceFlushTranscriptBytes: FORCE_FLUSH_TRANSCRIPT_BYTES,
    reserveTokensFloor: RESERVE_TOKENS_FLOOR,
    prompt:
      "Before this conversation is compacted, save any durable facts, " +
      "decisions, or commitments worth remembering using the available " +
      "memory tools." +
      NO_REPLY,
    systemPrompt:
      "You are a memory-keeping assistant. Persist only durable, " +
      "reusable information. Do not reply to the user.",
    relativePath: "memory/flush.md",
  };
}

// ---------------------------------------------------------------------------
// Memory prompt section (contract §C — registerMemoryPromptSection)
// ---------------------------------------------------------------------------

/**
 * Builder passed to api.registerMemoryPromptSection. Tells the agent that the
 * Starling-backed memory_store / memory_forget tools exist, but only when the
 * host reports them as available so we never advertise a missing tool.
 *
 * Signature matches MemoryPromptSectionBuilder: (params: { availableTools:
 * Set<string>; citationsMode? }) => string[].
 */
export const buildPromptSection: MemoryPromptSectionBuilder = (params) => {
  const lines: string[] = [];
  if (params.availableTools.has("memory_store")) {
    lines.push(
      "Use the `memory_store` tool to save durable information into long-term memory.",
    );
  }
  if (params.availableTools.has("memory_forget")) {
    lines.push(
      "Use the `memory_forget` tool to remove a memory by its id when it is no longer accurate.",
    );
  }
  return lines;
};
