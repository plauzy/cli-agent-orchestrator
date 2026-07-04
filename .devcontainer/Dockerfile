# Use the same Playwright image as CI
FROM mcr.microsoft.com/playwright:v1.50.0-jammy

# Install system dependencies (same as CI)
# Including tmux for real integration tests with terminal sessions
RUN apt-get update && apt-get install -y \
    unzip \
    curl \
    git \
    tmux \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install Bun
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:$PATH"

# Set working directory
WORKDIR /workspace
