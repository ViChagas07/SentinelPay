"use client";

import { Info } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ChannelPreference, NotificationPreferences } from "@/lib/api/schemas";

import { useI18n } from "@/lib/i18n/provider";
import {
  applyOptimisticPreferences,
  buildPreferencesUpdate,
  createPreferencesDraft,
  isPreferencesDraftDirty,
  maskPhoneDestination,
  preferencesDraftSchema,
  type ChannelDraft,
  type PreferencesDraft,
} from "@/lib/notifications/feed";
import { cn } from "@/lib/utils";

import { SectionError } from "@/features/dashboard/components/section-error";
import {
  useNotificationPreferences,
  useUpdateNotificationPreferences,
} from "../hooks/use-notifications";

const CHANNEL_KEYS = {
  email: "notifications.preferences.email",
  sms: "notifications.preferences.sms",
  whatsapp: "notifications.preferences.whatsapp",
} as const;

type PhoneChannel = "sms" | "whatsapp";

type DraftErrors = Partial<
  Record<"smsDestination" | "smsConsent" | "whatsappDestination" | "whatsappConsent", string>
>;

function findChannel(
  preferences: NotificationPreferences,
  channel: "email" | "sms" | "whatsapp",
): ChannelPreference | null {
  return preferences.channels.find((item) => item.channel === channel) ?? null;
}

function ChannelSwitch({
  checked,
  onChange,
  label,
}: Readonly<{
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}>) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative h-5 w-9 shrink-0 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        checked ? "border-primary bg-primary" : "border-border bg-border",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "absolute top-0.5 size-3.5 rounded-full bg-background transition-transform motion-reduce:transition-none",
          checked ? "translate-x-[18px]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

type PhoneDraftProps = {
  channel: PhoneChannel;
  draft: ChannelDraft;
  preference: ChannelPreference | null;
  errors: DraftErrors;
  onChange: (patch: Partial<ChannelDraft>) => void;
};

function PhoneDraftFields({ channel, draft, preference, errors, onChange }: PhoneDraftProps) {
  const { t } = useI18n();
  const destinationKey = channel === "sms" ? "smsDestination" : "whatsappDestination";
  const consentKey = channel === "sms" ? "smsConsent" : "whatsappConsent";
  const destinationError = errors[destinationKey];
  const consentError = errors[consentKey];
  const maskedNeedsConfirmation = Boolean(preference?.enabled) && draft.enabled;
  const destinationId = `${channel}-destination`;
  const consentId = `${channel}-consent`;
  const destinationErrorId = `${channel}-destination-error`;
  const consentErrorId = `${channel}-consent-error`;

  return (
    <div className="mt-3 space-y-2 rounded-[6px] border border-border bg-surface p-3">
      {maskedNeedsConfirmation ? (
        <p className="flex items-start gap-2 text-[0.65rem] leading-relaxed text-muted-foreground">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <span>{t("notifications.preferences.confirmPhone")}</span>
        </p>
      ) : null}

      <div className="space-y-1">
        <label
          htmlFor={destinationId}
          className="font-mono text-[0.6rem] uppercase tracking-[0.14em] text-muted-foreground"
        >
          {t("notifications.preferences.phoneFor", {
            channel: t(CHANNEL_KEYS[channel]),
          })}
        </label>
        <input
          id={destinationId}
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          value={draft.destination}
          placeholder={t("notifications.preferences.phoneHint")}
          onChange={(event) => onChange({ destination: event.target.value })}
          aria-invalid={Boolean(destinationError)}
          aria-describedby={destinationError ? destinationErrorId : undefined}
          className={cn(
            "h-9 w-full rounded-[6px] border bg-surface px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring",
            destinationError ? "border-risk-high/60" : "border-border",
          )}
        />
        {destinationError ? (
          <p id={destinationErrorId} className="text-xs text-risk-high">
            {destinationError}
          </p>
        ) : null}
      </div>

      <label htmlFor={consentId} className="flex items-start gap-2 text-xs leading-relaxed">
        <input
          id={consentId}
          type="checkbox"
          checked={draft.consent}
          onChange={(event) => onChange({ consent: event.target.checked })}
          aria-invalid={Boolean(consentError)}
          aria-describedby={consentError ? consentErrorId : undefined}
          className="mt-0.5 size-4 shrink-0 rounded-[3px] border border-border accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <span>{t("notifications.preferences.consent")}</span>
      </label>
      {consentError ? (
        <p id={consentErrorId} className="text-xs text-risk-high">
          {consentError}
        </p>
      ) : null}
    </div>
  );
}

type ChannelBlockProps = {
  channel: "email" | "sms" | "whatsapp";
  draft: ChannelDraft;
  preference: ChannelPreference | null;
  errors: DraftErrors;
  onChange: (patch: Partial<ChannelDraft>) => void;
};

function ChannelBlock({ channel, draft, preference, errors, onChange }: ChannelBlockProps) {
  const { t, formatDate } = useI18n();
  const label = t(CHANNEL_KEYS[channel]);
  const destination =
    channel === "email"
      ? (preference?.destination ?? t("notifications.preferences.notConfigured"))
      : draft.enabled && draft.destination
        ? (maskPhoneDestination(draft.destination) ?? t("notifications.preferences.notConfigured"))
        : (preference?.destination ?? t("notifications.preferences.notConfigured"));
  const consent = preference?.consented_at
    ? t("notifications.preferences.consentedAt", {
        date: formatDate(preference.consented_at, { dateStyle: "short" }),
      })
    : draft.enabled && draft.consent
      ? t("notifications.preferences.consentPending")
      : t("notifications.preferences.notConsented");

  return (
    <div className="border-b border-border py-4 first:pt-0 last:border-b-0 last:pb-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">{label}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {t("notifications.preferences.destination")}: {destination}
          </p>
          <p className="mt-0.5 text-[0.65rem] text-muted-foreground">{consent}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Badge variant={draft.enabled ? "petrol" : "outline"}>
            {draft.enabled
              ? t("notifications.preferences.enabled")
              : t("notifications.preferences.disabled")}
          </Badge>
          <ChannelSwitch
            checked={draft.enabled}
            onChange={(enabled) => onChange({ enabled })}
            label={t(
              draft.enabled
                ? "notifications.preferences.disable"
                : "notifications.preferences.enable",
              { channel: label },
            )}
          />
        </div>
      </div>

      {channel !== "email" && draft.enabled ? (
        <PhoneDraftFields
          channel={channel}
          draft={draft}
          preference={preference}
          errors={errors}
          onChange={onChange}
        />
      ) : null}
    </div>
  );
}

function ChannelsForm({ preferences }: Readonly<{ preferences: NotificationPreferences }>) {
  const { t } = useI18n();
  const mutation = useUpdateNotificationPreferences();
  const [draft, setDraft] = useState<PreferencesDraft>(
    () => createPreferencesDraft(preferences).draft,
  );
  const [errors, setErrors] = useState<DraftErrors>({});
  const dirty = isPreferencesDraftDirty(draft, preferences);
  const maskedPhoneNeedsConfirmation =
    (Boolean(findChannel(preferences, "sms")?.enabled) &&
      draft.sms.enabled &&
      draft.sms.destination.trim().length === 0) ||
    (Boolean(findChannel(preferences, "whatsapp")?.enabled) &&
      draft.whatsapp.enabled &&
      draft.whatsapp.destination.trim().length === 0);

  function updateChannel(channel: "email" | "sms" | "whatsapp", patch: Partial<ChannelDraft>) {
    setErrors({});
    setDraft((current) => ({
      ...current,
      [channel]: { ...current[channel], ...patch },
    }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = preferencesDraftSchema.safeParse(draft);

    if (!result.success) {
      const nextErrors: DraftErrors = {};

      for (const issue of result.error.issues) {
        const channel = issue.path[0];
        const field = issue.path[1];

        if (
          (channel !== "sms" && channel !== "whatsapp") ||
          (field !== "destination" && field !== "consent")
        ) {
          continue;
        }

        const message =
          issue.message === "consent"
            ? t("notifications.preferences.consentRequired")
            : issue.message === "e164"
              ? t("notifications.preferences.phoneInvalid")
              : t("notifications.preferences.phoneRequired");
        const key =
          `${channel}${field === "destination" ? "Destination" : "Consent"}` as keyof DraftErrors;
        nextErrors[key] = message;
      }

      setErrors(nextErrors);
      return;
    }

    setErrors({});
    const input = buildPreferencesUpdate(draft, preferences);
    const optimistic = applyOptimisticPreferences(preferences, draft, new Date().toISOString());

    mutation.mutate(
      { input, optimistic },
      {
        onSuccess: () => {
          setDraft((current) => ({
            email: current.email,
            sms: { ...current.sms, destination: "" },
            whatsapp: { ...current.whatsapp, destination: "" },
          }));
          toast.success(t("notifications.preferences.saved"));
        },
        onError: () => {
          setDraft(createPreferencesDraft(preferences).draft);
          setErrors({});
          toast.error(t("notifications.preferences.saveError"));
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <ChannelBlock
          channel="email"
          draft={draft.email}
          preference={findChannel(preferences, "email")}
          errors={errors}
          onChange={(patch) => updateChannel("email", patch)}
        />
        <ChannelBlock
          channel="sms"
          draft={draft.sms}
          preference={findChannel(preferences, "sms")}
          errors={errors}
          onChange={(patch) => updateChannel("sms", patch)}
        />
        <ChannelBlock
          channel="whatsapp"
          draft={draft.whatsapp}
          preference={findChannel(preferences, "whatsapp")}
          errors={errors}
          onChange={(patch) => updateChannel("whatsapp", patch)}
        />
      </div>

      <p className="text-[0.65rem] leading-relaxed text-muted-foreground">
        {t("notifications.preferences.maskedHint")} {t("notifications.preferences.verificationGap")}
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          disabled={!dirty || maskedPhoneNeedsConfirmation || mutation.isPending}
        >
          {t("notifications.preferences.save")}
        </Button>
        {!dirty ? (
          <span className="text-[0.65rem] text-muted-foreground">
            {t("notifications.preferences.noChanges")}
          </span>
        ) : null}
      </div>
    </form>
  );
}

export function ChannelsPanel() {
  const { t } = useI18n();
  const query = useNotificationPreferences();

  return (
    <section
      id="canais"
      aria-labelledby="channels-title"
      className="scroll-mt-24 rounded-[6px] border border-border bg-card p-5 sm:p-6"
    >
      <h2 id="channels-title" className="font-serif text-2xl leading-tight tracking-tight">
        {t("notifications.preferences.title")}
      </h2>
      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
        {t("notifications.preferences.description")}
      </p>

      <div className="mt-4">
        {query.isPending ? (
          <div className="space-y-2" role="status" aria-live="polite">
            <span className="sr-only">{t("notifications.preferences.loading")}</span>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : query.isError || !query.data ? (
          <SectionError
            onRetry={() => void query.refetch()}
            message={t("notifications.preferences.error")}
          />
        ) : (
          <ChannelsForm preferences={query.data} />
        )}
      </div>
    </section>
  );
}
