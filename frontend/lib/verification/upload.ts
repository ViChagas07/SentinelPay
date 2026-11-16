import type { AnalysisKind } from "@/lib/api/schemas";

export const DEFAULT_UPLOAD_MAX_MB = 25;

const BYTES_PER_MB = 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg"] as const;
const ACCEPTED_MIME_TYPES = new Set(["application/pdf", "image/png", "image/jpeg"]);
const GENERIC_MIME_TYPES = new Set(["", "application/octet-stream", "binary/octet-stream"]);

export type UploadFileKind = "pdf" | "image";

export type UploadValidation =
  | { ok: true; kind: UploadFileKind }
  | { ok: false; reason: "empty" | "too_large" | "unsupported_type" };

function extensionOf(name: string): string {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

function mimeOf(file: File): string {
  return (file.type || "").toLowerCase().split(";")[0]?.trim() ?? "";
}

export function getUploadMaxMb(): number {
  const configured = Number(process.env.NEXT_PUBLIC_UPLOAD_MAX_MB);

  if (Number.isFinite(configured) && configured > 0 && configured <= 300) {
    return configured;
  }

  return DEFAULT_UPLOAD_MAX_MB;
}

export function getUploadMaxBytes(): number {
  return Math.floor(getUploadMaxMb() * BYTES_PER_MB);
}

export function detectFileKind(file: File): UploadFileKind | "unknown" {
  const mime = mimeOf(file);
  const extension = extensionOf(file.name);

  if (mime === "application/pdf" || extension === ".pdf") {
    return "pdf";
  }

  if (
    mime === "image/png" ||
    mime === "image/jpeg" ||
    extension === ".png" ||
    extension === ".jpg" ||
    extension === ".jpeg"
  ) {
    return "image";
  }

  return "unknown";
}

export function validateUploadFile(
  file: File,
  maxBytes: number = getUploadMaxBytes(),
): UploadValidation {
  if (file.size <= 0) {
    return { ok: false, reason: "empty" };
  }

  if (file.size > maxBytes) {
    return { ok: false, reason: "too_large" };
  }

  const mime = mimeOf(file);
  const extension = extensionOf(file.name);

  if (ACCEPTED_MIME_TYPES.has(mime)) {
    return { ok: true, kind: mime === "application/pdf" ? "pdf" : "image" };
  }

  if (GENERIC_MIME_TYPES.has(mime) && ACCEPTED_EXTENSIONS.includes(extension as never)) {
    return { ok: true, kind: extension === ".pdf" ? "pdf" : "image" };
  }

  return { ok: false, reason: "unsupported_type" };
}

export function formatFileSize(bytes: number, locale: string): string {
  const safeBytes = Math.max(0, Number.isFinite(bytes) ? bytes : 0);

  if (safeBytes < BYTES_PER_MB) {
    return new Intl.NumberFormat(locale, {
      style: "unit",
      unit: "kilobyte",
      maximumFractionDigits: 1,
    }).format(safeBytes / 1024);
  }

  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: "megabyte",
    maximumFractionDigits: 1,
  }).format(safeBytes / BYTES_PER_MB);
}

export function createIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  const bytes = new Uint8Array(16);

  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    crypto.getRandomValues(bytes);
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }

  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export type UploadRequestBody = {
  file: File;
  kind: AnalysisKind;
};

export function buildUploadFormData({ file, kind }: UploadRequestBody): FormData {
  const formData = new FormData();
  formData.set("kind", kind);
  formData.set("file", file);
  return formData;
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
