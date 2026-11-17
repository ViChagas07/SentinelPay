"use client";

import { Gauge, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Logo, Wordmark } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { UserProfile } from "@/lib/api/schemas";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import { formatBadgeCount } from "@/lib/shell/alerts";
import type { ShellOrganization } from "@/lib/shell/organization";
import { SHELL_NAV_ITEMS, isShellPathActive } from "@/lib/shell/routes";
import { cn } from "@/lib/utils";

import { SHELL_NAV_ICONS } from "../nav-icons";
import { HelpCard } from "./help-card";
import { OrganizationSwitcher } from "./organization-switcher";
import { UserMenu } from "./user-menu";

type SidebarContentProps = {
  user: UserProfile;
  collapsed: boolean;
  unreadCount: number;
  organizations: readonly ShellOrganization[];
  supportUrl: string | null;
  onToggle?: () => void;
  onNavigate?: () => void;
  onLogout: () => void;
  loggingOut: boolean;
  instanceId: "desktop" | "mobile";
};

function SidebarNavItem({
  href,
  labelKey,
  collapsed,
  animateIndicator,
  instanceId,
  unreadCount,
  onNavigate,
}: {
  href: string;
  labelKey: TranslationKey;
  collapsed: boolean;
  animateIndicator: boolean;
  instanceId: "desktop" | "mobile";
  unreadCount: number;
  onNavigate?: () => void;
}) {
  const { t } = useI18n();
  const pathname = usePathname();
  const active = isShellPathActive(pathname, href);
  const label = t(labelKey);
  const Icon = SHELL_NAV_ICONS[href] ?? Gauge;
  const badge = href === "/notificacoes" ? formatBadgeCount(unreadCount) : null;
  const badgeLabel =
    unreadCount === 1
      ? t("shell.notifications.badge.one")
      : t("shell.notifications.badge", { count: unreadCount });

  const content = (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      onClick={onNavigate}
      className={cn(
        "relative flex items-center gap-3 rounded-[6px] px-3 py-2 text-sm transition-colors",
        collapsed && "justify-center px-0",
        active
          ? "text-on-petrol"
          : "text-on-petrol/80 hover:bg-petrol-active/50 hover:text-on-petrol",
      )}
    >
      {active ? (
        animateIndicator ? (
          <motion.span
            layoutId={`shell-sidebar-active-${instanceId}`}
            aria-hidden="true"
            className="absolute inset-0 rounded-[6px] bg-petrol-active"
            transition={{ type: "spring", stiffness: 420, damping: 34 }}
          />
        ) : (
          <span aria-hidden="true" className="absolute inset-0 rounded-[6px] bg-petrol-active" />
        )
      ) : null}
      <Icon className="relative z-10 size-4 shrink-0" aria-hidden="true" />
      <span className={cn("relative z-10 min-w-0 truncate", collapsed && "sr-only")}>{label}</span>
      {badge ? (
        <>
          <span
            aria-hidden="true"
            className={cn(
              "relative z-20 rounded-full bg-primary px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold leading-none text-primary-foreground",
              collapsed ? "absolute right-0.5 top-0.5" : "ml-auto",
            )}
          >
            {badge}
          </span>
          <span className="sr-only">{badgeLabel}</span>
        </>
      ) : null}
    </Link>
  );

  if (!collapsed) {
    return content;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{content}</TooltipTrigger>
      <TooltipContent side="right" align="center">
        {label}
        {badge ? ` (${badge})` : ""}
      </TooltipContent>
    </Tooltip>
  );
}

function SidebarContent({
  user,
  collapsed,
  unreadCount,
  organizations,
  supportUrl,
  onToggle,
  onNavigate,
  onLogout,
  loggingOut,
  instanceId,
}: SidebarContentProps) {
  const { t } = useI18n();
  const reduceMotion = useReducedMotion() ?? false;
  const animateIndicator = !reduceMotion;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-4",
          collapsed ? "flex-col justify-center" : "justify-between",
          !onToggle && "pr-12",
        )}
      >
        <Link href="/painel" aria-label={t("app.name")} className="rounded-[6px]">
          {collapsed ? (
            <Logo
              className="size-7"
              variant="compactLight"
              title={t("app.name")}
              priority
              sizes="28px"
            />
          ) : (
            <Wordmark
              name={t("app.name")}
              className="text-on-petrol"
              variant="compactLight"
              priority
            />
          )}
        </Link>
        {onToggle ? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8 text-on-petrol hover:bg-petrol-active hover:text-on-petrol"
            aria-label={collapsed ? t("shell.sidebar.expand") : t("shell.sidebar.collapse")}
            aria-expanded={!collapsed}
            onClick={onToggle}
          >
            {collapsed ? (
              <PanelLeftOpen aria-hidden="true" />
            ) : (
              <PanelLeftClose aria-hidden="true" />
            )}
          </Button>
        ) : null}
      </div>

      {organizations.length > 0 ? (
        <div className="px-2 pb-2">
          <OrganizationSwitcher organizations={organizations} collapsed={collapsed} />
        </div>
      ) : null}

      <nav aria-label={t("shell.sidebar.nav")} className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        <ul className="space-y-1">
          {SHELL_NAV_ITEMS.map((item) => (
            <li key={item.href}>
              <SidebarNavItem
                href={item.href}
                labelKey={item.labelKey}
                collapsed={collapsed}
                animateIndicator={animateIndicator}
                instanceId={instanceId}
                unreadCount={unreadCount}
                onNavigate={onNavigate}
              />
            </li>
          ))}
        </ul>
      </nav>

      <div className="space-y-2 border-t border-on-petrol/15 p-2">
        {supportUrl ? <HelpCard supportUrl={supportUrl} collapsed={collapsed} /> : null}
        <UserMenu
          user={user}
          variant="sidebar"
          collapsed={collapsed}
          onLogout={onLogout}
          loggingOut={loggingOut}
        />
      </div>
    </div>
  );
}

export function DesktopSidebar(props: Omit<SidebarContentProps, "instanceId" | "onNavigate">) {
  return (
    <aside
      data-collapsed={props.collapsed}
      className={cn(
        "sticky top-0 hidden h-dvh shrink-0 flex-col overflow-hidden border-r border-on-petrol/15 bg-petrol-sidebar text-on-petrol transition-[width] duration-200 lg:flex",
        props.collapsed ? "w-20" : "w-64",
      )}
    >
      <SidebarContent {...props} instanceId="desktop" />
    </aside>
  );
}

export function MobileSidebar({
  open,
  onOpenChange,
  ...props
}: Omit<SidebarContentProps, "instanceId" | "collapsed" | "onToggle" | "onNavigate"> & {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useI18n();

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="left"
        className="w-[280px] max-w-[86vw] border-on-petrol/15 bg-petrol-sidebar p-0 text-on-petrol [&>button]:text-on-petrol [&>button:hover]:bg-petrol-active [&>button:hover]:text-on-petrol [&>button:focus-visible]:ring-on-petrol"
      >
        <SheetHeader className="sr-only">
          <SheetTitle>{t("shell.sidebar.nav")}</SheetTitle>
          <SheetDescription>{t("app.tagline")}</SheetDescription>
        </SheetHeader>
        <SidebarContent
          {...props}
          collapsed={false}
          instanceId="mobile"
          onNavigate={() => onOpenChange(false)}
        />
      </SheetContent>
    </Sheet>
  );
}
