import { describe, expect, it } from "vitest";

import { BACK_FALLBACK_PATH, resolveBackNavigationAction } from "./back-navigation";

describe("resolveBackNavigationAction", () => {
  it("returns to the previous entry when the browser has history", () => {
    expect(resolveBackNavigationAction(2)).toBe("history");
    expect(resolveBackNavigationAction(9)).toBe("history");
  });

  it("falls back to the landing page on a fresh tab", () => {
    expect(resolveBackNavigationAction(0)).toBe("fallback");
    expect(resolveBackNavigationAction(1)).toBe("fallback");
  });

  it("points the fallback at the public home", () => {
    expect(BACK_FALLBACK_PATH).toBe("/");
  });
});
