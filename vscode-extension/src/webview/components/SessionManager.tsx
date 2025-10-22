import React, { useState, useEffect } from 'react';
import { CAOClient } from '../api/caoClient';
import { Session, Terminal } from '../types';
import { vscode } from '../utils/vscode';

interface SessionManagerProps {
  client: CAOClient;
}

export const SessionManager: React.FC<SessionManagerProps> = ({ client }) => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newSessionName, setNewSessionName] = useState('');
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [expandedSessions, setExpandedSessions] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadSessions();
    const interval = setInterval(loadSessions, 3000);
    return () => clearInterval(interval);
  }, []);

  const loadSessions = async () => {
    try {
      const data = await client.getSessions();
      setSessions(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSession = async () => {
    if (!newSessionName.trim()) {
      vscode.showError('Session name is required');
      return;
    }

    try {
      await client.createSession(newSessionName, selectedAgents);
      setShowCreateDialog(false);
      setNewSessionName('');
      setSelectedAgents([]);
      await loadSessions();
      vscode.showInfo(`Session "${newSessionName}" created successfully`);
    } catch (err: any) {
      vscode.showError(`Failed to create session: ${err.message}`);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await client.deleteSession(sessionId);
      await loadSessions();
      vscode.showInfo('Session deleted successfully');
    } catch (err: any) {
      vscode.showError(`Failed to delete session: ${err.message}`);
    }
  };

  const toggleSessionExpansion = (sessionId: string) => {
    const newExpanded = new Set(expandedSessions);
    if (newExpanded.has(sessionId)) {
      newExpanded.delete(sessionId);
    } else {
      newExpanded.add(sessionId);
    }
    setExpandedSessions(newExpanded);
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'IDLE': return 'info';
      case 'BUSY': return 'warning';
      case 'COMPLETED': return 'success';
      case 'ERROR': return 'error';
      default: return 'info';
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
    <div className="session-manager">
      <div className="section">
        <div className="section-header">
          <h2>Active Sessions</h2>
          <button className="primary" onClick={() => setShowCreateDialog(true)}>
            + New Session
          </button>
        </div>

        {sessions.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-message">
              No active sessions. Create one to get started.
            </div>
          </div>
        ) : (
          <div className="sessions-list">
            {sessions.map(session => (
              <div key={session.session_id} className="card">
                <div className="card-header">
                  <div
                    className="card-title"
                    style={{ cursor: 'pointer' }}
                    onClick={() => toggleSessionExpansion(session.session_id)}
                  >
                    <span style={{ marginRight: '8px' }}>
                      {expandedSessions.has(session.session_id) ? '▼' : '▶'}
                    </span>
                    {session.name}
                    <span style={{ marginLeft: '10px', fontSize: '12px', opacity: 0.7 }}>
                      ({session.terminals.length} terminal{session.terminals.length !== 1 ? 's' : ''})
                    </span>
                  </div>
                  <div className="card-actions">
                    <button
                      className="secondary"
                      onClick={() => vscode.openTerminal(session.name)}
                    >
                      Open Terminal
                    </button>
                    <button
                      className="danger"
                      onClick={() => handleDeleteSession(session.session_id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>

                {expandedSessions.has(session.session_id) && (
                  <div className="terminals-list">
                    {session.terminals.length === 0 ? (
                      <div style={{ padding: '10px', opacity: 0.7, fontSize: '12px' }}>
                        No terminals in this session
                      </div>
                    ) : (
                      session.terminals.map(terminal => (
                        <div key={terminal.terminal_id} className="terminal-item">
                          <div className="terminal-info">
                            <div className="terminal-header">
                              <strong>{terminal.agent_profile}</strong>
                              <span className={`badge ${getStatusBadgeClass(terminal.status)}`}>
                                {terminal.status}
                              </span>
                            </div>
                            <div style={{ fontSize: '11px', opacity: 0.7, marginTop: '4px' }}>
                              ID: {terminal.terminal_id}
                            </div>
                            {terminal.inbox.length > 0 && (
                              <div style={{ fontSize: '11px', marginTop: '4px' }}>
                                📬 {terminal.inbox.length} message{terminal.inbox.length !== 1 ? 's' : ''} in inbox
                              </div>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {showCreateDialog && (
        <div className="dialog-overlay" onClick={() => setShowCreateDialog(false)}>
          <div className="dialog" onClick={e => e.stopPropagation()}>
            <h3>Create New Session</h3>
            <div className="form-group">
              <label>Session Name</label>
              <input
                type="text"
                value={newSessionName}
                onChange={e => setNewSessionName(e.target.value)}
                placeholder="my-session"
              />
            </div>
            <div className="form-group">
              <label>Initial Agents (optional)</label>
              <input
                type="text"
                value={selectedAgents.join(', ')}
                onChange={e => setSelectedAgents(e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                placeholder="code_supervisor, developer"
              />
              <div className="help-text">
                Comma-separated list of agent profile names
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button className="secondary" onClick={() => setShowCreateDialog(false)}>
                Cancel
              </button>
              <button className="primary" onClick={handleCreateSession}>
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .terminals-list {
          margin-top: 15px;
          padding-top: 15px;
          border-top: 1px solid var(--vscode-panel-border);
        }

        .terminal-item {
          padding: 10px;
          background-color: var(--vscode-list-hoverBackground);
          border-radius: 4px;
          margin-bottom: 8px;
        }

        .terminal-info {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .terminal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .dialog-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background-color: rgba(0, 0, 0, 0.5);
          display: flex;
          justify-content: center;
          align-items: center;
          z-index: 1000;
        }

        .dialog {
          background-color: var(--vscode-editor-background);
          border: 1px solid var(--vscode-panel-border);
          border-radius: 4px;
          padding: 20px;
          min-width: 400px;
          max-width: 90%;
        }

        .dialog h3 {
          margin-bottom: 20px;
          font-size: 16px;
        }
      `}</style>
    </div>
  );
};
