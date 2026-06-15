# OpenClaw + Starling memory plugin — isolated integration container.
#
# Topology (see docker/README.md): this container runs ONLY OpenClaw. The
# Starling dashboard runs on the macOS host (it loads a native Mach-O
# `_core.so` that cannot load inside a Linux container). The plugin reaches
# the host dashboard via `host.docker.internal`.
#
# SECRETS: no token / api key is ever baked into an image layer. The dashboard
# URL and bearer token arrive only at runtime via environment variables
# (STARLING_DASHBOARD_URL / STARLING_TOKEN), and the entrypoint templates them
# into ~/.openclaw/openclaw.json inside the running container's ephemeral fs.
#
# OpenClaw is pinned to 2026.6.6 — the same version the plugin was type-checked
# and built against (integrations/openclaw/package-lock.json).

FROM node:22-slim

ARG OPENCLAW_VERSION=2026.6.6

# git is occasionally needed by npm during plugin/dep resolution; tini gives us
# a real PID 1 so signals (compose stop) reach node cleanly.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates tini curl \
    && rm -rf /var/lib/apt/lists/*

# --- Install OpenClaw (pinned) -------------------------------------------------
RUN npm install -g "openclaw@${OPENCLAW_VERSION}" \
    && openclaw --version

# --- Build the Starling memory plugin inside the image -------------------------
# We copy source (NOT the host's dist/ or node_modules/, see .dockerignore) and
# build a fresh dist with the pinned openclaw types. This avoids shipping a
# stale dist and keeps the image hermetic.
#
# We deliberately do NOT `npm ci`: the plugin's only devDeps are typescript +
# @sinclair/typebox + vitest, and the vitest tree (→ vite) is large and not
# needed in a runtime image. We install exactly two packages, pinned to the
# lockfile versions:
#   - typescript            — build-time only (tsc), pruned after build
#   - @sinclair/typebox     — RUNTIME dependency: dist/index.js does
#                             `import { Type } from "@sinclair/typebox"`, so it
#                             must remain resolvable from the plugin dir.
# `openclaw/plugin-sdk/plugin-entry` is provided by the global openclaw install
# (declared as a peerDependency).
WORKDIR /opt/starling-plugin
COPY package.json tsconfig.json openclaw.plugin.json ./
COPY src ./src
# npm can hit transient ECONNRESET against the registry; retry a few times.
RUN npm config set fetch-retries 5 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm install --no-save --no-audit --no-fund \
         typescript@5.9.3 @sinclair/typebox@0.34.48 \
    && npm run build \
    && npm uninstall --no-save typescript || true \
    && npm install --no-save --no-audit --no-fund @sinclair/typebox@0.34.48 \
    && ls -la dist node_modules/@sinclair

# In-container e2e harnesses (loaded by docker/integration-test.sh via
# `compose exec node ...`). They import the compiled dist/*.js directly.
COPY docker/roundtrip.mjs docker/downgrade.mjs ./

# OpenClaw discovers the plugin via plugins.load.paths pointing at this dir
# (templated into openclaw.json by the entrypoint). The manifest
# (openclaw.plugin.json) + package.json "openclaw.extensions" -> ./dist/index.js
# make it a discoverable native plugin.

# --- Runtime config templating -------------------------------------------------
# OpenClaw resolves its config via OPENCLAW_CONFIG_PATH (an explicit file). Do
# NOT set OPENCLAW_HOME — OpenClaw treats it as its own base dir and appends
# `/.openclaw`, which silently relocates (and doubles) the config path.
ENV OPENCLAW_CONFIG_PATH=/root/.openclaw/openclaw.json \
    OPENCLAW_STATE_DIR=/root/.openclaw
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Defaults; override at `docker compose up` / `docker run -e`.
ENV STARLING_DASHBOARD_URL="http://host.docker.internal:8787" \
    STARLING_TENANT="openclaw" \
    STARLING_HOLDER="agent" \
    STARLING_AUTO_RECALL="true" \
    STARLING_AUTO_CAPTURE="true" \
    STARLING_PLUGIN_DIR="/opt/starling-plugin"
# NOTE: STARLING_TOKEN is intentionally NOT set here — it must be injected at
# runtime so the secret never lands in an image layer.

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
# Default command keeps the container alive for `docker compose exec` driven
# integration testing; override to run a one-shot OpenClaw command.
CMD ["sleep", "infinity"]
