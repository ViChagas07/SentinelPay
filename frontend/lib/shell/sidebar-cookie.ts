export const SIDEBAR_COOKIE = "sp_sidebar";

export const SIDEBAR_MODES = ["expanded", "rail"] as const;

export type SidebarMode = (typeof SIDEBAR_MODES)[number];

export function resolveSidebarMode(value: string | undefined | null): SidebarMode {
  return value === "rail" ? "rail" : "expanded";
}

export function writeSidebarMode(mode: SidebarMode): void {
  if (typeof document === "undefined") {
    return;
  }

  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${SIDEBAR_COOKIE}=${mode}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
}
