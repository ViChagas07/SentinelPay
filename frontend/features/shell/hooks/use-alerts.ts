"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch, endpoints, notificationListSchema, unreadCountSchema } from "@/lib/api";
import type { NotificationList, UnreadCount } from "@/lib/api/schemas";
import { queryKeys } from "@/lib/query/keys";
import {
  ALERT_PAGE_SIZE,
  MAX_ALERT_PAGES,
  countHighRiskAlerts,
  type HighRiskAlertCount,
} from "@/lib/shell/alerts";

export function useShellUnreadCount(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.notifications.unreadCount,
    queryFn: () =>
      apiFetch<UnreadCount>(endpoints.notifications.unreadCount, {
        schema: unreadCountSchema,
      }),
    enabled,
    retry: false,
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useHighRiskAlertCount(enabled: boolean) {
  return useQuery<HighRiskAlertCount>({
    queryKey: queryKeys.shell.highRiskAlerts,
    queryFn: () =>
      countHighRiskAlerts(async (cursor) => {
        const page = await apiFetch<NotificationList>(endpoints.notifications.list, {
          schema: notificationListSchema,
          query: {
            type: ["high_risk_detected"],
            unread: true,
            limit: ALERT_PAGE_SIZE,
            cursor: cursor ?? undefined,
          },
        });

        return page;
      }, MAX_ALERT_PAGES),
    enabled,
    retry: false,
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}
