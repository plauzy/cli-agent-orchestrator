import React, { useState, useEffect } from 'react';
import { CAOClient } from '../api/caoClient';
import { Flow } from '../types';
import { vscode } from '../utils/vscode';

interface FlowManagerProps {
  client: CAOClient;
}

export const FlowManager: React.FC<FlowManagerProps> = ({ client }) => {
  const [flows, setFlows] = useState<Flow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadFlows();
    const interval = setInterval(loadFlows, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadFlows = async () => {
    try {
      const data = await client.getFlows();
      setFlows(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load flows');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleFlow = async (flowName: string, enabled: boolean) => {
    try {
      if (enabled) {
        await client.disableFlow(flowName);
      } else {
        await client.enableFlow(flowName);
      }
      await loadFlows();
      vscode.showInfo(`Flow "${flowName}" ${enabled ? 'disabled' : 'enabled'}`);
    } catch (err: any) {
      vscode.showError(`Failed to toggle flow: ${err.message}`);
    }
  };

  const handleRunFlow = async (flowName: string) => {
    try {
      await client.runFlow(flowName);
      vscode.showInfo(`Flow "${flowName}" started`);
    } catch (err: any) {
      vscode.showError(`Failed to run flow: ${err.message}`);
    }
  };

  const handleRemoveFlow = async (flowName: string) => {
    try {
      await client.removeFlow(flowName);
      await loadFlows();
      vscode.showInfo(`Flow "${flowName}" removed`);
    } catch (err: any) {
      vscode.showError(`Failed to remove flow: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert error">
        {error}
      </div>
    );
  }

  return (
    <div className="flow-manager">
      <div className="section">
        <div className="section-header">
          <h2>Scheduled Flows</h2>
        </div>

        <div className="alert info" style={{ marginBottom: '15px' }}>
          Flows are scheduled agent sessions that run automatically based on cron expressions.
          Use the CLI to add new flows: <code>cao flow add &lt;flow-file&gt;</code>
        </div>

        {flows.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">⏰</div>
            <div className="empty-state-message">
              No flows configured. Use the CLI to add flows.
            </div>
          </div>
        ) : (
          <div className="flows-list">
            {flows.map(flow => (
              <div key={flow.name} className="card">
                <div className="card-header">
                  <div className="card-title">
                    {flow.name}
                    {flow.enabled ? (
                      <span className="badge success" style={{ marginLeft: '10px' }}>Enabled</span>
                    ) : (
                      <span className="badge" style={{ marginLeft: '10px' }}>Disabled</span>
                    )}
                  </div>
                  <div className="card-actions">
                    <button
                      className="secondary"
                      onClick={() => handleRunFlow(flow.name)}
                    >
                      Run Now
                    </button>
                    <button
                      className={flow.enabled ? 'secondary' : 'primary'}
                      onClick={() => handleToggleFlow(flow.name, flow.enabled)}
                    >
                      {flow.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button
                      className="danger"
                      onClick={() => handleRemoveFlow(flow.name)}
                    >
                      Remove
                    </button>
                  </div>
                </div>

                <div className="flow-details">
                  <div className="flow-detail-row">
                    <span className="label">Schedule:</span>
                    <code>{flow.schedule}</code>
                  </div>
                  <div className="flow-detail-row">
                    <span className="label">Agent Profile:</span>
                    <span>{flow.agent_profile}</span>
                  </div>
                  {flow.next_run && (
                    <div className="flow-detail-row">
                      <span className="label">Next Run:</span>
                      <span>{new Date(flow.next_run).toLocaleString()}</span>
                    </div>
                  )}
                  {flow.script && (
                    <div className="flow-detail-row">
                      <span className="label">Script:</span>
                      <code>{flow.script}</code>
                    </div>
                  )}
                  <div className="flow-detail-row">
                    <span className="label">Prompt:</span>
                    <div className="flow-prompt">{flow.prompt}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <style>{`
        .flow-details {
          margin-top: 15px;
          padding-top: 15px;
          border-top: 1px solid var(--vscode-panel-border);
          font-size: 13px;
        }

        .flow-detail-row {
          display: flex;
          gap: 10px;
          margin-bottom: 8px;
        }

        .flow-detail-row .label {
          font-weight: 600;
          min-width: 120px;
        }

        .flow-prompt {
          flex: 1;
          padding: 8px;
          background-color: var(--vscode-textCodeBlock-background);
          border-radius: 4px;
          font-size: 12px;
          line-height: 1.5;
          white-space: pre-wrap;
        }

        code {
          background-color: var(--vscode-textCodeBlock-background);
          padding: 2px 6px;
          border-radius: 3px;
          font-family: var(--vscode-editor-font-family);
          font-size: 12px;
        }
      `}</style>
    </div>
  );
};
