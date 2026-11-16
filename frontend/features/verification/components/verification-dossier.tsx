"use client";

import { AlertCircle, ArrowLeft, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { RiskRuler } from "@/components/ui/risk-ruler";
import { RiskStamp } from "@/components/ui/risk-stamp";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import { uuidSchema } from "@/lib/api/schemas";
import type { AnalysisDetail } from "@/lib/api/schemas";
import { useSession } from "@/features/auth/hooks/use-session";
import { resolveTimeZone } from "@/lib/dashboard/date";
import { queryKeys } from "@/lib/query/keys";
import { formatDate, INTL_LOCALE } from "@/lib/i18n/format";
import { useI18n } from "@/lib/i18n/provider";
import { getAnalysisErrorKey } from "@/lib/verification/errors";
import { createIdempotencyKey, formatFileSize } from "@/lib/verification/upload";
import { uploadAnalysis, type UploadProgress } from "@/lib/verification/upload-analysis";

import { useAnalysisJob } from "../hooks/use-verification";
import { forgetDocument, peekDocument, rememberDocument } from "../lib/document-handoff";
import { KIND_KEYS, STATUS_KEYS } from "../lib/labels";
import { LazyDocumentViewer } from "./lazy-document-viewer";
import {
  DegradationNotice,
  DossierActions,
  DossierMetadata,
  EvidenceList,
  ExtractedFieldsTable,
  ResultUnavailable,
} from "./dossier-panels";
import { JobProgressPanel } from "./job-progress-panel";

function DossierHeader({ analysis }: Readonly<{ analysis: AnalysisDetail }>) {
  const { t, locale } = useI18n();
  const { user } = useSession();
  const timeZone = resolveTimeZone(user?.timezone);

  return (
    <header className="border-b border-border pb-5">
      <Link
        href="/verificacao"
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden="true" />
        {t("verification.dossier.back")}
      </Link>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
            {t("verification.dossier.eyebrow")}
          </p>
          <h1 className="mt-2 break-all font-mono text-2xl leading-tight tracking-tight sm:text-3xl">
            {t("verification.dossier.title", { id: analysis.id.slice(0, 8) })}
          </h1>
          <p className="mt-2 break-all font-mono text-[0.65rem] text-muted-foreground">
            {analysis.id}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            {t("verification.dossier.created", {
              date: formatDate(analysis.created_at, locale, {
                dateStyle: "medium",
                timeStyle: "short",
                timeZone,
              }),
            })}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{t(KIND_KEYS[analysis.kind])}</Badge>
          <Badge variant="outline">{t(STATUS_KEYS[analysis.status])}</Badge>
        </div>
      </div>
    </header>
  );
}

function DossierSkeleton() {
  const { t } = useI18n();

  return (
    <div
      aria-busy="true"
      aria-label={t("verification.dossier.loading")}
      className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]"
    >
      <Skeleton className="h-[34rem] w-full" />
      <div className="space-y-4">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    </div>
  );
}

function ResultView({
  analysis,
  file,
  onRefresh,
}: Readonly<{
  analysis: AnalysisDetail;
  file: File | null;
  onRefresh: () => void;
}>) {
  const { t } = useI18n();
  const { user } = useSession();
  const result = analysis.result;

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <div className="min-w-0 space-y-4 xl:sticky xl:top-6 xl:self-start">
        <LazyDocumentViewer file={file} />
      </div>
      <div className="min-w-0 space-y-8">
        {result ? (
          <>
            {analysis.status === "degraded" ? (
              <DegradationNotice flags={result.degradation_flags} />
            ) : null}
            <section aria-labelledby="verification-risk-title" className="min-w-0">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <h2
                  id="verification-risk-title"
                  className="font-serif text-2xl leading-tight tracking-tight"
                >
                  {t("verification.dossier.risk.title")}
                </h2>
                <RiskStamp band={result.band} />
              </div>
              <div className="mt-4">
                <RiskRuler score={result.score} band={result.band} variant="large" />
              </div>
              <div className="mt-3 flex flex-wrap gap-3 font-mono text-[0.65rem] text-muted-foreground">
                <span>
                  {t("verification.dossier.risk.baseScore", { score: result.base_score })}
                </span>
                <span>
                  {t("verification.dossier.risk.llmAdjustment", { value: result.llm_adjustment })}
                </span>
              </div>
            </section>

            <section aria-labelledby="verification-justification-title" className="min-w-0">
              <h2
                id="verification-justification-title"
                className="font-serif text-2xl leading-tight tracking-tight"
              >
                {t("verification.dossier.justification.title")}
              </h2>
              <p className="mt-3 whitespace-pre-line font-serif text-lg leading-relaxed">
                {result.justification.trim().length > 0
                  ? result.justification
                  : t("verification.dossier.justification.empty")}
              </p>
              {result.inconsistencies.length > 0 ? (
                <div className="mt-4">
                  <h3 className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
                    {t("verification.dossier.inconsistencies.title")}
                  </h3>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed">
                    {result.inconsistencies.map((item, index) => (
                      <li key={`${item}-${index}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>

            <EvidenceList kind={analysis.kind} evidence={result.evidence} />
          </>
        ) : (
          <ResultUnavailable errorCode={analysis.error_code} />
        )}

        <ExtractedFieldsTable fields={[]} />
        <DossierMetadata analysis={analysis} timeZone={resolveTimeZone(user?.timezone)} />
        <DossierActions analysisId={analysis.id} onRefresh={onRefresh} />
      </div>
    </div>
  );
}

export function VerificationDossier({ analysisId }: Readonly<{ analysisId: string }>) {
  const { t, locale } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const validId = uuidSchema.safeParse(analysisId).success;
  const query = useAnalysisJob(validId ? analysisId : null);
  const [file] = useState<File | null>(() => (validId ? peekDocument(analysisId) : null));
  const [resending, setResending] = useState(false);
  const [resendProgress, setResendProgress] = useState<UploadProgress | null>(null);
  const [resendError, setResendError] = useState<ApiError | null>(null);

  useEffect(() => {
    return () => {
      if (validId) {
        forgetDocument(analysisId);
      }
    };
  }, [analysisId, validId]);

  if (!validId) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
        <EmptyState
          title={t("verification.dossier.notFound.title")}
          description={t("verification.dossier.notFound.description")}
          action={{
            label: t("verification.dossier.notFound.action"),
            href: "/verificacao",
          }}
        />
      </div>
    );
  }

  const analysis = query.data;

  async function handleResend(): Promise<void> {
    if (!analysis || !file) {
      return;
    }

    setResending(true);
    setResendProgress(null);
    setResendError(null);

    try {
      const created = await uploadAnalysis(
        {
          file,
          kind: analysis.kind,
          idempotencyKey: createIdempotencyKey(),
        },
        { onProgress: setResendProgress, locale: INTL_LOCALE[locale] },
      );

      rememberDocument(created.analysis_id, file);
      forgetDocument(analysis.id);
      await queryClient.invalidateQueries({ queryKey: queryKeys.analyses.all });
      router.push(`/verificacao/${created.analysis_id}`);
    } catch (error) {
      setResendError(
        error instanceof ApiError
          ? error
          : new ApiError({
              status: 0,
              code: "network_error",
              title: "Network error",
              detail: "The upload could not reach the service.",
            }),
      );
    } finally {
      setResending(false);
      setResendProgress(null);
    }
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      {query.isPending ? (
        <>
          <div className="border-b border-border pb-5">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="mt-4 h-8 w-2/3" />
          </div>
          <div className="mt-6">
            <DossierSkeleton />
          </div>
        </>
      ) : query.isError && !analysis ? (
        <div className="rounded-[6px] border border-border bg-card p-6" role="alert">
          <p className="flex items-center gap-2 text-sm font-medium">
            <AlertCircle className="size-4" aria-hidden="true" />
            {query.error instanceof ApiError && query.error.status === 404
              ? t("verification.dossier.notFound.title")
              : t("verification.dossier.error.title")}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            {query.error instanceof ApiError && query.error.status === 404
              ? t("verification.dossier.notFound.description")
              : t("verification.dossier.error.description")}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={() => void query.refetch()}>
              <RefreshCw aria-hidden="true" />
              {t("verification.job.failed.retryPolling")}
            </Button>
            <Button asChild variant="ghost">
              <Link href="/verificacao">{t("verification.dossier.notFound.action")}</Link>
            </Button>
          </div>
        </div>
      ) : analysis ? (
        <>
          <DossierHeader analysis={analysis} />

          {resendError ? (
            <div
              role="alert"
              className="mt-4 rounded-[6px] border border-risk-high/50 bg-risk-high/5 p-4"
            >
              <p className="flex items-center gap-2 text-sm font-medium">
                <AlertCircle className="size-4" aria-hidden="true" />
                {t("verification.upload.error.title")}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {t(getAnalysisErrorKey(resendError.code))}
              </p>
            </div>
          ) : null}

          {resending ? (
            <div role="status" className="mt-4 rounded-[6px] border border-border bg-surface p-4">
              <p className="text-sm font-medium">{t("verification.upload.submitting")}</p>
              <p className="mt-1 font-mono text-[0.65rem] tabular-nums text-muted-foreground">
                {t("verification.upload.progress.bytes", {
                  loaded: formatFileSize(resendProgress?.loaded ?? 0, INTL_LOCALE[locale]),
                  total: formatFileSize(
                    resendProgress?.total ?? file?.size ?? 0,
                    INTL_LOCALE[locale],
                  ),
                })}
              </p>
            </div>
          ) : null}

          <div className="mt-6">
            {analysis.status === "queued" || analysis.status === "processing" ? (
              <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
                <LazyDocumentViewer file={file} scanning />
                <JobProgressPanel
                  analysis={analysis}
                  showDossierLink={false}
                  onRetryPolling={() => void query.refetch()}
                />
              </div>
            ) : analysis.status === "failed" ? (
              <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
                <LazyDocumentViewer file={file} />
                <JobProgressPanel
                  analysis={analysis}
                  showDossierLink={false}
                  onRetryPolling={() => void query.refetch()}
                  onResend={file ? () => void handleResend() : undefined}
                  resending={resending}
                />
              </div>
            ) : (
              <ResultView analysis={analysis} file={file} onRefresh={() => void query.refetch()} />
            )}
          </div>

          <p className="mt-8 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
            {t("verification.disclaimer")}
          </p>
        </>
      ) : null}
    </div>
  );
}
