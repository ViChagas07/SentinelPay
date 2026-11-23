"use client";

import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useI18n } from "@/lib/i18n/provider";
import { THEME_MODES, isThemeMode, type ThemeMode } from "@/lib/theme/constants";
import { useTheme } from "@/lib/theme/provider";
import type { TranslationKey } from "@/lib/i18n";

const THEME_ICONS: Record<ThemeMode, LucideIcon> = {
  system: Monitor,
  light: Sun,
  dark: Moon,
};

const THEME_LABEL_KEYS: Record<ThemeMode, TranslationKey> = {
  system: "theme.system",
  light: "theme.light",
  dark: "theme.dark",
};

export function ThemeToggle() {
  const { t } = useI18n();
  const { mode, setMode } = useTheme();
  const CurrentIcon = THEME_ICONS[mode];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          aria-label={`${t("theme.label")}: ${t(THEME_LABEL_KEYS[mode])}`}
        >
          <CurrentIcon aria-hidden="true" />
          <span className="hidden sm:inline">{t(THEME_LABEL_KEYS[mode])}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" sideOffset={10}>
        <DropdownMenuLabel>{t("theme.label")}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuRadioGroup
          value={mode}
          onValueChange={(value) => {
            if (isThemeMode(value)) {
              setMode(value);
            }
          }}
        >
          {THEME_MODES.map((themeMode) => {
            const Icon = THEME_ICONS[themeMode];

            return (
              <DropdownMenuRadioItem key={themeMode} value={themeMode}>
                <Icon aria-hidden="true" />
                {t(THEME_LABEL_KEYS[themeMode])}
              </DropdownMenuRadioItem>
            );
          })}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
