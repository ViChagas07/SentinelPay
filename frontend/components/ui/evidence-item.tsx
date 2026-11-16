"use client";

import { ScanSearch } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { EvidenceSeverity } from "@/lib/api/schemas";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

export type EvidenceFramework = "FEBRABAN" | "INSS" | "CLT";

export type EvidenceItemProps = {
  severity: EvidenceSeverity;
  framework: EvidenceFramework;
  rule: string;
  excerpt: string;
  source?: string;
  highlighted?: boolean;
  onToggleHighlight?: () => void;
  className?: string;
};

const SEVERITY_LABEL_KEYS: Record<EvidenceSeverity, TranslationKey> = {
  critical: "design.evidence.severity.critical",
  high: "design.evidence.severity.high",
  medium: "design.evidence.severity.medium",
  low: "design.evidence.severity.low",
  info: "design.evidence.severity.info",
};

export function EvidenceItem({
  severity,
  framework,
  rule,
  excerpt,
  source,
  highlighted = false,
  onToggleHighlight,
  className,
}: EvidenceItemProps) {
  const { t } = useI18n();

  return (
    <article
      data-highlighted={highlighted || undefined}
      className={cn(
        "rounded-[6px] border bg-card p-4",
        highlighted ? "border-petrol-600 bg-petrol-600/10" : "border-border",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "inline-flex items-center rounded-[6px] border border-border px-2 py-0.5 font-mono text-[0.65rem] uppercase tracking-[0.16em]",
            severity === "critical" && "font-semibold",
          )}
        >
          {t(SEVERITY_LABEL_KEYS[severity])}
        </span>
        <span className="inline-flex items-center rounded-[6px] border border-border px-2 py-0.5 font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
          {framework}
        </span>
        {highlighted ? (
          <span className="font-mono text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-foreground">
            {t("design.evidence.highlighted")}
          </span>
        ) : null}
      </div>
      <h3 className="mt-3 text-base font-medium leading-snug">{rule}</h3>
      <blockquote className="mt-2 border-l border-border pl-3 text-sm leading-relaxed text-muted-foreground">
        {excerpt}
      </blockquote>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        {source ? (
          <p className="font-mono text-[0.65rem] text-muted-foreground">{source}</p>
        ) : (
          <span />
        )}
        {onToggleHighlight ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-pressed={highlighted}
            onClick={onToggleHighlight}
          >
            <ScanSearch aria-hidden="true" />
            {highlighted ? t("design.evidence.clearHighlight") : t("design.evidence.highlight")}
          </Button>
        ) : null}
      </div>
    </article>
  );
}
