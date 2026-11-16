import {
  ApiError,
  createAnalysisResponseSchema,
  endpoints,
  getApiLocale,
  notifyForbidden,
  notifyRateLimited,
  notifyUnauthorized,
  problemSchema,
} from "@/lib/api";
import type { AnalysisKind, CreateAnalysisResponse } from "@/lib/api/schemas";

import { buildUploadFormData } from "./upload";

export type UploadProgress = {
  loaded: number;
  total: number;
  percent: number;
  lengthComputable: boolean;
};

export type UploadAnalysisInput = {
  file: File;
  kind: AnalysisKind;
  idempotencyKey: string;
};

export type UploadAnalysisOptions = {
  onProgress?: (progress: UploadProgress) => void;
  signal?: AbortSignal;
  locale?: string;
  xhrFactory?: () => XMLHttpRequest;
};

function toPercent(loaded: number, total: number): number {
  if (total <= 0) {
    return 0;
  }

  return Math.min(100, Math.max(0, Math.round((loaded / total) * 100)));
}

function parseRetryAfter(value: string | null): number | null {
  if (!value) {
    return null;
  }

  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds >= 0 ? Math.ceil(seconds) : null;
}

function apiErrorFromXhr(xhr: XMLHttpRequest): ApiError {
  const requestId = xhr.getResponseHeader("x-request-id");
  const retryAfterSeconds = parseRetryAfter(xhr.getResponseHeader("retry-after"));
  let payload: unknown = null;

  try {
    payload = xhr.responseText ? JSON.parse(xhr.responseText) : null;
  } catch {
    payload = null;
  }

  const parsed = problemSchema.safeParse(payload);

  if (parsed.success) {
    return new ApiError({
      status: xhr.status,
      code: parsed.data.code,
      title: parsed.data.title,
      detail: parsed.data.detail,
      requestId: parsed.data.request_id || requestId,
      instance: parsed.data.instance,
      retryAfterSeconds,
      evidence: parsed.data.evidence,
    });
  }

  return new ApiError({
    status: xhr.status,
    title: xhr.statusText || "Request failed",
    code: "http_error",
    detail: "The upload failed without a problem document.",
    requestId,
    retryAfterSeconds,
  });
}

export function uploadAnalysis(
  input: UploadAnalysisInput,
  options: UploadAnalysisOptions = {},
): Promise<CreateAnalysisResponse> {
  return new Promise((resolve, reject) => {
    const xhr = options.xhrFactory ? options.xhrFactory() : new XMLHttpRequest();
    let settled = false;

    function cleanup(): void {
      options.signal?.removeEventListener("abort", handleSignalAbort);
    }

    function fail(error: unknown): void {
      if (settled) {
        return;
      }

      settled = true;
      cleanup();
      reject(error);
    }

    function succeed(value: CreateAnalysisResponse): void {
      if (settled) {
        return;
      }

      settled = true;
      cleanup();
      resolve(value);
    }

    function handleSignalAbort(): void {
      if (settled) {
        return;
      }

      xhr.abort();
    }

    const total = input.file.size;
    options.onProgress?.({
      loaded: 0,
      total,
      percent: 0,
      lengthComputable: total > 0,
    });

    xhr.open("POST", endpoints.analyses.create, true);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Accept", "application/json");
    xhr.setRequestHeader("Idempotency-Key", input.idempotencyKey);

    const requestLocale = options.locale ?? getApiLocale();

    if (requestLocale) {
      xhr.setRequestHeader("Accept-Language", requestLocale);
    }

    xhr.upload.onprogress = (event) => {
      const loaded = event.loaded;
      const reportedTotal = event.lengthComputable ? event.total : total;

      options.onProgress?.({
        loaded,
        total: reportedTotal,
        percent: toPercent(loaded, reportedTotal),
        lengthComputable: event.lengthComputable,
      });
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        let payload: unknown = null;

        try {
          payload = xhr.responseText ? JSON.parse(xhr.responseText) : null;
        } catch (error) {
          fail(
            new ApiError({
              status: xhr.status,
              code: "invalid_response",
              title: "Invalid response",
              detail: "The upload response is not valid JSON.",
              requestId: xhr.getResponseHeader("x-request-id"),
              cause: error,
            }),
          );
          return;
        }

        const parsed = createAnalysisResponseSchema.safeParse(payload);

        if (!parsed.success) {
          fail(
            new ApiError({
              status: xhr.status,
              code: "response_schema_invalid",
              title: "Invalid response",
              detail: "The upload response did not match the expected schema.",
              requestId: xhr.getResponseHeader("x-request-id"),
              issues: parsed.error.issues,
            }),
          );
          return;
        }

        succeed(parsed.data);
        return;
      }

      const error = apiErrorFromXhr(xhr);

      if (error.status === 401) {
        notifyUnauthorized(error);
      }

      if (error.status === 403) {
        notifyForbidden(error);
      }

      if (error.status === 429) {
        notifyRateLimited(error);
      }

      fail(error);
    };

    xhr.onerror = () => {
      fail(
        new ApiError({
          status: 0,
          code: "network_error",
          title: "Network error",
          detail: "The upload could not reach the service.",
        }),
      );
    };

    xhr.onabort = () => {
      fail(new DOMException("The upload was aborted.", "AbortError"));
    };

    if (options.signal) {
      if (options.signal.aborted) {
        fail(new DOMException("The upload was aborted.", "AbortError"));
        return;
      }

      options.signal.addEventListener("abort", handleSignalAbort, { once: true });
    }

    try {
      xhr.send(buildUploadFormData(input));
    } catch (error) {
      fail(
        new ApiError({
          status: 0,
          code: "network_error",
          title: "Network error",
          detail: "The upload could not be started.",
          cause: error,
        }),
      );
    }
  });
}
