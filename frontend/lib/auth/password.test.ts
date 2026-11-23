import { describe, expect, it } from "vitest";

import type { PasswordPolicy } from "@/lib/auth/capabilities";

import { identifierFragments, passwordIssues, passwordStrength } from "./password";

const POLICY: PasswordPolicy = {
  minLength: 10,
  maxLength: 128,
  requirements: ["min_length", "max_length", "not_common", "not_personal"],
  hibpEnabled: false,
};

describe("passwordIssues", () => {
  it("accepts a long passphrase", () => {
    expect(passwordIssues("correto cavalo bateria grampo", POLICY)).toEqual([]);
  });

  it("flags short passwords", () => {
    expect(passwordIssues("curta1", POLICY)).toContain("too_short");
  });

  it("flags over-long passwords", () => {
    expect(passwordIssues("a".repeat(129), POLICY)).toContain("too_long");
  });

  it("flags the common list regardless of case and spacing", () => {
    expect(passwordIssues("Senha123 ", POLICY)).toContain("too_common");
  });

  it("flags passwords containing the e-mail or name", () => {
    const identifiers = identifierFragments("mariana.silva@example.com", "Mariana Silva");

    expect(passwordIssues("mariana-2026-forte", POLICY, identifiers)).toContain(
      "contains_identifier",
    );
    expect(passwordIssues("silva-forte-2026", POLICY, identifiers)).toContain(
      "contains_identifier",
    );
    expect(passwordIssues("outra frase longa aqui", POLICY, identifiers)).toEqual([]);
  });
});

describe("passwordStrength", () => {
  it("starts weak for an empty value", () => {
    expect(passwordStrength("", POLICY)).toBe("weak");
  });

  it("keeps common passwords weak", () => {
    expect(passwordStrength("senha12345", POLICY)).toBe("weak");
  });

  it("grows with length and character variety", () => {
    expect(passwordStrength("frase longa ok", POLICY)).toBe("fair");
    expect(passwordStrength("Frase-longa-2026", POLICY)).toBe("strong");
  });
});

describe("identifierFragments", () => {
  it("drops short fragments and accents", () => {
    expect(identifierFragments("jo@example.com", "Jo Cit")).toEqual([]);
    expect(identifierFragments("joana.pereira@example.com", "Joana Pereira")).toEqual([
      "joana",
      "pereira",
      "joana",
      "pereira",
    ]);
  });
});
