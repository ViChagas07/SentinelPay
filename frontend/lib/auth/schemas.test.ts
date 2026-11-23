import { describe, expect, it } from "vitest";

import {
  emailRequestSchema,
  emailSchema,
  passwordLoginSchema,
  registerSchema,
  resetPasswordSchema,
  verifyEmailSchema,
} from "./schemas";

describe("emailSchema", () => {
  it("normalizes case and spacing", () => {
    expect(emailSchema.parse("  Pessoa@Example.COM ")).toBe("pessoa@example.com");
  });

  it("rejects malformed addresses", () => {
    expect(emailSchema.safeParse("sem-arroba").success).toBe(false);
    expect(emailSchema.safeParse("a@b").success).toBe(false);
    expect(emailSchema.safeParse("a@@b.com").success).toBe(false);
  });
});

describe("registerSchema", () => {
  const base = {
    nome_completo: "Pessoa Exemplo",
    email: "pessoa@example.com",
    senha: "frase secreta longa",
    aceite_termos: true,
    aceite_privacidade: true,
  };

  it("accepts a complete payload", () => {
    expect(registerSchema.safeParse(base).success).toBe(true);
  });

  it("refuses extra fields", () => {
    expect(registerSchema.safeParse({ ...base, role: "admin" }).success).toBe(false);
  });

  it("requires both consents", () => {
    expect(registerSchema.safeParse({ ...base, aceite_privacidade: false }).success).toBe(false);
  });
});

describe("other schemas", () => {
  it("validates a token request", () => {
    expect(verifyEmailSchema.safeParse({ token: "x".repeat(20) }).success).toBe(true);
    expect(verifyEmailSchema.safeParse({ token: "curto" }).success).toBe(false);
  });

  it("validates the reset payload", () => {
    const payload = { token: "x".repeat(20), nova_senha: "outra frase longa" };

    expect(resetPasswordSchema.safeParse(payload).success).toBe(true);
    expect(resetPasswordSchema.safeParse({ ...payload, extra: 1 }).success).toBe(false);
  });

  it("normalizes the e-mail request", () => {
    expect(emailRequestSchema.parse({ email: "A@B.com" })).toEqual({ email: "a@b.com" });
  });

  it("requires e-mail and password on login", () => {
    expect(passwordLoginSchema.safeParse({ email: "a@b.com", senha: "" }).success).toBe(false);
  });
});
