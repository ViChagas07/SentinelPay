import type { AnalysisKind, AnalysisStatus, EvidenceSeverity } from "@/lib/api/schemas";
import type { TranslationKey } from "@/lib/i18n";
import type { EvidenceFramework } from "@/lib/verification/evidence";

export const STATUS_KEYS: Record<AnalysisStatus, TranslationKey> = {
  queued: "dashboard.status.queued",
  running: "dashboard.status.running",
  processing: "dashboard.status.processing",
  cancelling: "dashboard.status.cancelling",
  cancelled: "dashboard.status.cancelled",
  completed: "dashboard.status.completed",
  degraded: "dashboard.status.degraded",
  failed: "dashboard.status.failed",
};

export const KIND_KEYS: Record<AnalysisKind, TranslationKey> = {
  boleto: "dashboard.kind.boleto",
  payslip: "dashboard.kind.payslip",
  receipt: "dashboard.kind.receipt",
};

export const SEVERITY_KEYS: Record<EvidenceSeverity, TranslationKey> = {
  critical: "design.evidence.severity.critical",
  high: "design.evidence.severity.high",
  medium: "design.evidence.severity.medium",
  low: "design.evidence.severity.low",
  info: "design.evidence.severity.info",
};

export const FRAMEWORK_KEYS: Record<EvidenceFramework, TranslationKey> = {
  febraban: "verification.dossier.evidence.framework.febraban",
  inss: "verification.dossier.evidence.framework.inss",
  irrf: "verification.dossier.evidence.framework.irrf",
  clt: "verification.dossier.evidence.framework.clt",
  folha: "verification.dossier.evidence.framework.folha",
  guardrail: "verification.dossier.evidence.framework.guardrail",
  arrecadacao: "verification.dossier.evidence.framework.arrecadacao",
  interna: "verification.dossier.evidence.framework.interna",
};
