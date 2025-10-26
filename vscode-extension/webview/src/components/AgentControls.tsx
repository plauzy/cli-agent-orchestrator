import { useState } from 'react';
import {
  Container,
  Header,
  SpaceBetween,
  Button,
  Select,
  Box
} from '@cloudscape-design/components';

interface AgentControlsProps {
  onLaunchAgent: (agentProfile: string) => void;
}

const AGENT_PROFILES = [
  { label: 'Code Supervisor', value: 'code_supervisor' },
  { label: 'Developer', value: 'developer' },
  { label: 'Reviewer', value: 'reviewer' }
];

export function AgentControls({ onLaunchAgent }: AgentControlsProps) {
  const [selectedProfile, setSelectedProfile] = useState(AGENT_PROFILES[0]);

  const handleLaunch = () => {
    if (selectedProfile) {
      onLaunchAgent(selectedProfile.value);
    }
  };

  return (
    <Container
      header={
        <Header
          variant="h2"
          description="Launch new agent sessions"
        >
          Agent Controls
        </Header>
      }
    >
      <SpaceBetween size="m">
        <Select
          selectedOption={selectedProfile}
          onChange={({ detail }) => {
            const option = detail.selectedOption;
            if (option) {
              setSelectedProfile(option as typeof AGENT_PROFILES[0]);
            }
          }}
          options={AGENT_PROFILES}
          selectedAriaLabel="Selected"
          placeholder="Select agent profile"
        />

        <Button
          variant="primary"
          onClick={handleLaunch}
          iconName="add-plus"
          fullWidth
        >
          Launch Agent
        </Button>

        <Box variant="small" color="text-body-secondary">
          <SpaceBetween size="xs">
            <div><strong>Code Supervisor:</strong> Coordinates multi-agent workflows</div>
            <div><strong>Developer:</strong> Implements features and fixes</div>
            <div><strong>Reviewer:</strong> Reviews code and provides feedback</div>
          </SpaceBetween>
        </Box>
      </SpaceBetween>
    </Container>
  );
}
