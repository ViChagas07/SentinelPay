import { describe, expect, it } from "vitest";

import { evaluatePasswordMatch } from "@/lib/auth/password-match";

describe("evaluatePasswordMatch", () => {
  it("stays idle while both fields are empty", () => {
    expect(evaluatePasswordMatch("", "")).toBe("idle");
  });

  it("stays idle while the confirmation is empty", () => {
    expect(evaluatePasswordMatch("senha-forte-2026", "")).toBe("idle");
  });

  it("returns match when both values are identical", () => {
    expect(evaluatePasswordMatch("senha-forte-2026", "senha-forte-2026")).toBe("match");
  });

  it("returns mismatch when the values differ", () => {
    expect(evaluatePasswordMatch("senha-forte-2026", "senha-forte-2025")).toBe("mismatch");
  });

  it("treats a partial confirmation as mismatch", () => {
    expect(evaluatePasswordMatch("senha-forte-2026", "senha")).toBe("mismatch");
  });

  it("is case and whitespace sensitive", () => {
    expect(evaluatePasswordMatch("Senha Forte", "senha forte")).toBe("mismatch");
    expect(evaluatePasswordMatch("senha ", "senha")).toBe("mismatch");
  });

  it("goes back to idle when both sides are cleared", () => {
    expect(evaluatePasswordMatch("", "")).toBe("idle");
  });
});
