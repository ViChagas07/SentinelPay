import { describe, expect, it } from "vitest";

import { RISK_BAND_LAYOUT, bandForScore, clampScore, scoreToPercent } from "./ruler";

describe("risk ruler geometry", () => {
  it("keeps the three bands contiguous and proportional", () => {
    expect(RISK_BAND_LAYOUT.map((band) => band.width)).toEqual([40, 30, 30]);
    expect(RISK_BAND_LAYOUT[0]?.start).toBe(0);
    expect(RISK_BAND_LAYOUT[1]?.start).toBe(40);
    expect(RISK_BAND_LAYOUT[2]?.start).toBe(70);
    expect(RISK_BAND_LAYOUT[2]?.end).toBe(100);
  });

  it("positions scores from 0 to 100 without classifying them", () => {
    expect(scoreToPercent(0)).toBe(0);
    expect(scoreToPercent(39)).toBe(39);
    expect(scoreToPercent(54)).toBe(54);
    expect(scoreToPercent(100)).toBe(100);
  });

  it("clamps out-of-range and invalid scores for layout purposes", () => {
    expect(clampScore(-10)).toBe(0);
    expect(clampScore(140)).toBe(100);
    expect(clampScore(Number.NaN)).toBe(0);
    expect(clampScore(Number.POSITIVE_INFINITY)).toBe(0);
  });

  it("maps scores to the same bands used by the backend", () => {
    expect(bandForScore(0)).toBe("low");
    expect(bandForScore(39)).toBe("low");
    expect(bandForScore(40)).toBe("attention");
    expect(bandForScore(69)).toBe("attention");
    expect(bandForScore(70)).toBe("high");
    expect(bandForScore(100)).toBe("high");
  });

  it("clamps out-of-range values before mapping bands", () => {
    expect(bandForScore(-20)).toBe("low");
    expect(bandForScore(140)).toBe("high");
    expect(bandForScore(Number.NaN)).toBe("low");
  });
});
