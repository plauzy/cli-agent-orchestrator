import { useEffect, useState } from 'react'
import Container from '@cloudscape-design/components/container'
import Header from '@cloudscape-design/components/header'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Grid from '@cloudscape-design/components/grid'
import Box from '@cloudscape-design/components/box'
import StatusIndicator from '@cloudscape-design/components/status-indicator'
import ColumnLayout from '@cloudscape-design/components/column-layout'
import Cards from '@cloudscape-design/components/cards'
import Badge from '@cloudscape-design/components/badge'
import Button from '@cloudscape-design/components/button'
import Link from '@cloudscape-design/components/link'
import { Session, Terminal, TerminalStatus } from '../types'
import axios from 'axios'

export default function Dashboard() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadSessions()
    const interval = setInterval(loadSessions, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [])

  const loadSessions = async () => {
    try {
      const response = await axios.get('/api/sessions')
      setSessions(response.data)
    } catch (error) {
      console.error('Failed to load sessions:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusIndicator = (status: TerminalStatus) => {
    switch (status) {
      case TerminalStatus.IDLE:
        return <StatusIndicator>Idle</StatusIndicator>
      case TerminalStatus.BUSY:
        return <StatusIndicator type="in-progress">Busy</StatusIndicator>
      case TerminalStatus.COMPLETED:
        return <StatusIndicator type="success">Completed</StatusIndicator>
      case TerminalStatus.ERROR:
        return <StatusIndicator type="error">Error</StatusIndicator>
      default:
        return <StatusIndicator>Unknown</StatusIndicator>
    }
  }

  const totalTerminals = sessions.reduce((sum, s) => sum + s.terminals.length, 0)
  const activeTerminals = sessions.reduce(
    (sum, s) => sum + s.terminals.filter(t => t.status === TerminalStatus.BUSY).length,
    0
  )

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Real-time monitoring and management of multi-agent workflows"
        actions={
          <Button variant="primary" onClick={loadSessions}>
            Refresh
          </Button>
        }
      >
        Multi-Agent Dashboard
      </Header>

      <Grid gridDefinition={[{ colspan: 4 }, { colspan: 4 }, { colspan: 4 }]}>
        <Container>
          <Box textAlign="center" padding={{ vertical: 'l' }}>
            <Box variant="awsui-key-label">Active Sessions</Box>
            <Box fontSize="display-l" fontWeight="bold" color="text-status-info">
              {sessions.length}
            </Box>
          </Box>
        </Container>

        <Container>
          <Box textAlign="center" padding={{ vertical: 'l' }}>
            <Box variant="awsui-key-label">Total Agents</Box>
            <Box fontSize="display-l" fontWeight="bold">
              {totalTerminals}
            </Box>
          </Box>
        </Container>

        <Container>
          <Box textAlign="center" padding={{ vertical: 'l' }}>
            <Box variant="awsui-key-label">Active Agents</Box>
            <Box fontSize="display-l" fontWeight="bold" color="text-status-success">
              {activeTerminals}
            </Box>
          </Box>
        </Container>
      </Grid>

      <Container header={<Header variant="h2">Architecture Overview</Header>}>
        <SpaceBetween size="l">
          <Box>
            <Box variant="h3" padding={{ bottom: 's' }}>
              The Three Commandments
            </Box>
            <ColumnLayout columns={3} variant="text-grid">
              <div>
                <Box variant="strong">1. Start Simple</Box>
                <Box variant="p" color="text-body-secondary">
                  Single agent before multi-agent. Minimal tools before extensive toolkit.
                  Measure before adding complexity.
                </Box>
              </div>
              <div>
                <Box variant="strong">2. Agent's Point of View</Box>
                <Box variant="p" color="text-body-secondary">
                  The agent only knows what it sees. Design everything from its perspective.
                  Review transcripts and verify context completeness.
                </Box>
              </div>
              <div>
                <Box variant="strong">3. Tools Mirror UI, Not API</Box>
                <Box variant="p" color="text-body-secondary">
                  Tools should present complete, contextualized information like user interfaces,
                  not require multiple API-style calls.
                </Box>
              </div>
            </ColumnLayout>
          </Box>

          <Box>
            <Box variant="h3" padding={{ bottom: 's' }}>
              Quick Decision Guide
            </Box>
            <Box padding="m" variant="code">
              Can one agent handle all tools (&lt;20)?
              <br />
              ├─ YES → Use Single-Agent
              <br />
              └─ NO → Continue
              <br />
              &nbsp;&nbsp;&nbsp;&nbsp;│<br />
              &nbsp;&nbsp;&nbsp;&nbsp;Can tasks run in parallel?
              <br />
              &nbsp;&nbsp;&nbsp;&nbsp;├─ YES → Use Multi-Agent (Parallel Pattern)
              <br />
              &nbsp;&nbsp;&nbsp;&nbsp;└─ NO → Continue
              <br />
              &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br />
              &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Do tasks need specialized context?
              <br />
              &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├─ YES → Use Multi-Agent
              (Coordinator-Specialist)
              <br />
              &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└─ NO → Use Single-Agent (simplify tools
              instead)
            </Box>
          </Box>
        </SpaceBetween>
      </Container>

      <Container header={<Header variant="h2">Active Sessions</Header>}>
        {loading ? (
          <Box textAlign="center" padding="l">
            <StatusIndicator type="loading">Loading sessions...</StatusIndicator>
          </Box>
        ) : sessions.length === 0 ? (
          <Box textAlign="center" padding="l" color="text-body-secondary">
            No active sessions. Launch a new agent session to get started.
          </Box>
        ) : (
          <Cards
            cardDefinition={{
              header: (session) => (
                <Link fontSize="heading-m" href={`/sessions/${session.id}`}>
                  {session.name}
                </Link>
              ),
              sections: [
                {
                  id: 'terminals',
                  header: 'Agent Terminals',
                  content: (session) => (
                    <SpaceBetween size="xs">
                      {session.terminals.map((terminal: Terminal) => (
                        <Box key={terminal.id}>
                          <ColumnLayout columns={3} variant="text-grid">
                            <div>
                              <Box variant="awsui-key-label">Terminal ID</Box>
                              <Box>{terminal.id.substring(0, 8)}...</Box>
                            </div>
                            <div>
                              <Box variant="awsui-key-label">Agent Profile</Box>
                              <Badge color="blue">{terminal.agent_profile || 'N/A'}</Badge>
                            </div>
                            <div>
                              <Box variant="awsui-key-label">Status</Box>
                              {getStatusIndicator(terminal.status)}
                            </div>
                          </ColumnLayout>
                        </Box>
                      ))}
                    </SpaceBetween>
                  )
                },
                {
                  id: 'created',
                  header: 'Created',
                  content: (session) => new Date(session.created_at).toLocaleString()
                }
              ]
            }}
            items={sessions}
            cardsPerRow={[{ cards: 1 }, { minWidth: 500, cards: 2 }]}
          />
        )}
      </Container>

      <Container
        header={
          <Header
            variant="h2"
            description="Navigate to different sections to explore multi-agent workflow capabilities"
          >
            Explore Features
          </Header>
        }
      >
        <ColumnLayout columns={2} variant="text-grid">
          <div>
            <Box variant="h4" padding={{ bottom: 'xs' }}>
              <Link href="/orchestration">Agent Orchestration</Link>
            </Box>
            <Box variant="p" color="text-body-secondary">
              View and manage coordinator and specialist agents. Visualize agent hierarchies and
              delegation patterns.
            </Box>
          </div>
          <div>
            <Box variant="h4" padding={{ bottom: 'xs' }}>
              <Link href="/delegation">Task Delegation</Link>
            </Box>
            <Box variant="p" color="text-body-secondary">
              Create tasks with complete context transfer. Use templates to ensure agents receive
              all necessary information.
            </Box>
          </div>
          <div>
            <Box variant="h4" padding={{ bottom: 'xs' }}>
              <Link href="/patterns">Workflow Patterns</Link>
            </Box>
            <Box variant="p" color="text-body-secondary">
              Explore handoff, assign, and send message patterns. Compare different orchestration
              modes for your use case.
            </Box>
          </div>
          <div>
            <Box variant="h4" padding={{ bottom: 'xs' }}>
              <Link href="/tool-design">Tool Design Analyzer</Link>
            </Box>
            <Box variant="p" color="text-body-secondary">
              Analyze your tools for UI-centric vs API-centric design. Get recommendations to
              reduce agent tool calls.
            </Box>
          </div>
        </ColumnLayout>
      </Container>
    </SpaceBetween>
  )
}
