"use client";

import { AlertCircle, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import { queryKeys } from "@/lib/query/keys";
import { useI18n } from "@/lib/i18n/provider";
import { INTL_LOCALE } from "@/lib/i18n/format";
import { getAnalysisErrorKey } from "@/lib/verification/errors";
import { isActiveStatus } from "@/lib/verification/polling";
import { createIdempotencyKey, formatFileSize } from "@/lib/verification/upload";
import { uploadAnalysis, type UploadProgress } from "@/lib/verification/upload-analysis";

import { useAnalysisJob } from "../hooks/use-verification";
import { forgetDocument, rememberDocument } from "../lib/document-handoff";
import { LazyDocumentViewer } from "./lazy-document-viewer";
import { JobProgressPanel } from "./job-progress-panel";
import { RecentVerifications } from "./recent-verifications";
import { UploadForm } from "./upload-form";
import { VerificationSteps } from "./verification-steps";

type ActiveAnalysis = {
  id: string;
  file: File;
};

function ActiveVerification({
  analysis,
  onReset,
  onReplaced,
}: Readonly<{
  analysis: ActiveAnalysis;
  onReset: () => void;
  onReplaced: (analysisId: string) => void;
}>) {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const query = useAnalysisJob(analysis.id);
  const [resending, setResending] = useState(false);
  const [resendProgress, setResendProgress] = useState<UploadProgress | null>(null);
  const [resendError, setResendError] = useState<ApiError | null>(null);

  async function resend(kind: "boleto" | "payslip" | "receipt"): Promise<void> {
    setResending(true);
    setResendProgress(null);
    setResendError(null);

    try {
      const created = await uploadAnalysis(
        {
          file: analysis.file,
          kind,
          idempotencyKey: createIdempotencyKey(),
        },
        { onProgress: setResendProgress, locale: INTL_LOCALE[locale] },
      );

      rememberDocument(created.analysis_id, analysis.file);
      forgetDocument(analysis.id);
      await queryClient.invalidateQueries({ queryKey: queryKeys.analyses.all });
      onReplaced(created.analysis_id);
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

  const status = query.data?.status;
  const scanning = status !== undefined && isActiveStatus(status);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground">
          {t("verification.eyebrow")}
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            forgetDocument(analysis.id);
            onReset();
          }}
        >
          {t("verification.dossier.actions.newVerification")}
        </Button>
      </div>

      {resendError ? (
        <div role="alert" className="rounded-[6px] border border-risk-high/50 bg-risk-high/5 p-4">
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
        <div role="status" className="rounded-[6px] border border-border bg-surface p-4">
          <p className="text-sm font-medium">{t("verification.upload.submitting")}</p>
          <p className="mt-1 font-mono text-[0.65rem] tabular-nums text-muted-foreground">
            {t("verification.upload.progress.bytes", {
              loaded: formatFileSize(resendProgress?.loaded ?? 0, INTL_LOCALE[locale]),
              total: formatFileSize(
                resendProgress?.total ?? analysis.file.size,
                INTL_LOCALE[locale],
              ),
            })}
          </p>
        </div>
      ) : null}

      {query.isPending ? (
        <div
          aria-busy="true"
          aria-label={t("verification.job.title")}
          className="grid gap-6 xl:grid-cols-2"
        >
          <Skeleton className="h-[28rem] w-full" />
          <Skeleton className="h-[28rem] w-full" />
        </div>
      ) : query.isError ? (
        <div className="rounded-[6px] border border-border bg-card p-5" role="alert">
          <p className="flex items-center gap-2 text-sm font-medium">
            <AlertCircle className="size-4" aria-hidden="true" />
            {t("verification.dossier.error.title")}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {query.error instanceof ApiError
              ? t(getAnalysisErrorKey(query.error.code))
              : t("verification.dossier.error.description")}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => void query.refetch()}
          >
            <RefreshCw aria-hidden="true" />
            {t("verification.job.failed.retryPolling")}
          </Button>
        </div>
      ) : query.data ? (
        <div className="grid gap-6 xl:grid-cols-2">
          <LazyDocumentViewer file={analysis.file} scanning={scanning} />
          <JobProgressPanel
            analysis={query.data}
            showDossierLink
            streamState={query.streamState}
            onRetryPolling={() => void query.refetch()}
            onCancelled={() => {
              forgetDocument(analysis.id);
              onReset();
            }}
            onResend={
              query.data.status === "failed"
                ? () => {
                    void resend(query.data.kind);
                  }
                : undefined
            }
            resending={resending}
          />
        </div>
      ) : null}
    </div>
  );
}

export function VerificationPage({
  initialKind,
}: Readonly<{ initialKind?: "boleto" | "payslip" }>) {
  const { t } = useI18n();
  const [active, setActive] = useState<ActiveAnalysis | null>(null);

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <header className="border-b border-border pb-6">
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
          {t("verification.eyebrow")}
        </p>
        <h1 className="mt-2 max-w-3xl font-serif text-4xl leading-tight tracking-tight sm:text-5xl">
          {t("verification.title")}
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          {t("verification.description")}
        </p>
      </header>

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          {active ? (
            <ActiveVerification
              analysis={active}
              onReset={() => setActive(null)}
              onReplaced={(analysisId) => setActive({ id: analysisId, file: active.file })}
            />
          ) : (
            <UploadForm
              initialKind={initialKind}
              onCreated={(analysisId, file) => setActive({ id: analysisId, file })}
            />
          )}
        </div>
        <aside aria-label={t("verification.sidebar.label")} className="min-w-0 space-y-8">
          <VerificationSteps />
          <RecentVerifications />
        </aside>
      </div>
    </div>
  );
}
