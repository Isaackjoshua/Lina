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

  // Turn these into real tests when you implement isAllowedAdmin.
  it.todo("accepts the configured account");
  it.todo("decides how letter case is treated (GitHub usernames are case-insensitive)");
});
