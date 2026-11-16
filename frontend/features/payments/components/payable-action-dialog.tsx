"use client";

import { useState, type FormEvent } from "react";
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
import { reschedulePayableRequestSchema } from "@/lib/api/schemas/payables";
import type { Payable } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { usePayableAction, useReschedulePayable } from "@/features/payables/hooks/use-payables";

export type PayableActionRequest =
  | { kind: "pay"; payable: Payable }
  | { kind: "confirm"; payable: Payable }
  | { kind: "reschedule"; payable: Payable };

function actionErrorKey(error: unknown): "payments.action.stateError" | "payments.action.error" {
  return error instanceof ApiError && (error.status === 409 || error.status === 404)
    ? "payments.action.stateError"
    : "payments.action.error";
}

type RescheduleFormProps = {
  payable: Payable;
  onDone: () => void;
};

function RescheduleForm({ payable, onDone }: RescheduleFormProps) {
  const { t } = useI18n();
  const mutation = useReschedulePayable();
  const [dueDate, setDueDate] = useState(payable.due_date);
  const [error, setError] = useState<string | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = reschedulePayableRequestSchema.safeParse({ due_date: dueDate });

    if (!parsed.success) {
      setError(t("payments.reschedule.invalid"));
      return;
    }

    setError(null);
    mutation.mutate(
      { payableId: payable.id, dueDate: parsed.data.due_date },
      {
        onSuccess: () => {
          toast.success(t("payments.reschedule.success"));
          onDone();
        },
        onError: (mutationError) => {
          toast.error(t(actionErrorKey(mutationError)));
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1.5">
        <label
          htmlFor="payable-due-date"
          className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
        >
          {t("payments.reschedule.label")}
        </label>
        <input
          id="payable-due-date"
          type="date"
          value={dueDate}
          onChange={(event) => setDueDate(event.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? "payable-due-date-error" : undefined}
          className={cn(
            "h-9 w-full rounded-[6px] border bg-surface px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring",
            error ? "border-risk-high/60" : "border-border",
          )}
        />
        {error ? (
          <p id="payable-due-date-error" className="text-xs text-risk-high">
            {error}
          </p>
        ) : null}
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone} disabled={mutation.isPending}>
          {t("payments.receipt.cancel")}
        </Button>
        <Button type="submit" disabled={mutation.isPending}>
          {t("payments.reschedule.submit")}
        </Button>
      </DialogFooter>
    </form>
  );
}

export type PayableActionDialogProps = {
  request: PayableActionRequest | null;
  onClose: () => void;
};

export function PayableActionDialog({ request, onClose }: PayableActionDialogProps) {
  const { t, formatDate } = useI18n();
  const mutation = usePayableAction();

  function close(): void {
    if (!mutation.isPending) {
      onClose();
    }
  }

  function confirmAction(): void {
    if (!request || request.kind === "reschedule") {
      return;
    }

    mutation.mutate(
      {
        payableId: request.payable.id,
        action: request.kind === "pay" ? "pay" : "confirm",
      },
      {
        onSuccess: () => {
          toast.success(
            t(request.kind === "pay" ? "payments.pay.success" : "payments.confirm.success"),
          );
          onClose();
        },
        onError: (error) => {
          toast.error(t(actionErrorKey(error)));
        },
      },
    );
  }

  if (!request) {
    return null;
  }

  const payable = request.payable;
  const isReschedule = request.kind === "reschedule";
  const titleKey =
    request.kind === "pay"
      ? "payments.pay.title"
      : request.kind === "confirm"
        ? "payments.confirm.title"
        : "payments.reschedule.title";
  const submitKey =
    request.kind === "pay"
      ? "payments.pay.submit"
      : request.kind === "confirm"
        ? "payments.confirm.submit"
        : "payments.reschedule.submit";
  const formattedDue = formatDate(`${payable.due_date}T12:00:00Z`, {
    dateStyle: "long",
  });

  return (
    <Dialog open onOpenChange={(nextOpen) => (nextOpen ? undefined : close())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t(titleKey)}</DialogTitle>
          <DialogDescription>
            {request.kind === "pay"
              ? t("payments.pay.description", {
                  description: payable.description,
                  date: formattedDue,
                })
              : request.kind === "confirm"
                ? t("payments.confirm.description", {
                    description: payable.description,
                  })
                : t("payments.reschedule.description", {
                    description: payable.description,
                  })}
          </DialogDescription>
        </DialogHeader>

        {isReschedule ? (
          <RescheduleForm
            key={`${payable.id}-${payable.due_date}`}
            payable={payable}
            onDone={close}
          />
        ) : (
          <DialogFooter>
            <Button type="button" variant="outline" onClick={close} disabled={mutation.isPending}>
              {t("payments.receipt.cancel")}
            </Button>
            <Button type="button" onClick={confirmAction} disabled={mutation.isPending}>
              {t(submitKey)}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
