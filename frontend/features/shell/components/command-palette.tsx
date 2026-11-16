"use client";

import { FilePlus2, Keyboard, SearchX, UserRound } from "lucide-react";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { useI18n } from "@/lib/i18n/provider";
import { SHELL_NAV_ITEMS } from "@/lib/shell/routes";

import { SHELL_NAV_ICONS } from "../nav-icons";

const NAV_SHORTCUTS: Record<string, string> = {
  "/painel": "g p",
  "/verificacao": "g v",
};

export type CommandPaletteProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onNavigate: (href: string) => void;
  onNewVerification: () => void;
  onOpenShortcuts: () => void;
};

export function CommandPalette({
  open,
  onOpenChange,
  onNavigate,
  onNewVerification,
  onOpenShortcuts,
}: CommandPaletteProps) {
  const { t } = useI18n();

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("shell.command.title")}
      description={t("shell.command.description")}
    >
      <CommandInput
        aria-label={t("shell.command.placeholder")}
        placeholder={t("shell.command.placeholder")}
      />
      <CommandList>
        <CommandEmpty>{t("shell.command.empty")}</CommandEmpty>

        <CommandGroup heading={t("shell.command.group.search")}>
          <CommandItem value="document-search-unavailable" disabled className="items-start">
            <SearchX className="mt-0.5" aria-hidden="true" />
            <span className="flex min-w-0 flex-col">
              <span>{t("shell.command.search.unavailable")}</span>
              <span className="text-xs text-muted-foreground">
                {t("shell.command.search.unavailableHint")}
              </span>
            </span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading={t("shell.command.group.navigation")}>
          {SHELL_NAV_ITEMS.map((item) => {
            const Icon = SHELL_NAV_ICONS[item.href] ?? UserRound;
            const shortcut = NAV_SHORTCUTS[item.href];

            return (
              <CommandItem
                key={item.href}
                value={`${t(item.labelKey)} ${item.href}`}
                onSelect={() => onNavigate(item.href)}
              >
                <Icon aria-hidden="true" />
                {t(item.labelKey)}
                {shortcut ? <CommandShortcut>{shortcut}</CommandShortcut> : null}
              </CommandItem>
            );
          })}
          <CommandItem
            value={`${t("shell.nav.account")} /account`}
            onSelect={() => onNavigate("/account")}
          >
            <UserRound aria-hidden="true" />
            {t("shell.nav.account")}
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading={t("shell.command.group.actions")}>
          <CommandItem
            value={`${t("shell.command.action.newVerification")} ${t("shell.command.key.newVerification")}`}
            onSelect={onNewVerification}
          >
            <FilePlus2 aria-hidden="true" />
            {t("shell.command.action.newVerification")}
            <CommandShortcut>{t("shell.command.key.newVerification")}</CommandShortcut>
          </CommandItem>
          <CommandItem
            value={`${t("shell.command.action.shortcuts")} ?`}
            onSelect={onOpenShortcuts}
          >
            <Keyboard aria-hidden="true" />
            {t("shell.command.action.shortcuts")}
            <CommandShortcut>?</CommandShortcut>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
