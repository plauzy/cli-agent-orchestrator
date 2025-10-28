#!/bin/bash
set -e

echo "🚀 Setting up CLI Agent Orchestrator development environment..."

# Install tmux (required for CAO)
echo "📦 Installing tmux..."
sudo apt-get update
sudo apt-get install -y tmux

# Verify tmux version
tmux -V

# Install uv for Python package management
echo "📦 Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
cd /workspaces/cli-agent-orchestrator
uv sync

# Install CAO
echo "📦 Installing CLI Agent Orchestrator..."
uv tool install -e .

# Install built-in agent profiles
echo "📦 Installing agent profiles..."
cao install code_supervisor
cao install developer
cao install reviewer

# Initialize database
echo "📦 Initializing database..."
cao init

# Install VSCode extension dependencies
echo "📦 Installing VSCode extension dependencies..."
cd /workspaces/cli-agent-orchestrator/vscode-extension
npm ci

# Install webview dependencies
echo "📦 Installing webview dependencies..."
cd /workspaces/cli-agent-orchestrator/vscode-extension/webview
npm ci --legacy-peer-deps

# Build webview
echo "🔨 Building webview..."
npm run build

# Go back to root
cd /workspaces/cli-agent-orchestrator

echo "✅ Development environment setup complete!"
echo ""
echo "🎯 Quick Start:"
echo "  1. Start CAO server: cao-server"
echo "  2. Launch an agent: cao launch --agents code_supervisor"
echo "  3. Develop extension: cd vscode-extension && npm run compile"
echo "  4. Press F5 to debug the extension"
echo ""
echo "📚 For more information, see README.md"
