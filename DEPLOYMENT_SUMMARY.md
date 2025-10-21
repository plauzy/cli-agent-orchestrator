# CLI Agent Orchestrator - Complete Deployment Solution

## 🎉 Project Overview

A comprehensive multi-agent workflow management system with:
1. **Cloudscape UX** - Production-ready React frontend demonstrating best practices
2. **AWS CDK Infrastructure** - Serverless deployment with full CI/CD pipeline
3. **Multi-Agent Best Practices** - Implementation of Anthropic's orchestration principles

---

## 📦 What's Included

### 1. Cloudscape Multi-Agent Workflow UX

**Location:** `frontend/`

A comprehensive web interface built with AWS Cloudscape Design System demonstrating **The Three Commandments** of multi-agent development.

**Features:**
- 📊 **Real-time Dashboard** - Monitor agent sessions and system health
- 🤖 **Agent Orchestration** - Visualize coordinator-specialist hierarchies
- 📝 **Task Delegation** - Context transfer templates with good/bad examples
- 🔄 **Workflow Patterns** - Handoff, Assign, Send Message explorers
- 🛠️ **Tool Design Analyzer** - Compare API-centric vs UI-centric patterns
- 📚 **Best Practices Guide** - The 10 Commandments implementation

**Tech Stack:**
- React 18 + TypeScript
- AWS Cloudscape Design System
- Vite build tooling
- Axios for API integration

**Run Locally:**
```bash
cd frontend
npm install
npm run dev
# Visit http://localhost:3000
```

**Documentation:**
- [Frontend README](frontend/README.md)
- [UX Implementation Guide](CLOUDSCAPE_UX_GUIDE.md)

---

### 2. AWS CDK Infrastructure

**Location:** `infrastructure/`

Production-ready serverless infrastructure following AWS best practices.

**Components:**

#### Frontend Stack
- **S3** - Static website hosting
- **CloudFront** - CDN with edge caching
- **Custom Cache Policies** - HTML (0s TTL) and static assets (1 year TTL)
- **Security Headers** - CSP, HSTS, X-Frame-Options, etc.
- **Route53 + ACM** - Optional custom domain support

#### Backend Stack
- **API Gateway** - RESTful API with CORS
- **Lambda** - Python 3.11 serverless functions
- **Lambda Layers** - Shared dependencies
- **DynamoDB** - Sessions and terminals tables
- **CloudWatch** - Logs and metrics
- **X-Ray** - Distributed tracing

#### Pipeline Stack
- **CodePipeline** - Automated deployments
- **CodeBuild** - Parallel frontend/backend builds
- **Manual Approval** - Production deployment gate
- **SNS** - Pipeline notifications
- **S3** - Artifact storage

**Deploy to AWS:**
```bash
# First time setup
npm install -g aws-cdk
aws configure
cdk bootstrap aws://ACCOUNT-ID/REGION

# Deploy to dev
cd infrastructure
npm install
npm run deploy:dev

# Deploy to production
npm run deploy:prod
```

**Documentation:**
- [Infrastructure README](infrastructure/README.md)
- [Deployment Guide](infrastructure/DEPLOYMENT.md)

---

## 🏗️ Architecture Overview

### Local Development

```
┌─────────────────────┐
│   Browser           │
│  localhost:3000     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Vite Dev Server   │
│   React Frontend    │
└──────────┬──────────┘
           │
           │ Proxy: /api → localhost:9889
           ▼
┌─────────────────────┐
│   CAO Server        │
│   FastAPI Backend   │
│   Port: 9889        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   SQLite DB         │
│   Tmux Sessions     │
└─────────────────────┘
```

### AWS Production Deployment

```
┌──────────────────────────────────────────────┐
│                  Users                        │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  Route53 (Optional)  │
         │   cao.example.com    │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │   CloudFront CDN     │
         │  - HTTPS/TLS 1.2+    │
         │  - Edge Caching      │
         │  - Security Headers  │
         │  - Gzip/Brotli       │
         └──────────┬───────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌──────────────┐      ┌─────────────────┐
│  S3 Bucket   │      │  API Gateway    │
│  Frontend    │      │  REST API       │
│  React App   │      └────────┬────────┘
└──────────────┘               │
                               ▼
                      ┌─────────────────┐
                      │  Lambda         │
                      │  Python 3.11    │
                      │  + Layers       │
                      └────────┬────────┘
                               │
                      ┌────────┴────────┐
                      │                 │
                      ▼                 ▼
               ┌─────────────┐   ┌─────────────┐
               │ DynamoDB    │   │ DynamoDB    │
               │ Sessions    │   │ Terminals   │
               └─────────────┘   └─────────────┘

          Monitoring & Observability:
          ├─ CloudWatch Logs
          ├─ CloudWatch Metrics
          ├─ X-Ray Traces
          └─ CloudWatch Alarms
```

### CI/CD Pipeline

```
GitHub Push (main branch)
        ↓
┌────────────────────┐
│  CodePipeline      │
└────────┬───────────┘
         │
    ┌────▼────────────────────┐
    │   Source Stage          │
    │   - GitHub Webhook      │
    │   - Clone Repository    │
    └────────┬────────────────┘
             │
    ┌────────▼────────────────────────┐
    │   Build Stage (Parallel)        │
    ├─────────────────────────────────┤
    │  Frontend Build  │ Backend Build│
    │  ├─ npm ci       │ ├─ pip install
    │  ├─ npm lint     │ ├─ pytest    │
    │  └─ npm build    │ └─ cdk build │
    └────────┬────────────────────────┘
             │
    ┌────────▼────────────────┐
    │  Approval Stage (Prod)  │
    │  - Manual Review        │
    │  - SNS Notification     │
    └────────┬────────────────┘
             │
    ┌────────▼────────────────┐
    │   Deploy Stage          │
    │   - cdk deploy --all    │
    │   - Update CloudFront   │
    │   - Invalidate Cache    │
    └─────────────────────────┘
```

---

## 🚀 Getting Started

### Option 1: Local Development

**Prerequisites:**
- Node.js 18+
- Python 3.11+
- tmux 3.3+

**Steps:**
```bash
# 1. Clone repository
git clone https://github.com/awslabs/cli-agent-orchestrator.git
cd cli-agent-orchestrator

# 2. Install Python dependencies
uv sync

# 3. Start CAO server
cao-server

# 4. In another terminal, start frontend
cd frontend
npm install
npm run dev

# 5. Open browser
open http://localhost:3000
```

### Option 2: AWS Deployment

**Prerequisites:**
- AWS Account
- AWS CLI configured
- Node.js 18+
- AWS CDK CLI

**Steps:**
```bash
# 1. Bootstrap CDK (first time only)
cdk bootstrap aws://ACCOUNT-ID/us-east-1

# 2. Configure environment
cd infrastructure
vim lib/config.ts  # Update account ID and settings

# 3. Deploy to dev
npm install
npm run deploy:dev

# 4. Get outputs
# CloudFront URL will be in stack outputs

# 5. Deploy to prod (with custom domain)
npm run deploy:prod
```

---

## 📊 Multi-Agent Best Practices Demonstrated

### The Three Commandments

#### 1. Start Simple, Add Complexity Only When Needed

**Where to See:**
- Dashboard decision tree for single vs multi-agent
- Agent Orchestration page showing tool counts (<20 recommended)
- Best Practices guide with metrics-based justification

**Implementation:**
- Single coordinator agent
- Specialist agents only when needed
- Tool count tracking and warnings

#### 2. Think From the Agent's Point of View

**Where to See:**
- Task Delegation page with context transfer templates
- Good vs bad delegation examples
- Complete context verification checklist

**Implementation:**
- Verbose context transfer by default
- Agent perspective visualizations
- Transcript review guidelines

#### 3. Tools Should Mirror UI, Not API

**Where to See:**
- Tool Design Analyzer with side-by-side comparisons
- Efficiency metrics (50-67% call reduction)
- Real-world Slack integration example

**Implementation:**
- UI-centric tool examples throughout
- Tool call reduction calculator
- Design quality checklist

### The 10 Commandments

1. Start Simple, Add Complexity Only When Needed
2. Think From the Agent's Point of View
3. Tools Should Mirror UI, Not API
4. Provide Complete Context to Subagents
5. Measure and Justify Complexity
6. Code is a Superpower
7. Minimize Communication Overhead
8. Test From Agent's Perspective
9. Document Everything
10. Iterate Based on Reality

**Full implementation in:** `frontend/src/pages/BestPractices.tsx`

---

## 💰 Cost Breakdown

### Local Development
- **Cost:** $0 (runs on your machine)
- **Resources:** CPU, memory only

### AWS Development Environment
- **Monthly Cost:** $5-20
- **Components:**
  - S3: ~$1 (storage + requests)
  - CloudFront: Free tier covers most usage
  - Lambda: Free tier covers most usage
  - DynamoDB: ~$2-5 (on-demand)
  - API Gateway: Free tier covers most usage
  - CloudWatch: ~$1-3 (logs)

### AWS Production Environment (10K users/day)
- **Monthly Cost:** $125-150
- **Components:**
  - CloudFront: ~$50 (data transfer)
  - Lambda: ~$20 (compute)
  - DynamoDB: ~$30 (reads/writes)
  - API Gateway: ~$20 (requests)
  - S3: ~$5 (storage + requests)
  - Other services: ~$5-15

**Cost Optimization Tips:**
- Enable CloudFront compression
- Use DynamoDB on-demand billing
- Set S3 lifecycle policies
- Use Lambda reserved concurrency
- Enable API Gateway caching

---

## 🔒 Security Features

### Built-In Security

✅ **Encryption at Rest**
- S3 buckets: AWS managed encryption
- DynamoDB tables: AWS managed encryption
- CloudWatch logs: Encrypted

✅ **Encryption in Transit**
- TLS 1.2+ enforced everywhere
- CloudFront HTTPS redirects
- API Gateway HTTPS only

✅ **IAM Best Practices**
- Least privilege policies
- No hardcoded credentials
- Role-based access control

✅ **Network Security**
- S3 bucket policies (no public access)
- CloudFront OAI for S3 access
- API Gateway throttling
- DDoS protection (CloudFront)

✅ **Application Security**
- Security headers (CSP, HSTS, X-Frame-Options)
- CORS configuration
- Input validation
- XSS protection

✅ **Monitoring & Compliance**
- CloudWatch logging
- X-Ray tracing
- CloudTrail integration ready
- Audit logs

### Additional Recommendations

🔒 **For Production:**
- Enable AWS WAF on CloudFront
- Set up AWS Shield (free tier)
- Use KMS for customer-managed keys
- Enable GuardDuty
- Set up AWS Config
- Enable VPC Flow Logs
- Use Secrets Manager for sensitive data

---

## 📈 Monitoring & Observability

### CloudWatch Dashboards

**Metrics to Monitor:**
- API Gateway: Request count, latency, errors
- Lambda: Invocations, duration, errors, throttles
- DynamoDB: Read/write capacity, throttles
- CloudFront: Requests, cache hit ratio, errors
- S3: Bucket size, requests

### CloudWatch Alarms

**Recommended Alarms:**
```
API Gateway 5xx Errors > 10 in 5 minutes
Lambda Errors > 5 in 5 minutes
Lambda Duration > 5000ms
DynamoDB Throttles > 0
CloudFront 5xx Error Rate > 1%
```

### X-Ray Tracing

**Enabled For:**
- API Gateway requests
- Lambda function executions
- DynamoDB calls

**View In:** AWS X-Ray Console → Service Map

### Logs

**CloudWatch Log Groups:**
- `/aws/apigateway/cao-{env}` - API access logs
- `/aws/lambda/cao-{env}-api` - Lambda function logs
- `/aws/codebuild/cao-{env}-*` - Build logs

**Tail Logs:**
```bash
# API Gateway logs
aws logs tail /aws/apigateway/cao-prod --follow

# Lambda logs
aws logs tail /aws/lambda/cao-prod-api --follow
```

---

## 🧪 Testing

### Frontend Testing

```bash
cd frontend

# Lint
npm run lint

# Build
npm run build

# Preview production build
npm run preview
```

### Backend Testing

```bash
# Unit tests
pytest test/

# Integration tests
pytest test/ -m integration

# Coverage
pytest --cov=src test/
```

### Infrastructure Testing

```bash
cd infrastructure

# Synthesize CloudFormation
npm run synth

# View changes
npm run diff

# Run CDK tests
npm test
```

### Load Testing

```bash
# Install Artillery
npm install -g artillery

# Run load test
artillery quick --count 100 --num 10 https://your-api-url/sessions
```

---

## 🐛 Troubleshooting

### Common Issues

**Issue: Frontend can't connect to API**
```bash
# Check CAO server is running
curl http://localhost:9889/sessions

# Check frontend proxy config
cat frontend/vite.config.ts
```

**Issue: CDK deployment fails**
```bash
# Check AWS credentials
aws sts get-caller-identity

# Bootstrap CDK if not done
cdk bootstrap

# Check CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name cao-dev-frontend
```

**Issue: CloudFront serving old content**
```bash
# Create invalidation
aws cloudfront create-invalidation \
  --distribution-id DISTID \
  --paths "/*"
```

**Issue: Lambda timeout**
```bash
# Increase timeout in config.ts
backend: {
  timeout: 60  // seconds
}

# Redeploy
npm run deploy:dev
```

**Issue: DynamoDB throttling**
```bash
# Check metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ThrottledRequests \
  --dimensions Name=TableName,Value=cao-prod-sessions

# Consider provisioned capacity or on-demand increase
```

---

## 📚 Documentation Index

### Core Documentation
- [README.md](README.md) - Project overview and quick start
- [CODEBASE.md](CODEBASE.md) - Codebase architecture

### Frontend
- [frontend/README.md](frontend/README.md) - Frontend setup guide
- [CLOUDSCAPE_UX_GUIDE.md](CLOUDSCAPE_UX_GUIDE.md) - Implementation details

### Infrastructure
- [infrastructure/README.md](infrastructure/README.md) - Complete CDK guide
- [infrastructure/DEPLOYMENT.md](infrastructure/DEPLOYMENT.md) - Quick deploy reference

### Best Practices
- Frontend Best Practices: `frontend/src/pages/BestPractices.tsx`
- The Three Commandments: Throughout frontend pages
- The 10 Commandments: `frontend/src/pages/BestPractices.tsx`

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

Apache-2.0 - See [LICENSE](LICENSE) for details.

---

## 🎯 What's Next?

### Phase 2: Enhanced Features

- [ ] Real-time terminal streaming with WebSockets
- [ ] Advanced metrics and analytics dashboard
- [ ] Workflow builder with drag-and-drop
- [ ] Multi-user collaboration
- [ ] Team dashboards

### Phase 3: AI Integration

- [ ] Smart architecture recommendations
- [ ] Automated tool design analysis
- [ ] Context completeness validation
- [ ] Performance benchmarking

---

## 🙏 Acknowledgments

- **AWS Cloudscape Design System** - For the excellent UI components
- **Anthropic** - For multi-agent orchestration best practices
- **AWS CDK** - For infrastructure as code framework
- **Community** - For feedback and contributions

---

**Built with ❤️ using multi-agent workflow best practices**

🤖 Generated with [Claude Code](https://claude.com/claude-code)
