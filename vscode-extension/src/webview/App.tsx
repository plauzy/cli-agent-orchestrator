// Main React application component
import React, { useState, useEffect } from 'react';
import {
  Session,
  Terminal,
  Flow,
  MessageToWebview,
  MessageFromWebview
} from '../shared/types';
import SessionsView from './components/SessionsView';
import TerminalsView from './components/TerminalsView';
import FlowsView from './components/FlowsView';

declare const acquireVsCodeApi: () => {
  postMessage(message: MessageFromWebview): void;
  getState(): any;
  setState(state: any): void;
};

const vscode = acquireVsCodeApi();

type Tab = 'sessions' | 'flows';

interface Notification {
  id: number;
  type: 'success' | 'error' | 'info';
  message: string;
}

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('sessions');
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [terminals, setTerminals] = useState<Terminal[]>([]);
  const [flows, setFlows] = useState<Flow[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);

  useEffect(() => {
    // Request initial data
    vscode.postMessage({ type: 'getSessions' });

    // Listen for messages from extension
    const handleMessage = (event: MessageEvent<MessageToWebview>) => {
      const message = event.data;

      switch (message.type) {
        case 'updateSessions':
          setSessions(message.sessions);
          // If a session was selected, update it
          if (selectedSession) {
            const updated = message.sessions.find(s => s.name === selectedSession.name);
            if (updated) {
              setSelectedSession(updated);
            }
          }
          break;

        case 'updateTerminals':
          setTerminals(message.terminals);
          break;

        case 'updateFlows':
          setFlows(message.flows);
          break;

        case 'success':
          addNotification('success', message.message);
          break;

        case 'error':
          addNotification('error', message.message);
          break;

        case 'updateTerminalOutput':
          // Handle terminal output update
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [selectedSession]);

  const addNotification = (type: 'success' | 'error' | 'info', message: string) => {
    const id = Date.now();
    setNotifications(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 5000);
  };

  const handleSessionSelect = (session: Session) => {
    setSelectedSession(session);
    vscode.postMessage({ type: 'getTerminals', sessionName: session.name });
  };

  const handleRefresh = () => {
    vscode.postMessage({ type: 'getSessions' });
    if (activeTab === 'flows') {
      vscode.postMessage({ type: 'getFlows' });
    }
  };

  return (
    <div className="app-container">
      <div className="header">
        <h1>CLI Agent Orchestrator</h1>
        <button className="button" onClick={handleRefresh}>
          ⟳ Refresh
        </button>
      </div>

      {notifications.length > 0 && (
        <div style={{ padding: '0 16px' }}>
          {notifications.map(notification => (
            <div
              key={notification.id}
              className={`notification notification-${notification.type}`}
            >
              {notification.message}
            </div>
          ))}
        </div>
      )}

      <div className="tabs">
        <button
          className={`tab ${activeTab === 'sessions' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('sessions');
            vscode.postMessage({ type: 'getSessions' });
          }}
        >
          Sessions & Terminals
        </button>
        <button
          className={`tab ${activeTab === 'flows' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('flows');
            vscode.postMessage({ type: 'getFlows' });
          }}
        >
          Flows
        </button>
      </div>

      <div className="content">
        {activeTab === 'sessions' && (
          <div className="split-view">
            <div className="split-pane-left">
              <SessionsView
                sessions={sessions}
                selectedSession={selectedSession}
                onSessionSelect={handleSessionSelect}
                vscode={vscode}
              />
            </div>
            <div className="split-pane-right">
              <TerminalsView
                session={selectedSession}
                terminals={terminals}
                vscode={vscode}
              />
            </div>
          </div>
        )}

        {activeTab === 'flows' && <FlowsView flows={flows} vscode={vscode} />}
      </div>
    </div>
  );
};

export default App;
