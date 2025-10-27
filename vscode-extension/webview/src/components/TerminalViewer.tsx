import { useState, useEffect, useRef } from 'react';
import {
  Container,
  Header,
  SpaceBetween,
  Input,
  Button,
  Box,
  Tabs
} from '@cloudscape-design/components';
import { Terminal } from '../types';
import { useVSCodeAPI } from '../hooks/useVSCodeAPI';

interface TerminalViewerProps {
  terminal: Terminal;
  onSendInput: (terminalId: string, input: string) => void;
}

export function TerminalViewer({ terminal, onSendInput }: TerminalViewerProps) {
  const { sendMessage, onMessage } = useVSCodeAPI();
  const [output, setOutput] = useState<string>('');
  const [input, setInput] = useState('');
  const outputRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    // Fetch initial output
    sendMessage({
      command: 'getTerminalOutput',
      terminalId: terminal.id
    });

    // Listen for output updates
    const cleanup = onMessage((message) => {
      if (
        message.command === 'terminalOutput' &&
        message.terminalId === terminal.id
      ) {
        setOutput(message.data);
      }
    });

    return cleanup;
  }, [terminal.id]);

  useEffect(() => {
    // Auto-scroll to bottom
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const handleSendInput = () => {
    if (input.trim()) {
      onSendInput(terminal.id, input);
      setInput('');
    }
  };

  const handleKeyPress = (event: any) => {
    if (event.detail?.key === 'Enter') {
      event.preventDefault();
      handleSendInput();
    }
  };

  return (
    <SpaceBetween size="l">
      <Container
        header={
          <Header
            variant="h2"
            description={`Terminal ID: ${terminal.id}`}
          >
            {terminal.agent_profile}
          </Header>
        }
      >
        <Tabs
          tabs={[
            {
              label: 'Output',
              id: 'output',
              content: (
                <Box padding={{ vertical: 's' }}>
                  <pre
                    ref={outputRef}
                    style={{
                      backgroundColor: 'var(--vscode-terminal-background)',
                      color: 'var(--vscode-terminal-foreground)',
                      padding: '12px',
                      borderRadius: '4px',
                      maxHeight: '400px',
                      overflowY: 'auto',
                      fontFamily: 'var(--vscode-editor-font-family)',
                      fontSize: 'var(--vscode-editor-font-size)',
                      whiteSpace: 'pre-wrap',
                      wordWrap: 'break-word'
                    }}
                  >
                    {output || 'No output yet...'}
                  </pre>
                </Box>
              )
            },
            {
              label: 'Info',
              id: 'info',
              content: (
                <Box padding={{ vertical: 's' }}>
                  <SpaceBetween size="s">
                    <div>
                      <strong>Session ID:</strong> {terminal.session_id}
                    </div>
                    <div>
                      <strong>Status:</strong> {terminal.status}
                    </div>
                    <div>
                      <strong>Created:</strong>{' '}
                      {new Date(terminal.created_at).toLocaleString()}
                    </div>
                    <div>
                      <strong>Updated:</strong>{' '}
                      {new Date(terminal.updated_at).toLocaleString()}
                    </div>
                  </SpaceBetween>
                </Box>
              )
            }
          ]}
        />
      </Container>

      <Container header={<Header variant="h3">Send Input</Header>}>
        <SpaceBetween size="s">
          <Input
            value={input}
            onChange={({ detail }) => setInput(detail.value)}
            onKeyDown={handleKeyPress}
            placeholder="Enter command or message for the agent..."
            disabled={terminal.status !== 'IDLE'}
            type="text"
          />
          <Button
            variant="primary"
            onClick={handleSendInput}
            disabled={terminal.status !== 'IDLE' || !input.trim()}
          >
            Send
          </Button>
          {terminal.status !== 'IDLE' && (
            <Box color="text-status-info">
              Agent is currently {terminal.status.toLowerCase()}. Please wait...
            </Box>
          )}
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
