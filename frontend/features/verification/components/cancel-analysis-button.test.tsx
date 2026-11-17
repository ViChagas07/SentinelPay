import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetApiInterceptors } from "@/lib/api";
import { I18nProvider } from "@/lib/i18n/provider";

import { CancelAnalysisButton } from "./cancel-analysis-button";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

const ANALYSIS_ID = "6f0f2b62-6e2a-4b67-8e3f-2d6f4e6a1b2c";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function problem(status: number, code: string): Response {
  return jsonResponse(
    {
      type: "about:blank",
      title: "Conflict",
      status,
      detail: "Analysis has already finished.",
      instance: `/api/v1/analyses/${ANALYSIS_ID}/cancel`,
      code,
      request_id: "req-1",
    },
    status,
  );
}

function renderButton(
  status: "running" | "cancelled" | "completed",
  onCancelled = vi.fn(),
  onRefresh = vi.fn(),
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
    return (
      <I18nProvider initialLocale="pt">
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </I18nProvider>
    );
  }

  render(
    <CancelAnalysisButton
      analysisId={ANALYSIS_ID}
      status={status}
      onCancelled={onCancelled}
      onRefresh={onRefresh}
    />,
    { wrapper: Wrapper },
  );

  return { onCancelled, onRefresh };
}

describe("CancelAnalysisButton", () => {
  afterEach(() => {
    resetApiInterceptors();
    vi.unstubAllGlobals();
  });

  it("asks for confirmation and sends a POST cancel request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ analysis_id: ANALYSIS_ID, status: "cancelling" }, 202));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const { onCancelled } = renderButton("running");

    await user.click(screen.getByRole("button", { name: "Cancelar análise" }));

    expect(screen.getByText("Cancelar esta análise?")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Tem certeza? O progresso será perdido e o resultado parcial será removido.",
      ),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sim, cancelar" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toContain(`/api/v1/analyses/${ANALYSIS_ID}/cancel`);
    expect(init).toMatchObject({ method: "POST", credentials: "include" });
    expect(onCancelled).not.toHaveBeenCalled();
  });

  it("returns to the upload screen when the server confirms the cancellation", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ analysis_id: ANALYSIS_ID, status: "cancelled" }, 202));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const { onCancelled } = renderButton("running");

    await user.click(screen.getByRole("button", { name: "Cancelar análise" }));
    await user.click(screen.getByRole("button", { name: "Sim, cancelar" }));

    await waitFor(() => expect(onCancelled).toHaveBeenCalledTimes(1));
  });

  it("explains that a finished analysis cannot be cancelled", async () => {
    const fetchMock = vi.fn().mockResolvedValue(problem(409, "analysis_not_cancellable"));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const { onRefresh } = renderButton("running");

    await user.click(screen.getByRole("button", { name: "Cancelar análise" }));
    await user.click(screen.getByRole("button", { name: "Sim, cancelar" }));

    await waitFor(() =>
      expect(
        screen.getByText("Esta análise já terminou e não pode ser cancelada."),
      ).toBeInTheDocument(),
    );
    expect(onRefresh).toHaveBeenCalled();
  });

  it("does not render the button for a finished analysis", () => {
    renderButton("completed");

    expect(screen.queryByRole("button", { name: "Cancelar análise" })).not.toBeInTheDocument();
  });
});
