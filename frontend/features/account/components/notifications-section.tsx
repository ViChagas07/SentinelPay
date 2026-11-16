"use client";

import { ArrowUpRight, Bell } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";

export function NotificationsSection() {
  const { t } = useI18n();

  return (
    <section aria-labelledby="account-notifications-title">
      <h2
        id="account-notifications-title"
        className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
      >
        {t("account.notifications.title")}
      </h2>
      <p className="mt-1 max-w-2xl text-sm leading-relaxed text-foreground/70">
        {t("account.notifications.description")}
      </p>

      <div className="mt-5 rounded-[6px] border border-border bg-card p-5 sm:p-6">
        <div className="flex flex-wrap items-start gap-4">
          <span className="grid size-11 shrink-0 place-items-center rounded-full border border-border bg-surface-elevated">
            <Bell className="size-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h3 className="text-sm font-medium">{t("account.notifications.channels")}</h3>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-foreground/70">
              {t("account.notifications.channelsDescription")}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm">
                <Link href="/notificacoes#canais">
                  {t("account.notifications.manage")}
                  <ArrowUpRight aria-hidden="true" />
                </Link>
              </Button>
              <Button asChild variant="ghost" size="sm">
                <Link href="/notificacoes">{t("account.notifications.center")}</Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
