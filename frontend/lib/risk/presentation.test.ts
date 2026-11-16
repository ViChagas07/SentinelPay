import { AlertTriangle, OctagonAlert, ShieldCheck } from "lucide-react";
import { describe, expect, it } from "vitest";

import { getRiskPresentation } from "./presentation";

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
