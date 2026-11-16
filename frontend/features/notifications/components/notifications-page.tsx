"use client";

import { Bell, Info } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import type { NotificationType } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";
import { NOTIFICATIONS_POLL_MS } from "@/lib/notifications/feed";

import { ChannelsPanel } from "./channels-panel";
import { NOTIFICATION_TYPE_KEYS, NotificationRow } from "./notification-row";
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotificationFeed,
  useUnreadCount,
} from "../hooks/use-notifications";

type ReadFilter = "all" | "unread";

function FeedSkeleton() {
  const { t } = useI18n();

  return (
    <div className="space-y-2 p-4" role="status" aria-live="polite">
      <span className="sr-only">{t("notifications.list.loading")}</span>
      {[0, 1, 2, 3].map((index) => (
        <div
          key={index}
          className="space-y-2 border-b border-border pb-3 last:border-b-0 last:pb-0"
        >
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-3 w-2/3" />
          <Skeleton className="h-3 w-1/4" />
        </div>
      ))}
    </div>
  );
}

export function NotificationsPage() {
  const { t } = useI18n();
  const typeLabelId = useId();
  const readLabelId = useId();
  const channelLabelId = useId();
  const channelNoteId = useId();
  const [typeFilter, setTypeFilter] = useState<NotificationType | "all">("all");
  const [readFilter, setReadFilter] = useState<ReadFilter>("all");

  const feedQuery = useNotificationFeed({
    type: typeFilter === "all" ? undefined : typeFilter,
    unread: readFilter === "unread" ? true : undefined,
  });
  const unreadQuery = useUnreadCount({ refetchInterval: NOTIFICATIONS_POLL_MS });
  const markAll = useMarkAllNotificationsRead();
  const markRead = useMarkNotificationRead();

  const items = useMemo(
    () => feedQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [feedQuery.data],
  );
  const unread = unreadQuery.data?.unread ?? null;
  const filtered = typeFilter !== "all" || readFilter === "unread";
  const firstLoad = feedQuery.isPending && !feedQuery.data;
  const error = feedQuery.isError && !feedQuery.data;

  function clearFilters(): void {
    setTypeFilter("all");
    setReadFilter("all");
  }

  function handleMarkRead(notificationId: string): void {
    markRead.mutate(notificationId, {
      onError: () => toast.error(t("notifications.list.markReadError")),
    });
  }

  function handleMarkAll(): void {
    markAll.mutate(undefined, {
      onSuccess: () => toast.success(t("notifications.markAllSuccess")),
      onError: () => toast.error(t("notifications.markAllError")),
    });
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <header className="border-b border-border pb-6">
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
          {t("notifications.eyebrow")}
        </p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <h1 className="font-serif text-4xl leading-tight tracking-tight sm:text-5xl">
              {t("notifications.title")}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              {t("notifications.description")}
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={handleMarkAll}
            disabled={unread === null || unread === 0 || markAll.isPending}
          >
            <Bell aria-hidden="true" />
            {t("notifications.markAll")}
          </Button>
        </div>
      </header>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section aria-labelledby="notifications-recent-title" className="min-w-0">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2
                id="notifications-recent-title"
                className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
              >
                {t("notifications.list.title")}
              </h2>
              <p aria-live="polite" className="mt-1 text-xs text-muted-foreground">
                {unread === null
                  ? t("library.countPending")
                  : unread === 0
                    ? t("notifications.unreadCountZero")
                    : t("notifications.unreadCount", { count: unread })}
              </p>
            </div>
            <p className="text-[0.65rem] text-muted-foreground">
              {t("notifications.list.polling")}
            </p>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="space-y-1.5">
              <span
                id={typeLabelId}
                className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
              >
                {t("notifications.filters.type")}
              </span>
              <Select
                value={typeFilter}
                onValueChange={(value) =>
                  setTypeFilter(value === "all" ? "all" : (value as NotificationType))
                }
              >
                <SelectTrigger aria-labelledby={typeLabelId}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("notifications.filters.typeAll")}</SelectItem>
                  {(Object.keys(NOTIFICATION_TYPE_KEYS) as NotificationType[]).map((type) => (
                    <SelectItem key={type} value={type}>
                      {t(NOTIFICATION_TYPE_KEYS[type])}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <span
                id={readLabelId}
                className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
              >
                {t("notifications.filters.read")}
              </span>
              <Select
                value={readFilter}
                onValueChange={(value) => setReadFilter(value as ReadFilter)}
              >
                <SelectTrigger aria-labelledby={readLabelId}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("notifications.filters.readAll")}</SelectItem>
                  <SelectItem value="unread">{t("notifications.filters.readUnread")}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <span
                id={channelLabelId}
                className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
              >
                {t("notifications.filters.channel")}
              </span>
              <Select disabled value="all">
                <SelectTrigger aria-labelledby={channelLabelId} aria-describedby={channelNoteId}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("notifications.filters.channelAll")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <p
            id={channelNoteId}
            className="mt-2 flex items-start gap-2 text-[0.65rem] leading-relaxed text-muted-foreground"
          >
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            <span>{t("notifications.filters.channelUnavailable")}</span>
          </p>

          <div className="mt-4 overflow-hidden rounded-[6px] border border-border bg-card">
            {firstLoad ? (
              <FeedSkeleton />
            ) : error ? (
              <div role="alert" className="space-y-3 p-5">
                <p className="font-serif text-xl leading-tight tracking-tight">
                  {t("notifications.list.errorTitle")}
                </p>
                <p className="text-sm text-muted-foreground">
                  {t("notifications.list.errorDescription")}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void feedQuery.refetch()}
                >
                  {t("notifications.list.retry")}
                </Button>
              </div>
            ) : items.length === 0 ? (
              <div className="p-5">
                <EmptyState
                  className="border-t-0 pt-0"
                  title={t(
                    filtered
                      ? "notifications.list.emptyFilteredTitle"
                      : "notifications.list.emptyTitle",
                  )}
                  description={t(
                    filtered
                      ? "notifications.list.emptyFilteredDescription"
                      : "notifications.list.emptyDescription",
                  )}
                  action={
                    filtered
                      ? {
                          label: t("notifications.list.clearFilters"),
                          onClick: clearFilters,
                        }
                      : undefined
                  }
                />
              </div>
            ) : (
              <ul aria-label={t("notifications.list.title")}>
                {items.map((notification) => (
                  <NotificationRow
                    key={notification.id}
                    notification={notification}
                    onMarkRead={handleMarkRead}
                  />
                ))}
              </ul>
            )}
          </div>

          {feedQuery.hasNextPage ? (
            <div className="mt-3 flex justify-center">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void feedQuery.fetchNextPage()}
                disabled={feedQuery.isFetchingNextPage}
              >
                {feedQuery.isFetchingNextPage
                  ? t("notifications.list.loadingMore")
                  : t("notifications.list.loadMore")}
              </Button>
            </div>
          ) : null}
        </section>

        <ChannelsPanel />
      </div>
    </div>
  );
}
