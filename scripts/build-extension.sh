#!/bin/bash
set -e

echo "🔨 Building CLI Agent Orchestrator VSCode Extension..."

# Navigate to extension directory
cd "$(dirname "$0")/../vscode-extension"

echo "📦 Installing extension dependencies..."
npm install

echo "📦 Installing webview dependencies..."
cd webview
npm install

echo "🔨 Building webview..."
npm run build

echo "🔨 Compiling extension..."
cd ..
npm run compile

echo "✅ Extension build complete!"
echo ""
echo "To test the extension:"
echo "  1. Open vscode-extension folder in VSCode"
echo "  2. Press F5 to launch Extension Development Host"
echo ""
echo "To package for distribution:"
echo "  npm install -g @vscode/vsce"
echo "  vsce package"
