/**
 * config.ts — StarlingMemoryConfig validation for the OpenClaw plugin.
 *
 * parseConfig accepts raw (unknown) plugin config from api.pluginConfig,
 * validates required fields, and fills in defaults for optional ones.
 *
 * SECURITY: token value is NEVER included in error messages or logs.
 */

export interface StarlingMemoryConfig {
  /** Base URL of the Starling dashboard API, e.g. "http://localhost:7777" */
  dashboardUrl: string;
  /** Bearer token for dashboard authentication. Never logged. */
  token: string;
  /** Tenant namespace for synthetic statement:// paths. Default: "openclaw" */
  tenant: string;
  /** Default holder identity sent to /api/remember. Default: "agent" */
  holder: string;
  /** Automatically capture session transcripts on compaction. Default: true */
  autoCapture: boolean;
  /** Automatically inject working-set context before agent starts. Default: true */
  autoRecall: boolean;
}

/**
 * Validates and coerces raw plugin config into StarlingMemoryConfig.
 *
 * Required fields: dashboardUrl, token (both must be non-empty strings).
 * Optional fields with defaults: tenant="openclaw", holder="agent",
 *   autoCapture=true, autoRecall=true (non-boolean values fall back to default).
 *
 * @throws {Error} if dashboardUrl or token are missing or empty.
 *   Error messages never include the token value.
 */
export function parseConfig(raw: unknown): StarlingMemoryConfig {
  const obj =
    raw !== null && typeof raw === "object" ? (raw as Record<string, unknown>) : {};

  // Required: dashboardUrl
  const dashboardUrl = obj["dashboardUrl"];
  if (typeof dashboardUrl !== "string" || dashboardUrl === "") {
    throw new Error(
      "starling memory plugin: missing required config 'dashboardUrl'"
    );
  }

  // Required: token (value intentionally excluded from error messages)
  const token = obj["token"];
  if (typeof token !== "string" || token === "") {
    throw new Error(
      "starling memory plugin: missing required config 'token'"
    );
  }

  // Optional with defaults
  const tenantRaw = obj["tenant"];
  const tenant =
    typeof tenantRaw === "string" && tenantRaw !== "" ? tenantRaw : "openclaw";

  const holderRaw = obj["holder"];
  const holder =
    typeof holderRaw === "string" && holderRaw !== "" ? holderRaw : "agent";

  const autoCaptureRaw = obj["autoCapture"];
  const autoCapture =
    typeof autoCaptureRaw === "boolean" ? autoCaptureRaw : true;

  const autoRecallRaw = obj["autoRecall"];
  const autoRecall =
    typeof autoRecallRaw === "boolean" ? autoRecallRaw : true;

  return { dashboardUrl, token, tenant, holder, autoCapture, autoRecall };
}

/**
 * Minimal configSchema shim compatible with definePluginEntry's configSchema slot.
 * Zod / TypeBox plugins expose a { parse } method; this mirrors that shape.
 */
export const configSchema = { parse: parseConfig };
