"use client";

import { Building2, Check, ChevronsUpDown } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useI18n } from "@/lib/i18n/provider";
import type { ShellOrganization } from "@/lib/shell/organization";
import { cn } from "@/lib/utils";

export type OrganizationSwitcherProps = {
  organizations: readonly ShellOrganization[];
  selectedId?: string;
  onSelect?: (id: string) => void;
  collapsed?: boolean;
};

export function OrganizationSwitcher({
  organizations,
  selectedId,
  onSelect,
  collapsed = false,
}: OrganizationSwitcherProps) {
  const { t } = useI18n();
  const current = organizations.find((item) => item.id === selectedId) ?? organizations[0];

  if (!current) {
    return null;
  }

  const plan = t("shell.sidebar.organization.plan", { plan: current.plan });

  if (organizations.length === 1) {
    return (
      <div
        title={current.name}
        className={cn(
          "flex items-center gap-2 rounded-[6px] border border-on-petrol/15 px-2 py-2 text-on-petrol",
          collapsed && "justify-center",
        )}
      >
        <Building2 className="size-4 shrink-0" aria-hidden="true" />
        {collapsed ? null : (
          <span className="min-w-0">
            <span className="block truncate text-xs font-medium">{current.name}</span>
            <span className="block truncate font-mono text-[0.6rem] uppercase tracking-[0.14em] text-on-petrol/75">
              {plan}
            </span>
          </span>
        )}
      </div>
    );
  }

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={collapsed ? `${current.name}, ${plan}` : undefined}
          className={cn(
            "flex w-full items-center gap-2 rounded-[6px] border border-on-petrol/15 px-2 py-2 text-left text-on-petrol transition-colors hover:bg-petrol-active",
            collapsed && "justify-center",
          )}
        >
          <Building2 className="size-4 shrink-0" aria-hidden="true" />
          {collapsed ? null : (
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-medium">{current.name}</span>
              <span className="block truncate font-mono text-[0.6rem] uppercase tracking-[0.14em] text-on-petrol/75">
                {plan}
              </span>
            </span>
          )}
          {collapsed ? null : <ChevronsUpDown className="size-3 shrink-0" aria-hidden="true" />}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="bottom" className="z-[60] w-64">
        {organizations.map((organization) => (
          <DropdownMenuItem
            key={organization.id}
            onSelect={() => onSelect?.(organization.id)}
            className="gap-2"
          >
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm">{organization.name}</span>
              <span className="block truncate font-mono text-[0.65rem] text-muted-foreground">
                {t("shell.sidebar.organization.plan", { plan: organization.plan })}
              </span>
            </span>
            {organization.id === current.id ? (
              <Check className="size-4 shrink-0" aria-hidden="true" />
            ) : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
