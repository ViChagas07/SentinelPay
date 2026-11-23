export const LEGAL_VERSION = "1.1";

export const LEGAL_UPDATED_AT = "2026-11-23";

export type LegalDocumentKind = "terms" | "privacy";

export const LEGAL_PATHS: Record<LegalDocumentKind, string> = {
  terms: "/termos",
  privacy: "/privacidade",
};
