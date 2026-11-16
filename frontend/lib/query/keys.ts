type ListParams = Readonly<Record<string, unknown>>;

export const queryKeys = {
  auth: {
    refresh: ["auth", "refresh"] as const,
  },
  users: {
    me: ["users", "me"] as const,
  },
  analyses: {
    all: ["analyses"] as const,
    list: (params: ListParams) => ["analyses", "list", params] as const,
    library: ["analyses", "library"] as const,
    detail: (analysisId: string) => ["analyses", "detail", analysisId] as const,
  },
  dashboard: {
    analyses: (periodDays: number) => ["dashboard", "analyses", periodDays] as const,
  },
  documents: {
    url: (documentId: string) => ["documents", "url", documentId] as const,
  },
  payables: {
    all: ["payables"] as const,
    list: (params: ListParams) => ["payables", "list", params] as const,
    sample: (statuses: readonly string[] | null) => ["payables", "sample", statuses] as const,
    reminderPreferences: ["payables", "reminder-preferences"] as const,
  },
  notifications: {
    all: ["notifications"] as const,
    list: (params: ListParams) => ["notifications", "list", params] as const,
    feed: (params: ListParams) => ["notifications", "feed", params] as const,
    unreadCount: ["notifications", "unread-count"] as const,
    preferences: ["notifications", "preferences"] as const,
  },
  shell: {
    highRiskAlerts: ["shell", "high-risk-alerts"] as const,
  },
} as const;
