import { describe, expect, it } from "vitest";
import { localeAlternates } from "../src/lib/seo";

describe("localeAlternates", () => {
  it("links both languages and defaults to Swahili", () => {
    const alternates = localeAlternates("en", "/about");
    expect(alternates.canonical).toBe("http://localhost:3000/en/about");
    expect(alternates.languages).toEqual({
      sw: "http://localhost:3000/sw/about",
      en: "http://localhost:3000/en/about",
      "x-default": "http://localhost:3000/sw/about",
    });
  });
});
