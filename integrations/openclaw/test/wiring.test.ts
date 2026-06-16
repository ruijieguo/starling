/**
 * wiring.test.ts — unit tests for the plugin's register() wiring.
 *
 * index.ts exposes `wirePlugin(api, cfg, client)` (the body of definePluginEntry's
 * register) so the OpenClaw api surface can be mocked. We assert it registers the
 * unified memory capability, the two write tools, and the two hooks, and that the
 * tools/hooks route through the client with the configured holder.
 */
import { describe, it, expect, vi } from "vitest";
import { wirePlugin } from "../src/index.js";
import type { StarlingMemoryConfig } from "../src/config.js";
import type { StarlingClient } from "../src/client.js";

const CFG: StarlingMemoryConfig = {
  dashboardUrl: "http://localhost:7777",
  token: "secret",
  tenant: "openclaw",
  holder: "agent",
  autoCapture: true,
  autoRecall: true,
};

function makeFakeClient(): StarlingClient {
  return {
    recall: vi.fn(async () => []),
    statement: vi.fn(async () => null),
    workingSet: vi.fn(async () => ({ render: "WS" })),
    remember: vi.fn(async () => {}),
    forget: vi.fn(async () => {}),
  } as unknown as StarlingClient;
}

function makeFakeApi() {
  return {
    registerMemoryCapability: vi.fn(),
    registerTool: vi.fn(),
    on: vi.fn(),
  };
}

describe("wirePlugin", () => {
  it("registers a unified memory capability with runtime + promptBuilder + flushPlanResolver", () => {
    const api = makeFakeApi();
    wirePlugin(api as never, CFG, makeFakeClient());
    expect(api.registerMemoryCapability).toHaveBeenCalledTimes(1);
    const cap = api.registerMemoryCapability.mock.calls[0][0];
    expect(cap.runtime).toBeTruthy();
    expect(typeof cap.promptBuilder).toBe("function");
    expect(typeof cap.flushPlanResolver).toBe("function");
  });

  it("registers memory_store and memory_forget tools (in order)", () => {
    const api = makeFakeApi();
    wirePlugin(api as never, CFG, makeFakeClient());
    const names = api.registerTool.mock.calls.map((c) => (c[0] as { name: string }).name);
    expect(names).toEqual(["memory_store", "memory_forget"]);
  });

  it("memory_store tool writes via client.remember with cfg.holder", async () => {
    const api = makeFakeApi();
    const client = makeFakeClient();
    wirePlugin(api as never, CFG, client);
    const storeTool = api.registerTool.mock.calls[0][0] as {
      execute: (id: string, p: unknown) => Promise<unknown>;
    };
    await storeTool.execute("call-1", { text: "hello world" });
    expect(client.remember).toHaveBeenCalledWith("hello world", "agent");
  });

  it("memory_forget tool deletes via client.forget", async () => {
    const api = makeFakeApi();
    const client = makeFakeClient();
    wirePlugin(api as never, CFG, client);
    const forgetTool = api.registerTool.mock.calls[1][0] as {
      execute: (id: string, p: unknown) => Promise<unknown>;
    };
    await forgetTool.execute("call-1", { memoryId: "s1" });
    expect(client.forget).toHaveBeenCalledWith(["s1"]);
  });

  it("registers before_prompt_build (auto-recall) + before_compaction (auto-capture) hooks", () => {
    const api = makeFakeApi();
    wirePlugin(api as never, CFG, makeFakeClient());
    const hooks = api.on.mock.calls.map((c) => c[0]);
    expect(hooks).toContain("before_prompt_build");
    expect(hooks).toContain("before_compaction");
  });

  it("auto-recall hook injects the working set as prependContext under cfg.holder", async () => {
    const api = makeFakeApi();
    const client = makeFakeClient();
    wirePlugin(api as never, CFG, client);
    const entry = api.on.mock.calls.find((c) => c[0] === "before_prompt_build");
    const handler = entry![1] as () => Promise<unknown>;
    const result = await handler();
    expect(client.workingSet).toHaveBeenCalledWith("agent", "agent");
    expect(result).toEqual({ prependContext: "WS" });
  });

  it("auto-capture hook persists recent user text via client.remember", async () => {
    const api = makeFakeApi();
    const client = makeFakeClient();
    wirePlugin(api as never, CFG, client);
    const entry = api.on.mock.calls.find((c) => c[0] === "before_compaction");
    const handler = entry![1] as (e: unknown) => Promise<unknown>;
    await handler({ messages: [{ role: "user", content: "I use pnpm" }] });
    expect(client.remember).toHaveBeenCalledWith("I use pnpm", "agent");
  });

  it("omits both hooks when autoRecall/autoCapture are off", () => {
    const api = makeFakeApi();
    wirePlugin(api as never, { ...CFG, autoRecall: false, autoCapture: false }, makeFakeClient());
    expect(api.on).not.toHaveBeenCalled();
  });
});
