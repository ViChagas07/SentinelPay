import { normalizePrivacyEmail } from "@/lib/site/privacy";

export type LegalIdentity = {
  controllerName: string | null;
  controllerTaxId: string | null;
  controllerAddress: string | null;
  contactEmail: string | null;
  dpoName: string | null;
  dpoEmail: string | null;
};

export type LegalIdentityEnv = Record<string, string | undefined>;

function normalizeText(value: string | undefined, maxLength: number): string | null {
  const candidate = value?.trim().replace(/\s+/g, " ");

  if (!candidate) {
    return null;
  }

  return candidate.slice(0, maxLength);
}

export function resolveLegalIdentity(env: LegalIdentityEnv = process.env): LegalIdentity {
  const contactEmail =
    normalizePrivacyEmail(env.NEXT_PUBLIC_LEGAL_CONTACT_EMAIL) ??
    normalizePrivacyEmail(env.NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL);

  return {
    controllerName: normalizeText(env.NEXT_PUBLIC_LEGAL_CONTROLLER_NAME, 200),
    controllerTaxId: normalizeText(env.NEXT_PUBLIC_LEGAL_CONTROLLER_TAX_ID, 32),
    controllerAddress: normalizeText(env.NEXT_PUBLIC_LEGAL_ADDRESS, 300),
    contactEmail,
    dpoName: normalizeText(env.NEXT_PUBLIC_LEGAL_DPO_NAME, 200),
    dpoEmail: normalizePrivacyEmail(env.NEXT_PUBLIC_LEGAL_DPO_EMAIL),
  };
}

export function hasLegalIdentity(identity: LegalIdentity): boolean {
  return Object.values(identity).some((value) => value !== null);
}
