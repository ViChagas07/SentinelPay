import { describe, expect, it } from "vitest";

import { normalizePrivacyEmail, resolvePrivacyContact } from "./privacy";

describe("privacy contact", () => {
  it("accepts a valid http or https url", () => {
    expect(
      resolvePrivacyContact({
        url: "https://privacy.example.test/contato",
        email: "privacidade@example.test",
      }),
    ).toEqual({
      url: "https://privacy.example.test/contato",
      email: "privacidade@example.test",
      href: "https://privacy.example.test/contato",
      isFallback: false,
    });
  });

  it("falls back to a valid email when there is no url", () => {
    expect(
      resolvePrivacyContact({
        url: "javascript:alert(1)",
        email: "privacidade@example.test",
      }),
    ).toEqual({
      url: null,
      email: "privacidade@example.test",
      href: "mailto:privacidade@example.test",
      isFallback: false,
    });
  });

  it("falls back to the support page without a configured channel", () => {
    expect(
      resolvePrivacyContact({
        url: "",
        email: "not-an-email",
      }),
    ).toEqual({
      url: null,
      email: null,
      href: "/suporte",
      isFallback: true,
    });
  });

  it("validates the email shape", () => {
    expect(normalizePrivacyEmail(" privacidade@example.test ")).toBe("privacidade@example.test");
    expect(normalizePrivacyEmail("privacidade")).toBeNull();
  });
});
