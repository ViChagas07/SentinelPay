import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import ts from "typescript";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DICTIONARIES_DIR = path.join(ROOT, "lib", "i18n", "dictionaries");
const ALLOWED_LOCALES = ["pt", "es", "en"];
const UI_ROOTS = ["app", "components", "features"].map((dir) => path.join(ROOT, dir));
const TEXT_ATTRIBUTES = new Set([
  "alt",
  "aria-description",
  "aria-label",
  "aria-placeholder",
  "aria-roledescription",
  "aria-valuetext",
  "placeholder",
  "title",
]);
const TOAST_METHODS = new Set(["success", "error", "info", "warning", "message", "loading"]);
const LETTERS = /\p{L}/u;

const errors = [];

function fail(message) {
  errors.push(message);
}

function listFiles(dir, extensions) {
  const found = [];

  for (const entry of readdirSync(dir)) {
    const absolute = path.join(dir, entry);
    const stats = statSync(absolute);

    if (stats.isDirectory()) {
      if (entry === "node_modules" || entry === ".next") {
        continue;
      }

      found.push(...listFiles(absolute, extensions));
      continue;
    }

    if (extensions.has(path.extname(entry))) {
      found.push(absolute);
    }
  }

  return found;
}

function parse(file) {
  const source = readFileSync(file, "utf8");
  const scriptKind = file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;

  return ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, scriptKind);
}

function readLocales() {
  const constants = parse(path.join(ROOT, "lib", "i18n", "constants.ts"));
  let locales = null;

  const visit = (node) => {
    if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      node.name.text === "LOCALES"
    ) {
      const initializer = node.initializer;

      if (!initializer) {
        return;
      }

      const array = unwrapExpression(initializer);

      if (ts.isArrayLiteralExpression(array)) {
        locales = array.elements
          .filter((element) => ts.isStringLiteral(element))
          .map((element) => element.text);
      }
    }

    ts.forEachChild(node, visit);
  };

  visit(constants);
  return locales;
}

function unwrapExpression(node) {
  let current = node;

  while (
    current &&
    (ts.isAsExpression(current) ||
      ts.isSatisfiesExpression(current) ||
      ts.isParenthesizedExpression(current))
  ) {
    current = current.expression;
  }

  return current;
}

function readDictionary(locale) {
  const file = path.join(DICTIONARIES_DIR, `${locale}.ts`);
  const source = parse(file);
  const entries = new Map();

  const visit = (node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === locale) {
      const object = unwrapExpression(node.initializer);

      if (object && ts.isObjectLiteralExpression(object)) {
        for (const property of object.properties) {
          if (!ts.isPropertyAssignment(property)) {
            continue;
          }

          const name = property.name.getText(source).replace(/^["']|["']$/g, "");
          const value = property.initializer;

          if (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)) {
            entries.set(name, value.text);
          } else {
            entries.set(name, null);
          }
        }
      }
    }

    ts.forEachChild(node, visit);
  };

  visit(source);
  return entries;
}

function placeholders(value) {
  const found = new Set();
  const pattern = /\{(\w+)\}/g;
  let match = pattern.exec(value ?? "");

  while (match) {
    found.add(match[1]);
    match = pattern.exec(value ?? "");
  }

  return [...found].sort();
}

function checkDictionaries() {
  const locales = readLocales();

  if (!locales) {
    fail("Nao foi possivel ler LOCALES em lib/i18n/constants.ts.");
    return;
  }

  const unexpected = locales.filter((locale) => !ALLOWED_LOCALES.includes(locale));
  const missingLocales = ALLOWED_LOCALES.filter((locale) => !locales.includes(locale));

  if (unexpected.length > 0) {
    fail(`Locales nao permitidos em LOCALES: ${unexpected.join(", ")}.`);
  }

  if (missingLocales.length > 0) {
    fail(`Locales ausentes em LOCALES: ${missingLocales.join(", ")}.`);
  }

  const dictionaryFiles = readdirSync(DICTIONARIES_DIR)
    .filter((file) => file.endsWith(".ts"))
    .map((file) => file.replace(/\.ts$/, ""))
    .filter((name) => name !== "index");

  const unexpectedFiles = dictionaryFiles.filter((name) => !ALLOWED_LOCALES.includes(name));

  if (unexpectedFiles.length > 0) {
    fail(`Dicionarios fora dos idiomas permitidos: ${unexpectedFiles.join(", ")}.`);
  }

  const dictionaries = new Map();
  const reference = readDictionary("pt");

  for (const locale of ALLOWED_LOCALES) {
    const dictionary = readDictionary(locale);
    dictionaries.set(locale, dictionary);

    if (dictionary.size === 0) {
      fail(`Dicionario ${locale} vazio ou ilegivel.`);
      continue;
    }

    for (const [key, value] of dictionary) {
      if (value === null) {
        fail(`Chave "${key}" em ${locale} nao tem valor de texto.`);
      } else if (value.trim().length === 0) {
        fail(`Chave "${key}" em ${locale} esta vazia.`);
      }
    }

    for (const key of reference.keys()) {
      if (!dictionary.has(key)) {
        fail(`Chave "${key}" falta em ${locale}.`);
      }
    }

    for (const key of dictionary.keys()) {
      if (!reference.has(key)) {
        fail(`Chave "${key}" existe em ${locale} e falta em pt.`);
      }
    }
  }

  for (const [key, referenceValue] of reference) {
    const expected = placeholders(referenceValue);

    for (const locale of ALLOWED_LOCALES) {
      const value = dictionaries.get(locale)?.get(key);
      const actual = placeholders(value);

      if (expected.join(",") !== actual.join(",")) {
        fail(
          `Placeholders divergentes em "${key}" (${locale}): esperado [${expected.join(
            ", ",
          )}], encontrado [${actual.join(", ")}].`,
        );
      }
    }
  }
}

function describe(file, node) {
  const { line } = ts.getLineAndCharacterOfPosition(node.getSourceFile(), node.getStart());
  return `${path.relative(ROOT, file)}:${line + 1}`;
}

function checkLiteral(file, node, value, context) {
  if (!LETTERS.test(value)) {
    return;
  }

  fail(`Texto fixo fora do dicionario em ${describe(file, node)} (${context}): "${value}".`);
}

function checkUiFile(file) {
  const source = parse(file);

  const visit = (node) => {
    if (ts.isJsxText(node)) {
      const text = node.text.trim();

      if (LETTERS.test(text)) {
        checkLiteral(file, node, text, "texto JSX");
      }
    }

    if (
      ts.isJsxAttribute(node) &&
      TEXT_ATTRIBUTES.has(node.name.getText(source)) &&
      node.initializer
    ) {
      if (ts.isStringLiteral(node.initializer)) {
        checkLiteral(file, node, node.initializer.text, `atributo ${node.name.getText(source)}`);
      } else if (
        ts.isJsxExpression(node.initializer) &&
        node.initializer.expression &&
        ts.isStringLiteral(node.initializer.expression)
      ) {
        checkLiteral(
          file,
          node,
          node.initializer.expression.text,
          `atributo ${node.name.getText(source)}`,
        );
      }
    }

    if (ts.isCallExpression(node)) {
      const expression = node.expression;

      if (
        ts.isPropertyAccessExpression(expression) &&
        ts.isIdentifier(expression.expression) &&
        expression.expression.text === "toast" &&
        TOAST_METHODS.has(expression.name.text) &&
        node.arguments.length > 0 &&
        ts.isStringLiteral(node.arguments[0])
      ) {
        checkLiteral(file, node, node.arguments[0].text, `toast.${expression.name.text}`);
      }

      if (
        ts.isIdentifier(expression) &&
        ["alert", "confirm", "prompt"].includes(expression.text) &&
        node.arguments.length > 0 &&
        ts.isStringLiteral(node.arguments[0])
      ) {
        checkLiteral(file, node, node.arguments[0].text, expression.text);
      }
    }

    ts.forEachChild(node, visit);
  };

  visit(source);
}

function checkHardcodedText() {
  for (const root of UI_ROOTS) {
    const files = listFiles(root, new Set([".tsx"])).filter(
      (file) =>
        !file.includes(".test.") &&
        // Catalogo interno de componentes, dev-only e com 404 em producao.
        !file.endsWith("design-showcase.tsx") &&
        // Imagem Open Graph gerada no servidor, nao e interface HTML.
        !file.endsWith("opengraph-image.tsx"),
    );

    for (const file of files) {
      checkUiFile(file);
    }
  }
}

checkDictionaries();
checkHardcodedText();

if (errors.length > 0) {
  console.error("Falha na verificacao de i18n:");
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log("i18n ok: pt, es e en completos, sem texto fixo em JSX.");
