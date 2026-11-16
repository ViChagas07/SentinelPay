"use client";

import { useCallback, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

import { TooltipProvider } from "@/components/ui/tooltip";
import { useLogout } from "@/features/auth/hooks/use-auth";
import { useSession } from "@/features/auth/hooks/use-session";
import type { UserProfile } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";
import type { ShellOrganization } from "@/lib/shell/organization";
import { getShellPage } from "@/lib/shell/routes";
import { writeSidebarMode } from "@/lib/shell/sidebar-cookie";
import { getSupportUrl } from "@/lib/shell/organization";
import { PageTransition } from "@/components/ui/motion/page-transition";

import { useHighRiskAlertCount, useShellUnreadCount } from "../hooks/use-alerts";
import { useShellShortcuts } from "../hooks/use-shell-shortcuts";
import { CommandPalette } from "./command-palette";
import { DocumentAlerts } from "./document-alerts";
import { ShellHeader } from "./header";
import { ShellFooter } from "./shell-footer";
import { ShellSkeleton } from "./shell-skeleton";
import { ShortcutsDialog } from "./shortcuts-dialog";
import { DesktopSidebar, MobileSidebar } from "./sidebar";

const SHELL_ORGANIZATIONS: readonly ShellOrganization[] = [];

export function AppShell({
  initialCollapsed,
  initialUser,
  children,
}: Readonly<{ initialCollapsed: boolean; initialUser?: UserProfile | null; children: ReactNode }>) {
  const { t } = useI18n();
  const pathname = usePathname();
  const router = useRouter();
  const { user, status } = useSession(initialUser);
  const { mutate: logout, isPending: loggingOut } = useLogout();
  const [collapsed, setCollapsed] = useState(initialCollapsed);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const unread = useShellUnreadCount(Boolean(user)).data?.unread ?? 0;
  const alerts = useHighRiskAlertCount(Boolean(user));
  const alertCount = alerts.data?.count ?? 0;
  const alertTruncated = alerts.data?.truncated ?? false;
  const page = getShellPage(pathname);
  const title = t(page.titleKey);
  const supportUrl = getSupportUrl();

  const handleToggleSidebar = useCallback(() => {
    setCollapsed((current) => {
      const next = !current;
      writeSidebarMode(next ? "rail" : "expanded");
      return next;
    });
  }, []);

  const handleNavigate = useCallback(
    (href: string) => {
      setMobileOpen(false);
      setCommandOpen(false);
      router.push(href);
    },
    [router],
  );

  const handleNewVerification = useCallback(() => {
    handleNavigate("/verificacao/nova");
  }, [handleNavigate]);

  const handleOpenShortcuts = useCallback(() => {
    setCommandOpen(false);
    setShortcutsOpen(true);
  }, []);

  const handleLogout = useCallback(() => {
    logout();
  }, [logout]);

  useShellShortcuts(
    {
      onCommand: () => setCommandOpen(true),
      onPanel: () => handleNavigate("/painel"),
      onVerification: () => handleNavigate("/verificacao"),
      onNewVerification: handleNewVerification,
      onHelp: () => setShortcutsOpen(true),
    },
    {
      enabled: Boolean(user) && !mobileOpen && !commandOpen && !shortcutsOpen,
    },
  );

  if (status === "loading" || !user) {
    return <ShellSkeleton />;
  }

  return (
    <TooltipProvider delayDuration={250}>
      <div className="flex min-h-dvh w-full min-w-0 bg-background">
        <DesktopSidebar
          user={user}
          collapsed={collapsed}
          unreadCount={unread}
          organizations={SHELL_ORGANIZATIONS}
          supportUrl={supportUrl}
          onToggle={handleToggleSidebar}
          onLogout={handleLogout}
          loggingOut={loggingOut}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <ShellHeader
            titleKey={page.titleKey}
            breadcrumbs={page.breadcrumbs}
            user={user}
            onOpenMenu={() => setMobileOpen(true)}
            onOpenSearch={() => setCommandOpen(true)}
            onLogout={handleLogout}
            loggingOut={loggingOut}
          />

          <main id="conteudo" className="min-w-0 flex-1">
            <PageTransition key={pathname} className="min-w-0">
              {children}
            </PageTransition>
          </main>

          <ShellFooter />
        </div>
      </div>

      <MobileSidebar
        open={mobileOpen}
        onOpenChange={setMobileOpen}
        user={user}
        unreadCount={unread}
        organizations={SHELL_ORGANIZATIONS}
        supportUrl={supportUrl}
        onLogout={handleLogout}
        loggingOut={loggingOut}
      />

      <CommandPalette
        open={commandOpen}
        onOpenChange={setCommandOpen}
        onNavigate={handleNavigate}
        onNewVerification={handleNewVerification}
        onOpenShortcuts={handleOpenShortcuts}
      />

      <ShortcutsDialog open={shortcutsOpen} onOpenChange={setShortcutsOpen} />

      <DocumentAlerts count={alertCount} truncated={alertTruncated} baseTitle={title} />
    </TooltipProvider>
  );
}
