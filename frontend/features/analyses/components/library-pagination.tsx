"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";

export type LibraryPaginationProps = {
  page: number;
  totalPages: number;
  total: number;
  onPageChange: (page: number) => void;
};

export function LibraryPagination({
  page,
  totalPages,
  total,
  onPageChange,
}: LibraryPaginationProps) {
  const { t } = useI18n();

  return (
    <nav
      aria-label={t("library.pagination.aria")}
      className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4"
    >
      <p className="text-xs text-muted-foreground">{t("library.pagination.summary", { total })}</p>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={t("library.pagination.previous")}
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft aria-hidden="true" />
        </Button>
        <p aria-live="polite" className="font-mono text-xs tabular-nums text-muted-foreground">
          {t("library.pagination.page", { page, totalPages })}
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={t("library.pagination.next")}
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          <ChevronRight aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
}
