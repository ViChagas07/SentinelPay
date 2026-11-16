import type { ZodIssue } from "zod";

import { problemSchema } from "./schemas/common";

type ApiErrorOptions = {
  status: number;
  code: string;
  title: string;
  detail: string;
  requestId?: string | null;
  instance?: string | null;
  retryAfterSeconds?: number | null;
  issues?: ZodIssue[];
  evidence?: string[];
  cause?: unknown;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly title: string;
  readonly detail: string;
  readonly requestId: string | null;
  readonly instance: string | null;
  readonly retryAfterSeconds: number | null;
  readonly issues: ZodIssue[];
  readonly evidence: string[];

  constructor(options: ApiErrorOptions) {
    super(options.detail, { cause: options.cause });
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.title = options.title;
    this.detail = options.detail;
    this.requestId = options.requestId ?? null;
    this.instance = options.instance ?? null;
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
    this.issues = options.issues ?? [];
    this.evidence = options.evidence ?? [];
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

export function isUnauthorizedError(value: unknown): value is ApiError {
  return isApiError(value) && value.status === 401;
}

export function isForbiddenError(value: unknown): value is ApiError {
  return isApiError(value) && value.status === 403;
}

export function httpStatusToCode(status: number): string {
  switch (status) {
    case 400:
      return "bad_request";
    case 401:
      return "unauthorized";
    case 403:
      return "forbidden";
    case 404:
      return "not_found";
    case 405:
      return "method_not_allowed";
    case 409:
      return "conflict";
    case 413:
      return "request_too_large";
    case 422:
      return "validation_error";
    case 429:
      return "rate_limited";
    case 500:
      return "internal_error";
    case 503:
      return "service_unavailable";
    case 504:
      return "request_timeout";
    default:
      return "http_error";
  }
}

function parseRetryAfter(value: string | null): number | null {
  if (!value) {
    return null;
  }

  const seconds = Number(value);

  if (Number.isFinite(seconds) && seconds >= 0) {
    return Math.ceil(seconds);
  }

  const date = Date.parse(value);

  if (Number.isNaN(date)) {
    return null;
  }

  return Math.max(0, Math.ceil((date - Date.now()) / 1000));
}

export async function readApiError(response: Response): Promise<ApiError> {
  const headerRequestId = response.headers.get("x-request-id");
  const retryAfterSeconds = parseRetryAfter(response.headers.get("retry-after"));
  let payload: unknown = null;

  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  const parsed = problemSchema.safeParse(payload);

  if (parsed.success) {
    return new ApiError({
      status: response.status,
      code: parsed.data.code,
      title: parsed.data.title,
      detail: parsed.data.detail,
      requestId: parsed.data.request_id || headerRequestId,
      instance: parsed.data.instance,
      retryAfterSeconds,
      evidence: parsed.data.evidence,
    });
  }

  return new ApiError({
    status: response.status,
    code: httpStatusToCode(response.status),
    title: response.statusText || "Request failed",
    detail: "The API returned an error without a problem document.",
    requestId: headerRequestId,
    retryAfterSeconds,
  });
}
