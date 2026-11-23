"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useI18n } from "@/lib/i18n/provider";
import type { LegalBlock, LegalLink, LegalTable } from "@/lib/legal/content/types";
import type { LegalIdentity } from "@/lib/legal/identity";
import { getPrivacyContactFromEnv } from "@/lib/site/privacy";

function resolveLink(href: string): { href: string; external: boolean } {
  if (href === "privacy-contact") {
    const contact = getPrivacyContactFromEnv();
    return { href: contact.href, external: contact.href.startsWith("http") };
  }

  return { href, external: href.startsWith("http") };
}

function LinkItem({ item }: Readonly<{ item: LegalLink }>) {
  const { href, external } = resolveLink(item.href);
  const className =
    "inline-flex min-h-9 items-center rounded-[4px] border border-border bg-surface px-3 py-1.5 text-sm text-foreground underline decoration-border underline-offset-4 transition-colors hover:bg-surface-elevated";

  if (href.startsWith("/")) {
    return (
      <Link href={href} className={className}>
        {item.label}
      </Link>
    );
  }

  return (
    <a
      href={href}
      className={className}
      {...(external ? { target: "_blank", rel: "noreferrer" } : {})}
    >
      {item.label}
    </a>
  );
}

function IdentityBlock({ identity }: Readonly<{ identity: LegalIdentity }>) {
  const { t } = useI18n();
  const rows: { label: string; value: ReactNode }[] = [];

  if (identity.controllerName) {
    rows.push({ label: t("legal.identity.controller"), value: identity.controllerName });
  }

  if (identity.controllerTaxId) {
    rows.push({ label: t("legal.identity.taxId"), value: identity.controllerTaxId });
  }

  if (identity.controllerAddress) {
    rows.push({ label: t("legal.identity.address"), value: identity.controllerAddress });
  }

  if (identity.contactEmail) {
    rows.push({
      label: t("legal.identity.contact"),
      value: (
        <a
          className="break-all underline decoration-border underline-offset-4 hover:decoration-foreground"
          href={`mailto:${identity.contactEmail}`}
        >
          {identity.contactEmail}
        </a>
      ),
    });
  }

  if (identity.dpoName) {
    rows.push({ label: t("legal.identity.dpo"), value: identity.dpoName });
  }

  if (identity.dpoEmail) {
    rows.push({
      label: t("legal.identity.dpoEmail"),
      value: (
        <a
          className="break-all underline decoration-border underline-offset-4 hover:decoration-foreground"
          href={`mailto:${identity.dpoEmail}`}
        >
          {identity.dpoEmail}
        </a>
      ),
    });
  }

  if (rows.length === 0) {
    return (
      <p className="rounded-[6px] border border-border bg-surface-elevated p-4 text-sm leading-relaxed text-muted-foreground">
        {t("legal.identity.missing")}
      </p>
    );
  }

  return (
    <dl className="grid gap-x-6 gap-y-2 rounded-[6px] border border-border bg-card p-4 sm:grid-cols-[minmax(0,12rem)_minmax(0,1fr)] sm:p-5">
      {rows.map((row) => (
        <div key={row.label} className="contents">
          <dt className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground sm:pt-0.5">
            {row.label}
          </dt>
          <dd className="mb-2 break-words text-sm text-foreground sm:mb-0">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function TableBlock({ table }: Readonly<{ table: LegalTable }>) {
  return (
    <div className="space-y-2">
      <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground">
        {table.caption}
      </p>
      <div
        className="overflow-x-auto rounded-[6px] border border-border"
        role="region"
        aria-label={table.caption}
        tabIndex={0}
      >
        <table className="w-full min-w-[40rem] border-collapse text-sm">
          <caption className="sr-only">{table.caption}</caption>
          <thead>
            <tr className="bg-surface-elevated">
              {table.headers.map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="border-b border-border px-3 py-2.5 text-left font-mono text-[0.65rem] font-medium uppercase tracking-[0.14em] text-foreground"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, rowIndex) => (
              <tr key={`${table.caption}-${rowIndex}`} className="align-top">
                {row.map((cell, cellIndex) => {
                  const cellClassName =
                    "border-b border-border px-3 py-2.5 text-left text-sm leading-relaxed text-foreground/80 last:border-b-0";

                  return cellIndex === 0 ? (
                    <th key={`${rowIndex}-${cellIndex}`} scope="row" className={cellClassName}>
                      {cell}
                    </th>
                  ) : (
                    <td key={`${rowIndex}-${cellIndex}`} className={cellClassName}>
                      {cell}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function LegalBlocks({
  blocks,
  identity,
}: Readonly<{ blocks: LegalBlock[]; identity: LegalIdentity }>) {
  return (
    <>
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;

        switch (block.type) {
          case "paragraph":
            return (
              <p key={key} className="text-[0.95rem] leading-7 text-foreground/80">
                {block.text}
              </p>
            );
          case "subheading":
            return (
              <h3 key={key} className="pt-2 text-base font-semibold text-foreground">
                {block.text}
              </h3>
            );
          case "list":
            return block.ordered ? (
              <ol
                key={key}
                className="list-decimal space-y-2 pl-5 text-[0.95rem] leading-7 text-foreground/80"
              >
                {block.items.map((item) => (
                  <li key={item} className="pl-1">
                    {item}
                  </li>
                ))}
              </ol>
            ) : (
              <ul
                key={key}
                className="list-disc space-y-2 pl-5 text-[0.95rem] leading-7 text-foreground/80"
              >
                {block.items.map((item) => (
                  <li key={item} className="pl-1">
                    {item}
                  </li>
                ))}
              </ul>
            );
          case "table":
            return <TableBlock key={key} table={block.table} />;
          case "note":
            return (
              <div
                key={key}
                className="rounded-[6px] border border-border bg-surface-elevated p-4 text-sm leading-relaxed text-foreground/80"
              >
                {block.text}
              </div>
            );
          case "links":
            return (
              <div key={key} className="flex flex-wrap gap-2 pt-1">
                {block.items.map((item) => (
                  <LinkItem key={`${item.href}-${item.label}`} item={item} />
                ))}
              </div>
            );
          case "identity":
            return <IdentityBlock key={key} identity={identity} />;
          default:
            return null;
        }
      })}
    </>
  );
}
