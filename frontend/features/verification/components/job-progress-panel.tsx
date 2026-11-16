"use client";

import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { useEffect, useState } from "react";

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
import { cn } from "@/lib/utils";

const STATUS_KEYS: Record<AnalysisStatus, TranslationKey> = {
  queued: "dashboard.status.queued",
  processing: "dashboard.status.processing",
  completed: "dashboard.status.completed",
  degraded: "dashboard.status.degraded",
  failed: "dashboard.status.failed",
};

type StageState = "pending" | "active" | "done" | "failed";

const STAGE_LABEL_KEYS: TranslationKey[] = [
  "verification.job.stage.document",
  "verification.job.stage.extraction",
  "verification.job.stage.rules",
  "verification.job.stage.classification",
  "verification.job.stage.justification",
];

const STAGE_STATE_KEYS: Record<StageState, TranslationKey> = {
  pending: "verification.job.stage.pending",
  active: "verification.job.stage.active",
  done: "verification.job.stage.done",
  failed: "verification.job.stage.failed",
};

function StageIcon({ state }: Readonly<{ state: StageState }>) {
  if (state === "done") {
    return <CheckCircle2 className="size-4 text-petrol-600" aria-hidden="true" />;
  }

  if (state === "failed") {
    return <XCircle className="size-4 text-risk-high" aria-hidden="true" />;
  }

  if (state === "active") {
    return <Loader2 className="size-4 animate-spin text-petrol-600" aria-hidden="true" />;
  }

  return <Circle className="size-4 text-muted-foreground" aria-hidden="true" />;
}

function IndeterminateBar() {
  const { t } = useI18n();
  const reduceMotion = useReducedMotion() ?? false;

  return (
    <div
      role="progressbar"
      aria-label={t("verification.job.progress.aria")}
      aria-valuetext={t("verification.job.progress.indeterminate")}
      className="h-1.5 w-full overflow-hidden rounded-full border border-border bg-surface-elevated"
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

function jobState(status: AnalysisStatus): StageState {
  if (status === "queued") {
    return "pending";
  }

  if (status === "processing") {
    return "active";
  }

  if (status === "failed") {
    return "failed";
  }

  return "done";
}

function stageStates(status: AnalysisStatus): StageState[] {
  if (status === "completed" || status === "degraded") {
    return STAGE_LABEL_KEYS.map(() => "done");
  }

  return STAGE_LABEL_KEYS.map(() => "pending");
}

export type AnalysisPipelineProps = {
  status: AnalysisStatus;
};

export function AnalysisPipeline({ status }: AnalysisPipelineProps) {
  const { t } = useI18n();
  const stages = stageStates(status);
  const overall = jobState(status);

  return (
    <div className="min-w-0">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium">{t("verification.job.stagesTitle")}</h3>
        <Badge variant="outline">
          <StageIcon state={overall} />
          {t(STAGE_STATE_KEYS[overall])}
        </Badge>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
        {t("verification.job.stagesNote")}
      </p>
      <ol className="mt-4 space-y-2" aria-label={t("verification.job.stagesTitle")}>
        <li className="flex items-start gap-3 rounded-[6px] border border-border bg-surface-elevated px-3 py-2">
          <StageIcon state={overall} />
          <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
            <span className="text-sm font-medium">{t("verification.job.stage.job")}</span>
            <span className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">
              {t(STAGE_STATE_KEYS[overall])}
            </span>
          </div>
        </li>
        {STAGE_LABEL_KEYS.map((labelKey, index) => {
          const state = stages[index] ?? "pending";

          return (
            <li key={labelKey} className="flex items-start gap-3 px-3 py-1.5">
              <StageIcon state={state} />
              <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
                <span className="text-sm text-muted-foreground">{t(labelKey)}</span>
                <span className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">
                  {t(STAGE_STATE_KEYS[state])}
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export type JobProgressPanelProps = {
  analysis: AnalysisDetail;
  showDossierLink?: boolean;
  onRetryPolling?: () => void;
  onResend?: () => void;
  resending?: boolean;
};

export function JobProgressPanel({
  analysis,
  showDossierLink = true,
  onRetryPolling,
  onResend,
  resending = false,
}: JobProgressPanelProps) {
  const { t } = useI18n();
  const active = isActiveStatus(analysis.status);
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
        </div>
      </div>

      <div className="mt-4" aria-live="polite">
        {active ? (
          <>
            <IndeterminateBar />
            <p className="mt-2 text-sm text-muted-foreground">
              {analysis.status === "queued"
                ? t("verification.job.queued")
                : t("verification.job.processing")}{" "}
              {t("verification.job.progress.indeterminate")}
            </p>
          </>
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
        ) : result ? (
          <div className="rounded-[6px] border border-border bg-surface p-4">
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
          </div>
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
          analysis.status === "failed" ? "opacity-70" : "",
        )}
      >
        <AnalysisPipeline status={analysis.status} />
      </div>
    </section>
  );
}
