import { z } from "zod";

import { cursorPageSchema, isoDateTimeSchema, uuidSchema } from "./common";

export const notificationTypeSchema = z.enum([
  "analysis_completed",
  "high_risk_detected",
  "receipt_analyzed",
  "payable_due_soon",
  "payable_due_today",
  "payable_overdue",
  "payable_due_reminder",
]);

export const notificationSchema = z.object({
  id: uuidSchema,
  type: notificationTypeSchema,
  payload: z.record(z.string(), z.string()),
  read: z.boolean(),
  read_at: isoDateTimeSchema.nullable(),
  created_at: isoDateTimeSchema.nullable(),
});

export const notificationListSchema = cursorPageSchema(notificationSchema);

export const unreadCountSchema = z.object({
  unread: z.number().int().nonnegative(),
});

export const readAllSchema = z.object({
  updated: z.number().int().nonnegative(),
});

export const deliveryChannelSchema = z.enum(["email", "sms", "whatsapp"]);

export const channelPreferenceSchema = z.object({
  channel: deliveryChannelSchema,
  enabled: z.boolean(),
  destination: z.string().nullable(),
  consented_at: isoDateTimeSchema.nullable(),
});

export const notificationPreferencesSchema = z.object({
  locale: z.string(),
  timezone: z.string(),
  channels: z.array(channelPreferenceSchema),
});

export const channelPreferenceUpdateSchema = z.object({
  enabled: z.boolean(),
  destination: z.string().nullable().optional(),
  consent: z.boolean(),
});

export const notificationPreferencesUpdateSchema = z.object({
  locale: z.string().optional(),
  email: channelPreferenceUpdateSchema.optional(),
  sms: channelPreferenceUpdateSchema.optional(),
  whatsapp: channelPreferenceUpdateSchema.optional(),
});

export type NotificationType = z.infer<typeof notificationTypeSchema>;
export type NotificationItem = z.infer<typeof notificationSchema>;
export type NotificationList = z.infer<typeof notificationListSchema>;
export type UnreadCount = z.infer<typeof unreadCountSchema>;
export type ReadAll = z.infer<typeof readAllSchema>;
export type DeliveryChannel = z.infer<typeof deliveryChannelSchema>;
export type ChannelPreference = z.infer<typeof channelPreferenceSchema>;
export type NotificationPreferences = z.infer<typeof notificationPreferencesSchema>;
export type ChannelPreferenceUpdate = z.infer<typeof channelPreferenceUpdateSchema>;
export type NotificationPreferencesUpdate = z.infer<typeof notificationPreferencesUpdateSchema>;
