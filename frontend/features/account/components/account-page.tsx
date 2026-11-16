"use client";

import { useMemo, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { useSession } from "@/features/auth/hooks/use-session";
import { useI18n } from "@/lib/i18n/provider";
import { getPrivacyContactFromEnv } from "@/lib/site/privacy";

import { AccountSectionNav, type AccountSection } from "./account-section-nav";
import { DangerSection } from "./danger-section";
import { NotificationsSection } from "./notifications-section";
import { OrganizationSection } from "./organization-section";
import { PreferencesSection } from "./preferences-section";
import { PrivacySection } from "./privacy-section";
import { ProfileSection } from "./profile-section";
import { SecuritySection } from "./security-section";

export type AccountPageProps = {
  sessionExpiresAt: number | null;
};

function AccountSkeleton() {
  const { t } = useI18n();

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8" role="status">
      <span className="sr-only">{t("account.loading")}</span>
      <div className="space-y-3 border-b border-border pb-6">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-12 w-64 max-w-full" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      <div className="mt-8 grid gap-6 md:grid-cols-[13rem_minmax(0,1fr)]">
        <Skeleton className="h-12 w-full" />
        <div className="space-y-3">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    </div>
  );
}

export function AccountPage({ sessionExpiresAt }: AccountPageProps) {
  const { t } = useI18n();
  const { user, status } = useSession();
  const [active, setActive] = useState<AccountSection>("profile");
  const privacyContact = useMemo(() => getPrivacyContactFromEnv(), []);

  if (status === "loading") {
    return <AccountSkeleton />;
  }

  if (!user) {
    return <AccountSkeleton />;
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
      <header className="border-b border-border pb-6">
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-foreground/70">
          {t("account.eyebrow")}
        </p>
        <div className="mt-2">
          <h1 className="font-serif text-4xl leading-tight tracking-tight sm:text-5xl">
            {t("account.title")}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground/70">
            {t("account.description")}
          </p>
        </div>
      </header>

      <div className="mt-8 grid gap-6 md:grid-cols-[13rem_minmax(0,1fr)]">
        <AccountSectionNav active={active} onChange={setActive} />

        <div
          role="tabpanel"
          id={`account-panel-${active}`}
          aria-labelledby={`account-tab-${active}`}
          tabIndex={0}
          className="min-w-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-4 focus-visible:ring-offset-background"
        >
          {active === "profile" ? <ProfileSection user={user} /> : null}
          {active === "organization" ? <OrganizationSection user={user} /> : null}
          {active === "preferences" ? <PreferencesSection /> : null}
          {active === "notifications" ? <NotificationsSection /> : null}
          {active === "security" ? <SecuritySection sessionExpiresAt={sessionExpiresAt} /> : null}
          {active === "privacy" ? <PrivacySection contact={privacyContact} /> : null}
          {active === "danger" ? <DangerSection contact={privacyContact} /> : null}
        </div>
      </div>
    </div>
  );
}
