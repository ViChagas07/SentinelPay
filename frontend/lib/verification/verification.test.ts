import { describe, expect, it } from "vitest";

import { getEvidenceFramework, getRuleLabelKey } from "./evidence";
import {
  elapsedBetween,
  formatElapsed,
  isActiveStatus,
  isCancellableStatus,
  isLongRunning,
  isTerminalStatus,
  pollIntervalFor,
  LONG_JOB_MS,
} from "./polling";
import {
  DEFAULT_UPLOAD_MAX_MB,
  createIdempotencyKey,
  formatFileSize,
  getUploadMaxMb,
  validateUploadFile,
} from "./upload";

function fileOf(name: string, type: string, size: number): File {
  const content = new Uint8Array(Math.max(1, Math.min(size, 1024)));
  const file = new File([content], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

describe("upload validation", () => {
  it("accepts PDF, PNG and JPEG by MIME type", () => {
    expect(validateUploadFile(fileOf("boleto.pdf", "application/pdf", 2048), 1024 * 1024)).toEqual({
      ok: true,
      kind: "pdf",
    });
    expect(validateUploadFile(fileOf("conta.png", "image/png", 2048), 1024 * 1024)).toEqual({
      ok: true,
      kind: "image",
    });
    expect(validateUploadFile(fileOf("conta.jpg", "image/jpeg", 2048), 1024 * 1024)).toEqual({
      ok: true,
      kind: "image",
    });
  });

  it("falls back to the extension when the browser sends a generic MIME type", () => {
    expect(
      validateUploadFile(fileOf("documento.PDF", "application/octet-stream", 2048), 1024 * 1024),
    ).toEqual({ ok: true, kind: "pdf" });
    expect(validateUploadFile(fileOf("foto.JPEG", "", 2048), 1024 * 1024)).toEqual({
      ok: true,
      kind: "image",
    });
  });

  it("rejects empty files, unsupported types and files above the limit", () => {
    expect(validateUploadFile(fileOf("vazio.pdf", "application/pdf", 0), 100)).toMatchObject({
      ok: false,
      reason: "empty",
    });
    expect(validateUploadFile(fileOf("texto.txt", "text/plain", 10), 100)).toMatchObject({
      ok: false,
      reason: "unsupported_type",
    });
    expect(validateUploadFile(fileOf("grande.pdf", "application/pdf", 101), 100)).toMatchObject({
      ok: false,
      reason: "too_large",
    });
  });

  it("uses the backend default of 25 MB when the environment has no override", () => {
    expect(getUploadMaxMb()).toBe(DEFAULT_UPLOAD_MAX_MB);
  });

  it("formats file sizes in the interface locale", () => {
    expect(formatFileSize(512 * 1024, "pt-BR")).toContain("512");
    expect(formatFileSize(1.5 * 1024 * 1024, "pt-BR")).toContain("1,5");
    expect(formatFileSize(2 * 1024 * 1024, "en")).toContain("2");
  });

  it("creates idempotency keys inside the backend format", () => {
    const keyword = createIdempotencyKey();
    const second = createIdempotencyKey();

    expect(keyword).toMatch(/^[A-Za-z0-9._:-]{8,128}$/);
    expect(second).not.toBe(keyword);
  });
});

describe("job polling", () => {
  it("classifies terminal and active statuses", () => {
    expect(isTerminalStatus("completed")).toBe(true);
    expect(isTerminalStatus("degraded")).toBe(true);
    expect(isTerminalStatus("failed")).toBe(true);
    expect(isTerminalStatus("cancelled")).toBe(true);
    expect(isTerminalStatus("queued")).toBe(false);
    expect(isTerminalStatus("running")).toBe(false);
    expect(isTerminalStatus("processing")).toBe(false);
    expect(isTerminalStatus("cancelling")).toBe(false);
    expect(isActiveStatus("queued")).toBe(true);
    expect(isActiveStatus("running")).toBe(true);
    expect(isActiveStatus("processing")).toBe(true);
    expect(isActiveStatus("cancelling")).toBe(true);
    expect(isActiveStatus("cancelled")).toBe(false);
    expect(isCancellableStatus("queued")).toBe(true);
    expect(isCancellableStatus("running")).toBe(true);
    expect(isCancellableStatus("cancelling")).toBe(false);
    expect(isCancellableStatus("completed")).toBe(false);
  });

  it("grows the polling interval with the job age and stops at the end", () => {
    expect(pollIntervalFor("queued", 0)).toBe(2500);
    expect(pollIntervalFor("processing", 30_000)).toBe(2500);
    expect(pollIntervalFor("running", 30_000)).toBe(2500);
    expect(pollIntervalFor("cancelling", 30_000)).toBe(1000);
    expect(pollIntervalFor("processing", 2 * 60_000)).toBe(5000);
    expect(pollIntervalFor("processing", 5 * 60_000)).toBe(10_000);
    expect(pollIntervalFor("processing", 9 * 60_000)).toBe(20_000);
    expect(pollIntervalFor("completed", 0)).toBe(false);
    expect(pollIntervalFor("degraded", 0)).toBe(false);
    expect(pollIntervalFor("failed", 0)).toBe(false);
    expect(pollIntervalFor("cancelled", 0)).toBe(false);
  });

  it("calculates elapsed time and flags long jobs", () => {
    const now = new Date("2026-11-16T12:10:00Z");

    expect(elapsedBetween("2026-11-16T12:00:00Z", now)).toBe(600_000);
    expect(elapsedBetween("not-a-date", now)).toBe(0);
    expect(isLongRunning("processing", LONG_JOB_MS)).toBe(true);
    expect(isLongRunning("running", LONG_JOB_MS)).toBe(true);
    expect(isLongRunning("completed", LONG_JOB_MS)).toBe(false);
  });

  it("formats elapsed time as a stopwatch", () => {
    expect(formatElapsed(0)).toBe("0:00");
    expect(formatElapsed(65_000)).toBe("1:05");
    expect(formatElapsed(3_725_000)).toBe("1:02:05");
  });
});

describe("evidence presentation", () => {
  it("maps each kind to the correct normative framework", () => {
    expect(getEvidenceFramework("boleto", "boleto.dv_invalid")).toBe("febraban");
    expect(getEvidenceFramework("payslip", "payslip.inss_mismatch")).toBe("inss");
    expect(getEvidenceFramework("payslip", "payslip.irrf_mismatch")).toBe("irrf");
    expect(getEvidenceFramework("payslip", "payslip.overtime_below_minimum")).toBe("clt");
    expect(getEvidenceFramework("payslip", "payslip.base_below_minimum")).toBe("folha");
    expect(getEvidenceFramework("payslip", "payslip.net_mismatch")).toBe("folha");
    expect(getEvidenceFramework("payslip", "guardrail.prompt_injection")).toBe("guardrail");
    expect(getEvidenceFramework("receipt", "receipt.dv_invalid")).toBe("arrecadacao");
  });

  it("translates known rule keys and returns null for unknown keys", () => {
    expect(getRuleLabelKey("boleto.dv_invalid")).toBe("verification.rule.boleto.dv_invalid");
    expect(getRuleLabelKey("payslip.net_mismatch")).toBe("verification.rule.payslip.net_mismatch");
    expect(getRuleLabelKey("unknown.rule")).toBeNull();
  });
});
