import { describe, expect, it } from "vitest";
import { safeExternalUrl } from "../src/lib/url";

describe("safeExternalUrl", () => {
  it("allows absolute http and https URLs", () => {
    expect(safeExternalUrl("https://example.com/path")).toBe(
      "https://example.com/path",
    );
    expect(safeExternalUrl("http://example.com/path")).toBe(
      "http://example.com/path",
    );
  });

  it("blocks unsafe or relative URLs", () => {
    expect(safeExternalUrl("javascript:alert(1)")).toBeUndefined();
    expect(safeExternalUrl("data:text/html,<h1>bad</h1>")).toBeUndefined();
    expect(safeExternalUrl("/local/path")).toBeUndefined();
  });
});
