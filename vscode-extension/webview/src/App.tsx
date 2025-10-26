import { useState, useEffect } from 'react';
import {
  AppLayout,
  ContentLayout,
  Header,
  SpaceBetween,
  Container,
  SplitPanel
} from '@cloudscape-design/components';
import { SessionList } from './components/SessionList';
import { TerminalViewer } from './components/TerminalViewer';
import { AgentControls } from './components/AgentControls';
import { FlowManager } from './components/FlowManager';
import { useVSCodeAPI } from './hooks/useVSCodeAPI';
import { Session, Terminal, Flow } from './types';

function App() {
  const { sendMessage, onMessage } = useVSCodeAPI();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [terminals, setTerminals] = useState<Terminal[]>([]);
  const [flows, setFlows] = useState<Flow[]>([]);
  const [selectedTerminal, setSelectedTerminal] = useState<Terminal | null>(null);
  const [splitPanelOpen, setSplitPanelOpen] = useState(false);
  const [navigationOpen, setNavigationOpen] = useState(true);

  // Fetch data on mount
  useEffect(() => {
    sendMessage({ command: 'getSessions' });
    sendMessage({ command: 'getFlows' });

    // Set up auto-refresh
    const interval = setInterval(() => {
      sendMessage({ command: 'getSessions' });
      if (selectedTerminal) {
        sendMessage({
          command: 'getTerminalOutput',
          terminalId: selectedTerminal.id
        });
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [selectedTerminal]);

  // Handle messages from extension
  useEffect(() => {
    onMessage((message) => {
      switch (message.command) {
        case 'sessionsData':
          setSessions(message.data);
          // Fetch terminals for all sessions
          message.data.forEach((session: Session) => {
            sendMessage({
              command: 'getTerminals',
              sessionId: session.id
            });
          });
          break;

        case 'terminalsData':
          setTerminals((prev) => {
            const newTerminals = message.data;
            const merged = [...prev];
            newTerminals.forEach((newTerm: Terminal) => {
              const index = merged.findIndex(t => t.id === newTerm.id);
              if (index >= 0) {
                merged[index] = newTerm;
              } else {
                merged.push(newTerm);
              }
            });
            return merged;
          });
          break;

        case 'flowsData':
          setFlows(message.data);
          break;

        case 'agentLaunched':
          setTerminals((prev) => [...prev, message.data]);
          sendMessage({ command: 'getSessions' });
          break;

        case 'terminalDeleted':
          setTerminals((prev) => prev.filter(t => t.id !== message.terminalId));
          if (selectedTerminal?.id === message.terminalId) {
            setSelectedTerminal(null);
          }
          break;

        case 'error':
          console.error('Error from extension:', message.data);
          break;
      }
    });
  }, [selectedTerminal]);

  const handleTerminalSelect = (terminal: Terminal) => {
    setSelectedTerminal(terminal);
    setSplitPanelOpen(true);
    sendMessage({
      command: 'getTerminalOutput',
      terminalId: terminal.id
    });
  };

  const handleLaunchAgent = (agentProfile: string) => {
    sendMessage({
      command: 'launchAgent',
      agentProfile
    });
  };

  const handleDeleteTerminal = (terminalId: string) => {
    sendMessage({
      command: 'deleteTerminal',
      terminalId
    });
  };

  const handleSendInput = (terminalId: string, input: string) => {
    sendMessage({
      command: 'sendInput',
      terminalId,
      input
    });
  };

  const handleRunFlow = (flowName: string) => {
    sendMessage({
      command: 'runFlow',
      flowName
    });
  };

  return (
    <AppLayout
      headerSelector="#header"
      navigation={
        <SpaceBetween size="l">
          <AgentControls onLaunchAgent={handleLaunchAgent} />
          <FlowManager flows={flows} onRunFlow={handleRunFlow} />
        </SpaceBetween>
      }
      navigationOpen={navigationOpen}
      onNavigationChange={({ detail }) => setNavigationOpen(detail.open)}
      content={
        <ContentLayout
          header={
            <Header
              variant="h1"
              description="Multi-agent orchestration with TMUX session management"
            >
              CLI Agent Orchestrator
            </Header>
          }
        >
          <Container>
            <SessionList
              sessions={sessions}
              terminals={terminals}
              onTerminalSelect={handleTerminalSelect}
              onDeleteTerminal={handleDeleteTerminal}
              selectedTerminalId={selectedTerminal?.id}
            />
          </Container>
        </ContentLayout>
      }
      splitPanel={
        selectedTerminal && (
          <SplitPanel
            header={`Terminal: ${selectedTerminal.agent_profile} (${selectedTerminal.status})`}
            i18nStrings={{
              preferencesTitle: 'Split panel preferences',
              preferencesPositionLabel: 'Split panel position',
              preferencesPositionDescription: 'Choose the default split panel position.',
              preferencesPositionSide: 'Side',
              preferencesPositionBottom: 'Bottom',
              preferencesConfirm: 'Confirm',
              preferencesCancel: 'Cancel',
              closeButtonAriaLabel: 'Close panel',
              openButtonAriaLabel: 'Open panel',
              resizeHandleAriaLabel: 'Resize split panel'
            }}
          >
            <TerminalViewer
              terminal={selectedTerminal}
              onSendInput={handleSendInput}
            />
          </SplitPanel>
        )
      }
      splitPanelOpen={splitPanelOpen}
      onSplitPanelToggle={({ detail }) => setSplitPanelOpen(detail.open)}
      splitPanelPreferences={{ position: 'bottom' }}
      toolsHide
    />
  );
}

export default App;
