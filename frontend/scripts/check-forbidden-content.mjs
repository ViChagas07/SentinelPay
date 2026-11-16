import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PRODUCTION_ROOTS = ["app", "components", "features", "lib", "styles"].map((dir) =>
  path.join(ROOT, dir),
);
const DOCUMENT_ROOTS = [
  "app",
  "components",
  "features",
  "lib",
  "styles",
  "e2e",
  "tests",
  "docs",
  "scripts",
].map((dir) => path.join(ROOT, dir));
const ROOT_DOCUMENTS = ["README.md", "PROGRESS.md", "AGENTS.md", "middleware.ts", "next.config.ts"]
  .map((file) => path.join(ROOT, file))
  .filter((file) => {
    try {
      return statSync(file).isFile();
    } catch {
      return false;
    }
  });
const SOURCE_EXTENSIONS = new Set([".ts", ".tsx", ".css", ".mjs", ".js"]);
const DOCUMENT_EXTENSIONS = new Set([".ts", ".tsx", ".css", ".mjs", ".js", ".md", ".json"]);
const IGNORED_DIRECTORIES = new Set(["node_modules", ".next", "test-results", "playwright-report"]);

const FICTIONAL_TERMS = [
  { label: "mock", pattern: /\bmock(?:s|ed|ing)?\b/i },
  { label: "fixture", pattern: /\bfixtures?\b/i },
  { label: "faker", pattern: /\bfaker\b/i },
  { label: "lorem", pattern: /\blorem\b/i },
  { label: "Ana Souza", pattern: /\bAna\s+Souza\b/i },
  { label: "Nova Empresa", pattern: /\bNova\s+Empresa\b/i },
  { label: "Bradesco S.A.", pattern: /\bBradesco\s+S\.?\s*A\.?\b/i },
  { label: "Claro S.A.", pattern: /\bClaro\s+S\.?\s*A\.?\b/i },
  { label: "Vértice Logística", pattern: /\bV[ée]rtice\s+Log[íi]stica\b/i },
];

const errors = [];
let scannedProduction = 0;
let scannedDocuments = 0;

function listFiles(dir, extensions, { skipTests = false } = {}) {
  const found = [];

  for (const entry of readdirSync(dir)) {
    if (IGNORED_DIRECTORIES.has(entry)) {
      continue;
    }

    const absolute = path.join(dir, entry);
    const stats = statSync(absolute);

    if (stats.isDirectory()) {
      found.push(...listFiles(absolute, extensions, { skipTests }));
      continue;
    }

    if (!extensions.has(path.extname(entry))) {
      continue;
    }

    if (skipTests && (entry.includes(".test.") || entry.includes(".spec."))) {
      continue;
    }

    found.push(absolute);
  }

  return found;
}

function relative(file) {
  return path.relative(ROOT, file);
}

function scanProductionFiction() {
  for (const root of PRODUCTION_ROOTS) {
    for (const file of listFiles(root, SOURCE_EXTENSIONS, { skipTests: true })) {
      scannedProduction += 1;
      const source = readFileSync(file, "utf8");
      const lines = source.split(/\r?\n/);

      for (const term of FICTIONAL_TERMS) {
        lines.forEach((line, index) => {
          if (term.pattern.test(line)) {
            errors.push(`Dado ficticio "${term.label}" em ${relative(file)}:${index + 1}.`);
          }
        });
      }
    }
  }
}

function scanEmDash() {
  const files = new Set();

  for (const root of DOCUMENT_ROOTS) {
    for (const file of listFiles(root, DOCUMENT_EXTENSIONS)) {
      files.add(file);
    }
  }

  for (const file of ROOT_DOCUMENTS) {
    files.add(file);
  }

  for (const file of files) {
    scannedDocuments += 1;
    const source = readFileSync(file, "utf8");
    const lines = source.split(/\r?\n/);

    lines.forEach((line, index) => {
      if (line.includes("\u2014")) {
        errors.push(`Travessao longo em ${relative(file)}:${index + 1}.`);
      }
    });
  }
}

scanProductionFiction();
scanEmDash();

if (errors.length > 0) {
  console.error("Falha na varredura de conteudo proibido:");
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log(
  `Conteudo ok: ${scannedProduction} arquivos de producao sem dados ficticios e ${scannedDocuments} arquivos sem travessao longo.`,
);
