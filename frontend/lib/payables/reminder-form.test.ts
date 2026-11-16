import { describe, expect, it } from "vitest";

import {
  parseOffsetsInput,
  reminderFormSchema,
  reminderFormToUpdate,
  reminderPreferenceToForm,
} from "./reminder-form";

describe("parseOffsetsInput", () => {
  it("parses unique values between 0 and 30", () => {
    expect(parseOffsetsInput("3, 1, 0")).toEqual([3, 1, 0]);
    expect(parseOffsetsInput("7;15 30")).toEqual([7, 15, 30]);
  });

  it("rejects duplicates, out of range and empty input", () => {
    expect(parseOffsetsInput("3, 3")).toBeNull();
    expect(parseOffsetsInput("31")).toBeNull();
    expect(parseOffsetsInput("-1")).toBeNull();
    expect(parseOffsetsInput("")).toBeNull();
  });
});

describe("reminderFormSchema", () => {
  it("normalizes a valid form", () => {
    const result = reminderFormSchema.safeParse({ offsetsInput: "3, 1, 0", localTime: "09:30" });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual({ offsetsDays: [3, 1, 0], localTime: "09:30:00" });
    }
  });

  it("returns stable codes for translated messages", () => {
    const offsets = reminderFormSchema.safeParse({ offsetsInput: "31", localTime: "09:00" });
    const time = reminderFormSchema.safeParse({ offsetsInput: "3, 1", localTime: "25:00" });

    expect(offsets.success).toBe(false);
    expect(time.success).toBe(false);

    if (!offsets.success) {
      expect(offsets.error.issues[0]?.message).toBe("offsets");
    }

    if (!time.success) {
      expect(time.error.issues[0]?.message).toBe("time");
    }
  });
});

describe("reminderPreferenceToForm", () => {
  it("prepares the API preference for the form", () => {
    expect(
      reminderPreferenceToForm({
        offsets_days: [3, 1, 0],
        local_time: "09:00:00",
        channels: ["in_app"],
        timezone: "America/Sao_Paulo",
      }),
    ).toEqual({ offsetsInput: "3, 1, 0", localTime: "09:00" });
  });
});

describe("reminderFormToUpdate", () => {
  it("sorts the offsets and keeps the only supported channel", () => {
    expect(reminderFormToUpdate({ offsetsDays: [0, 7, 1], localTime: "08:15:00" })).toEqual({
      offsets_days: [7, 1, 0],
      local_time: "08:15:00",
      channels: ["in_app"],
    });
  });
});
