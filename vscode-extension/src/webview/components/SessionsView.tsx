// Sessions list and management component
import React, { useState } from 'react';
import { Session, CreateSessionRequest, ProviderType } from '../../shared/types';
import { MessageFromWebview } from '../../shared/types';

interface SessionsViewProps {
  sessions: Session[];
  selectedSession: Session | null;
  onSessionSelect: (session: Session) => void;
  vscode: {
    postMessage(message: MessageFromWebview): void;
  };
}

const SessionsView: React.FC<SessionsViewProps> = ({
  sessions,
  selectedSession,
  onSessionSelect,
  vscode
}) => {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [provider, setProvider] = useState<ProviderType>(ProviderType.Q_CLI);
  const [agentProfile, setAgentProfile] = useState('');
  const [sessionName, setSessionName] = useState('');

  const handleCreateSession = () => {
    const request: CreateSessionRequest = {
      provider,
      agent_profile: agentProfile || undefined,
      session_name: sessionName || undefined,
      headless: false
    };

    vscode.postMessage({ type: 'createSession', request });
    setShowCreateForm(false);
    setAgentProfile('');
    setSessionName('');
  };

  const handleDeleteSession = (session: Session, event: React.MouseEvent) => {
    event.stopPropagation();
    if (confirm(`Are you sure you want to delete session "${session.name}"?`)) {
      vscode.postMessage({ type: 'deleteSession', sessionName: session.name });
    }
  };

  return (
    <div>
      <div className="toolbar">
        <h2 style={{ margin: 0, fontSize: '16px', flex: 1 }}>Sessions</h2>
        <button className="button" onClick={() => setShowCreateForm(!showCreateForm)}>
          + New Session
        </button>
      </div>

      {showCreateForm && (
        <div className="card">
          <h3 className="card-title">Create New Session</h3>
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
              <label className="form-label">Session Name (optional)</label>
              <input
                className="input form-input"
                type="text"
                placeholder="Auto-generated if empty"
                value={sessionName}
                onChange={e => setSessionName(e.target.value)}
              />
            </div>

            <div className="actions">
              <button className="button" onClick={handleCreateSession}>
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

      {sessions.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📦</div>
          <div className="empty-state-text">No sessions found</div>
          <button className="button" onClick={() => setShowCreateForm(true)}>
            Create First Session
          </button>
        </div>
      ) : (
        <div>
          {sessions.map(session => (
            <div
              key={session.id}
              className={`list-item ${
                selectedSession?.id === session.id ? 'selected' : ''
              }`}
              onClick={() => onSessionSelect(session)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, marginBottom: '4px' }}>
                    {session.name}
                  </div>
                  <div style={{ fontSize: '12px', opacity: 0.8 }}>
                    Status: {session.status}
                    {session.terminals && ` • ${session.terminals.length} terminal(s)`}
                  </div>
                </div>
                <button
                  className="button button-danger"
                  onClick={e => handleDeleteSession(session, e)}
                  style={{ fontSize: '11px', padding: '4px 8px' }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SessionsView;
