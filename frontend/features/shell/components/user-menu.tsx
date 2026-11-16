"use client";

import { ChevronRight, Languages, LogOut, Monitor, Moon, Sun, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { UserProfile } from "@/lib/api/schemas";
import { LOCALES, isLocale, type Locale } from "@/lib/i18n";
import { getInitials } from "@/lib/shell/initials";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import { THEME_MODES, isThemeMode, type ThemeMode } from "@/lib/theme/constants";
import { useTheme } from "@/lib/theme/provider";
import { cn } from "@/lib/utils";

import { UserAvatar } from "./user-avatar";

const LOCALE_LABEL_KEYS: Record<Locale, TranslationKey> = {
  pt: "language.pt",
  es: "language.es",
  en: "language.en",
};

const THEME_LABEL_KEYS: Record<ThemeMode, TranslationKey> = {
  system: "theme.system",
  light: "theme.light",
  dark: "theme.dark",
};

const THEME_ICONS = {
  system: Monitor,
  light: Sun,
  dark: Moon,
} as const;

export type UserMenuProps = {
  user: UserProfile;
  variant: "sidebar" | "header";
  collapsed?: boolean;
  onLogout: () => void;
  loggingOut?: boolean;
};

export function UserMenu({
  user,
  variant,
  collapsed = false,
  onLogout,
  loggingOut = false,
}: UserMenuProps) {
  const { t, locale, setLocale } = useI18n();
  const { mode, setMode } = useTheme();
  const router = useRouter();
  const CurrentThemeIcon = THEME_ICONS[mode];
  const sidebar = variant === "sidebar";
  const menuLabel = `${user.name ?? user.email}, ${t("shell.user.menu")}, ${getInitials(
    user.name,
    user.email,
  )}`;

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        {sidebar ? (
          <button
            type="button"
            aria-label={collapsed ? menuLabel : undefined}
            className={cn(
              "flex w-full items-center gap-2 rounded-[6px] px-2 py-2 text-left text-on-petrol transition-colors hover:bg-petrol-active",
              collapsed && "justify-center",
            )}
          >
            <UserAvatar name={user.name} email={user.email} />
            {collapsed ? null : (
              <>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-xs font-medium">
                    {user.name ?? user.email}
                  </span>
                  <span className="block truncate text-[0.65rem] text-on-petrol/75">
                    {user.email}
                  </span>
                </span>
                <ChevronRight className="size-3 shrink-0 rotate-90" aria-hidden="true" />
              </>
            )}
          </button>
        ) : (
          <button
            type="button"
            aria-label={menuLabel}
            className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <UserAvatar name={user.name} email={user.email} />
          </button>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align={sidebar ? "start" : "end"}
        side={sidebar ? "top" : "bottom"}
        className="z-[60] w-64"
      >
        <DropdownMenuLabel className="font-normal">
          <span className="block truncate text-sm font-medium">{user.name ?? user.email}</span>
          <span className="block truncate text-xs font-normal text-muted-foreground">
            {user.email}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/account")}>
          <UserRound aria-hidden="true" />
          {t("shell.user.account")}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <Languages aria-hidden="true" />
            {t("shell.user.language")}
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="z-[60]">
            <DropdownMenuRadioGroup
              value={locale}
              onValueChange={(value) => {
                if (isLocale(value)) {
                  setLocale(value);
                }
              }}
            >
              {LOCALES.map((option) => (
                <DropdownMenuRadioItem key={option} value={option}>
                  {t(LOCALE_LABEL_KEYS[option])}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <CurrentThemeIcon aria-hidden="true" />
            {t("shell.user.theme")}
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="z-[60]">
            <DropdownMenuRadioGroup
              value={mode}
              onValueChange={(value) => {
                if (isThemeMode(value)) {
                  setMode(value);
                }
              }}
            >
              {THEME_MODES.map((option) => (
                <DropdownMenuRadioItem key={option} value={option}>
                  {t(THEME_LABEL_KEYS[option])}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={loggingOut} onSelect={onLogout}>
          <LogOut aria-hidden="true" />
          {loggingOut ? t("auth.logout.loading") : t("shell.user.logout")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
