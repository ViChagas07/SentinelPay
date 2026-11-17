import { API_V1_PREFIX } from "./config";

export type PayableAction = "confirm" | "pay" | "dismiss";

function withId(base: string, id: string, suffix = ""): string {
  return `${base}/${encodeURIComponent(id)}${suffix}`;
}

export const endpoints = {
  auth: {
    googleLogin: `${API_V1_PREFIX}/auth/google/login`,
    refresh: `${API_V1_PREFIX}/auth/refresh`,
    logout: `${API_V1_PREFIX}/auth/logout`,
  },
  users: {
    me: `${API_V1_PREFIX}/users/me`,
  },
  analyses: {
    list: `${API_V1_PREFIX}/analyses`,
    create: `${API_V1_PREFIX}/analyses`,
    detail: (analysisId: string) => withId(`${API_V1_PREFIX}/analyses`, analysisId),
    events: (analysisId: string) => withId(`${API_V1_PREFIX}/analyses`, analysisId, "/events"),
    cancel: (analysisId: string) => withId(`${API_V1_PREFIX}/analyses`, analysisId, "/cancel"),
  },
  documents: {
    upload: `${API_V1_PREFIX}/documents/upload`,
    url: (documentId: string) => withId(`${API_V1_PREFIX}/documents`, documentId, "/url"),
  },
  payables: {
    list: `${API_V1_PREFIX}/payables`,
    reminderPreferences: `${API_V1_PREFIX}/payables/reminder-preferences`,
    action: (payableId: string, action: PayableAction) =>
      withId(`${API_V1_PREFIX}/payables`, payableId, `/${action}`),
    dueDate: (payableId: string) => withId(`${API_V1_PREFIX}/payables`, payableId, "/due-date"),
  },
  notifications: {
    list: `${API_V1_PREFIX}/notifications`,
    unreadCount: `${API_V1_PREFIX}/notifications/unread-count`,
    readAll: `${API_V1_PREFIX}/notifications/read-all`,
    detail: (notificationId: string) => withId(`${API_V1_PREFIX}/notifications`, notificationId),
    read: (notificationId: string) =>
      withId(`${API_V1_PREFIX}/notifications`, notificationId, "/read"),
    remove: (notificationId: string) => withId(`${API_V1_PREFIX}/notifications`, notificationId),
  },
  notificationPreferences: `${API_V1_PREFIX}/notification-preferences`,
} as const;
