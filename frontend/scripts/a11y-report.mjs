import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUTPUT = path.join(ROOT, "docs", "quality", "axe-matrix.json");

const result = spawnSync(
  "npx",
  ["playwright", "test", "e2e/a11y-matrix.spec.ts", "--reporter=json"],
  {
    cwd: ROOT,
    encoding: "utf8",
    shell: process.platform === "win32",
    timeout: 900_000,
    maxBuffer: 64 * 1024 * 1024,
    windowsHide: true,
  },
);

mkdirSync(path.dirname(OUTPUT), { recursive: true });
writeFileSync(OUTPUT, result.stdout ?? "", "utf8");

if (result.status !== 0) {
  console.error("A matriz axe falhou. Veja docs/quality/axe-matrix.json.");
  process.exit(1);
}

console.log("Matriz axe salva em docs/quality/axe-matrix.json.");
