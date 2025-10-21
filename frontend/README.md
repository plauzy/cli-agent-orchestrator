# CLI Agent Orchestrator - Cloudscape UX

A comprehensive multi-agent workflow management interface built with AWS Cloudscape Design System, demonstrating best practices for agent orchestration.

## Features

### 🎯 Multi-Agent Workflow Best Practices

This UX demonstrates the **Three Commandments** of agent development:

1. **Start Simple, Add Complexity Only When Needed**
   - Decision trees for single vs multi-agent architecture
   - Clear guidance on when to add complexity

2. **Think From the Agent's Point of View**
   - Visualizations of agent context and perspective
   - Tools to verify agents have complete information

3. **Tools Should Mirror UI, Not API**
   - Tool design analyzer comparing API-centric vs UI-centric patterns
   - Real examples showing efficiency gains

### 📊 Dashboard Features

- **Real-time Monitoring**: Live view of active agent sessions and terminals
- **Agent Orchestration**: Visualize coordinator and specialist agent hierarchies
- **Task Delegation**: Create tasks with complete context transfer templates
- **Workflow Patterns**: Explore Handoff, Assign, and Send Message patterns
- **Tool Design Analyzer**: Analyze and optimize tool design for efficiency
- **Best Practices Guide**: Comprehensive reference for multi-agent development

### 🏗️ Architecture Patterns

The UI demonstrates three key multi-agent patterns:

1. **Coordinator-Specialist**: Coordinator delegates to domain specialists
2. **Parallel MapReduce**: Split work, process in parallel, combine results
3. **Test-Time Compute**: Multiple approaches evaluated for best result

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- CAO server running on `http://localhost:9889`

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

The application will be available at `http://localhost:3000`

### Backend API

The frontend expects the CAO server to be running:

```bash
# In the project root
cao-server
```

The frontend proxies API calls from `/api/*` to `http://localhost:9889/*`

## Project Structure

```
frontend/
├── src/
│   ├── pages/
│   │   ├── Dashboard.tsx              # Main dashboard with overview
│   │   ├── AgentOrchestration.tsx     # Agent hierarchy visualization
│   │   ├── TaskDelegation.tsx         # Context transfer templates
│   │   ├── WorkflowPatterns.tsx       # Orchestration mode explorer
│   │   ├── ToolDesign.tsx             # Tool design analyzer
│   │   └── BestPractices.tsx          # Comprehensive guide
│   ├── types/
│   │   └── index.ts                   # TypeScript type definitions
│   ├── App.tsx                        # Main application component
│   └── main.tsx                       # Application entry point
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## Key Components

### Dashboard

The main dashboard provides:
- Live session monitoring
- Agent status indicators
- Quick decision guide for architecture selection
- Navigation to all features

### Agent Orchestration

Visualize multi-agent architectures:
- Coordinator and specialist agent profiles
- Tool inventories with design analysis
- UI-centric vs API-centric comparison
- Real-world examples

### Task Delegation

Create properly delegated tasks:
- Context transfer template builder
- Good vs bad delegation examples
- Generated prompts for subagents
- Best practices checklist

### Workflow Patterns

Explore orchestration modes:
- **Handoff**: Synchronous task delegation
- **Assign**: Asynchronous parallel execution
- **Send Message**: Ongoing collaboration
- Architecture pattern examples
- Pattern selection guide

### Tool Design Analyzer

Optimize tool efficiency:
- API-centric vs UI-centric comparisons
- Tool call reduction calculations
- Design checklist and red flags
- Real-world Slack integration example

### Best Practices Guide

Comprehensive reference:
- The 10 Commandments of Agent Development
- Metrics and success criteria
- System health indicators
- Common failure modes and solutions
- Development workflow phases

## Design Principles

### Following Anthropic Best Practices

This UX is built following the Anthropic Agent Orchestrator Best Practices:

1. **Complete Context**: Every view provides full information agents need
2. **UI-Centric Design**: Information bundled like human-visible interfaces
3. **Clear Hierarchies**: Coordinator-specialist patterns visualized
4. **Efficiency Metrics**: Track tool calls, success rates, overhead
5. **Real Examples**: Concrete comparisons of good vs bad patterns

### Cloudscape Design System

Built with AWS Cloudscape for:
- Consistent, professional UI components
- Accessibility out of the box
- Responsive layouts
- Production-ready patterns

## Development

### Running Locally

```bash
npm run dev
```

Visit `http://localhost:3000` to see the application.

### Building

```bash
npm run build
```

The optimized production build will be in the `dist/` directory.

### Linting

```bash
npm run lint
```

## Integration with CAO

This frontend integrates with the CLI Agent Orchestrator backend:

- **GET /sessions**: List all active sessions
- **GET /sessions/{id}**: Get session details
- **POST /sessions/{id}/terminals**: Create new terminal
- **GET /terminals/{id}**: Get terminal status
- **POST /terminals/{id}/input**: Send input to terminal
- **GET /terminals/{id}/output**: Get terminal output

See the [API documentation](../docs/api.md) for full details.

## Key Concepts Demonstrated

### Single Agent vs Multi-Agent

Decision tree helps users choose:
- Can one agent handle <20 tools? → Single agent
- Can tasks run in parallel? → Multi-agent (Parallel)
- Need specialized context? → Multi-agent (Coordinator-Specialist)

### Orchestration Modes

Three patterns for different use cases:
- **Handoff**: Sequential workflows with dependencies
- **Assign**: Parallel independent tasks
- **Send Message**: Iterative collaboration

### Tool Design Quality

Checklist for evaluating tools:
- Multiple calls needed for basic info? → Redesign
- Returns IDs needing resolution? → Pre-resolve
- Missing UI-visible info? → Add it

## Contributing

When adding new features:

1. Follow the Three Commandments
2. Add examples (good and bad)
3. Include metrics where applicable
4. Update this README

## Resources

- [Anthropic Agent Orchestrator Best Practices](https://github.com/anthropics/anthropic-cookbook)
- [AWS Cloudscape Design System](https://cloudscape.design/)
- [CLI Agent Orchestrator](https://github.com/awslabs/cli-agent-orchestrator)

## License

Apache-2.0 - See LICENSE file for details
