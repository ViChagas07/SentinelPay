import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/i18n/provider", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) =>
      params?.plan ? `${key}:${params.plan}` : key,
  }),
}));

import { OrganizationSwitcher } from "./organization-switcher";

describe("OrganizationSwitcher", () => {
  it("renders nothing when the API returns no organization", () => {
    const { container } = render(<OrganizationSwitcher organizations={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a single organization without a dropdown", () => {
    render(
      <OrganizationSwitcher
        organizations={[{ id: "o1", name: "Organização única", plan: "pro" }]}
      />,
    );

    expect(screen.getByText("Organização única")).toBeInTheDocument();
    expect(screen.getByText(/shell.sidebar.organization.plan:pro/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("offers a dropdown when there are multiple organizations", () => {
    render(
      <OrganizationSwitcher
        organizations={[
          { id: "o1", name: "Primeira", plan: "pro" },
          { id: "o2", name: "Segunda", plan: "free" },
        ]}
      />,
    );

    expect(screen.getByRole("button")).toBeInTheDocument();
    expect(screen.getByText("Primeira")).toBeInTheDocument();
  });
});
