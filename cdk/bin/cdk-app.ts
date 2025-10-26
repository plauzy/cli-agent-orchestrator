#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { CAOInfrastructureStack } from '../lib/cao-infrastructure-stack';
import { CAONetworkStack } from '../lib/cao-network-stack';
import { CAOAuthStack } from '../lib/cao-auth-stack';

const app = new cdk.App();

// Network stack - VPC, subnets, security groups
const networkStack = new CAONetworkStack(app, 'CAONetworkStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  description: 'Network infrastructure for CLI Agent Orchestrator'
});

// Auth stack - Cognito user pools and identity pools
const authStack = new CAOAuthStack(app, 'CAOAuthStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  description: 'Authentication and authorization for CLI Agent Orchestrator'
});

// Main infrastructure stack - ECS, ALB, Auto Scaling
const infrastructureStack = new CAOInfrastructureStack(app, 'CAOInfrastructureStack', {
  vpc: networkStack.vpc,
  userPool: authStack.userPool,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  description: 'Main infrastructure for CLI Agent Orchestrator'
});

infrastructureStack.addDependency(networkStack);
infrastructureStack.addDependency(authStack);

app.synth();
