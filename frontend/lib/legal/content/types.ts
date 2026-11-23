export type LegalLink = {
  label: string;
  href: string;
};

export type LegalTable = {
  caption: string;
  headers: string[];
  rows: string[][];
};

export type LegalBlock =
  | { type: "paragraph"; text: string }
  | { type: "subheading"; text: string }
  | { type: "list"; items: string[]; ordered?: boolean }
  | { type: "table"; table: LegalTable }
  | { type: "note"; text: string }
  | { type: "links"; items: LegalLink[] }
  | { type: "identity" };

export type LegalSection = {
  id: string;
  title: string;
  blocks: LegalBlock[];
};

export type LegalDocument = {
  title: string;
  subtitle: string;
  notice?: string;
  sections: LegalSection[];
};

export type LegalContent = {
  terms: LegalDocument;
  privacy: LegalDocument;
};
