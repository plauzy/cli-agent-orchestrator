# Multi-stage build for optimized dev container
FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tmux \
    git \
    curl \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest

# Install AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf aws awscliv2.zip

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

USER vscode

# Set up Python environment
ENV PATH="/home/vscode/.cargo/bin:$PATH"
ENV PYTHONUNBUFFERED=1

WORKDIR /workspaces/cli-agent-orchestrator
