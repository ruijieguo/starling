/**
 * runtime.test.ts — Unit tests for the MemoryPluginRuntime assembly.
 *
 * StarlingClient is mocked with a hand-rolled fake (no real HTTP). We assert the
 * manager routes through map + client correctly, that readFile degrades on an
 * unowned path without calling the client, that status() reports a backend in
 * the allowed union, and that buildFlushPlan emits the required fields.
 */

import { describe, it, expect, vi } from "vitest";
import {
  makeStarlingManager,
  makeStarlingRuntime,
  buildFlushPlan,
  buildPromptSection,
} from "../src/runtime.js";
import type { StarlingMemoryConfig } from "../src/config.js";
import type { StarlingClient } from "../src/client.js";
import type { RecallHit } from "../src/map.js";

const CFG: StarlingMemoryConfig = {
  dashboardUrl: "http://localhost:7777",
  token: "secret-token",
  tenant: "openclaw",
  holder: "agent",
  autoCapture: true,
  autoRecall: true,
};

/** Build a fake StarlingClient with vitest mocks for the methods runtime uses. */
function makeFakeClient(overrides?: {
  recall?: (q: string, k: number) => Promise<RecallHit[]>;
  statement?: (id: string) => Promise<Record<string, unknown> | null>;
}): StarlingClient {
  const fake = {
    recall: vi.fn(overrides?.recall ?? (async () => [])),
    statement: vi.fn(overrides?.statement ?? (async () => null)),
    workingSet: vi.fn(async () => null),
    remember: vi.fn(async () => {}),
    forget: vi.fn(async () => {}),
  };
  // Cast confined to the test: the runtime only touches the methods above.
  return fake as unknown as StarlingClient;
}

describe("makeStarlingManager.search", () => {
  it("calls client.recall and maps hits to MemorySearchResult rows", async () => {
    const hits: RecallHit[] = [
      { id: "s1", subject: "Ada", predicate: "likes", object: "math", score: 0.9 },
    ];
    const client = makeFakeClient({ recall: async () => hits });
    const mgr = makeStarlingManager(CFG, client);

    const results = await mgr.search("who likes math", { maxResults: 5 });

    expect(client.recall).toHaveBeenCalledWith("who likes math", 5);
    expect(results).toHaveLength(1);
    const row = results[0];
    // Synthetic, re-decodable path + memory source + citation == statement id.
    expect(row.path).toBe("statement://openclaw/s1");
    expect(row.snippet).toBe("Ada likes math");
    expect(row.source).toBe("memory");
    expect(row.citation).toBe("s1");
    expect(row.score).toBe(0.9);
  });

  it("defaults maxResults to 10 when opts omitted", async () => {
    const client = makeFakeClient();
    const mgr = makeStarlingManager(CFG, client);
    await mgr.search("q");
    expect(client.recall).toHaveBeenCalledWith("q", 10);
  });
});

describe("makeStarlingManager.readFile", () => {
  it("decodes a statement:// path, fetches the statement, and renders text", async () => {
    const client = makeFakeClient({
      statement: async (id) => ({
        subject_id: `subj-${id}`,
        predicate: "is",
        object_value: "blue",
      }),
    });
    const mgr = makeStarlingManager(CFG, client);

    const res = await mgr.readFile({ relPath: "statement://openclaw/s42" });

    expect(client.statement).toHaveBeenCalledWith("s42");
    expect(res.path).toBe("statement://openclaw/s42");
    expect(res.text).toBe("subj-s42 is blue");
  });

  it("degrades to empty text WITHOUT calling the client on an unowned path", async () => {
    const client = makeFakeClient();
    const mgr = makeStarlingManager(CFG, client);

    const res = await mgr.readFile({ relPath: "not-a-statement-path" });

    expect(res).toEqual({ text: "", path: "not-a-statement-path" });
    expect(client.statement).not.toHaveBeenCalled();
  });

  it("degrades WITHOUT calling the client on a cross-tenant path", async () => {
    const client = makeFakeClient({
      statement: async () => ({ subject_id: "x", predicate: "y", object_value: "z" }),
    });
    const mgr = makeStarlingManager(CFG, client);

    const res = await mgr.readFile({ relPath: "statement://other-tenant/s1" });

    expect(res).toEqual({ text: "", path: "statement://other-tenant/s1" });
    expect(client.statement).not.toHaveBeenCalled();
  });

  it("degrades to empty fields when client.statement returns null", async () => {
    const client = makeFakeClient({ statement: async () => null });
    const mgr = makeStarlingManager(CFG, client);

    const res = await mgr.readFile({ relPath: "statement://openclaw/missing" });

    expect(client.statement).toHaveBeenCalledWith("missing");
    expect(res.path).toBe("statement://openclaw/missing");
    // Empty subject/predicate/object render as a string of two spaces.
    expect(res.text).toBe("  ");
  });
});

describe("makeStarlingManager.status / probes", () => {
  it("reports a backend in the allowed union and a starling provider label", () => {
    const mgr = makeStarlingManager(CFG, makeFakeClient());
    const status = mgr.status();
    expect(["builtin", "qmd"]).toContain(status.backend);
    expect(status.provider).toBe("starling");
  });

  it("probes resolve without throwing (degrade-safe defaults)", async () => {
    const mgr = makeStarlingManager(CFG, makeFakeClient());
    const embed = await mgr.probeEmbeddingAvailability();
    expect(embed.ok).toBe(true);
    const vector = await mgr.probeVectorAvailability();
    expect(vector).toBe(true);
  });

  it("sync is a no-op that resolves", async () => {
    const mgr = makeStarlingManager(CFG, makeFakeClient());
    await expect(mgr.sync?.()).resolves.toBeUndefined();
  });
});

describe("makeStarlingRuntime", () => {
  it("getMemorySearchManager yields a manager; backend config is in the union", async () => {
    const rt = makeStarlingRuntime(CFG, makeFakeClient());
    const got = await rt.getMemorySearchManager({
      // params shape per MemoryPluginRuntime; values are irrelevant to the stub.
      cfg: {} as never,
      agentId: "a1",
    });
    expect(got.manager).not.toBeNull();
    expect(typeof got.manager?.search).toBe("function");

    const backend = rt.resolveMemoryBackendConfig({ cfg: {} as never, agentId: "a1" });
    expect(["builtin", "qmd"]).toContain(backend.backend);
  });
});

describe("buildFlushPlan", () => {
  it("returns a plan with all required MemoryFlushPlan fields", () => {
    const plan = buildFlushPlan();
    expect(plan).not.toBeNull();
    expect(typeof plan!.softThresholdTokens).toBe("number");
    expect(typeof plan!.forceFlushTranscriptBytes).toBe("number");
    expect(typeof plan!.reserveTokensFloor).toBe("number");
    expect(typeof plan!.prompt).toBe("string");
    expect(typeof plan!.systemPrompt).toBe("string");
    expect(typeof plan!.relativePath).toBe("string");
    expect(plan!.relativePath.length).toBeGreaterThan(0);
  });
});

describe("buildPromptSection", () => {
  it("advertises only the memory tools that are available", () => {
    const both = buildPromptSection({ availableTools: new Set(["memory_store", "memory_forget"]) });
    expect(both).toHaveLength(2);

    const none = buildPromptSection({ availableTools: new Set<string>() });
    expect(none).toEqual([]);

    const storeOnly = buildPromptSection({ availableTools: new Set(["memory_store"]) });
    expect(storeOnly).toHaveLength(1);
    expect(storeOnly[0]).toContain("memory_store");
  });
});
