"use client";

import { Ban, CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { BrandLoader } from "@/components/brand/brand-loader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RiskRuler } from "@/components/ui/risk-ruler";
import { RiskStamp } from "@/components/ui/risk-stamp";
import type { AnalysisDetail, AnalysisStatus } from "@/lib/api/schemas";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import { getAnalysisErrorKey } from "@/lib/verification/errors";
import {
  elapsedBetween,
  formatElapsed,
  isActiveStatus,
  isLongRunning,
} from "@/lib/verification/polling";
import {
  ANALYSIS_STAGES,
  STAGE_LABEL_KEYS,
  displayPercent,
  isLongStage,
  progressOf,
  stageStateLabelKey,
  stageStates,
  type AnalysisStreamState,
  type StageState,
} from "@/lib/verification/progress";
import { cn } from "@/lib/utils";

import { CancelAnalysisButton } from "./cancel-analysis-button";

const STATUS_KEYS: Record<AnalysisStatus, TranslationKey> = {
  queued: "dashboard.status.queued",
  running: "dashboard.status.running",
  processing: "dashboard.status.processing",
  cancelling: "dashboard.status.cancelling",
  cancelled: "dashboard.status.cancelled",
  completed: "dashboard.status.completed",
  degraded: "dashboard.status.degraded",
  failed: "dashboard.status.failed",
};

function StageIcon({ state }: Readonly<{ state: StageState }>) {
  if (state === "done") {
    return <CheckCircle2 className="size-4 text-petrol-600" aria-hidden="true" />;
  }

  if (state === "failed") {
    return <XCircle className="size-4 text-risk-high" aria-hidden="true" />;
  }

  if (state === "cancelled") {
    return <Ban className="size-4 text-risk-high" aria-hidden="true" />;
  }

  if (state === "active" || state === "cancelling") {
    return <Loader2 className="size-4 animate-spin text-petrol-600" aria-hidden="true" />;
  }

  return <Circle className="size-4 text-muted-foreground" aria-hidden="true" />;
}

function StageIndeterminateBar() {
  const { t } = useI18n();
  const reduceMotion = useReducedMotion() ?? false;

  return (
    <div
      className="mt-1.5 h-1 w-full max-w-40 overflow-hidden rounded-full bg-surface-elevated"
      aria-hidden="true"
      title={t("verification.job.progress.indeterminate")}
    >
      <motion.div
        className="h-full w-1/3 rounded-full bg-petrol-500"
        initial={{ x: "-120%" }}
        animate={reduceMotion ? { x: "0%" } : { x: ["-120%", "320%"] }}
        transition={
          reduceMotion
            ? { duration: 0 }
            : { duration: 1.6, ease: "easeInOut", repeat: Number.POSITIVE_INFINITY }
        }
      />
    </div>
  );
}

export type AnalysisPipelineProps = {
  analysis: AnalysisDetail;
};

export function AnalysisPipeline({ analysis }: AnalysisPipelineProps) {
  const { t } = useI18n();
  const progress = progressOf(analysis.progress, analysis.status);
  const stages = stageStates(progress, analysis.status);

  return (
    <div className="min-w-0">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium">{t("verification.job.stagesTitle")}</h3>
        <Badge variant="outline">{t(STATUS_KEYS[analysis.status])}</Badge>
      </div>
      <ol className="mt-4 space-y-1.5" aria-label={t("verification.job.stagesTitle")}>
        {ANALYSIS_STAGES.map((stage, index) => {
          const state = stages[index] ?? "pending";
          const active = state === "active" || state === "cancelling";

          return (
            <li
              key={stage}
              aria-current={active ? "step" : undefined}
              className={cn(
                "flex items-start gap-3 rounded-[6px] px-3 py-2",
                active && "border border-petrol-500/30 bg-petrol-500/5",
              )}
            >
              <StageIcon state={state} />
              <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-2">
                <div className="min-w-0">
                  <span
                    className={cn(
                      "text-sm",
                      state === "pending" ? "text-muted-foreground" : "text-foreground",
                      active && "font-medium",
                    )}
                  >
                    {t(STAGE_LABEL_KEYS[stage])}
                  </span>
                  {active && progress.stage === stage && progress.detail ? (
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      {progress.detail}
                    </span>
                  ) : null}
                  {active && isLongStage(stage) ? <StageIndeterminateBar /> : null}
                </div>
                <span className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">
                  {t(stageStateLabelKey(state))}
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function ConnectionNotice({ state }: Readonly<{ state: AnalysisStreamState }>) {
  const { t } = useI18n();

  if (state === "reconnecting") {
    return (
      <p
        role="status"
        aria-live="polite"
        className="mt-3 flex items-center gap-2 rounded-[6px] border border-border bg-surface-elevated px-3 py-2 text-xs text-muted-foreground"
      >
        <Loader2 className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
        {t("verification.job.connection.reconnecting")}
      </p>
    );
  }

  if (state === "polling") {
    return (
      <p
        role="status"
        aria-live="polite"
        className="mt-3 rounded-[6px] border border-border bg-surface-elevated px-3 py-2 text-xs text-muted-foreground"
      >
        {t("verification.job.connection.polling")}
      </p>
    );
  }

  return null;
}

export type JobProgressPanelProps = {
  analysis: AnalysisDetail;
  showDossierLink?: boolean;
  streamState?: AnalysisStreamState;
  onRetryPolling?: () => void;
  onResend?: () => void;
  onCancelled?: () => void;
  resending?: boolean;
};

export function JobProgressPanel({
  analysis,
  showDossierLink = true,
  streamState = "closed",
  onRetryPolling,
  onResend,
  onCancelled,
  resending = false,
}: JobProgressPanelProps) {
  const { t } = useI18n();
  const reduceMotion = useReducedMotion() ?? false;
  const active = isActiveStatus(analysis.status);
  const progress = progressOf(analysis.progress, analysis.status);
  const percent = displayPercent(progress, analysis.status);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    if (!active) {
      return;
    }

    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);

  const elapsed = elapsedBetween(analysis.created_at, now);
  const longRunning = isLongRunning(analysis.status, elapsed);
  const result = analysis.result_available ? analysis.result : null;
  const errorKey = getAnalysisErrorKey(analysis.error_code);
  const stageLabel =
    progress.stage !== null
      ? t(STAGE_LABEL_KEYS[progress.stage])
      : analysis.status === "cancelling"
        ? t("verification.job.stage.cancelling")
        : analysis.status === "running" || analysis.status === "processing"
          ? t("verification.job.stage.validation")
          : t("verification.job.queued");
  const detail = progress.detail ?? stageLabel;
  const percentText = t("verification.job.progress.percent", { percent });

  return (
    <section
      aria-labelledby="verification-job-title"
      className="min-w-0 rounded-[6px] border border-border bg-card p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
            {t("verification.eyebrow")}
          </p>
          <h2
            id="verification-job-title"
            className="mt-2 font-serif text-xl leading-tight tracking-tight"
          >
            {t("verification.job.title")}
          </h2>
          <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
            {t("verification.job.id", { id: analysis.id.slice(0, 8) })}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {t("verification.job.elapsed", { time: formatElapsed(elapsed) })}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{t(STATUS_KEYS[analysis.status])}</Badge>
          {result ? <RiskStamp band={result.band} /> : null}
          <CancelAnalysisButton
            analysisId={analysis.id}
            status={analysis.status}
            onCancelled={onCancelled}
            onRefresh={onRetryPolling}
          />
        </div>
      </div>

      <div className="mt-4" aria-live="polite" aria-atomic="false">
        {active ? (
          <>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="flex min-w-0 items-center gap-2">
                <BrandLoader className="size-5 shrink-0" />
                <span className="min-w-0">
                  <span className="font-medium text-foreground">{stageLabel}</span>
                  <span className="block truncate text-xs text-muted-foreground">{detail}</span>
                </span>
              </span>
              <span className="font-mono text-sm tabular-nums text-petrol-700">
                {t("verification.job.progress.percentShort", { percent })}
              </span>
            </div>
            <div
              role="progressbar"
              aria-label={t("verification.job.progress.aria")}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={percent}
              aria-valuetext={`${percentText}. ${detail}`}
              className="relative mt-2 h-2 w-full overflow-hidden rounded-full border border-border bg-surface-elevated"
            >
              <div
                className="h-full rounded-full bg-petrol-500 transition-[width] duration-500 ease-out motion-reduce:transition-none"
                style={{ width: `${percent}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {analysis.status === "queued"
                ? t("verification.job.queued")
                : analysis.status === "cancelling"
                  ? t("verification.job.cancelling")
                  : isLongStage(progress.stage)
                    ? t("verification.job.progress.longStage")
                    : t("verification.job.progress.waiting")}
            </p>
          </>
        ) : analysis.status === "cancelled" ? (
          <div role="status" className="rounded-[6px] border border-border bg-surface p-4">
            <h3 className="text-base font-medium">{t("verification.job.cancelled.title")}</h3>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              {t("verification.job.cancelled.body")}
            </p>
            {onCancelled ? (
              <Button type="button" className="mt-3" size="sm" onClick={onCancelled}>
                {t("verification.cancel.newAnalysis")}
              </Button>
            ) : (
              <Button asChild className="mt-3" size="sm">
                <Link href="/verificacao">{t("verification.cancel.newAnalysis")}</Link>
              </Button>
            )}
          </div>
        ) : analysis.status === "failed" ? (
          <div role="alert" className="rounded-[6px] border border-risk-high/50 bg-risk-high/5 p-4">
            <h3 className="text-base font-medium">{t("verification.job.failed.title")}</h3>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t(errorKey)}</p>
            {analysis.error_code ? (
              <p className="mt-2 font-mono text-[0.65rem] text-muted-foreground">
                {t("verification.job.errorCode", { code: analysis.error_code })}
              </p>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              {onRetryPolling ? (
                <Button type="button" variant="outline" size="sm" onClick={onRetryPolling}>
                  {t("verification.job.failed.retryPolling")}
                </Button>
              ) : null}
              {onResend ? (
                <Button type="button" size="sm" onClick={onResend} disabled={resending}>
                  {resending
                    ? t("verification.upload.submitting")
                    : t("verification.job.failed.resend")}
                </Button>
              ) : null}
            </div>
          </div>
        ) : analysis.result_available && result === null ? (
          <div
            role="status"
            className="flex items-center gap-3 rounded-[6px] border border-border bg-surface p-4"
          >
            <BrandLoader className="size-5 shrink-0" />
            <p className="text-sm text-muted-foreground">{t("verification.job.loadingResult")}</p>
          </div>
        ) : result ? (
          <AnimatePresence initial={false}>
            <motion.div
              key="result"
              initial={reduceMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.35, ease: "easeOut" }}
              className="rounded-[6px] border border-border bg-surface p-4"
            >
              <p className="text-sm font-medium">
                {analysis.status === "degraded"
                  ? t("verification.job.degraded.title")
                  : t("verification.job.completed.title")}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {analysis.status === "degraded"
                  ? t("verification.job.degraded.body")
                  : t("verification.job.completed.body")}
              </p>
              <div className="mt-4">
                <RiskRuler score={result.score} band={result.band} variant="medium" />
              </div>
              {showDossierLink ? (
                <Button asChild className="mt-4" size="sm">
                  <Link href={`/verificacao/${analysis.id}`}>
                    {t("verification.job.openDossier")}
                  </Link>
                </Button>
              ) : null}
            </motion.div>
          </AnimatePresence>
        ) : (
          <div className="rounded-[6px] border border-border bg-surface p-4">
            <p className="text-sm leading-relaxed text-muted-foreground">
              {t("verification.job.resultUnavailable")}
            </p>
            {showDossierLink ? (
              <Button asChild className="mt-3" size="sm" variant="outline">
                <Link href={`/verificacao/${analysis.id}`}>
                  {t("verification.job.openDossier")}
                </Link>
              </Button>
            ) : null}
          </div>
        )}
      </div>

      <ConnectionNotice state={streamState} />

      {longRunning ? (
        <div className="mt-4 rounded-[6px] border border-border bg-surface-elevated p-3">
          <p className="text-sm font-medium">{t("verification.job.long.title")}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {t("verification.job.long.body")}
          </p>
        </div>
      ) : null}

      <div
        className={cn(
          "mt-5 border-t border-border pt-4",
          analysis.status === "failed" || analysis.status === "cancelled" ? "opacity-70" : "",
        )}
      >
        <AnalysisPipeline analysis={analysis} />
      </div>
    </section>
  );
}
