# OpenClaw + Starling memory plugin — Docker integration environment

Run OpenClaw in an isolated container with the Starling memory plugin installed,
talking to a Starling dashboard running on your **host**.

## Topology (and why)

```
┌─ macOS host ───────────────────────────────┐        ┌─ docker container ─────────────┐
│ Starling dashboard (FastAPI + uvicorn)      │  HTTP  │ OpenClaw 2026.6.6              │
│   loads native _core.so (Mach-O, arm64)     │◀───────│   + @starling/openclaw-memory  │
│   bind 0.0.0.0:8787  (token-auth)           │ host.  │   plugins.slots.memory=starling│
│   ~/.starling/{starling.json, dashboard.db} │ docker.│   reaches host via             │
│                                             │internal│   host.docker.internal:<port>  │
└─────────────────────────────────────────────┘        └────────────────────────────────┘
```

**The dashboard runs on the host, not in a container, on purpose.** Starling's
engine is a native `_core.so` compiled as a **macOS Mach-O (arm64)** binary. It
**cannot be loaded inside a Linux container.** So:

- **Starling dashboard → host** (your existing venv + already-compiled `_core.so`).
- **OpenClaw → container** (isolated; does not touch your real `~/.openclaw`
  install or the system OpenClaw at `/opt/homebrew/lib/node_modules/openclaw`).
- The plugin reaches the host dashboard over `host.docker.internal:<port>`.

The compose file therefore defines **only** the `openclaw` service.

## Secrets

The dashboard bearer **token is never written into the image or this repo.** It
is read from your host environment at run time and templated into the
container's `~/.openclaw/openclaw.json` by `entrypoint.sh` (inside the running
container's ephemeral filesystem only). `STARLING_TOKEN` is intentionally absent
from the Dockerfile `ENV`; both `entrypoint.sh` and compose fail fast if it is
unset.

---

## 1. Start the Starling dashboard on the host

The dashboard launcher is `scripts/run_dashboard.py` (uvicorn). For the container
to reach it, bind to `0.0.0.0` (the default `127.0.0.1` is not reachable from the
container). The bearer token lives in `~/.starling/starling.json`.

From the repo root (`/Users/jaredguo-mini/develop/memory/starling`):

```bash
# Bind to all interfaces so host.docker.internal resolves to the dashboard.
STARLING_DASH_HOST=0.0.0.0 \
  .venv/bin/python scripts/run_dashboard.py --no-build
# → "Dashboard ready → http://127.0.0.1:8787/#token=<token>"
```

Notes:
- `--no-build` skips the SvelteKit frontend build (the integration test only
  needs the JSON API).
- The dashboard reads `llm` + `embedder` (and the `token`) from
  `~/.starling/starling.json`. With an embedder configured (the repo's config
  uses dashscope `text-embedding-v4`, dim 1024), captured statements get
  embedded by the background tick (`tick_interval_s`, default 30s).
- To avoid touching your normal dashboard DB, point at a throwaway DB and a
  spare port:
  ```bash
  STARLING_DASH_HOST=0.0.0.0 STARLING_DASH_PORT=8799 \
    STARLING_DASH_DB=/tmp/starling-e2e.db STARLING_DASH_TENANT=openclaw \
    STARLING_DASH_TICK_INTERVAL=5 \
    .venv/bin/python scripts/run_dashboard.py --no-build
  ```

### Get the token

```bash
export STARLING_TOKEN=$(python3 -c \
  "import json,os;print(json.load(open(os.path.expanduser('~/.starling/starling.json')))['token'])")
```

---

## 2. Bring up OpenClaw + the plugin

```bash
cd integrations/openclaw
STARLING_TOKEN=$STARLING_TOKEN docker compose -f docker/docker-compose.yml up --build
# default STARLING_PORT=8787; override if the dashboard is on another port:
#   STARLING_TOKEN=$STARLING_TOKEN STARLING_PORT=8799 docker compose -f docker/docker-compose.yml up --build
```

Environment passed through to the container (all overridable; only `STARLING_TOKEN`
is required):

| Var                      | Default                                   | Purpose                              |
| ------------------------ | ----------------------------------------- | ------------------------------------ |
| `STARLING_TOKEN`         | — (required)                              | Dashboard bearer token (host env)    |
| `STARLING_PORT`          | `8787`                                     | Host dashboard port                  |
| `STARLING_TENANT`        | `openclaw`                                 | Tenant for synthetic `statement://`  |
| `STARLING_HOLDER`        | `agent`                                    | Holder identity sent to `/api/remember` |
| `STARLING_AUTO_RECALL`   | `true`                                     | `before_prompt_build` context inject |
| `STARLING_AUTO_CAPTURE`  | `true`                                     | `before_compaction` transcript capture |

The container stays up (`sleep infinity`) so you can drive it with
`docker compose exec`.

### How the plugin is installed (mechanism)

OpenClaw discovers third-party plugins three ways (`docs/plugins/` + `docs/tools/plugin.md`):
`openclaw plugins install <pkg|path>` (ClawHub→npm, or a local dir/tarball), the
workspace/global `extensions/` dirs, or **`plugins.load.paths`** in the config.

This image uses **`plugins.load.paths`**: the Dockerfile builds the plugin to
`/opt/starling-plugin` (manifest `openclaw.plugin.json` at the dir root, entry at
`dist/index.js` via `package.json` → `openclaw.extensions`), and `entrypoint.sh`
writes a config pointing `plugins.load.paths` at it, selecting the slot with
`plugins.slots.memory = "starling"` and supplying `plugins.entries.starling.config`
(`dashboardUrl`, `token`, `tenant`, …).

**Config resolution gotcha:** OpenClaw 2026.6.6 resolves its config from
**`OPENCLAW_CONFIG_PATH`** (an explicit file). The container sets it to
`/root/.openclaw/openclaw.json`. Do **not** set `OPENCLAW_HOME` — OpenClaw treats
it as its own base dir and appends `/.openclaw`, silently relocating the config
to `…/.openclaw/.openclaw/openclaw.json` (the config then appears empty:
`openclaw config get plugins.slots.memory` → "Config path not found"). Verify
discovery with `openclaw plugins inspect starling` (should show `Status: loaded`).

---

## 3. Integration test

```bash
cd integrations/openclaw
STARLING_TOKEN=$STARLING_TOKEN STARLING_PORT=8799 ./docker/integration-test.sh
```

What it does (all assertions against the **host** dashboard):

0. Precondition: host dashboard reachable at `http://127.0.0.1:$STARLING_PORT`.
1. `docker compose up` (builds the image once if missing; `BUILD=1` forces a
   rebuild). Prints the redacted entrypoint config.
2. `openclaw plugins inspect starling` → plugin **discovered + loaded**.
3. Round-trip via `roundtrip.mjs` (runs **inside** the container, importing the
   compiled `dist/*.js` — the exact code OpenClaw loads): `status` → `remember`
   → `sync/tick` → `recall`. Asserts the host statement count **increased**
   (`/api/overview` → `counts.statements`).
4. Downgrade (`downgrade.mjs`): point the client at an unreachable URL → reads
   degrade (`recall` → `[]`, `working_set` → `null`, **no throw**), `remember`
   **enqueues** (queue length grows); then restore the URL and `flushQueue()`
   drains it.

The test tears the container down (`compose down -v`) on exit.

### Driving a single memory operation by hand

```bash
cd integrations/openclaw
docker compose -f docker/docker-compose.yml exec openclaw \
  node /opt/starling-plugin/roundtrip.mjs
# inspect what landed:
curl -s "http://127.0.0.1:8799/api/statements?limit=20" \
  -H "Authorization: Bearer $STARLING_TOKEN" | python3 -m json.tool
```

---

## 4. Observed behavior (self-audit) — read before relying on recall

These were verified during the end-to-end run; some are **Starling-side**
characteristics, not plugin/docker defects.

1. **Write path works end-to-end.** `remember` from inside the container creates
   real statements on the host dashboard across the `host.docker.internal`
   boundary (statement count `0 → 1`, with vectors in `statement_vectors`). The
   plugin's HTTP transport, the slot wiring, and the topology are sound.

2. **`/api/recall` empty for freshly-remembered data — ROOT-CAUSED + FIXED.**
   The original symptom (recall returned nothing for a statement that exists and
   is embedded) was **not** a Starling retrieval defect. It was a **holder
   dimension mismatch**: the plugin captured under `cfg.holder` (`"agent"`) but
   `/api/recall` recalled under the dashboard's `agent` (`"self"`), and the
   candidate SQL `s.holder_id = ?` excluded the row. Reproduced host-side and
   fixed by (a) adding a `holder` override to `/api/recall` + `/api/working_set`
   (commit `122f1ff`) and (b) the plugin passing `cfg.holder` on recall, matching
   capture (commit `2e0e3ce`); plus case-insensitive `perspective` (`d78dd8d`).
   Recall now returns plugin-captured memories. **Prereq still applies:** an
   embedder must be configured (semantic cosine) and the statement must be
   embedded by a tick first (see #4).

3. **Auto-recall (`before_prompt_build`)** uses
   `working_set(interlocutor=cfg.holder, holder=cfg.holder)` — holder now
   matches capture (fixed with #2). Content quality still depends on the embedder
   + tick. Note: `working_set` uses `cfg.holder` as *both* agent and
   interlocutor (self-working-set); a true "other party" dimension is a
   follow-up (the OpenClaw hook does not surface a counterpart/interlocutor id).

4. **Capture → search timing.** Statements are embedded by the dashboard's
   **background tick** (`tick_interval_s`). For a deterministic test, either set
   a short interval (`STARLING_DASH_TICK_INTERVAL=5`) or `POST /api/tick` before
   searching. `roundtrip.mjs` calls `sync()` (→ `/api/tick`) and waits ~3s.

5. **Extraction is non-deterministic and input-sensitive.** `POST /api/remember`
   returns `200 {outcome:"accepted", statement_ids:[…]}` but `statement_ids` can
   be **empty** when the LLM extractor finds no clear subject/predicate/object
   (e.g. a bare "standup at 9:30" reminder). Interlocutor-attributed, relational
   facts ("Bob's favorite database is Postgres") extract reliably. The plugin's
   `remember(text, holder)` does **not** send an `interlocutor`; consider whether
   capture should pass one.

6. **`autoCapture` (`before_compaction`)** persists the recent user-stated window
   (newest user messages up to a char budget, via `collectUserText`) so the
   extractor distils facts from more than the last message. Full sessionFile
   JSONL ingestion remains a follow-up. Left on by default.

7. **Plugin doctor: clean.** Earlier 2026.6.6 warnings — "must declare
   contracts.tools" (×2 for the write tools), "non-capability shape", and "legacy
   before_agent_start" — are all resolved: the manifest declares
   `contracts.tools: ["memory_store","memory_forget"]`, registration is the
   unified `registerMemoryCapability({runtime,promptBuilder,flushPlanResolver})`,
   and auto-recall uses `before_prompt_build`. `openclaw plugins doctor` →
   **"No plugin issues detected."**
   > **docker build gotcha:** a plain `docker compose build` (even `--no-cache`)
   > can be fed a **stale `dist`** by docker desktop's buildkit/virtiofs file
   > cache — the container ends up running old code. Verify the container's code
   > matches host (`grep -c registerMemoryCapability /opt/starling-plugin/dist/index.js`).
   > To force fresh code without a working rebuild, bind-mount the host build:
   > `-v "$PWD/dist:/opt/starling-plugin/dist" -v "$PWD/src:/opt/starling-plugin/src"`,
   > or restart docker desktop / `docker builder prune`.

---

## Files

| File                  | Purpose                                                              |
| --------------------- | ------------------------------------------------------------------- |
| `openclaw.Dockerfile` | node:22-slim + `openclaw@2026.6.6` (pinned) + builds the plugin      |
| `entrypoint.sh`       | Renders `openclaw.json` from env at runtime (token never baked in)  |
| `docker-compose.yml`  | The single `openclaw` service; passes env through; `host.docker.internal` |
| `.dockerignore`       | Keeps host `dist/`, `node_modules/`, and secrets out of the build context |
| `integration-test.sh` | Orchestrates the end-to-end test from the host                      |
| `roundtrip.mjs`       | In-container write/recall round-trip against the host dashboard      |
| `downgrade.mjs`       | In-container degradation + retry-queue-flush check                  |
