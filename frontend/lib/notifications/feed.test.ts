import { describe, expect, it } from "vitest";

import type { NotificationPreferences } from "@/lib/api/schemas";

import {
  applyOptimisticPreferences,
  buildPreferencesUpdate,
  createPreferencesDraft,
  isE164,
  isPreferencesDraftDirty,
  maskPhoneDestination,
  notificationBand,
  notificationChannel,
  notificationKind,
  notificationScore,
  notificationTarget,
  phoneChannelDraftSchema,
  preferencesDraftSchema,
  type PreferencesDraft,
} from "./feed";

const NOW = "2026-11-16T15:00:00.000Z";

const PREFERENCES: NotificationPreferences = {
  locale: "pt-BR",
  timezone: "America/Sao_Paulo",
  channels: [
    {
      channel: "email",
      enabled: true,
      destination: "v***@example.test",
      consented_at: "2026-11-01T12:00:00Z",
    },
    { channel: "sms", enabled: false, destination: null, consented_at: null },
    { channel: "whatsapp", enabled: false, destination: null, consented_at: null },
  ],
};

function baseDraft(overrides: Partial<PreferencesDraft> = {}): PreferencesDraft {
  return {
    ...createPreferencesDraft(PREFERENCES).draft,
    ...overrides,
  };
}

describe("notificationTarget", () => {
  it("prefers the analysis and falls back to the payable", () => {
    expect(
      notificationTarget({
        analysis_id: "11111111-1111-4111-8111-111111111111",
        payable_id: "22222222-2222-4222-8222-222222222222",
      }),
    ).toEqual({
      kind: "analysis",
      href: "/verificacao/11111111-1111-4111-8111-111111111111",
    });

    expect(notificationTarget({ payable_id: "22222222-2222-4222-8222-222222222222" })).toEqual({
      kind: "payable",
      href: "/pagamentos?vencimento=22222222-2222-4222-8222-222222222222",
    });
  });

  it("returns null for invalid or missing ids", () => {
    expect(notificationTarget({})).toBeNull();
    expect(notificationTarget({ analysis_id: "not-a-uuid" })).toBeNull();
  });
});

describe("notification payload helpers", () => {
  it("reads only valid channels, kinds, scores and bands", () => {
    expect(notificationChannel({ channel: "whatsapp" })).toBe("whatsapp");
    expect(notificationChannel({ channel: "in_app" })).toBe("in_app");
    expect(notificationChannel({ channel: "carrier-pigeon" })).toBeNull();
    expect(notificationKind({ document_type: "receipt" })).toBe("receipt");
    expect(notificationKind({ document_type: "unknown" })).toBeNull();
    expect(notificationScore({ score: "82" })).toBe(82);
    expect(notificationScore({ score: "120" })).toBeNull();
    expect(notificationBand({ band: "high" })).toBe("high");
    expect(notificationBand({ band: "medium" })).toBeNull();
  });
});

describe("phone masking and E.164", () => {
  it("accepts the backend E.164 format", () => {
    expect(isE164("+5511999999999")).toBe(true);
    expect(isE164("11999999999")).toBe(false);
    expect(isE164("+1")).toBe(false);
  });

  it("masks the middle of a valid phone", () => {
    expect(maskPhoneDestination("+5511999999999")).toBe("+55 11 *****9999");
    expect(maskPhoneDestination("+15551234567")).toBe("+15 55 *****4567");
    expect(maskPhoneDestination("11999999999")).toBeNull();
  });
});

describe("preference drafts", () => {
  it("starts phone channels with masked destinations requiring confirmation", () => {
    const state = createPreferencesDraft({
      ...PREFERENCES,
      channels: [
        PREFERENCES.channels[0],
        {
          channel: "sms",
          enabled: true,
          destination: "+55 11 *****9999",
          consented_at: "2026-11-01T12:00:00Z",
        },
        PREFERENCES.channels[2],
      ],
    });

    expect(state.draft.sms).toEqual({ enabled: true, destination: "", consent: true });
    expect(state.needsPhoneConfirmation).toBe(true);
  });

  it("validates enabled phone channels with Zod codes", () => {
    const missing = phoneChannelDraftSchema.safeParse({
      enabled: true,
      destination: "",
      consent: true,
    });
    const invalid = phoneChannelDraftSchema.safeParse({
      enabled: true,
      destination: "11999999999",
      consent: true,
    });
    const noConsent = phoneChannelDraftSchema.safeParse({
      enabled: true,
      destination: "+5511999999999",
      consent: false,
    });
    const valid = phoneChannelDraftSchema.safeParse({
      enabled: true,
      destination: "+5511999999999",
      consent: true,
    });

    expect(missing.success).toBe(false);
    expect(invalid.success).toBe(false);
    expect(noConsent.success).toBe(false);
    expect(valid.success).toBe(true);

    if (!missing.success) {
      expect(missing.error.issues[0]?.message).toBe("required");
    }

    if (!invalid.success) {
      expect(invalid.error.issues[0]?.message).toBe("e164");
    }

    if (!noConsent.success) {
      expect(noConsent.error.issues[0]?.message).toBe("consent");
    }
  });

  it("accepts a disabled phone channel without destination or consent", () => {
    const result = preferencesDraftSchema.safeParse(
      baseDraft({
        sms: { enabled: false, destination: "", consent: false },
      }),
    );

    expect(result.success).toBe(true);
  });

  it("detects dirty drafts", () => {
    expect(isPreferencesDraftDirty(baseDraft(), PREFERENCES)).toBe(false);
    expect(
      isPreferencesDraftDirty(
        baseDraft({ email: { enabled: false, destination: "", consent: false } }),
        PREFERENCES,
      ),
    ).toBe(true);
  });

  it("builds the full replacement payload for all channels", () => {
    expect(
      buildPreferencesUpdate(
        baseDraft({
          sms: { enabled: true, destination: "+5511999999999", consent: true },
        }),
        PREFERENCES,
      ),
    ).toEqual({
      email: {
        enabled: true,
        destination: "v***@example.test",
        consent: true,
      },
      sms: {
        enabled: true,
        destination: "+5511999999999",
        consent: true,
      },
      whatsapp: {
        enabled: false,
        destination: null,
        consent: false,
      },
    });
  });

  it("applies optimistic values with a masked phone", () => {
    const optimistic = applyOptimisticPreferences(
      PREFERENCES,
      baseDraft({
        sms: { enabled: true, destination: "+5511999999999", consent: true },
      }),
      NOW,
    );
    const sms = optimistic.channels.find((channel) => channel.channel === "sms");

    expect(sms).toEqual({
      channel: "sms",
      enabled: true,
      destination: "+55 11 *****9999",
      consented_at: NOW,
    });
  });
});
