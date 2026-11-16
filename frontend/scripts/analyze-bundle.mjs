import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";
import vm from "node:vm";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const NEXT_DIR = path.join(ROOT, ".next");
const STATIC_DIR = path.join(NEXT_DIR, "static");
const APP_DIR = path.join(NEXT_DIR, "server", "app");
const MAX_GZIP_KILOBYTES = 280;

function listFiles(dir, suffix) {
  const found = [];

  for (const entry of readdirSync(dir)) {
    const absolute = path.join(dir, entry);

    if (statSync(absolute).isDirectory()) {
      found.push(...listFiles(absolute, suffix));
      continue;
    }

    if (entry.endsWith(suffix)) {
      found.push(absolute);
    }
  }

  return found;
}

const sizeCache = new Map();

function sizesFor(assetPath) {
  const normalized = assetPath.replace(/^\/_next\//, "").replace(/^_next\//, "");
  const absolute = path.join(NEXT_DIR, normalized);

  if (sizeCache.has(absolute)) {
    return sizeCache.get(absolute);
  }

  const raw = readFileSync(absolute);
  const value = { raw: raw.length, gzip: gzipSync(raw).length };
  sizeCache.set(absolute, value);
  return value;
}

function kilobytes(bytes) {
  return `${(bytes / 1024).toFixed(1)} kB`;
}

function routeFromManifest(file) {
  const relative = path.relative(APP_DIR, file).replace(/\\/g, "/");
  const withoutFile = relative.replace(/\/?page_client-reference-manifest\.js$/, "");
  const route = `/${withoutFile}`
    .replace(/\/page$/, "")
    .replace(/\/\([^)]+\)/g, "")
    .replace(/\/+/g, "/");

  return route === "" ? "/" : route;
}

function readManifest(file) {
  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(readFileSync(file, "utf8"), sandbox);
  const manifests = sandbox.__RSC_MANIFEST ?? {};
  const keys = Object.keys(manifests);
  return keys.length > 0 ? manifests[keys[0]] : null;
}

if (!statSync(APP_DIR, { throwIfNoEntry: false })) {
  console.error("Build ausente. Rode `npm run build` antes de `npm run analyze`.");
  process.exit(1);
}

const manifests = listFiles(APP_DIR, "page_client-reference-manifest.js");
const routes = [];

for (const manifestFile of manifests) {
  const manifest = readManifest(manifestFile);

  if (!manifest) {
    continue;
  }

  const relative = path.relative(APP_DIR, manifestFile).replace(/\\/g, "/");
  const withoutFile = relative.replace(/\/?page_client-reference-manifest\.js$/, "");
  const entryKey = `[project]/app${withoutFile ? `/${withoutFile}` : ""}/page`;
  const jsAssets = new Set(manifest.entryJSFiles?.[entryKey] ?? []);
  const cssAssets = new Set((manifest.entryCSSFiles?.[entryKey] ?? []).map((entry) => entry.path));
  let jsRaw = 0;
  let jsGzip = 0;
  let cssRaw = 0;
  let cssGzip = 0;

  for (const asset of jsAssets) {
    const size = sizesFor(asset);
    jsRaw += size.raw;
    jsGzip += size.gzip;
  }

  for (const asset of cssAssets) {
    const size = sizesFor(asset);
    cssRaw += size.raw;
    cssGzip += size.gzip;
  }

  routes.push({
    route: routeFromManifest(manifestFile),
    jsRaw,
    jsGzip,
    cssRaw,
    cssGzip,
  });
}

routes.sort((left, right) => right.jsGzip - left.jsGzip);

console.log("Bundle por rota (entry JS e CSS do primeiro carregamento, gzip):\n");
console.log(
  "Rota".padEnd(32),
  "JS raw".padStart(10),
  "JS gzip".padStart(10),
  "CSS gzip".padStart(10),
);

for (const route of routes) {
  console.log(
    route.route.padEnd(32),
    kilobytes(route.jsRaw).padStart(10),
    kilobytes(route.jsGzip).padStart(10),
    kilobytes(route.cssGzip).padStart(10),
  );
}

const chunks = listFiles(STATIC_DIR, ".js")
  .map((file) => {
    const raw = readFileSync(file);
    return {
      file: path.relative(NEXT_DIR, file).replace(/\\/g, "/"),
      raw: raw.length,
      gzip: gzipSync(raw).length,
    };
  })
  .sort((left, right) => right.raw - left.raw)
  .slice(0, 10);

console.log("\nMaiores chunks JS:\n");

for (const chunk of chunks) {
  console.log(
    chunk.file.padEnd(48),
    kilobytes(chunk.raw).padStart(10),
    kilobytes(chunk.gzip).padStart(10),
  );
}

const overBudget = routes.filter((route) => route.jsGzip > MAX_GZIP_KILOBYTES * 1024);

if (overBudget.length > 0) {
  console.error(`\nOrcamento de ${MAX_GZIP_KILOBYTES} kB gzip excedido em:`);
  for (const route of overBudget) {
    console.error(`- ${route.route}: ${kilobytes(route.jsGzip)}`);
  }
  process.exit(1);
}

console.log(`\nOrcamento ok: todas as rotas abaixo de ${MAX_GZIP_KILOBYTES} kB de JS gzip.`);
