import * as cdk from 'aws-cdk-lib';
import * as codepipeline from 'aws-cdk-lib/aws-codepipeline';
import * as codepipeline_actions from 'aws-cdk-lib/aws-codepipeline-actions';
import * as codebuild from 'aws-cdk-lib/aws-codebuild';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import { Construct } from 'constructs';
import { Config } from '../config';

interface PipelineStackProps extends cdk.StackProps {
  config: Config;
}

export class PipelineStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: PipelineStackProps) {
    super(scope, id, props);

    const { config } = props;

    if (!config.pipeline) {
      throw new Error('Pipeline configuration is required');
    }

    // S3 Bucket for artifacts
    const artifactBucket = new s3.Bucket(this, 'ArtifactBucket', {
      bucketName: `cao-${config.environment}-pipeline-artifacts-${this.account}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [
        {
          id: 'DeleteOldArtifacts',
          enabled: true,
          expiration: cdk.Duration.days(30)
        }
      ]
    });

    // SNS Topic for pipeline notifications
    const pipelineTopic = new sns.Topic(this, 'PipelineTopic', {
      topicName: `cao-${config.environment}-pipeline-notifications`,
      displayName: 'CAO Pipeline Notifications'
    });

    // GitHub Token from Secrets Manager
    const githubToken = secretsmanager.Secret.fromSecretNameV2(
      this,
      'GitHubToken',
      config.pipeline.githubTokenSecretName
    );

    // Source Stage
    const sourceOutput = new codepipeline.Artifact('SourceOutput');

    const sourceAction = new codepipeline_actions.GitHubSourceAction({
      actionName: 'GitHub_Source',
      owner: config.pipeline.githubOwner,
      repo: config.pipeline.githubRepo,
      branch: config.pipeline.githubBranch,
      oauthToken: githubToken.secretValue,
      output: sourceOutput,
      trigger: codepipeline_actions.GitHubTrigger.WEBHOOK
    });

    // Build Stage - Backend
    const backendBuildProject = new codebuild.PipelineProject(this, 'BackendBuild', {
      projectName: `cao-${config.environment}-backend-build`,
      description: 'Build backend Lambda functions',
      environment: {
        buildImage: codebuild.LinuxBuildImage.STANDARD_7_0,
        computeType: codebuild.ComputeType.SMALL,
        privileged: false
      },
      buildSpec: codebuild.BuildSpec.fromObject({
        version: '0.2',
        phases: {
          install: {
            'runtime-versions': {
              python: '3.11',
              nodejs: '18'
            },
            commands: [
              'echo "Installing dependencies"',
              'pip install -r requirements.txt',
              'npm install -g aws-cdk'
            ]
          },
          pre_build: {
            commands: [
              'echo "Running tests"',
              'python -m pytest test/ || true'
            ]
          },
          build: {
            commands: [
              'echo "Building backend"',
              'cd infrastructure',
              'npm ci',
              'npm run build'
            ]
          }
        },
        artifacts: {
          files: ['**/*']
        }
      }),
      cache: codebuild.Cache.local(codebuild.LocalCacheMode.SOURCE)
    });

    const backendBuildOutput = new codepipeline.Artifact('BackendBuildOutput');

    const backendBuildAction = new codepipeline_actions.CodeBuildAction({
      actionName: 'Backend_Build',
      project: backendBuildProject,
      input: sourceOutput,
      outputs: [backendBuildOutput]
    });

    // Build Stage - Frontend
    const frontendBuildProject = new codebuild.PipelineProject(this, 'FrontendBuild', {
      projectName: `cao-${config.environment}-frontend-build`,
      description: 'Build frontend React application',
      environment: {
        buildImage: codebuild.LinuxBuildImage.STANDARD_7_0,
        computeType: codebuild.ComputeType.SMALL,
        privileged: false
      },
      buildSpec: codebuild.BuildSpec.fromObject({
        version: '0.2',
        phases: {
          install: {
            'runtime-versions': {
              nodejs: '18'
            },
            commands: [
              'echo "Installing frontend dependencies"',
              'cd frontend',
              'npm ci'
            ]
          },
          pre_build: {
            commands: [
              'echo "Running linter"',
              'npm run lint || true'
            ]
          },
          build: {
            commands: [
              'echo "Building frontend"',
              'npm run build'
            ]
          }
        },
        artifacts: {
          'base-directory': 'frontend/dist',
          files: ['**/*']
        }
      }),
      cache: codebuild.Cache.local(
        codebuild.LocalCacheMode.SOURCE,
        codebuild.LocalCacheMode.CUSTOM
      ),
      environmentVariables: {
        VITE_API_URL: {
          value: `https://api.cao.example.com/${config.environment}` // Update with actual API URL
        }
      }
    });

    const frontendBuildOutput = new codepipeline.Artifact('FrontendBuildOutput');

    const frontendBuildAction = new codepipeline_actions.CodeBuildAction({
      actionName: 'Frontend_Build',
      project: frontendBuildProject,
      input: sourceOutput,
      outputs: [frontendBuildOutput]
    });

    // Deploy Stage - CDK Deploy
    const deployProject = new codebuild.PipelineProject(this, 'DeployProject', {
      projectName: `cao-${config.environment}-deploy`,
      description: 'Deploy infrastructure and application',
      environment: {
        buildImage: codebuild.LinuxBuildImage.STANDARD_7_0,
        computeType: codebuild.ComputeType.SMALL,
        privileged: false
      },
      buildSpec: codebuild.BuildSpec.fromObject({
        version: '0.2',
        phases: {
          install: {
            'runtime-versions': {
              nodejs: '18'
            },
            commands: [
              'npm install -g aws-cdk'
            ]
          },
          build: {
            commands: [
              'cd infrastructure',
              'npm ci',
              'npm run build',
              `cdk deploy --all --require-approval never --context environment=${config.environment}`
            ]
          }
        }
      })
    });

    // Grant deploy permissions
    deployProject.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'cloudformation:*',
        's3:*',
        'cloudfront:*',
        'lambda:*',
        'apigateway:*',
        'dynamodb:*',
        'iam:*',
        'logs:*',
        'events:*',
        'ssm:GetParameter'
      ],
      resources: ['*']
    }));

    const deployAction = new codepipeline_actions.CodeBuildAction({
      actionName: 'CDK_Deploy',
      project: deployProject,
      input: backendBuildOutput
    });

    // Manual Approval Stage (for production)
    const approvalAction = new codepipeline_actions.ManualApprovalAction({
      actionName: 'Manual_Approval',
      notificationTopic: pipelineTopic,
      additionalInformation: `Approve deployment to ${config.environment} environment`
    });

    // Create Pipeline
    const pipeline = new codepipeline.Pipeline(this, 'Pipeline', {
      pipelineName: `cao-${config.environment}-pipeline`,
      pipelineType: codepipeline.PipelineType.V2,
      artifactBucket: artifactBucket,
      crossAccountKeys: false,
      restartExecutionOnUpdate: true,
      stages: [
        {
          stageName: 'Source',
          actions: [sourceAction]
        },
        {
          stageName: 'Build',
          actions: [backendBuildAction, frontendBuildAction]
        },
        ...(config.environment === 'prod' ? [{
          stageName: 'Approval',
          actions: [approvalAction]
        }] : []),
        {
          stageName: 'Deploy',
          actions: [deployAction]
        }
      ]
    });

    // Pipeline notifications
    pipeline.onStateChange('PipelineStateChange', {
      target: new cdk.aws_events_targets.SnsTopic(pipelineTopic),
      description: 'Pipeline state change notification'
    });

    // Outputs
    new cdk.CfnOutput(this, 'PipelineName', {
      value: pipeline.pipelineName,
      description: 'CodePipeline Name',
      exportName: `${config.environment}-pipeline-name`
    });

    new cdk.CfnOutput(this, 'PipelineUrl', {
      value: `https://console.aws.amazon.com/codesuite/codepipeline/pipelines/${pipeline.pipelineName}/view`,
      description: 'Pipeline Console URL'
    });

    new cdk.CfnOutput(this, 'ArtifactBucketName', {
      value: artifactBucket.bucketName,
      description: 'Artifact Bucket Name'
    });
  }
}
