import { mkdirSync } from "node:fs";
import { spawnSync } from "node:child_process";

const baseUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
const openApiUrl = `${baseUrl}/openapi.json`;

mkdirSync("lib/api/generated", { recursive: true });

const result = spawnSync(
  "npx",
  ["openapi-typescript", openApiUrl, "-o", "lib/api/generated/openapi.d.ts"],
  {
    stdio: "inherit",
    shell: process.platform === "win32",
  },
);

if (result.status !== 0) {
  process.stderr.write(`Could not generate API types from ${openApiUrl}.\n`);
  process.exit(result.status ?? 1);
}

process.stdout.write("Generated lib/api/generated/openapi.d.ts\n");
