import type { AnalysisProgress, AnalysisStage, AnalysisStatus } from "@/lib/api/schemas";
import type { TranslationKey } from "@/lib/i18n";

export const ANALYSIS_STAGES: readonly AnalysisStage[] = [
  "validation",
  "ocr",
  "extraction",
  "classification",
  "rag",
  "llm",
  "persistence",
];

export const STAGE_LABEL_KEYS: Record<AnalysisStage, TranslationKey> = {
  validation: "verification.job.stage.validation",
  ocr: "verification.job.stage.ocr",
  extraction: "verification.job.stage.extraction",
  classification: "verification.job.stage.classification",
  rag: "verification.job.stage.rag",
  llm: "verification.job.stage.llm",
  persistence: "verification.job.stage.persistence",
};

export type StageState = "done" | "active" | "cancelling" | "pending" | "failed" | "cancelled";

export type AnalysisStreamState =
  "connecting" | "connected" | "reconnecting" | "polling" | "closed";

export const EMPTY_PROGRESS: AnalysisProgress = {
  percent: 0,
  stage: null,
  detail: null,
  started_at: null,
  indeterminate: false,
};

export function progressOf(
  progress: AnalysisProgress | null | undefined,
  status: AnalysisStatus,
): AnalysisProgress {
  if (progress) {
    return progress;
  }

  return {
    ...EMPTY_PROGRESS,
    percent: status === "completed" || status === "degraded" ? 100 : 0,
    indeterminate: status === "running" || status === "cancelling",
  };
}

export function stageStates(progress: AnalysisProgress, status: AnalysisStatus): StageState[] {
  if (status === "completed" || status === "degraded") {
    return ANALYSIS_STAGES.map(() => "done");
  }

  if (status === "queued") {
    return ANALYSIS_STAGES.map(() => "pending");
  }

  const currentIndex = progress.stage === null ? -1 : ANALYSIS_STAGES.indexOf(progress.stage);

  return ANALYSIS_STAGES.map((_stage, index) => {
    if (status === "cancelled") {
      if (currentIndex < 0) {
        return "pending";
      }
      if (index < currentIndex) {
        return "done";
      }
      return index === currentIndex ? "cancelled" : "pending";
    }

    if (status === "failed") {
      if (currentIndex < 0) {
        return index === 0 ? "failed" : "pending";
      }
      if (index < currentIndex) {
        return "done";
      }
      return index === currentIndex ? "failed" : "pending";
    }

    if (currentIndex < 0) {
      if (index !== 0) {
        return "pending";
      }
      return status === "cancelling" ? "cancelling" : "active";
    }

    if (index < currentIndex) {
      return "done";
    }

    if (index === currentIndex) {
      return status === "cancelling" ? "cancelling" : "active";
    }

    return "pending";
  });
}

export function stageStateLabelKey(state: StageState): TranslationKey {
  switch (state) {
    case "done":
      return "verification.job.stage.done";
    case "active":
      return "verification.job.stage.active";
    case "cancelling":
      return "verification.job.stage.cancelling";
    case "failed":
      return "verification.job.stage.failed";
    case "cancelled":
      return "verification.job.stage.cancelled";
    default:
      return "verification.job.stage.pending";
  }
}

export function displayPercent(progress: AnalysisProgress, status: AnalysisStatus): number {
  const value = status === "completed" || status === "degraded" ? 100 : progress.percent;
  return Math.min(100, Math.max(0, Math.round(value)));
}

export function isLongStage(stage: AnalysisStage | null): boolean {
  return stage === "rag" || stage === "llm";
}

export function isStageDetailProgress(progress: AnalysisProgress): boolean {
  return progress.detail !== null && progress.detail.trim().length > 0;
}
