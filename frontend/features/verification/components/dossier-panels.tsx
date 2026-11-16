"use client";

import { AlertTriangle, Check, Copy, Link2, Plus, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { AnalysisDetail, AnalysisEvidence, AnalysisKind } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";
import { formatDate } from "@/lib/i18n/format";
import { resolveTimeZone } from "@/lib/dashboard/date";
import { getEvidenceFramework, getRuleLabelKey } from "@/lib/verification/evidence";
import { getAnalysisErrorKey, getDegradationFlagKey } from "@/lib/verification/errors";

import { FRAMEWORK_KEYS, KIND_KEYS, SEVERITY_KEYS, STATUS_KEYS } from "../lib/labels";

export type ExtractedField = {
  label: string;
  value: string;
};

export function EvidenceList({
  kind,
  evidence,
}: Readonly<{ kind: AnalysisKind; evidence: readonly AnalysisEvidence[] }>) {
  const { t } = useI18n();

  return (
    <section aria-labelledby="verification-evidence-title" className="min-w-0">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h2
          id="verification-evidence-title"
          className="font-serif text-2xl leading-tight tracking-tight"
        >
          {t("verification.dossier.evidence.title")}
        </h2>
        <span className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
          {t("verification.dossier.evidence.count", { count: evidence.length })}
        </span>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
        {t("verification.dossier.evidence.limitation")}
      </p>
      {evidence.length === 0 ? (
        <p className="mt-4 rounded-[6px] border border-border bg-surface p-4 text-sm text-muted-foreground">
          {t("verification.dossier.evidence.empty")}
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {evidence.map((item, index) => {
            const framework = getEvidenceFramework(kind, item.message_key);
            const ruleKey = getRuleLabelKey(item.message_key);
            const ruleLabel = ruleKey ? t(ruleKey) : t("verification.dossier.evidence.untitled");

            return (
              <li
                key={`${item.rule_id}-${item.message_key}-${index}`}
                className="rounded-[6px] border border-border bg-card p-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{t(SEVERITY_KEYS[item.severity])}</Badge>
                  <Badge variant="outline">{t(FRAMEWORK_KEYS[framework])}</Badge>
                  <span className="font-mono text-[0.6rem] uppercase tracking-[0.14em] text-muted-foreground">
                    {t("verification.dossier.evidence.weight", { weight: item.weight })}
                  </span>
                </div>
                <p className="mt-3 font-mono text-[0.6rem] uppercase tracking-[0.14em] text-muted-foreground">
                  {t("verification.dossier.evidence.ruleEvaluated")}
                </p>
                <h3 className="mt-1 text-base font-medium leading-snug">{ruleLabel}</h3>
                <p className="mt-1 break-all font-mono text-[0.65rem] text-muted-foreground">
                  {item.message_key}
                </p>
                {item.rule_id !== item.message_key ? (
                  <p className="mt-1 break-all font-mono text-[0.65rem] text-muted-foreground">
                    {item.rule_id}
                  </p>
                ) : null}
                <p className="mt-2 break-all font-mono text-[0.65rem] leading-relaxed text-muted-foreground">
                  {t("verification.dossier.evidence.source")}: {item.source}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export function ExtractedFieldsTable({ fields }: Readonly<{ fields: readonly ExtractedField[] }>) {
  const { t } = useI18n();
  const [copied, setCopied] = useState<string | null>(null);

  async function copyValue(value: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(value);
      toast.success(t("verification.dossier.fields.copied"));
      window.setTimeout(() => setCopied(null), 2000);
    } catch {
      toast.error(t("verification.dossier.fields.copyError"));
    }
  }

  return (
    <section aria-labelledby="verification-fields-title" className="min-w-0">
      <h2
        id="verification-fields-title"
        className="font-serif text-2xl leading-tight tracking-tight"
      >
        {t("verification.dossier.fields.title")}
      </h2>
      {fields.length === 0 ? (
        <div className="mt-4 rounded-[6px] border border-border bg-surface p-4">
          <p className="text-sm font-medium">{t("verification.dossier.fields.emptyTitle")}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {t("verification.dossier.fields.emptyDescription")}
          </p>
        </div>
      ) : (
        <div className="mt-4 overflow-hidden rounded-[6px] border border-border">
          <table
            className="w-full table-fixed text-sm"
            aria-label={t("verification.dossier.fields.title")}
          >
            <thead className="bg-surface-elevated">
              <tr>
                <th
                  scope="col"
                  className="px-3 py-2 text-left font-mono text-[0.65rem] uppercase tracking-[0.14em] text-muted-foreground"
                >
                  {t("verification.dossier.fields.field")}
                </th>
                <th
                  scope="col"
                  className="px-3 py-2 text-left font-mono text-[0.65rem] uppercase tracking-[0.14em] text-muted-foreground"
                >
                  {t("verification.dossier.fields.value")}
                </th>
                <th scope="col" className="w-12 px-3 py-2">
                  <span className="sr-only">{t("verification.dossier.fields.copy")}</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {fields.map((field) => (
                <tr key={`${field.label}-${field.value}`}>
                  <th
                    scope="row"
                    className="break-words px-3 py-2 text-left font-medium text-muted-foreground"
                  >
                    {field.label}
                  </th>
                  <td className="break-all px-3 py-2 font-mono text-xs tabular-nums">
                    {field.value}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`${t("verification.dossier.fields.copy")}: ${field.label}`}
                      onClick={() => void copyValue(field.value)}
                    >
                      {copied === field.value ? (
                        <Check aria-hidden="true" />
                      ) : (
                        <Copy aria-hidden="true" />
                      )}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function DegradationNotice({ flags }: Readonly<{ flags: readonly string[] }>) {
  const { t } = useI18n();

  if (flags.length === 0) {
    return null;
  }

  return (
    <div role="status" className="rounded-[6px] border border-border bg-surface p-4">
      <p className="flex items-center gap-2 text-sm font-medium">
        <AlertTriangle className="size-4" aria-hidden="true" />
        {t("verification.job.degraded.title")}
      </p>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
        {t("verification.job.degraded.body")}
      </p>
      <ul className="mt-2 space-y-1">
        {flags.map((flag) => (
          <li key={flag} className="text-xs leading-relaxed text-muted-foreground">
            {t(getDegradationFlagKey(flag), { flag })}
          </li>
        ))}
      </ul>
    </div>
  );
}

function MetaRow({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2 border-b border-border py-2 last:border-b-0">
      <dt className="font-mono text-[0.65rem] uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </dt>
      <dd className="min-w-0 break-words text-right text-sm">{value}</dd>
    </div>
  );
}

export function DossierMetadata({
  analysis,
  timeZone,
}: Readonly<{ analysis: AnalysisDetail; timeZone: string }>) {
  const { t, locale } = useI18n();
  const resolvedZone = resolveTimeZone(timeZone);
  const format = (value: string) =>
    formatDate(value, locale, {
      dateStyle: "long",
      timeStyle: "short",
      timeZone: resolvedZone,
    });

  return (
    <section aria-labelledby="verification-metadata-title" className="min-w-0">
      <h2
        id="verification-metadata-title"
        className="font-serif text-2xl leading-tight tracking-tight"
      >
        {t("verification.dossier.metadata.title")}
      </h2>
      <dl className="mt-3 rounded-[6px] border border-border bg-surface px-4">
        <MetaRow
          label={t("verification.dossier.metadata.kind")}
          value={t(KIND_KEYS[analysis.kind])}
        />
        <MetaRow
          label={t("verification.dossier.metadata.status")}
          value={t(STATUS_KEYS[analysis.status])}
        />
        <MetaRow
          label={t("verification.dossier.metadata.created")}
          value={format(analysis.created_at)}
        />
        <MetaRow
          label={t("verification.dossier.metadata.updated")}
          value={format(analysis.updated_at)}
        />
        <MetaRow
          label={t("verification.dossier.metadata.language")}
          value={t("verification.dossier.metadata.unavailable")}
        />
        <MetaRow
          label={t("verification.dossier.metadata.pipeline")}
          value={t("verification.dossier.metadata.unavailable")}
        />
      </dl>
      <div className="mt-3 rounded-[6px] border border-border bg-surface p-4">
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.14em] text-muted-foreground">
          {t("verification.dossier.metadata.flags")}
        </p>
        {!analysis.result ? (
          <p className="mt-2 text-xs text-muted-foreground">
            {t("verification.dossier.metadata.unavailable")}
          </p>
        ) : analysis.result.degradation_flags.length > 0 ? (
          <ul className="mt-2 space-y-1">
            {analysis.result.degradation_flags.map((flag) => (
              <li key={flag} className="text-xs leading-relaxed text-muted-foreground">
                {t(getDegradationFlagKey(flag), { flag })}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xs text-muted-foreground">
            {t("verification.dossier.metadata.noFlags")}
          </p>
        )}
      </div>
    </section>
  );
}

export function DossierActions({
  analysisId,
  onRefresh,
}: Readonly<{
  analysisId: string;
  onRefresh: () => void;
}>) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const href = useMemo(() => `/verificacao/${analysisId}`, [analysisId]);

  async function copyLink(): Promise<void> {
    const url = new URL(href, window.location.origin).toString();

    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.success(t("verification.dossier.actions.copied"));
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error(t("verification.dossier.actions.copyError"));
    }
  }

  return (
    <section aria-labelledby="verification-actions-title" className="min-w-0">
      <h2
        id="verification-actions-title"
        className="font-serif text-2xl leading-tight tracking-tight"
      >
        {t("verification.dossier.actions.title")}
      </h2>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button asChild>
          <Link href="/verificacao">
            <Plus aria-hidden="true" />
            {t("verification.dossier.actions.newVerification")}
          </Link>
        </Button>
        <Button type="button" variant="outline" onClick={() => void copyLink()}>
          {copied ? <Check aria-hidden="true" /> : <Link2 aria-hidden="true" />}
          {t("verification.dossier.actions.copyLink")}
        </Button>
        <Button type="button" variant="ghost" onClick={onRefresh}>
          <RefreshCw aria-hidden="true" />
          {t("verification.job.failed.retryPolling")}
        </Button>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        {t("verification.dossier.actions.downloadUnavailable")}
      </p>
    </section>
  );
}

export function ResultUnavailable({ errorCode }: Readonly<{ errorCode: string | null }>) {
  const { t } = useI18n();

  return (
    <section className="rounded-[6px] border border-border bg-card p-5" role="status">
      <p className="flex items-center gap-2 text-sm font-medium">
        <AlertTriangle className="size-4" aria-hidden="true" />
        {t("verification.dossier.unavailable.title")}
      </p>
      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
        {t("verification.dossier.unavailable.description")}
      </p>
      {errorCode ? (
        <p className="mt-2 font-mono text-[0.65rem] text-muted-foreground">
          {t(getAnalysisErrorKey(errorCode))}
        </p>
      ) : null}
    </section>
  );
}
