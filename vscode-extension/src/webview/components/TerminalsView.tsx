// Terminals list and management component
import React, { useState } from 'react';
import {
  Session,
  Terminal,
  CreateTerminalRequest,
  ProviderType,
  TerminalStatus
} from '../../shared/types';
import { MessageFromWebview } from '../../shared/types';
import TerminalDetail from './TerminalDetail';

interface TerminalsViewProps {
  session: Session | null;
  terminals: Terminal[];
  vscode: {
    postMessage(message: MessageFromWebview): void;
  };
}

const TerminalsView: React.FC<TerminalsViewProps> = ({ session, terminals, vscode }) => {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedTerminal, setSelectedTerminal] = useState<Terminal | null>(null);
  const [provider, setProvider] = useState<ProviderType>(ProviderType.Q_CLI);
  const [agentProfile, setAgentProfile] = useState('');
  const [windowName, setWindowName] = useState('');

  const handleCreateTerminal = () => {
    if (!session) {
      return;
    }

    const request: CreateTerminalRequest = {
      provider,
      agent_profile: agentProfile || undefined,
      window_name: windowName || undefined
    };

    vscode.postMessage({
      type: 'createTerminal',
      sessionName: session.name,
      request
    });

    setShowCreateForm(false);
    setAgentProfile('');
    setWindowName('');
  };

  const handleDeleteTerminal = (terminal: Terminal, event: React.MouseEvent) => {
    event.stopPropagation();
    if (confirm(`Are you sure you want to delete terminal "${terminal.id}"?`)) {
      vscode.postMessage({ type: 'deleteTerminal', terminalId: terminal.id });
      if (selectedTerminal?.id === terminal.id) {
        setSelectedTerminal(null);
      }
    }
  };

  const getStatusBadgeClass = (status?: TerminalStatus): string => {
    if (!status) {
      return 'status-badge';
    }
    switch (status) {
      case TerminalStatus.IDLE:
        return 'status-badge status-idle';
      case TerminalStatus.PROCESSING:
        return 'status-badge status-processing';
      case TerminalStatus.COMPLETED:
        return 'status-badge status-completed';
      case TerminalStatus.ERROR:
        return 'status-badge status-error';
      case TerminalStatus.WAITING_PERMISSION:
      case TerminalStatus.WAITING_USER_ANSWER:
        return 'status-badge status-waiting';
      default:
        return 'status-badge';
    }
  };

  if (!session) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">👈</div>
        <div className="empty-state-text">Select a session to view terminals</div>
      </div>
    );
  }

  if (selectedTerminal) {
    return (
      <TerminalDetail
        terminal={selectedTerminal}
        vscode={vscode}
        onBack={() => setSelectedTerminal(null)}
      />
    );
  }

  return (
    <div>
      <div className="toolbar">
        <h2 style={{ margin: 0, fontSize: '16px', flex: 1 }}>
          Terminals - {session.name}
        </h2>
        <button className="button" onClick={() => setShowCreateForm(!showCreateForm)}>
          + New Terminal
        </button>
      </div>

      {showCreateForm && (
        <div className="card">
          <h3 className="card-title">Create New Terminal</h3>
          <div className="card-body">
            <div className="form-group">
              <label className="form-label">Provider</label>
              <select
                className="select form-input"
                value={provider}
                onChange={e => setProvider(e.target.value as ProviderType)}
              >
                <option value={ProviderType.Q_CLI}>Q CLI</option>
                <option value={ProviderType.CLAUDE_CODE}>Claude Code</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Agent Profile (optional)</label>
              <input
                className="input form-input"
                type="text"
                placeholder="developer, reviewer, etc."
                value={agentProfile}
                onChange={e => setAgentProfile(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Window Name (optional)</label>
              <input
                className="input form-input"
                type="text"
                placeholder="Auto-generated if empty"
                value={windowName}
                onChange={e => setWindowName(e.target.value)}
              />
            </div>

            <div className="actions">
              <button className="button" onClick={handleCreateTerminal}>
                Create
              </button>
              <button
                className="button button-secondary"
                onClick={() => setShowCreateForm(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {terminals.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">💻</div>
          <div className="empty-state-text">No terminals in this session</div>
          <button className="button" onClick={() => setShowCreateForm(true)}>
            Create First Terminal
          </button>
        </div>
      ) : (
        <div>
          {terminals.map(terminal => (
            <div
              key={terminal.id}
              className="card"
              onClick={() => setSelectedTerminal(terminal)}
              style={{ cursor: 'pointer' }}
            >
              <div className="card-header">
                <div>
                  <div style={{ fontWeight: 600, marginBottom: '4px' }}>
                    {terminal.name}
                  </div>
                  <div style={{ fontSize: '12px', opacity: 0.8 }}>
                    ID: {terminal.id} • Provider: {terminal.provider}
                  </div>
                  {terminal.agent_profile && (
                    <div style={{ fontSize: '12px', opacity: 0.8 }}>
                      Agent: {terminal.agent_profile}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <span className={getStatusBadgeClass(terminal.status)}>
                    {terminal.status || 'UNKNOWN'}
                  </span>
                  <button
                    className="button button-danger"
                    onClick={e => handleDeleteTerminal(terminal, e)}
                    style={{ fontSize: '11px', padding: '4px 8px' }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default TerminalsView;
