// Terminal detail view with output and input
import React, { useState, useEffect } from 'react';
import { Terminal, TerminalStatus } from '../../shared/types';
import { MessageFromWebview, MessageToWebview } from '../../shared/types';

interface TerminalDetailProps {
  terminal: Terminal;
  vscode: {
    postMessage(message: MessageFromWebview): void;
  };
  onBack: () => void;
}

const TerminalDetail: React.FC<TerminalDetailProps> = ({ terminal, vscode, onBack }) => {
  const [output, setOutput] = useState<string>('');
  const [inputMessage, setInputMessage] = useState('');
  const [outputMode, setOutputMode] = useState<'full' | 'last'>('full');
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    // Load initial output
    loadOutput();

    // Listen for output updates
    const handleMessage = (event: MessageEvent<MessageToWebview>) => {
      const message = event.data;
      if (message.type === 'updateTerminalOutput' && message.terminalId === terminal.id) {
        setOutput(message.output);
      }
    };

    window.addEventListener('message', handleMessage);

    // Auto-refresh interval
    let interval: NodeJS.Timeout | null = null;
    if (autoRefresh) {
      interval = setInterval(() => {
        loadOutput();
      }, 3000);
    }

    return () => {
      window.removeEventListener('message', handleMessage);
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [terminal.id, outputMode, autoRefresh]);

  const loadOutput = () => {
    vscode.postMessage({
      type: 'getOutput',
      terminalId: terminal.id,
      mode: outputMode
    });
  };

  const handleSendInput = () => {
    if (!inputMessage.trim()) {
      return;
    }

    vscode.postMessage({
      type: 'sendInput',
      terminalId: terminal.id,
      message: inputMessage
    });

    setInputMessage('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleSendInput();
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

  return (
    <div>
      <div className="toolbar">
        <button className="button button-secondary" onClick={onBack}>
          ← Back
        </button>
        <h2 style={{ margin: 0, fontSize: '16px', flex: 1 }}>
          Terminal: {terminal.name}
        </h2>
        <span className={getStatusBadgeClass(terminal.status)}>
          {terminal.status || 'UNKNOWN'}
        </span>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Terminal Info</div>
        </div>
        <div className="card-body">
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px', fontSize: '13px' }}>
            <strong>ID:</strong>
            <span>{terminal.id}</span>
            <strong>Provider:</strong>
            <span>{terminal.provider}</span>
            <strong>Session:</strong>
            <span>{terminal.session_name}</span>
            {terminal.agent_profile && (
              <>
                <strong>Agent Profile:</strong>
                <span>{terminal.agent_profile}</span>
              </>
            )}
            <strong>Created:</strong>
            <span>{terminal.created_at ? new Date(terminal.created_at).toLocaleString() : 'N/A'}</span>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Terminal Output</div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <select
              className="select"
              value={outputMode}
              onChange={e => setOutputMode(e.target.value as 'full' | 'last')}
              style={{ fontSize: '11px' }}
            >
              <option value="full">Full Output</option>
              <option value="last">Last Message</option>
            </select>
            <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={e => setAutoRefresh(e.target.checked)}
              />
              Auto-refresh
            </label>
            <button
              className="button"
              onClick={loadOutput}
              style={{ fontSize: '11px', padding: '4px 8px' }}
            >
              ⟳ Refresh
            </button>
          </div>
        </div>
        <div className="card-body">
          {output ? (
            <pre className="code-block">{output}</pre>
          ) : (
            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--vscode-descriptionForeground)' }}>
              No output available. Click refresh to load.
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Send Input</div>
        </div>
        <div className="card-body">
          <div className="form-group">
            <label className="form-label">Message</label>
            <textarea
              className="textarea form-input"
              value={inputMessage}
              onChange={e => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message here... (Ctrl+Enter to send)"
              rows={6}
            />
          </div>
          <div className="actions">
            <button
              className="button"
              onClick={handleSendInput}
              disabled={!inputMessage.trim()}
            >
              Send Message
            </button>
            <button
              className="button button-secondary"
              onClick={() => setInputMessage('')}
            >
              Clear
            </button>
          </div>
          <div style={{ fontSize: '11px', marginTop: '8px', opacity: 0.7 }}>
            Tip: Press Ctrl+Enter (Cmd+Enter on Mac) to send the message
          </div>
        </div>
      </div>
    </div>
  );
};

export default TerminalDetail;
