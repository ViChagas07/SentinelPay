"use client";

import { ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useI18n } from "@/lib/i18n/provider";
import type { LegalSection } from "@/lib/legal/content/types";
import { cn } from "@/lib/utils";

function useActiveSection(sections: LegalSection[]): string {
  const [activeId, setActiveId] = useState(sections[0]?.id ?? "");

  useEffect(() => {
    const elements = sections
      .map((section) => window.document.getElementById(section.id))
      .filter((element): element is HTMLElement => element !== null);

    if (elements.length === 0 || typeof IntersectionObserver === "undefined") {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((first, second) => first.boundingClientRect.top - second.boundingClientRect.top);
        const first = visible[0];

        if (first) {
          setActiveId(first.target.id);
        }
      },
      { rootMargin: "-88px 0px -65% 0px", threshold: [0, 0.2, 1] },
    );

    for (const element of elements) {
      observer.observe(element);
    }

    return () => observer.disconnect();
  }, [sections]);

  return activeId;
}

function TocList({
  sections,
  activeId,
  onNavigate,
}: Readonly<{
  sections: LegalSection[];
  activeId: string;
  onNavigate?: () => void;
}>) {
  return (
    <ol className="border-l border-border">
      {sections.map((section, index) => {
        const active = section.id === activeId;

        return (
          <li key={section.id}>
            <a
              href={`#${section.id}`}
              onClick={onNavigate}
              aria-current={active ? "location" : undefined}
              className={cn(
                "-ml-px block border-l-2 py-1 pl-3 pr-2 text-[0.8125rem] leading-snug transition-colors hover:text-foreground",
                active
                  ? "border-petrol-primary text-foreground"
                  : "border-transparent text-muted-foreground",
              )}
            >
              <span className="mr-1.5 font-mono text-[0.65rem] tabular-nums text-muted-foreground">
                {String(index + 1).padStart(2, "0")}
              </span>
              {section.title}
            </a>
          </li>
        );
      })}
    </ol>
  );
}

export function LegalToc({ sections }: Readonly<{ sections: LegalSection[] }>) {
  const { t } = useI18n();
  const activeId = useActiveSection(sections);
  const detailsRef = useRef<HTMLDetailsElement | null>(null);
  const closeMobile = () => detailsRef.current?.removeAttribute("open");

  return (
    <>
      <div className="print:hidden lg:hidden">
        <details ref={detailsRef} className="group rounded-[6px] border border-border bg-card">
          <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium text-foreground">
            {t("legal.toc")}
            <ChevronDown
              className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
              aria-hidden="true"
            />
          </summary>
          <nav aria-label={t("legal.tocLabel")} className="border-t border-border px-3 py-2">
            <TocList sections={sections} activeId={activeId} onNavigate={closeMobile} />
          </nav>
        </details>
      </div>

      <div className="hidden print:hidden lg:block">
        <div className="sticky top-24 pr-2">
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.22em] text-muted-foreground">
            {t("legal.toc")}
          </p>
          <nav aria-label={t("legal.tocLabel")} className="mt-3">
            <TocList sections={sections} activeId={activeId} />
          </nav>
        </div>
      </div>
    </>
  );
}
