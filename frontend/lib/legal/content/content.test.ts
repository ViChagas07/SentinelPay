import { describe, expect, it } from "vitest";

import { en } from "@/lib/legal/content/en";
import { es } from "@/lib/legal/content/es";
import { pt } from "@/lib/legal/content/pt";
import type { LegalBlock, LegalContent, LegalDocument } from "@/lib/legal/content/types";
import { LEGAL_UPDATED_AT, LEGAL_VERSION } from "@/lib/legal/version";

const LOCALES: { name: string; content: LegalContent }[] = [
  { name: "pt", content: pt },
  { name: "es", content: es },
  { name: "en", content: en },
];

function allBlocks(document: LegalDocument): LegalBlock[] {
  return document.sections.flatMap((section) => section.blocks);
}

describe("legal content", () => {
  it("keeps the version and the update date in a valid format", () => {
    expect(LEGAL_VERSION.trim().length).toBeGreaterThan(0);
    expect(LEGAL_UPDATED_AT).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(Number.isNaN(new Date(`${LEGAL_UPDATED_AT}T00:00:00Z`).getTime())).toBe(false);
  });

  it("has the required number of sections in every locale", () => {
    for (const { content } of LOCALES) {
      expect(content.privacy.sections).toHaveLength(15);
      expect(content.terms.sections).toHaveLength(12);
    }
  });

  it("keeps the same section ids and order in every locale", () => {
    const reference = pt;

    for (const { name, content } of LOCALES) {
      expect(
        content.privacy.sections.map((section) => section.id),
        `${name} privacy ids`,
      ).toEqual(reference.privacy.sections.map((section) => section.id));
      expect(
        content.terms.sections.map((section) => section.id),
        `${name} terms ids`,
      ).toEqual(reference.terms.sections.map((section) => section.id));
    }
  });

  it("keeps unique, non-empty section titles", () => {
    for (const { content } of LOCALES) {
      for (const document of [content.privacy, content.terms]) {
        const ids = document.sections.map((section) => section.id);
        expect(new Set(ids).size).toBe(ids.length);
        expect(document.title.trim().length).toBeGreaterThan(0);
        expect(document.subtitle.trim().length).toBeGreaterThan(0);

        for (const section of document.sections) {
          expect(section.id).toMatch(/^[a-z0-9-]+$/);
          expect(section.title.trim().length).toBeGreaterThan(0);
          expect(section.blocks.length).toBeGreaterThan(0);
        }
      }
    }
  });

  it("has well-formed blocks", () => {
    for (const { content } of LOCALES) {
      for (const document of [content.privacy, content.terms]) {
        for (const block of allBlocks(document)) {
          switch (block.type) {
            case "paragraph":
            case "subheading":
            case "note":
              expect(block.text.trim().length).toBeGreaterThan(0);
              break;
            case "list":
              expect(block.items.length).toBeGreaterThan(0);
              for (const item of block.items) {
                expect(item.trim().length).toBeGreaterThan(0);
              }
              break;
            case "table":
              expect(block.table.caption.trim().length).toBeGreaterThan(0);
              expect(block.table.headers.length).toBeGreaterThan(1);
              expect(block.table.rows.length).toBeGreaterThan(0);
              for (const row of block.table.rows) {
                expect(row).toHaveLength(block.table.headers.length);
                for (const cell of row) {
                  expect(cell.trim().length).toBeGreaterThan(0);
                }
              }
              break;
            case "links":
              expect(block.items.length).toBeGreaterThan(0);
              for (const item of block.items) {
                expect(item.label.trim().length).toBeGreaterThan(0);
                expect(
                  item.href === "privacy-contact" ||
                    item.href.startsWith("/") ||
                    item.href.startsWith("https://") ||
                    item.href.startsWith("mailto:"),
                ).toBe(true);
              }
              break;
            case "identity":
              break;
          }
        }
      }
    }
  });

  it("shows the institutional identity once in the first privacy section", () => {
    for (const { content } of LOCALES) {
      const first = content.privacy.sections[0];

      expect(first?.id).toBe("quem-somos");
      expect(first?.blocks.filter((block) => block.type === "identity")).toHaveLength(1);
    }
  });

  it("only shows the translation notice outside Portuguese", () => {
    expect(pt.privacy.notice).toBeUndefined();
    expect(pt.terms.notice).toBeUndefined();
    expect(es.privacy.notice?.trim().length).toBeGreaterThan(0);
    expect(es.terms.notice?.trim().length).toBeGreaterThan(0);
    expect(en.privacy.notice?.trim().length).toBeGreaterThan(0);
    expect(en.terms.notice?.trim().length).toBeGreaterThan(0);
  });

  it("does not contain em dash, placeholders or empty table cells", () => {
    const serialized = JSON.stringify([pt, es, en]);

    expect(serialized.includes("\u2014")).toBe(false);
    expect(serialized.includes("{{")).toBe(false);
  });
});
