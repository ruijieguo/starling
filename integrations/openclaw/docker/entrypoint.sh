#!/usr/bin/env bash
# Entrypoint: render the OpenClaw config from runtime env, then exec CMD.
#
# OpenClaw resolves its config from OPENCLAW_CONFIG_PATH (set in the Dockerfile).
# The Starling dashboard bearer token (STARLING_TOKEN) and URL
# (STARLING_DASHBOARD_URL) are injected as environment variables at container
# start. We write them into the config *here*, at runtime, inside the
# container's ephemeral filesystem — never into an image layer and never into
# git. Values are JSON-encoded via node so their bytes can never break the file
# or be shell-interpolated.
set -euo pipefail

: "${STARLING_DASHBOARD_URL:?STARLING_DASHBOARD_URL must be set}"
: "${STARLING_TOKEN:?STARLING_TOKEN must be set (inject at runtime, never bake into the image)}"
: "${STARLING_TENANT:=openclaw}"
: "${STARLING_HOLDER:=agent}"
: "${STARLING_AUTO_RECALL:=true}"
: "${STARLING_AUTO_CAPTURE:=true}"
: "${STARLING_PLUGIN_DIR:=/opt/starling-plugin}"
: "${OPENCLAW_CONFIG_PATH:=/root/.openclaw/openclaw.json}"
: "${OPENCLAW_STATE_DIR:=/root/.openclaw}"

CONFIG="${OPENCLAW_CONFIG_PATH}"
mkdir -p "$(dirname "${CONFIG}")" "${OPENCLAW_STATE_DIR}/workspace"

# Render config with node (proper JSON escaping; reads secrets from env, never argv).
node > "${CONFIG}" <<'NODE'
const stateDir = process.env.OPENCLAW_STATE_DIR || "/root/.openclaw";
const cfg = {
  agents: { defaults: { workspace: stateDir + "/workspace" } },
  plugins: {
    enabled: true,
    // Discover the Starling plugin from the path we built into the image.
    // OpenClaw resolves the dir's entry via its package.json
    // "openclaw.extensions" -> ./dist/index.js.
    load: { paths: [process.env.STARLING_PLUGIN_DIR] },
    // Claim the exclusive memory slot with our plugin id.
    slots: { memory: "starling" },
    entries: {
      starling: {
        enabled: true,
        config: {
          dashboardUrl: process.env.STARLING_DASHBOARD_URL,
          token: process.env.STARLING_TOKEN,
          tenant: process.env.STARLING_TENANT,
          holder: process.env.STARLING_HOLDER,
          autoRecall: process.env.STARLING_AUTO_RECALL !== "false",
          autoCapture: process.env.STARLING_AUTO_CAPTURE !== "false",
        },
      },
    },
  },
};
process.stdout.write(JSON.stringify(cfg, null, 2) + "\n");
NODE

chmod 600 "${CONFIG}"

# Redacted confirmation — never print the token.
echo "[entrypoint] wrote ${CONFIG}"
echo "[entrypoint]   plugins.slots.memory = starling"
echo "[entrypoint]   plugins.load.paths   = [${STARLING_PLUGIN_DIR}]"
echo "[entrypoint]   dashboardUrl         = ${STARLING_DASHBOARD_URL}"
echo "[entrypoint]   token                = <redacted, ${#STARLING_TOKEN} chars>"

exec "$@"
