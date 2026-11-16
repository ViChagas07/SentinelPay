"use client";

import { BellRing, Info } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ReminderPreference } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";
import {
  reminderFormSchema,
  reminderFormToUpdate,
  reminderPreferenceToForm,
} from "@/lib/payables/reminder-form";

import { SectionError } from "@/features/dashboard/components/section-error";
import {
  useReminderPreferences,
  useUpdateReminderPreferences,
} from "@/features/payables/hooks/use-payables";

type ReminderFormProps = {
  preference: ReminderPreference;
};

function ReminderForm({ preference }: ReminderFormProps) {
  const { t } = useI18n();
  const initial = reminderPreferenceToForm(preference);
  const mutation = useUpdateReminderPreferences();
  const [offsetsInput, setOffsetsInput] = useState(initial.offsetsInput);
  const [localTime, setLocalTime] = useState(initial.localTime);
  const [errors, setErrors] = useState<{ offsets?: string; time?: string }>({});

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = reminderFormSchema.safeParse({ offsetsInput, localTime });

    if (!result.success) {
      const nextErrors: { offsets?: string; time?: string } = {};

      for (const issue of result.error.issues) {
        if (issue.message === "offsets") {
          nextErrors.offsets = t("payments.reminders.offsetsError");
        }

        if (issue.message === "time") {
          nextErrors.time = t("payments.reminders.timeError");
        }
      }

      setErrors(nextErrors);
      return;
    }

    setErrors({});
    mutation.mutate(reminderFormToUpdate(result.data), {
      onSuccess: () => toast.success(t("payments.reminders.saved")),
      onError: () => toast.error(t("payments.reminders.error")),
    });
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <label
            htmlFor="reminder-offsets"
            className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
          >
            {t("payments.reminders.offsets")}
          </label>
          <input
            id="reminder-offsets"
            type="text"
            value={offsetsInput}
            onChange={(event) => setOffsetsInput(event.target.value)}
            aria-invalid={Boolean(errors.offsets)}
            aria-describedby={errors.offsets ? "reminder-offsets-error" : "reminder-offsets-hint"}
            className="h-9 w-full rounded-[6px] border border-border bg-surface px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          {errors.offsets ? (
            <p id="reminder-offsets-error" className="text-xs text-risk-high">
              {errors.offsets}
            </p>
          ) : (
            <p
              id="reminder-offsets-hint"
              className="text-[0.65rem] leading-relaxed text-muted-foreground"
            >
              {t("payments.reminders.offsetsHint")}
            </p>
          )}
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="reminder-time"
            className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
          >
            {t("payments.reminders.time")}
          </label>
          <input
            id="reminder-time"
            type="time"
            value={localTime}
            onChange={(event) => setLocalTime(event.target.value)}
            aria-invalid={Boolean(errors.time)}
            aria-describedby={errors.time ? "reminder-time-error" : undefined}
            className="h-9 w-full rounded-[6px] border border-border bg-surface px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          {errors.time ? (
            <p id="reminder-time-error" className="text-xs text-risk-high">
              {errors.time}
            </p>
          ) : (
            <p className="text-[0.65rem] leading-relaxed text-muted-foreground">
              {t("payments.reminders.timezone", { timezone: preference.timezone })}
            </p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground">
          {t("payments.reminders.channel")}
        </span>
        <Badge variant="petrol">
          <BellRing className="size-3" aria-hidden="true" />
          {t("payments.reminders.inApp")}
        </Badge>
      </div>

      <p className="flex items-start gap-2 text-[0.65rem] leading-relaxed text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        <span>
          {t("payments.reminders.channelNote")}{" "}
          <Link
            href="/notificacoes#canais"
            className="underline underline-offset-4 hover:text-foreground"
          >
            {t("notifications.preferences.title")}
          </Link>
        </span>
      </p>

      <Button type="submit" disabled={mutation.isPending}>
        {t("payments.reminders.save")}
      </Button>
    </form>
  );
}

export function RemindersPanel() {
  const { t } = useI18n();
  const query = useReminderPreferences();

  return (
    <section
      id="payments-reminders"
      aria-labelledby="payments-reminders-title"
      className="scroll-mt-24 rounded-[6px] border border-border bg-card p-5 sm:p-6"
    >
      <h2
        id="payments-reminders-title"
        className="font-serif text-2xl leading-tight tracking-tight"
      >
        {t("payments.reminders.title")}
      </h2>
      <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        {t("payments.reminders.description")}
      </p>

      <div className="mt-4">
        {query.isPending ? (
          <div className="space-y-2" role="status" aria-live="polite">
            <span className="sr-only">{t("payments.reminders.loading")}</span>
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-2/3" />
          </div>
        ) : query.isError || !query.data ? (
          <SectionError
            onRetry={() => void query.refetch()}
            message={t("payments.reminders.error")}
          />
        ) : (
          <ReminderForm preference={query.data} />
        )}
      </div>
    </section>
  );
}
