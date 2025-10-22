// Flows management component
import React, { useState } from 'react';
import { Flow } from '../../shared/types';
import { MessageFromWebview } from '../../shared/types';

interface FlowsViewProps {
  flows: Flow[];
  vscode: {
    postMessage(message: MessageFromWebview): void;
  };
}

const FlowsView: React.FC<FlowsViewProps> = ({ flows, vscode }) => {
  const [selectedFlow, setSelectedFlow] = useState<Flow | null>(null);

  const handleEnableFlow = (flowName: string) => {
    vscode.postMessage({ type: 'enableFlow', flowName });
  };

  const handleDisableFlow = (flowName: string) => {
    vscode.postMessage({ type: 'disableFlow', flowName });
  };

  const handleRunFlow = (flowName: string) => {
    if (confirm(`Are you sure you want to run flow "${flowName}" now?`)) {
      vscode.postMessage({ type: 'runFlow', flowName });
    }
  };

  const formatCronSchedule = (schedule: string): string => {
    // Simple cron description
    const parts = schedule.split(' ');
    if (parts.length === 5) {
      const [minute, hour, day, month, weekday] = parts;
      if (minute === '0' && hour === '9' && weekday === '1-5') {
        return 'Daily at 9:00 AM (weekdays)';
      }
      return `Cron: ${schedule}`;
    }
    return schedule;
  };

  if (flows.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">⚡</div>
        <div className="empty-state-text">
          No flows configured
        </div>
        <div style={{ fontSize: '13px', marginTop: '8px', opacity: 0.8 }}>
          Use the CLI to add flows: <code>cao flow add &lt;file&gt;</code>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="toolbar">
        <h2 style={{ margin: 0, fontSize: '16px', flex: 1 }}>
          Scheduled Flows ({flows.length})
        </h2>
      </div>

      <div style={{ display: 'grid', gap: '12px' }}>
        {flows.map(flow => (
          <div key={flow.name} className="card">
            <div className="card-header">
              <div>
                <div className="card-title">{flow.name}</div>
                <div style={{ fontSize: '12px', opacity: 0.8, marginTop: '4px' }}>
                  Agent: {flow.agent_profile}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span
                  className={`status-badge ${
                    flow.enabled ? 'status-idle' : 'status-badge'
                  }`}
                  style={{ opacity: flow.enabled ? 1 : 0.5 }}
                >
                  {flow.enabled ? 'ENABLED' : 'DISABLED'}
                </span>
                <button
                  className="button"
                  onClick={() => setSelectedFlow(selectedFlow?.name === flow.name ? null : flow)}
                  style={{ fontSize: '11px', padding: '4px 8px' }}
                >
                  {selectedFlow?.name === flow.name ? 'Hide Details' : 'Details'}
                </button>
              </div>
            </div>

            {selectedFlow?.name === flow.name && (
              <div className="card-body" style={{ borderTop: '1px solid var(--vscode-panel-border)', paddingTop: '12px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px', fontSize: '13px', marginBottom: '16px' }}>
                  <strong>Schedule:</strong>
                  <span>{formatCronSchedule(flow.schedule)}</span>

                  <strong>File Path:</strong>
                  <span style={{ fontFamily: 'monospace', fontSize: '12px' }}>{flow.file_path}</span>

                  {flow.script && (
                    <>
                      <strong>Script:</strong>
                      <span style={{ fontFamily: 'monospace', fontSize: '12px' }}>{flow.script}</span>
                    </>
                  )}

                  {flow.last_run && (
                    <>
                      <strong>Last Run:</strong>
                      <span>{new Date(flow.last_run).toLocaleString()}</span>
                    </>
                  )}

                  {flow.next_run && (
                    <>
                      <strong>Next Run:</strong>
                      <span>{new Date(flow.next_run).toLocaleString()}</span>
                    </>
                  )}
                </div>

                <div className="actions">
                  <button
                    className="button"
                    onClick={() => handleRunFlow(flow.name)}
                  >
                    ▶ Run Now
                  </button>

                  {flow.enabled ? (
                    <button
                      className="button button-secondary"
                      onClick={() => handleDisableFlow(flow.name)}
                    >
                      Disable
                    </button>
                  ) : (
                    <button
                      className="button"
                      onClick={() => handleEnableFlow(flow.name)}
                    >
                      Enable
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: '16px', backgroundColor: 'var(--vscode-textCodeBlock-background)' }}>
        <div className="card-header">
          <div className="card-title">💡 Flow Management</div>
        </div>
        <div className="card-body" style={{ fontSize: '13px' }}>
          <p>To manage flows, use the CAO CLI:</p>
          <ul style={{ marginLeft: '20px', marginTop: '8px' }}>
            <li><code>cao flow add &lt;file&gt;</code> - Add a new flow</li>
            <li><code>cao flow list</code> - List all flows</li>
            <li><code>cao flow remove &lt;name&gt;</code> - Remove a flow</li>
          </ul>
          <p style={{ marginTop: '12px', fontSize: '12px', opacity: 0.8 }}>
            Flow files are Markdown with YAML frontmatter defining the schedule and agent profile.
          </p>
        </div>
      </div>
    </div>
  );
};

export default FlowsView;
