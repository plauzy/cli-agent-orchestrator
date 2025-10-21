# CDK Infrastructure for CLI Agent Orchestrator

This directory contains AWS CDK infrastructure code for deploying the CLI Agent Orchestrator frontend and backend using AWS serverless best practices.

## Architecture

### Infrastructure Components

**Frontend:**
- **S3** - Static website hosting
- **CloudFront** - CDN with edge caching and HTTPS
- **Route53** (optional) - Custom domain DNS
- **Certificate Manager** (optional) - SSL/TLS certificates

**Backend:**
- **API Gateway** - RESTful API endpoints
- **Lambda** - Serverless compute for API handlers
- **DynamoDB** - NoSQL database for sessions and terminals
- **Lambda Layers** - Shared Python dependencies

**CI/CD:**
- **CodePipeline** - Automated deployment pipeline
- **CodeBuild** - Build and test automation
- **S3** - Artifact storage
- **SNS** - Pipeline notifications

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Users/Browsers                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Route53 (Optional)  │
              │   Custom Domain      │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │    CloudFront CDN    │
              │  - HTTPS/TLS         │
              │  - Edge Caching      │
              │  - Security Headers  │
              └──────────┬───────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
   ┌─────────┐   ┌─────────────┐   ┌─────────────┐
   │   S3    │   │ API Gateway │   │ Static      │
   │ Bucket  │   │             │   │ Assets      │
   │         │   └──────┬──────┘   └─────────────┘
   │ React   │          │
   │ App     │          ▼
   └─────────┘   ┌─────────────┐
                 │   Lambda    │
                 │   Handler   │
                 └──────┬──────┘
                        │
                 ┌──────┴──────┐
                 │             │
                 ▼             ▼
          ┌───────────┐  ┌──────────┐
          │ DynamoDB  │  │ DynamoDB │
          │ Sessions  │  │Terminals │
          └───────────┘  └──────────┘
```

## Prerequisites

- **AWS Account** with appropriate permissions
- **AWS CLI** configured with credentials
- **Node.js 18+** and npm
- **AWS CDK CLI** installed globally: `npm install -g aws-cdk`
- **Python 3.11+** for Lambda runtime
- **Docker** for Lambda bundling (optional but recommended)

## Setup

### 1. Install Dependencies

```bash
cd infrastructure
npm install
```

### 2. Configure AWS Credentials

```bash
aws configure
# Or use AWS SSO
aws sso login --profile your-profile
```

### 3. Bootstrap CDK (First Time Only)

```bash
# Bootstrap for dev environment
cdk bootstrap aws://ACCOUNT-ID/REGION

# Or with profile
cdk bootstrap aws://ACCOUNT-ID/REGION --profile your-profile
```

### 4. Configure Environment

Edit `lib/config.ts` to configure your environments:

```typescript
const prodConfig: Config = {
  environment: 'prod',
  account: 'YOUR-AWS-ACCOUNT-ID',
  region: 'us-east-1',

  // Optional: Custom domain
  domainName: 'cao.example.com',
  certificateArn: 'arn:aws:acm:us-east-1:ACCOUNT:certificate/CERT_ID',
  hostedZoneId: 'HOSTED_ZONE_ID',

  // ... rest of config
};
```

## Deployment

### Dev Environment

```bash
# Synthesize CloudFormation templates
npm run synth

# View changes
npm run diff

# Deploy all stacks
npm run deploy:dev
```

### Production Environment

```bash
# Deploy to production
npm run deploy:prod
```

### Individual Stack Deployment

```bash
# Deploy only frontend
cdk deploy cao-prod-frontend --context environment=prod

# Deploy only backend
cdk deploy cao-prod-backend --context environment=prod

# Deploy only pipeline
cdk deploy cao-prod-pipeline --context environment=prod
```

## Stack Details

### Frontend Stack

**Resources Created:**
- S3 bucket for static hosting
- CloudFront distribution with:
  - Origin Access Identity for S3
  - Custom cache policies for HTML and static assets
  - Security headers policy
  - Error responses for SPA routing
- Route53 alias record (if custom domain configured)
- S3 deployment with automatic CloudFront invalidation

**Configuration:**
```typescript
frontend: {
  buildCommand: 'npm run build',
  buildOutputDir: 'dist',
  cacheControl: {
    html: 'public, max-age=0, must-revalidate',
    static: 'public, max-age=31536000, immutable'
  }
}
```

**Outputs:**
- `WebsiteURL` - CloudFront distribution URL
- `BucketName` - S3 bucket name
- `DistributionId` - CloudFront distribution ID

### Backend Stack

**Resources Created:**
- DynamoDB tables:
  - Sessions table
  - Terminals table with GSI for session queries
- Lambda function for API handler
- Lambda layer for Python dependencies
- API Gateway REST API with:
  - CORS configuration
  - CloudWatch logging
  - Access logging
  - Throttling
  - API key and usage plan

**API Endpoints:**
```
GET    /sessions
POST   /sessions
GET    /sessions/{sessionId}
DELETE /sessions/{sessionId}
GET    /sessions/{sessionId}/terminals
POST   /sessions/{sessionId}/terminals
GET    /terminals/{terminalId}
DELETE /terminals/{terminalId}
POST   /terminals/{terminalId}/input
GET    /terminals/{terminalId}/output
```

**Outputs:**
- `ApiEndpoint` - API Gateway URL
- `ApiKeyId` - API key ID
- `TerminalTableName` - DynamoDB terminal table name
- `SessionTableName` - DynamoDB session table name

### Pipeline Stack (Production Only)

**Resources Created:**
- CodePipeline with stages:
  - Source (GitHub webhook)
  - Build (parallel frontend/backend builds)
  - Approval (manual approval for prod)
  - Deploy (CDK deploy)
- CodeBuild projects for:
  - Backend build and test
  - Frontend build and lint
  - CDK deployment
- S3 bucket for artifacts
- SNS topic for notifications

**Pipeline Flow:**
```
GitHub Push
    ↓
Source Stage
    ↓
Build Stage (parallel)
├── Backend Build
│   ├── Install Python deps
│   ├── Run tests
│   └── Build CDK
└── Frontend Build
    ├── Install npm deps
    ├── Run linter
    └── Build React app
    ↓
Approval Stage (prod only)
    ↓
Deploy Stage
    └── CDK Deploy All Stacks
```

## Environment Variables

### Frontend Build

The frontend build requires the API URL as an environment variable:

```bash
VITE_API_URL=https://your-api-url.com npm run build
```

This is automatically set during CDK deployment.

### Backend Lambda

Lambda functions have access to:

```bash
ENVIRONMENT=dev|prod
LOG_LEVEL=DEBUG|INFO
TERMINAL_TABLE_NAME=cao-{env}-terminals
SESSION_TABLE_NAME=cao-{env}-sessions
POWERTOOLS_SERVICE_NAME=cao-api
POWERTOOLS_METRICS_NAMESPACE=cao-{env}
```

## Cost Optimization

### Development Environment

- S3: Pay per GB stored + requests
- CloudFront: Free tier (first 1TB/month)
- Lambda: Free tier (first 1M requests/month)
- DynamoDB: On-demand pricing (pay per request)
- API Gateway: Free tier (first 1M requests/month)

**Estimated Monthly Cost (Dev):** $5-20

### Production Environment

With moderate traffic (10K users/day):
- CloudFront: ~$50/month
- Lambda: ~$20/month
- DynamoDB: ~$30/month
- API Gateway: ~$20/month
- S3: ~$5/month

**Estimated Monthly Cost (Prod):** $125-150

### Cost Reduction Strategies

1. **Enable CloudFront compression** - Reduces egress costs
2. **Use DynamoDB on-demand billing** - Pay only for what you use
3. **Set S3 lifecycle policies** - Auto-delete old artifacts
4. **Use Lambda reserved concurrency** - Control costs in prod
5. **Enable API Gateway caching** - Reduce Lambda invocations

## Security Best Practices

### ✅ Implemented

- **Encryption at rest** - S3, DynamoDB use AWS managed keys
- **Encryption in transit** - TLS 1.2+ enforced everywhere
- **Least privilege IAM** - Minimal permissions for all roles
- **VPC isolation** (optional) - Can deploy Lambda in VPC
- **WAF protection** (optional) - Can add AWS WAF to CloudFront
- **Secrets management** - GitHub token in Secrets Manager
- **CloudWatch logging** - All API calls logged
- **X-Ray tracing** - Distributed tracing enabled
- **HTTPS only** - CloudFront redirects HTTP to HTTPS
- **Security headers** - CSP, HSTS, X-Frame-Options

### 🔒 Additional Recommendations

1. **Enable AWS WAF** on CloudFront
2. **Set up AWS Shield Standard** (free tier)
3. **Enable VPC endpoints** for DynamoDB/S3
4. **Use AWS KMS** for customer-managed keys
5. **Enable GuardDuty** for threat detection
6. **Set up AWS Config** for compliance monitoring
7. **Enable CloudTrail** for audit logging
8. **Use AWS Secrets Manager** for API keys

## Monitoring & Observability

### CloudWatch Dashboards

Create custom dashboards for:
- API Gateway request/error rates
- Lambda duration/errors/throttles
- DynamoDB read/write capacity
- CloudFront cache hit ratio
- S3 bucket metrics

### CloudWatch Alarms

Recommended alarms:
- API Gateway 5xx errors > threshold
- Lambda errors > threshold
- Lambda duration > 5 seconds
- DynamoDB throttling events
- CloudFront 5xx error rate > 1%

### X-Ray Tracing

Enabled by default for:
- API Gateway
- Lambda functions

View traces in X-Ray console to debug performance issues.

### Logs

All logs sent to CloudWatch Logs:
- API Gateway access logs: `/aws/apigateway/cao-{env}`
- Lambda logs: `/aws/lambda/cao-{env}-api`
- CodeBuild logs: `/aws/codebuild/cao-{env}-*`

## Troubleshooting

### Deployment Failures

**Issue:** CDK bootstrap failed
```bash
# Solution: Ensure you have admin permissions
aws sts get-caller-identity

# Bootstrap with verbose output
cdk bootstrap --verbose
```

**Issue:** Lambda bundling failed
```bash
# Solution: Ensure Docker is running
docker ps

# Or disable bundling and use pre-built assets
```

**Issue:** CloudFront invalidation timeout
```bash
# Solution: Invalidations can take 10-15 minutes
# Monitor in CloudFront console
```

### Runtime Issues

**Issue:** API Gateway 403 errors
```bash
# Check IAM permissions on Lambda
# Verify CORS configuration
# Check API key if using authentication
```

**Issue:** CloudFront serving stale content
```bash
# Create invalidation
aws cloudfront create-invalidation \
  --distribution-id DISTID \
  --paths "/*"
```

**Issue:** DynamoDB throttling
```bash
# Check CloudWatch metrics
# Consider switching to provisioned capacity
# Or increase on-demand limits
```

## Cleanup

### Delete All Resources

```bash
# Dev environment
cdk destroy --all --context environment=dev

# Prod environment (requires manual approval)
cdk destroy --all --context environment=prod
```

### Manual Cleanup Required

Some resources require manual deletion:
- S3 buckets with `RETAIN` policy (prod)
- DynamoDB tables with `RETAIN` policy (prod)
- CloudWatch log groups (retained for compliance)
- Route53 hosted zones (if created manually)

## Advanced Configuration

### Custom Domain Setup

1. **Request ACM Certificate** (us-east-1 for CloudFront):
```bash
aws acm request-certificate \
  --domain-name cao.example.com \
  --validation-method DNS \
  --region us-east-1
```

2. **Validate Certificate** via DNS or email

3. **Update config.ts**:
```typescript
domainName: 'cao.example.com',
certificateArn: 'arn:aws:acm:us-east-1:ACCOUNT:certificate/CERT_ID',
hostedZoneId: 'HOSTED_ZONE_ID'
```

4. **Deploy** - Route53 records created automatically

### Multi-Region Deployment

For global deployment:

```typescript
// config.ts
const regions = ['us-east-1', 'eu-west-1', 'ap-southeast-1'];

regions.forEach(region => {
  new FrontendStack(app, `cao-${region}-frontend`, {
    env: { region }
    // ...
  });
});
```

### VPC Configuration

To deploy Lambda in VPC:

```typescript
// backend-stack.ts
import * as ec2 from 'aws-cdk-lib/aws-ec2';

const vpc = new ec2.Vpc(this, 'Vpc', {
  maxAzs: 2
});

const apiHandler = new lambda.Function(this, 'ApiHandler', {
  vpc,
  vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
  // ...
});
```

## CI/CD Integration

### GitHub Actions

Alternative to CodePipeline:

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: ${{ secrets.AWS_ROLE }}
          aws-region: us-east-1
      - run: |
          cd infrastructure
          npm ci
          npm run deploy:prod
```

### GitLab CI

```yaml
# .gitlab-ci.yml
deploy:
  image: node:18
  script:
    - cd infrastructure
    - npm ci
    - npm run deploy:prod
  only:
    - main
```

## Testing

### Unit Tests

```bash
cd infrastructure
npm test
```

### Integration Tests

```bash
# Test API endpoints
curl https://your-api-url/sessions

# Test CloudFront distribution
curl https://your-cloudfront-url
```

### Load Testing

Use tools like Artillery or Apache Bench:

```bash
# Install Artillery
npm install -g artillery

# Run load test
artillery quick --count 100 --num 10 https://your-api-url/sessions
```

## Support

For issues or questions:
- Check [AWS CDK documentation](https://docs.aws.amazon.com/cdk/)
- Review [CloudFormation events](https://console.aws.amazon.com/cloudformation)
- Check [CloudWatch logs](https://console.aws.amazon.com/cloudwatch)
- Open issue in GitHub repository

## License

Apache-2.0 - See LICENSE file for details
