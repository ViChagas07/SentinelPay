import { describe, expect, it } from "vitest";

import { getSiteUrl, getSupportExternalUrl, resolveSupportHref } from "./config";

describe("site configuration", () => {
  it("accepts http and https support urls", () => {
    expect(getSupportExternalUrl("https://support.example.com/help")).toBe(
      "https://support.example.com/help",
    );
    expect(getSupportExternalUrl("http://support.example.com")).toBe("http://support.example.com/");
  });

  it("rejects empty, malformed and non-http values", () => {
    expect(getSupportExternalUrl("")).toBeNull();
    expect(getSupportExternalUrl("   ")).toBeNull();
    expect(getSupportExternalUrl("javascript:alert(1)")).toBeNull();
    expect(getSupportExternalUrl("support.example.com")).toBeNull();
  });

  it("falls back to the local support page when no channel exists", () => {
    expect(resolveSupportHref("")).toBe("/suporte");
    expect(resolveSupportHref(undefined)).toBe("/suporte");
    expect(resolveSupportHref("ftp://support.example.com")).toBe("/suporte");
    expect(resolveSupportHref("https://support.example.com")).toBe("https://support.example.com/");
  });

  it("uses the configured site url and keeps the local fallback", () => {
    const original = process.env.NEXT_PUBLIC_SITE_URL;

    process.env.NEXT_PUBLIC_SITE_URL = "https://sentinelpay.example.com/app";
    expect(getSiteUrl()).toBe("https://sentinelpay.example.com");

    process.env.NEXT_PUBLIC_SITE_URL = "not-a-url";
    expect(getSiteUrl()).toBe("http://localhost:3000");

    process.env.NEXT_PUBLIC_SITE_URL = original;
  });
});
