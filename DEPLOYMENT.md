# CLI Agent Orchestrator - Cloud Deployment Guide

This guide covers deploying the CLI Agent Orchestrator to AWS using the provided CDK infrastructure.

## Architecture

The cloud deployment consists of three main stacks:

```
┌────────────────────────────────────────────────────────────────┐
│                    Internet Gateway                             │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│           Application Load Balancer (ALB)                       │
│  • HTTPS/HTTP termination                                      │
│  • Sticky sessions (cookie-based)                              │
│  • Health checks                                                │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│              ECS Fargate Service                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  Task 1     │  │  Task 2     │  │  Task N     │            │
│  │ (CAO Server)│  │ (CAO Server)│  │ (CAO Server)│            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│  • Auto-scaling (2-10 tasks)                                   │
│  • CPU & Request-based scaling                                 │
└──────────────────────────┬─────────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
    ┌──────────┐  ┌──────────────┐  ┌─────────┐
    │ DynamoDB │  │ElastiCache   │  │ Cognito │
    │ Sessions │  │ Redis        │  │ Auth    │
    │          │  │ (Session     │  │ User    │
    │          │  │  Storage)    │  │ Pool    │
    └──────────┘  └──────────────┘  └─────────┘
```

### Stack Components

#### 1. Network Stack (`CAONetworkStack`)
- **VPC**: Multi-AZ with public and private subnets
- **NAT Gateway**: For outbound internet access from private subnets
- **Security Groups**: For ALB and ECS tasks
- **CIDR**: Configurable IP ranges

#### 2. Auth Stack (`CAOAuthStack`)
- **Cognito User Pool**: User authentication
- **User Pool Client**: OAuth2/OIDC configuration
- **Identity Pool**: Federated identity management
- **Advanced Security**: Risk-based adaptive authentication

#### 3. Infrastructure Stack (`CAOInfrastructureStack`)
- **ECS Cluster**: Fargate-based container orchestration
- **ECR Repository**: Docker image storage
- **Application Load Balancer**: Traffic distribution
- **Target Group**: With sticky sessions
- **Auto Scaling**: CPU and request-based policies
- **DynamoDB**: Session persistence
- **ElastiCache Redis**: Session caching
- **CloudWatch Logs**: Centralized logging

## Prerequisites

### 1. AWS Account Setup

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure credentials
aws configure
# AWS Access Key ID: <your-access-key>
# AWS Secret Access Key: <your-secret-key>
# Default region name: us-east-1
# Default output format: json
```

### 2. Install CDK

```bash
# Install AWS CDK globally
npm install -g aws-cdk

# Verify installation
cdk --version
# Expected: 2.115.0 or higher
```

### 3. Bootstrap CDK

```bash
# Bootstrap your AWS environment (one-time per region/account)
cdk bootstrap aws://ACCOUNT-ID/REGION

# Example:
cdk bootstrap aws://123456789012/us-east-1
```

## Deployment Steps

### Step 1: Build Docker Image

First, build the CAO server Docker image:

```bash
# Create Dockerfile for CAO server
cd /path/to/cli-agent-orchestrator

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

# Build image
docker build -t cao-server:latest .

# Test locally
docker run -p 9889:9889 cao-server:latest
```

### Step 2: Push to ECR

```bash
# Get ECR repository URI (from CDK output or create manually)
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REPO="cli-agent-orchestrator"

# Create ECR repository if it doesn't exist
aws ecr create-repository --repository-name $ECR_REPO --region $AWS_REGION || true

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag image
docker tag cao-server:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# Push image
docker push \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest
```

### Step 3: Deploy CDK Stacks

```bash
# Navigate to CDK directory
cd cdk

# Install dependencies
npm install

# Synthesize CloudFormation templates (optional - for review)
cdk synth

# Deploy all stacks
cdk deploy --all

# Or deploy stacks individually
cdk deploy CAONetworkStack
cdk deploy CAOAuthStack
cdk deploy CAOInfrastructureStack

# Confirm deployment
# Press 'y' when prompted
```

### Step 4: Verify Deployment

```bash
# Get load balancer DNS name
aws cloudformation describe-stacks \
  --stack-name CAOInfrastructureStack \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' \
  --output text

# Test health endpoint
curl http://<load-balancer-dns>/health

# Expected output:
# {"status":"healthy"}
```

## Configuration

### Environment Variables

The ECS tasks are configured with the following environment variables:

```typescript
environment: {
  PORT: '9889',
  USER_POOL_ID: userPool.userPoolId,
  DYNAMODB_TABLE: sessionTable.tableName,
  REDIS_HOST: redisCluster.attrRedisEndpointAddress,
  REDIS_PORT: redisCluster.attrRedisEndpointPort,
}
```

### Auto-Scaling Policies

#### CPU-Based Scaling
- **Target**: 70% CPU utilization
- **Scale Out**: When CPU > 70% for 60 seconds
- **Scale In**: When CPU < 70% for 60 seconds
- **Min Capacity**: 2 tasks
- **Max Capacity**: 10 tasks

#### Request-Based Scaling
- **Target**: 1000 requests per target
- **Scale Out**: When requests > 1000/target for 60 seconds
- **Scale In**: When requests < 1000/target for 60 seconds

### Session Management

#### Sticky Sessions (ALB)
- **Cookie Name**: `cao-session`
- **Duration**: 1 hour (3600 seconds)
- **Type**: Load balancer cookie

#### Session Storage (DynamoDB + Redis)
- **DynamoDB**: Persistent session data
- **Redis**: Session caching for fast access
- **TTL**: Automatic cleanup of expired sessions

## Monitoring and Logging

### CloudWatch Logs

View logs for ECS tasks:

```bash
# List log streams
aws logs describe-log-streams \
  --log-group-name /ecs/cao-server \
  --order-by LastEventTime \
  --descending \
  --max-items 10

# Tail logs
aws logs tail /ecs/cao-server --follow
```

### CloudWatch Metrics

Key metrics to monitor:

1. **ECS Service**:
   - `CPUUtilization`
   - `MemoryUtilization`
   - `DesiredTaskCount`
   - `RunningTaskCount`

2. **ALB**:
   - `RequestCount`
   - `TargetResponseTime`
   - `HealthyHostCount`
   - `UnHealthyHostCount`

3. **DynamoDB**:
   - `ConsumedReadCapacityUnits`
   - `ConsumedWriteCapacityUnits`
   - `UserErrors`

4. **ElastiCache**:
   - `CPUUtilization`
   - `CurrConnections`
   - `Evictions`

### CloudWatch Dashboards

Create a custom dashboard:

```bash
aws cloudwatch put-dashboard --dashboard-name CAODashboard --dashboard-body file://dashboard.json
```

Example `dashboard.json`:

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ECS", "CPUUtilization", {"stat": "Average"}],
          [".", "MemoryUtilization", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "ECS Resource Utilization"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ApplicationELB", "RequestCount", {"stat": "Sum"}],
          [".", "TargetResponseTime", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "ALB Performance"
      }
    }
  ]
}
```

## Security

### IAM Roles

The deployment creates the following IAM roles:

1. **Task Execution Role**:
   - Pull images from ECR
   - Write logs to CloudWatch
   - Access secrets from Secrets Manager

2. **Task Role**:
   - Read/Write to DynamoDB
   - Access ElastiCache
   - Invoke other AWS services as needed

### Security Groups

1. **ALB Security Group**:
   - Inbound: 80 (HTTP), 443 (HTTPS) from 0.0.0.0/0
   - Outbound: All traffic

2. **ECS Security Group**:
   - Inbound: 9889 from ALB Security Group
   - Outbound: All traffic

3. **Cache Security Group**:
   - Inbound: 6379 from ECS Security Group
   - Outbound: None

### Cognito Security

- **Password Policy**:
  - Min length: 12 characters
  - Requires: lowercase, uppercase, digits, symbols
  - Temp password validity: 3 days

- **Advanced Security**:
  - Risk-based adaptive authentication
  - Compromised credentials detection
  - Account takeover protection

## Updating the Deployment

### Update Application Code

```bash
# Build new image
docker build -t cao-server:latest .

# Tag with new version
docker tag cao-server:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:v1.2.3

# Also tag as latest
docker tag cao-server:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# Push both tags
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:v1.2.3
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# Force new deployment
aws ecs update-service \
  --cluster cao-cluster \
  --service cao-service \
  --force-new-deployment
```

### Update Infrastructure

```bash
# Make changes to CDK code
# Then deploy
cd cdk
cdk deploy --all

# Or specific stack
cdk deploy CAOInfrastructureStack
```

## Cost Optimization

### Estimated Monthly Costs

Based on moderate usage (2 tasks, 24/7):

| Service | Configuration | Monthly Cost |
|---------|---------------|--------------|
| **ECS Fargate** | 2 tasks × 1 vCPU × 2GB | ~$60 |
| **ALB** | 1 load balancer | ~$22 |
| **DynamoDB** | Pay-per-request | ~$5-20 |
| **ElastiCache** | cache.t3.micro | ~$12 |
| **NAT Gateway** | 1 NAT Gateway | ~$32 |
| **Data Transfer** | Varies | ~$10-50 |
| **CloudWatch** | Logs + Metrics | ~$10 |
| **Total** | | **~$151-206/month** |

### Cost Reduction Strategies

1. **Use Fargate Spot**:
```typescript
// In CAOInfrastructureStack
capacityProviderStrategies: [{
  capacityProvider: 'FARGATE_SPOT',
  weight: 1,
}]
// Savings: Up to 70% on compute
```

2. **Reduce Task Count During Off-Hours**:
```bash
# Scale down at night
aws application-autoscaling put-scheduled-action \
  --service-namespace ecs \
  --scheduled-action-name scale-down \
  --schedule "cron(0 22 * * ? *)" \
  --scalable-target-action MinCapacity=1,MaxCapacity=1

# Scale up in morning
aws application-autoscaling put-scheduled-action \
  --service-namespace ecs \
  --scheduled-action-name scale-up \
  --schedule "cron(0 6 * * ? *)" \
  --scalable-target-action MinCapacity=2,MaxCapacity=10
```

3. **Use DynamoDB On-Demand Pricing**:
   - Already configured in CDK
   - Automatic scaling
   - No capacity planning needed

4. **Optimize Log Retention**:
```typescript
// In CAOInfrastructureStack
logGroup: new logs.LogGroup(this, 'CAOLogGroup', {
  retention: logs.RetentionDays.ONE_WEEK, // Change to THREE_DAYS
})
```

5. **Use VPC Endpoints** (instead of NAT Gateway):
```typescript
// Add VPC endpoints for AWS services
vpc.addGatewayEndpoint('S3Endpoint', {
  service: ec2.GatewayVpcEndpointAwsService.S3,
});

vpc.addInterfaceEndpoint('ECREndpoint', {
  service: ec2.InterfaceVpcEndpointAwsService.ECR,
});
```

## Disaster Recovery

### Backup Strategy

1. **DynamoDB**:
   - Point-in-time recovery enabled (35 days)
   - On-demand backups available

2. **ECR Images**:
   - Cross-region replication (configure separately)
   - Lifecycle policy retains last 10 images

### Restore Procedure

1. **DynamoDB Restore**:
```bash
aws dynamodb restore-table-to-point-in-time \
  --source-table-name cao-sessions \
  --target-table-name cao-sessions-restored \
  --restore-date-time 2025-01-01T00:00:00Z
```

2. **Redeploy Stack**:
```bash
cdk destroy --all
cdk deploy --all
```

## Troubleshooting

### Tasks Not Starting

1. **Check Task Logs**:
```bash
aws logs tail /ecs/cao-server --follow
```

2. **Check Task Events**:
```bash
aws ecs describe-services \
  --cluster cao-cluster \
  --services cao-service \
  --query 'services[0].events[:5]'
```

3. **Common Issues**:
   - ECR image pull failed: Check IAM permissions
   - Container crashes: Check application logs
   - Health check failed: Verify `/health` endpoint

### Load Balancer Issues

1. **No Healthy Targets**:
```bash
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn>
```

2. **503 Errors**:
   - All targets unhealthy
   - Auto-scaling not keeping up
   - Application crashed

### Performance Issues

1. **High CPU**:
   - Increase task count manually
   - Adjust auto-scaling thresholds
   - Optimize application code

2. **High Memory**:
   - Increase task memory limit
   - Check for memory leaks
   - Review application logs

## Cleanup

### Delete All Resources

```bash
# Delete CDK stacks (in reverse order)
cdk destroy CAOInfrastructureStack
cdk destroy CAOAuthStack
cdk destroy CAONetworkStack

# Manually delete remaining resources
# (CDK may not delete everything to prevent data loss)

# Delete ECR repository
aws ecr delete-repository \
  --repository-name cli-agent-orchestrator \
  --force

# Delete DynamoDB table (if retained)
aws dynamodb delete-table --table-name cao-sessions

# Empty and delete S3 buckets (if any)
aws s3 rb s3://your-bucket-name --force
```

### Cost Warning

Always verify resources are deleted to avoid unexpected charges:

```bash
# List ECS services
aws ecs list-services --cluster cao-cluster

# List ALBs
aws elbv2 describe-load-balancers

# List DynamoDB tables
aws dynamodb list-tables

# List ElastiCache clusters
aws elasticache describe-cache-clusters
```

## Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [Cognito User Pools](https://docs.aws.amazon.com/cognito/latest/developerguide/)
- [Application Load Balancer](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/)

## License

Apache-2.0 License - see [LICENSE](../LICENSE)
