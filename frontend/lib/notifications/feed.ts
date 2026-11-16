import { z } from "zod";

import type {
  ChannelPreference,
  NotificationPreferences,
  NotificationPreferencesUpdate,
} from "@/lib/api/schemas";
import { uuidSchema } from "@/lib/api/schemas/common";

export const NOTIFICATIONS_PAGE_SIZE = 20;
export const NOTIFICATIONS_POLL_MS = 20_000;

const E164_PATTERN = /^\+[1-9]\d{7,14}$/;

export const NOTIFICATION_CHANNELS = ["email", "sms", "whatsapp", "in_app"] as const;
export type NotificationChannel = (typeof NOTIFICATION_CHANNELS)[number];

export type NotificationTarget =
  { kind: "analysis"; href: string } | { kind: "payable"; href: string };

export function notificationTarget(payload: Record<string, string>): NotificationTarget | null {
  const analysisId = payload.analysis_id;

  if (analysisId && uuidSchema.safeParse(analysisId).success) {
    return {
      kind: "analysis",
      href: `/verificacao/${encodeURIComponent(analysisId)}`,
    };
  }

  const payableId = payload.payable_id;

  if (payableId && uuidSchema.safeParse(payableId).success) {
    return {
      kind: "payable",
      href: `/pagamentos?vencimento=${encodeURIComponent(payableId)}`,
    };
  }

  return null;
}

export function notificationChannel(payload: Record<string, string>): NotificationChannel | null {
  const channel = payload.channel;

  return channel && (NOTIFICATION_CHANNELS as readonly string[]).includes(channel)
    ? (channel as NotificationChannel)
    : null;
}

export function notificationKind(
  payload: Record<string, string>,
): "boleto" | "payslip" | "receipt" | null {
  const kind = payload.document_type;

  return kind === "boleto" || kind === "payslip" || kind === "receipt" ? kind : null;
}

export function notificationScore(payload: Record<string, string>): number | null {
  const score = Number(payload.score);

  return Number.isInteger(score) && score >= 0 && score <= 100 ? score : null;
}

export function notificationBand(
  payload: Record<string, string>,
): "low" | "attention" | "high" | null {
  const band = payload.band;

  return band === "low" || band === "attention" || band === "high" ? band : null;
}

export function isE164(value: string): boolean {
  return E164_PATTERN.test(value.trim());
}

export function maskPhoneDestination(value: string): string | null {
  const phone = value.trim();

  if (!isE164(phone)) {
    return null;
  }

  const digits = phone.slice(1);
  const country = digits.slice(0, 2);
  const area = digits.slice(2, 4);
  const lastFour = digits.slice(-4);

  return `+${country} ${area} *****${lastFour}`;
}

export type ChannelDraft = {
  enabled: boolean;
  destination: string;
  consent: boolean;
};

export type PreferencesDraft = {
  email: ChannelDraft;
  sms: ChannelDraft;
  whatsapp: ChannelDraft;
};

export type PreferencesDraftState = {
  draft: PreferencesDraft;
  needsPhoneConfirmation: boolean;
};

function findChannel(
  preferences: NotificationPreferences,
  channel: "email" | "sms" | "whatsapp",
): ChannelPreference | null {
  return preferences.channels.find((item) => item.channel === channel) ?? null;
}

export function createPreferencesDraft(
  preferences: NotificationPreferences,
): PreferencesDraftState {
  const email = findChannel(preferences, "email");
  const sms = findChannel(preferences, "sms");
  const whatsapp = findChannel(preferences, "whatsapp");

  return {
    draft: {
      email: {
        enabled: email?.enabled ?? false,
        destination: email?.destination ?? "",
        consent: email?.consented_at !== null && email?.consented_at !== undefined,
      },
      sms: {
        enabled: sms?.enabled ?? false,
        destination: "",
        consent: sms?.consented_at !== null && sms?.consented_at !== undefined,
      },
      whatsapp: {
        enabled: whatsapp?.enabled ?? false,
        destination: "",
        consent: whatsapp?.consented_at !== null && whatsapp?.consented_at !== undefined,
      },
    },
    needsPhoneConfirmation: Boolean(sms?.enabled || whatsapp?.enabled),
  };
}

export const phoneChannelDraftSchema = z
  .object({
    enabled: z.boolean(),
    destination: z.string(),
    consent: z.boolean(),
  })
  .superRefine((value, context) => {
    if (!value.enabled) {
      return;
    }

    if (value.destination.trim().length === 0) {
      context.addIssue({
        code: "custom",
        path: ["destination"],
        message: "required",
      });
      return;
    }

    if (!isE164(value.destination)) {
      context.addIssue({
        code: "custom",
        path: ["destination"],
        message: "e164",
      });
    }

    if (!value.consent) {
      context.addIssue({
        code: "custom",
        path: ["consent"],
        message: "consent",
      });
    }
  });

export const preferencesDraftSchema = z.object({
  email: z.object({
    enabled: z.boolean(),
    destination: z.string(),
    consent: z.boolean(),
  }),
  sms: phoneChannelDraftSchema,
  whatsapp: phoneChannelDraftSchema,
});

export function isPreferencesDraftDirty(
  draft: PreferencesDraft,
  preferences: NotificationPreferences,
): boolean {
  const email = findChannel(preferences, "email");
  const sms = findChannel(preferences, "sms");
  const whatsapp = findChannel(preferences, "whatsapp");

  return (
    draft.email.enabled !== (email?.enabled ?? false) ||
    draft.sms.enabled !== (sms?.enabled ?? false) ||
    draft.whatsapp.enabled !== (whatsapp?.enabled ?? false) ||
    draft.sms.destination.trim().length > 0 ||
    draft.whatsapp.destination.trim().length > 0 ||
    (draft.sms.enabled && draft.sms.consent !== Boolean(sms?.consented_at)) ||
    (draft.whatsapp.enabled && draft.whatsapp.consent !== Boolean(whatsapp?.consented_at))
  );
}

export function buildPreferencesUpdate(
  draft: PreferencesDraft,
  preferences: NotificationPreferences,
): NotificationPreferencesUpdate {
  const email = findChannel(preferences, "email");

  return {
    email: {
      enabled: draft.email.enabled,
      destination: email?.destination ?? null,
      consent: draft.email.enabled,
    },
    sms: draft.sms.enabled
      ? {
          enabled: true,
          destination: draft.sms.destination.trim(),
          consent: true,
        }
      : { enabled: false, destination: null, consent: false },
    whatsapp: draft.whatsapp.enabled
      ? {
          enabled: true,
          destination: draft.whatsapp.destination.trim(),
          consent: true,
        }
      : { enabled: false, destination: null, consent: false },
  };
}

function optimisticChannel(
  current: ChannelPreference | null,
  channel: "email" | "sms" | "whatsapp",
  draft: ChannelDraft,
  nowIso: string,
): ChannelPreference {
  const enabled = draft.enabled;
  const destination =
    channel === "email"
      ? (current?.destination ?? null)
      : enabled
        ? maskPhoneDestination(draft.destination)
        : null;

  return {
    channel,
    enabled,
    destination,
    consented_at: enabled ? (current?.consented_at ?? nowIso) : null,
  };
}

export function applyOptimisticPreferences(
  preferences: NotificationPreferences,
  draft: PreferencesDraft,
  nowIso: string,
): NotificationPreferences {
  const email = findChannel(preferences, "email");
  const sms = findChannel(preferences, "sms");
  const whatsapp = findChannel(preferences, "whatsapp");

  return {
    ...preferences,
    channels: [
      optimisticChannel(email, "email", draft.email, nowIso),
      optimisticChannel(sms, "sms", draft.sms, nowIso),
      optimisticChannel(whatsapp, "whatsapp", draft.whatsapp, nowIso),
    ],
  };
}
