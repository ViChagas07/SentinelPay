import { analysisProgressEventSchema, type AnalysisProgressEvent } from "@/lib/api/schemas";
import type { AnalysisStreamState } from "@/lib/verification/progress";

export type EventSourceLike = {
  addEventListener: (type: string, listener: (event: MessageEvent<string>) => void) => void;
  close: () => void;
  onopen: ((event: Event) => void) | null;
  onerror: ((event: Event) => void) | null;
};

export type EventSourceFactory = (url: string) => EventSourceLike;

export type AnalysisStreamOptions = {
  url: string;
  onEvent: (event: AnalysisProgressEvent) => void;
  onStateChange: (state: AnalysisStreamState) => void;
  eventSourceFactory?: EventSourceFactory;
  maxRetries?: number;
  retryDelayMs?: number;
};

export type ParsedSseBlock = {
  event: string;
  data: string;
};

export function parseSseBlock(block: string): ParsedSseBlock | null {
  let event = "message";
  const data: string[] = [];

  for (const line of block.split(/\r?\n/)) {
    if (line.length === 0 || line.startsWith(":")) {
      continue;
    }

    const separator = line.indexOf(":");
    if (separator < 0) {
      continue;
    }

    const field = line.slice(0, separator);
    const rawValue = line.slice(separator + 1);
    const value = rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue;

    if (field === "event") {
      event = value;
    } else if (field === "data") {
      data.push(value);
    }
  }

  if (data.length === 0) {
    return null;
  }

  return { event, data: data.join("\n") };
}

function parseEvent(payload: string): AnalysisProgressEvent | null {
  let raw: unknown;

  try {
    raw = JSON.parse(payload);
  } catch {
    return null;
  }

  const parsed = analysisProgressEventSchema.safeParse(raw);
  return parsed.success ? parsed.data : null;
}

export function createAnalysisStream(options: AnalysisStreamOptions): { close: () => void } {
  const factory = options.eventSourceFactory ?? ((url: string) => new EventSource(url));
  const maxRetries = options.maxRetries ?? 2;
  const retryDelayMs = options.retryDelayMs ?? 1500;
  let source: EventSourceLike | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let retries = 0;
  let closed = false;

  const close = (): void => {
    closed = true;
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
    source?.close();
    source = null;
  };

  const handleFrame = (raw: string): void => {
    const event = parseEvent(raw);
    if (event !== null) {
      options.onEvent(event);
    }
  };

  const connect = (): void => {
    if (closed) {
      return;
    }

    options.onStateChange(retries === 0 ? "connecting" : "reconnecting");

    try {
      source = factory(options.url);
    } catch {
      closed = true;
      options.onStateChange("polling");
      return;
    }

    source.onopen = () => {
      retries = 0;
      options.onStateChange("connected");
    };

    source.addEventListener("progress", (event) => {
      handleFrame(event.data);
    });

    source.addEventListener("done", (event) => {
      handleFrame(event.data);
      close();
      options.onStateChange("closed");
    });

    source.onerror = () => {
      source?.close();
      source = null;

      if (closed) {
        return;
      }

      retries += 1;

      if (retries > maxRetries) {
        closed = true;
        options.onStateChange("polling");
        return;
      }

      options.onStateChange("reconnecting");
      timer = setTimeout(() => {
        timer = null;
        connect();
      }, retryDelayMs);
    };
  };

  connect();

  return { close };
}
