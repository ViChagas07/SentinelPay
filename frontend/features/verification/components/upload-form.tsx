"use client";

import { AlertCircle, Lock, ShieldCheck } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useI18n } from "@/lib/i18n/provider";
import type { TranslationKey } from "@/lib/i18n";
import { ApiError } from "@/lib/api/errors";
import type { AnalysisKind } from "@/lib/api/schemas";
import { queryKeys } from "@/lib/query/keys";
import { INTL_LOCALE } from "@/lib/i18n/format";
import { getAnalysisErrorKey } from "@/lib/verification/errors";
import {
  createIdempotencyKey,
  formatFileSize,
  getUploadMaxBytes,
  isAbortError,
  validateUploadFile,
} from "@/lib/verification/upload";
import { uploadAnalysis, type UploadProgress } from "@/lib/verification/upload-analysis";

import { rememberDocument } from "../lib/document-handoff";
import { UploadDropzone } from "./upload-dropzone";

type Phase = "idle" | "uploading" | "canceled";

const FILE_ERROR_KEYS: Record<string, TranslationKey> = {
  empty: "verification.upload.error.empty",
  too_large: "verification.upload.error.too_large",
  unsupported_type: "verification.upload.error.unsupported_type",
};

export type UploadFormProps = {
  initialKind?: AnalysisKind;
  onCreated: (analysisId: string, file: File) => void;
};

export function UploadForm({ initialKind, onCreated }: UploadFormProps) {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const typeLabelId = useId();
  const typeErrorId = useId();
  const [kind, setKind] = useState<AnalysisKind | "">(initialKind ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [typeError, setTypeError] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [uploadError, setUploadError] = useState<ApiError | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const idempotencyKeyRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  function describeFileError(reason: string, candidate: File): string {
    const key = FILE_ERROR_KEYS[reason] ?? "verification.upload.error.unsupported_type";
    return t(key, {
      size: formatFileSize(candidate.size, INTL_LOCALE[locale]),
      limit: formatFileSize(getUploadMaxBytes(), INTL_LOCALE[locale]),
    });
  }

  function selectFile(candidate: File | null): void {
    idempotencyKeyRef.current = null;
    setUploadError(null);
    setPhase("idle");
    setProgress(null);

    if (!candidate) {
      setFile(null);
      setFileError(null);
      return;
    }

    setFile(candidate);

    const validation = validateUploadFile(candidate);

    setFileError(validation.ok ? null : describeFileError(validation.reason, candidate));
  }

  async function submit(): Promise<void> {
    setUploadError(null);
    setPhase("idle");
    setProgress(null);

    if (!kind) {
      setTypeError(true);
      return;
    }

    setTypeError(false);

    if (!file) {
      setFileError(t("verification.upload.error.empty"));
      return;
    }

    const validation = validateUploadFile(file);

    if (!validation.ok) {
      setFileError(describeFileError(validation.reason, file));
      return;
    }

    const controller = new AbortController();
    const idempotencyKey = idempotencyKeyRef.current ?? createIdempotencyKey();
    idempotencyKeyRef.current = idempotencyKey;
    abortRef.current = controller;
    setPhase("uploading");
    setProgress({ loaded: 0, total: file.size, percent: 0, lengthComputable: file.size > 0 });

    try {
      const created = await uploadAnalysis(
        { file, kind, idempotencyKey },
        {
          signal: controller.signal,
          onProgress: setProgress,
          locale: INTL_LOCALE[locale],
        },
      );

      idempotencyKeyRef.current = null;
      rememberDocument(created.analysis_id, file);
      await queryClient.invalidateQueries({ queryKey: queryKeys.analyses.all });
      onCreated(created.analysis_id, file);
    } catch (error) {
      if (isAbortError(error)) {
        setPhase("canceled");
        setProgress(null);
        return;
      }

      setPhase("idle");
      setUploadError(
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
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  }

  const uploading = phase === "uploading";
  const fileValid = file ? validateUploadFile(file).ok : false;
  const canSubmit = Boolean(kind && file && fileValid) && !uploading;
  const errorMessage = uploadError ? t(getAnalysisErrorKey(uploadError.code)) : null;

  return (
    <section aria-labelledby="verification-upload-title" className="min-w-0">
      <div className="rounded-[6px] border border-border bg-card p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full border border-border bg-surface-elevated">
            <ShieldCheck className="size-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h2
              id="verification-upload-title"
              className="font-serif text-2xl leading-tight tracking-tight"
            >
              {t("verification.upload.header")}
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              {t("verification.description")}
            </p>
          </div>
        </div>

        <form
          className="mt-6 space-y-5"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <div className="space-y-1.5">
            <span
              id={typeLabelId}
              className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
            >
              {t("verification.type.label")}
            </span>
            <Select
              value={kind}
              onValueChange={(value) => {
                idempotencyKeyRef.current = null;
                setKind(value as AnalysisKind);
                setTypeError(false);
              }}
              disabled={uploading}
            >
              <SelectTrigger
                aria-labelledby={typeLabelId}
                aria-invalid={typeError}
                aria-describedby={typeError ? typeErrorId : undefined}
              >
                <SelectValue placeholder={t("verification.type.placeholder")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="boleto">{t("verification.type.boleto")}</SelectItem>
                <SelectItem value="payslip">{t("verification.type.payslip")}</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {kind === "boleto"
                ? t("verification.type.boletoHint")
                : kind === "payslip"
                  ? t("verification.type.payslipHint")
                  : t("verification.type.required")}
            </p>
            {typeError ? (
              <p id={typeErrorId} role="alert" className="text-sm text-foreground">
                {t("verification.type.required")}
              </p>
            ) : null}
          </div>

          <UploadDropzone
            file={file}
            onFileChange={(candidate) => selectFile(candidate)}
            error={fileError}
            disabled={uploading}
          />

          {uploading ? (
            <div className="rounded-[6px] border border-border bg-surface p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium">{t("verification.upload.submitting")}</p>
                <p className="font-mono text-xs tabular-nums text-muted-foreground">
                  {t("verification.upload.progress.percent", {
                    percent: progress?.percent ?? 0,
                  })}
                </p>
              </div>
              <div
                role="progressbar"
                aria-label={t("verification.upload.progress.aria")}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={progress?.percent ?? 0}
                className="mt-3 h-1.5 w-full overflow-hidden rounded-full border border-border bg-surface-elevated"
              >
                <div
                  className="h-full rounded-full bg-petrol-500 transition-[width] duration-200"
                  style={{ width: `${progress?.percent ?? 0}%` }}
                />
              </div>
              <p className="mt-2 font-mono text-[0.65rem] tabular-nums text-muted-foreground">
                {t("verification.upload.progress.bytes", {
                  loaded: formatFileSize(progress?.loaded ?? 0, INTL_LOCALE[locale]),
                  total: formatFileSize(progress?.total ?? file?.size ?? 0, INTL_LOCALE[locale]),
                })}
              </p>
              {(progress?.percent ?? 0) >= 100 ? (
                <p className="mt-2 text-xs text-muted-foreground">
                  {t("verification.upload.progress.waiting")}
                </p>
              ) : null}
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={() => abortRef.current?.abort()}
              >
                {t("verification.upload.cancel")}
              </Button>
            </div>
          ) : null}

          {phase === "canceled" ? (
            <div role="status" className="rounded-[6px] border border-border bg-surface p-4">
              <p className="text-sm font-medium">{t("verification.upload.canceled.title")}</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {t("verification.upload.canceled.body")}
              </p>
            </div>
          ) : null}

          {errorMessage ? (
            <div
              role="alert"
              className="rounded-[6px] border border-risk-high/50 bg-risk-high/5 p-4"
            >
              <p className="flex items-center gap-2 text-sm font-medium">
                <AlertCircle className="size-4" aria-hidden="true" />
                {t("verification.upload.error.title")}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{errorMessage}</p>
              {uploadError?.requestId ? (
                <p className="mt-2 font-mono text-[0.6rem] text-muted-foreground">
                  {t("verification.upload.error.requestId")} {uploadError.requestId}
                </p>
              ) : null}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="flex max-w-md items-start gap-2 text-xs leading-relaxed text-muted-foreground">
              <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span>
                <span className="font-medium text-foreground">
                  {t("verification.upload.security.title")}.
                </span>{" "}
                {t("verification.upload.security.body")}
              </span>
            </p>
            <Button type="submit" disabled={!canSubmit}>
              {uploading ? t("verification.upload.submitting") : t("verification.upload.submit")}
            </Button>
          </div>
        </form>
      </div>
    </section>
  );
}
