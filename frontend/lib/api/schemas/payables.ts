import { z } from "zod";

import { cursorPageSchema, isoDateSchema, isoDateTimeSchema, uuidSchema } from "./common";

export const payableStatusSchema = z.enum([
  "pending_confirmation",
  "pending",
  "paid",
  "overdue",
  "dismissed",
]);

export const payableSchema = z.object({
  id: uuidSchema,
  analysis_id: uuidSchema,
  description: z.string(),
  amount: z.string().regex(/^\d+\.\d{2}$/),
  due_date: isoDateSchema,
  status: payableStatusSchema,
  created_at: isoDateTimeSchema.nullable(),
  updated_at: isoDateTimeSchema.nullable(),
});

export const payableListSchema = cursorPageSchema(payableSchema);

const localTimeSchema = z.string().regex(/^\d{2}:\d{2}(:\d{2})?$/);

export const reminderChannelSchema = z.enum(["in_app"]);

export const reminderPreferenceSchema = z.object({
  offsets_days: z.array(z.number().int().min(0).max(30)),
  local_time: localTimeSchema,
  channels: z.array(reminderChannelSchema),
  timezone: z.string(),
});

export const reminderPreferenceUpdateSchema = z.object({
  offsets_days: z.array(z.number().int().min(0).max(30)).min(1),
  local_time: localTimeSchema,
  channels: z.array(reminderChannelSchema).min(1),
});

export const reschedulePayableRequestSchema = z.object({
  due_date: isoDateSchema,
});

export type PayableStatus = z.infer<typeof payableStatusSchema>;
export type Payable = z.infer<typeof payableSchema>;
export type PayableList = z.infer<typeof payableListSchema>;
export type ReminderPreference = z.infer<typeof reminderPreferenceSchema>;
export type ReminderPreferenceUpdate = z.infer<typeof reminderPreferenceUpdateSchema>;
export type ReschedulePayableRequest = z.infer<typeof reschedulePayableRequestSchema>;
