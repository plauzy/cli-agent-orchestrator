#!/bin/bash
set -e

echo "🚀 Installing CLI Agent Orchestrator VSCode Extension"
echo ""

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js version 18+ is required (current: $(node -v))"
    exit 1
fi

echo "✅ Node.js $(node -v) found"

# Check npm
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed"
    exit 1
fi

echo "✅ npm $(npm -v) found"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
npm install

# Build extension
echo ""
echo "🔨 Building extension..."
npm run build

# Package extension
echo ""
echo "📦 Packaging extension..."
npm run package

# Install in VSCode
echo ""
echo "🔧 Installing extension in VSCode..."
VSIX_FILE=$(ls cao-vscode-*.vsix 2>/dev/null | head -n1)

if [ -z "$VSIX_FILE" ]; then
    echo "❌ VSIX file not found"
    exit 1
fi

if command -v code &> /dev/null; then
    code --install-extension "$VSIX_FILE"
    echo "✅ Extension installed successfully!"
else
    echo "⚠️  'code' command not found"
    echo "   Please install the extension manually:"
    echo "   1. Open VSCode"
    echo "   2. Go to Extensions (Ctrl+Shift+X)"
    echo "   3. Click '...' → 'Install from VSIX...'"
    echo "   4. Select: $VSIX_FILE"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Start CAO server: cao-server"
echo "2. Open VSCode and click the CAO icon in the activity bar"
echo "3. See QUICKSTART.md for a guided tour"
echo ""
