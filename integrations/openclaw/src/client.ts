/**
 * client.ts — StarlingClient: HTTP transport layer for the OpenClaw memory plugin.
 *
 * Reads degrade gracefully (network errors → empty/null, no throw).
 * Writes are queued on failure (non-401) and retried via flushQueue().
 * 401/403 → StarlingAuthError (config error, never queued, always re-throws).
 *
 * SECURITY: cfg.token is NEVER included in log messages, warn strings, or
 * error messages. All console.warn calls must not reference cfg.token.
 */

import type { StarlingMemoryConfig } from "./config.js";
import type { RecallHit } from "./map.js";

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/** Thrown when the dashboard returns 401 or 403 (bad/missing token). */
export class StarlingAuthError extends Error {
  constructor(status: number) {
    super(`starling memory plugin: dashboard auth failed (HTTP ${status})`);
    this.name = "StarlingAuthError";
  }
}

/** Thrown for non-2xx responses that are not auth errors. */
export class StarlingHttpError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "StarlingHttpError";
  }
}

// ---------------------------------------------------------------------------
// Write queue
// ---------------------------------------------------------------------------

interface QueuedWrite {
  method: "POST";
  path: string;
  body: unknown;
  attempts: number;
}

const QUEUE_MAX = 1000;

// ---------------------------------------------------------------------------
// Backoff calculator (pure — no real sleep; callers decide whether to use it)
// ---------------------------------------------------------------------------

/** Returns retry delay in milliseconds for the given attempt count (0-indexed).
 *  Default: 100 * 2^attempts, capped at 30 000 ms.
 *  Inject a custom implementation in tests to avoid real waits.
 */
export function defaultBackoffMs(attempts: number): number {
  return Math.min(100 * Math.pow(2, attempts), 30_000);
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export class StarlingClient {
  private readonly baseUrl: string;
  private readonly writeQueue: QueuedWrite[] = [];
  /** Overridable backoff calculator — swap out in tests for instant retries. */
  backoffMs: (attempts: number) => number = defaultBackoffMs;

  constructor(private readonly cfg: StarlingMemoryConfig) {
    this.baseUrl = cfg.dashboardUrl.replace(/\/+$/, "");
  }

  // -------------------------------------------------------------------------
  // Private helpers
  // -------------------------------------------------------------------------

  /** Returns request headers with Bearer token. Token never included in logs. */
  private headers(): Record<string, string> {
    return {
      Authorization: `Bearer ${this.cfg.token}`,
      "Content-Type": "application/json",
    };
  }

  /**
   * Core fetch wrapper. Throws StarlingAuthError on 401/403.
   * Throws StarlingHttpError on other non-2xx. Lets network errors propagate.
   */
  private async req(
    method: "GET" | "POST",
    path: string,
    body?: unknown,
  ): Promise<Response> {
    const url = `${this.baseUrl}${path}`;
    const init: RequestInit = {
      method,
      headers: this.headers(),
    };
    if (body !== undefined) {
      init.body = JSON.stringify(body);
    }

    const res = await fetch(url, init);

    if (res.status === 401 || res.status === 403) {
      throw new StarlingAuthError(res.status);
    }
    if (!res.ok) {
      throw new StarlingHttpError(
        res.status,
        `starling memory plugin: dashboard returned HTTP ${res.status}`,
      );
    }
    return res;
  }

  // -------------------------------------------------------------------------
  // Read methods — degrade on error (non-auth failures return empty/null)
  // -------------------------------------------------------------------------

  /**
   * POST /api/recall — semantic search.
   * Returns [] on any non-auth failure (network, 5xx, etc.).
   * Throws StarlingAuthError on 401/403.
   */
  async recall(query: string, k: number): Promise<RecallHit[]> {
    try {
      const res = await this.req("POST", "/api/recall", { query, k });
      const json = (await res.json()) as { results: RecallHit[] };
      return json.results ?? [];
    } catch (err) {
      if (err instanceof StarlingAuthError) throw err;
      console.warn("starling memory plugin: recall unavailable — degrading to []");
      return [];
    }
  }

  /**
   * GET /api/working_set — context injection.
   * Returns null on any non-auth failure.
   * Throws StarlingAuthError on 401/403.
   */
  async workingSet(
    interlocutor: string,
    goal?: string,
    tokenBudget?: number,
  ): Promise<{ render: string } | null> {
    const params = new URLSearchParams({ interlocutor });
    if (goal !== undefined) params.set("goal", goal);
    if (tokenBudget !== undefined) params.set("token_budget", String(tokenBudget));
    const path = `/api/working_set?${params.toString()}`;

    try {
      const res = await this.req("GET", path);
      const json = (await res.json()) as { render: string };
      return { render: json.render };
    } catch (err) {
      if (err instanceof StarlingAuthError) throw err;
      console.warn("starling memory plugin: working_set unavailable — degrading to null");
      return null;
    }
  }

  /**
   * GET /api/statement/{id} — fetch a single statement.
   * Returns null on 404 or any non-auth failure.
   * Throws StarlingAuthError on 401/403.
   */
  async statement(id: string): Promise<Record<string, unknown> | null> {
    try {
      const res = await this.req("GET", `/api/statement/${encodeURIComponent(id)}`);
      return (await res.json()) as Record<string, unknown>;
    } catch (err) {
      if (err instanceof StarlingAuthError) throw err;
      // 404 comes through as StarlingHttpError with status 404 — treat as null
      console.warn("starling memory plugin: statement unavailable — degrading to null");
      return null;
    }
  }

  // -------------------------------------------------------------------------
  // Write methods — failures enqueue for retry (except 401 → always throws)
  // -------------------------------------------------------------------------

  /**
   * POST /api/remember — capture text as a memory statement.
   * On 401/403 → throws StarlingAuthError (not queued).
   * On other failures → enqueues for retry, does NOT throw.
   */
  async remember(text: string, holder?: string): Promise<void> {
    const body: { text: string; holder?: string } =
      holder !== undefined ? { text, holder } : { text };
    await this._writeWithQueue("POST", "/api/remember", body);
  }

  /**
   * POST /api/forget — delete statements by id.
   * On 401/403 → throws StarlingAuthError (not queued).
   * On other failures → enqueues for retry, does NOT throw.
   */
  async forget(ids: string[]): Promise<void> {
    await this._writeWithQueue("POST", "/api/forget", { ids });
  }

  /**
   * Internal write dispatcher: try the request; on non-auth failure, enqueue.
   */
  private async _writeWithQueue(
    method: "POST",
    path: string,
    body: unknown,
  ): Promise<void> {
    try {
      await this.req(method, path, body);
    } catch (err) {
      if (err instanceof StarlingAuthError) throw err;
      // Non-auth failure — enqueue for later retry; do not throw
      this._enqueue({ method, path, body, attempts: 0 });
    }
  }

  /** Push to the write queue, dropping oldest entry if at capacity. */
  private _enqueue(entry: QueuedWrite): void {
    if (this.writeQueue.length >= QUEUE_MAX) {
      this.writeQueue.shift(); // drop oldest
      console.warn(
        "starling memory plugin: write queue full — oldest entry evicted",
      );
    }
    this.writeQueue.push(entry);
  }

  /**
   * Retry all queued writes. Successful entries are removed; failed entries
   * keep their slot with attempts incremented. The backoffMs function is
   * consulted for callers that want to know the suggested delay, but
   * flushQueue itself does NOT sleep — it fires all retries immediately so
   * that tests do not require real timers.
   */
  async flushQueue(): Promise<void> {
    // Iterate a snapshot so mutations during iteration are safe
    const snapshot = [...this.writeQueue];
    for (const entry of snapshot) {
      try {
        await this.req(entry.method, entry.path, entry.body);
        // Success — remove from queue
        const idx = this.writeQueue.indexOf(entry);
        if (idx !== -1) this.writeQueue.splice(idx, 1);
      } catch (err) {
        if (err instanceof StarlingAuthError) {
          // Config is broken — stop flushing, propagate
          entry.attempts++;
          throw err;
        }
        entry.attempts++;
        // Leave in queue for the next flush
        console.warn(
          `starling memory plugin: flush retry failed (attempt ${entry.attempts})`,
        );
      }
    }
  }

  /** Expose queue length for observability / tests. */
  get queueLength(): number {
    return this.writeQueue.length;
  }
}
