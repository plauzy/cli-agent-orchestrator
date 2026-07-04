import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { connectAGUI, pingInstance } from "../api";

// EventSource isn't in jsdom; install a stub that records construction
// + lets us push events into the registered listeners.
class StubEventSource {
  static last: StubEventSource | null = null;
  listeners = new Map<string, ((ev: MessageEvent) => void)[]>();
  url: string;
  onopen: (() => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    StubEventSource.last = this;
  }
  addEventListener(type: string, listener: (ev: MessageEvent) => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type)!.push(listener);
  }
  emit(type: string, data: unknown) {
    const evt = new MessageEvent(type, { data: JSON.stringify(data) });
    this.listeners.get(type)?.forEach((l) => l(evt));
  }
  close() {
    this.closed = true;
  }
}

beforeEach(() => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).EventSource = StubEventSource as any;
});
afterEach(() => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  delete (globalThis as any).EventSource;
});


describe("connectAGUI", () => {
  it("builds the URL with since + access_token query params", () => {
    connectAGUI({
      instanceUrl: "http://localhost:9889",
      since: "2026-05-01T00:00:00Z",
      accessToken: "abc",
      onEvent: () => {},
    });
    const url = StubEventSource.last!.url;
    expect(url).toContain("/agui/v1/stream");
    expect(url).toContain("since=2026-05-01");
    expect(url).toContain("access_token=abc");
  });

  it("dispatches each AG-UI typed event to onEvent with parsed data", () => {
    const events: { type: string; data: Record<string, unknown> }[] = [];
    connectAGUI({
      instanceUrl: "http://localhost:9889",
      onEvent: (e) => events.push(e),
    });
    const es = StubEventSource.last!;
    es.emit("RUN_STARTED", { thread_id: "cao-x", run_id: "cao-x" });
    es.emit("STEP_STARTED", { step_id: "abc12345", step_name: "developer" });
    es.emit("RAW", { cao_type: "terminal.interrupt", payload: {} });
    expect(events).toHaveLength(3);
    expect(events[0].type).toBe("RUN_STARTED");
    expect(events[0].data.thread_id).toBe("cao-x");
    expect(events[2].type).toBe("RAW");
    expect(events[2].data.cao_type).toBe("terminal.interrupt");
  });

  it("close() shuts the EventSource down", () => {
    const conn = connectAGUI({
      instanceUrl: "http://localhost:9889",
      onEvent: () => {},
    });
    conn.close();
    expect(StubEventSource.last!.closed).toBe(true);
  });
});


describe("pingInstance", () => {
  it("returns true when /health responds 200", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(new Response("OK", { status: 200 }));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (globalThis as any).fetch = fetchSpy;
    expect(await pingInstance("http://localhost:9889")).toBe(true);
    expect(fetchSpy.mock.calls[0][0]).toContain("/health");
  });

  it("returns false when /health rejects", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (globalThis as any).fetch = vi.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    expect(await pingInstance("http://localhost:9889")).toBe(false);
  });
});
