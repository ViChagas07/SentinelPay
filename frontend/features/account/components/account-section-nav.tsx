"use client";

import {
  Bell,
  Building2,
  Lock,
  ShieldCheck,
  SlidersHorizontal,
  TriangleAlert,
  UserRound,
} from "lucide-react";
import { useRef, type KeyboardEvent } from "react";

import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

export const ACCOUNT_SECTIONS = [
  "profile",
  "organization",
  "preferences",
  "notifications",
  "security",
  "privacy",
  "danger",
] as const;

export type AccountSection = (typeof ACCOUNT_SECTIONS)[number];

const SECTION_META: Record<AccountSection, { labelKey: TranslationKey; icon: typeof UserRound }> = {
  profile: { labelKey: "account.section.profile", icon: UserRound },
  organization: { labelKey: "account.section.organization", icon: Building2 },
  preferences: { labelKey: "account.section.preferences", icon: SlidersHorizontal },
  notifications: { labelKey: "account.section.notifications", icon: Bell },
  security: { labelKey: "account.section.security", icon: ShieldCheck },
  privacy: { labelKey: "account.section.privacy", icon: Lock },
  danger: { labelKey: "account.section.danger", icon: TriangleAlert },
};

export type AccountSectionNavProps = {
  active: AccountSection;
  onChange: (section: AccountSection) => void;
};

export function AccountSectionNav({ active, onChange }: AccountSectionNavProps) {
  const { t } = useI18n();
  const refs = useRef<Partial<Record<AccountSection, HTMLButtonElement | null>>>({});

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    const index = ACCOUNT_SECTIONS.indexOf(active);
    let nextIndex: number | null = null;

    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      nextIndex = (index + 1) % ACCOUNT_SECTIONS.length;
    } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      nextIndex = (index - 1 + ACCOUNT_SECTIONS.length) % ACCOUNT_SECTIONS.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = ACCOUNT_SECTIONS.length - 1;
    }

    if (nextIndex === null) {
      return;
    }

    event.preventDefault();
    const next = ACCOUNT_SECTIONS[nextIndex];

    if (!next) {
      return;
    }

    onChange(next);
    refs.current[next]?.focus();
  }

  return (
    <div className="min-w-0 md:sticky md:top-20 md:self-start">
      <div
        role="tablist"
        aria-label={t("account.section.navigation")}
        onKeyDown={handleKeyDown}
        className="-mx-4 flex gap-1 overflow-x-auto px-4 pb-1 md:mx-0 md:flex-col md:overflow-visible md:rounded-[6px] md:border md:border-border md:bg-card md:p-1 md:px-1 md:pb-1"
      >
        {ACCOUNT_SECTIONS.map((section) => {
          const meta = SECTION_META[section];
          const Icon = meta.icon;
          const selected = section === active;

          return (
            <button
              key={section}
              ref={(element) => {
                refs.current[section] = element;
              }}
              type="button"
              role="tab"
              id={`account-tab-${section}`}
              aria-selected={selected}
              aria-controls={selected ? `account-panel-${section}` : undefined}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(section)}
              className={cn(
                "inline-flex min-w-max items-center gap-2 rounded-[6px] px-3 py-2 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background md:w-full md:min-w-0",
                selected
                  ? "bg-surface-elevated text-foreground shadow-sm ring-1 ring-border"
                  : "text-foreground/70 hover:bg-surface-elevated/60 hover:text-foreground",
                section === "danger" && selected && "ring-risk-high/40",
              )}
            >
              <Icon
                className={cn("size-4 shrink-0", section === "danger" && "text-risk-high")}
                aria-hidden="true"
              />
              <span className="whitespace-nowrap">{t(meta.labelKey)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
