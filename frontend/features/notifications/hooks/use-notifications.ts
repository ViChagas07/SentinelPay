"use client";

import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryKey,
} from "@tanstack/react-query";

import {
  apiFetch,
  endpoints,
  notificationListSchema,
  notificationPreferencesSchema,
  notificationPreferencesUpdateSchema,
  notificationSchema,
  readAllSchema,
  unreadCountSchema,
} from "@/lib/api";
import type {
  NotificationItem,
  NotificationList,
  NotificationPreferences,
  NotificationPreferencesUpdate,
  NotificationType,
  ReadAll,
  UnreadCount,
} from "@/lib/api/schemas";
import { NOTIFICATIONS_PAGE_SIZE, NOTIFICATIONS_POLL_MS } from "@/lib/notifications/feed";
import { queryKeys } from "@/lib/query/keys";

export type NotificationsFilters = {
  type?: NotificationType[];
  unread?: boolean;
  limit?: number;
  cursor?: string | null;
};

export type NotificationFeedFilters = {
  type?: NotificationType;
  unread?: boolean;
};

type NotificationSnapshot = {
  lists: [QueryKey, NotificationList | undefined][];
  feeds: [QueryKey, InfiniteData<NotificationList> | undefined][];
  unread: UnreadCount | undefined;
};

export function useNotifications(filters: NotificationsFilters = {}) {
  const normalizedParams = {
    type: filters.type ?? null,
    unread: filters.unread ?? null,
    limit: filters.limit ?? null,
    cursor: filters.cursor ?? null,
  };

  return useQuery({
    queryKey: queryKeys.notifications.list(normalizedParams),
    queryFn: () =>
      apiFetch<NotificationList>(endpoints.notifications.list, {
        schema: notificationListSchema,
        query: {
          type: normalizedParams.type ?? undefined,
          unread: normalizedParams.unread ?? undefined,
          limit: normalizedParams.limit ?? undefined,
          cursor: normalizedParams.cursor ?? undefined,
        },
      }),
    placeholderData: keepPreviousData,
  });
}

export function useNotificationFeed(filters: NotificationFeedFilters = {}) {
  const normalizedParams = {
    type: filters.type ?? null,
    unread: filters.unread ?? null,
  };

  return useInfiniteQuery({
    queryKey: queryKeys.notifications.feed(normalizedParams),
    queryFn: ({ pageParam }) =>
      apiFetch<NotificationList>(endpoints.notifications.list, {
        schema: notificationListSchema,
        query: {
          type: normalizedParams.type ? [normalizedParams.type] : undefined,
          unread: normalizedParams.unread ?? undefined,
          limit: NOTIFICATIONS_PAGE_SIZE,
          cursor: pageParam ?? undefined,
        },
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor,
    staleTime: 10_000,
    refetchInterval: NOTIFICATIONS_POLL_MS,
    refetchOnWindowFocus: true,
  });
}

export function useUnreadCount(options: { refetchInterval?: number } = {}) {
  return useQuery({
    queryKey: queryKeys.notifications.unreadCount,
    queryFn: () =>
      apiFetch<UnreadCount>(endpoints.notifications.unreadCount, {
        schema: unreadCountSchema,
      }),
    refetchInterval: options.refetchInterval,
    refetchOnWindowFocus: true,
  });
}

function mapNotificationList(
  data: NotificationList | undefined,
  notificationId: string,
  readAt: string,
): NotificationList | undefined {
  if (!data) {
    return data;
  }

  return {
    ...data,
    items: data.items.map((item) =>
      item.id === notificationId && !item.read ? { ...item, read: true, read_at: readAt } : item,
    ),
  };
}

function mapNotificationFeed(
  data: InfiniteData<NotificationList> | undefined,
  notificationId: string,
  readAt: string,
): InfiniteData<NotificationList> | undefined {
  if (!data) {
    return data;
  }

  return {
    ...data,
    pages: data.pages.map((page) => ({
      ...page,
      items: page.items.map((item) =>
        item.id === notificationId && !item.read ? { ...item, read: true, read_at: readAt } : item,
      ),
    })),
  };
}

function readAllInList(
  data: NotificationList | undefined,
  readAt: string,
): NotificationList | undefined {
  if (!data) {
    return data;
  }

  return {
    ...data,
    items: data.items.map((item) => (item.read ? item : { ...item, read: true, read_at: readAt })),
  };
}

function readAllInFeed(
  data: InfiniteData<NotificationList> | undefined,
  readAt: string,
): InfiniteData<NotificationList> | undefined {
  if (!data) {
    return data;
  }

  return {
    ...data,
    pages: data.pages.map((page) => ({
      ...page,
      items: page.items.map((item) =>
        item.read ? item : { ...item, read: true, read_at: readAt },
      ),
    })),
  };
}

function snapshotNotifications(
  queryClient: ReturnType<typeof useQueryClient>,
): NotificationSnapshot {
  return {
    lists: queryClient.getQueriesData<NotificationList>({
      queryKey: ["notifications", "list"],
    }),
    feeds: queryClient.getQueriesData<InfiniteData<NotificationList>>({
      queryKey: ["notifications", "feed"],
    }),
    unread: queryClient.getQueryData<UnreadCount>(queryKeys.notifications.unreadCount),
  };
}

function restoreNotifications(
  queryClient: ReturnType<typeof useQueryClient>,
  snapshot: NotificationSnapshot | undefined,
): void {
  if (!snapshot) {
    return;
  }

  for (const [key, data] of snapshot.lists) {
    queryClient.setQueryData(key, data);
  }

  for (const [key, data] of snapshot.feeds) {
    queryClient.setQueryData(key, data);
  }

  queryClient.setQueryData(queryKeys.notifications.unreadCount, snapshot.unread);
}

function invalidateNotificationLists(queryClient: ReturnType<typeof useQueryClient>): void {
  void queryClient.invalidateQueries({ queryKey: ["notifications", "list"] });
  void queryClient.invalidateQueries({ queryKey: ["notifications", "feed"] });
  void queryClient.invalidateQueries({ queryKey: queryKeys.notifications.unreadCount });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (notificationId: string) =>
      apiFetch<NotificationItem>(endpoints.notifications.read(notificationId), {
        method: "POST",
        schema: notificationSchema,
      }),
    onMutate: async (notificationId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.notifications.all });
      const snapshot = snapshotNotifications(queryClient);
      const wasUnread = [...snapshot.lists, ...snapshot.feeds].some(([, data]) => {
        if (!data) {
          return false;
        }

        const items = "pages" in data ? data.pages.flatMap((page) => page.items) : data.items;

        return items.some((item) => item.id === notificationId && !item.read);
      });
      const readAt = new Date().toISOString();

      queryClient.setQueriesData<NotificationList>(
        { queryKey: ["notifications", "list"] },
        (data) => mapNotificationList(data, notificationId, readAt),
      );
      queryClient.setQueriesData<InfiniteData<NotificationList>>(
        { queryKey: ["notifications", "feed"] },
        (data) => mapNotificationFeed(data, notificationId, readAt),
      );

      if (wasUnread) {
        queryClient.setQueryData<UnreadCount>(queryKeys.notifications.unreadCount, (data) =>
          data ? { unread: Math.max(0, data.unread - 1) } : data,
        );
      }

      return snapshot;
    },
    onError: (_error, _notificationId, snapshot) => {
      restoreNotifications(queryClient, snapshot);
    },
    onSettled: () => {
      invalidateNotificationLists(queryClient);
    },
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      apiFetch<ReadAll>(endpoints.notifications.readAll, {
        method: "POST",
        schema: readAllSchema,
      }),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: queryKeys.notifications.all });
      const snapshot = snapshotNotifications(queryClient);
      const readAt = new Date().toISOString();

      queryClient.setQueriesData<NotificationList>(
        { queryKey: ["notifications", "list"] },
        (data) => readAllInList(data, readAt),
      );
      queryClient.setQueriesData<InfiniteData<NotificationList>>(
        { queryKey: ["notifications", "feed"] },
        (data) => readAllInFeed(data, readAt),
      );
      queryClient.setQueryData<UnreadCount>(queryKeys.notifications.unreadCount, { unread: 0 });

      return snapshot;
    },
    onError: (_error, _variables, snapshot) => {
      restoreNotifications(queryClient, snapshot);
    },
    onSettled: () => {
      invalidateNotificationLists(queryClient);
    },
  });
}

export function useDeleteNotification() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (notificationId: string) =>
      apiFetch<void>(endpoints.notifications.remove(notificationId), {
        method: "DELETE",
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all }),
  });
}

export function useNotificationPreferences() {
  return useQuery({
    queryKey: queryKeys.notifications.preferences,
    queryFn: () =>
      apiFetch<NotificationPreferences>(endpoints.notificationPreferences, {
        schema: notificationPreferencesSchema,
      }),
  });
}

export type UpdateNotificationPreferencesVariables = {
  input: NotificationPreferencesUpdate;
  optimistic: NotificationPreferences;
};

export function useUpdateNotificationPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ input }: UpdateNotificationPreferencesVariables) =>
      apiFetch<NotificationPreferences>(endpoints.notificationPreferences, {
        method: "PUT",
        schema: notificationPreferencesSchema,
        body: notificationPreferencesUpdateSchema.parse(input),
      }),
    onMutate: async ({ optimistic }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.notifications.preferences });
      const previous = queryClient.getQueryData<NotificationPreferences>(
        queryKeys.notifications.preferences,
      );
      queryClient.setQueryData(queryKeys.notifications.preferences, optimistic);
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.notifications.preferences, context.previous);
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.notifications.preferences, data);
    },
  });
}
