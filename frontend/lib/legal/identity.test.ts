import { describe, expect, it } from "vitest";

import { hasLegalIdentity, resolveLegalIdentity } from "@/lib/legal/identity";

describe("resolveLegalIdentity", () => {
  it("returns empty fields when nothing is configured", () => {
    const identity = resolveLegalIdentity({});

    expect(identity).toEqual({
      controllerName: null,
      controllerTaxId: null,
      controllerAddress: null,
      contactEmail: null,
      dpoName: null,
      dpoEmail: null,
    });
    expect(hasLegalIdentity(identity)).toBe(false);
  });

  it("normalizes text and caps its length", () => {
    const identity = resolveLegalIdentity({
      NEXT_PUBLIC_LEGAL_CONTROLLER_NAME: `  Sentinel   Pagamentos  ${"x".repeat(300)}  `,
      NEXT_PUBLIC_LEGAL_CONTROLLER_TAX_ID: "  12.345.678/0001-90 ",
      NEXT_PUBLIC_LEGAL_ADDRESS: " Rua Um, 10, São Paulo ",
    });

    expect(identity.controllerName?.startsWith("Sentinel Pagamentos")).toBe(true);
    expect(identity.controllerName?.length).toBe(200);
    expect(identity.controllerTaxId).toBe("12.345.678/0001-90");
    expect(identity.controllerAddress).toBe("Rua Um, 10, São Paulo");
  });

  it("uses the legal contact email and falls back to the privacy email", () => {
    expect(
      resolveLegalIdentity({ NEXT_PUBLIC_LEGAL_CONTACT_EMAIL: " dpo@example.com " }).contactEmail,
    ).toBe("dpo@example.com");

    expect(
      resolveLegalIdentity({
        NEXT_PUBLIC_LEGAL_CONTACT_EMAIL: "not-an-email",
        NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL: "privacidade@example.com",
      }).contactEmail,
    ).toBe("privacidade@example.com");

    expect(resolveLegalIdentity({ NEXT_PUBLIC_LEGAL_CONTACT_EMAIL: "no" }).contactEmail).toBeNull();
  });

  it("validates the DPO email independently", () => {
    expect(
      resolveLegalIdentity({
        NEXT_PUBLIC_LEGAL_DPO_NAME: "  Maria  Silva ",
        NEXT_PUBLIC_LEGAL_DPO_EMAIL: "maria@example.com",
      }),
    ).toMatchObject({ dpoName: "Maria Silva", dpoEmail: "maria@example.com" });

    expect(resolveLegalIdentity({ NEXT_PUBLIC_LEGAL_DPO_EMAIL: "sem-arroba" }).dpoEmail).toBeNull();
  });

  it("reports when at least one field is available", () => {
    expect(hasLegalIdentity(resolveLegalIdentity({ NEXT_PUBLIC_LEGAL_DPO_NAME: "DPO" }))).toBe(
      true,
    );
  });
});
