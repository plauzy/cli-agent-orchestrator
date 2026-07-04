import React, { useEffect, useReducer, useState } from "react";
import { accessTokenFromLocation, connectAGUI } from "../api";
import type { AGUIEvent, CaoInstance, SessionSummary, TerminalSummary } from "../types";
import { GenerativeUI, type GenerativeUIData } from "./GenerativeUI";

interface State {
  sessions: Map<string, SessionSummary>;
  terminals: Map<string, TerminalSummary>;
  raw: AGUIEvent[];
  generative: GenerativeUIData[];
}

const EMPTY: State = {
  sessions: new Map(),
  terminals: new Map(),
  raw: [],
  generative: [],
};

function reducer(state: State, event: AGUIEvent): State {
  // Pure reducer over AG-UI typed events. The wire payload uses the
  // shape from services/agui_stream.py::to_agui_event.
  const data = event.data;
  if (event.type === "RUN_STARTED") {
    const name = String(data.thread_id ?? "");
    const sessions = new Map(state.sessions);
    sessions.set(name, { name, active_terminals: new Set() });
    return { ...state, sessions };
  }
  if (event.type === "RUN_FINISHED") {
    const name = String(data.thread_id ?? "");
    const sessions = new Map(state.sessions);
    sessions.delete(name);
    return { ...state, sessions };
  }
  if (event.type === "STEP_STARTED") {
    const tid = String(data.step_id ?? "");
    const terminals = new Map(state.terminals);
    terminals.set(tid, {
      id: tid,
      agent_name: (data.step_name as string | null) ?? null,
      provider: (data.provider as string | null) ?? null,
      status: "running",
    });
    return { ...state, terminals };
  }
  if (event.type === "STEP_FINISHED") {
    const tid = String(data.step_id ?? "");
    const terminals = new Map(state.terminals);
    const existing = terminals.get(tid);
    if (existing) {
      terminals.set(tid, { ...existing, status: "terminated" });
    }
    return { ...state, terminals };
  }
  if (event.type === "GENERATIVE_UI") {
    // Agent-authored UI intent. Keep the last 20 for the live surface.
    const gen: GenerativeUIData = {
      component: String(data.component ?? ""),
      props: (data.props as Record<string, unknown> | undefined) ?? {},
      terminal_id: (data.terminal_id as string | null | undefined) ?? null,
      event_id: (data.event_id as string | null | undefined) ?? null,
    };
    return { ...state, generative: [...state.generative, gen].slice(-20) };
  }
  if (event.type === "RAW" || event.type === "TEXT_MESSAGE_CONTENT") {
    // Keep last 100 raw / message events for the live ticker.
    return {
      ...state,
      raw: [...state.raw, event].slice(-100),
    };
  }
  return state;
}

interface Props {
  instance: CaoInstance;
}

export function InstanceTab({ instance }: Props) {
  const [state, dispatch] = useReducer(reducer, EMPTY);
  const [connection, setConnection] = useState<"connecting" | "open" | "error">(
    "connecting",
  );

  useEffect(() => {
    const conn = connectAGUI({
      instanceUrl: instance.url,
      // Auth-enabled CAO: EventSource can't send headers, so the JWT rides in
      // the URL (?access_token=). Picked up from the PWA's own location.
      accessToken: accessTokenFromLocation(),
      onOpen: () => setConnection("open"),
      onError: () => setConnection("error"),
      onEvent: (event) => dispatch(event),
    });
    return () => conn.close();
  }, [instance.url]);

  return (
    <section className="cao-pwa-tab">
      <header>
        <h2>{instance.label}</h2>
        <span className={`cao-pwa-status ${connection}`}>
          {connection === "open" ? "● connected" : connection === "connecting" ? "○ connecting" : "✗ error"}
        </span>
        <code>{instance.url}</code>
      </header>

      <div className="cao-pwa-grid">
        <article>
          <h3>Sessions ({state.sessions.size})</h3>
          {state.sessions.size === 0 ? (
            <p className="cao-pwa-empty">No active sessions.</p>
          ) : (
            <ul>
              {Array.from(state.sessions.values()).map((s) => (
                <li key={s.name}>{s.name}</li>
              ))}
            </ul>
          )}
        </article>

        <article>
          <h3>Terminals ({state.terminals.size})</h3>
          {state.terminals.size === 0 ? (
            <p className="cao-pwa-empty">No terminals.</p>
          ) : (
            <ul>
              {Array.from(state.terminals.values()).map((t) => (
                <li key={t.id} className={`cao-pwa-terminal ${t.status}`}>
                  <strong>{t.agent_name ?? "?"}</strong>
                  <span className="cao-pwa-provider">{t.provider ?? "?"}</span>
                  <span className="cao-pwa-status-pill">{t.status}</span>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article>
          <h3>Generative UI ({state.generative.length})</h3>
          {state.generative.length === 0 ? (
            <p className="cao-pwa-empty">No agent-authored UI yet.</p>
          ) : (
            <div className="cao-pwa-generative">
              {state.generative.map((g, i) => (
                <GenerativeUI key={g.event_id ?? i} data={g} />
              ))}
            </div>
          )}
        </article>

        <article>
          <h3>Event stream</h3>
          {state.raw.length === 0 ? (
            <p className="cao-pwa-empty">No events yet.</p>
          ) : (
            <ol className="cao-pwa-events">
              {state.raw.map((e, i) => (
                <li key={i}>
                  <strong>{e.type}</strong>{" "}
                  {String(e.data.cao_type ?? "")}
                </li>
              ))}
            </ol>
          )}
        </article>
      </div>
    </section>
  );
}
