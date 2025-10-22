import React, { useState, useEffect } from 'react';
import { CAOClient } from '../api/caoClient';
import { Session, Terminal, AgentProfile } from '../types';
import { vscode } from '../utils/vscode';

interface OrchestrationPanelProps {
  client: CAOClient;
}

export const OrchestrationPanel: React.FC<OrchestrationPanelProps> = ({ client }) => {
  const [mode, setMode] = useState<'handoff' | 'assign' | 'send_message'>('handoff');
  const [sessions, setSessions] = useState<Session[]>([]);
  const [profiles, setProfiles] = useState<AgentProfile[]>([]);
  const [selectedSession, setSelectedSession] = useState('');
  const [selectedTerminal, setSelectedTerminal] = useState('');
  const [selectedProfile, setSelectedProfile] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [sessionsData, profilesData] = await Promise.all([
        client.getSessions(),
        client.getAgentProfiles(),
      ]);
      setSessions(sessionsData);
      setProfiles(profilesData);
    } catch (err: any) {
      vscode.showError(`Failed to load data: ${err.message}`);
    }
  };

  const getCurrentTerminals = (): Terminal[] => {
    if (!selectedSession) return [];
    const session = sessions.find(s => s.session_id === selectedSession);
    return session?.terminals || [];
  };

  const handleExecute = async () => {
    if (!message.trim()) {
      vscode.showError('Message is required');
      return;
    }

    if ((mode === 'handoff' || mode === 'assign') && !selectedProfile) {
      vscode.showError('Agent profile is required');
      return;
    }

    if (mode === 'send_message' && !selectedTerminal) {
      vscode.showError('Target terminal is required');
      return;
    }

    setLoading(true);
    try {
      let result;
      const fromTerminalId = selectedTerminal || getCurrentTerminals()[0]?.terminal_id;

      if (!fromTerminalId) {
        throw new Error('No terminal selected or available');
      }

      switch (mode) {
        case 'handoff':
          result = await client.handoff(fromTerminalId, selectedProfile, message);
          vscode.showInfo(`Handoff created to ${selectedProfile}`);
          break;
        case 'assign':
          result = await client.assign(fromTerminalId, selectedProfile, message);
          vscode.showInfo(`Task assigned to ${selectedProfile}`);
          break;
        case 'send_message':
          await client.sendMessage(selectedTerminal, message);
          vscode.showInfo('Message sent successfully');
          break;
      }

      setMessage('');
      await loadData();
    } catch (err: any) {
      vscode.showError(`Orchestration failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="orchestration-panel">
      <div className="section">
        <div className="section-header">
          <h2>Orchestration</h2>
        </div>

        <div className="alert info" style={{ marginBottom: '20px' }}>
          <strong>Orchestration Modes:</strong><br />
          • <strong>Handoff</strong>: Transfer control and wait for completion (synchronous)<br />
          • <strong>Assign</strong>: Spawn an independent agent task (asynchronous)<br />
          • <strong>Send Message</strong>: Communicate with an existing agent
        </div>

        <div className="orchestration-form">
          <div className="form-group">
            <label>Orchestration Mode</label>
            <div className="mode-selector">
              <button
                className={mode === 'handoff' ? 'mode-btn active' : 'mode-btn'}
                onClick={() => setMode('handoff')}
              >
                🔄 Handoff
              </button>
              <button
                className={mode === 'assign' ? 'mode-btn active' : 'mode-btn'}
                onClick={() => setMode('assign')}
              >
                ✨ Assign
              </button>
              <button
                className={mode === 'send_message' ? 'mode-btn active' : 'mode-btn'}
                onClick={() => setMode('send_message')}
              >
                💬 Send Message
              </button>
            </div>
          </div>

          <div className="form-group">
            <label>Session</label>
            <select
              value={selectedSession}
              onChange={e => {
                setSelectedSession(e.target.value);
                setSelectedTerminal('');
              }}
            >
              <option value="">Select a session</option>
              {sessions.map(session => (
                <option key={session.session_id} value={session.session_id}>
                  {session.name} ({session.terminals.length} terminals)
                </option>
              ))}
            </select>
          </div>

          {mode === 'send_message' && (
            <div className="form-group">
              <label>Target Terminal</label>
              <select
                value={selectedTerminal}
                onChange={e => setSelectedTerminal(e.target.value)}
              >
                <option value="">Select a terminal</option>
                {getCurrentTerminals().map(terminal => (
                  <option key={terminal.terminal_id} value={terminal.terminal_id}>
                    {terminal.agent_profile} - {terminal.status}
                  </option>
                ))}
              </select>
            </div>
          )}

          {(mode === 'handoff' || mode === 'assign') && (
            <div className="form-group">
              <label>Agent Profile</label>
              <select
                value={selectedProfile}
                onChange={e => setSelectedProfile(e.target.value)}
              >
                <option value="">Select an agent profile</option>
                {profiles.map(profile => (
                  <option key={profile.name} value={profile.name}>
                    {profile.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="form-group">
            <label>Message / Task</label>
            <textarea
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder={
                mode === 'handoff'
                  ? 'Describe the task to hand off...'
                  : mode === 'assign'
                  ? 'Describe the task to assign...'
                  : 'Enter your message...'
              }
              rows={6}
            />
          </div>

          <button
            className="primary"
            onClick={handleExecute}
            disabled={loading || !selectedSession || !message.trim()}
            style={{ width: '100%' }}
          >
            {loading ? 'Processing...' : `Execute ${mode.replace('_', ' ')}`}
          </button>
        </div>

        <div className="orchestration-help">
          <h3>Quick Guide</h3>
          <div className="help-section">
            <h4>🔄 Handoff</h4>
            <p>
              Transfer control to another agent and wait for completion. Use this when you need
              sequential task execution with results returned to the caller.
            </p>
            <p><em>Example: Code review workflow where results must be processed.</em></p>
          </div>
          <div className="help-section">
            <h4>✨ Assign</h4>
            <p>
              Spawn an independent agent to work on a task asynchronously. The agent continues
              working in the background and sends results back when complete.
            </p>
            <p><em>Example: Parallel test execution across multiple test suites.</em></p>
          </div>
          <div className="help-section">
            <h4>💬 Send Message</h4>
            <p>
              Send a message to an existing agent terminal. Messages are queued and delivered
              when the agent is idle. Use for iterative feedback or multi-turn conversations.
            </p>
            <p><em>Example: Providing additional context to a running agent.</em></p>
          </div>
        </div>
      </div>

      <style>{`
        .orchestration-form {
          background-color: var(--vscode-editor-background);
          border: 1px solid var(--vscode-panel-border);
          border-radius: 4px;
          padding: 20px;
          margin-bottom: 30px;
        }

        .mode-selector {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 10px;
        }

        .mode-btn {
          background-color: var(--vscode-button-secondaryBackground);
          color: var(--vscode-button-secondaryForeground);
          border: 2px solid transparent;
          padding: 12px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 13px;
          transition: all 0.2s;
        }

        .mode-btn:hover {
          background-color: var(--vscode-button-secondaryHoverBackground);
        }

        .mode-btn.active {
          background-color: var(--vscode-button-background);
          color: var(--vscode-button-foreground);
          border-color: var(--vscode-focusBorder);
        }

        .orchestration-help {
          background-color: var(--vscode-textBlockQuote-background);
          border-left: 4px solid var(--vscode-focusBorder);
          padding: 20px;
          border-radius: 4px;
        }

        .orchestration-help h3 {
          font-size: 15px;
          margin-bottom: 15px;
        }

        .help-section {
          margin-bottom: 20px;
        }

        .help-section:last-child {
          margin-bottom: 0;
        }

        .help-section h4 {
          font-size: 14px;
          margin-bottom: 8px;
        }

        .help-section p {
          font-size: 13px;
          line-height: 1.5;
          margin-bottom: 8px;
          opacity: 0.9;
        }

        .help-section em {
          font-size: 12px;
          opacity: 0.7;
        }
      `}</style>
    </div>
  );
};
