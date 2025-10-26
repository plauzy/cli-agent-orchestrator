#!/bin/bash
set -e

echo "🚀 Setting up CLI Agent Orchestrator development environment..."

# Check prerequisites
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 is not installed. Please install $1 first."
        return 1
    else
        echo "✅ $1 is installed"
        return 0
    fi
}

echo ""
echo "Checking prerequisites..."
MISSING=0

check_command python3 || MISSING=1
check_command node || MISSING=1
check_command npm || MISSING=1
check_command tmux || MISSING=1

if [ $MISSING -eq 1 ]; then
    echo ""
    echo "Please install missing prerequisites and try again."
    exit 1
fi

echo ""
echo "All prerequisites satisfied!"
echo ""

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
uv sync

# Install CAO
echo "📦 Installing CLI Agent Orchestrator..."
uv tool install -e .

# Install agent profiles
echo "📦 Installing agent profiles..."
cao install code_supervisor
cao install developer
cao install reviewer

# Initialize database
echo "📦 Initializing database..."
cao init

# Build VSCode extension
echo "📦 Building VSCode extension..."
cd vscode-extension

npm install

cd webview
npm install
npm run build

cd ..
npm run compile

cd ..

# Optional: Install CDK dependencies
if [ "$INSTALL_CDK" = "true" ]; then
    echo "📦 Installing CDK dependencies..."
    cd cdk
    npm install
    cd ..
fi

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "🎯 Quick Start:"
echo ""
echo "1. Start CAO server:"
echo "   cao-server"
echo ""
echo "2. Launch an agent (in another terminal):"
echo "   cao launch --agents code_supervisor"
echo ""
echo "3. Develop extension:"
echo "   cd vscode-extension"
echo "   Press F5 in VSCode to debug"
echo ""
echo "4. Deploy to AWS (optional):"
echo "   ./scripts/deploy-to-aws.sh"
