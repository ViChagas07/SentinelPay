"use client";

import { FileText, Image as ImageIcon, Upload, X } from "lucide-react";
import { useId, useRef, useState, type ClipboardEvent, type DragEvent } from "react";

import { Button } from "@/components/ui/button";
import { INTL_LOCALE } from "@/lib/i18n/format";
import { useI18n } from "@/lib/i18n/provider";
import {
  formatFileSize,
  getUploadMaxBytes,
  validateUploadFile,
  type UploadValidation,
} from "@/lib/verification/upload";
import { cn } from "@/lib/utils";

export type UploadDropzoneProps = {
  file: File | null;
  onFileChange: (file: File | null, validation: UploadValidation | null) => void;
  error: string | null;
  disabled?: boolean;
};

function fileFromClipboard(event: ClipboardEvent<HTMLDivElement>): File | null {
  const files = event.clipboardData.files;

  if (files.length > 0) {
    return files[0] ?? null;
  }

  for (const item of Array.from(event.clipboardData.items)) {
    if (item.kind === "file") {
      return item.getAsFile();
    }
  }

  return null;
}

export function UploadDropzone({
  file,
  onFileChange,
  error,
  disabled = false,
}: UploadDropzoneProps) {
  const { t, locale } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const hintId = useId();
  const errorId = useId();
  const limit = formatFileSize(getUploadMaxBytes(), INTL_LOCALE[locale]);

  function acceptFile(candidate: File | null): void {
    if (!candidate) {
      return;
    }

    onFileChange(candidate, validateUploadFile(candidate));
  }

  function openPicker(): void {
    if (disabled) {
      return;
    }

    inputRef.current?.click();
  }

  function handleDrop(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    setDragActive(false);

    if (disabled) {
      return;
    }

    acceptFile(event.dataTransfer.files[0] ?? null);
  }

  function handlePaste(event: ClipboardEvent<HTMLDivElement>): void {
    if (disabled) {
      return;
    }

    const pasted = fileFromClipboard(event);

    if (pasted) {
      event.preventDefault();
      acceptFile(pasted);
    }
  }

  const describedBy = error ? `${hintId} ${errorId}` : hintId;

  return (
    <div
      onDragEnter={(event) => {
        event.preventDefault();
        if (!disabled) {
          setDragActive(true);
        }
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) {
          setDragActive(true);
        }
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        setDragActive(false);
      }}
      onDrop={handleDrop}
      onPaste={handlePaste}
      className={cn(
        "rounded-[6px] border border-dashed p-4 transition-colors",
        dragActive ? "border-petrol-600 bg-petrol-50/40" : "border-border bg-surface",
        error ? "border-risk-high/60" : "",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
        className="hidden"
        aria-label={t("verification.upload.dropzone.inputLabel")}
        onChange={(event) => {
          acceptFile(event.target.files?.[0] ?? null);
          event.target.value = "";
        }}
        disabled={disabled}
      />

      {file ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-[6px] border border-border bg-surface-elevated">
              {file.type.startsWith("image/") ? (
                <ImageIcon className="size-4" aria-hidden="true" />
              ) : (
                <FileText className="size-4" aria-hidden="true" />
              )}
            </span>
            <div className="min-w-0">
              <p className="truncate font-mono text-xs" title={file.name}>
                {file.name}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {formatFileSize(file.size, INTL_LOCALE[locale])}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={openPicker}
              disabled={disabled}
            >
              <Upload aria-hidden="true" />
              {t("verification.upload.dropzone.replace")}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onFileChange(null, null)}
              disabled={disabled}
            >
              <X aria-hidden="true" />
              {t("verification.upload.dropzone.remove")}
            </Button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={openPicker}
          disabled={disabled}
          aria-describedby={describedBy}
          className="flex w-full flex-col items-center gap-2 rounded-[6px] px-4 py-8 text-center outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-60"
        >
          <span className="flex size-12 items-center justify-center rounded-full border border-border bg-surface-elevated">
            <Upload className="size-5" aria-hidden="true" />
          </span>
          <span className="text-base font-medium">{t("verification.upload.dropzone.label")}</span>
          <span id={hintId} className="text-xs leading-relaxed text-muted-foreground">
            {t("verification.upload.dropzone.hint")}
          </span>
          <span className="text-xs leading-relaxed text-muted-foreground">
            {t("verification.upload.dropzone.pasteHint")}
          </span>
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">
            {t("verification.upload.dropzone.limit", { size: limit })}
          </span>
        </button>
      )}

      {file ? (
        <p id={hintId} className="mt-3 text-xs leading-relaxed text-muted-foreground">
          {t("verification.upload.dropzone.hint")} {t("verification.upload.dropzone.pasteHint")}
        </p>
      ) : null}

      {error ? (
        <p id={errorId} role="alert" className="mt-3 text-sm text-foreground">
          {error}
        </p>
      ) : null}
    </div>
  );
}
