import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnalysisProgressEvent } from "@/lib/api/schemas";

import { createAnalysisStream, parseSseBlock, type EventSourceLike } from "./events";

const ANALYSIS_ID = "6f0f2b62-6e2a-4b67-8e3f-2d6f4e6a1b2c";

function event(status: AnalysisProgressEvent["status"] = "running"): AnalysisProgressEvent {
  return {
    id: ANALYSIS_ID,
    status,
    kind: "boleto",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:10Z",
    error_code: null,
    result_available: status === "completed",
    progress: {
      percent: status === "completed" ? 100 : 55,
      stage: status === "completed" ? "persistence" : "rag",
      detail: "Reranqueando",
      started_at: "2026-01-01T00:00:05Z",
      indeterminate: status === "running",
    },
    cancelled_at: null,
  };
}

class FakeSource implements EventSourceLike {
  readonly handlers = new Map<string, (message: MessageEvent<string>) => void>();
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;

  addEventListener(type: string, listener: (message: MessageEvent<string>) => void): void {
    this.handlers.set(type, listener);
  }

  close(): void {
    this.closed = true;
  }

  open(): void {
    this.onopen?.(new Event("open"));
  }

  fail(): void {
    this.onerror?.(new Event("error"));
  }

  emit(type: string, payload: unknown): void {
    const listener = this.handlers.get(type);
    listener?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
  }

  emitRaw(type: string, payload: string): void {
    const listener = this.handlers.get(type);
    listener?.({ data: payload } as MessageEvent<string>);
  }
}

describe("SSE parsing", () => {
  it("parses named events with multi-line data", () => {
    expect(parseSseBlock('event: progress\ndata: {"a":1}\ndata: {"b":2}\n\n')).toEqual({
      event: "progress",
      data: '{"a":1}\n{"b":2}',
    });
  });

  it("ignores comments and empty blocks", () => {
    expect(parseSseBlock(": ping\n\n")).toBeNull();
    expect(parseSseBlock("event: progress\n\n")).toBeNull();
  });
});

describe("analysis stream", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("parses progress and closes on done", () => {
    const sources: FakeSource[] = [];
    const states: string[] = [];
    const received: AnalysisProgressEvent[] = [];
    const stream = createAnalysisStream({
      url: "/api/v1/analyses/id/events",
      eventSourceFactory: () => {
        const source = new FakeSource();
        sources.push(source);
        return source;
      },
      onEvent: (item) => received.push(item),
      onStateChange: (state) => states.push(state),
    });

    const source = sources[0];
    expect(source).toBeDefined();
    source?.open();
    source?.emit("progress", event());
    source?.emit("done", event("completed"));

    expect(received).toHaveLength(2);
    expect(received[1]?.status).toBe("completed");
    expect(states).toContain("connected");
    expect(states.at(-1)).toBe("closed");
    expect(source?.closed).toBe(true);
    stream.close();
  });

  it("ignores malformed payloads", () => {
    const sources: FakeSource[] = [];
    const received: AnalysisProgressEvent[] = [];
    const stream = createAnalysisStream({
      url: "/events",
      eventSourceFactory: () => {
        const source = new FakeSource();
        sources.push(source);
        return source;
      },
      onEvent: (item) => received.push(item),
      onStateChange: () => undefined,
    });

    sources[0]?.emitRaw("progress", "{not-json");
    sources[0]?.emitRaw("progress", JSON.stringify({ id: "missing" }));

    expect(received).toEqual([]);
    stream.close();
  });

  it("falls back to polling after repeated connection errors", () => {
    vi.useFakeTimers();
    const sources: FakeSource[] = [];
    const states: string[] = [];
    const stream = createAnalysisStream({
      url: "/events",
      eventSourceFactory: () => {
        const source = new FakeSource();
        sources.push(source);
        return source;
      },
      onEvent: () => undefined,
      onStateChange: (state) => states.push(state),
    });

    sources[0]?.fail();
    expect(states.at(-1)).toBe("reconnecting");
    vi.advanceTimersByTime(1500);
    sources[1]?.fail();
    vi.advanceTimersByTime(1500);
    sources[2]?.fail();

    expect(sources).toHaveLength(3);
    expect(states.at(-1)).toBe("polling");
    expect(sources.every((source) => source.closed)).toBe(true);
    stream.close();
  });

  it("reconnects and resets the retry count when the connection opens", () => {
    vi.useFakeTimers();
    const sources: FakeSource[] = [];
    const states: string[] = [];
    const stream = createAnalysisStream({
      url: "/events",
      eventSourceFactory: () => {
        const source = new FakeSource();
        sources.push(source);
        return source;
      },
      onEvent: () => undefined,
      onStateChange: (state) => states.push(state),
    });

    sources[0]?.fail();
    vi.advanceTimersByTime(1500);
    sources[1]?.open();

    expect(states.at(-1)).toBe("connected");
    stream.close();
  });
});
