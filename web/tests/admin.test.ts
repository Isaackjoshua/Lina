import { describe, expect, it } from "vitest";
import { isAllowedAdmin } from "../src/lib/admin";

describe("isAllowedAdmin", () => {
  it("rejects everyone when ADMIN_GITHUB_USERNAME is unset or blank", () => {
    expect(isAllowedAdmin("izy", undefined)).toBe(false);
    expect(isAllowedAdmin("izy", "")).toBe(false);
    expect(isAllowedAdmin("", "")).toBe(false);
    expect(isAllowedAdmin(undefined, undefined)).toBe(false);
  });

  it("rejects a missing login", () => {
    expect(isAllowedAdmin(undefined, "izy")).toBe(false);
    expect(isAllowedAdmin(null, "izy")).toBe(false);
  });

  it("rejects a different account", () => {
    expect(isAllowedAdmin("someone-else", "izy")).toBe(false);
    expect(isAllowedAdmin("izy2", "izy")).toBe(false);
  });

  it("accepts the configured account", () => {
    expect(isAllowedAdmin("izy", "izy")).toBe(true);
  });

  it("ignores letter case and spaces around the configured name", () => {
    expect(isAllowedAdmin("Izy", "izy")).toBe(true);
    expect(isAllowedAdmin("izy", " IZY ")).toBe(true);
  });

  it("does not trim the login itself, which comes from GitHub, not from a person typing", () => {
    expect(isAllowedAdmin(" izy", "izy")).toBe(false);
  });

  it("rejects everyone when the configured name is only spaces", () => {
    expect(isAllowedAdmin("", "   ")).toBe(false);
    expect(isAllowedAdmin("   ", "   ")).toBe(false);
  });
});
