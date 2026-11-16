import { describe, expect, it } from "vitest";

import { resolveSidebarMode } from "./sidebar-cookie";

describe("sidebar mode", () => {
  it("keeps the rail mode when the cookie says rail", () => {
    expect(resolveSidebarMode("rail")).toBe("rail");
  });

  it("defaults to expanded for missing or invalid values", () => {
    expect(resolveSidebarMode("expanded")).toBe("expanded");
    expect(resolveSidebarMode(undefined)).toBe("expanded");
    expect(resolveSidebarMode("compact")).toBe("expanded");
  });
});
