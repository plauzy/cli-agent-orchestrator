import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';
import { Config } from '../config';
import * as path from 'path';

interface BackendStackProps extends cdk.StackProps {
  config: Config;
}

export class BackendStack extends cdk.Stack {
  public readonly apiUrl: string;
  public readonly api: apigateway.RestApi;

  constructor(scope: Construct, id: string, props: BackendStackProps) {
    super(scope, id, props);

    const { config } = props;

    // DynamoDB Table for Terminal State
    const terminalTable = new dynamodb.Table(this, 'TerminalTable', {
      tableName: `cao-${config.environment}-terminals`,
      partitionKey: {
        name: 'id',
        type: dynamodb.AttributeType.STRING
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: config.environment === 'prod',
      removalPolicy: config.environment === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
      timeToLiveAttribute: 'ttl'
    });

    // Add GSI for session queries
    terminalTable.addGlobalSecondaryIndex({
      indexName: 'SessionIndex',
      partitionKey: {
        name: 'session_id',
        type: dynamodb.AttributeType.STRING
      },
      sortKey: {
        name: 'created_at',
        type: dynamodb.AttributeType.STRING
      },
      projectionType: dynamodb.ProjectionType.ALL
    });

    // DynamoDB Table for Sessions
    const sessionTable = new dynamodb.Table(this, 'SessionTable', {
      tableName: `cao-${config.environment}-sessions`,
      partitionKey: {
        name: 'id',
        type: dynamodb.AttributeType.STRING
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: config.environment === 'prod',
      removalPolicy: config.environment === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY
    });

    // Lambda Layer for shared dependencies
    const pythonLayer = new lambda.LayerVersion(this, 'PythonLayer', {
      layerVersionName: `cao-${config.environment}-python-deps`,
      code: lambda.Code.fromAsset(path.join(__dirname, '../../../'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: [
            'bash',
            '-c',
            [
              'pip install -r requirements.txt -t /asset-output/python',
              'cd /asset-output',
              'find . -type d -name __pycache__ -exec rm -rf {} +',
              'find . -type f -name "*.pyc" -delete'
            ].join(' && ')
          ]
        }
      }),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Python dependencies for CAO backend'
    });

    // Lambda Function for API
    const apiHandler = new lambda.Function(this, 'ApiHandler', {
      functionName: `cao-${config.environment}-api`,
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda/api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: [
            'bash',
            '-c',
            [
              'cp -r /asset-input/* /asset-output/',
              'cd /asset-output',
              'find . -type d -name __pycache__ -exec rm -rf {} +',
              'find . -type f -name "*.pyc" -delete'
            ].join(' && ')
          ]
        }
      }),
      layers: [pythonLayer],
      memorySize: config.backend.memorySize,
      timeout: cdk.Duration.seconds(config.backend.timeout),
      environment: {
        ...config.backend.environment,
        TERMINAL_TABLE_NAME: terminalTable.tableName,
        SESSION_TABLE_NAME: sessionTable.tableName,
        POWERTOOLS_SERVICE_NAME: 'cao-api',
        POWERTOOLS_METRICS_NAMESPACE: `cao-${config.environment}`,
        LOG_LEVEL: config.backend.environment.LOG_LEVEL
      },
      tracing: lambda.Tracing.ACTIVE,
      logRetention: config.environment === 'prod'
        ? logs.RetentionDays.ONE_MONTH
        : logs.RetentionDays.ONE_WEEK,
      reservedConcurrentExecutions: config.environment === 'prod' ? 10 : undefined
    });

    // Grant DynamoDB permissions
    terminalTable.grantReadWriteData(apiHandler);
    sessionTable.grantReadWriteData(apiHandler);

    // API Gateway
    const logGroup = new logs.LogGroup(this, 'ApiLogs', {
      logGroupName: `/aws/apigateway/cao-${config.environment}`,
      retention: config.environment === 'prod'
        ? logs.RetentionDays.ONE_MONTH
        : logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    this.api = new apigateway.RestApi(this, 'Api', {
      restApiName: `cao-${config.environment}-api`,
      description: `CLI Agent Orchestrator API - ${config.environment}`,
      deployOptions: {
        stageName: config.environment,
        tracingEnabled: true,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: config.environment !== 'prod',
        metricsEnabled: true,
        accessLogDestination: new apigateway.LogGroupLogDestination(logGroup),
        accessLogFormat: apigateway.AccessLogFormat.jsonWithStandardFields({
          caller: true,
          httpMethod: true,
          ip: true,
          protocol: true,
          requestTime: true,
          resourcePath: true,
          responseLength: true,
          status: true,
          user: true
        }),
        throttlingBurstLimit: config.environment === 'prod' ? 100 : 50,
        throttlingRateLimit: config.environment === 'prod' ? 100 : 50
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          'Content-Type',
          'X-Amz-Date',
          'Authorization',
          'X-Api-Key',
          'X-Amz-Security-Token'
        ],
        maxAge: cdk.Duration.days(1)
      },
      cloudWatchRole: true,
      endpointConfiguration: {
        types: [apigateway.EndpointType.REGIONAL]
      }
    });

    // API Gateway Integration
    const integration = new apigateway.LambdaIntegration(apiHandler, {
      proxy: true,
      allowTestInvoke: true
    });

    // API Routes
    const sessions = this.api.root.addResource('sessions');
    sessions.addMethod('GET', integration);
    sessions.addMethod('POST', integration);

    const session = sessions.addResource('{sessionId}');
    session.addMethod('GET', integration);
    session.addMethod('DELETE', integration);

    const terminals = session.addResource('terminals');
    terminals.addMethod('GET', integration);
    terminals.addMethod('POST', integration);

    const terminal = this.api.root.addResource('terminals').addResource('{terminalId}');
    terminal.addMethod('GET', integration);
    terminal.addMethod('DELETE', integration);

    const terminalInput = terminal.addResource('input');
    terminalInput.addMethod('POST', integration);

    const terminalOutput = terminal.addResource('output');
    terminalOutput.addMethod('GET', integration);

    // API Key for external access (optional)
    const apiKey = this.api.addApiKey('ApiKey', {
      apiKeyName: `cao-${config.environment}-key`,
      description: `API Key for CAO ${config.environment}`,
      enabled: true
    });

    const usagePlan = this.api.addUsagePlan('UsagePlan', {
      name: `cao-${config.environment}-usage`,
      description: `Usage plan for CAO ${config.environment}`,
      throttle: {
        rateLimit: config.environment === 'prod' ? 100 : 50,
        burstLimit: config.environment === 'prod' ? 200 : 100
      },
      quota: {
        limit: config.environment === 'prod' ? 100000 : 10000,
        period: apigateway.Period.DAY
      }
    });

    usagePlan.addApiKey(apiKey);
    usagePlan.addApiStage({
      stage: this.api.deploymentStage
    });

    this.apiUrl = this.api.url;

    // Outputs
    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: this.apiUrl,
      description: 'API Gateway Endpoint',
      exportName: `${config.environment}-api-endpoint`
    });

    new cdk.CfnOutput(this, 'ApiKeyId', {
      value: apiKey.keyId,
      description: 'API Key ID',
      exportName: `${config.environment}-api-key-id`
    });

    new cdk.CfnOutput(this, 'TerminalTableName', {
      value: terminalTable.tableName,
      description: 'Terminal DynamoDB Table',
      exportName: `${config.environment}-terminal-table`
    });

    new cdk.CfnOutput(this, 'SessionTableName', {
      value: sessionTable.tableName,
      description: 'Session DynamoDB Table',
      exportName: `${config.environment}-session-table`
    });
  }
}
