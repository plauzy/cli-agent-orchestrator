#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { FrontendStack } from '../lib/stacks/frontend-stack';
import { BackendStack } from '../lib/stacks/backend-stack';
import { PipelineStack } from '../lib/stacks/pipeline-stack';
import { getConfig } from '../lib/config';

const app = new cdk.App();

// Get environment from context
const environment = app.node.tryGetContext('environment') || 'dev';
const config = getConfig(environment);

// Add common tags to all resources
const tags = {
  Environment: config.environment,
  Project: 'CLIAgentOrchestrator',
  ManagedBy: 'CDK',
  Repository: 'cli-agent-orchestrator'
};

// Stack naming convention: cao-{environment}-{stack}
const stackPrefix = `cao-${config.environment}`;

// Backend Stack (API Gateway + Lambda)
const backendStack = new BackendStack(app, `${stackPrefix}-backend`, {
  stackName: `${stackPrefix}-backend`,
  description: 'Backend API for CLI Agent Orchestrator',
  env: {
    account: config.account,
    region: config.region
  },
  tags,
  config
});

// Frontend Stack (S3 + CloudFront)
const frontendStack = new FrontendStack(app, `${stackPrefix}-frontend`, {
  stackName: `${stackPrefix}-frontend`,
  description: 'Frontend hosting for CLI Agent Orchestrator',
  env: {
    account: config.account,
    region: config.region
  },
  tags,
  config,
  apiUrl: backendStack.apiUrl
});

// CI/CD Pipeline Stack
if (config.environment === 'prod') {
  new PipelineStack(app, `${stackPrefix}-pipeline`, {
    stackName: `${stackPrefix}-pipeline`,
    description: 'CI/CD Pipeline for CLI Agent Orchestrator',
    env: {
      account: config.account,
      region: config.region
    },
    tags,
    config
  });
}

app.synth();
