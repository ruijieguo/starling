/**
 * Starling memory plugin for OpenClaw — minimal skeleton (P3.b2 Task 5).
 *
 * Claims the `plugins.slots.memory` slot via manifest `kind:"memory"` +
 * `definePluginEntry({ kind:"memory" })`, and registers a hybrid memory
 * runtime (`registerMemoryRuntime`). This Task ships only the skeleton:
 * a stub MemorySearchManager that returns empty/unavailable results so the
 * manifest, entry, and types are exercised and the package compiles.
 *
 * The full seven capabilities (search/get/index/recall/capture/flush/remove)
 * land in a later Task; see
 * docs/superpowers/specs/2026-06-15-p3-b2-openclaw-contract.md.
 */
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

/**
 * Stub MemorySearchManager.
 *
 * Shape matches OpenClaw's `RegisteredMemorySearchManager`
 * (memory-state.d.ts) — the object returned by `getMemorySearchManager`,
 * which only requires `status` + the two probes (no search/readFile). Reads
 * report "unavailable" rather than throwing, so a not-yet-wired Starling
 * backend never interrupts an agent turn.
 */
const stubManager = {
  status() {
    // Conforms to MemoryProviderStatus (host/types.d.ts): backend + provider
    // are required. Task 6 fills these from the Starling dashboard overview.
    return {
      backend: "builtin" as const,
      provider: "starling",
    };
  },
  async probeEmbeddingAvailability() {
    // MemoryEmbeddingProbeResult = { ok: boolean; error?: string }
    return { ok: false, error: "starling skeleton: embedding probe not wired" };
  },
  async probeVectorAvailability() {
    return false;
  },
};

/**
 * Stub MemoryPluginRuntime (memory-state.d.ts). `getMemorySearchManager`
 * always yields the stub manager; `resolveMemoryBackendConfig` reports the
 * builtin backend. Task 6 replaces this with a Starling-client-backed runtime.
 */
const runtime = {
  async getMemorySearchManager(_params: {
    agentId: string;
    purpose?: "default" | "status";
  }) {
    return { manager: stubManager };
  },
  resolveMemoryBackendConfig(_params: { agentId: string }) {
    return { backend: "builtin" as const };
  },
};

export default definePluginEntry({
  id: "starling",
  name: "Starling Memory",
  description: "Starling-backed long-term cognitive memory (skeleton)",
  kind: "memory",
  register(api) {
    // search/get/index path. Stub for now; capture/flush/recall/remove wiring
    // (registerTool / registerMemoryFlushPlan / api.on) arrives in Task 6.
    api.registerMemoryRuntime(runtime as Parameters<typeof api.registerMemoryRuntime>[0]);
  },
});
