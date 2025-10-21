import { useState } from 'react'
import Container from '@cloudscape-design/components/container'
import Header from '@cloudscape-design/components/header'
import SpaceBetween from '@cloudscape-design/components/space-between'
import FormField from '@cloudscape-design/components/form-field'
import Input from '@cloudscape-design/components/input'
import Textarea from '@cloudscape-design/components/textarea'
import Select from '@cloudscape-design/components/select'
import Button from '@cloudscape-design/components/button'
import Box from '@cloudscape-design/components/box'
import ColumnLayout from '@cloudscape-design/components/column-layout'
import Alert from '@cloudscape-design/components/alert'
import ExpandableSection from '@cloudscape-design/components/expandable-section'
import Tabs from '@cloudscape-design/components/tabs'

interface TaskForm {
  overallObjective: string
  overallContext: string
  taskDescription: string
  taskPriority: 'high' | 'medium' | 'low'
  availableTools: string
  inputData: string
  constraints: string
  expectedOutputFormat: string
  successCriteria: string
  deadline: string
  dependsOn: string
  blocks: string
}

const initialForm: TaskForm = {
  overallObjective: '',
  overallContext: '',
  taskDescription: '',
  taskPriority: 'medium',
  availableTools: '',
  inputData: '{}',
  constraints: '{}',
  expectedOutputFormat: '',
  successCriteria: '',
  deadline: '',
  dependsOn: '',
  blocks: ''
}

const exampleGoodDelegation: TaskForm = {
  overallObjective:
    "Evaluate market entry into the AI tools space for code generation. Timeline: 6-month launch window. Budget: $500k initial investment.",
  overallContext:
    "We're a team of 5 engineers with ML expertise. Our differentiator will be integration with enterprise workflows. Target customers: mid-size tech companies (100-1000 employees). Priority regions: North America, Europe.",
  taskDescription:
    "Research the competitive landscape for AI-powered code generation tools, focusing on: pricing models, key features, target customers, and market positioning.",
  taskPriority: 'high',
  availableTools: 'web_search, fetch_url, summarize_text',
  inputData: JSON.stringify(
    {
      industry_reports_db: 'available',
      company_database: 'available',
      focus_period: 'last 24 months'
    },
    null,
    2
  ),
  constraints: JSON.stringify(
    {
      time_limit: '48 hours',
      focus_on_public_pricing: true,
      research_hours: 4,
      synthesis_hours: 2
    },
    null,
    2
  ),
  expectedOutputFormat:
    'Structured markdown report with: Executive summary (3-5 bullets), Competitor analysis table, Key insights section, Recommendations section',
  successCriteria:
    '- Identified 8-10 direct competitors\n- Documented pricing models for each\n- Analyzed feature differentiation\n- Assessed market positioning strategies\n- Highlighted 3-5 key insights for our strategy',
  deadline: '2025-10-23T17:00:00Z',
  dependsOn: '',
  blocks: 'product-feature-prioritization, pricing-strategy-development, gtm-planning'
}

const exampleBadDelegation: TaskForm = {
  overallObjective: 'Research competitors',
  overallContext: '',
  taskDescription: 'Research competitors in the AI tools market.',
  taskPriority: 'medium',
  availableTools: '',
  inputData: '{}',
  constraints: '{}',
  expectedOutputFormat: '',
  successCriteria: '',
  deadline: '',
  dependsOn: '',
  blocks: ''
}

export default function TaskDelegation() {
  const [form, setForm] = useState<TaskForm>(initialForm)
  const [selectedPriority, setSelectedPriority] = useState({ label: 'Medium', value: 'medium' })

  const generatePrompt = () => {
    return `To: [Subagent Name]
From: [Coordinator]

## Overall Objective
${form.overallObjective || '[What we\'re ultimately trying to achieve]'}

## Context You Need
${form.overallContext || '[All relevant information for this subtask]'}

## Your Specific Task
${form.taskDescription || '[What this subagent needs to accomplish]'}

Priority: ${form.taskPriority}

## Resources Available
Tools: ${form.availableTools || '[list with brief descriptions]'}

Input data provided:
\`\`\`json
${form.inputData}
\`\`\`

## Constraints
\`\`\`json
${form.constraints}
\`\`\`

## Expected Output
Format: ${form.expectedOutputFormat || '[Exactly how to return results]'}

Success criteria:
${form.successCriteria || '[How we\'ll know this subtask is complete]'}

${form.deadline ? `## Deadline\nComplete by: ${form.deadline}` : ''}

${form.dependsOn ? `## Dependencies\nDepends on: ${form.dependsOn}` : ''}

${form.blocks ? `## Blocks\nThis work blocks: ${form.blocks}` : ''}

## Integration Plan
[How your work fits into larger system]`
  }

  const loadExample = (example: TaskForm) => {
    setForm(example)
    setSelectedPriority({
      label: example.taskPriority.charAt(0).toUpperCase() + example.taskPriority.slice(1),
      value: example.taskPriority
    })
  }

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Create tasks with complete context transfer following multi-agent best practices"
      >
        Task Delegation
      </Header>

      <Alert type="info" header="Critical Insight: Subagents need MORE context, not less">
        Agents trained on multi-agent tasks naturally become verbose when briefing subagents. Verbose
        context prevents: repeated clarification requests, assumptions contradicting overall goal,
        results that don't integrate well, and inefficient back-and-forth communication.
      </Alert>

      <Container
        header={
          <Header
            variant="h2"
            description="Compare good vs bad delegation practices"
            actions={
              <SpaceBetween direction="horizontal" size="xs">
                <Button onClick={() => loadExample(exampleBadDelegation)}>Load Bad Example</Button>
                <Button variant="primary" onClick={() => loadExample(exampleGoodDelegation)}>
                  Load Good Example
                </Button>
              </SpaceBetween>
            }
          >
            Examples
          </Header>
        }
      >
        <ColumnLayout columns={2} variant="text-grid">
          <div>
            <Box variant="h4" color="text-status-error">
              ❌ Bad Delegation
            </Box>
            <Box variant="code" padding="s">
              <pre style={{ fontSize: '12px' }}>
                {`"Research competitors in the AI tools market."

Problems:
- No context about overall objective
- No constraints or timeline
- No success criteria
- No resource information
- Agent must make assumptions`}
              </pre>
            </Box>
          </div>
          <div>
            <Box variant="h4" color="text-status-success">
              ✓ Good Delegation
            </Box>
            <Box variant="code" padding="s">
              <pre style={{ fontSize: '12px' }}>
                {`To: Research Specialist

## Overall Objective
Evaluate market entry into AI tools space.
Timeline: 6-month launch. Budget: $500k.

## Your Specific Task
Research competitive landscape for AI code
generation tools: pricing, features, customers,
positioning.

## Context You Need
- Team: 5 engineers with ML expertise
- Differentiator: Enterprise workflow integration
- Target: Mid-size tech companies (100-1000 employees)
- Priority regions: North America, Europe

[Complete context continues...]`}
              </pre>
            </Box>
          </div>
        </ColumnLayout>
      </Container>

      <Tabs
        tabs={[
          {
            label: 'Task Form',
            id: 'form',
            content: (
              <Container>
                <SpaceBetween size="m">
                  <ExpandableSection headerText="Overall Mission Context" defaultExpanded>
                    <SpaceBetween size="m">
                      <FormField
                        label="Overall Objective"
                        description="What are we ultimately trying to achieve? Include timeline and budget."
                      >
                        <Textarea
                          value={form.overallObjective}
                          onChange={(e) => setForm({ ...form, overallObjective: e.detail.value })}
                          placeholder="e.g., Evaluate market entry into the AI tools space for code generation. Timeline: 6-month launch window. Budget: $500k initial investment."
                          rows={3}
                        />
                      </FormField>

                      <FormField
                        label="Overall Context"
                        description="All relevant background information: team capabilities, differentiators, target market, prior work completed, constraints."
                      >
                        <Textarea
                          value={form.overallContext}
                          onChange={(e) => setForm({ ...form, overallContext: e.detail.value })}
                          placeholder="e.g., We're a team of 5 engineers with ML expertise. Our differentiator will be integration with enterprise workflows..."
                          rows={5}
                        />
                      </FormField>
                    </SpaceBetween>
                  </ExpandableSection>

                  <ExpandableSection headerText="Specific Task Details" defaultExpanded>
                    <SpaceBetween size="m">
                      <FormField
                        label="Task Description"
                        description="What specifically does this subagent need to accomplish?"
                      >
                        <Textarea
                          value={form.taskDescription}
                          onChange={(e) => setForm({ ...form, taskDescription: e.detail.value })}
                          placeholder="e.g., Research the competitive landscape for AI-powered code generation tools..."
                          rows={4}
                        />
                      </FormField>

                      <FormField label="Task Priority">
                        <Select
                          selectedOption={selectedPriority}
                          onChange={(e) => {
                            setSelectedPriority(e.detail.selectedOption)
                            setForm({
                              ...form,
                              taskPriority: e.detail.selectedOption.value as 'high' | 'medium' | 'low'
                            })
                          }}
                          options={[
                            { label: 'High', value: 'high' },
                            { label: 'Medium', value: 'medium' },
                            { label: 'Low', value: 'low' }
                          ]}
                        />
                      </FormField>
                    </SpaceBetween>
                  </ExpandableSection>

                  <ExpandableSection headerText="Resources & Constraints">
                    <SpaceBetween size="m">
                      <FormField
                        label="Available Tools"
                        description="Comma-separated list of tools the agent can use"
                      >
                        <Input
                          value={form.availableTools}
                          onChange={(e) => setForm({ ...form, availableTools: e.detail.value })}
                          placeholder="e.g., web_search, fetch_url, summarize_text"
                        />
                      </FormField>

                      <FormField label="Input Data" description="JSON object with input data">
                        <Textarea
                          value={form.inputData}
                          onChange={(e) => setForm({ ...form, inputData: e.detail.value })}
                          rows={5}
                        />
                      </FormField>

                      <FormField label="Constraints" description="JSON object with constraints">
                        <Textarea
                          value={form.constraints}
                          onChange={(e) => setForm({ ...form, constraints: e.detail.value })}
                          rows={5}
                        />
                      </FormField>
                    </SpaceBetween>
                  </ExpandableSection>

                  <ExpandableSection headerText="Output Requirements">
                    <SpaceBetween size="m">
                      <FormField
                        label="Expected Output Format"
                        description="Exactly how should the agent return results?"
                      >
                        <Textarea
                          value={form.expectedOutputFormat}
                          onChange={(e) =>
                            setForm({ ...form, expectedOutputFormat: e.detail.value })
                          }
                          placeholder="e.g., Structured markdown report with: Executive summary, Competitor analysis table, Key insights, Recommendations"
                          rows={3}
                        />
                      </FormField>

                      <FormField
                        label="Success Criteria"
                        description="How will we know this subtask is complete? One per line."
                      >
                        <Textarea
                          value={form.successCriteria}
                          onChange={(e) => setForm({ ...form, successCriteria: e.detail.value })}
                          placeholder={'- Identified 8-10 direct competitors\n- Documented pricing models\n- Analyzed feature differentiation'}
                          rows={5}
                        />
                      </FormField>
                    </SpaceBetween>
                  </ExpandableSection>

                  <ExpandableSection headerText="Dependencies & Timeline">
                    <SpaceBetween size="m">
                      <FormField label="Deadline (ISO format)" description="When must this be completed?">
                        <Input
                          value={form.deadline}
                          onChange={(e) => setForm({ ...form, deadline: e.detail.value })}
                          placeholder="e.g., 2025-10-23T17:00:00Z"
                          type="text"
                        />
                      </FormField>

                      <FormField
                        label="Depends On"
                        description="Comma-separated list of task IDs this depends on"
                      >
                        <Input
                          value={form.dependsOn}
                          onChange={(e) => setForm({ ...form, dependsOn: e.detail.value })}
                          placeholder="e.g., task-123, task-456"
                        />
                      </FormField>

                      <FormField
                        label="Blocks"
                        description="Comma-separated list of task IDs that depend on this"
                      >
                        <Input
                          value={form.blocks}
                          onChange={(e) => setForm({ ...form, blocks: e.detail.value })}
                          placeholder="e.g., product-feature-prioritization, pricing-strategy"
                        />
                      </FormField>
                    </SpaceBetween>
                  </ExpandableSection>
                </SpaceBetween>
              </Container>
            )
          },
          {
            label: 'Generated Prompt',
            id: 'prompt',
            content: (
              <Container>
                <SpaceBetween size="m">
                  <Alert type="success" header="Context Transfer Template">
                    This prompt includes all the context a subagent needs to work autonomously. Copy
                    this to send to your specialist agent.
                  </Alert>
                  <FormField label="Task Delegation Prompt">
                    <Textarea value={generatePrompt()} readOnly rows={25} />
                  </FormField>
                  <Button variant="primary" iconName="copy">
                    Copy to Clipboard
                  </Button>
                </SpaceBetween>
              </Container>
            )
          },
          {
            label: 'Best Practices',
            id: 'best-practices',
            content: (
              <Container>
                <SpaceBetween size="l">
                  <Box>
                    <Box variant="h3">Context Transfer Best Practices</Box>
                    <Box variant="p">
                      Follow these guidelines when delegating tasks to subagents:
                    </Box>
                  </Box>

                  <ColumnLayout columns={2} variant="text-grid">
                    <div>
                      <Box variant="h4">✓ Do This</Box>
                      <Box component="ul">
                        <li>Provide complete overall objective and context</li>
                        <li>Explain WHY the subtask matters to the whole</li>
                        <li>Include all constraints and dependencies upfront</li>
                        <li>Specify exact output format and success criteria</li>
                        <li>List available resources and tools</li>
                        <li>Be verbose - more context is better than less</li>
                        <li>Include examples of expected output</li>
                      </Box>
                    </div>
                    <div>
                      <Box variant="h4">✗ Don't Do This</Box>
                      <Box component="ul">
                        <li>Send minimal task description</li>
                        <li>Assume agent will infer context</li>
                        <li>Omit overall objective</li>
                        <li>Leave success criteria vague</li>
                        <li>Skip resource and constraint information</li>
                        <li>Use brief, terse instructions</li>
                        <li>Expect agent to ask for clarification</li>
                      </Box>
                    </div>
                  </ColumnLayout>

                  <Box>
                    <Box variant="h4">Why Verbose Context Works</Box>
                    <ColumnLayout columns={2} variant="text-grid">
                      <div>
                        <Box variant="strong">Prevents:</Box>
                        <Box component="ul">
                          <li>Repeated clarification requests</li>
                          <li>Assumptions contradicting overall goal</li>
                          <li>Results that don't integrate well</li>
                          <li>Inefficient back-and-forth communication</li>
                        </Box>
                      </div>
                      <div>
                        <Box variant="strong">Enables:</Box>
                        <Box component="ul">
                          <li>Autonomous work without interruption</li>
                          <li>Results that align with overall objective</li>
                          <li>Efficient use of agent capabilities</li>
                          <li>Better integration with other work streams</li>
                        </Box>
                      </div>
                    </ColumnLayout>
                  </Box>
                </SpaceBetween>
              </Container>
            )
          }
        ]}
      />
    </SpaceBetween>
  )
}
