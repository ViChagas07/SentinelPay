import type { AnalysisKind } from "@/lib/api/schemas";
import type { TranslationKey } from "@/lib/i18n";

export type EvidenceFramework =
  "febraban" | "inss" | "irrf" | "clt" | "folha" | "guardrail" | "arrecadacao" | "interna";

const RULE_LABELS: Record<string, TranslationKey> = {
  "boleto.line_invalid": "verification.rule.boleto.line_invalid",
  "boleto.dv_invalid": "verification.rule.boleto.dv_invalid",
  "boleto.line_barcode_mismatch": "verification.rule.boleto.line_barcode_mismatch",
  "boleto.amount_mismatch": "verification.rule.boleto.amount_mismatch",
  "boleto.due_date_mismatch": "verification.rule.boleto.due_date_mismatch",
  "boleto.bank_header_mismatch": "verification.rule.boleto.bank_header_mismatch",
  "boleto.bank_code_unknown": "verification.rule.boleto.bank_code_unknown",
  "boleto.currency_unsupported": "verification.rule.boleto.currency_unsupported",
  "boleto.tax_id_invalid": "verification.rule.boleto.tax_id_invalid",
  "boleto.field_illegible": "verification.rule.boleto.field_illegible",
  "boleto.barcode_unreadable": "verification.rule.boleto.barcode_unreadable",
  "boleto.utility_line_not_verifiable": "verification.rule.boleto.utility_line_not_verifiable",
  "payslip.earnings_total_mismatch": "verification.rule.payslip.earnings_total_mismatch",
  "payslip.deductions_total_mismatch": "verification.rule.payslip.deductions_total_mismatch",
  "payslip.net_mismatch": "verification.rule.payslip.net_mismatch",
  "payslip.net_exceeds_earnings": "verification.rule.payslip.net_exceeds_earnings",
  "payslip.inss_mismatch": "verification.rule.payslip.inss_mismatch",
  "payslip.irrf_mismatch": "verification.rule.payslip.irrf_mismatch",
  "payslip.base_below_minimum": "verification.rule.payslip.base_below_minimum",
  "payslip.overtime_below_minimum": "verification.rule.payslip.overtime_below_minimum",
  "payslip.competency_implausible": "verification.rule.payslip.competency_implausible",
  "payslip.employer_cnpj_invalid": "verification.rule.payslip.employer_cnpj_invalid",
  "payslip.employee_cpf_invalid": "verification.rule.payslip.employee_cpf_invalid",
  "payslip.duplicate_item": "verification.rule.payslip.duplicate_item",
  "payslip.rounding_incoherent": "verification.rule.payslip.rounding_incoherent",
  "payslip.field_illegible": "verification.rule.payslip.field_illegible",
  "guardrail.prompt_injection": "verification.rule.guardrail.prompt_injection",
  "guardrail.policy_override": "verification.rule.guardrail.policy_override",
  "guardrail.prompt_disclosure": "verification.rule.guardrail.prompt_disclosure",
  "guardrail.role_change": "verification.rule.guardrail.role_change",
  "guardrail.exfiltration": "verification.rule.guardrail.exfiltration",
  "guardrail.fake_system": "verification.rule.guardrail.fake_system",
  "guardrail.delimiter_escape": "verification.rule.guardrail.delimiter_escape",
  "guardrail.invisible_unicode": "verification.rule.guardrail.invisible_unicode",
  "guardrail.homoglyph": "verification.rule.guardrail.homoglyph",
  "guardrail.too_long": "verification.rule.guardrail.too_long",
  "guardrail.report_rejected": "verification.rule.guardrail.report_rejected",
};

export function getEvidenceFramework(kind: AnalysisKind, messageKey: string): EvidenceFramework {
  if (messageKey.startsWith("guardrail.")) {
    return "guardrail";
  }

  if (kind === "boleto") {
    return "febraban";
  }

  if (kind === "receipt") {
    return "arrecadacao";
  }

  if (messageKey.includes("inss")) {
    return "inss";
  }

  if (messageKey.includes("irrf")) {
    return "irrf";
  }

  if (messageKey.includes("overtime")) {
    return "clt";
  }

  return "folha";
}

export function getRuleLabelKey(messageKey: string): TranslationKey | null {
  return RULE_LABELS[messageKey] ?? null;
}
