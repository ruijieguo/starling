import { describe, it, expect } from "vitest";
import {
  encodePath,
  decodePath,
  recallToSearchResults,
  statementToReadResult,
  workingSetToContext,
  captureToRememberBody,
  removeToForgetBody,
  collectUserText,
} from "../src/map.js";

describe("encodePath / decodePath roundtrip", () => {
  it("encodes and decodes back to original values", () => {
    const path = encodePath("t", "abc");
    expect(path).toBe("statement://t/abc");
    expect(decodePath(path)).toEqual({ tenant: "t", id: "abc" });
  });

  it("handles tenant and id with various characters", () => {
    const path = encodePath("myTenant", "stmt-42");
    expect(decodePath(path)).toEqual({ tenant: "myTenant", id: "stmt-42" });
  });

  it("returns null for garbage input", () => {
    expect(decodePath("garbage")).toBeNull();
  });

  it("returns null for http:// prefix", () => {
    expect(decodePath("http://x")).toBeNull();
  });

  it("returns null for empty string", () => {
    expect(decodePath("")).toBeNull();
  });

  it("returns null for statement:// without tenant/id", () => {
    expect(decodePath("statement://")).toBeNull();
  });

  it("returns null for statement:// with only tenant (no slash+id)", () => {
    expect(decodePath("statement://tenant")).toBeNull();
  });
});

describe("recallToSearchResults", () => {
  it("maps two hits to MemSearchResult array", () => {
    const hits = [
      { id: "id1", subject: "Alice", predicate: "knows", object: "Bob", score: 0.9 },
      { id: "id2", subject: "Cat", predicate: "is", object: "animal", score: 0.7 },
    ];
    const results = recallToSearchResults(hits, "t");
    expect(results).toHaveLength(2);

    expect(results[0]).toEqual({
      path: "statement://t/id1",
      startLine: 0,
      endLine: 0,
      score: 0.9,
      snippet: "Alice knows Bob",
      source: "memory",
      citation: "id1",
    });

    expect(results[1]).toEqual({
      path: "statement://t/id2",
      startLine: 0,
      endLine: 0,
      score: 0.7,
      snippet: "Cat is animal",
      source: "memory",
      citation: "id2",
    });
  });

  it("returns empty array for no hits", () => {
    expect(recallToSearchResults([], "t")).toEqual([]);
  });
});

describe("statementToReadResult", () => {
  it("renders text as subject predicate object_value", () => {
    const stmt = { subject_id: "Alice", predicate: "knows", object_value: "Bob" };
    const result = statementToReadResult(stmt, "statement://t/id1");
    expect(result).toEqual({
      text: "Alice knows Bob",
      path: "statement://t/id1",
    });
  });
});

describe("workingSetToContext", () => {
  it("returns the render string directly", () => {
    expect(workingSetToContext({ render: "R" })).toBe("R");
  });

  it("returns empty string if render is empty", () => {
    expect(workingSetToContext({ render: "" })).toBe("");
  });
});

describe("captureToRememberBody", () => {
  it("returns text and holder when both provided", () => {
    expect(captureToRememberBody("hi", "h")).toEqual({ text: "hi", holder: "h" });
  });

  it("returns only text when holder is omitted", () => {
    expect(captureToRememberBody("hi")).toEqual({ text: "hi" });
  });
});

describe("removeToForgetBody", () => {
  it("wraps memoryId in ids array", () => {
    expect(removeToForgetBody("x")).toEqual({ ids: ["x"] });
  });
});

describe("collectUserText", () => {
  it("gathers recent user messages in chronological order", () => {
    const msgs = [
      { role: "user", content: "I use pnpm" },
      { role: "assistant", content: "noted" },
      { role: "user", content: "and I'm in UTC+8" },
    ];
    expect(collectUserText(msgs)).toBe("I use pnpm\nand I'm in UTC+8");
  });

  it("skips assistant/system and non-text messages", () => {
    const msgs = [
      { role: "assistant", content: "hi" },
      { role: "user", content: "fact one" },
      { role: "system", content: "x" },
    ];
    expect(collectUserText(msgs)).toBe("fact one");
  });

  it("extracts text from array content blocks", () => {
    const msgs = [
      {
        role: "user",
        content: [
          { type: "text", text: "block A" },
          { type: "image" },
          { type: "text", text: "block B" },
        ],
      },
    ];
    expect(collectUserText(msgs)).toBe("block A\nblock B");
  });

  it("respects the maxChars budget, keeping the newest", () => {
    const msgs = [
      { role: "user", content: "old" },
      { role: "user", content: "new" },
    ];
    expect(collectUserText(msgs, 3)).toBe("new");
  });

  it("returns empty for no user content / non-array input", () => {
    expect(collectUserText([])).toBe("");
    expect(collectUserText(undefined)).toBe("");
    expect(collectUserText([{ role: "assistant", content: "x" }])).toBe("");
  });
});
