# AWS CDK Infrastructure Deployment Guide

Quick reference for common deployment tasks.

## Quick Commands

```bash
# Install dependencies
cd infrastructure && npm install

# View infrastructure changes
npm run diff

# Deploy to dev
npm run deploy:dev

# Deploy to production
npm run deploy:prod

# Destroy all resources
npm run destroy
```

## First-Time Setup

1. **Configure AWS credentials**
   ```bash
   aws configure
   # Or use SSO
   aws sso login --profile your-profile
   ```

2. **Bootstrap CDK** (one-time per account/region)
   ```bash
   cdk bootstrap aws://ACCOUNT-ID/REGION
   ```

3. **Configure environments**
   - Edit `infrastructure/lib/config.ts`
   - Update account ID, region, domain settings

4. **Deploy**
   ```bash
   cd infrastructure
   npm install
   npm run deploy:dev
   ```

## Environment Configuration

### Development
- No custom domain
- Lower resource limits
- Aggressive cleanup policies
- No manual approval in pipeline

### Production
- Custom domain support
- Higher resource limits
- Data retention policies
- Manual approval required
- Full monitoring and alarms

## Custom Domain Setup

1. **Request ACM certificate** (in us-east-1 for CloudFront):
   ```bash
   aws acm request-certificate \
     --domain-name cao.example.com \
     --validation-method DNS \
     --region us-east-1
   ```

2. **Validate certificate** via DNS records

3. **Update config.ts**:
   ```typescript
   domainName: 'cao.example.com',
   certificateArn: 'arn:aws:acm:...',
   hostedZoneId: 'Z1234...'
   ```

4. **Redeploy** - Route53 records created automatically

## Monitoring

### View Logs
```bash
# API Gateway logs
aws logs tail /aws/apigateway/cao-prod --follow

# Lambda logs
aws logs tail /aws/lambda/cao-prod-api --follow

# CodeBuild logs
aws logs tail /aws/codebuild/cao-prod-frontend-build --follow
```

### CloudWatch Dashboard
- Navigate to CloudWatch Console
- Select Dashboards
- View cao-{environment} dashboard

### X-Ray Traces
- Navigate to X-Ray Console
- View service map
- Analyze traces for performance issues

## Troubleshooting

### CloudFront Cache Issues
```bash
# Invalidate cache
aws cloudfront create-invalidation \
  --distribution-id E1234567890ABC \
  --paths "/*"
```

### API Gateway CORS Errors
- Check API Gateway CORS configuration
- Verify CloudFront origin settings
- Check Lambda response headers

### DynamoDB Throttling
- Check CloudWatch metrics
- Increase on-demand limits
- Or switch to provisioned capacity

### Lambda Errors
```bash
# View recent errors
aws logs filter-pattern \
  --log-group-name /aws/lambda/cao-prod-api \
  --filter-pattern "ERROR"
```

## Security Checklist

- [ ] AWS credentials secured (not in code)
- [ ] API keys rotated regularly
- [ ] CloudWatch alarms configured
- [ ] DynamoDB encryption enabled
- [ ] S3 buckets not public
- [ ] CloudFront HTTPS enforced
- [ ] Lambda in VPC (if needed)
- [ ] WAF rules configured (prod)
- [ ] Secrets in Secrets Manager
- [ ] CloudTrail logging enabled

## Cost Management

### Monitor Costs
```bash
# Get current month costs
aws ce get-cost-and-usage \
  --time-period Start=2025-10-01,End=2025-10-31 \
  --granularity MONTHLY \
  --metrics BlendedCost
```

### Cost Optimization
- Enable S3 lifecycle policies
- Use CloudFront compression
- Set Lambda memory appropriately
- Use DynamoDB on-demand billing
- Delete unused resources

## Backup & Disaster Recovery

### DynamoDB Backups
```bash
# Create on-demand backup
aws dynamodb create-backup \
  --table-name cao-prod-sessions \
  --backup-name cao-sessions-backup-$(date +%Y%m%d)
```

### S3 Versioning
- Enabled automatically
- Old versions deleted after 30 days

### CloudFormation Stacks
- Template stored in cdk.out/
- Can redeploy from template

## Support

- AWS Support: https://console.aws.amazon.com/support
- CDK Issues: https://github.com/aws/aws-cdk/issues
- Project Issues: https://github.com/awslabs/cli-agent-orchestrator/issues
