import { describe, it, expect } from "vitest";
import { parseConfig } from "../src/config.js";

describe("parseConfig", () => {
  const validBase = {
    dashboardUrl: "http://localhost:7777",
    token: "secret-tok",
    tenant: "myTenant",
    holder: "myAgent",
    autoCapture: false,
    autoRecall: false,
  };

  it("accepts a fully valid config", () => {
    const cfg = parseConfig(validBase);
    expect(cfg.dashboardUrl).toBe("http://localhost:7777");
    expect(cfg.token).toBe("secret-tok");
    expect(cfg.tenant).toBe("myTenant");
    expect(cfg.holder).toBe("myAgent");
    expect(cfg.autoCapture).toBe(false);
    expect(cfg.autoRecall).toBe(false);
  });

  it("throws when dashboardUrl is missing", () => {
    const raw = { token: "tok" };
    expect(() => parseConfig(raw)).toThrow(
      "starling memory plugin: missing required config 'dashboardUrl'"
    );
  });

  it("throws when dashboardUrl is empty string", () => {
    const raw = { dashboardUrl: "", token: "tok" };
    expect(() => parseConfig(raw)).toThrow(
      "starling memory plugin: missing required config 'dashboardUrl'"
    );
  });

  it("throws when token is missing", () => {
    const raw = { dashboardUrl: "http://localhost:7777" };
    expect(() => parseConfig(raw)).toThrow(
      "starling memory plugin: missing required config 'token'"
    );
  });

  it("throws when token is empty string", () => {
    const raw = { dashboardUrl: "http://localhost:7777", token: "" };
    expect(() => parseConfig(raw)).toThrow(
      "starling memory plugin: missing required config 'token'"
    );
  });

  it("error message does NOT contain token value when token is present but dashboardUrl missing", () => {
    // The key invariant: the actual token secret value must never appear in errors.
    // We test by omitting dashboardUrl while supplying a real-looking token value,
    // then verifying the error does not echo back the token secret.
    const secretValue = "super-secret-abc123";
    const raw = { token: secretValue };
    try {
      parseConfig(raw);
      expect.fail("should have thrown");
    } catch (e) {
      expect((e as Error).message).not.toContain(secretValue);
    }
  });

  it("error message does NOT contain token value when token field is wrong type", () => {
    // Passing a non-empty token object to ensure the value never leaks.
    const raw = { dashboardUrl: "http://localhost:7777", token: 42 };
    try {
      parseConfig(raw);
      expect.fail("should have thrown");
    } catch (e) {
      expect((e as Error).message).not.toContain("42");
    }
  });

  it("uses default tenant 'openclaw' when not provided", () => {
    const cfg = parseConfig({ dashboardUrl: "http://localhost:7777", token: "tok" });
    expect(cfg.tenant).toBe("openclaw");
  });

  it("uses default holder 'agent' when not provided", () => {
    const cfg = parseConfig({ dashboardUrl: "http://localhost:7777", token: "tok" });
    expect(cfg.holder).toBe("agent");
  });

  it("defaults autoCapture to true when not provided", () => {
    const cfg = parseConfig({ dashboardUrl: "http://localhost:7777", token: "tok" });
    expect(cfg.autoCapture).toBe(true);
  });

  it("defaults autoRecall to true when not provided", () => {
    const cfg = parseConfig({ dashboardUrl: "http://localhost:7777", token: "tok" });
    expect(cfg.autoRecall).toBe(true);
  });

  it("uses default autoCapture=true when non-boolean provided", () => {
    const cfg = parseConfig({ dashboardUrl: "http://localhost:7777", token: "tok", autoCapture: "yes" });
    expect(cfg.autoCapture).toBe(true);
  });

  it("uses default autoRecall=true when non-boolean provided", () => {
    const cfg = parseConfig({ dashboardUrl: "http://localhost:7777", token: "tok", autoRecall: 1 });
    expect(cfg.autoRecall).toBe(true);
  });

  it("applies provided tenant and holder", () => {
    const cfg = parseConfig({
      dashboardUrl: "http://localhost:7777",
      token: "tok",
      tenant: "corp",
      holder: "bot",
    });
    expect(cfg.tenant).toBe("corp");
    expect(cfg.holder).toBe("bot");
  });

  it("handles null/non-object raw gracefully — throws on missing dashboardUrl", () => {
    expect(() => parseConfig(null)).toThrow(
      "starling memory plugin: missing required config 'dashboardUrl'"
    );
    expect(() => parseConfig(42)).toThrow(
      "starling memory plugin: missing required config 'dashboardUrl'"
    );
  });
});
