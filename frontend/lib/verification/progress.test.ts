import { describe, expect, it } from "vitest";

import type { AnalysisProgress } from "@/lib/api/schemas";

import {
  ANALYSIS_STAGES,
  displayPercent,
  isLongStage,
  progressOf,
  stageStateLabelKey,
  stageStates,
} from "./progress";

function progress(stage: AnalysisProgress["stage"], percent = 50): AnalysisProgress {
  return {
    percent,
    stage,
    detail: stage === null ? null : "detalhe",
    started_at: null,
    indeterminate: true,
  };
}

describe("analysis progress", () => {
  it("marks all stages pending while queued", () => {
    expect(stageStates(progress(null, 0), "queued")).toEqual(ANALYSIS_STAGES.map(() => "pending"));
  });

  it("marks previous stages done, the current stage active and the rest pending", () => {
    expect(stageStates(progress("rag", 55), "running")).toEqual([
      "done",
      "done",
      "done",
      "done",
      "active",
      "pending",
      "pending",
    ]);
  });

  it("marks the current stage as cancelling when cancellation is requested", () => {
    expect(stageStates(progress("llm", 80), "cancelling")[5]).toBe("cancelling");
    expect(stageStates(progress(null, 0), "cancelling")[0]).toBe("cancelling");
  });

  it("marks the current stage failed or cancelled without advancing", () => {
    expect(stageStates(progress("ocr", 10), "failed")[1]).toBe("failed");
    expect(stageStates(progress("ocr", 10), "cancelled")[1]).toBe("cancelled");
  });

  it("marks all stages done on completion", () => {
    expect(stageStates(progress("persistence", 100), "completed")).toEqual(
      ANALYSIS_STAGES.map(() => "done"),
    );
    expect(stageStates(progress(null, 0), "degraded")).toEqual(ANALYSIS_STAGES.map(() => "done"));
  });

  it("uses the persisted percentage and forces completion to one hundred", () => {
    expect(displayPercent(progress("rag", 55), "running")).toBe(55);
    expect(displayPercent(progress(null, 0), "completed")).toBe(100);
    expect(displayPercent(progress("ocr", 130), "running")).toBe(100);
    expect(displayPercent(progress("ocr", -10), "running")).toBe(0);
  });

  it("falls back honestly when the API does not send progress", () => {
    expect(progressOf(undefined, "running")).toMatchObject({
      percent: 0,
      stage: null,
      indeterminate: true,
    });
    expect(progressOf(undefined, "completed").percent).toBe(100);
  });

  it("flags the long stages and maps their state labels", () => {
    expect(isLongStage("rag")).toBe(true);
    expect(isLongStage("llm")).toBe(true);
    expect(isLongStage("ocr")).toBe(false);
    expect(stageStateLabelKey("cancelled")).toBe("verification.job.stage.cancelled");
  });
});
