import React from "react";

/**
 * Generative UI renderer for CAO.
 *
 * This is the frontend half of CAO's differentiator: a *heterogeneous* fleet of
 * CLI agents (Claude Code, Q, Kiro, Codex, Gemini, ...) can each author a UI
 * intent, and this component renders it *uniformly* — the operator cannot tell
 * (and does not care) which provider produced it.
 *
 * Safety mirrors the server (`services/agui_stream.py::GENERATIVE_UI_COMPONENTS`):
 * a closed allow-list of named components with JSON props. There is no HTML, no
 * script, no `dangerouslySetInnerHTML`, no `eval`. An unknown component renders a
 * visible, inert "unsupported" placeholder rather than anything the agent chose —
 * defense-in-depth on top of the server-side refusal.
 */

export interface GenerativeUIData {
  component: string;
  props?: Record<string, unknown>;
  terminal_id?: string | null;
  event_id?: string | null;
}

export interface GenerativeUIProps {
  data: GenerativeUIData;
  /** Optional action handler (approve/reject/choose). Read-only surfaces omit it. */
  onAction?: (action: string, payload: Record<string, unknown>) => void;
}

const str = (v: unknown, fallback = ""): string =>
  typeof v === "string" ? v : v == null ? fallback : String(v);

const num = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;

const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);

// The closed client allow-list. Mirrors the server set. A component missing
// here is rendered as an inert placeholder, never as agent-chosen markup.
const RENDERERS: Record<
  string,
  (props: Record<string, unknown>, onAction?: GenerativeUIProps["onAction"]) => React.ReactElement
> = {
  approval_card: (p, onAction) => (
    <div className="gen-ui gen-ui-approval" role="group" aria-label="approval request">
      <h4>{str(p.title, "Approval requested")}</h4>
      {p.detail ? <p className="gen-ui-detail">{str(p.detail)}</p> : null}
      {p.risk ? <span className={`gen-ui-risk risk-${str(p.risk)}`}>{str(p.risk)} risk</span> : null}
      <div className="gen-ui-actions">
        <button type="button" onClick={() => onAction?.("approve", p)} disabled={!onAction}>
          Approve
        </button>
        <button type="button" onClick={() => onAction?.("reject", p)} disabled={!onAction}>
          Reject
        </button>
      </div>
    </div>
  ),

  choice_prompt: (p, onAction) => (
    <div className="gen-ui gen-ui-choice" role="group" aria-label="choice prompt">
      <h4>{str(p.question, "Choose an option")}</h4>
      <ul>
        {arr(p.choices).map((c, i) => {
          const label = typeof c === "string" ? c : str((c as Record<string, unknown>)?.label, `Option ${i + 1}`);
          const value = typeof c === "string" ? c : str((c as Record<string, unknown>)?.value, label);
          return (
            <li key={i}>
              <button type="button" onClick={() => onAction?.("choose", { value })} disabled={!onAction}>
                {label}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  ),

  diff_summary: (p) => {
    const files = arr(p.files);
    return (
      <div className="gen-ui gen-ui-diff" role="group" aria-label="diff summary">
        <h4>{str(p.title, "Changes")}</h4>
        <ul>
          {files.map((f, i) => {
            const file = f as Record<string, unknown>;
            return (
              <li key={i}>
                <code>{str(file.path, "?")}</code>
                <span className="gen-ui-add">+{num(file.additions) ?? 0}</span>
                <span className="gen-ui-del">-{num(file.deletions) ?? 0}</span>
              </li>
            );
          })}
        </ul>
      </div>
    );
  },

  progress: (p) => {
    const value = num(p.value);
    const indeterminate = value == null;
    return (
      <div className="gen-ui gen-ui-progress" role="group" aria-label="progress">
        <span className="gen-ui-progress-label">{str(p.label, "Working…")}</span>
        <progress
          max={1}
          {...(indeterminate ? {} : { value: Math.max(0, Math.min(1, value)) })}
          aria-valuenow={indeterminate ? undefined : value}
        />
      </div>
    );
  },

  metric: (p) => (
    <div className="gen-ui gen-ui-metric" role="group" aria-label="metric">
      <span className="gen-ui-metric-label">{str(p.label, "metric")}</span>
      <span className="gen-ui-metric-value">
        {str(p.value, "—")}
        {p.unit ? <span className="gen-ui-metric-unit"> {str(p.unit)}</span> : null}
      </span>
    </div>
  ),

  agent_card: (p) => (
    <div className="gen-ui gen-ui-agent-card" role="group" aria-label="agent card">
      <strong>{str(p.name, "agent")}</strong>
      <span className="gen-ui-provider">{str(p.provider, "?")}</span>
      {p.status ? <span className={`gen-ui-status status-${str(p.status)}`}>{str(p.status)}</span> : null}
    </div>
  ),
};

/** Names this client can render — mirror of the server allow-list. */
export const SUPPORTED_COMPONENTS = Object.freeze(Object.keys(RENDERERS));

export function GenerativeUI({ data, onAction }: GenerativeUIProps): React.ReactElement {
  const renderer = RENDERERS[data.component];
  if (!renderer) {
    // Inert placeholder — never render an unknown, agent-chosen component.
    return (
      <div className="gen-ui gen-ui-unsupported" role="note" data-component={data.component}>
        Unsupported component: <code>{data.component}</code>
      </div>
    );
  }
  return renderer(data.props ?? {}, onAction);
}
