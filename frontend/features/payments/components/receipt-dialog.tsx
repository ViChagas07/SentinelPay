"use client";

import { Info, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api/errors";
import type { NotificationPreferences } from "@/lib/api/schemas";
import { INTL_LOCALE } from "@/lib/i18n/format";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import { getAnalysisErrorKey } from "@/lib/verification/errors";
import {
  createIdempotencyKey,
  formatFileSize,
  getUploadMaxBytes,
  isAbortError,
  type UploadValidation,
} from "@/lib/verification/upload";
import { uploadAnalysis, type UploadProgress } from "@/lib/verification/upload-analysis";
import { validateReceiptFile, type ReceiptFileError } from "@/lib/payables/receipt-form";
import { queryKeys } from "@/lib/query/keys";

import { rememberDocument } from "@/features/verification/lib/document-handoff";
import { UploadDropzone } from "@/features/verification/components/upload-dropzone";
import { useNotificationPreferences } from "@/features/notifications/hooks/use-notifications";
import { useReminderPreferences } from "@/features/payables/hooks/use-payables";

const FILE_ERROR_KEYS: Record<ReceiptFileError, TranslationKey> = {
  required: "payments.receipt.fileRequired",
  empty: "verification.upload.error.empty",
  too_large: "verification.upload.error.too_large",
  unsupported_type: "verification.upload.error.unsupported_type",
};

function fileErrorMessage(
  reason: ReceiptFileError,
  file: File | null,
  t: (key: TranslationKey, params?: Record<string, string | number>) => string,
  locale: string,
): string {
  if (reason === "too_large" && file) {
    return t("verification.upload.error.too_large", {
      size: formatFileSize(file.size, locale),
      limit: formatFileSize(getUploadMaxBytes(), locale),
    });
  }

  return t(FILE_ERROR_KEYS[reason]);
}

const CHANNEL_LABEL_KEYS = {
  email: "notifications.preferences.email",
  sms: "notifications.preferences.sms",
  whatsapp: "notifications.preferences.whatsapp",
} as const;

function enabledChannelLabels(
  preferences: NotificationPreferences | undefined,
  t: (key: TranslationKey) => string,
): string {
  if (!preferences) {
    return "";
  }

  return preferences.channels
    .filter((channel) => channel.enabled)
    .map((channel) => t(CHANNEL_LABEL_KEYS[channel.channel]))
    .join(", ");
}

export type ReceiptDialogProps = {
  onClose: () => void;
};

export function ReceiptDialog({ onClose }: ReceiptDialogProps) {
  const { t, locale } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [uploadError, setUploadError] = useState<ApiError | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const reminderQuery = useReminderPreferences();
  const notificationQuery = useNotificationPreferences();

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  function selectFile(candidate: File | null, validation: UploadValidation | null): void {
    setIdempotencyKey(null);
    setUploadError(null);
    setFile(candidate);

    if (!candidate) {
      setFileError(null);
      return;
    }

    if (validation && !validation.ok) {
      setFileError(fileErrorMessage(validation.reason, candidate, t, INTL_LOCALE[locale]));
      return;
    }

    const reason = validateReceiptFile(candidate);
    setFileError(reason ? fileErrorMessage(reason, candidate, t, INTL_LOCALE[locale]) : null);
  }

  function close(): void {
    if (!uploading) {
      onClose();
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setUploadError(null);

    const reason = validateReceiptFile(file);

    if (reason || !file) {
      setFileError(fileErrorMessage(reason ?? "required", file, t, INTL_LOCALE[locale]));
      return;
    }

    const controller = new AbortController();
    const key = idempotencyKey ?? createIdempotencyKey();
    setIdempotencyKey(key);
    abortRef.current = controller;
    setUploading(true);
    setProgress({ loaded: 0, total: file.size, percent: 0, lengthComputable: file.size > 0 });

    try {
      const created = await uploadAnalysis(
        { file, kind: "receipt", idempotencyKey: key },
        {
          signal: controller.signal,
          onProgress: setProgress,
          locale: INTL_LOCALE[locale],
        },
      );

      rememberDocument(created.analysis_id, file);
      setIdempotencyKey(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.analyses.all });
      await queryClient.invalidateQueries({ queryKey: queryKeys.payables.all });
      toast.success(t("payments.receipt.success"));
      onClose();
      router.push(`/verificacao/${created.analysis_id}`);
    } catch (error) {
      if (isAbortError(error)) {
        setUploading(false);
        setProgress(null);
        return;
      }

      setUploading(false);
      setUploadError(
        error instanceof ApiError
          ? error
          : new ApiError({
              status: 0,
              code: "network_error",
              title: "Network error",
              detail: "The receipt upload could not reach the service.",
            }),
      );
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  }

  const channels = enabledChannelLabels(notificationQuery.data, t);
  const reminderSummary = reminderQuery.data
    ? t("payments.receipt.remindersSummary", {
        offsets: reminderQuery.data.offsets_days.join(", "),
        time: reminderQuery.data.local_time.slice(0, 5),
      })
    : reminderQuery.isPending
      ? t("payments.reminders.loading")
      : t("payments.receipt.remindersUnavailable");

  return (
    <Dialog
      open
      onOpenChange={(nextOpen) => {
        if (!nextOpen) {
          close();
        }
      }}
    >
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("payments.receipt.title")}</DialogTitle>
          <DialogDescription>{t("payments.receipt.description")}</DialogDescription>
        </DialogHeader>

        <form onSubmit={(event) => void submit(event)} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1.5">
              <label
                htmlFor="receipt-type"
                className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
              >
                {t("payments.receipt.type")}
              </label>
              <input
                id="receipt-type"
                type="text"
                value={t("payments.receipt.typeReceipt")}
                readOnly
                disabled
                className="h-9 w-full rounded-[6px] border border-border bg-surface px-3 text-sm text-foreground outline-none disabled:opacity-100"
              />
            </div>
            {[
              { id: "receipt-issuer", label: t("payments.receipt.issuer") },
              { id: "receipt-amount", label: t("payments.receipt.amount") },
              { id: "receipt-due", label: t("payments.receipt.dueDate") },
            ].map((field) => (
              <div key={field.id} className="space-y-1.5">
                <label
                  htmlFor={field.id}
                  className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
                >
                  {field.label}
                </label>
                <input
                  id={field.id}
                  type="text"
                  value=""
                  readOnly
                  disabled
                  placeholder={t("payments.receipt.extracted")}
                  className="h-9 w-full rounded-[6px] border border-border bg-surface px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground disabled:opacity-100"
                />
              </div>
            ))}
          </div>

          <p className="flex items-start gap-2 text-[0.65rem] leading-relaxed text-muted-foreground">
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            <span>{t("payments.receipt.manualNote")}</span>
          </p>

          <div className="space-y-1.5">
            <span className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground">
              {t("payments.receipt.file")}
            </span>
            <UploadDropzone
              file={file}
              onFileChange={selectFile}
              error={fileError}
              disabled={uploading}
            />
            <p className="text-[0.65rem] leading-relaxed text-muted-foreground">
              {t("payments.receipt.fileRequired")}
            </p>
          </div>

          <div className="space-y-2 rounded-[6px] border border-border bg-surface p-3">
            <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground">
              {t("payments.receipt.reminders")}
            </p>
            <p className="text-xs leading-relaxed">{reminderSummary}</p>
            <a
              href="#payments-reminders"
              onClick={(event) => {
                event.preventDefault();
                onClose();
                document.getElementById("payments-reminders")?.scrollIntoView({
                  block: "start",
                });
              }}
              className="inline-flex text-xs underline underline-offset-4 hover:text-foreground"
            >
              {t("payments.receipt.configureReminders")}
            </a>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {channels
                ? t("payments.receipt.channelsValue", { channels })
                : notificationQuery.isPending
                  ? t("notifications.preferences.loading")
                  : notificationQuery.isError
                    ? t("notifications.preferences.error")
                    : t("payments.receipt.noChannels")}
            </p>
            <Link
              href="/notificacoes#canais"
              onClick={onClose}
              className="inline-flex text-xs underline underline-offset-4 hover:text-foreground"
            >
              {t("payments.receipt.channelsLink")}
            </Link>
          </div>

          {uploadError ? (
            <p
              role="alert"
              className="rounded-[6px] border border-risk-high/40 bg-risk-high/5 p-3 text-xs text-foreground"
            >
              {t(getAnalysisErrorKey(uploadError.code))}
            </p>
          ) : null}

          {uploading ? (
            <div className="space-y-1">
              <div
                role="progressbar"
                aria-label={t("payments.receipt.uploading")}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={progress?.percent ?? 0}
                className="h-1.5 overflow-hidden rounded-full bg-border"
              >
                <div
                  className="h-full bg-primary transition-[width] duration-200 motion-reduce:transition-none"
                  style={{ width: `${progress?.percent ?? 0}%` }}
                />
              </div>
              <p className="text-[0.65rem] text-muted-foreground">
                {t("payments.receipt.uploading")} {progress?.percent ?? 0}%
              </p>
            </div>
          ) : null}

          <DialogFooter>
            {uploading ? (
              <Button type="button" variant="outline" onClick={() => abortRef.current?.abort()}>
                {t("payments.receipt.cancelUpload")}
              </Button>
            ) : (
              <>
                <Button type="button" variant="outline" onClick={close}>
                  {t("payments.receipt.cancel")}
                </Button>
                <Button type="submit">
                  <ShieldCheck aria-hidden="true" />
                  {t("payments.receipt.submit")}
                </Button>
              </>
            )}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
