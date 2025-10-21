import { useState } from 'react'
import Container from '@cloudscape-design/components/container'
import Header from '@cloudscape-design/components/header'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Grid from '@cloudscape-design/components/grid'
import Box from '@cloudscape-design/components/box'
import ColumnLayout from '@cloudscape-design/components/column-layout'
import Badge from '@cloudscape-design/components/badge'
import ExpandableSection from '@cloudscape-design/components/expandable-section'
import Table from '@cloudscape-design/components/table'
import Button from '@cloudscape-design/components/button'
import Tabs from '@cloudscape-design/components/tabs'
import { AgentProfile, Tool } from '../types'

// Sample agent profiles demonstrating multi-agent best practices
const sampleAgents: AgentProfile[] = [
  {
    name: 'Code Supervisor',
    role: 'Coordinator Agent',
    type: 'coordinator',
    expertise: ['Project Management', 'Task Delegation', 'Result Synthesis'],
    description:
      'Coordinates overall workflow, delegates to specialists, and synthesizes results. Maintains complete project context while agents focus on their domains.',
    tools: [
      {
        name: 'handoff',
        description:
          'Transfer control to another agent and wait for completion (synchronous execution)',
        design_type: 'ui-centric',
        parameters: [
          { name: 'agent_profile', type: 'string', description: 'Agent to delegate to', required: true },
          {
            name: 'task_message',
            type: 'string',
            description: 'Complete task description with full context',
            required: true
          }
        ],
        returns: 'Agent output after task completion',
        average_calls_per_task: 2
      },
      {
        name: 'assign',
        description: 'Spawn an agent to work independently (asynchronous execution)',
        design_type: 'ui-centric',
        parameters: [
          { name: 'agent_profile', type: 'string', description: 'Agent to assign to', required: true },
          {
            name: 'task_message',
            type: 'string',
            description: 'Task with callback instructions',
            required: true
          }
        ],
        returns: 'Terminal ID of spawned agent',
        average_calls_per_task: 3
      },
      {
        name: 'send_message',
        description: 'Communicate with an existing agent',
        design_type: 'ui-centric',
        parameters: [
          { name: 'terminal_id', type: 'string', description: 'Target terminal ID', required: true },
          { name: 'message', type: 'string', description: 'Message content', required: true }
        ],
        returns: 'Message delivery confirmation',
        average_calls_per_task: 5
      }
    ]
  },
  {
    name: 'Developer Specialist',
    role: 'Code Implementation Specialist',
    type: 'specialist',
    expertise: ['Code Writing', 'File Operations', 'Git Operations'],
    description:
      'Specialist focused on implementing features and writing code. Receives complete context from coordinator including requirements, constraints, and integration points.',
    tools: [
      {
        name: 'read_file_complete',
        description: 'Read file with surrounding context (UI-centric design)',
        design_type: 'ui-centric',
        parameters: [
          { name: 'file_path', type: 'string', description: 'File to read', required: true },
          {
            name: 'include_context',
            type: 'boolean',
            description: 'Include imports, dependencies, and related files',
            required: false
          }
        ],
        returns:
          'File content with imports, dependencies, related file references, and usage examples',
        average_calls_per_task: 3
      },
      {
        name: 'write_file',
        description: 'Write or update file',
        design_type: 'ui-centric',
        parameters: [
          { name: 'file_path', type: 'string', description: 'File path', required: true },
          { name: 'content', type: 'string', description: 'File content', required: true }
        ],
        returns: 'Success confirmation',
        average_calls_per_task: 4
      },
      {
        name: 'git_commit',
        description: 'Create git commit with context',
        design_type: 'ui-centric',
        parameters: [
          { name: 'message', type: 'string', description: 'Commit message', required: true },
          { name: 'files', type: 'array', description: 'Files to commit', required: false }
        ],
        returns: 'Commit hash and summary',
        average_calls_per_task: 1
      }
    ]
  },
  {
    name: 'Code Reviewer',
    role: 'Code Review Specialist',
    type: 'specialist',
    expertise: ['Code Analysis', 'Best Practices', 'Security Review'],
    description:
      'Specialist focused on reviewing code quality, security, and best practices. Receives full context about the feature, requirements, and integration points.',
    tools: [
      {
        name: 'analyze_code_complete',
        description: 'Analyze code with full project context (UI-centric)',
        design_type: 'ui-centric',
        parameters: [
          { name: 'file_path', type: 'string', description: 'File to analyze', required: true },
          {
            name: 'analysis_type',
            type: 'array',
            description: 'Types: security, performance, style, logic',
            required: true
          }
        ],
        returns:
          'Complete analysis with: issues found, severity levels, suggested fixes, affected code snippets, related files impacted',
        average_calls_per_task: 2
      },
      {
        name: 'get_project_context',
        description: 'Get complete project context for review',
        design_type: 'ui-centric',
        parameters: [
          { name: 'scope', type: 'string', description: 'Review scope', required: true }
        ],
        returns:
          'Project structure, dependencies, coding standards, test coverage, recent changes',
        average_calls_per_task: 1
      }
    ]
  },
  {
    name: 'Test Specialist',
    role: 'Testing Specialist',
    type: 'specialist',
    expertise: ['Test Writing', 'Test Execution', 'Coverage Analysis'],
    description:
      'Specialist focused on writing and running tests. Receives complete context about features to test, expected behavior, and edge cases.',
    tools: [
      {
        name: 'run_tests_complete',
        description: 'Run tests with detailed results (UI-centric)',
        design_type: 'ui-centric',
        parameters: [
          { name: 'test_path', type: 'string', description: 'Test file or directory', required: true },
          {
            name: 'options',
            type: 'object',
            description: 'Test options (coverage, verbose, etc)',
            required: false
          }
        ],
        returns:
          'Complete test results: passed/failed tests with details, coverage metrics, performance data, failure stack traces with context, suggested fixes',
        average_calls_per_task: 2
      },
      {
        name: 'write_test',
        description: 'Write test with context',
        design_type: 'ui-centric',
        parameters: [
          { name: 'test_file', type: 'string', description: 'Test file path', required: true },
          { name: 'test_content', type: 'string', description: 'Test content', required: true }
        ],
        returns: 'Test creation confirmation',
        average_calls_per_task: 3
      }
    ]
  }
]

export default function AgentOrchestration() {
  const [selectedAgent, setSelectedAgent] = useState<AgentProfile>(sampleAgents[0])

  const coordinatorAgents = sampleAgents.filter((a) => a.type === 'coordinator')
  const specialistAgents = sampleAgents.filter((a) => a.type === 'specialist')

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Visualize and manage multi-agent architectures following best practices"
      >
        Agent Orchestration
      </Header>

      <Container
        header={
          <Header variant="h2" description="Following the Coordinator-Specialist pattern">
            Multi-Agent Architecture
          </Header>
        }
      >
        <Box>
          <Box textAlign="center" padding={{ vertical: 'l' }}>
            <Box variant="code" fontSize="body-s">
              <pre>
                {`┌────────────────────────────────┐
│    Coordinator Agent           │
│    (Code Supervisor)           │
│    - Maintains overall context │
│    - Delegates to specialists  │
│    - Synthesizes results       │
└──────────┬─────────────────────┘
           │
    ┌──────┴────────┬───────────┬──────────┐
    │               │           │          │
┌───▼────┐   ┌─────▼──┐   ┌────▼───┐  ┌──▼─────┐
│Developer│   │Reviewer│   │  Test  │  │  Docs  │
│Specialist   │Specialist  │Specialist  │Specialist
│         │   │        │   │        │  │        │
│Tools: 8 │   │Tools: 4│   │Tools: 5│  │Tools: 3│
└─────────┘   └────────┘   └────────┘  └────────┘`}
              </pre>
            </Box>
          </Box>

          <ColumnLayout columns={2} variant="text-grid">
            <div>
              <Box variant="h4">Why This Works</Box>
              <Box variant="p">
                ✓ Each specialist has &lt;20 tools (manageable)
                <br />
                ✓ Clear domain boundaries reduce confusion
                <br />
                ✓ Coordinator maintains overall context
                <br />
                ✓ Specialists receive complete context for subtasks
                <br />✓ Natural task parallelization when possible
              </Box>
            </div>
            <div>
              <Box variant="h4">Key Principles Applied</Box>
              <Box variant="p">
                • Start simple: Single coordinator, add specialists as needed
                <br />
                • Agent perspective: Each agent gets full context
                <br />
                • UI-centric tools: Minimize calls per task
                <br />• Context transfer: Verbose delegation prevents issues
              </Box>
            </div>
          </ColumnLayout>
        </Box>
      </Container>

      <Grid gridDefinition={[{ colspan: 4 }, { colspan: 8 }]}>
        <Container header={<Header variant="h3">Select Agent</Header>}>
          <SpaceBetween size="m">
            <Box>
              <Box variant="awsui-key-label" padding={{ bottom: 'xs' }}>
                Coordinator Agents
              </Box>
              {coordinatorAgents.map((agent) => (
                <Box key={agent.name} padding={{ vertical: 'xs' }}>
                  <Button
                    variant={selectedAgent.name === agent.name ? 'primary' : 'normal'}
                    fullWidth
                    onClick={() => setSelectedAgent(agent)}
                  >
                    {agent.name}
                  </Button>
                </Box>
              ))}
            </Box>

            <Box>
              <Box variant="awsui-key-label" padding={{ bottom: 'xs' }}>
                Specialist Agents
              </Box>
              {specialistAgents.map((agent) => (
                <Box key={agent.name} padding={{ vertical: 'xs' }}>
                  <Button
                    variant={selectedAgent.name === agent.name ? 'primary' : 'normal'}
                    fullWidth
                    onClick={() => setSelectedAgent(agent)}
                  >
                    {agent.name}
                  </Button>
                </Box>
              ))}
            </Box>
          </SpaceBetween>
        </Container>

        <Container
          header={
            <Header
              variant="h3"
              description={selectedAgent.role}
              actions={
                <Badge color={selectedAgent.type === 'coordinator' ? 'blue' : 'green'}>
                  {selectedAgent.type}
                </Badge>
              }
            >
              {selectedAgent.name}
            </Header>
          }
        >
          <Tabs
            tabs={[
              {
                label: 'Overview',
                id: 'overview',
                content: (
                  <SpaceBetween size="m">
                    <Box>
                      <Box variant="h4">Description</Box>
                      <Box variant="p">{selectedAgent.description}</Box>
                    </Box>

                    <ColumnLayout columns={2} variant="text-grid">
                      <div>
                        <Box variant="h4">Expertise</Box>
                        <SpaceBetween size="xs">
                          {selectedAgent.expertise.map((skill) => (
                            <Badge key={skill} color="blue">
                              {skill}
                            </Badge>
                          ))}
                        </SpaceBetween>
                      </div>
                      <div>
                        <Box variant="h4">Tool Count</Box>
                        <Box fontSize="heading-xl">{selectedAgent.tools.length} tools</Box>
                        <Box variant="small" color="text-status-success">
                          {selectedAgent.tools.length <= 20
                            ? '✓ Within recommended limit (<20)'
                            : '⚠ Consider splitting into multiple specialists'}
                        </Box>
                      </div>
                    </ColumnLayout>
                  </SpaceBetween>
                )
              },
              {
                label: 'Tools',
                id: 'tools',
                content: (
                  <Table
                    columnDefinitions={[
                      {
                        id: 'name',
                        header: 'Tool Name',
                        cell: (tool: Tool) => tool.name
                      },
                      {
                        id: 'design',
                        header: 'Design Type',
                        cell: (tool: Tool) => (
                          <Badge color={tool.design_type === 'ui-centric' ? 'green' : 'red'}>
                            {tool.design_type}
                          </Badge>
                        )
                      },
                      {
                        id: 'description',
                        header: 'Description',
                        cell: (tool: Tool) => tool.description
                      },
                      {
                        id: 'calls',
                        header: 'Avg Calls/Task',
                        cell: (tool: Tool) => tool.average_calls_per_task || 'N/A'
                      }
                    ]}
                    items={selectedAgent.tools}
                    empty={
                      <Box textAlign="center" color="inherit">
                        No tools configured
                      </Box>
                    }
                  />
                )
              },
              {
                label: 'Tool Details',
                id: 'tool-details',
                content: (
                  <SpaceBetween size="m">
                    {selectedAgent.tools.map((tool) => (
                      <ExpandableSection key={tool.name} headerText={tool.name} variant="container">
                        <SpaceBetween size="s">
                          <ColumnLayout columns={2} variant="text-grid">
                            <div>
                              <Box variant="awsui-key-label">Design Type</Box>
                              <Badge color={tool.design_type === 'ui-centric' ? 'green' : 'red'}>
                                {tool.design_type}
                              </Badge>
                            </div>
                            <div>
                              <Box variant="awsui-key-label">Average Calls per Task</Box>
                              <Box>{tool.average_calls_per_task || 'N/A'}</Box>
                            </div>
                          </ColumnLayout>

                          <Box>
                            <Box variant="awsui-key-label">Description</Box>
                            <Box>{tool.description}</Box>
                          </Box>

                          <Box>
                            <Box variant="awsui-key-label">Parameters</Box>
                            <Table
                              columnDefinitions={[
                                {
                                  id: 'name',
                                  header: 'Name',
                                  cell: (param) => param.name
                                },
                                {
                                  id: 'type',
                                  header: 'Type',
                                  cell: (param) => <Badge>{param.type}</Badge>
                                },
                                {
                                  id: 'required',
                                  header: 'Required',
                                  cell: (param) =>
                                    param.required ? (
                                      <Badge color="red">Required</Badge>
                                    ) : (
                                      <Badge>Optional</Badge>
                                    )
                                },
                                {
                                  id: 'description',
                                  header: 'Description',
                                  cell: (param) => param.description
                                }
                              ]}
                              items={tool.parameters}
                              variant="embedded"
                            />
                          </Box>

                          <Box>
                            <Box variant="awsui-key-label">Returns</Box>
                            <Box variant="code">{tool.returns}</Box>
                          </Box>
                        </SpaceBetween>
                      </ExpandableSection>
                    ))}
                  </SpaceBetween>
                )
              }
            ]}
          />
        </Container>
      </Grid>

      <Container
        header={
          <Header variant="h2" description="Why UI-centric design reduces agent overhead">
            Tool Design Best Practices
          </Header>
        }
      >
        <ColumnLayout columns={2} variant="text-grid">
          <div>
            <Box variant="h4" color="text-status-error">
              ❌ Bad Design (API-Centric)
            </Box>
            <Box variant="code" padding="s">
              <pre>
                {`# Agent needs 3 calls to understand one message
get_message(id) → {user_id, channel_id, text}
get_user(user_id) → {username}
get_channel(channel_id) → {channel_name}

Total: 3 tool calls for basic info`}
              </pre>
            </Box>
          </div>
          <div>
            <Box variant="h4" color="text-status-success">
              ✓ Good Design (UI-Centric)
            </Box>
            <Box variant="code" padding="s">
              <pre>
                {`# Agent gets complete context in one call
get_message(id) → {
  text: "...",
  author_name: "John Smith",
  channel_name: "#engineering",
  timestamp: "2025-10-20T10:30:00Z"
}

Total: 1 tool call with full context`}
              </pre>
            </Box>
          </div>
        </ColumnLayout>
      </Container>
    </SpaceBetween>
  )
}
