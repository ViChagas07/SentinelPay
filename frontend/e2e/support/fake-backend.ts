import type { BrowserContext, Page, Route } from "@playwright/test";

export type FakeResponse = {
  status: number;
  body: unknown;
  contentType?: string;
  headers?: Record<string, string>;
};

export type FakeBackendOptions = {
  create?: FakeResponse | (() => FakeResponse);
  detail?: (analysisId: string) => FakeResponse;
  list?: FakeResponse | ((url: URL) => FakeResponse);
  payables?: FakeResponse | ((url: URL) => FakeResponse);
  payableAction?: (payableId: string, action: string) => FakeResponse;
  payableDueDate?: (payableId: string, dueDate: string) => FakeResponse;
  notifications?: FakeResponse | ((url: URL) => FakeResponse);
  unreadCount?: FakeResponse | (() => FakeResponse);
  readAll?: FakeResponse | (() => FakeResponse);
  notificationRead?: (notificationId: string) => FakeResponse;
  notificationPreferences?: FakeResponse | (() => FakeResponse);
  updateNotificationPreferences?: (body: unknown) => FakeResponse;
  reminderPreferences?: FakeResponse | (() => FakeResponse);
  updateReminderPreferences?: (body: unknown) => FakeResponse;
  logout?: FakeResponse | (() => FakeResponse);
};

const DEFAULT_NOTIFICATION_PREFERENCES = {
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
};

const DEFAULT_REMINDER_PREFERENCES = {
  offsets_days: [3, 1, 0],
  local_time: "09:00:00",
  channels: ["in_app"],
  timezone: "UTC",
};

function resolveResponse(
  response: FakeResponse | undefined | (() => FakeResponse),
  fallback: FakeResponse,
): FakeResponse {
  return typeof response === "function" ? response() : (response ?? fallback);
}

export const FAKE_USER = {
  id: "11111111-1111-4111-8111-111111111111",
  email: "verificacao.e2e@example.test",
  name: "Sessão de verificação",
  role: "user",
  preferred_locale: "pt-BR",
  timezone: "UTC",
};

export function problem(status: number, code: string, detail: string): FakeResponse {
  return {
    status,
    contentType: "application/problem+json",
    body: {
      type: `https://paysentineliq.local/problems/${code}`,
      title: "Erro de teste",
      status,
      detail,
      instance: "/api/v1/analyses",
      code,
      request_id: "req-e2e",
    },
  };
}

export function analysisDetail(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  const now = new Date().toISOString();

  return {
    id: "22222222-2222-4222-8222-222222222222",
    status: "completed",
    kind: "boleto",
    created_at: now,
    updated_at: now,
    error_code: null,
    result_available: true,
    result: {
      score: 82,
      band: "high",
      base_score: 80,
      llm_adjustment: 2,
      evidence: [
        {
          rule_id: "dv_invalid",
          severity: "critical",
          weight: 70,
          message_key: "boleto.dv_invalid",
          source: "knowledge/febraban/manual_febraban_v1.pdf#1.5",
        },
      ],
      justification: "A linha digitável não fecha com o dígito verificador conferido.",
      inconsistencies: ["Valor diverge da linha digitável."],
      degradation_flags: [],
    },
    ...overrides,
  };
}

export async function applyFakeSessionCookies(
  context: BrowserContext,
  baseURL: string,
): Promise<void> {
  await context.addCookies([
    { name: "sp_session", value: "fake-session-token", url: baseURL, httpOnly: true },
    { name: "sp_refresh", value: "fake-refresh-token", url: baseURL, httpOnly: true },
    { name: "sp_csrf", value: "fake-csrf-token", url: baseURL, httpOnly: true },
    {
      name: "sp_session_exp",
      value: String(Date.now() + 10 * 60_000),
      url: baseURL,
      httpOnly: true,
    },
  ]);
}

async function fulfillResponse(route: Route, response: FakeResponse): Promise<void> {
  await route.fulfill({
    status: response.status,
    contentType: response.contentType ?? "application/json",
    headers: { "x-request-id": "req-e2e", ...response.headers },
    body:
      response.status === 204 || response.status === 304
        ? undefined
        : JSON.stringify(response.body),
  });
}

export async function installFakeBackend(
  page: Page,
  options: FakeBackendOptions = {},
): Promise<void> {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const path = url.pathname;

    if (path === "/api/v1/auth/logout" && method === "POST") {
      const response = typeof options.logout === "function" ? options.logout() : options.logout;

      if (response) {
        await fulfillResponse(route, response);
        return;
      }

      await route.fulfill({ status: 204, headers: { "x-request-id": "req-e2e" } });
      return;
    }

    if (path === "/api/v1/users/me" && method === "GET") {
      await fulfillResponse(route, { status: 200, body: FAKE_USER });
      return;
    }

    if (path === "/api/v1/notifications/unread-count" && method === "GET") {
      await fulfillResponse(
        route,
        resolveResponse(options.unreadCount, { status: 200, body: { unread: 0 } }),
      );
      return;
    }

    if (path === "/api/v1/notifications/read-all" && method === "POST") {
      await fulfillResponse(
        route,
        resolveResponse(options.readAll, { status: 200, body: { updated: 0 } }),
      );
      return;
    }

    if (path === "/api/v1/notifications" && method === "GET") {
      const notifications = options.notifications;
      const response = typeof notifications === "function" ? notifications(url) : notifications;

      await fulfillResponse(
        route,
        response ?? { status: 200, body: { items: [], next_cursor: null } },
      );
      return;
    }

    if (path.startsWith("/api/v1/notifications/") && path.endsWith("/read") && method === "POST") {
      const notificationId = path.slice("/api/v1/notifications/".length, -"/read".length);

      if (options.notificationRead) {
        await fulfillResponse(route, options.notificationRead(notificationId));
        return;
      }

      await fulfillResponse(
        route,
        problem(404, "notification_not_found", "Notificação não encontrada."),
      );
      return;
    }

    if (path === "/api/v1/notification-preferences" && method === "GET") {
      await fulfillResponse(
        route,
        resolveResponse(options.notificationPreferences, {
          status: 200,
          body: DEFAULT_NOTIFICATION_PREFERENCES,
        }),
      );
      return;
    }

    if (path === "/api/v1/notification-preferences" && method === "PUT") {
      const body = request.postDataJSON() as unknown;

      if (options.updateNotificationPreferences) {
        await fulfillResponse(route, options.updateNotificationPreferences(body));
        return;
      }

      await fulfillResponse(route, { status: 200, body: DEFAULT_NOTIFICATION_PREFERENCES });
      return;
    }

    if (path === "/api/v1/payables/reminder-preferences" && method === "GET") {
      await fulfillResponse(
        route,
        resolveResponse(options.reminderPreferences, {
          status: 200,
          body: DEFAULT_REMINDER_PREFERENCES,
        }),
      );
      return;
    }

    if (path === "/api/v1/payables/reminder-preferences" && method === "PUT") {
      const body = request.postDataJSON() as {
        offsets_days?: number[];
        local_time?: string;
        channels?: string[];
      };

      if (options.updateReminderPreferences) {
        await fulfillResponse(route, options.updateReminderPreferences(body));
        return;
      }

      await fulfillResponse(route, {
        status: 200,
        body: {
          offsets_days: body.offsets_days ?? [3, 1, 0],
          local_time: body.local_time ?? "09:00:00",
          channels: body.channels ?? ["in_app"],
          timezone: "UTC",
        },
      });
      return;
    }

    if (path === "/api/v1/payables" && method === "GET") {
      const payables = options.payables;
      const response = typeof payables === "function" ? payables(url) : payables;

      await fulfillResponse(
        route,
        response ?? { status: 200, body: { items: [], next_cursor: null } },
      );
      return;
    }

    if (path.startsWith("/api/v1/payables/") && method === "POST") {
      const rest = path.slice("/api/v1/payables/".length);
      const [payableId, action] = rest.split("/");

      if (payableId && action && options.payableAction) {
        await fulfillResponse(route, options.payableAction(payableId, action));
        return;
      }

      await fulfillResponse(route, problem(404, "payable_not_found", "Vencimento não encontrado."));
      return;
    }

    if (path.startsWith("/api/v1/payables/") && path.endsWith("/due-date") && method === "PATCH") {
      const payableId = path.slice("/api/v1/payables/".length, -"/due-date".length);
      const body = request.postDataJSON() as { due_date?: string };

      if (options.payableDueDate && body.due_date) {
        await fulfillResponse(route, options.payableDueDate(payableId, body.due_date));
        return;
      }

      await fulfillResponse(route, problem(404, "payable_not_found", "Vencimento não encontrado."));
      return;
    }

    if (path === "/api/v1/analyses" && method === "GET") {
      const list = options.list;
      const response =
        typeof list === "function"
          ? list(url)
          : (list ?? { status: 200, body: { items: [], next_cursor: null } });

      await fulfillResponse(route, response);
      return;
    }

    if (path === "/api/v1/analyses" && method === "POST") {
      const create = options.create;
      const response =
        typeof create === "function"
          ? create()
          : (create ?? {
              status: 202,
              body: {
                analysis_id: "22222222-2222-4222-8222-222222222222",
                status: "queued",
              },
            });

      await fulfillResponse(route, response);
      return;
    }

    if (path.startsWith("/api/v1/analyses/") && method === "GET") {
      const analysisId = path.slice("/api/v1/analyses/".length);

      if (options.detail) {
        await fulfillResponse(route, options.detail(analysisId));
        return;
      }

      await fulfillResponse(route, problem(404, "analysis_not_found", "Análise não encontrada."));
      return;
    }

    await fulfillResponse(route, problem(404, "not_found", "Rota de teste não mapeada."));
  });
}
