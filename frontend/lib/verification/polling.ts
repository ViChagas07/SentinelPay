import type { AnalysisStatus } from "@/lib/api/schemas";

export const LONG_JOB_MS = 10 * 60_000;

const SECOND_MS = 1000;
const MINUTE_MS = 60 * SECOND_MS;

export function isTerminalStatus(status: AnalysisStatus): boolean {
  return (
    status === "completed" || status === "degraded" || status === "failed" || status === "cancelled"
  );
}

export function isActiveStatus(status: AnalysisStatus): boolean {
  return (
    status === "queued" ||
    status === "running" ||
    status === "processing" ||
    status === "cancelling"
  );
}

export function isCancellableStatus(status: AnalysisStatus): boolean {
  return status === "queued" || status === "running" || status === "processing";
}

export function pollIntervalFor(status: AnalysisStatus, elapsedMs: number): number | false {
  if (isTerminalStatus(status)) {
    return false;
  }

  if (status === "cancelling") {
    return 1000;
  }

  const elapsed = Math.max(0, Number.isFinite(elapsedMs) ? elapsedMs : 0);

  if (elapsed < MINUTE_MS) {
    return 2500;
  }

  if (elapsed < 3 * MINUTE_MS) {
    return 5000;
  }

  if (elapsed < 8 * MINUTE_MS) {
    return 10_000;
  }

  return 20_000;
}

export function elapsedBetween(createdAt: string, now: Date = new Date()): number {
  const created = new Date(createdAt).getTime();

  if (Number.isNaN(created)) {
    return 0;
  }

  return Math.max(0, now.getTime() - created);
}

export function formatElapsed(elapsedMs: number): string {
  const totalSeconds = Math.max(0, Math.floor(elapsedMs / SECOND_MS));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function isLongRunning(status: AnalysisStatus, elapsedMs: number): boolean {
  return isActiveStatus(status) && elapsedMs >= LONG_JOB_MS;
}
