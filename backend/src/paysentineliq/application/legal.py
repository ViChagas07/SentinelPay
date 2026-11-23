from paysentineliq.domain.legal_consent import LegalDocument

LEGAL_VERSION = "1.1"
LEGAL_DOCUMENTS: tuple[LegalDocument, ...] = (
    LegalDocument.TERMS,
    LegalDocument.PRIVACY,
)
