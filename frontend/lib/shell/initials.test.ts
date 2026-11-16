import { describe, expect, it } from "vitest";

import { getInitials } from "./initials";

describe("getInitials", () => {
  it("uses the first and last name", () => {
    expect(getInitials("Sessão de teste", "e2e@example.test")).toBe("ST");
    expect(getInitials("Ana", "ana@example.test")).toBe("A");
  });

  it("falls back to the email when the name is empty", () => {
    expect(getInitials(null, "analista@example.test")).toBe("A");
    expect(getInitials("   ", "  beta@example.test")).toBe("B");
  });

  it("never returns an empty string", () => {
    expect(getInitials(null, "")).toBe("?");
  });
});
