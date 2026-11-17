"use client";

import { Loader2, XCircle } from "lucide-react";
import { useState } from "react";

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
import type { AnalysisStatus } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";
import { isCancellableStatus } from "@/lib/verification/polling";

import { useCancelAnalysis } from "../hooks/use-verification";

export type CancelAnalysisButtonProps = {
  analysisId: string;
  status: AnalysisStatus;
  onCancelled?: () => void;
  onRefresh?: () => void;
};

export function CancelAnalysisButton({
  analysisId,
  status,
  onCancelled,
  onRefresh,
}: CancelAnalysisButtonProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const cancel = useCancelAnalysis(analysisId);
  const cancelling = status === "cancelling" || cancel.isPending;
  const cancellable = isCancellableStatus(status);

  if (!cancellable && !cancelling) {
    return null;
  }

  const conflict = cancel.error instanceof ApiError && cancel.error.status === 409;
  const failureMessage = conflict
    ? t("verification.cancel.alreadyFinished")
    : t("verification.cancel.error");

  const handleConfirm = (): void => {
    cancel.mutate(undefined, {
      onSuccess: (data) => {
        setOpen(false);
        if (data.status === "cancelled") {
          onCancelled?.();
        }
      },
      onError: () => {
        onRefresh?.();
      },
    });
  };

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="border-risk-high/40 text-risk-high hover:bg-risk-high/5"
        disabled={cancelling}
        onClick={() => setOpen(true)}
        aria-busy={cancelling}
      >
        {cancelling ? (
          <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
        ) : (
          <XCircle aria-hidden="true" />
        )}
        {cancelling ? t("verification.cancel.cancelling") : t("verification.cancel.button")}
      </Button>

      <Dialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (next) {
            cancel.reset();
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("verification.cancel.confirmTitle")}</DialogTitle>
            <DialogDescription>{t("verification.cancel.confirmBody")}</DialogDescription>
          </DialogHeader>

          {cancel.isError ? (
            <p role="alert" className="text-sm text-risk-high">
              {failureMessage}
            </p>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              {t("verification.cancel.keep")}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="border-risk-high/40 text-risk-high hover:bg-risk-high/5"
              onClick={handleConfirm}
              disabled={cancel.isPending}
              aria-busy={cancel.isPending}
            >
              {cancel.isPending ? (
                <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
              ) : null}
              {cancel.isPending
                ? t("verification.cancel.cancelling")
                : t("verification.cancel.confirmAction")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
