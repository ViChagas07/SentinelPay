import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import {
  analysisDetail,
  applyFakeSessionCookies,
  installFakeBackend,
  problem,
  type FakeResponse,
} from "./support/fake-backend";
import type { NotificationItem, NotificationPreferences } from "@/lib/api/schemas";

const ANALYSIS_ID = "70000000-0000-4000-8000-000000000007";
const PAYABLE_ID = "10000000-0000-4000-8000-000000000001";
const NOW = "2026-11-16T12:00:00Z";

const INITIAL_NOTIFICATIONS: NotificationItem[] = [
  {
    id: "90000000-0000-4000-8000-000000000009",
    type: "analysis_completed",
    payload: {
      analysis_id: ANALYSIS_ID,
      document_type: "boleto",
      score: "82",
      band: "high",
    },
    read: false,
    read_at: null,
    created_at: NOW,
  },
  {
    id: "a0000000-0000-4000-8000-00000000000a",
    type: "payable_due_today",
    payload: {
      payable_id: PAYABLE_ID,
      due_date: "2026-11-16",
      channel: "in_app",
    },
    read: false,
    read_at: null,
    created_at: NOW,
  },
  {
    id: "b0000000-0000-4000-8000-00000000000b",
    type: "high_risk_detected",
    payload: {
      analysis_id: ANALYSIS_ID,
      document_type: "payslip",
      score: "91",
      band: "high",
    },
    read: true,
    read_at: "2026-11-15T10:00:00Z",
    created_at: "2026-11-15T09:00:00Z",
  },
  {
    id: "c0000000-0000-4000-8000-00000000000c",
    type: "payable_due_soon",
    payload: {
      payable_id: PAYABLE_ID,
      due_date: "2026-11-21",
      offset_days: "5",
      channel: "in_app",
    },
    read: false,
    read_at: null,
    created_at: "2026-11-14T09:00:00Z",
  },
];

function requireBaseUrl(): string {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  return baseURL;
}

type NotificationsHarness = {
  notifications: NotificationItem[];
  unread: number;
  preferences: NotificationPreferences;
};

async function openNotifications(
  page: Page,
  context: BrowserContext,
  options: { failPreferencesSave?: boolean } = {},
): Promise<NotificationsHarness> {
  const baseURL = requireBaseUrl();
  const harness: NotificationsHarness = {
    notifications: INITIAL_NOTIFICATIONS.map((item) => ({ ...item })),
    unread: 3,
    preferences: {
      locale: "pt-BR",
      timezone: "UTC",
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
    },
  };

  function listNotifications(url: URL): FakeResponse {
    const types = url.searchParams.getAll("type");
    const unreadOnly = url.searchParams.get("unread") === "true";
    let items = harness.notifications;

    if (types.length > 0) {
      items = items.filter((item) => types.includes(item.type));
    }

    if (unreadOnly) {
      items = items.filter((item) => !item.read);
    }

    return { status: 200, body: { items, next_cursor: null } };
  }

  await applyFakeSessionCookies(context, baseURL);
  await installFakeBackend(page, {
    notifications: listNotifications,
    unreadCount: () => ({ status: 200, body: { unread: harness.unread } }),
    readAll: () => {
      const updated = harness.notifications.filter((item) => !item.read).length;

      harness.notifications = harness.notifications.map((item) =>
        item.read ? item : { ...item, read: true, read_at: NOW },
      );
      harness.unread = 0;

      return { status: 200, body: { updated } };
    },
    notificationRead: (notificationId) => {
      const item = harness.notifications.find((candidate) => candidate.id === notificationId);

      if (!item) {
        return { status: 404, body: { code: "notification_not_found" } };
      }

      if (!item.read) {
        item.read = true;
        item.read_at = NOW;
        harness.unread = Math.max(0, harness.unread - 1);
      }

      return { status: 200, body: item };
    },
    notificationPreferences: () => ({ status: 200, body: harness.preferences }),
    updateNotificationPreferences: (body) => {
      if (options.failPreferencesSave) {
        return problem(500, "internal_error", "Falha de teste ao salvar canais.");
      }

      const parsed = body as {
        email?: { enabled?: boolean; consent?: boolean };
        sms?: { enabled?: boolean; destination?: string | null; consent?: boolean };
        whatsapp?: { enabled?: boolean; destination?: string | null; consent?: boolean };
      };
      const email = harness.preferences.channels.find((item) => item.channel === "email");
      const sms = harness.preferences.channels.find((item) => item.channel === "sms");
      const whatsapp = harness.preferences.channels.find((item) => item.channel === "whatsapp");

      harness.preferences = {
        ...harness.preferences,
        channels: [
          {
            channel: "email",
            enabled: Boolean(parsed.email?.enabled),
            destination: email?.destination ?? null,
            consented_at: parsed.email?.enabled ? "2026-11-16T12:00:00Z" : null,
          },
          {
            channel: "sms",
            enabled: Boolean(parsed.sms?.enabled),
            destination: parsed.sms?.enabled ? "+55 11 *****9999" : null,
            consented_at: parsed.sms?.enabled ? "2026-11-16T12:00:00Z" : null,
          },
          {
            channel: "whatsapp",
            enabled: Boolean(parsed.whatsapp?.enabled),
            destination: parsed.whatsapp?.enabled ? "+55 11 *****8888" : null,
            consented_at: parsed.whatsapp?.enabled ? "2026-11-16T12:00:00Z" : null,
          },
        ],
      };
      void sms;
      void whatsapp;

      return { status: 200, body: harness.preferences };
    },
    detail: (analysisId) => ({
      status: 200,
      body: analysisDetail({
        id: analysisId,
        kind: "boleto",
        status: "completed",
        result_available: true,
        result: {
          score: 82,
          band: "high",
          base_score: 80,
          llm_adjustment: 2,
          evidence: [],
          justification: "Justificativa sintética do teste.",
          inconsistencies: [],
          degradation_flags: [],
        },
      }),
    }),
  });
  await page.goto("/notificacoes");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 20_000 });

  return harness;
}

test.describe("notifications", () => {
  test("keeps the sidebar badge coherent with the real unread list", async ({ page, context }) => {
    const harness = await openNotifications(page, context);

    await expect(page.getByText("04 / Notificações")).toBeVisible();
    await expect(page.getByText("Não lidas: 3")).toBeVisible();
    await expect(page.getByText("3 não lidas")).toBeVisible();

    const list = page.getByRole("list", { name: "Recentes" });
    await expect(list.getByRole("listitem")).toHaveCount(4);
    await expect(list.getByText("Análise concluída")).toBeVisible();
    await expect(list.getByText("Vence hoje")).toBeVisible();
    await expect(list.getByText("Risco alto detectado")).toBeVisible();
    await expect(list.getByText("Vencimento próximo")).toBeVisible();

    const channelFilter = page.getByRole("combobox", { name: "Canal" });
    await expect(channelFilter).toBeDisabled();
    await expect(
      page.getByText(
        "A API não informa o canal de entrega na notificação. O filtro por canal fica indisponível.",
      ),
    ).toBeVisible();

    await page.getByRole("combobox", { name: "Tipo" }).click();
    await page.getByRole("option", { name: "Risco alto detectado" }).click();
    await expect(list.getByRole("listitem")).toHaveCount(1);
    await expect(list.getByText("Risco alto detectado")).toBeVisible();

    await page.getByRole("combobox", { name: "Tipo" }).click();
    await page.getByRole("option", { name: "Todos os tipos" }).click();
    await expect(list.getByRole("listitem")).toHaveCount(4);

    await page.getByRole("button", { name: "Marcar todas como lidas" }).click();
    await expect(page.getByText("Notificações marcadas como lidas.")).toBeVisible();
    await expect(page.getByText("Nenhuma não lida")).toBeVisible();
    await expect(page.getByText("3 não lidas")).toHaveCount(0);
    expect(harness.unread).toBe(0);

    await page.reload();
    await expect(page.getByText("Nenhuma não lida")).toBeVisible();
    await expect(page.getByText("3 não lidas")).toHaveCount(0);
  });

  test("has no axe violations on the notification center", async ({ page, context }) => {
    await openNotifications(page, context);

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
  });

  test("marks one notification as read and links to the related analysis", async ({
    page,
    context,
  }) => {
    const harness = await openNotifications(page, context);
    const list = page.getByRole("list", { name: "Recentes" });

    await list.getByRole("button", { name: "Marcar como lida" }).first().click();
    await expect(page.getByText("Não lidas: 2")).toBeVisible();
    await expect(page.getByText("2 não lidas")).toBeVisible();
    expect(harness.unread).toBe(2);

    await list.getByRole("link", { name: /Análise concluída/ }).click();
    await expect(page).toHaveURL(new RegExp(`/verificacao/${ANALYSIS_ID}$`));
    await expect(page.getByRole("heading", { name: "Índice de risco" })).toBeVisible({
      timeout: 20_000,
    });
  });

  test("persists channel preferences across reloads", async ({ page, context }) => {
    await openNotifications(page, context);

    const emailSwitch = page.getByRole("switch", { name: "Desativar E-mail" });
    await expect(emailSwitch).toHaveAttribute("aria-checked", "true");
    await emailSwitch.click();
    await page.getByRole("button", { name: "Salvar canais" }).click();
    await expect(page.getByText("Canais de alerta atualizados.")).toBeVisible();

    await page.reload();
    await expect(page.getByRole("switch", { name: "Ativar E-mail" })).toHaveAttribute(
      "aria-checked",
      "false",
    );

    await page.getByRole("switch", { name: "Ativar SMS" }).click();
    await page.getByRole("textbox", { name: "Número de SMS" }).fill("+5511999999999");
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Salvar canais" }).click();
    await expect(page.getByText("Canais de alerta atualizados.")).toBeVisible();

    await page.reload();
    await expect(page.getByRole("switch", { name: "Desativar SMS" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(page.getByText("+55 11 *****9999").first()).toBeVisible();
  });

  test("reverts an optimistic channel change when the server fails", async ({ page, context }) => {
    await openNotifications(page, context, { failPreferencesSave: true });

    await page.getByRole("switch", { name: "Desativar E-mail" }).click();
    await page.getByRole("button", { name: "Salvar canais" }).click();

    await expect(page.getByText("Não foi possível salvar os canais.")).toBeVisible();
    await expect(page.getByRole("switch", { name: "Desativar E-mail" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });
});
