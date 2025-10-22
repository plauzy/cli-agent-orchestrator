# Changelog

All notable changes to the CLI Agent Orchestrator VSCode extension will be documented in this file.

## [0.1.0] - 2025-01-XX

### Added

- Initial release of CAO VSCode Extension
- Session management interface
  - Create new sessions with Q CLI or Claude Code provider
  - View all active CAO sessions
  - Delete sessions
- Terminal management interface
  - Create terminals within sessions
  - View terminal status (IDLE, PROCESSING, COMPLETED, ERROR, etc.)
  - Delete terminals
- Terminal interaction features
  - Send input to terminals
  - View terminal output (full or last message)
  - Auto-refresh terminal output
  - Real-time status monitoring
- Flow management interface
  - View scheduled flows
  - Enable/disable flows
  - Run flows on demand
  - View flow details (schedule, agent profile, etc.)
- Configuration options
  - Configurable CAO API server URL
  - Auto-refresh interval setting
  - Default provider selection
- VSCode integration
  - Command palette commands
  - Activity bar sidebar view
  - Native VSCode theme support
  - Keyboard shortcuts (Ctrl+Enter to send messages)

### Technical Features

- React-based webview UI
- TypeScript throughout
- Axios HTTP client for API communication
- Webpack build system
- Message-based communication between extension host and webview
- Comprehensive type definitions matching CAO Python models

## [Unreleased]

### Planned Features

- Agent profile management UI
- Inbox/message queue visualization
- Terminal output search and filtering
- Session and terminal favoriting
- Export terminal output to file
- Terminal command history
- Multi-terminal selection and bulk actions
- Performance metrics dashboard
- WebSocket support for real-time updates
- Integrated terminal logs viewer
