import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PRODUCTION_ROOTS = ["app", "components", "features", "lib"].map((dir) =>
  path.join(ROOT, dir),
);
const SOURCE_EXTENSIONS = new Set([".ts", ".tsx", ".mjs", ".js"]);
const IGNORED_DIRECTORIES = new Set(["node_modules", ".next", "test-results", "playwright-report"]);

const RULES = [
  {
    label: "HTML injetado com dangerouslySetInnerHTML",
    pattern: /dangerouslySetInnerHTML/,
  },
  {
    label: "armazenamento web para dados de sessao",
    pattern: /\b(?:localStorage|sessionStorage|indexedDB)\b/,
  },
  {
    label: "atribuicao direta de innerHTML",
    pattern: /\.innerHTML\s*=/,
  },
  {
    label: "codigo dinamico com eval ou Function",
    pattern: /\beval\s*\(|\bnew\s+Function\s*\(/,
  },
  {
    label: "log esquecido em codigo de producao",
    pattern: /console\.(?:log|debug)\s*\(/,
  },
  {
    label: "variavel publica com nome de segredo",
    pattern: /NEXT_PUBLIC_[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PRIVATE_KEY)[A-Z0-9_]*/,
  },
];

const errors = [];
let scanned = 0;

function listFiles(dir) {
  const found = [];

  for (const entry of readdirSync(dir)) {
    if (IGNORED_DIRECTORIES.has(entry)) {
      continue;
    }

    const absolute = path.join(dir, entry);
    const stats = statSync(absolute);

    if (stats.isDirectory()) {
      found.push(...listFiles(absolute));
      continue;
    }

    if (
      SOURCE_EXTENSIONS.has(path.extname(entry)) &&
      !entry.includes(".test.") &&
      !entry.includes(".spec.")
    ) {
      found.push(absolute);
    }
  }

  return found;
}

for (const root of PRODUCTION_ROOTS) {
  for (const file of listFiles(root)) {
    scanned += 1;
    const lines = readFileSync(file, "utf8").split(/\r?\n/);

    for (const rule of RULES) {
      lines.forEach((line, index) => {
        if (rule.pattern.test(line)) {
          errors.push(`${rule.label} em ${path.relative(ROOT, file)}:${index + 1}: ${line.trim()}`);
        }
      });
    }
  }
}

const envExamplePath = path.join(ROOT, ".env.example");
const envExample = readFileSync(envExamplePath, "utf8");

for (const line of envExample.split(/\r?\n/)) {
  if (RULES[5].pattern.test(line)) {
    errors.push(`Variavel publica com nome de segredo em .env.example: ${line.trim()}`);
  }
}

if (errors.length > 0) {
  console.error("Falha na verificacao de seguranca do codigo:");
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log(`Seguranca ok: ${scanned} arquivos de producao sem padroes inseguros.`);
