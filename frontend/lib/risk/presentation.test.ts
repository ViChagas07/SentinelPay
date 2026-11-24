import { AlertTriangle, OctagonAlert, ShieldCheck } from "lucide-react";
import { describe, expect, it } from "vitest";

import { getLandingRiskPalette, getRiskPresentation } from "./presentation";

describe("risk presentation", () => {
  it("maps low to its label, color and icon", () => {
    expect(getRiskPresentation("low")).toMatchObject({
      band: "low",
      labelKey: "risk.low",
      tone: "low",
      color: "var(--risk-low)",
      icon: ShieldCheck,
    });
  });

  it("maps attention to its label, color and icon", () => {
    expect(getRiskPresentation("attention")).toMatchObject({
      band: "attention",
      labelKey: "risk.attention",
      tone: "attention",
      color: "var(--risk-medium)",
      icon: AlertTriangle,
    });
  });

  it("maps high to its label, color and icon", () => {
    expect(getRiskPresentation("high")).toMatchObject({
      band: "high",
      labelKey: "risk.high",
      tone: "high",
      color: "var(--risk-high)",
      icon: OctagonAlert,
    });
  });
});

describe("landing risk palette", () => {
  it("uses green for low, yellow for attention and red for high", () => {
    expect(getLandingRiskPalette("low")).toEqual({
      color: "var(--risk-demo-low)",
      foreground: "var(--risk-demo-low-foreground)",
    });
    expect(getLandingRiskPalette("attention")).toEqual({
      color: "var(--risk-medium)",
      foreground: "var(--risk-medium-foreground)",
    });
    expect(getLandingRiskPalette("high")).toEqual({
      color: "var(--risk-high)",
      foreground: "var(--risk-high-foreground)",
    });
  });
});
