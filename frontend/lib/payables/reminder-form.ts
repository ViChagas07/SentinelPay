import { z } from "zod";

import type { ReminderPreference, ReminderPreferenceUpdate } from "@/lib/api/schemas";

const TIME_PATTERN = /^([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?$/;

export type ReminderFormValues = {
  offsetsDays: number[];
  localTime: string;
};

export function parseOffsetsInput(input: string): number[] | null {
  const parts = input
    .split(/[,;\s]+/)
    .map((part) => part.trim())
    .filter((part) => part.length > 0);

  if (parts.length === 0 || parts.length > 31) {
    return null;
  }

  const values = parts.map((part) => Number(part));

  if (
    values.some((value) => !Number.isInteger(value) || value < 0 || value > 30) ||
    new Set(values).size !== values.length
  ) {
    return null;
  }

  return values;
}

export const reminderFormSchema = z
  .object({
    offsetsInput: z.string(),
    localTime: z.string(),
  })
  .superRefine((value, context) => {
    if (parseOffsetsInput(value.offsetsInput) === null) {
      context.addIssue({
        code: "custom",
        path: ["offsetsInput"],
        message: "offsets",
      });
    }

    const match = TIME_PATTERN.exec(value.localTime.trim());

    if (!match) {
      context.addIssue({
        code: "custom",
        path: ["localTime"],
        message: "time",
      });
    }
  })
  .transform<ReminderFormValues>((value) => {
    const offsetsDays = parseOffsetsInput(value.offsetsInput) ?? [];
    const match = TIME_PATTERN.exec(value.localTime.trim());
    const localTime = match ? `${match[1]}:${match[2]}:${match[3] ?? "00"}` : "09:00:00";

    return { offsetsDays, localTime };
  });

export function reminderPreferenceToForm(preference: ReminderPreference): {
  offsetsInput: string;
  localTime: string;
} {
  return {
    offsetsInput: preference.offsets_days.join(", "),
    localTime: preference.local_time.slice(0, 5),
  };
}

export function reminderFormToUpdate(values: ReminderFormValues): ReminderPreferenceUpdate {
  return {
    offsets_days: [...values.offsetsDays].sort((left, right) => right - left),
    local_time: values.localTime,
    channels: ["in_app"],
  };
}
