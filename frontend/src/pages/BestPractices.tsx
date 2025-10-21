import Container from '@cloudscape-design/components/container'
import Header from '@cloudscape-design/components/header'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Box from '@cloudscape-design/components/box'
import ColumnLayout from '@cloudscape-design/components/column-layout'
import ExpandableSection from '@cloudscape-design/components/expandable-section'
import Table from '@cloudscape-design/components/table'
import Badge from '@cloudscape-design/components/badge'
import Alert from '@cloudscape-design/components/alert'

const commandments = [
  {
    number: 1,
    title: 'Start Simple, Add Complexity Only When Needed',
    description:
      'Single agent before multi-agent. Minimal tools before extensive toolkit. Measure before adding complexity.',
    details: [
      'Can one agent handle this with <20 tools? Use single agent',
      'Can tasks run in parallel? Consider multi-agent',
      'Do tasks need specialized context? Use coordinator-specialist',
      'Document why each complexity was added'
    ],
    antipatterns: [
      'Building multi-agent systems for problems solvable by single agents',
      'Adding tools "just in case"',
      'Premature optimization with complex orchestration'
    ]
  },
  {
    number: 2,
    title: "Think From the Agent's Point of View",
    description:
      'The agent only knows what it sees. Design everything from its perspective.',
    details: [
      'Always review raw transcripts and tool call logs',
      'Put yourself in agent\'s position: "If I only saw this, could I solve it?"',
      'Test agents with minimal context to identify gaps',
      'Provide explicit context rather than assuming inference'
    ],
    antipatterns: [
      'Assuming agent will infer missing information',
      'Not reviewing actual transcripts',
      'Providing implicit context'
    ]
  },
  {
    number: 3,
    title: 'Tools Should Mirror UI, Not API',
    description:
      'Tools should present complete, contextualized information like user interfaces.',
    details: [
      'Bundle related information together',
      'Include context visible to human users',
      'Minimize tool calls for common tasks',
      'Pre-resolve IDs to human-readable names'
    ],
    antipatterns: [
      'API-centric design requiring multiple calls',
      'Returning IDs without resolution',
      'Stripping context from responses'
    ]
  },
  {
    number: 4,
    title: 'Provide Complete Context to Subagents',
    description:
      'Subagents need MORE context, not less. Be verbose when delegating.',
    details: [
      'Include overall objective, not just immediate task',
      'Explain why subtask matters to the whole',
      'Provide examples of expected output',
      'List all constraints and dependencies upfront'
    ],
    antipatterns: [
      'Sending minimal task descriptions',
      'Omitting overall objective',
      'Using brief, terse instructions'
    ]
  },
  {
    number: 5,
    title: 'Measure and Justify Complexity',
    description: 'Every additional component must prove its value.',
    details: [
      'Track success rate, tool calls, completion time',
      'Compare single vs multi-agent performance',
      'Document why each component exists',
      'Remove components not providing value'
    ],
    antipatterns: [
      'Adding components without measuring impact',
      'Keeping "dead weight" capabilities',
      'Premature optimization'
    ]
  },
  {
    number: 6,
    title: 'Code is a Superpower',
    description:
      "Leverage agent's coding ability for repetitive or complex tasks.",
    details: [
      'Use for loops for repetitive actions',
      'Process large amounts of data with code',
      'Create complex artifacts (SVGs, spreadsheets, PDFs)',
      'Code executes faster than sequential tool calls'
    ],
    antipatterns: ['Always using tool calls instead of code', 'Not leveraging programming abilities']
  },
  {
    number: 7,
    title: 'Minimize Communication Overhead',
    description: 'Keep multi-agent coordination efficient.',
    details: [
      'Design clear boundaries between agent responsibilities',
      'Minimize handoffs between agents',
      'Use parallel execution where possible',
      'Coordination overhead should be <20% of total time'
    ],
    antipatterns: [
      'Excessive back-and-forth between agents',
      'Unclear responsibility boundaries',
      'Sequential when parallel would work'
    ]
  },
  {
    number: 8,
    title: 'Test From Agent\'s Perspective',
    description: 'What the agent sees is all it knows.',
    details: [
      'Review actual transcripts, not assumptions',
      'Test with minimal context to find gaps',
      'Verify agent has all information needed',
      'Check for implicit assumptions'
    ],
    antipatterns: [
      'Testing only happy paths',
      'Not reviewing actual agent behavior',
      'Assuming agent will figure it out'
    ]
  },
  {
    number: 9,
    title: 'Document Everything',
    description: 'Decisions, failure modes, solutions, patterns.',
    details: [
      'Why was each component added?',
      'What problems did we encounter?',
      'How were they solved?',
      'What patterns emerged?'
    ],
    antipatterns: ['No documentation', 'Outdated documentation', 'Missing rationale for decisions']
  },
  {
    number: 10,
    title: 'Iterate Based on Reality',
    description: 'Transcripts reveal truth - optimize based on actual behavior.',
    details: [
      'Review failed attempts systematically',
      'Identify patterns in failures',
      'Adjust prompts or tools based on evidence',
      'Re-test and measure improvements'
    ],
    antipatterns: [
      'Optimizing based on theory, not reality',
      'Not learning from failures',
      'Making changes without measuring impact'
    ]
  }
]

const healthIndicators = {
  healthy: [
    'Can explain why each component exists',
    'Agents complete tasks with ≤5 tool calls',
    'Multi-agent coordination overhead <20% of total time',
    'First-time success rate >80%',
    'Can debug using transcripts, not guessing',
    'New team members understand architecture quickly'
  ],
  unhealthy: [
    'Components without clear purpose',
    'Excessive tool calls for simple tasks',
    'High coordination overhead',
    'Low success rate',
    'Difficult to debug',
    'Complex architecture that\'s hard to explain'
  ]
}

const metrics = [
  {
    category: 'Efficiency',
    metric: 'Tool Calls per Task',
    target: '≤5 for common tasks',
    measurement: 'Count tool calls in transcripts'
  },
  {
    category: 'Efficiency',
    metric: 'Context Window Usage',
    target: 'Managed, not maxed',
    measurement: 'Monitor token usage'
  },
  {
    category: 'Efficiency',
    metric: 'Task Completion Time',
    target: 'Track improvements',
    measurement: 'Measure end-to-end duration'
  },
  {
    category: 'Quality',
    metric: 'First-Time Success Rate',
    target: '>80%',
    measurement: 'Tasks completed correctly first time'
  },
  {
    category: 'Quality',
    metric: 'Error Rate',
    target: '<20%',
    measurement: 'Frequency and types of errors'
  },
  {
    category: 'System Health',
    metric: 'Coordination Overhead',
    target: '<20%',
    measurement: 'Time spent coordinating vs. working'
  }
]

export default function BestPractices() {
  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Comprehensive guide to multi-agent workflow best practices"
      >
        Best Practices Guide
      </Header>

      <Alert type="info" header="Based on Anthropic Agent Orchestrator Best Practices">
        These guidelines are based on production experience building and deploying agent systems.
        Following them will help you avoid common pitfalls and build reliable, efficient
        multi-agent workflows.
      </Alert>

      <Container
        header={
          <Header variant="h2" description="Core principles for effective agent systems">
            The 10 Commandments of Agent Development
          </Header>
        }
      >
        <SpaceBetween size="m">
          {commandments.map((commandment) => (
            <ExpandableSection
              key={commandment.number}
              headerText={`${commandment.number}. ${commandment.title}`}
              variant="container"
            >
              <SpaceBetween size="m">
                <Box variant="p">{commandment.description}</Box>

                <ColumnLayout columns={2} variant="text-grid">
                  <div>
                    <Box variant="h4" color="text-status-success">
                      ✓ Best Practices
                    </Box>
                    <Box component="ul">
                      {commandment.details.map((detail, idx) => (
                        <li key={idx}>{detail}</li>
                      ))}
                    </Box>
                  </div>
                  <div>
                    <Box variant="h4" color="text-status-error">
                      ✗ Anti-Patterns to Avoid
                    </Box>
                    <Box component="ul">
                      {commandment.antipatterns.map((pattern, idx) => (
                        <li key={idx}>{pattern}</li>
                      ))}
                    </Box>
                  </div>
                </ColumnLayout>
              </SpaceBetween>
            </ExpandableSection>
          ))}
        </SpaceBetween>
      </Container>

      <Container
        header={
          <Header variant="h2" description="Key metrics to track for agent system health">
            Metrics and Success Criteria
          </Header>
        }
      >
        <Table
          columnDefinitions={[
            {
              id: 'category',
              header: 'Category',
              cell: (item) => <Badge color="blue">{item.category}</Badge>
            },
            {
              id: 'metric',
              header: 'Metric',
              cell: (item) => item.metric
            },
            {
              id: 'target',
              header: 'Target',
              cell: (item) => <Box color="text-status-success">{item.target}</Box>
            },
            {
              id: 'measurement',
              header: 'How to Measure',
              cell: (item) => item.measurement
            }
          ]}
          items={metrics}
          variant="embedded"
        />
      </Container>

      <Container
        header={
          <Header variant="h2" description="Indicators of system health">
            System Health Checklist
          </Header>
        }
      >
        <ColumnLayout columns={2} variant="text-grid">
          <div>
            <Box variant="h3" color="text-status-success">
              ✓ Healthy System
            </Box>
            <Box component="ul">
              {healthIndicators.healthy.map((indicator, idx) => (
                <li key={idx}>
                  <Box color="text-status-success">{indicator}</Box>
                </li>
              ))}
            </Box>
          </div>
          <div>
            <Box variant="h3" color="text-status-error">
              ✗ Unhealthy System
            </Box>
            <Box component="ul">
              {healthIndicators.unhealthy.map((indicator, idx) => (
                <li key={idx}>
                  <Box color="text-status-error">{indicator}</Box>
                </li>
              ))}
            </Box>
          </div>
        </ColumnLayout>
      </Container>

      <Container
        header={
          <Header variant="h2" description="Step-by-step process for building agent systems">
            Agent Development Workflow
          </Header>
        }
      >
        <SpaceBetween size="m">
          <ExpandableSection headerText="Phase 1: Requirements Analysis" defaultExpanded>
            <Box component="ul">
              <li>What is the core objective?</li>
              <li>What tools/data access is needed?</li>
              <li>Can this be done with a single agent?</li>
              <li>What are the success criteria?</li>
              <li>What are the constraints (time, cost, quality)?</li>
            </Box>
          </ExpandableSection>

          <ExpandableSection headerText="Phase 2: Architecture Design">
            <SpaceBetween size="s">
              <Box variant="h4">For Single-Agent:</Box>
              <Box component="ol">
                <li>Define agent role and objective</li>
                <li>List required tools (aim for &lt;20)</li>
                <li>Design system prompt</li>
                <li>Plan context management strategy</li>
                <li>Define output format</li>
              </Box>

              <Box variant="h4">For Multi-Agent:</Box>
              <Box component="ol">
                <li>Identify natural task boundaries</li>
                <li>Design agent hierarchy</li>
                <li>Plan context transfer protocol</li>
                <li>Define communication interfaces</li>
                <li>Establish coordination strategy</li>
              </Box>
            </SpaceBetween>
          </ExpandableSection>

          <ExpandableSection headerText="Phase 3: Tool Development">
            <Box component="ol">
              <li>Design from agent's perspective (UI not API)</li>
              <li>Implement with comprehensive docstrings</li>
              <li>Include examples in documentation</li>
              <li>Add error handling with actionable messages</li>
              <li>Test with example conversations</li>
            </Box>
          </ExpandableSection>

          <ExpandableSection headerText="Phase 4: Implementation">
            <Box component="ol">
              <li>Implement system prompt</li>
              <li>Integrate tools</li>
              <li>Test with example scenarios</li>
              <li>Refine based on transcripts</li>
              <li>Measure success rate</li>
            </Box>
          </ExpandableSection>

          <ExpandableSection headerText="Phase 5: Testing and Refinement">
            <SpaceBetween size="s">
              <Box variant="h4">Testing Checklist:</Box>
              <Box component="ul">
                <li>✓ Happy path scenarios work correctly</li>
                <li>✓ Edge cases handled gracefully</li>
                <li>✓ Error messages are actionable</li>
                <li>✓ Context maintained across interactions</li>
                <li>✓ Tool calls are efficient</li>
                <li>✓ Success rate meets criteria</li>
              </Box>

              <Box variant="h4">Refinement Process:</Box>
              <Box component="ol">
                <li>Review failed attempts</li>
                <li>Identify patterns in failures</li>
                <li>Adjust prompts or tools</li>
                <li>Re-test</li>
                <li>Iterate until success criteria met</li>
              </Box>
            </SpaceBetween>
          </ExpandableSection>

          <ExpandableSection headerText="Phase 6: Monitoring and Optimization">
            <Box component="ul">
              <li>Track success rate (% of tasks completed correctly)</li>
              <li>Monitor average tool calls per task</li>
              <li>Measure context window utilization</li>
              <li>Track response time</li>
              <li>Monitor error rate by type</li>
              <li>Optimize based on real usage patterns</li>
            </Box>
          </ExpandableSection>
        </SpaceBetween>
      </Container>

      <Container
        header={
          <Header variant="h2" description="Common problems and their solutions">
            Common Failure Modes
          </Header>
        }
      >
        <SpaceBetween size="m">
          <ExpandableSection headerText="Communication Overhead" variant="container">
            <ColumnLayout columns={2} variant="text-grid">
              <div>
                <Box variant="h4">Symptoms</Box>
                <Box component="ul">
                  <li>Many messages between agents with little progress</li>
                  <li>Repeated clarification requests</li>
                  <li>Task takes longer with multiple agents</li>
                </Box>
              </div>
              <div>
                <Box variant="h4">Solutions</Box>
                <Box component="ul">
                  <li>Provide complete context upfront</li>
                  <li>Design clear boundaries</li>
                  <li>Minimize handoffs</li>
                  <li>Use parallel execution</li>
                </Box>
              </div>
            </ColumnLayout>
          </ExpandableSection>

          <ExpandableSection headerText="Insufficient Context for Subagents" variant="container">
            <ColumnLayout columns={2} variant="text-grid">
              <div>
                <Box variant="h4">Symptoms</Box>
                <Box component="ul">
                  <li>Subagent asks questions coordinator knows</li>
                  <li>Results don't integrate well</li>
                  <li>Repeated back-and-forth for clarification</li>
                </Box>
              </div>
              <div>
                <Box variant="h4">Solutions</Box>
                <Box component="ul">
                  <li>Transfer MORE context, not less</li>
                  <li>Include overall objective</li>
                  <li>Explain why subtask matters</li>
                  <li>Use context transfer templates</li>
                </Box>
              </div>
            </ColumnLayout>
          </ExpandableSection>

          <ExpandableSection headerText="Over-Complicated Tool Design" variant="container">
            <ColumnLayout columns={2} variant="text-grid">
              <div>
                <Box variant="h4">Symptoms</Box>
                <Box component="ul">
                  <li>Many sequential tool calls for simple tasks</li>
                  <li>Lots of ID resolution and data joining</li>
                  <li>Agent struggles to maintain context</li>
                </Box>
              </div>
              <div>
                <Box variant="h4">Solutions</Box>
                <Box component="ul">
                  <li>Bundle related information</li>
                  <li>Pre-resolve IDs to names</li>
                  <li>Return complete context in single calls</li>
                  <li>Add smart defaults and filtering</li>
                </Box>
              </div>
            </ColumnLayout>
          </ExpandableSection>

          <ExpandableSection headerText="Overbuilding" variant="container">
            <ColumnLayout columns={2} variant="text-grid">
              <div>
                <Box variant="h4">Symptoms</Box>
                <Box component="ul">
                  <li>Many agents but performance doesn't justify it</li>
                  <li>Lots of unused capabilities</li>
                  <li>Difficult to debug or understand</li>
                </Box>
              </div>
              <div>
                <Box variant="h4">Solutions</Box>
                <Box component="ul">
                  <li>Remove components not providing value</li>
                  <li>Consolidate similar agents</li>
                  <li>Start simple, measure, then add</li>
                  <li>Document reason for each component</li>
                </Box>
              </div>
            </ColumnLayout>
          </ExpandableSection>
        </SpaceBetween>
      </Container>

      <Container
        header={
          <Header variant="h2" description="Quick references for common decisions">
            Decision Trees
          </Header>
        }
      >
        <SpaceBetween size="m">
          <Box>
            <Box variant="h4" padding={{ bottom: 's' }}>
              Single vs. Multi-Agent Decision
            </Box>
            <Box variant="code" padding="m">
              <pre>
                {`Can one agent handle all tools (<20)?
├─ YES → Use Single-Agent
└─ NO → Continue
    │
    Can tasks run in parallel?
    ├─ YES → Use Multi-Agent (Parallel Pattern)
    └─ NO → Continue
        │
        Do tasks need specialized context?
        ├─ YES → Use Multi-Agent (Coordinator-Specialist)
        └─ NO → Use Single-Agent (simplify tool design instead)`}
              </pre>
            </Box>
          </Box>

          <Box>
            <Box variant="h4" padding={{ bottom: 's' }}>
              Tool Design Quality Check
            </Box>
            <Box variant="code" padding="m">
              <pre>
                {`Does this tool require multiple calls to get basic info?
├─ YES → REDESIGN (bundle information)
└─ NO → Continue
    │
    Does it return IDs that need resolution?
    ├─ YES → REDESIGN (pre-resolve to names)
    └─ NO → Continue
        │
        Would a human need this info in the UI?
        ├─ YES → Include it
        └─ NO → Consider if agent really needs it`}
              </pre>
            </Box>
          </Box>
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  )
}
