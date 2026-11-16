import type { ApiError } from "./errors";

type ApiInterceptors = {
  onUnauthorized?: (error: ApiError) => void;
  onForbidden?: (error: ApiError) => void;
  onRateLimited?: (error: ApiError) => void;
};

let interceptors: ApiInterceptors = {};

export function configureApiInterceptors(next: ApiInterceptors): void {
  interceptors = next;
}

export function resetApiInterceptors(): void {
  interceptors = {};
}

function notify(handler: ((error: ApiError) => void) | undefined, error: ApiError): void {
  try {
    handler?.(error);
  } catch {
    return;
  }
}

export function notifyUnauthorized(error: ApiError): void {
  notify(interceptors.onUnauthorized, error);
}

export function notifyForbidden(error: ApiError): void {
  notify(interceptors.onForbidden, error);
}

export function notifyRateLimited(error: ApiError): void {
  notify(interceptors.onRateLimited, error);
}
