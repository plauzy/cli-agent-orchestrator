# CLI Agent Orchestrator

CLI Agent Orchestrator(CAO, pronounced as "kay-oh"), is a lightweight orchestration system for managing multiple AI agent sessions in tmux terminals. Enables Multi-agent collaboration via MCP server.

## Hierarchical Multi-Agent System

CLI Agent Orchestrator (CAO) implements a hierarchical multi-agent system that enables complex problem-solving through specialized division of CLI Developer Agents.

![CAO Architecture](./docs/assets/cao_architecture.png)

### Key Features

* **Hierarchical orchestration** – CAO's supervisor agent coordinates workflow management and task delegation to specialized worker agents. The supervisor maintains overall project context while agents focus on their domains of expertise.

* **Session-based isolation** – Each agent operates in isolated tmux sessions, ensuring proper context separation while enabling seamless communication through Model Context Protocol (MCP) servers. This provides both coordination and parallel processing capabilities.

* **Intelligent task delegation** – CAO automatically routes tasks to appropriate specialists based on project requirements, expertise matching, and workflow dependencies. The system adapts between individual agent work and coordinated team efforts through three orchestration patterns:
  - **Handoff** - Synchronous task transfer with wait-for-completion
  - **Assign** - Asynchronous task spawning for parallel execution  
  - **Send Message** - Direct communication with existing agents

* **Flexible workflow patterns** – CAO supports both sequential coordination for dependent tasks and parallel processing for independent work streams. This allows optimization of both development speed and quality assurance processes.

* **Flow - Scheduled runs** – Automated execution of workflows at specified intervals using cron-like scheduling, enabling routine tasks and monitoring workflows to run unattended.

* **Context preservation** – The supervisor agent provides only necessary context to each worker agent, avoiding context pollution while maintaining workflow coherence.

* **Direct worker interaction and steering** – Users can interact directly with worker agents to provide additional steering, distinguishing from sub-agents features by allowing real-time guidance and course correction.

* **Advanced CLI integration** – CAO agents have full access to advanced features of the developer CLI, such as the [sub-agents](https://docs.claude.com/en/docs/claude-code/sub-agents) feature of Claude Code, [Custom Agent](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/command-line-custom-agents.html) of Amazon Q Developer for CLI and so on.

For detailed project structure and architecture, see [CODEBASE.md](CODEBASE.md).

## Installation

1. Install tmux (version 3.3 or higher required)

```bash
bash <(curl -s https://raw.githubusercontent.com/awslabs/cli-agent-orchestrator/refs/heads/main/tmux-install.sh)
```

2. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Install CLI Agent Orchestrator:
```bash
uv tool install git+https://github.com/awslabs/cli-agent-orchestrator.git@main --upgrade
```

## Quick Start

### Installing Agents

CAO supports installing agents from multiple sources:

**1. Install built-in agents (bundled with CAO):**
```bash
cao install code_supervisor
cao install developer
cao install reviewer
```

**2. Install from a local file:**
```bash
cao install ./my-custom-agent.md
cao install /absolute/path/to/agent.md
```

**3. Install from a URL:**
```bash
cao install https://example.com/agents/custom-agent.md
```

When installing from a file or URL, the agent is saved to your local agent store (`~/.aws/cli-agent-orchestrator/agent-store/`) and can be referenced by name in future installations.

For details on creating custom agent profiles, see [docs/agent-profile.md](docs/agent-profile.md).

### Launching Agents

Start the cao server:
```bash
cao-server
```

In another terminal, launch a terminal with an agent profile:
```bash
cao launch --agents code_supervisor
```

Shutdown sessions:
```bash
# Shutdown all cao sessions
cao shutdown --all

# Shutdown specific session
cao shutdown --session cao-my-session
```

### Working with tmux Sessions

All agent sessions run in tmux. Useful commands:

```bash
# List all sessions
tmux list-sessions

# Attach to a session
tmux attach -t <session-name>

# Detach from session (inside tmux)
Ctrl+b, then d

# Delete a session
cao shutdown --session <session-name>
```

## MCP Server Tools and Orchestration Modes

CAO provides a local HTTP server that processes orchestration requests. CLI agents can interact with this server through MCP tools to coordinate multi-agent workflows.

### How It Works

Each agent terminal is assigned a unique `CAO_TERMINAL_ID` environment variable. The server uses this ID to:
- Route messages between agents
- Track terminal status (IDLE, BUSY, COMPLETED, ERROR)
- Manage terminal-to-terminal communication via inbox
- Coordinate orchestration operations

When an agent calls an MCP tool, the server identifies the caller by their `CAO_TERMINAL_ID` and orchestrates accordingly.

### Orchestration Modes

CAO supports three orchestration patterns:

**1. Handoff** - Transfer control to another agent and wait for completion
- Creates a new terminal with the specified agent profile
- Sends the task message and waits for the agent to finish
- Returns the agent's output to the caller
- Automatically exits the agent after completion
- Use when you need **synchronous** task execution with results

Example: Sequential code review workflow

![Handoff Workflow](./docs/assets/handoff-workflow.png)

**2. Assign** - Spawn an agent to work independently (async)
- Creates a new terminal with the specified agent profile
- Sends the task message with callback instructions
- Returns immediately with the terminal ID
- Agent continues working in the background
- Assigned agent sends results back to supervisor via `send_message` when complete
- Messages are queued for delivery if the supervisor is busy (common in parallel workflows)
- Use for **asynchronous** task execution or fire-and-forget operations

Example: Parallel test execution

![Parallel Test Execution](./docs/assets/parallel-test-execution.png)

**3. Send Message** - Communicate with an existing agent
- Sends a message to a specific terminal's inbox
- Messages are queued and delivered when the terminal is idle
- Enables ongoing collaboration between agents
- Common for **swarm** operations where multiple agents coordinate dynamically
- Use for iterative feedback or multi-turn conversations

Example: Multi-role feature development
![Multi-role Feature Development](./docs/assets/multi-role-feature-development.png)

### Custom Orchestration

The `cao-server` runs on `http://localhost:9889` by default and exposes REST APIs for session management, terminal control, and messaging. The CLI commands (`cao launch`, `cao shutdown`) and MCP server tools (`handoff`, `assign`, `send_message`) are just examples of how these APIs can be packaged together.

You can combine the three orchestration modes above into custom workflows, or create entirely new orchestration patterns using the underlying APIs to fit your specific needs.

For complete API documentation, see [docs/api.md](docs/api.md).

## Flows - Scheduled Agent Sessions

Flows allow you to schedule agent sessions to run automatically based on cron expressions.

### Prerequisites

Install the agent profile you want to use:
```bash
cao install developer
```

### Quick Start

The example flow asks a simple world trivia question every morning at 7:30 AM.

```bash
# 1. Start the cao server
cao-server

# 2. In another terminal, add a flow
cao flow add examples/flow/morning-trivia.md

# 3. List flows to see schedule and status
cao flow list

# 4. Manually run a flow (optional - for testing)
cao flow run morning-trivia

# 5. View flow execution (after it runs)
tmux list-sessions
tmux attach -t <session-name>

# 6. Cleanup session when done
cao shutdown --session <session-name>
```

**IMPORTANT:** The `cao-server` must be running for flows to execute on schedule.

### Example 1: Simple Scheduled Task

A flow that runs at regular intervals with a static prompt (no script needed):

**File: `daily-standup.md`**
```yaml
---
name: daily-standup
schedule: "0 9 * * 1-5"  # 9am weekdays
agent_profile: developer
---

Review yesterday's commits and create a standup summary.
```

### Example 2: Conditional Execution with Health Check

A flow that monitors a service and only executes when there's an issue:

**File: `monitor-service.md`**
```yaml
---
name: monitor-service
schedule: "*/5 * * * *"  # Every 5 minutes
agent_profile: developer
script: ./health-check.sh
---

The service at [[url]] is down (status: [[status_code]]).
Please investigate and triage the issue:
1. Check recent deployments
2. Review error logs
3. Identify root cause
4. Suggest remediation steps
```

**Script: `health-check.sh`**
```bash
#!/bin/bash
URL="https://api.example.com/health"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL")

if [ "$STATUS" != "200" ]; then
  # Service is down - execute flow
  echo "{\"execute\": true, \"output\": {\"url\": \"$URL\", \"status_code\": \"$STATUS\"}}"
else
  # Service is healthy - skip execution
  echo "{\"execute\": false, \"output\": {}}"
fi
```

### Flow Commands

```bash
# Add a flow
cao flow add daily-standup.md

# List all flows (shows schedule, next run time, enabled status)
cao flow list

# Enable/disable a flow
cao flow enable daily-standup
cao flow disable daily-standup

# Manually run a flow (ignores schedule)
cao flow run daily-standup

# Remove a flow
cao flow remove daily-standup
```

## Cloudscape Multi-Agent Workflow UX

A comprehensive web interface built with AWS Cloudscape Design System that demonstrates multi-agent workflow best practices.

### Features

The Cloudscape UX provides an interactive environment for:

- **Real-time Dashboard**: Monitor active agent sessions, terminals, and system health
- **Agent Orchestration**: Visualize coordinator and specialist agent hierarchies
- **Task Delegation**: Create tasks with complete context transfer templates
- **Workflow Patterns**: Explore Handoff, Assign, and Send Message orchestration modes
- **Tool Design Analyzer**: Compare API-centric vs UI-centric tool designs
- **Best Practices Guide**: Comprehensive reference for multi-agent development

### The Three Commandments

The UI demonstrates the core principles of effective agent systems:

1. **Start Simple, Add Complexity Only When Needed**
   - Decision trees for architecture selection
   - Clear guidance on when to use single vs multi-agent

2. **Think From the Agent's Point of View**
   - Visualizations of agent context and perspective
   - Tools to verify complete information transfer

3. **Tools Should Mirror UI, Not API**
   - Tool design analyzer with efficiency calculations
   - Real examples showing tool call reduction

### Quick Start

```bash
# 1. Start the CAO server
cao-server

# 2. In another terminal, start the frontend
cd frontend
npm install
npm run dev

# 3. Open browser to http://localhost:3000
```

The frontend connects to the CAO server API at `http://localhost:9889`.

### Architecture Patterns Demonstrated

The UI showcases three key multi-agent patterns:

1. **Coordinator-Specialist**: Coordinator delegates to domain specialists
2. **Parallel MapReduce**: Split work, process in parallel, combine results
3. **Test-Time Compute**: Multiple approaches evaluated for best result

### Documentation

For detailed information about the Cloudscape UX:
- [Frontend README](frontend/README.md) - Complete setup and feature guide
- [Best Practices](frontend/src/pages/BestPractices.tsx) - The 10 Commandments implementation
- [UX Implementation Guide](CLOUDSCAPE_UX_GUIDE.md) - Comprehensive implementation details

## AWS Serverless Deployment

Deploy the entire application to AWS using CDK infrastructure following serverless best practices.

### Infrastructure Components

**Frontend:**
- **S3** - Static website hosting
- **CloudFront** - CDN with edge caching, HTTPS, and security headers
- **Route53** (optional) - Custom domain DNS
- **ACM** (optional) - SSL/TLS certificates

**Backend:**
- **API Gateway** - RESTful API endpoints
- **Lambda** - Serverless compute for API handlers
- **DynamoDB** - NoSQL database for sessions and terminals
- **CloudWatch** - Logging and monitoring
- **X-Ray** - Distributed tracing

**CI/CD:**
- **CodePipeline** - Automated deployment pipeline
- **CodeBuild** - Build and test automation
- **SNS** - Pipeline notifications

### Quick Deploy

```bash
# 1. Install CDK
npm install -g aws-cdk

# 2. Configure AWS credentials
aws configure

# 3. Bootstrap CDK (first time only)
cdk bootstrap aws://ACCOUNT-ID/REGION

# 4. Deploy to development
cd infrastructure
npm install
npm run deploy:dev

# 5. Deploy to production
npm run deploy:prod
```

### Architecture

```
Users → Route53 → CloudFront → S3 (Frontend)
                            ↓
                    API Gateway → Lambda → DynamoDB
                            ↓
                     CloudWatch Logs
                     X-Ray Traces
```

### Cost Estimates

- **Dev Environment:** $5-20/month
- **Prod Environment (10K users/day):** $125-150/month

### Features

✅ Multi-environment support (dev/prod)
✅ Infrastructure as Code with CDK
✅ Serverless architecture for cost optimization
✅ Security best practices (encryption, HTTPS, IAM)
✅ Automated CI/CD pipeline
✅ CloudWatch monitoring and alarms
✅ X-Ray distributed tracing
✅ Custom domain support
✅ Comprehensive documentation

### Documentation

- [Infrastructure README](infrastructure/README.md) - Complete CDK setup guide
- [Deployment Guide](infrastructure/DEPLOYMENT.md) - Quick reference for deployments
- [Cost Optimization](infrastructure/README.md#cost-optimization) - Tips to reduce AWS costs

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the Apache-2.0 License.

