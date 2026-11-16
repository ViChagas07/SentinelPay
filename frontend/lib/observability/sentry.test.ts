import { describe, expect, it } from "vitest";

import {
  observabilityConfigured,
  readObservabilityConfig,
  resetObservabilityForTests,
  sanitizeEvent,
  sanitizeText,
} from "./sentry";

describe("observability configuration", () => {
  it("stays disabled without a DSN", () => {
    expect(readObservabilityConfig({})).toBeNull();
    expect(observabilityConfigured({})).toBe(false);
  });

  it("accepts HTTPS DSNs and clamps the sample rate", () => {
    const config = readObservabilityConfig({
      NEXT_PUBLIC_SENTRY_DSN: "https://public@example.sentry.io/42",
      NEXT_PUBLIC_SENTRY_ENVIRONMENT: "preview",
      NEXT_PUBLIC_SENTRY_RELEASE: "abc123",
      NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE: "4",
    });

    expect(config).toEqual({
      dsn: "https://public@example.sentry.io/42",
      environment: "preview",
      release: "abc123",
      tracesSampleRate: 1,
    });
  });

  it("rejects insecure or malformed DSNs outside localhost", () => {
    expect(readObservabilityConfig({ NEXT_PUBLIC_SENTRY_DSN: "http://example.test/1" })).toBeNull();
    expect(readObservabilityConfig({ NEXT_PUBLIC_SENTRY_DSN: "not-a-dsn" })).toBeNull();
  });

  it("defaults the environment to NODE_ENV", () => {
    const config = readObservabilityConfig({
      NEXT_PUBLIC_SENTRY_DSN: "https://public@example.sentry.io/42",
      NODE_ENV: "production",
    });

    expect(config?.environment).toBe("production");
    expect(config?.tracesSampleRate).toBe(0);
  });

  it("resets the module between tests", () => {
    resetObservabilityForTests();
    expect(observabilityConfigured({})).toBe(false);
  });
});

describe("observability sanitization", () => {
  it("redacts PII, tokens and private query parameters", () => {
    const text = sanitizeText(
      "Falha para joao.silva@example.com CPF 123.456.789-09 CNPJ 12.345.678/0001-90 telefone (11) 98765-4321 Bearer abc.def.ghi token=segredo https://app.test/doc?document=contrato.pdf",
    );

    expect(text).not.toContain("joao.silva@example.com");
    expect(text).not.toContain("123.456.789-09");
    expect(text).not.toContain("12.345.678/0001-90");
    expect(text).not.toContain("98765-4321");
    expect(text).not.toContain("abc.def.ghi");
    expect(text).not.toContain("segredo");
    expect(text).not.toContain("contrato.pdf");
    expect(text).toContain("[REDACTED]");
  });

  it("keeps only safe event fields and sanitized exceptions", () => {
    const event = sanitizeEvent({
      type: undefined,
      event_id: "abc",
      timestamp: 1,
      platform: "javascript",
      level: "error",
      environment: "test",
      release: "r1",
      user: { email: "joao.silva@example.com" },
      request: { url: "https://app.test/doc?file=contrato.pdf" },
      breadcrumbs: [{ message: "documento confidencial" }],
      extra: { documentText: "conteudo do documento" },
      contexts: { document: { text: "conteudo" } },
      tags: { boundary: "app", "invalid key": "value" },
      exception: {
        values: [
          {
            type: "Error",
            value: "Falha para maria@example.com com CPF 123.456.789-09",
            stacktrace: { frames: [{ filename: "app.js", lineno: 1 }] },
          },
        ],
      },
    });

    expect(event.user).toBeUndefined();
    expect(event.request).toBeUndefined();
    expect(event.breadcrumbs).toBeUndefined();
    expect(event.extra).toBeUndefined();
    expect(event.contexts).toBeUndefined();
    expect(event.tags).toEqual({ boundary: "app" });
    expect(event.exception?.values?.[0]?.value).not.toContain("maria@example.com");
    expect(event.exception?.values?.[0]?.value).not.toContain("123.456.789-09");
    expect(event.exception?.values?.[0]?.stacktrace).toBeUndefined();
  });

  it("truncates very long messages", () => {
    expect(sanitizeText("a".repeat(5_000))).toHaveLength(1_000);
  });
});
