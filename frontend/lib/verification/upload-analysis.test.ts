import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { resetApiInterceptors } from "@/lib/api/interceptors";
import { setApiLocale } from "@/lib/api/locale";

import { uploadAnalysis } from "./upload-analysis";

type FakeListener = ((event: ProgressEvent) => void) | null;

class FakeXhr {
  upload = { onprogress: null as FakeListener };
  status = 0;
  statusText = "OK";
  responseText = "";
  withCredentials = false;
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  method = "";
  url = "";
  headers: Record<string, string> = {};
  body: Document | XMLHttpRequestBodyInit | null = null;
  responseHeaders: Record<string, string> = {};

  open(method: string, url: string): void {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string): void {
    this.headers[name] = value;
  }

  getResponseHeader(name: string): string | null {
    return this.responseHeaders[name.toLowerCase()] ?? null;
  }

  send(body: Document | XMLHttpRequestBodyInit | null): void {
    this.body = body;
  }

  abort(): void {
    this.onabort?.();
  }

  progress(loaded: number, total: number, lengthComputable = true): void {
    this.upload.onprogress?.({
      loaded,
      total,
      lengthComputable,
    } as ProgressEvent);
  }

  respond(status: number, body: unknown): void {
    this.status = status;
    this.responseText = typeof body === "string" ? body : JSON.stringify(body);
    this.onload?.();
  }

  failNetwork(): void {
    this.onerror?.();
  }
}

function asXhr(xhr: FakeXhr): XMLHttpRequest {
  return xhr as unknown as XMLHttpRequest;
}

const FILE = new File([new Uint8Array([1, 2, 3])], "boleto.pdf", { type: "application/pdf" });

describe("uploadAnalysis", () => {
  beforeEach(() => {
    resetApiInterceptors();
    setApiLocale("pt-BR");
  });

  afterEach(() => {
    resetApiInterceptors();
    setApiLocale(undefined);
  });

  it("sends multipart with locale, idempotency key and reports real bytes", async () => {
    const xhr = new FakeXhr();
    const onProgress = vi.fn();
    const promise = uploadAnalysis(
      { file: FILE, kind: "boleto", idempotencyKey: "key-123456" },
      { onProgress, xhrFactory: () => asXhr(xhr) },
    );

    expect(xhr.method).toBe("POST");
    expect(xhr.url).toBe("/api/v1/analyses");
    expect(xhr.withCredentials).toBe(true);
    expect(xhr.headers["Idempotency-Key"]).toBe("key-123456");
    expect(xhr.headers["Accept-Language"]).toBe("pt-BR");
    expect(xhr.body).toBeInstanceOf(FormData);
    expect(onProgress).toHaveBeenCalledWith({
      loaded: 0,
      total: FILE.size,
      percent: 0,
      lengthComputable: true,
    });

    xhr.progress(2, 6);
    expect(onProgress).toHaveBeenLastCalledWith({
      loaded: 2,
      total: 6,
      percent: 33,
      lengthComputable: true,
    });

    xhr.respond(202, {
      analysis_id: "9bdfc8f1-7e3b-4f1f-8f79-8f0f9e1c2a11",
      status: "queued",
    });

    await expect(promise).resolves.toEqual({
      analysis_id: "9bdfc8f1-7e3b-4f1f-8f79-8f0f9e1c2a11",
      status: "queued",
    });
  });

  it("turns a problem response into a typed API error", async () => {
    const xhr = new FakeXhr();
    const promise = uploadAnalysis(
      { file: FILE, kind: "payslip", idempotencyKey: "key-123456" },
      { xhrFactory: () => asXhr(xhr) },
    );

    xhr.responseHeaders["x-request-id"] = "req-9";
    xhr.respond(413, {
      type: "https://paysentineliq.local/problems/upload_too_large",
      title: "Payload too large",
      status: 413,
      detail: "Upload exceeds the allowed size.",
      instance: "/api/v1/analyses",
      code: "upload_too_large",
      request_id: "req-9",
    });

    await expect(promise).rejects.toBeInstanceOf(ApiError);
    await expect(promise).rejects.toMatchObject({
      status: 413,
      code: "upload_too_large",
      requestId: "req-9",
    });
  });

  it("rejects invalid success payloads", async () => {
    const xhr = new FakeXhr();
    const promise = uploadAnalysis(
      { file: FILE, kind: "boleto", idempotencyKey: "key-123456" },
      { xhrFactory: () => asXhr(xhr) },
    );

    xhr.respond(202, { analysis_id: "not-a-uuid", status: "queued" });

    await expect(promise).rejects.toMatchObject({ code: "response_schema_invalid" });
  });

  it("supports cancellation through AbortController", async () => {
    const xhr = new FakeXhr();
    const controller = new AbortController();
    const promise = uploadAnalysis(
      { file: FILE, kind: "boleto", idempotencyKey: "key-123456" },
      { xhrFactory: () => asXhr(xhr), signal: controller.signal },
    );

    controller.abort();

    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
  });

  it("rejects immediately when the signal is already aborted", async () => {
    const xhr = new FakeXhr();
    const controller = new AbortController();
    controller.abort();

    const promise = uploadAnalysis(
      { file: FILE, kind: "boleto", idempotencyKey: "key-123456" },
      { xhrFactory: () => asXhr(xhr), signal: controller.signal },
    );

    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
    expect(xhr.body).toBeNull();
  });

  it("lets the caller force the interface locale", async () => {
    const xhr = new FakeXhr();
    const promise = uploadAnalysis(
      { file: FILE, kind: "boleto", idempotencyKey: "key-123456" },
      { xhrFactory: () => asXhr(xhr), locale: "es" },
    );

    expect(xhr.headers["Accept-Language"]).toBe("es");

    xhr.respond(202, {
      analysis_id: "9bdfc8f1-7e3b-4f1f-8f79-8f0f9e1c2a11",
      status: "queued",
    });

    await expect(promise).resolves.toMatchObject({ status: "queued" });
  });

  it("converts network failures into a typed API error", async () => {
    const xhr = new FakeXhr();
    const promise = uploadAnalysis(
      { file: FILE, kind: "boleto", idempotencyKey: "key-123456" },
      { xhrFactory: () => asXhr(xhr) },
    );

    xhr.failNetwork();

    await expect(promise).rejects.toMatchObject({ status: 0, code: "network_error" });
  });
});
