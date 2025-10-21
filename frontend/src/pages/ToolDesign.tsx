import { useState } from 'react'
import Container from '@cloudscape-design/components/container'
import Header from '@cloudscape-design/components/header'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Box from '@cloudscape-design/components/box'
import ColumnLayout from '@cloudscape-design/components/column-layout'
import Alert from '@cloudscape-design/components/alert'
import Tabs from '@cloudscape-design/components/tabs'
import Table from '@cloudscape-design/components/table'
import Badge from '@cloudscape-design/components/badge'
import Cards from '@cloudscape-design/components/cards'
import ProgressBar from '@cloudscape-design/components/progress-bar'

interface ToolComparison {
  task: string
  api_centric: {
    description: string
    calls: number
    code: string
  }
  ui_centric: {
    description: string
    calls: number
    code: string
  }
}

const toolComparisons: ToolComparison[] = [
  {
    task: 'Get message with author and channel info',
    api_centric: {
      description: 'Agent needs 3 separate calls to get complete information',
      calls: 3,
      code: `# Call 1: Get message
msg = get_message(id)
# Returns: {user_id: "123", channel_id: "456", text: "Hello"}

# Call 2: Get user info
user = get_user(msg.user_id)
# Returns: {username: "john"}

# Call 3: Get channel info
channel = get_channel(msg.channel_id)
# Returns: {channel_name: "#engineering"}

# Agent must manually join the data
full_context = {
  "text": msg.text,
  "author": user.username,
  "channel": channel.channel_name
}`
    },
    ui_centric: {
      description: 'Agent gets everything in one call, just like a human sees in the UI',
      calls: 1,
      code: `# Single call with complete context
msg = get_message_complete(id)
# Returns: {
#   text: "Hello",
#   author_name: "John Smith",
#   author_email: "john@company.com",
#   author_title: "Senior Engineer",
#   channel_name: "#engineering",
#   channel_description: "Engineering team",
#   timestamp: "2025-10-20T10:30:00Z",
#   reactions: [{emoji: "👍", count: 3}],
#   thread_info: {reply_count: 5}
# }

# Agent has everything immediately`
    }
  },
  {
    task: 'List files with metadata',
    api_centric: {
      description: 'Multiple calls to get file details',
      calls: 5,
      code: `# Call 1: List files
files = list_files("/src")
# Returns: ["a.py", "b.py", "c.py"]

# Call 2-4: Get metadata for each (3 calls)
for file in files:
  stats = get_file_stats(file)
  # Returns: {size: 1024, modified: "..."}

# Call 5: Get file types
types = get_file_types(files)

# Total: 5 calls for basic file listing`
    },
    ui_centric: {
      description: 'Single call returns everything visible in a file explorer',
      calls: 1,
      code: `# Single call with complete file information
files = list_files_complete("/src")
# Returns: [
#   {
#     path: "/src/a.py",
#     name: "a.py",
#     size: 1024,
#     size_human: "1 KB",
#     modified: "2025-10-20T10:30:00Z",
#     modified_relative: "2 hours ago",
#     type: "Python",
#     permissions: "rw-r--r--",
#     lines: 50
#   },
#   { ... more files ... }
# ]

# Everything an agent needs in one call`
    }
  },
  {
    task: 'Get PR with review status',
    api_centric: {
      description: 'Agent must make multiple calls and join data',
      calls: 6,
      code: `# Call 1: Get PR
pr = get_pr(123)

# Call 2: Get author
author = get_user(pr.author_id)

# Call 3: Get reviewers
reviewers = get_reviewers(pr.id)

# Call 4: Get review status
statuses = get_review_statuses(pr.id)

# Call 5: Get CI status
ci = get_ci_status(pr.id)

# Call 6: Get changed files
files = get_pr_files(pr.id)

# Total: 6 calls to understand one PR`
    },
    ui_centric: {
      description: 'Complete PR context like GitHub UI shows',
      calls: 1,
      code: `# Single call with everything from PR page
pr = get_pr_complete(123)
# Returns: {
#   title: "Add authentication",
#   author: {name: "John", email: "john@co.com"},
#   status: "open",
#   reviewers: [
#     {name: "Alice", status: "approved"},
#     {name: "Bob", status: "changes_requested"}
#   ],
#   ci_status: "passing",
#   checks: [{name: "tests", status: "success"}],
#   files_changed: 5,
#   additions: 120,
#   deletions: 30,
#   comments_count: 8
# }

# Agent sees complete PR state immediately`
    }
  }
]

const designChecklist = [
  {
    question: 'Does this tool require multiple calls to get basic info?',
    bad: 'YES → REDESIGN (bundle information)',
    good: 'NO → Continue'
  },
  {
    question: 'Does it return IDs that need resolution?',
    bad: 'YES → REDESIGN (pre-resolve to names)',
    good: 'NO → Continue'
  },
  {
    question: 'Would a human need this info in the UI?',
    bad: 'NO → Consider if agent really needs it',
    good: 'YES → Include it'
  },
  {
    question: 'Agent makes same call repeatedly?',
    bad: 'YES → Add caching or bundle data',
    good: 'NO → Good design'
  },
  {
    question: 'Tool calls average >5 per common task?',
    bad: 'YES → Redesign tools to bundle operations',
    good: 'NO → Acceptable efficiency'
  }
]

const redFlags = [
  {
    symptom: 'Agent makes same tool call repeatedly',
    problem: 'Missing information in tool response',
    solution: 'Bundle related data in single call'
  },
  {
    symptom: 'Agent needs >3 calls for common tasks',
    problem: 'Tools too granular (API-centric)',
    solution: 'Create composite tools for workflows'
  },
  {
    symptom: 'Agent asks for information it should have',
    problem: 'Incomplete context in responses',
    solution: 'Include all UI-visible information'
  },
  {
    symptom: 'Many ID resolution calls needed',
    problem: 'Returning IDs instead of human-readable info',
    solution: 'Pre-resolve IDs to names/descriptions'
  },
  {
    symptom: 'Agent struggles to maintain context',
    problem: 'Information split across many calls',
    solution: 'Bundle complete context in responses'
  }
]

export default function ToolDesign() {
  const [selectedComparison, setSelectedComparison] = useState(0)

  const comparison = toolComparisons[selectedComparison]
  const savings = comparison.api_centric.calls - comparison.ui_centric.calls
  const efficiency = Math.round((savings / comparison.api_centric.calls) * 100)

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Learn to design tools that minimize agent overhead and improve efficiency"
      >
        Tool Design Analyzer
      </Header>

      <Alert type="info" header="Commandment #3: Tools Should Mirror UI, Not API">
        Tools should present complete, contextualized information like user interfaces, not require
        multiple API-style calls. This is the #1 way to reduce agent tool calls and improve
        efficiency.
      </Alert>

      <Container header={<Header variant="h2">API-Centric vs UI-Centric Comparison</Header>}>
        <SpaceBetween size="m">
          <Box>
            <Box variant="awsui-key-label" padding={{ bottom: 'xs' }}>
              Select Task
            </Box>
            <SpaceBetween direction="horizontal" size="xs">
              {toolComparisons.map((comp, idx) => (
                <Box
                  key={idx}
                  variant="a"
                  fontSize="body-m"
                  onClick={() => setSelectedComparison(idx)}
                  color={idx === selectedComparison ? 'text-status-info' : 'text-link-default'}
                >
                  {comp.task}
                </Box>
              ))}
            </SpaceBetween>
          </Box>

          <ColumnLayout columns={3} variant="text-grid">
            <div>
              <Box variant="awsui-key-label">Task</Box>
              <Box variant="h4">{comparison.task}</Box>
            </div>
            <div>
              <Box variant="awsui-key-label">Tool Calls Saved</Box>
              <Box fontSize="heading-xl" color="text-status-success">
                {savings} calls ({efficiency}% reduction)
              </Box>
            </div>
            <div>
              <Box variant="awsui-key-label">Efficiency Gain</Box>
              <ProgressBar value={efficiency} variant="flash" />
            </div>
          </ColumnLayout>

          <Tabs
            tabs={[
              {
                label: `❌ API-Centric (${comparison.api_centric.calls} calls)`,
                id: 'api',
                content: (
                  <SpaceBetween size="m">
                    <Alert type="error" header="Why This is Bad">
                      {comparison.api_centric.description}
                    </Alert>
                    <Box>
                      <Box variant="h4" padding={{ bottom: 's' }}>
                        Code Example
                      </Box>
                      <Box variant="code" padding="m">
                        <pre>{comparison.api_centric.code}</pre>
                      </Box>
                    </Box>
                    <ColumnLayout columns={2} variant="text-grid">
                      <div>
                        <Box variant="h5">Problems</Box>
                        <Box component="ul">
                          <li>Multiple sequential calls required</li>
                          <li>Agent must join data manually</li>
                          <li>Higher latency (network roundtrips)</li>
                          <li>More complex agent logic</li>
                          <li>Easy to miss related information</li>
                        </Box>
                      </div>
                      <div>
                        <Box variant="h5">Impact</Box>
                        <Box component="ul">
                          <li>
                            <Badge color="red">
                              {comparison.api_centric.calls} tool calls per task
                            </Badge>
                          </li>
                          <li>Slower agent execution</li>
                          <li>Higher cost (more API calls)</li>
                          <li>More prone to errors</li>
                          <li>Harder to debug</li>
                        </Box>
                      </div>
                    </ColumnLayout>
                  </SpaceBetween>
                )
              },
              {
                label: `✅ UI-Centric (${comparison.ui_centric.calls} call)`,
                id: 'ui',
                content: (
                  <SpaceBetween size="m">
                    <Alert type="success" header="Why This is Better">
                      {comparison.ui_centric.description}
                    </Alert>
                    <Box>
                      <Box variant="h4" padding={{ bottom: 's' }}>
                        Code Example
                      </Box>
                      <Box variant="code" padding="m">
                        <pre>{comparison.ui_centric.code}</pre>
                      </Box>
                    </Box>
                    <ColumnLayout columns={2} variant="text-grid">
                      <div>
                        <Box variant="h5">Benefits</Box>
                        <Box component="ul">
                          <li>Single call gets everything</li>
                          <li>Complete context immediately available</li>
                          <li>Lower latency (one roundtrip)</li>
                          <li>Simpler agent logic</li>
                          <li>Nothing gets missed</li>
                        </Box>
                      </div>
                      <div>
                        <Box variant="h5">Impact</Box>
                        <Box component="ul">
                          <li>
                            <Badge color="green">{comparison.ui_centric.calls} tool call per task</Badge>
                          </li>
                          <li>Faster agent execution</li>
                          <li>Lower cost (fewer API calls)</li>
                          <li>More reliable results</li>
                          <li>Easier to debug</li>
                        </Box>
                      </div>
                    </ColumnLayout>
                  </SpaceBetween>
                )
              }
            ]}
          />
        </SpaceBetween>
      </Container>

      <Container
        header={<Header variant="h2">Tool Design Checklist</Header>}
      >
        <Table
          columnDefinitions={[
            {
              id: 'question',
              header: 'Question to Ask',
              cell: (item) => item.question
            },
            {
              id: 'bad',
              header: '❌ If Yes / Bad',
              cell: (item) => <Box color="text-status-error">{item.bad}</Box>
            },
            {
              id: 'good',
              header: '✅ If No / Good',
              cell: (item) => <Box color="text-status-success">{item.good}</Box>
            }
          ]}
          items={designChecklist}
          variant="embedded"
        />
      </Container>

      <Container
        header={<Header variant="h2">Red Flags: Your Tool Design Needs Work If...</Header>}
      >
        <Cards
          cardDefinition={{
            header: (item) => (
              <Box>
                <Badge color="red">Red Flag</Badge>
                <Box variant="h4" padding={{ top: 'xs' }}>
                  {item.symptom}
                </Box>
              </Box>
            ),
            sections: [
              {
                id: 'problem',
                header: 'Problem',
                content: (item) => <Box color="text-status-error">{item.problem}</Box>
              },
              {
                id: 'solution',
                header: 'Solution',
                content: (item) => <Box color="text-status-success">✓ {item.solution}</Box>
              }
            ]
          }}
          items={redFlags}
          cardsPerRow={[{ cards: 1 }, { minWidth: 500, cards: 2 }]}
        />
      </Container>

      <Container
        header={
          <Header variant="h2" description="Following these guidelines will dramatically reduce tool calls">
            Tool Design Best Practices
          </Header>
        }
      >
        <ColumnLayout columns={2} variant="text-grid">
          <div>
            <Box variant="h3" color="text-status-success">
              ✓ Do This
            </Box>
            <Box component="ul">
              <li>
                <Box variant="strong">Bundle related information</Box>
                <br />
                Return everything a human would see in the UI
              </li>
              <li>
                <Box variant="strong">Pre-resolve IDs</Box>
                <br />
                Return "John Smith" not "user_id: 123"
              </li>
              <li>
                <Box variant="strong">Include metadata</Box>
                <br />
                Add timestamps, counts, status indicators
              </li>
              <li>
                <Box variant="strong">Provide context</Box>
                <br />
                Include related objects and relationships
              </li>
              <li>
                <Box variant="strong">Think workflows</Box>
                <br />
                Create tools for common multi-step tasks
              </li>
              <li>
                <Box variant="strong">Add smart defaults</Box>
                <br />
                Make common cases require fewer parameters
              </li>
            </Box>
          </div>
          <div>
            <Box variant="h3" color="text-status-error">
              ✗ Don't Do This
            </Box>
            <Box component="ul">
              <li>
                <Box variant="strong">Return minimal data</Box>
                <br />
                Forcing agent to make more calls
              </li>
              <li>
                <Box variant="strong">Return IDs without resolution</Box>
                <br />
                Requiring additional lookup calls
              </li>
              <li>
                <Box variant="strong">Omit obvious metadata</Box>
                <br />
                Missing timestamps, counts, etc.
              </li>
              <li>
                <Box variant="strong">Strip context</Box>
                <br />
                Returning objects in isolation
              </li>
              <li>
                <Box variant="strong">Create single-purpose tools</Box>
                <br />
                When workflows need multiple steps
              </li>
              <li>
                <Box variant="strong">Require all parameters</Box>
                <br />
                When smart defaults would work
              </li>
            </Box>
          </div>
        </ColumnLayout>
      </Container>

      <Container
        header={<Header variant="h2">Real-World Example: Slack Integration</Header>}
      >
        <Tabs
          tabs={[
            {
              label: '❌ Bad Design',
              id: 'bad-slack',
              content: (
                <Box variant="code" padding="m">
                  <pre>
                    {`# API-Centric Slack Tools (BAD)

def get_message(message_id):
    """Get basic message info"""
    return {
        "id": "msg_123",
        "user_id": "U123",
        "channel_id": "C456",
        "text": "Check out this new feature",
        "ts": "1698765432.123456"
    }

def get_user(user_id):
    """Get user info"""
    return {
        "id": "U123",
        "name": "john"
    }

def get_channel(channel_id):
    """Get channel info"""
    return {
        "id": "C456",
        "name": "engineering"
    }

# Agent needs 3+ calls to understand one message!
# Plus additional calls for reactions, threads, etc.`}
                  </pre>
                </Box>
              )
            },
            {
              label: '✅ Good Design',
              id: 'good-slack',
              content: (
                <Box variant="code" padding="m">
                  <pre>
                    {`# UI-Centric Slack Tools (GOOD)

def get_conversation_complete(channel, limit=50):
    """
    Get Slack conversation with complete context.

    Returns everything visible in Slack UI: message content,
    author info, channel details, thread context, reactions.
    """
    return {
        "channel": {
            "name": "#engineering",
            "description": "Engineering team channel",
            "member_count": 45,
            "is_private": False
        },
        "messages": [
            {
                "text": "Check out this new feature",
                "author": {
                    "name": "John Smith",
                    "email": "john@company.com",
                    "title": "Senior Engineer",
                    "avatar": "https://..."
                },
                "timestamp": "2025-10-20T10:30:00Z",
                "timestamp_relative": "2 hours ago",
                "reactions": [
                    {
                        "emoji": "👍",
                        "count": 3,
                        "users": ["Alice", "Bob", "Carol"]
                    }
                ],
                "thread_info": {
                    "is_thread_parent": True,
                    "reply_count": 3,
                    "latest_reply": "2025-10-20T11:00:00Z"
                },
                "attachments": [...],
                "mentions": ["@alice"]
            }
        ],
        "has_more": False,
        "total_messages": 47
    }

# Agent gets EVERYTHING in one call!
# Just like a human sees in the Slack UI`}
                  </pre>
                </Box>
              )
            }
          ]}
        />
      </Container>
    </SpaceBetween>
  )
}
