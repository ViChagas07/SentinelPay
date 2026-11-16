import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/i18n/provider", () => ({
  useI18n: () => ({
    t: (key: string) => (key === "app.name" ? "SentinelPay" : key),
  }),
}));

import { DocumentAlerts } from "./document-alerts";

function iconLink(): HTMLLinkElement {
  const link = document.createElement("link");
  link.rel = "icon";
  link.href = "/icon.svg";
  document.head.appendChild(link);
  return link;
}

describe("DocumentAlerts", () => {
  let link: HTMLLinkElement;

  beforeEach(() => {
    link = iconLink();
    document.title = "Painel Principal | SentinelPay";
  });

  afterEach(() => {
    link.remove();
  });

  it("keeps the page title and normal icon when there are no alerts", () => {
    render(<DocumentAlerts count={0} truncated={false} baseTitle="Painel Principal" />);

    expect(document.title).toBe("Painel Principal | SentinelPay");
    expect(link.getAttribute("href")).toBe("/icon.svg");
  });

  it("adds the alert count and the alert icon when alerts exist", () => {
    render(<DocumentAlerts count={2} truncated={false} baseTitle="Painel Principal" />);

    expect(document.title).toBe("(2) Painel Principal | SentinelPay");
    expect(link.getAttribute("href")).toBe("/favicon-alert.svg");
  });

  it("marks truncated counts and returns to normal at zero", () => {
    const { rerender } = render(
      <DocumentAlerts count={500} truncated baseTitle="Painel Principal" />,
    );

    expect(document.title).toBe("(500+) Painel Principal | SentinelPay");

    rerender(<DocumentAlerts count={0} truncated={false} baseTitle="Painel Principal" />);

    expect(document.title).toBe("Painel Principal | SentinelPay");
    expect(link.getAttribute("href")).toBe("/icon.svg");
  });
});
