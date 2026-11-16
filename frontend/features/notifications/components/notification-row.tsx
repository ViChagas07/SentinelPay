"use client";

import { ArrowUpRight, Circle } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { NotificationItem, NotificationType } from "@/lib/api/schemas";
import { formatRelativeTime } from "@/lib/dashboard/date";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import {
  notificationBand,
  notificationChannel,
  notificationKind,
  notificationScore,
  notificationTarget,
  type NotificationChannel,
} from "@/lib/notifications/feed";
import { cn } from "@/lib/utils";

export const NOTIFICATION_TYPE_KEYS: Record<NotificationType, TranslationKey> = {
  analysis_completed: "notifications.type.analysis_completed",
  high_risk_detected: "notifications.type.high_risk_detected",
  receipt_analyzed: "notifications.type.receipt_analyzed",
  payable_due_soon: "notifications.type.payable_due_soon",
  payable_due_today: "notifications.type.payable_due_today",
  payable_overdue: "notifications.type.payable_overdue",
  payable_due_reminder: "notifications.type.payable_due_reminder",
};

const KIND_KEYS = {
  boleto: "verification.type.boleto",
  payslip: "verification.type.payslip",
  receipt: "verification.type.receipt",
} as const;

const BAND_KEYS = {
  low: "risk.low",
  attention: "risk.attention",
  high: "risk.high",
} as const;

const CHANNEL_KEYS: Record<NotificationChannel, TranslationKey> = {
  email: "notifications.channel.email",
  sms: "notifications.channel.sms",
  whatsapp: "notifications.channel.whatsapp",
  in_app: "notifications.channel.in_app",
};

function notificationBody(
  notification: NotificationItem,
  t: (key: TranslationKey, params?: Record<string, string | number>) => string,
  formatDate: (value: Date | string | number, options?: Intl.DateTimeFormatOptions) => string,
): string | null {
  const payload = notification.payload;
  const kind = notificationKind(payload);
  const score = notificationScore(payload);
  const band = notificationBand(payload);
  const dueDate = payload.due_date
    ? formatDate(`${payload.due_date}T12:00:00Z`, { dateStyle: "medium" })
    : null;

  if (
    notification.type === "analysis_completed" ||
    notification.type === "high_risk_detected" ||
    notification.type === "receipt_analyzed"
  ) {
    if (kind && score !== null && band !== null) {
      return t("notifications.body.analysis", {
        kind: t(KIND_KEYS[kind]),
        score,
        band: t(BAND_KEYS[band]),
      });
    }

    return kind ? t("notifications.body.analysisNoScore", { kind: t(KIND_KEYS[kind]) }) : null;
  }

  if (notification.type === "payable_due_today") {
    return dueDate ? t("notifications.body.payableToday", { date: dueDate }) : null;
  }

  if (notification.type === "payable_overdue") {
    return dueDate ? t("notifications.body.payableOverdue", { date: dueDate }) : null;
  }

  const offsetDays = Number(payload.offset_days);

  if (dueDate && Number.isInteger(offsetDays) && offsetDays >= 0) {
    return t("notifications.body.payableOffset", { date: dueDate, days: offsetDays });
  }

  return dueDate ? t("notifications.body.payable", { date: dueDate }) : null;
}

export type NotificationRowProps = {
  notification: NotificationItem;
  onMarkRead: (notificationId: string) => void;
};

export function NotificationRow({ notification, onMarkRead }: NotificationRowProps) {
  const { t, locale, formatDate } = useI18n();
  const target = notificationTarget(notification.payload);
  const channel = notificationChannel(notification.payload);
  const body = notificationBody(notification, t, formatDate);
  const unread = !notification.read;
  const created = notification.created_at
    ? formatRelativeTime(notification.created_at, locale)
    : null;

  function markRead(): void {
    if (unread) {
      onMarkRead(notification.id);
    }
  }

  return (
    <li
      className={cn(
        "border-b border-border p-4 transition-colors last:border-b-0",
        unread ? "bg-surface-elevated/40" : "bg-transparent",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className={cn(
            "mt-1.5 size-2 shrink-0 rounded-full",
            unread ? "bg-primary" : "bg-transparent",
          )}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              {target ? (
                <Link
                  href={target.href}
                  onClick={markRead}
                  className="inline-flex items-start gap-1 rounded-[4px] text-sm font-medium underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  {t(NOTIFICATION_TYPE_KEYS[notification.type])}
                  <ArrowUpRight className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                </Link>
              ) : (
                <p className="text-sm font-medium">
                  {t(NOTIFICATION_TYPE_KEYS[notification.type])}
                </p>
              )}
              {body ? (
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{body}</p>
              ) : null}
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              {unread ? (
                <Badge variant="outline" className="gap-1">
                  <Circle className="size-1.5 fill-current" aria-hidden="true" />
                  {t("notifications.list.unread")}
                </Badge>
              ) : null}
              {channel ? (
                <Badge variant="secondary" className="text-[0.6rem]">
                  {t(CHANNEL_KEYS[channel])}
                </Badge>
              ) : null}
            </div>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.65rem] text-muted-foreground">
            {created ? (
              <time dateTime={notification.created_at ?? undefined}>{created}</time>
            ) : null}
            {notification.read && notification.read_at ? (
              <span>
                {t("notifications.list.readAt", {
                  date: formatDate(notification.read_at, {
                    dateStyle: "short",
                    timeStyle: "short",
                  }),
                })}
              </span>
            ) : null}
            {target ? (
              <Link
                href={target.href}
                onClick={markRead}
                className="inline-flex items-center gap-1 rounded-[4px] underline underline-offset-4 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                {t(
                  target.kind === "analysis"
                    ? "notifications.list.openAnalysis"
                    : "notifications.list.openPayable",
                )}
                <ArrowUpRight className="size-3" aria-hidden="true" />
              </Link>
            ) : (
              <span>{t("notifications.list.noTarget")}</span>
            )}
            {unread ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-[0.65rem]"
                onClick={() => onMarkRead(notification.id)}
              >
                {t("notifications.list.markRead")}
              </Button>
            ) : null}
          </div>
        </div>
      </div>
    </li>
  );
}
