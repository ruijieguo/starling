/**
 * client.test.ts — Unit tests for StarlingClient.
 *
 * All tests mock global.fetch — no real network calls.
 * backoffMs is replaced with () => 0 so tests never truly sleep.
 * Token value is confirmed absent from all console.warn output.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { StarlingClient, StarlingAuthError } from "../src/client.js";
import type { StarlingMemoryConfig } from "../src/config.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const BASE_CFG: StarlingMemoryConfig = {
  dashboardUrl: "http://localhost:7777/",
  token: "super-secret-test-token-abc123",
  tenant: "openclaw",
  holder: "agent",
  autoCapture: true,
  autoRecall: true,
};

/** Build a Response-like object that fetch resolves to. */
function makeResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

/** Create a client with instant backoff (no real sleep in retry logic). */
function makeClient(cfg: StarlingMemoryConfig = BASE_CFG): StarlingClient {
  const c = new StarlingClient(cfg);
  c.backoffMs = () => 0; // instant backoff for tests
  return c;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("StarlingClient", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // -------------------------------------------------------------------------
  // Token header format
  // -------------------------------------------------------------------------

  describe("request headers", () => {
    it("sends Authorization: Bearer <token> header on recall", async () => {
      fetchMock.mockResolvedValueOnce(
        makeResponse(200, { results: [] }),
      );
      const client = makeClient();
      await client.recall("foo", 5);

      expect(fetchMock).toHaveBeenCalledOnce();
      const [_url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = init.headers as Record<string, string>;
      expect(headers["Authorization"]).toBe(`Bearer ${BASE_CFG.token}`);
    });

    it("sends Content-Type: application/json on POST", async () => {
      fetchMock.mockResolvedValueOnce(
        makeResponse(200, { results: [] }),
      );
      const client = makeClient();
      await client.recall("foo", 5);

      const [_url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = init.headers as Record<string, string>;
      expect(headers["Content-Type"]).toBe("application/json");
    });

    it("strips trailing slash from baseUrl", async () => {
      fetchMock.mockResolvedValueOnce(
        makeResponse(200, { results: [] }),
      );
      const client = makeClient({ ...BASE_CFG, dashboardUrl: "http://localhost:7777///" });
      await client.recall("q", 3);

      const [url] = fetchMock.mock.calls[0] as [string];
      expect(url).toBe("http://localhost:7777/api/recall");
    });
  });

  // -------------------------------------------------------------------------
  // Read degradation — network error
  // -------------------------------------------------------------------------

  describe("recall — read degradation", () => {
    it("returns [] when fetch rejects (network error)", async () => {
      fetchMock.mockRejectedValueOnce(new Error("ECONNREFUSED"));
      const client = makeClient();
      const result = await client.recall("test query", 5);
      expect(result).toEqual([]);
    });

    it("does not throw on network error", async () => {
      fetchMock.mockRejectedValueOnce(new Error("ECONNREFUSED"));
      const client = makeClient();
      await expect(client.recall("test", 5)).resolves.toEqual([]);
    });

    it("returns [] on 500 server error", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(500, {}));
      const client = makeClient();
      const result = await client.recall("test", 3);
      expect(result).toEqual([]);
    });

    it("returns mapped results on 200", async () => {
      const hits = [
        { id: "1", subject: "A", predicate: "is", object: "B", score: 0.9 },
      ];
      fetchMock.mockResolvedValueOnce(makeResponse(200, { results: hits }));
      const client = makeClient();
      const result = await client.recall("test", 1);
      expect(result).toEqual(hits);
    });

    it("throws StarlingAuthError on 401", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(401, {}));
      const client = makeClient();
      await expect(client.recall("test", 5)).rejects.toBeInstanceOf(StarlingAuthError);
    });

    it("throws StarlingAuthError on 403", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(403, {}));
      const client = makeClient();
      await expect(client.recall("test", 5)).rejects.toBeInstanceOf(StarlingAuthError);
    });
  });

  describe("workingSet — read degradation", () => {
    it("returns null when fetch rejects", async () => {
      fetchMock.mockRejectedValueOnce(new Error("timeout"));
      const client = makeClient();
      const result = await client.workingSet("interlocutor-1");
      expect(result).toBeNull();
    });

    it("returns null on 503", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(503, {}));
      const client = makeClient();
      const result = await client.workingSet("i1");
      expect(result).toBeNull();
    });

    it("returns { render } on 200", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(200, { render: "context text" }));
      const client = makeClient();
      const result = await client.workingSet("i1", "h1", "my goal", 2000);
      expect(result).toEqual({ render: "context text" });
    });

    it("passes interlocutor/holder/goal/tokenBudget as query params", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(200, { render: "" }));
      const client = makeClient();
      await client.workingSet("alice", "agent", "the goal", 500);
      const [url] = fetchMock.mock.calls[0] as [string];
      expect(url).toContain("interlocutor=alice");
      expect(url).toContain("holder=agent");
      expect(url).toContain("goal=the+goal");
      expect(url).toContain("token_budget=500");
    });

    it("passes holder into the recall body when provided", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(200, { results: [] }));
      const client = makeClient();
      await client.recall("q", 5, "agent");
      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(JSON.parse(init.body as string)).toEqual({ query: "q", k: 5, holder: "agent" });
    });

    it("throws StarlingAuthError on 401", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(401, {}));
      const client = makeClient();
      await expect(client.workingSet("i1")).rejects.toBeInstanceOf(StarlingAuthError);
    });
  });

  describe("statement — read degradation", () => {
    it("returns null when fetch rejects", async () => {
      fetchMock.mockRejectedValueOnce(new Error("network down"));
      const client = makeClient();
      const result = await client.statement("stmt-42");
      expect(result).toBeNull();
    });

    it("returns null on 404", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(404, {}));
      const client = makeClient();
      const result = await client.statement("not-found");
      expect(result).toBeNull();
    });

    it("returns object on 200", async () => {
      const data = { id: "abc", subject: "X" };
      fetchMock.mockResolvedValueOnce(makeResponse(200, data));
      const client = makeClient();
      const result = await client.statement("abc");
      expect(result).toEqual(data);
    });

    it("encodes id in URL path", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(200, {}));
      const client = makeClient();
      await client.statement("foo/bar baz");
      const [url] = fetchMock.mock.calls[0] as [string];
      expect(url).toContain("/api/statement/foo%2Fbar%20baz");
    });

    it("throws StarlingAuthError on 401", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(401, {}));
      const client = makeClient();
      await expect(client.statement("x")).rejects.toBeInstanceOf(StarlingAuthError);
    });
  });

  // -------------------------------------------------------------------------
  // Write methods — success path
  // -------------------------------------------------------------------------

  describe("remember — success path", () => {
    it("resolves without enqueueing on 200", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(200, { statement_ids: ["1"] }));
      const client = makeClient();
      await client.remember("Alice knows Bob");
      expect(client.queueLength).toBe(0);
    });

    it("sends holder when provided", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(200, {}));
      const client = makeClient();
      await client.remember("some text", "my-agent");
      const [_url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const body = JSON.parse(init.body as string) as Record<string, unknown>;
      expect(body["holder"]).toBe("my-agent");
    });

    it("omits holder when not provided", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(200, {}));
      const client = makeClient();
      await client.remember("some text");
      const [_url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const body = JSON.parse(init.body as string) as Record<string, unknown>;
      expect(body).not.toHaveProperty("holder");
    });
  });

  describe("forget — success path", () => {
    it("resolves without enqueueing on 200", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(200, { forgotten: ["id1"] }));
      const client = makeClient();
      await client.forget(["id1"]);
      expect(client.queueLength).toBe(0);
    });
  });

  // -------------------------------------------------------------------------
  // Write methods — failure → enqueue
  // -------------------------------------------------------------------------

  describe("remember — failure enqueues", () => {
    it("does not throw when fetch rejects", async () => {
      fetchMock.mockRejectedValueOnce(new Error("ECONNREFUSED"));
      const client = makeClient();
      await expect(client.remember("some text")).resolves.toBeUndefined();
    });

    it("enqueues entry on fetch reject", async () => {
      fetchMock.mockRejectedValueOnce(new Error("network"));
      const client = makeClient();
      await client.remember("some text");
      expect(client.queueLength).toBe(1);
    });

    it("enqueues on 5xx", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(503, {}));
      const client = makeClient();
      await client.remember("text");
      expect(client.queueLength).toBe(1);
    });

    it("throws StarlingAuthError on 401 and does NOT enqueue", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(401, {}));
      const client = makeClient();
      await expect(client.remember("text")).rejects.toBeInstanceOf(StarlingAuthError);
      expect(client.queueLength).toBe(0);
    });

    it("throws StarlingAuthError on 403 and does NOT enqueue", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(403, {}));
      const client = makeClient();
      await expect(client.remember("text")).rejects.toBeInstanceOf(StarlingAuthError);
      expect(client.queueLength).toBe(0);
    });
  });

  describe("forget — failure enqueues", () => {
    it("does not throw when fetch rejects", async () => {
      fetchMock.mockRejectedValueOnce(new Error("timeout"));
      const client = makeClient();
      await expect(client.forget(["id1"])).resolves.toBeUndefined();
    });

    it("enqueues entry on fetch reject", async () => {
      fetchMock.mockRejectedValueOnce(new Error("timeout"));
      const client = makeClient();
      await client.forget(["id1"]);
      expect(client.queueLength).toBe(1);
    });

    it("throws StarlingAuthError on 401 and does NOT enqueue", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(401, {}));
      const client = makeClient();
      await expect(client.forget(["id1"])).rejects.toBeInstanceOf(StarlingAuthError);
      expect(client.queueLength).toBe(0);
    });
  });

  // -------------------------------------------------------------------------
  // flushQueue
  // -------------------------------------------------------------------------

  describe("flushQueue", () => {
    it("removes entry from queue on successful retry", async () => {
      // First call (remember) fails → enqueues
      fetchMock.mockRejectedValueOnce(new Error("network"));
      const client = makeClient();
      await client.remember("text to retry");
      expect(client.queueLength).toBe(1);

      // flushQueue call succeeds
      fetchMock.mockResolvedValueOnce(makeResponse(200, {}));
      await client.flushQueue();
      expect(client.queueLength).toBe(0);
    });

    it("keeps entry in queue when retry also fails", async () => {
      fetchMock.mockRejectedValueOnce(new Error("network"));
      const client = makeClient();
      await client.remember("text");
      expect(client.queueLength).toBe(1);

      // flush also fails
      fetchMock.mockRejectedValueOnce(new Error("still down"));
      await client.flushQueue();
      expect(client.queueLength).toBe(1);
    });

    it("increments attempts on failed flush", async () => {
      fetchMock.mockRejectedValue(new Error("always fails"));
      const client = makeClient();
      await client.remember("text");
      await client.flushQueue();
      // Can't inspect attempts directly, but we can verify the queue still has the entry
      expect(client.queueLength).toBe(1);
    });

    it("handles multiple queued writes — succeeds all", async () => {
      fetchMock.mockRejectedValueOnce(new Error("n"));
      fetchMock.mockRejectedValueOnce(new Error("n"));
      const client = makeClient();
      await client.remember("text1");
      await client.forget(["id1"]);
      expect(client.queueLength).toBe(2);

      // Both retry calls succeed
      fetchMock.mockResolvedValueOnce(makeResponse(200, {}));
      fetchMock.mockResolvedValueOnce(makeResponse(200, {}));
      await client.flushQueue();
      expect(client.queueLength).toBe(0);
    });

    it("flushQueue on empty queue is a no-op", async () => {
      const client = makeClient();
      await expect(client.flushQueue()).resolves.toBeUndefined();
    });
  });

  // -------------------------------------------------------------------------
  // Token never appears in warn/error messages
  // -------------------------------------------------------------------------

  describe("token safety", () => {
    const TOKEN = BASE_CFG.token; // "super-secret-test-token-abc123"

    it("console.warn does not contain token value on recall failure", async () => {
      fetchMock.mockRejectedValueOnce(new Error("network error"));
      const client = makeClient();
      await client.recall("q", 5);
      for (const call of warnSpy.mock.calls) {
        const msg = call.map(String).join(" ");
        expect(msg).not.toContain(TOKEN);
      }
    });

    it("console.warn does not contain token value on workingSet failure", async () => {
      fetchMock.mockRejectedValueOnce(new Error("network error"));
      const client = makeClient();
      await client.workingSet("i1");
      for (const call of warnSpy.mock.calls) {
        const msg = call.map(String).join(" ");
        expect(msg).not.toContain(TOKEN);
      }
    });

    it("console.warn does not contain token value on statement failure", async () => {
      fetchMock.mockRejectedValueOnce(new Error("network error"));
      const client = makeClient();
      await client.statement("x");
      for (const call of warnSpy.mock.calls) {
        const msg = call.map(String).join(" ");
        expect(msg).not.toContain(TOKEN);
      }
    });

    it("console.warn does not contain token value on remember failure", async () => {
      fetchMock.mockRejectedValueOnce(new Error("network error"));
      const client = makeClient();
      await client.remember("text");
      for (const call of warnSpy.mock.calls) {
        const msg = call.map(String).join(" ");
        expect(msg).not.toContain(TOKEN);
      }
    });

    it("console.warn does not contain token on flushQueue failure", async () => {
      fetchMock.mockRejectedValue(new Error("always fails"));
      const client = makeClient();
      await client.remember("text");
      await client.flushQueue();
      for (const call of warnSpy.mock.calls) {
        const msg = call.map(String).join(" ");
        expect(msg).not.toContain(TOKEN);
      }
    });

    it("StarlingAuthError message does not contain token value", async () => {
      fetchMock.mockResolvedValueOnce(makeResponse(401, {}));
      const client = makeClient();
      try {
        await client.recall("q", 1);
        expect.fail("should have thrown");
      } catch (e) {
        expect((e as Error).message).not.toContain(TOKEN);
      }
    });
  });

  // -------------------------------------------------------------------------
  // Queue capacity
  // -------------------------------------------------------------------------

  describe("queue capacity", () => {
    it("evicts oldest entry when queue is full (capacity 1000)", async () => {
      // Fill the queue by making 1000 failed remember calls
      const client = makeClient();
      fetchMock.mockRejectedValue(new Error("network"));

      // We'll add 1001 entries; the first should be evicted
      const calls: Promise<void>[] = [];
      for (let i = 0; i < 1001; i++) {
        calls.push(client.remember(`entry-${i}`));
      }
      await Promise.all(calls);

      expect(client.queueLength).toBe(1000);
      // After all evictions there should be a warn call about eviction
      const evictionWarns = warnSpy.mock.calls.filter(
        (c) => c[0] !== undefined && String(c[0]).includes("evicted"),
      );
      expect(evictionWarns.length).toBeGreaterThan(0);
    });
  });
});
