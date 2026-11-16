import type { ErrorEvent, Event } from "@sentry/browser";

type SentryModule = typeof import("@sentry/browser");

export type ObservabilityConfig = {
  dsn: string;
  environment: string;
  release: string | undefined;
  tracesSampleRate: number;
};

export type ObservabilityEnv = {
  NEXT_PUBLIC_SENTRY_DSN?: string;
  NEXT_PUBLIC_SENTRY_ENVIRONMENT?: string;
  NEXT_PUBLIC_SENTRY_RELEASE?: string;
  NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE?: string;
  NODE_ENV?: string;
};

const REDACTION = "[REDACTED]";
const MAX_TEXT_LENGTH = 1_000;
const SENSITIVE_QUERY =
  /([?&](?:token|access_token|refresh_token|id_token|document|file|q)=)[^&\s]+/gi;
const EMAIL = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
const CPF = /\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b/g;
const CNPJ = /\b\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}\b/g;
const PHONE = /\b(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}-?\d{4}\b/g;
const BEARER = /\bBearer\s+[A-Za-z0-9._~+/=-]+/gi;
const SECRET_ASSIGNMENT =
  /\b(?:password|senha|secret|token|api[_-]?key|authorization)\s*[:=]\s*[^\s,;]+/gi;
const LONG_DIGITS = /\b\d{7,}\b/g;

let sentry: SentryModule | null = null;

function sampleRate(value: string | undefined): number {
  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return 0;
  }

  return Math.min(1, Math.max(0, parsed));
}

export function readObservabilityConfig(
  env: ObservabilityEnv = process.env,
): ObservabilityConfig | null {
  const dsn = env.NEXT_PUBLIC_SENTRY_DSN?.trim();

  if (!dsn) {
    return null;
  }

  if (!dsn.startsWith("https://") && !dsn.startsWith("http://localhost")) {
    return null;
  }

  return {
    dsn,
    environment: env.NEXT_PUBLIC_SENTRY_ENVIRONMENT?.trim() || env.NODE_ENV?.trim() || "production",
    release: env.NEXT_PUBLIC_SENTRY_RELEASE?.trim() || undefined,
    tracesSampleRate: sampleRate(env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE),
  };
}

export function sanitizeText(value: string): string {
  return value
    .replace(SENSITIVE_QUERY, `$1${REDACTION}`)
    .replace(BEARER, `Bearer ${REDACTION}`)
    .replace(SECRET_ASSIGNMENT, (match) => {
      const separator = match.includes(":") ? ":" : "=";
      return `${match.split(separator)[0]}${separator}${REDACTION}`;
    })
    .replace(EMAIL, REDACTION)
    .replace(CNPJ, REDACTION)
    .replace(CPF, REDACTION)
    .replace(PHONE, REDACTION)
    .replace(LONG_DIGITS, REDACTION)
    .slice(0, MAX_TEXT_LENGTH);
}

function sanitizeTags(tags: Event["tags"]): Record<string, string> {
  const safeTags: Record<string, string> = {};

  for (const [key, value] of Object.entries(tags ?? {})) {
    if (typeof value === "string" && /^[a-z0-9_.-]{1,64}$/i.test(key)) {
      safeTags[key] = sanitizeText(value).slice(0, 200);
    }
  }

  return safeTags;
}

export function sanitizeEvent(event: ErrorEvent): ErrorEvent {
  const exceptions = event.exception?.values?.map((exception) => ({
    type: exception.type ? sanitizeText(exception.type) : undefined,
    value: exception.value ? sanitizeText(exception.value) : undefined,
  }));

  return {
    type: undefined,
    event_id: event.event_id,
    timestamp: event.timestamp,
    platform: event.platform,
    level: event.level,
    environment: event.environment,
    release: event.release,
    tags: sanitizeTags(event.tags),
    exception: exceptions && exceptions.length > 0 ? { values: exceptions } : undefined,
  } as ErrorEvent;
}

export function observabilityConfigured(env: ObservabilityEnv = process.env): boolean {
  return readObservabilityConfig(env) !== null;
}

export async function initObservability(env: ObservabilityEnv = process.env): Promise<boolean> {
  if (sentry !== null) {
    return true;
  }

  const config = readObservabilityConfig(env);

  if (config === null) {
    return false;
  }

  const sentryClient = await import("@sentry/browser");
  sentryClient.init({
    dsn: config.dsn,
    environment: config.environment,
    release: config.release,
    tracesSampleRate: config.tracesSampleRate,
    sendClientReports: false,
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      httpBodies: [],
      urlQueryParams: false,
      graphQL: { document: false, variables: false },
      genAI: { inputs: false, outputs: false },
      mcp: { inputs: false, outputs: false },
      databaseQueryData: false,
      queues: false,
      stackFrameVariables: false,
      frameContextLines: 0,
    },
    maxBreadcrumbs: 0,
    beforeBreadcrumb: () => null,
    beforeSend: (event) => sanitizeEvent(event),
  });
  sentry = sentryClient;
  return true;
}

export function reportBoundaryError(error: Error, boundary: string): void {
  if (sentry === null) {
    return;
  }

  sentry.captureException(error, {
    tags: { boundary: sanitizeText(boundary).slice(0, 64) },
  });
}

export function resetObservabilityForTests(): void {
  sentry = null;
}
