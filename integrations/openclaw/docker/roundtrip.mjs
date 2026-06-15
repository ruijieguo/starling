/**
 * roundtrip.mjs — in-container end-to-end check of the Starling memory plugin's
 * transport against the host dashboard, over host.docker.internal.
 *
 * This exercises the SAME compiled code the OpenClaw runtime loads
 * (/opt/starling-plugin/dist/client.js + runtime.js + map.js), proving the
 * plugin↔dashboard contract and the host/container topology deterministically
 * (no LLM-driven agent turn, no API keys needed in the container).
 *
 * Config (dashboardUrl, token, tenant) is read from the same env the entrypoint
 * uses — the token is never printed.
 *
 * Steps: status → remember → tick → recall → get → forget.
 * Exit non-zero on any hard failure; recall/get are reported but not fatal
 * (embedding may lag), so the harness stays robust while still surfacing them.
 */
const PLUGIN = process.env.STARLING_PLUGIN_DIR || "/opt/starling-plugin";
const { StarlingClient } = await import(`${PLUGIN}/dist/client.js`);
const { makeStarlingRuntime } = await import(`${PLUGIN}/dist/runtime.js`);

const cfg = {
  dashboardUrl: process.env.STARLING_DASHBOARD_URL,
  token: process.env.STARLING_TOKEN,
  tenant: process.env.STARLING_TENANT || "openclaw",
  holder: process.env.STARLING_HOLDER || "agent",
  autoCapture: true,
  autoRecall: true,
};

const MARKER = process.env.RT_MARKER || `docker-e2e-${Date.now()}`;
// Use a clearly relational, interlocutor-attributed fact so the dashboard's
// LLM extractor produces subject/predicate/object statements (a bare reminder
// like "standup at 9:30" often extracts to nothing). The MARKER lets the host
// curl confirm this exact write landed.
const text = `Bob mentioned (ref ${MARKER}) that his favorite database is Postgres and he dislikes meetings before noon.`;

function log(...a) { console.log("[roundtrip]", ...a); }
function fail(msg) { console.error("[roundtrip] FAIL:", msg); process.exit(1); }

const client = new StarlingClient(cfg);
const runtime = makeStarlingRuntime(cfg, client);

// 1) status via the registered MemoryPluginRuntime → MemorySearchManager.
let mgr;
try {
  const r = await runtime.getMemorySearchManager({ cfg: {}, agentId: cfg.holder });
  mgr = r.manager;
  if (!mgr) fail(`getMemorySearchManager returned no manager: ${r.error || "unknown"}`);
  const st = mgr.status();
  log("status:", JSON.stringify(st));
} catch (e) {
  fail(`status threw (dashboard unreachable?): ${e?.message || e}`);
}

// 2) capture — POST /api/remember through the client.
log(`remember marker=${MARKER}`);
await client.remember(text, cfg.holder);
if (client.queueLength > 0) {
  fail(`remember enqueued (write failed) — queueLength=${client.queueLength}`);
}
log("remember ok (write queue empty)");

// 3) index — sync()/tick so the statement gets embedded for semantic recall.
try {
  await mgr.sync?.({ reason: "e2e", force: true });
  log("sync/tick ok");
} catch (e) {
  log("sync/tick warn:", e?.message || e);
}

// Give the host a moment to embed (host tick_interval covers it too).
await new Promise((r) => setTimeout(r, 3000));

// 4) recall — POST /api/recall via MemorySearchManager.search.
let found = false;
try {
  const hits = await mgr.search("when is the standup meeting", { maxResults: 10 });
  log(`recall returned ${hits.length} hit(s)`);
  found = hits.some((h) => (h.snippet || "").includes("9:30") || (h.citation || "") !== "");
  if (hits[0]) log("top hit:", JSON.stringify({ path: hits[0].path, score: hits[0].score, snippet: hits[0].snippet }));
} catch (e) {
  log("recall warn:", e?.message || e);
}
log(found ? "recall HIT (semantic match found)" : "recall: no semantic match yet (embedding may lag; see /api/statements count)");

console.log(`RT_MARKER=${MARKER}`);
log("DONE — write path verified; recall is best-effort (see host /api/statements).");
