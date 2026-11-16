import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

import type { BrowserContext } from "@playwright/test";

export type DashboardPayableSeed = {
  id: string;
  description: string;
  amount: string;
  due_offset_days: number;
  status: string;
};

export type DashboardSeed = {
  user_timezone: string;
  analysis_ids: {
    failed: string;
    processing: string;
    completed: string[];
    previous: string[];
  };
  payables: DashboardPayableSeed[];
  notifications: number;
  average: number;
  conformity: number;
  documents_analyzed: number;
  high_risk: number;
  flagged: number;
  pending_receipts: number;
  seven_day_average: number;
  seven_day_conformity: number;
  seven_day_documents: number;
  seven_day_high_risk: number;
};

export type BackendSession = {
  email: string;
  accessToken: string;
  refreshToken: string;
  csrfToken: string;
  expiresIn: number;
  seed?: DashboardSeed;
};

export type CreateBackendSessionOptions = {
  seedDashboard?: boolean;
  email?: string;
};

const CONTAINER = process.env.E2E_API_CONTAINER ?? "paysentineliq-api-1";
const SCRIPT = join(process.cwd(), "e2e", "support", "create_session.py");
const DEFAULT_EMAIL = "e2e.session@paysentineliq.test";

function runDocker(args: readonly string[], timeout: number) {
  return spawnSync("docker", args, {
    encoding: "utf8",
    timeout,
    windowsHide: true,
  });
}

export function backendSessionAvailable(): boolean {
  if (!existsSync(SCRIPT)) {
    return false;
  }

  const result = runDocker(["exec", CONTAINER, "python", "-c", "import paysentineliq"], 20_000);
  return result.status === 0;
}

export function createBackendSession(options: CreateBackendSessionOptions = {}): BackendSession {
  const copy = runDocker(["cp", SCRIPT, `${CONTAINER}:/tmp/create_session.py`], 30_000);

  if (copy.status !== 0) {
    throw new Error(`Could not copy the session script: ${copy.stderr ?? ""}`);
  }

  const scriptArgs = [options.email ?? DEFAULT_EMAIL];

  if (options.seedDashboard) {
    scriptArgs.push("--seed-dashboard");
  }

  const result = runDocker(
    ["exec", CONTAINER, "python", "/tmp/create_session.py", ...scriptArgs],
    60_000,
  );

  if (result.status !== 0) {
    throw new Error(`Session mint failed: ${result.stderr || result.stdout}`);
  }

  const line = result.stdout.trim().split(/\r?\n/).pop() ?? "";
  const parsed: unknown = JSON.parse(line);

  if (
    typeof parsed !== "object" ||
    parsed === null ||
    !("access_token" in parsed) ||
    !("refresh_token" in parsed) ||
    !("email" in parsed)
  ) {
    throw new Error("Session mint returned an unexpected payload.");
  }

  const payload = parsed as {
    access_token: string;
    refresh_token: string;
    csrf_token?: string;
    email: string;
    expires_in?: number;
    seed?: DashboardSeed;
  };

  return {
    email: payload.email,
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    csrfToken: payload.csrf_token ?? "e2e-csrf-token",
    expiresIn: payload.expires_in ?? 900,
    seed: payload.seed,
  };
}

export async function applySessionCookies(
  context: BrowserContext,
  session: BackendSession,
  baseURL: string,
): Promise<void> {
  await context.addCookies([
    { name: "sp_session", value: session.accessToken, url: baseURL, httpOnly: true },
    { name: "sp_refresh", value: session.refreshToken, url: baseURL, httpOnly: true },
    { name: "sp_csrf", value: session.csrfToken, url: baseURL, httpOnly: true },
    {
      name: "sp_session_exp",
      value: String(Date.now() + 10 * 60_000),
      url: baseURL,
      httpOnly: true,
    },
  ]);
}
