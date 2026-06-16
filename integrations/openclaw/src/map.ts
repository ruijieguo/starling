/**
 * map.ts — Pure mapping functions: OpenClaw capability ↔ Starling dashboard API.
 *
 * No I/O. No openclaw type imports. Local minimal interfaces match the
 * contract (docs/superpowers/specs/2026-06-15-p3-b2-openclaw-contract.md §B).
 * Task 6 will wire these against real openclaw types.
 */

// ---------------------------------------------------------------------------
// Local minimal interfaces (Task 6 will align with openclaw types)
// ---------------------------------------------------------------------------

export interface RecallHit {
  id: string;
  subject: string;
  predicate: string;
  object: string;
  score: number;
}

export interface StatementRow {
  subject_id: string;
  predicate: string;
  object_value: string;
}

/** Mirrors openclaw MemorySource (host/types.d.ts) so recall hits align with
 *  the real MemorySearchResult.source union when consumed in runtime.ts. */
export type MemSource = "memory" | "sessions";

export interface MemSearchResult {
  path: string;
  startLine: number;
  endLine: number;
  score: number;
  snippet: string;
  source: MemSource;
  citation: string;
}

// ---------------------------------------------------------------------------
// Synthetic path encode / decode
// ---------------------------------------------------------------------------

/**
 * Encodes a tenant + statement id into a stable synthetic path.
 * OpenClaw uses this path for dedup and cross-call referencing.
 *
 * Invariant: decodePath(encodePath(t, id)) === { tenant: t, id }
 */
export function encodePath(tenant: string, id: string): string {
  return `statement://${tenant}/${id}`;
}

/**
 * Decodes a synthetic path back to { tenant, id }.
 * Returns null for any path that is not a valid statement:// URI.
 */
export function decodePath(relPath: string): { tenant: string; id: string } | null {
  const PREFIX = "statement://";
  if (!relPath.startsWith(PREFIX)) return null;

  const rest = relPath.slice(PREFIX.length);
  const slashIdx = rest.indexOf("/");
  // Must have at least one char before and one char after the slash.
  if (slashIdx <= 0) return null;

  const tenant = rest.slice(0, slashIdx);
  const id = rest.slice(slashIdx + 1);
  if (!id) return null;

  return { tenant, id };
}

// ---------------------------------------------------------------------------
// Recall → MemorySearchResult
// ---------------------------------------------------------------------------

/**
 * Maps dashboard POST /api/recall results to OpenClaw MemorySearchResult[].
 *
 * Each hit gets:
 *   path     = statement://<tenant>/<id>   (stable, re-decodable)
 *   snippet  = "<subject> <predicate> <object>"
 *   source   = "memory"
 *   citation = hit.id
 */
export function recallToSearchResults(
  results: RecallHit[],
  tenant: string,
): MemSearchResult[] {
  return results.map((hit) => ({
    path: encodePath(tenant, hit.id),
    startLine: 0,
    endLine: 0,
    score: hit.score,
    snippet: `${hit.subject} ${hit.predicate} ${hit.object}`,
    source: "memory",
    citation: hit.id,
  }));
}

// ---------------------------------------------------------------------------
// Statement → MemoryReadResult (readFile path)
// ---------------------------------------------------------------------------

/**
 * Maps a dashboard GET /api/statement/{id} row to OpenClaw readFile result.
 *
 * relPath is passed through unchanged so OpenClaw can correlate with the
 * original search result path.
 */
export function statementToReadResult(
  stmt: StatementRow,
  relPath: string,
): { text: string; path: string } {
  return {
    text: `${stmt.subject_id} ${stmt.predicate} ${stmt.object_value}`,
    path: relPath,
  };
}

// ---------------------------------------------------------------------------
// Working-set → context string (auto-inject recall)
// ---------------------------------------------------------------------------

/**
 * Extracts the pre-rendered context string from a working_set response.
 * Passed to OpenClaw prependContext in before_agent_start hook.
 */
export function workingSetToContext(ws: { render: string }): string {
  return ws.render;
}

// ---------------------------------------------------------------------------
// Capture → POST /api/remember body
// ---------------------------------------------------------------------------

/**
 * Builds the request body for POST /api/remember from a capture call.
 * holder is optional — when omitted the dashboard uses its own default.
 */
export function captureToRememberBody(
  text: string,
  holder?: string,
): { text: string; holder?: string } {
  if (holder !== undefined) {
    return { text, holder };
  }
  return { text };
}

// ---------------------------------------------------------------------------
// Remove → POST /api/forget body
// ---------------------------------------------------------------------------

/**
 * Builds the request body for POST /api/forget from a remove/memory_forget call.
 * memoryId is the statement id extracted from the search result citation.
 */
export function removeToForgetBody(memoryId: string): { ids: string[] } {
  return { ids: [memoryId] };
}

// ---------------------------------------------------------------------------
// before_compaction transcript → recent user text (auto-capture)
// ---------------------------------------------------------------------------

/** Extract plain text from a message `content` (string, or array of text blocks). */
function messageText(content: unknown): string {
  if (typeof content === "string") return content.trim();
  if (Array.isArray(content)) {
    const blocks: string[] = [];
    for (const block of content) {
      if (
        block !== null &&
        typeof block === "object" &&
        (block as Record<string, unknown>)["type"] === "text"
      ) {
        const t = (block as Record<string, unknown>)["text"];
        if (typeof t === "string") blocks.push(t);
      }
    }
    return blocks.join("\n").trim();
  }
  return "";
}

/**
 * Collects recent user-authored message text from a before_compaction transcript
 * (the host types `messages` as unknown[]). Walks newest-first, gathering user
 * messages up to maxChars, then returns them in chronological order. Auto-capture
 * sends this recent user-stated window — not just the single last message — so
 * Starling's extractor can distil structured facts from fuller context. Returns
 * "" when nothing usable is found. All field access is type-guarded.
 */
export function collectUserText(
  messages: unknown[] | undefined,
  maxChars = 2000,
): string {
  if (!Array.isArray(messages)) return "";
  const collected: string[] = [];
  let total = 0;
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m === null || typeof m !== "object") continue;
    const rec = m as Record<string, unknown>;
    if (rec["role"] !== "user") continue;
    const text = messageText(rec["content"]);
    if (!text) continue;
    if (total > 0 && total + text.length > maxChars) break;
    collected.push(text);
    total += text.length;
    if (total >= maxChars) break;
  }
  return collected.reverse().join("\n").trim(); // chronological order
}
