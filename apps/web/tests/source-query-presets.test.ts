import { describe, expect, it } from "vitest";
import {
  browserSafeScanSourceOrder,
  queryExamplesLabel,
  sourceQueryPresetByType,
} from "../src/lib/source-query-presets";

describe("source query presets", () => {
  it("keeps browser scan presets public-only", () => {
    expect(browserSafeScanSourceOrder).toEqual(["hackernews"]);
  });

  it("provides concrete examples for each supported source", () => {
    for (const source of [
      "hackernews",
      "github",
      "reddit",
      "stackexchange",
      "fixture",
    ]) {
      expect(sourceQueryPresetByType[source]?.examples.length).toBeGreaterThan(0);
    }
  });

  it("keeps credentialed source guidance operator-gated", () => {
    expect(sourceQueryPresetByType.github.credential).toMatch(/Operator-gated/i);
    expect(sourceQueryPresetByType.reddit.credential).toMatch(/Operator-gated/i);
    expect(sourceQueryPresetByType.stackexchange.credential).toMatch(
      /Operator-gated/i,
    );
  });

  it("renders a compact examples label", () => {
    expect(queryExamplesLabel("hackernews")).toContain("manual workflow");
  });
});
