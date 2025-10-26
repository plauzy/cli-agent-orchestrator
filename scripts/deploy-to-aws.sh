#!/bin/bash
set -e

echo "🚀 Deploying CLI Agent Orchestrator to AWS..."

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install AWS CLI first."
    exit 1
fi

if ! command -v cdk &> /dev/null; then
    echo "❌ AWS CDK is not installed. Please run: npm install -g aws-cdk"
    exit 1
fi

# Set variables
export AWS_REGION=${AWS_REGION:-us-east-1}
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REPO="cli-agent-orchestrator"

echo "📍 Region: $AWS_REGION"
echo "📍 Account: $AWS_ACCOUNT_ID"
echo ""

# Build Docker image
echo "🐳 Building Docker image..."
cd "$(dirname "$0")/.."

cat > Dockerfile <<'EOF'
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Install Python dependencies
RUN uv sync

# Install CAO
RUN uv tool install -e .

# Initialize database
RUN cao init

# Expose port
EXPOSE 9889

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:9889/health || exit 1

# Run server
CMD ["cao-server", "--host", "0.0.0.0", "--port", "9889"]
EOF

docker build -t cao-server:latest .

# Create ECR repository if it doesn't exist
echo "📦 Creating ECR repository..."
aws ecr create-repository \
    --repository-name $ECR_REPO \
    --region $AWS_REGION \
    --image-scanning-configuration scanOnPush=true \
    2>/dev/null || echo "Repository already exists"

# Login to ECR
echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag and push image
echo "⬆️  Pushing image to ECR..."
docker tag cao-server:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

docker push \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# Deploy CDK stacks
echo "☁️  Deploying CDK stacks..."
cd cdk

npm install

echo ""
echo "Deploying Network Stack..."
cdk deploy CAONetworkStack --require-approval never

echo ""
echo "Deploying Auth Stack..."
cdk deploy CAOAuthStack --require-approval never

echo ""
echo "Deploying Infrastructure Stack..."
cdk deploy CAOInfrastructureStack --require-approval never

# Get outputs
echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Getting deployment information..."

ALB_DNS=$(aws cloudformation describe-stacks \
    --stack-name CAOInfrastructureStack \
    --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' \
    --output text)

USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name CAOAuthStack \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

echo ""
echo "🌐 Load Balancer DNS: $ALB_DNS"
echo "👤 User Pool ID: $USER_POOL_ID"
echo ""
echo "Test the deployment:"
echo "  curl http://$ALB_DNS/health"
echo ""
echo "View logs:"
echo "  aws logs tail /ecs/cao-server --follow"
