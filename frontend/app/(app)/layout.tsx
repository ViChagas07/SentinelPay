import type { Metadata } from "next";
import { cookies } from "next/headers";
import type { ReactNode } from "react";

import { AppShell } from "@/features/shell/components/app-shell";
import { SIDEBAR_COOKIE, resolveSidebarMode } from "@/lib/shell/sidebar-cookie";
import { fetchInitialUser } from "@/lib/session/server-user";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default async function PrivateLayout({ children }: Readonly<{ children: ReactNode }>) {
  const cookieStore = await cookies();
  const collapsed = resolveSidebarMode(cookieStore.get(SIDEBAR_COOKIE)?.value) === "rail";
  const initialUser = await fetchInitialUser();

  return (
    <AppShell initialCollapsed={collapsed} initialUser={initialUser}>
      {children}
    </AppShell>
  );
}
