import { describe, expect, it } from "vitest";
import en from "../messages/en.json";
import sw from "../messages/sw.json";

function keys(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null) return [prefix];
  return Object.entries(value).flatMap(([k, v]) => keys(v, prefix ? `${prefix}.${k}` : k));
}

describe("translations", () => {
  it("has exactly the same keys in Swahili and English", () => {
    expect(keys(sw).sort()).toEqual(keys(en).sort());
  });

  it("has no empty strings", () => {
    for (const messages of [sw, en]) {
      for (const key of keys(messages)) {
        const text = key.split(".").reduce<unknown>((o, k) => (o as Record<string, unknown>)[k], messages);
        expect(text, key).toMatch(/\S/);
      }
    }
  });

  it("keeps fellowship and hackathon untranslated in Swahili (SPEC §3)", () => {
    expect(sw.types.fellowship).toBe("Fellowship");
    expect(sw.types.hackathon).toBe("Hackathon");
  });
});
