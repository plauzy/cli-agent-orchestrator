import React, { useState, useEffect } from 'react';
import { SessionManager } from './components/SessionManager';
import { FlowManager } from './components/FlowManager';
import { AgentProfiles } from './components/AgentProfiles';
import { OrchestrationPanel } from './components/OrchestrationPanel';
import { CAOClient } from './api/caoClient';
import { VSCodeAPI } from './utils/vscode';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'sessions' | 'flows' | 'agents' | 'orchestrate'>('sessions');
  const [serverStatus, setServerStatus] = useState<'connected' | 'disconnected' | 'checking'>('checking');
  const [caoClient] = useState(() => new CAOClient('http://localhost:9889'));

  useEffect(() => {
    checkServerStatus();
    const interval = setInterval(checkServerStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const checkServerStatus = async () => {
    try {
      const health = await caoClient.getHealth();
      setServerStatus(health.status === 'ok' ? 'connected' : 'disconnected');
    } catch (error) {
      setServerStatus('disconnected');
    }
  };

  return (
    <div className="cao-app">
      <header className="cao-header">
        <h1>CLI Agent Orchestrator</h1>
        <div className={`status-indicator ${serverStatus}`}>
          <span className="status-dot"></span>
          {serverStatus === 'connected' ? 'Connected' :
           serverStatus === 'disconnected' ? 'Disconnected' :
           'Checking...'}
        </div>
      </header>

      <nav className="cao-nav">
        <button
          className={activeTab === 'sessions' ? 'active' : ''}
          onClick={() => setActiveTab('sessions')}
        >
          Sessions
        </button>
        <button
          className={activeTab === 'flows' ? 'active' : ''}
          onClick={() => setActiveTab('flows')}
        >
          Flows
        </button>
        <button
          className={activeTab === 'agents' ? 'active' : ''}
          onClick={() => setActiveTab('agents')}
        >
          Agent Profiles
        </button>
        <button
          className={activeTab === 'orchestrate' ? 'active' : ''}
          onClick={() => setActiveTab('orchestrate')}
        >
          Orchestrate
        </button>
      </nav>

      <main className="cao-main">
        {activeTab === 'sessions' && <SessionManager client={caoClient} />}
        {activeTab === 'flows' && <FlowManager client={caoClient} />}
        {activeTab === 'agents' && <AgentProfiles client={caoClient} />}
        {activeTab === 'orchestrate' && <OrchestrationPanel client={caoClient} />}
      </main>
    </div>
  );
};
