import { useState } from 'react'
import Container from '@cloudscape-design/components/container'
import Header from '@cloudscape-design/components/header'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Box from '@cloudscape-design/components/box'
import ColumnLayout from '@cloudscape-design/components/column-layout'
import Cards from '@cloudscape-design/components/cards'
import Badge from '@cloudscape-design/components/badge'
import ExpandableSection from '@cloudscape-design/components/expandable-section'
import Tabs from '@cloudscape-design/components/tabs'
import Table from '@cloudscape-design/components/table'

interface Pattern {
  id: string
  name: string
  type: 'handoff' | 'assign' | 'send_message'
  description: string
  useCase: string
  execution: 'synchronous' | 'asynchronous'
  workflow: string
  diagram: string
  advantages: string[]
  whenToUse: string[]
  example: string
  metrics?: {
    typical_duration: string
    coordination_overhead: string
    best_for: string
  }
}

const patterns: Pattern[] = [
  {
    id: '1',
    name: 'Handoff Pattern',
    type: 'handoff',
    description: 'Transfer control to another agent and wait for completion',
    useCase: 'Sequential code review workflow',
    execution: 'synchronous',
    workflow: `1. Coordinator creates new terminal with specialist agent
2. Sends task message with full context
3. Waits for specialist to complete work
4. Receives specialist's output
5. Specialist terminal automatically exits
6. Coordinator continues with results`,
    diagram: `┌──────────────┐
│ Coordinator  │
└──────┬───────┘
       │ handoff(developer, "Implement feature X")
       ▼
┌──────────────┐
│  Developer   │ ◄── Works on task
│  Specialist  │
└──────┬───────┘
       │ Returns: "Feature implemented in file.py"
       ▼
┌──────────────┐
│ Coordinator  │ ◄── Receives results, continues
└──────────────┘`,
    advantages: [
      'Simple linear workflow',
      'Easy to reason about',
      'Clear causation',
      'Automatic cleanup',
      'Results guaranteed before proceeding'
    ],
    whenToUse: [
      'Need synchronous task execution with results',
      'Sequential workflow where next step depends on results',
      'Code review after implementation',
      'Validation before proceeding',
      'Single specialist needed for task'
    ],
    example: `# Coordinator agent uses handoff
result = handoff(
  agent_profile="developer",
  message="""
  Implement user authentication feature.

  Requirements:
  - JWT-based authentication
  - Login and signup endpoints
  - Password hashing with bcrypt

  Return the file paths of created files.
  """
)

# Coordinator waits here until developer finishes
# Then receives: "Created: auth.py, routes.py, models.py"

# Now coordinator can proceed with next step
review_result = handoff(
  agent_profile="reviewer",
  message=f"Review the authentication code in {result}"
)`,
    metrics: {
      typical_duration: '2-5 minutes per handoff',
      coordination_overhead: '10-15%',
      best_for: 'Sequential tasks with dependencies'
    }
  },
  {
    id: '2',
    name: 'Assign Pattern',
    type: 'assign',
    description: 'Spawn an agent to work independently (async)',
    useCase: 'Parallel test execution',
    execution: 'asynchronous',
    workflow: `1. Coordinator creates new terminal with specialist agent
2. Sends task message with callback instructions
3. Returns immediately with terminal ID
4. Specialist works in background
5. Specialist sends results back via send_message when complete
6. Messages queued if coordinator is busy`,
    diagram: `┌──────────────┐
│ Coordinator  │
└──┬───┬───┬───┘
   │   │   │ assign(test_spec_1, "Test module A")
   │   │   │ assign(test_spec_2, "Test module B")
   │   │   │ assign(test_spec_3, "Test module C")
   │   │   ▼
   │   │  ┌──────────────┐
   │   │  │ Test Spec 1  │ ◄── Works in parallel
   │   │  └──────┬───────┘
   │   ▼         │
   │  ┌──────────────┐    │
   │  │ Test Spec 2  │ ◄──┼── All work simultaneously
   │  └──────┬───────┘    │
   ▼         │            │
┌──────────────┐         │
│ Test Spec 3  │ ◄───────┘
└──────┬───────┘
       │ All send results back when done
       ▼
┌──────────────┐
│ Coordinator  │ ◄── Receives all results (queued if busy)
└──────────────┘`,
    advantages: [
      'Parallel execution for speed',
      'Non-blocking workflow',
      'Efficient resource utilization',
      'Scales to multiple tasks',
      'Fire-and-forget capability'
    ],
    whenToUse: [
      'Asynchronous task execution needed',
      'Parallel processing for speed',
      'Independent tasks with no dependencies',
      'Multiple specialists working simultaneously',
      'Batch processing scenarios'
    ],
    example: `# Coordinator spawns multiple agents in parallel
terminal_ids = []

# Start all tests in parallel
for module in ["auth", "api", "database"]:
  terminal_id = assign(
    agent_profile="test_specialist",
    message=f"""
    Run tests for {module} module.

    When complete, send results back to me with:
    - Tests passed/failed
    - Coverage percentage
    - Any errors found

    Use send_message(coordinator_id, results)
    """
  )
  terminal_ids.append(terminal_id)

# Coordinator continues immediately
# Results arrive asynchronously via send_message
# Messages are queued if coordinator is busy`,
    metrics: {
      typical_duration: '1-2 minutes (parallel)',
      coordination_overhead: '5-10%',
      best_for: 'Independent parallel tasks'
    }
  },
  {
    id: '3',
    name: 'Send Message Pattern',
    type: 'send_message',
    description: 'Communicate with an existing agent',
    useCase: 'Multi-role feature development with iterative feedback',
    execution: 'asynchronous',
    workflow: `1. Coordinator sends message to specific terminal's inbox
2. Message queued if terminal is busy
3. Message delivered when terminal becomes idle
4. Enables ongoing collaboration between agents
5. Supports multi-turn conversations`,
    diagram: `┌──────────────┐
│ Coordinator  │
└──────┬───────┘
       │ send_message(developer_id, "Add error handling")
       ▼
┌──────────────┐
│  Developer   │ ◄── Receives message when idle
│ (existing)   │
└──────┬───────┘
       │ send_message(coordinator_id, "Done, added try/catch")
       ▼
┌──────────────┐
│ Coordinator  │ ◄── Receives response
└──────┬───────┘
       │ send_message(reviewer_id, "Review error handling")
       ▼
┌──────────────┐
│   Reviewer   │ ◄── Iterative collaboration continues
│ (existing)   │
└──────────────┘`,
    advantages: [
      'Ongoing collaboration',
      'Multi-turn conversations',
      'Message queuing handles busy agents',
      'Dynamic coordination',
      'Swarm intelligence patterns'
    ],
    whenToUse: [
      'Iterative feedback needed',
      'Multi-turn conversations',
      'Agent collaboration and steering',
      'Swarm operations with dynamic coordination',
      'Updating existing agents with new information'
    ],
    example: `# Coordinator maintains ongoing collaboration
developer_id = assign(
  agent_profile="developer",
  message="Implement user profile feature"
)

# Later, send additional guidance
send_message(
  terminal_id=developer_id,
  message="Also add avatar upload functionality"
)

# Even later, after seeing results
send_message(
  terminal_id=developer_id,
  message="Great work! Now add input validation"
)

# Messages are queued and delivered when agent is idle`,
    metrics: {
      typical_duration: 'Variable (ongoing)',
      coordination_overhead: '15-20%',
      best_for: 'Iterative collaboration'
    }
  }
]

const architecturePatterns = [
  {
    name: 'Coordinator-Specialist',
    type: 'coordinator-specialist',
    description: 'Coordinator delegates to domain specialists',
    diagram: `        ┌──────────────┐
        │ Coordinator  │
        └───┬──┬──┬────┘
            │  │  │
    ┌───────┘  │  └───────┐
    │          │          │
┌───▼────┐ ┌──▼─────┐ ┌──▼────┐
│Search  │ │Analysis│ │Synth- │
│Special.│ │Special.│ │esis   │
└────────┘ └────────┘ └───────┘`,
    useCases: ['Complex tasks requiring different tool sets', 'Domain-specific expertise needed'],
    patterns: ['handoff', 'assign', 'send_message']
  },
  {
    name: 'Parallel MapReduce',
    type: 'parallel-mapreduce',
    description: 'Split work, process in parallel, combine results',
    diagram: `  ┌─────────────┐
  │Orchestrator │
  └──┬──┬──┬────┘
     │  │  │
┌────▼┐ │  │
│Work │ │  │  Process
│er 1 │ │  │  in
└────┬┘ │  │  parallel
     │ ┌▼──▼┐
     │ │Work│
     │ │er 2│
     │ └──┬─┘
  ┌──▼────▼──┐
  │  Reducer │
  └──────────┘`,
    useCases: ['Large documents', 'Multiple data sources', 'Batch processing'],
    patterns: ['assign']
  },
  {
    name: 'Test-Time Compute',
    type: 'test-time-compute',
    description: 'Multiple approaches, select best',
    diagram: `  ┌──────────┐
  │ Problem  │
  └─┬──┬──┬──┘
    │  │  │
┌───▼┐ │  │
│App │ │  │  Multiple
│r. A│ │  │  approaches
└───┬┘ │  │
    │ ┌▼──▼┐
    │ │App │
    │ │r. B│
    │ └──┬─┘
 ┌──▼────▼──┐
 │Evaluator │
 └──────────┘`,
    useCases: ['Complex problems', 'Multiple valid approaches', 'Quality optimization'],
    patterns: ['assign', 'send_message']
  }
]

export default function WorkflowPatterns() {
  const [selectedPattern, setSelectedPattern] = useState<Pattern>(patterns[0])

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Explore the three orchestration modes and multi-agent architecture patterns"
      >
        Workflow Patterns
      </Header>

      <Container
        header={<Header variant="h2">Orchestration Modes</Header>}
      >
        <Cards
          cardDefinition={{
            header: (pattern) => (
              <Box>
                <Box variant="h3">{pattern.name}</Box>
                <Badge color={pattern.execution === 'synchronous' ? 'blue' : 'green'}>
                  {pattern.execution}
                </Badge>
              </Box>
            ),
            sections: [
              {
                id: 'description',
                content: (pattern) => <Box variant="p">{pattern.description}</Box>
              },
              {
                id: 'usecase',
                header: 'Use Case',
                content: (pattern) => <Box variant="p">{pattern.useCase}</Box>
              },
              {
                id: 'actions',
                content: (pattern) => (
                  <Box textAlign="center">
                    <Box
                      variant="a"
                      fontSize="body-m"
                      onClick={() => setSelectedPattern(pattern)}
                      color="text-link-default"
                    >
                      View Details →
                    </Box>
                  </Box>
                )
              }
            ]
          }}
          items={patterns}
          cardsPerRow={[{ cards: 1 }, { minWidth: 500, cards: 3 }]}
        />
      </Container>

      <Container
        header={
          <Header
            variant="h2"
            description={selectedPattern.description}
            actions={
              <Badge color={selectedPattern.execution === 'synchronous' ? 'blue' : 'green'}>
                {selectedPattern.execution}
              </Badge>
            }
          >
            {selectedPattern.name}
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
                  <ColumnLayout columns={2} variant="text-grid">
                    <div>
                      <Box variant="h4">Execution Type</Box>
                      <Badge
                        color={selectedPattern.execution === 'synchronous' ? 'blue' : 'green'}
                      >
                        {selectedPattern.execution.toUpperCase()}
                      </Badge>
                      <Box variant="p" padding={{ top: 's' }}>
                        {selectedPattern.execution === 'synchronous'
                          ? 'Waits for completion before proceeding'
                          : 'Returns immediately, results arrive later'}
                      </Box>
                    </div>
                    <div>
                      <Box variant="h4">Primary Use Case</Box>
                      <Box variant="p">{selectedPattern.useCase}</Box>
                    </div>
                  </ColumnLayout>

                  {selectedPattern.metrics && (
                    <Box>
                      <Box variant="h4" padding={{ bottom: 's' }}>
                        Performance Metrics
                      </Box>
                      <ColumnLayout columns={3} variant="text-grid">
                        <div>
                          <Box variant="awsui-key-label">Typical Duration</Box>
                          <Box>{selectedPattern.metrics.typical_duration}</Box>
                        </div>
                        <div>
                          <Box variant="awsui-key-label">Coordination Overhead</Box>
                          <Box>{selectedPattern.metrics.coordination_overhead}</Box>
                        </div>
                        <div>
                          <Box variant="awsui-key-label">Best For</Box>
                          <Box>{selectedPattern.metrics.best_for}</Box>
                        </div>
                      </ColumnLayout>
                    </Box>
                  )}

                  <ColumnLayout columns={2} variant="text-grid">
                    <div>
                      <Box variant="h4">Advantages</Box>
                      <Box component="ul">
                        {selectedPattern.advantages.map((adv, idx) => (
                          <li key={idx}>{adv}</li>
                        ))}
                      </Box>
                    </div>
                    <div>
                      <Box variant="h4">When to Use</Box>
                      <Box component="ul">
                        {selectedPattern.whenToUse.map((use, idx) => (
                          <li key={idx}>{use}</li>
                        ))}
                      </Box>
                    </div>
                  </ColumnLayout>
                </SpaceBetween>
              )
            },
            {
              label: 'Workflow',
              id: 'workflow',
              content: (
                <SpaceBetween size="m">
                  <Box>
                    <Box variant="h4" padding={{ bottom: 's' }}>
                      Execution Flow
                    </Box>
                    <Box variant="code" padding="m">
                      <pre>{selectedPattern.workflow}</pre>
                    </Box>
                  </Box>

                  <Box>
                    <Box variant="h4" padding={{ bottom: 's' }}>
                      Visual Diagram
                    </Box>
                    <Box variant="code" padding="m">
                      <pre>{selectedPattern.diagram}</pre>
                    </Box>
                  </Box>
                </SpaceBetween>
              )
            },
            {
              label: 'Code Example',
              id: 'example',
              content: (
                <Box>
                  <Box variant="h4" padding={{ bottom: 's' }}>
                    Implementation Example
                  </Box>
                  <Box variant="code" padding="m">
                    <pre>{selectedPattern.example}</pre>
                  </Box>
                </Box>
              )
            }
          ]}
        />
      </Container>

      <Container
        header={
          <Header variant="h2" description="Combining orchestration modes into patterns">
            Multi-Agent Architecture Patterns
          </Header>
        }
      >
        <SpaceBetween size="l">
          {architecturePatterns.map((pattern) => (
            <ExpandableSection
              key={pattern.name}
              headerText={pattern.name}
              variant="container"
              defaultExpanded={pattern.type === 'coordinator-specialist'}
            >
              <SpaceBetween size="m">
                <Box variant="p">{pattern.description}</Box>

                <ColumnLayout columns={2} variant="text-grid">
                  <div>
                    <Box variant="h4">Architecture Diagram</Box>
                    <Box variant="code" padding="m">
                      <pre>{pattern.diagram}</pre>
                    </Box>
                  </div>
                  <div>
                    <SpaceBetween size="m">
                      <Box>
                        <Box variant="h4">Common Use Cases</Box>
                        <Box component="ul">
                          {pattern.useCases.map((useCase, idx) => (
                            <li key={idx}>{useCase}</li>
                          ))}
                        </Box>
                      </Box>
                      <Box>
                        <Box variant="h4">Uses Orchestration Patterns</Box>
                        <SpaceBetween direction="horizontal" size="xs">
                          {pattern.patterns.map((p) => (
                            <Badge key={p} color="blue">
                              {p}
                            </Badge>
                          ))}
                        </SpaceBetween>
                      </Box>
                    </SpaceBetween>
                  </div>
                </ColumnLayout>
              </SpaceBetween>
            </ExpandableSection>
          ))}
        </SpaceBetween>
      </Container>

      <Container
        header={
          <Header variant="h2" description="Decision framework for choosing the right pattern">
            Pattern Selection Guide
          </Header>
        }
      >
        <Table
          columnDefinitions={[
            {
              id: 'scenario',
              header: 'Scenario',
              cell: (item) => item.scenario
            },
            {
              id: 'pattern',
              header: 'Recommended Pattern',
              cell: (item) => <Badge color="blue">{item.pattern}</Badge>
            },
            {
              id: 'reason',
              header: 'Reason',
              cell: (item) => item.reason
            }
          ]}
          items={[
            {
              scenario: 'Need results before proceeding',
              pattern: 'Handoff',
              reason: 'Synchronous execution guarantees results'
            },
            {
              scenario: 'Multiple independent tasks',
              pattern: 'Assign',
              reason: 'Parallel execution for speed'
            },
            {
              scenario: 'Ongoing agent collaboration',
              pattern: 'Send Message',
              reason: 'Enables multi-turn conversations'
            },
            {
              scenario: 'Sequential code review',
              pattern: 'Handoff',
              reason: 'Review needs completed code'
            },
            {
              scenario: 'Batch processing 100 items',
              pattern: 'Assign',
              reason: 'Process items in parallel'
            },
            {
              scenario: 'Agent needs course correction',
              pattern: 'Send Message',
              reason: 'Send guidance to existing agent'
            }
          ]}
          variant="embedded"
        />
      </Container>
    </SpaceBetween>
  )
}
