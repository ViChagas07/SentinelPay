import type { TranslationKey } from "@/lib/i18n";

const ERROR_KEYS: Record<string, TranslationKey> = {
  analysis_timeout: "verification.error.analysis_timeout",
  analysis_failed: "verification.error.analysis_failed",
  analysis_not_found: "verification.error.analysis_not_found",
  unsupported_document: "verification.error.unsupported_document",
  unsupported_document_type: "verification.error.unsupported_type",
  document_not_found: "verification.error.document_not_found",
  invalid_document: "verification.error.invalid_document",
  empty_document: "verification.error.empty_document",
  llm_unavailable: "verification.error.llm_unavailable",
  rag_unavailable: "verification.error.rag_unavailable",
  storage_unavailable: "verification.error.storage_unavailable",
  storage_not_configured: "verification.error.storage_not_configured",
  ocr_unavailable: "verification.error.ocr_unavailable",
  ocr_timeout: "verification.error.ocr_timeout",
  embedding_unavailable: "verification.error.embedding_unavailable",
  upload_too_large: "verification.error.upload_too_large",
  pdf_page_limit_exceeded: "verification.error.page_limit",
  encrypted_pdf: "verification.error.encrypted_pdf",
  pdf_active_content: "verification.error.active_content",
  request_timeout: "verification.error.request_timeout",
  network_error: "verification.error.network",
  rate_limited: "verification.error.rate_limited",
  too_many_attempts: "verification.error.rate_limited",
  analysis_quota_exceeded: "verification.error.quota",
  idempotency_conflict: "verification.error.idempotency_conflict",
  invalid_idempotency_key: "verification.error.idempotency_key",
  task_dispatch_failed: "verification.error.dispatch",
  validation_error: "verification.error.validation",
  security_service_unavailable: "verification.error.security_unavailable",
  session_expired: "verification.error.session_expired",
  response_schema_invalid: "verification.error.invalid_response",
  invalid_response: "verification.error.invalid_response",
  http_error: "verification.error.http",
};

const FLAG_KEYS: Record<string, TranslationKey> = {
  llm_unavailable: "verification.flag.llm_unavailable",
  rag_unavailable: "verification.flag.rag_unavailable",
  ml_unavailable: "verification.flag.ml_unavailable",
  prompt_injection_detected: "verification.flag.prompt_injection_detected",
  guardrail_classifier_unavailable: "verification.flag.guardrail_classifier_unavailable",
  llm_output_rejected: "verification.flag.llm_output_rejected",
  llm_judge_unavailable: "verification.flag.llm_judge_unavailable",
  llm_judge_rejected: "verification.flag.llm_judge_rejected",
};

export function getAnalysisErrorKey(code: string | null | undefined): TranslationKey {
  if (code) {
    const key = ERROR_KEYS[code];

    if (key) {
      return key;
    }
  }

  return "verification.error.generic";
}

export function getDegradationFlagKey(flag: string): TranslationKey {
  return FLAG_KEYS[flag] ?? "verification.flag.unknown";
}
