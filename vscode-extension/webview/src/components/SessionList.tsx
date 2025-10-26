import { useState } from 'react';
import {
  Table,
  Box,
  SpaceBetween,
  Badge,
  Button,
  Header,
  CollectionPreferences,
  StatusIndicator
} from '@cloudscape-design/components';
import { Session, Terminal } from '../types';

interface SessionListProps {
  sessions: Session[];
  terminals: Terminal[];
  onTerminalSelect: (terminal: Terminal) => void;
  onDeleteTerminal: (terminalId: string) => void;
  selectedTerminalId?: string;
}

export function SessionList({
  sessions,
  terminals,
  onTerminalSelect,
  onDeleteTerminal,
  selectedTerminalId
}: SessionListProps) {
  const [selectedItems, setSelectedItems] = useState<Terminal[]>([]);

  const getStatusIndicator = (status: Terminal['status']) => {
    switch (status) {
      case 'IDLE':
        return <StatusIndicator type="success">Idle</StatusIndicator>;
      case 'BUSY':
        return <StatusIndicator type="in-progress">Busy</StatusIndicator>;
      case 'COMPLETED':
        return <StatusIndicator type="success">Completed</StatusIndicator>;
      case 'ERROR':
        return <StatusIndicator type="error">Error</StatusIndicator>;
      default:
        return <StatusIndicator type="info">Unknown</StatusIndicator>;
    }
  };

  const terminalsWithSession = terminals.map(terminal => {
    const session = sessions.find(s => s.id === terminal.session_id);
    return {
      ...terminal,
      session_name: session?.name || 'Unknown Session'
    };
  });

  return (
    <Table
      onSelectionChange={({ detail }) => {
        setSelectedItems(detail.selectedItems);
        if (detail.selectedItems.length > 0) {
          onTerminalSelect(detail.selectedItems[0]);
        }
      }}
      selectedItems={selectedTerminalId ?
        terminalsWithSession.filter(t => t.id === selectedTerminalId) :
        selectedItems
      }
      ariaLabels={{
        selectionGroupLabel: 'Items selection',
        allItemsSelectionLabel: ({ selectedItems }) =>
          `${selectedItems.length} ${
            selectedItems.length === 1 ? 'item' : 'items'
          } selected`,
        itemSelectionLabel: ({ selectedItems }, item) => item.id
      }}
      columnDefinitions={[
        {
          id: 'session',
          header: 'Session',
          cell: item => item.session_name,
          sortingField: 'session_name'
        },
        {
          id: 'agent_profile',
          header: 'Agent Profile',
          cell: item => (
            <Badge color="blue">{item.agent_profile}</Badge>
          ),
          sortingField: 'agent_profile'
        },
        {
          id: 'status',
          header: 'Status',
          cell: item => getStatusIndicator(item.status),
          sortingField: 'status'
        },
        {
          id: 'created_at',
          header: 'Created',
          cell: item => new Date(item.created_at).toLocaleString(),
          sortingField: 'created_at'
        },
        {
          id: 'actions',
          header: 'Actions',
          cell: item => (
            <SpaceBetween direction="horizontal" size="xs">
              <Button
                variant="inline-link"
                onClick={() => onTerminalSelect(item)}
              >
                View
              </Button>
              <Button
                variant="inline-link"
                onClick={() => onDeleteTerminal(item.id)}
              >
                Delete
              </Button>
            </SpaceBetween>
          )
        }
      ]}
      items={terminalsWithSession}
      loadingText="Loading terminals"
      selectionType="single"
      trackBy="id"
      empty={
        <Box textAlign="center" color="inherit">
          <SpaceBetween size="m">
            <b>No active agent sessions</b>
            <Button
              onClick={() => {}}
              iconName="add-plus"
            >
              Launch Agent
            </Button>
          </SpaceBetween>
        </Box>
      }
      header={
        <Header
          counter={`(${terminals.length})`}
          description="Active agent terminals across all sessions"
        >
          Agent Terminals
        </Header>
      }
      preferences={
        <CollectionPreferences
          title="Preferences"
          confirmLabel="Confirm"
          cancelLabel="Cancel"
          preferences={{
            pageSize: 10,
            visibleContent: [
              'session',
              'agent_profile',
              'status',
              'created_at',
              'actions'
            ]
          }}
          pageSizePreference={{
            title: 'Page size',
            options: [
              { value: 10, label: '10 items' },
              { value: 20, label: '20 items' },
              { value: 50, label: '50 items' }
            ]
          }}
          visibleContentPreference={{
            title: 'Select visible columns',
            options: [
              {
                label: 'Terminal properties',
                options: [
                  { id: 'session', label: 'Session' },
                  { id: 'agent_profile', label: 'Agent Profile' },
                  { id: 'status', label: 'Status' },
                  { id: 'created_at', label: 'Created' },
                  { id: 'actions', label: 'Actions' }
                ]
              }
            ]
          }}
        />
      }
    />
  );
}
