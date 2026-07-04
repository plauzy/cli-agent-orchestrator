// AG-UI client for one CAO instance.
//
// Native EventSource doesn't support custom headers, so when CAO is
// running in auth-enabled mode the operator passes ?access_token=
// via the URL (RFC §6). In default-off mode the token is optional.

import type { AGUIEvent } from "./types";

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

export function connectAGUI(opts: AGUIConnectOptions): AGUIConnection {
  const url = new URL("/agui/v1/stream", opts.instanceUrl);
  if (opts.since) url.searchParams.set("since", opts.since);
  if (opts.accessToken) url.searchParams.set("access_token", opts.accessToken);

  const es = new EventSource(url.toString(), { withCredentials: false });
  // AG-UI uses typed events — register a listener for each AG-UI
  // typed-event name we care about. The wildcard `message` event is
  // the default; for typed events we listen explicitly.
  const types = [
    "RUN_STARTED",
    "RUN_FINISHED",
    "STEP_STARTED",
    "STEP_FINISHED",
    "TEXT_MESSAGE_CONTENT",
    "RAW",
  ];
  for (const type of types) {
    es.addEventListener(type, (ev) => {
      const msgEvent = ev as MessageEvent;
      let parsed: Record<string, unknown> = {};
      try {
        parsed = JSON.parse(msgEvent.data);
      } catch {
        parsed = { raw: msgEvent.data };
      }
      opts.onEvent({ type, data: parsed });
    });
  }
  if (opts.onError) es.onerror = opts.onError;
  if (opts.onOpen) es.onopen = opts.onOpen;
  return {
    close() {
      es.close();
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
