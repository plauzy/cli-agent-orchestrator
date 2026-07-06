// AG-UI client for one CAO instance.
//
// Native EventSource can't set custom headers, so when CAO runs in
// auth-enabled mode the operator passes the JWT via ?access_token= in the URL
// (read from location.search by the caller). In default-off mode it's optional.

import type { AGUIEvent } from "./types";

// Every AG-UI typed event the server emits. Native EventSource delivers typed
// events only to listeners registered for that exact event name (the default
// `message` handler never fires for named frames), so we must subscribe to
// each one explicitly — otherwise GENERATIVE_UI / STATE_* / TOOL_CALL_* /
// RUN_ERROR frames are silently dropped by the client.
export const AGUI_EVENT_TYPES = [
  "RUN_STARTED",
  "RUN_FINISHED",
  "RUN_ERROR",
  "STEP_STARTED",
  "STEP_FINISHED",
  "TEXT_MESSAGE_CONTENT",
  "TOOL_CALL_START",
  "STATE_SNAPSHOT",
  "STATE_DELTA",
  "GENERATIVE_UI",
  "RAW",
] as const;

export interface AGUIConnectOptions {
  instanceUrl: string;
  accessToken?: string;
  since?: string;
  onEvent(event: AGUIEvent): void;
  onError?(err: Event): void;
  onOpen?(): void;
}

export interface AGUIConnection {
  close(): void;
}

/** Read the access token from the page URL (?access_token=…), if present. */
export function accessTokenFromLocation(): string | undefined {
  if (typeof window === "undefined" || !window.location) return undefined;
  return new URLSearchParams(window.location.search).get("access_token") ?? undefined;
}

/**
 * Connect to `/agui/v1/stream` with automatic reconnection.
 *
 * Native EventSource reconnects on its own but cannot resume from `?since=`,
 * so we manage reconnection ourselves: on a dropped connection we back off and
 * reopen with `since` set to the newest event timestamp we've seen, so the
 * client resumes without a gap (the server replays buffered history; the client
 * dedupes by event id).
 */
export function connectAGUI(opts: AGUIConnectOptions): AGUIConnection {
  let es: EventSource | null = null;
  let closed = false;
  let since = opts.since;
  let retry = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  function scheduleReconnect() {
    if (closed || reconnectTimer) return;
    es?.close();
    const delay = Math.min(1000 * 2 ** retry, 15000); // capped exponential backoff
    retry += 1;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      open();
    }, delay);
  }

  function open() {
    if (closed) return;
    const url = new URL("/agui/v1/stream", opts.instanceUrl);
    if (since) url.searchParams.set("since", since);
    if (opts.accessToken) url.searchParams.set("access_token", opts.accessToken);

    es = new EventSource(url.toString(), { withCredentials: false });

    es.onopen = () => {
      retry = 0;
      opts.onOpen?.();
    };
    es.onerror = (err) => {
      opts.onError?.(err);
      if (closed) return;
      // Always take over reconnection. A dropped connection leaves the native
      // EventSource in CONNECTING and it retries its ORIGINAL URL — which
      // would silently drop the ?since= cursor and lose the gap replay. Close
      // it and reopen with the up-to-date cursor instead.
      es?.close();
      scheduleReconnect();
    };

    for (const type of AGUI_EVENT_TYPES) {
      es.addEventListener(type, (ev) => {
        const msgEvent = ev as MessageEvent;
        let parsed: Record<string, unknown> = {};
        try {
          parsed = JSON.parse(msgEvent.data);
        } catch {
          parsed = { raw: msgEvent.data };
        }
        // Track the newest event timestamp so a reconnect can resume via ?since=.
        const ts = parsed["timestamp"];
        if (typeof ts === "string") since = ts;
        opts.onEvent({ type, data: parsed });
      });
    }
  }

  open();

  return {
    close() {
      closed = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      es?.close();
    },
  };
}

// Lightweight health probe used by the InstancePicker before persisting
// a new instance.
export async function pingInstance(url: string, signal?: AbortSignal): Promise<boolean> {
  try {
    const resp = await fetch(new URL("/health", url).toString(), {
      method: "GET",
      signal,
    });
    return resp.ok;
  } catch {
    return false;
  }
}
