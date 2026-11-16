import type { ZodType } from "zod";

import { ApiError } from "./errors";
import { notifyForbidden, notifyRateLimited, notifyUnauthorized } from "./interceptors";
import { getApiLocale } from "./locale";
import { handleResponse } from "./response";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type QueryValue = string | number | boolean | null | undefined;

export type QueryParams = Record<string, QueryValue | QueryValue[]>;

export type ApiFetchOptions<T> = {
  method?: HttpMethod;
  schema?: ZodType<T>;
  body?: unknown;
  formData?: FormData;
  query?: QueryParams;
  headers?: HeadersInit;
  signal?: AbortSignal;
  idempotencyKey?: string;
  locale?: string;
};

function appendQuery(url: URL, query: QueryParams | undefined): void {
  if (!query) {
    return;
  }

  for (const [key, rawValue] of Object.entries(query)) {
    const values = Array.isArray(rawValue) ? rawValue : [rawValue];

    for (const value of values) {
      if (value === undefined || value === null) {
        continue;
      }

      url.searchParams.append(key, String(value));
    }
  }
}

export async function apiFetch<T = void>(
  path: string,
  options: ApiFetchOptions<T> = {},
): Promise<T> {
  if (options.body !== undefined && options.formData !== undefined) {
    throw new ApiError({
      status: 0,
      code: "invalid_request",
      title: "Invalid request",
      detail: "Use either a JSON body or form data, not both.",
    });
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(normalizedPath, window.location.origin);
  appendQuery(url, options.query);

  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  const locale = options.locale ?? getApiLocale();

  if (locale && !headers.has("Accept-Language")) {
    headers.set("Accept-Language", locale);
  }

  if (options.idempotencyKey) {
    headers.set("Idempotency-Key", options.idempotencyKey);
  }

  let requestBody: BodyInit | undefined;

  if (options.formData) {
    requestBody = options.formData;
  } else if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    requestBody = JSON.stringify(options.body);
  }

  let response: Response;

  try {
    response = await fetch(url.toString(), {
      method: options.method ?? "GET",
      headers,
      body: requestBody,
      credentials: "include",
      cache: "no-store",
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }

    throw new ApiError({
      status: 0,
      code: "network_error",
      title: "Network error",
      detail: "The service could not be reached.",
      cause: error,
    });
  }

  if (!response.ok) {
    let apiError: ApiError;

    try {
      await handleResponse(response);
      apiError = new ApiError({
        status: response.status,
        code: "http_error",
        title: "Request failed",
        detail: "The request failed without a problem document.",
      });
    } catch (error) {
      if (!(error instanceof ApiError)) {
        throw error;
      }

      apiError = error;
    }

    if (apiError.status === 401) {
      notifyUnauthorized(apiError);
    }

    if (apiError.status === 403) {
      notifyForbidden(apiError);
    }

    if (apiError.status === 429) {
      notifyRateLimited(apiError);
    }

    throw apiError;
  }

  return handleResponse(response, options.schema);
}

export { API_V1_PREFIX } from "./config";
