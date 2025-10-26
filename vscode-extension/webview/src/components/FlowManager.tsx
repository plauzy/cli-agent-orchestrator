import {
  Container,
  Header,
  Table,
  Button,
  Badge,
  SpaceBetween,
  Box
} from '@cloudscape-design/components';
import { Flow } from '../types';

interface FlowManagerProps {
  flows: Flow[];
  onRunFlow: (flowName: string) => void;
}

export function FlowManager({ flows, onRunFlow }: FlowManagerProps) {
  return (
    <Container
      header={
        <Header
          variant="h2"
          description="Scheduled agent workflows"
          counter={`(${flows.length})`}
        >
          Flows
        </Header>
      }
    >
      <Table
        columnDefinitions={[
          {
            id: 'name',
            header: 'Name',
            cell: item => item.name,
            sortingField: 'name'
          },
          {
            id: 'agent_profile',
            header: 'Agent',
            cell: item => (
              <Badge color="blue">{item.agent_profile}</Badge>
            )
          },
          {
            id: 'schedule',
            header: 'Schedule',
            cell: item => <code>{item.schedule}</code>
          },
          {
            id: 'status',
            header: 'Status',
            cell: item => (
              item.enabled ? (
                <Badge color="green">Enabled</Badge>
              ) : (
                <Badge color="grey">Disabled</Badge>
              )
            )
          },
          {
            id: 'next_run',
            header: 'Next Run',
            cell: item => (
              item.next_run ?
                new Date(item.next_run).toLocaleString() :
                'N/A'
            )
          },
          {
            id: 'actions',
            header: 'Actions',
            cell: item => (
              <Button
                variant="inline-link"
                onClick={() => onRunFlow(item.name)}
                disabled={!item.enabled}
              >
                Run Now
              </Button>
            )
          }
        ]}
        items={flows}
        loadingText="Loading flows"
        trackBy="id"
        empty={
          <Box textAlign="center" color="inherit">
            <SpaceBetween size="m">
              <b>No flows configured</b>
              <Box variant="p" color="inherit">
                Use `cao flow add` to create scheduled workflows
              </Box>
            </SpaceBetween>
          </Box>
        }
        variant="embedded"
      />
    </Container>
  );
}
