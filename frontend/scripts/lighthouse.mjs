import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PORT = Number(process.env.LIGHTHOUSE_PORT ?? 3210);
const BASE_URL = `http://127.0.0.1:${PORT}`;
const CONTAINER = process.env.E2E_API_CONTAINER ?? "paysentineliq-api-1";
const MINIMUM_SCORE = 90;
const CATEGORIES = ["performance", "accessibility", "best-practices"];

function runDocker(args, timeout) {
  return spawnSync("docker", args, {
    encoding: "utf8",
    timeout,
    windowsHide: true,
  });
}

function mintSession() {
  const available = runDocker(["exec", CONTAINER, "python", "-c", "import paysentineliq"], 20_000);

  if (available.status !== 0) {
    return null;
  }

  const script = path.join(ROOT, "e2e", "support", "create_session.py");
  const copy = runDocker(["cp", script, `${CONTAINER}:/tmp/create_session.py`], 30_000);

  if (copy.status !== 0) {
    return null;
  }

  const result = runDocker(
    [
      "exec",
      CONTAINER,
      "python",
      "/tmp/create_session.py",
      "e2e.lighthouse@paysentineliq.test",
      "--seed-dashboard",
    ],
    60_000,
  );

  if (result.status !== 0) {
    return null;
  }

  const line = result.stdout.trim().split(/\r?\n/).pop() ?? "";

  try {
    return JSON.parse(line);
  } catch {
    return null;
  }
}

async function portInUse() {
  try {
    await fetch(BASE_URL, { signal: AbortSignal.timeout(1_000) });
    return true;
  } catch {
    return false;
  }
}

function stopServer(server) {
  if (!server || server.killed) {
    return;
  }

  if (process.platform === "win32" && server.pid) {
    spawnSync("taskkill", ["/pid", String(server.pid), "/T", "/F"], { windowsHide: true });
    return;
  }

  server.kill("SIGTERM");
}

async function waitForServer() {
  const deadline = Date.now() + 120_000;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(BASE_URL);

      if (response.ok) {
        return;
      }
    } catch {
      // The server is still starting.
    }

    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }

  throw new Error("O servidor de producao nao respondeu em 120 s.");
}

function startServer() {
  const child = spawn(
    process.platform === "win32" ? "npm.cmd" : "npm",
    ["run", "start", "--", "--hostname", "127.0.0.1", "--port", String(PORT)],
    {
      cwd: ROOT,
      env: {
        ...process.env,
        API_INTERNAL_URL: process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000",
        NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000",
        NEXT_PUBLIC_SITE_URL: BASE_URL,
        NEXT_TELEMETRY_DISABLED: "1",
      },
      stdio: "ignore",
      windowsHide: true,
      shell: process.platform === "win32",
    },
  );

  return child;
}

function cookieHeader(session) {
  const parts = [];

  if (session?.access_token) {
    parts.push(`sp_session=${session.access_token}`);
    parts.push(`sp_session_exp=${Date.now() + 10 * 60_000}`);
  }

  if (session?.refresh_token) {
    parts.push(`sp_refresh=${session.refresh_token}`);
  }

  if (session?.csrf_token) {
    parts.push(`sp_csrf=${session.csrf_token}`);
  }

  parts.push("locale=pt", "theme=light");

  return parts.join("; ");
}

async function main() {
  if (!existsSync(path.join(ROOT, ".next", "BUILD_ID"))) {
    throw new Error("Build ausente. Rode `npm run build` antes de `npm run lighthouse`.");
  }

  const session = mintSession();
  const cookie = cookieHeader(session);
  const { default: lighthouse } = await import("lighthouse");
  const { launch } = await import("chrome-launcher");
  const { chromium } = await import("@playwright/test");

  mkdirSync(path.join(ROOT, "docs", "quality"), { recursive: true });

  if (await portInUse()) {
    throw new Error(`A porta ${PORT} ja esta em uso. Finalize o processo e tente novamente.`);
  }

  const server = startServer();
  let chrome;

  try {
    await waitForServer();
    chrome = await launch({
      chromePath: chromium.executablePath(),
      chromeFlags: ["--headless=new", "--no-sandbox", "--disable-gpu"],
    });

    const targets = [
      { name: "landing", url: `${BASE_URL}/`, withSession: false },
      { name: "painel", url: `${BASE_URL}/painel`, withSession: true },
    ];
    const failures = [];

    for (const target of targets) {
      if (target.withSession && !session) {
        failures.push(`${target.name}: sessao indisponivel, painel nao medido.`);
        continue;
      }

      const options = {
        port: chrome.port,
        output: "json",
        logLevel: "error",
        onlyCategories: CATEGORIES,
        extraHeaders: target.withSession ? { Cookie: cookie } : undefined,
      };
      const result = await lighthouse(target.url, options);

      if (!result) {
        failures.push(`${target.name}: Lighthouse nao retornou resultado.`);
        continue;
      }

      const reportPath = path.join(ROOT, "docs", "quality", `lighthouse-${target.name}.json`);
      writeFileSync(reportPath, result.report, "utf8");

      const scores = Object.fromEntries(
        CATEGORIES.map((category) => [
          category,
          Math.round((result.lhr.categories[category]?.score ?? 0) * 100),
        ]),
      );

      console.log(
        `${target.name.padEnd(8)} performance ${scores.performance} | acessibilidade ${scores.accessibility} | boas praticas ${scores["best-practices"]}`,
      );

      for (const category of CATEGORIES) {
        if (scores[category] < MINIMUM_SCORE) {
          failures.push(`${target.name}: ${category} abaixo de ${MINIMUM_SCORE}.`);
        }
      }
    }

    if (failures.length > 0) {
      console.error("\nFalhas de Lighthouse:");
      for (const failure of failures) {
        console.error(`- ${failure}`);
      }
      process.exitCode = 1;
    }
  } finally {
    if (chrome) {
      await chrome.kill();
    }

    stopServer(server);
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
